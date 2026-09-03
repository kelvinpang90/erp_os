"""Unit tests for the MyInvois UBL 2.1 JSON document builder.

Covers:
  1. Envelope — namespaces, Invoice root, type code, version
  2. Party mapping — TIN/BRN/SST scheme IDs, state codes, country alpha-3
  3. Tax — per-line category + document-level TaxSubtotal aggregation
  4. Monetary totals — line extension, allowance, payable
  5. Foreign currency — TaxExchangeRate block
  6. Credit note — InvoiceTypeCode 02 + BillingReference
  7. Code-list lookups and their fallbacks
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.integrations.myinvois import InvoicePayload, LinePayload, PartyInfo
from app.integrations.myinvois_codes import (
    STATE_NOT_APPLICABLE,
    TAX_TYPE_NOT_APPLICABLE,
    UOM_FALLBACK,
    country_alpha3,
    invoice_type_code,
    state_code,
    tax_type_code,
    uom_code,
)
from app.integrations.myinvois_ubl import build_invoice_document


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _seller() -> PartyInfo:
    return PartyInfo(
        tin="C1234567890",
        name="Demo Malaysia Sdn Bhd",
        registration_no="202001012345",
        sst_no="A10-1234-56789012",
        msic_code="46510",
        address_line1="Level 12, Menara Demo",
        address_line2="Jalan Ampang",
        city="Kuala Lumpur",
        state="WP Kuala Lumpur",
        postcode="50450",
        country="MY",
        phone="+60312345678",
        email="billing@demo.my",
    )


def _buyer() -> PartyInfo:
    return PartyInfo(
        tin="C9876543210",
        name="Penang Retail Sdn Bhd",
        registration_no="201801054321",
        city="George Town",
        state="Penang",
        postcode="10200",
        country="MY",
        phone="+6045551234",
        email="ap@penangretail.my",
    )


def _line(
    line_no: int = 1,
    *,
    tax_type: str = "SALES_TAX",
    rate: str = "10.00",
    net: str = "1000.00",
    tax: str = "100.00",
    discount: str = "0",
) -> LinePayload:
    return LinePayload(
        line_no=line_no,
        description=f"Widget {line_no}",
        qty=Decimal("10"),
        uom_code="PCS",
        unit_price_excl_tax=Decimal("100.00"),
        tax_type=tax_type,
        tax_rate_percent=Decimal(rate),
        tax_amount=Decimal(tax),
        line_total_excl_tax=Decimal(net),
        discount_amount=Decimal(discount),
    )


def _payload(**overrides) -> InvoicePayload:
    lines = overrides.pop("lines", (_line(),))
    base = dict(
        document_no="INV-2026-00042",
        invoice_type="INVOICE",
        business_date="2026-09-01",
        currency="MYR",
        exchange_rate=Decimal("1"),
        seller_tin="C1234567890",
        seller_name="Demo Malaysia Sdn Bhd",
        seller_msic_code="46510",
        seller_sst_no="A10-1234-56789012",
        buyer_tin="C9876543210",
        buyer_name="Penang Retail Sdn Bhd",
        buyer_msic_code=None,
        subtotal_excl_tax=Decimal("1000.00"),
        tax_amount=Decimal("100.00"),
        total_incl_tax=Decimal("1100.00"),
        line_count=len(lines),
        seller=_seller(),
        buyer=_buyer(),
        lines=lines,
        issue_time="08:30:00Z",
    )
    base.update(overrides)
    return InvoicePayload(**base)


def _invoice(doc: dict) -> dict:
    return doc["Invoice"][0]


def _val(node: list) -> object:
    return node[0]["_"]


# ── 1. Envelope ──────────────────────────────────────────────────────────────


class TestEnvelope:
    def test_namespaces_and_root(self):
        doc = build_invoice_document(_payload())
        assert doc["_D"] == "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
        assert doc["_A"].endswith("CommonAggregateComponents-2")
        assert doc["_B"].endswith("CommonBasicComponents-2")
        assert isinstance(doc["Invoice"], list) and len(doc["Invoice"]) == 1

    def test_header_fields(self):
        inv = _invoice(build_invoice_document(_payload()))
        assert _val(inv["ID"]) == "INV-2026-00042"
        assert _val(inv["IssueDate"]) == "2026-09-01"
        assert _val(inv["IssueTime"]) == "08:30:00Z"
        assert _val(inv["DocumentCurrencyCode"]) == "MYR"
        # Tax currency is always MYR regardless of document currency.
        assert _val(inv["TaxCurrencyCode"]) == "MYR"

    def test_invoice_type_carries_version(self):
        inv = _invoice(build_invoice_document(_payload()))
        assert inv["InvoiceTypeCode"][0] == {"_": "01", "listVersionID": "1.0"}

    def test_issue_time_defaults_when_absent(self):
        inv = _invoice(build_invoice_document(_payload(issue_time=None)))
        assert _val(inv["IssueTime"]).endswith("Z")

    def test_no_billing_reference_on_plain_invoice(self):
        assert "BillingReference" not in _invoice(build_invoice_document(_payload()))

    def test_no_exchange_rate_for_local_currency(self):
        assert "TaxExchangeRate" not in _invoice(build_invoice_document(_payload()))


# ── 2. Parties ───────────────────────────────────────────────────────────────


class TestParties:
    def test_supplier_identification_scheme_ids(self):
        inv = _invoice(build_invoice_document(_payload()))
        party = inv["AccountingSupplierParty"][0]["Party"][0]
        ids = {
            entry["ID"][0]["schemeID"]: entry["ID"][0]["_"]
            for entry in party["PartyIdentification"]
        }
        assert ids["TIN"] == "C1234567890"
        assert ids["BRN"] == "202001012345"
        assert ids["SST"] == "A10-1234-56789012"
        assert ids["TTX"] == "NA"

    def test_supplier_has_msic_but_buyer_does_not(self):
        inv = _invoice(build_invoice_document(_payload()))
        seller = inv["AccountingSupplierParty"][0]["Party"][0]
        buyer = inv["AccountingCustomerParty"][0]["Party"][0]
        assert _val(seller["IndustryClassificationCode"]) == "46510"
        assert "IndustryClassificationCode" not in buyer

    def test_msic_name_is_the_industry_description_not_the_company(self):
        inv = _invoice(build_invoice_document(_payload()))
        code = inv["AccountingSupplierParty"][0]["Party"][0]["IndustryClassificationCode"][0]
        assert code["_"] == "46510"
        # No description stored on the org — must not leak the company name.
        assert code["name"] == "NOT APPLICABLE"

    def test_msic_description_is_used_when_available(self):
        seller = PartyInfo(
            tin="C1",
            name="Demo Sdn Bhd",
            msic_code="46510",
            msic_description="Wholesale of computer hardware",
        )
        inv = _invoice(build_invoice_document(_payload(seller=seller)))
        code = inv["AccountingSupplierParty"][0]["Party"][0]["IndustryClassificationCode"][0]
        assert code["name"] == "Wholesale of computer hardware"

    def test_supplier_msic_falls_back_when_unset(self):
        payload = _payload(seller=PartyInfo(tin="C1", name="No MSIC Sdn Bhd"))
        inv = _invoice(build_invoice_document(payload))
        code = inv["AccountingSupplierParty"][0]["Party"][0]["IndustryClassificationCode"][0]
        assert code["_"] == "00000"
        assert code["name"] == "NOT APPLICABLE"

    def test_postal_address_state_and_country(self):
        inv = _invoice(build_invoice_document(_payload()))
        addr = inv["AccountingCustomerParty"][0]["Party"][0]["PostalAddress"][0]
        assert _val(addr["CountrySubentityCode"]) == "07"       # Penang
        assert _val(addr["CityName"]) == "George Town"
        country = addr["Country"][0]["IdentificationCode"][0]
        assert country["_"] == "MYS"
        assert country["listID"] == "ISO3166-1"

    def test_address_lines_collapse_to_na_when_empty(self):
        payload = _payload(buyer=PartyInfo(tin="C2", name="Walk-in"))
        inv = _invoice(build_invoice_document(payload))
        addr = inv["AccountingCustomerParty"][0]["Party"][0]["PostalAddress"][0]
        assert [_val(entry["Line"]) for entry in addr["AddressLine"]] == ["NA"]

    def test_missing_contact_becomes_na(self):
        payload = _payload(buyer=PartyInfo(tin="C2", name="Walk-in"))
        inv = _invoice(build_invoice_document(payload))
        contact = inv["AccountingCustomerParty"][0]["Party"][0]["Contact"][0]
        assert _val(contact["Telephone"]) == "NA"
        assert _val(contact["ElectronicMail"]) == "NA"

    def test_party_falls_back_to_flat_fields(self):
        """A payload built without the rich structures still yields a document."""
        inv = _invoice(build_invoice_document(_payload(seller=None, buyer=None)))
        seller = inv["AccountingSupplierParty"][0]["Party"][0]
        assert _val(seller["PartyLegalEntity"][0]["RegistrationName"]) == (
            "Demo Malaysia Sdn Bhd"
        )
        assert seller["PartyIdentification"][0]["ID"][0]["_"] == "C1234567890"


# ── 3. Tax ───────────────────────────────────────────────────────────────────


class TestTax:
    def test_line_tax_category_carries_percent(self):
        inv = _invoice(build_invoice_document(_payload()))
        subtotal = inv["InvoiceLine"][0]["TaxTotal"][0]["TaxSubtotal"][0]
        category = subtotal["TaxCategory"][0]
        assert _val(category["ID"]) == "01"                     # Sales Tax
        assert category["Percent"][0]["_"] == 10.0
        scheme = category["TaxScheme"][0]["ID"][0]
        assert scheme["_"] == "OTH"
        assert scheme["schemeID"] == "UN/ECE 5153"

    def test_document_tax_totals_group_by_tax_type(self):
        lines = (
            _line(1, tax_type="SALES_TAX", net="1000.00", tax="100.00"),
            _line(2, tax_type="SALES_TAX", net="500.00", tax="50.00"),
            _line(3, tax_type="SERVICE_TAX", rate="6.00", net="200.00", tax="12.00"),
        )
        payload = _payload(
            lines=lines,
            subtotal_excl_tax=Decimal("1700.00"),
            tax_amount=Decimal("162.00"),
            total_incl_tax=Decimal("1862.00"),
        )
        inv = _invoice(build_invoice_document(payload))
        tax_total = inv["TaxTotal"][0]
        assert tax_total["TaxAmount"][0]["_"] == 162.0

        by_code = {
            _val(sub["TaxCategory"][0]["ID"]): sub for sub in tax_total["TaxSubtotal"]
        }
        assert by_code["01"]["TaxableAmount"][0]["_"] == 1500.0
        assert by_code["01"]["TaxAmount"][0]["_"] == 150.0
        assert by_code["02"]["TaxableAmount"][0]["_"] == 200.0
        assert by_code["02"]["TaxAmount"][0]["_"] == 12.0

    def test_exempt_lines_carry_an_exemption_reason(self):
        payload = _payload(
            lines=(_line(1, tax_type="EXEMPT", rate="0.00", net="300.00", tax="0"),),
            subtotal_excl_tax=Decimal("300.00"),
            tax_amount=Decimal("0"),
            total_incl_tax=Decimal("300.00"),
        )
        inv = _invoice(build_invoice_document(payload))
        category = inv["TaxTotal"][0]["TaxSubtotal"][0]["TaxCategory"][0]
        assert _val(category["ID"]) == "E"
        assert "TaxExemptionReason" in category


# ── 4. Lines and monetary totals ─────────────────────────────────────────────


class TestLinesAndTotals:
    def test_line_shape(self):
        inv = _invoice(build_invoice_document(_payload()))
        line = inv["InvoiceLine"][0]
        assert _val(line["ID"]) == "1"
        assert line["InvoicedQuantity"][0] == {"_": 10.0, "unitCode": "C62"}
        assert line["LineExtensionAmount"][0] == {"_": 1000.0, "currencyID": "MYR"}
        assert line["Price"][0]["PriceAmount"][0]["_"] == 100.0
        assert line["ItemPriceExtension"][0]["Amount"][0]["_"] == 1000.0
        classification = line["Item"][0]["CommodityClassification"][0][
            "ItemClassificationCode"
        ][0]
        assert classification == {"_": "022", "listID": "CLASS"}

    def test_line_discount_emits_allowance_charge(self):
        payload = _payload(lines=(_line(1, discount="25.00"),))
        line = _invoice(build_invoice_document(payload))["InvoiceLine"][0]
        allowance = line["AllowanceCharge"][0]
        assert allowance["ChargeIndicator"][0]["_"] is False
        assert allowance["Amount"][0]["_"] == 25.0

    def test_no_allowance_charge_without_discount(self):
        line = _invoice(build_invoice_document(_payload()))["InvoiceLine"][0]
        assert "AllowanceCharge" not in line

    def test_monetary_totals(self):
        inv = _invoice(build_invoice_document(_payload()))
        totals = inv["LegalMonetaryTotal"][0]
        assert totals["LineExtensionAmount"][0]["_"] == 1000.0
        assert totals["TaxExclusiveAmount"][0]["_"] == 1000.0
        assert totals["TaxInclusiveAmount"][0]["_"] == 1100.0
        assert totals["PayableAmount"][0]["_"] == 1100.0
        assert "AllowanceTotalAmount" not in totals

    def test_document_discount_emits_allowance_total(self):
        inv = _invoice(build_invoice_document(_payload(discount_amount=Decimal("50"))))
        assert inv["LegalMonetaryTotal"][0]["AllowanceTotalAmount"][0]["_"] == 50.0

    def test_amounts_round_half_up_to_two_places(self):
        payload = _payload(
            lines=(_line(1, net="1000.005", tax="100.004"),),
            subtotal_excl_tax=Decimal("1000.005"),
            tax_amount=Decimal("100.004"),
            total_incl_tax=Decimal("1100.009"),
        )
        totals = _invoice(build_invoice_document(payload))["LegalMonetaryTotal"][0]
        assert totals["TaxExclusiveAmount"][0]["_"] == 1000.01
        assert totals["TaxInclusiveAmount"][0]["_"] == 1100.01

    def test_lines_preserve_order(self):
        payload = _payload(lines=(_line(1), _line(2), _line(3)))
        inv = _invoice(build_invoice_document(payload))
        assert [_val(ln["ID"]) for ln in inv["InvoiceLine"]] == ["1", "2", "3"]


# ── 5. Foreign currency ──────────────────────────────────────────────────────


class TestForeignCurrency:
    def test_exchange_rate_block(self):
        payload = _payload(currency="USD", exchange_rate=Decimal("4.4500"))
        inv = _invoice(build_invoice_document(payload))
        rate = inv["TaxExchangeRate"][0]
        assert _val(rate["SourceCurrencyCode"]) == "USD"
        assert _val(rate["TargetCurrencyCode"]) == "MYR"
        assert rate["CalculationRate"][0]["_"] == 4.45

    def test_amounts_use_document_currency(self):
        payload = _payload(currency="USD", exchange_rate=Decimal("4.45"))
        inv = _invoice(build_invoice_document(payload))
        assert inv["LegalMonetaryTotal"][0]["PayableAmount"][0]["currencyID"] == "USD"
        assert _val(inv["TaxCurrencyCode"]) == "MYR"


# ── 6. Credit note ───────────────────────────────────────────────────────────


class TestCreditNote:
    def test_type_code_and_billing_reference(self):
        payload = _payload(
            invoice_type="CREDIT_NOTE",
            document_no="CN-2026-00007",
            original_uin="F9ABCDEF1234567890",
            original_document_no="INV-2026-00042",
        )
        inv = _invoice(build_invoice_document(payload))
        assert inv["InvoiceTypeCode"][0]["_"] == "02"
        ref = inv["BillingReference"][0]["InvoiceDocumentReference"][0]
        assert _val(ref["ID"]) == "INV-2026-00042"
        assert _val(ref["UUID"]) == "F9ABCDEF1234567890"

    def test_billing_reference_tolerates_missing_uin(self):
        payload = _payload(
            invoice_type="CREDIT_NOTE", original_document_no="INV-2026-00042"
        )
        ref = _invoice(build_invoice_document(payload))["BillingReference"][0][
            "InvoiceDocumentReference"
        ][0]
        assert _val(ref["UUID"]) == "NA"


# ── 7. Code lists ────────────────────────────────────────────────────────────


class TestCodeLists:
    @pytest.mark.parametrize(
        "state,expected",
        [
            ("Selangor", "10"),
            ("selangor", "10"),
            ("  Penang  ", "07"),
            ("Pulau Pinang", "07"),
            ("Kuala Lumpur", "14"),
            ("Johor", "01"),
            ("Sarawak", "13"),
            ("Atlantis", STATE_NOT_APPLICABLE),
            (None, STATE_NOT_APPLICABLE),
        ],
    )
    def test_state_codes(self, state, expected):
        assert state_code(state) == expected

    def test_non_malaysian_state_is_not_applicable(self):
        assert state_code("California", country="US") == STATE_NOT_APPLICABLE

    @pytest.mark.parametrize(
        "code,expected", [("MY", "MYS"), ("SG", "SGP"), (None, "MYS"), ("us", "USA")]
    )
    def test_country_alpha3(self, code, expected):
        assert country_alpha3(code) == expected

    @pytest.mark.parametrize(
        "tax_type,expected",
        [
            ("SALES_TAX", "01"),
            ("SERVICE_TAX", "02"),
            ("EXEMPT", "E"),
            ("", TAX_TYPE_NOT_APPLICABLE),
            (None, TAX_TYPE_NOT_APPLICABLE),
            ("SOMETHING_NEW", TAX_TYPE_NOT_APPLICABLE),
        ],
    )
    def test_tax_type_codes(self, tax_type, expected):
        assert tax_type_code(tax_type) == expected

    @pytest.mark.parametrize(
        "invoice_type,expected",
        [
            ("INVOICE", "01"),
            ("CONSOLIDATED", "01"),
            ("CREDIT_NOTE", "02"),
            ("SELF_BILLED", "11"),
            (None, "01"),
        ],
    )
    def test_invoice_type_codes(self, invoice_type, expected):
        assert invoice_type_code(invoice_type) == expected

    @pytest.mark.parametrize(
        "code,expected",
        [("PCS", "C62"), ("box", "XBX"), ("KG", "KGM"), ("WEIRD", UOM_FALLBACK), (None, UOM_FALLBACK)],
    )
    def test_uom_codes(self, code, expected):
        assert uom_code(code) == expected
