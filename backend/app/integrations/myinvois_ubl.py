"""UBL 2.1 JSON document builder for LHDN MyInvois.

Pure functions — no IO, no settings, no ORM. Takes an
:class:`~app.integrations.myinvois.InvoicePayload` and returns the ``dict``
that gets minified, hashed and base64-encoded by the real adapter.

Emits **v1.0** documents (``listVersionID: "1.0"``). Per the LHDN SDK, v1.0 is
structurally identical to v1.1 with signature validation disabled — which is
exactly what this integration needs until a Malaysian CA certificate is
available for XAdES signing.

All e-Invoice types (invoice / credit note / debit note / self-billed) share
the ``Invoice`` UBL root; ``InvoiceTypeCode`` is what distinguishes them.

JSON value convention: every UBL element is an array of objects whose text
content lives under the ``"_"`` key, with XML attributes as sibling keys —
e.g. ``"TaxAmount": [{"_": 10.0, "currencyID": "MYR"}]``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

from app.integrations.myinvois import InvoicePayload, LinePayload, PartyInfo
from app.integrations.myinvois_codes import (
    CONSUMER_TIN,
    DEFAULT_CLASSIFICATION_CODE,
    DEFAULT_TAX_EXEMPTION_REASON,
    NOT_APPLICABLE,
    country_alpha3,
    invoice_type_code,
    state_code,
    tax_type_code,
    uom_code,
)

UBL_VERSION = "1.0"

_NS = {
    "_D": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "_A": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "_B": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}

# MSIC placeholder when the organisation has not configured one. LHDN requires
# the supplier's IndustryClassificationCode to be present.
_MSIC_FALLBACK = "00000"
_MSIC_FALLBACK_NAME = "NOT APPLICABLE"

_TWO = Decimal("0.01")
_FOUR = Decimal("0.0001")


# ── Scalar helpers ───────────────────────────────────────────────────────────


def _money(value: Decimal) -> float:
    """Quantize to 2 dp then hand to the JSON encoder.

    Decimal is preserved through every calculation (rule A1); float appears
    only here, at the serialisation boundary, because the LHDN JSON schema
    types amounts as numbers.
    """
    return float(Decimal(value).quantize(_TWO, rounding=ROUND_HALF_UP))


def _qty(value: Decimal) -> float:
    return float(Decimal(value).quantize(_FOUR, rounding=ROUND_HALF_UP))


def _text(value: Any) -> list[dict[str, Any]]:
    return [{"_": value}]


def _amount(value: Decimal, currency: str) -> list[dict[str, Any]]:
    return [{"_": _money(value), "currencyID": currency}]


def _or_na(value: Optional[str]) -> str:
    """LHDN expects the literal "NA" rather than an omitted optional field."""
    text = (value or "").strip()
    return text or NOT_APPLICABLE


# ── Party ────────────────────────────────────────────────────────────────────


def _postal_address(party: PartyInfo) -> dict[str, Any]:
    lines = [ln for ln in (party.address_line1, party.address_line2) if ln]
    if not lines:
        lines = [NOT_APPLICABLE]
    return {
        "CityName": _text(_or_na(party.city)),
        "PostalZone": _text(_or_na(party.postcode)),
        "CountrySubentityCode": _text(state_code(party.state, country=party.country)),
        "AddressLine": [{"Line": _text(ln)} for ln in lines],
        "Country": [
            {
                "IdentificationCode": [
                    {
                        "_": country_alpha3(party.country),
                        "listID": "ISO3166-1",
                        "listAgencyID": "6",
                    }
                ]
            }
        ],
    }


def _party(party: PartyInfo, *, include_msic: bool) -> dict[str, Any]:
    """Build a UBL Party aggregate.

    ``include_msic`` is True for the supplier, whose IndustryClassificationCode
    is mandatory. LHDN treats it as optional on the buyer side, and most B2C
    buyers have none, so it is omitted there.
    """
    block: dict[str, Any] = {}
    if include_msic:
        # The `name` attribute is the MSIC *industry description*, not the
        # company name. The ERP stores only the code, so "NOT APPLICABLE" is
        # sent until a description field exists — see docs/myinvois-integration.md.
        block["IndustryClassificationCode"] = [
            {
                "_": party.msic_code or _MSIC_FALLBACK,
                "name": party.msic_description or _MSIC_FALLBACK_NAME,
            }
        ]
    block["PartyIdentification"] = [
        {"ID": [{"_": party.tin, "schemeID": "TIN"}]},
        {"ID": [{"_": _or_na(party.registration_no), "schemeID": "BRN"}]},
        {"ID": [{"_": _or_na(party.sst_no), "schemeID": "SST"}]},
        {"ID": [{"_": NOT_APPLICABLE, "schemeID": "TTX"}]},
    ]
    block["PostalAddress"] = [_postal_address(party)]
    block["PartyLegalEntity"] = [{"RegistrationName": _text(party.name)}]
    block["Contact"] = [
        {
            "Telephone": _text(_or_na(party.phone)),
            "ElectronicMail": _text(_or_na(party.email)),
        }
    ]
    return {"Party": [block]}


def _fallback_party(
    *,
    tin: str,
    name: str,
    msic_code: Optional[str],
    sst_no: Optional[str] = None,
) -> PartyInfo:
    """Derive a minimal party from the payload's flat fields.

    Only reached for hand-built payloads (tests, the mock adapter). The real
    ``_build_payload`` in the e-Invoice service always supplies the full
    ``PartyInfo``.
    """
    return PartyInfo(tin=tin or CONSUMER_TIN, name=name, msic_code=msic_code, sst_no=sst_no)


# ── Tax ──────────────────────────────────────────────────────────────────────


def _tax_scheme() -> list[dict[str, Any]]:
    return [
        {
            "ID": [
                {"_": "OTH", "schemeID": "UN/ECE 5153", "schemeAgencyID": "6"},
            ]
        }
    ]


def _tax_category(code: str, *, percent: Optional[Decimal] = None) -> dict[str, Any]:
    category: dict[str, Any] = {"ID": _text(code)}
    if percent is not None:
        category["Percent"] = [{"_": float(percent)}]
    if code == "E":
        category["TaxExemptionReason"] = _text(DEFAULT_TAX_EXEMPTION_REASON)
    category["TaxScheme"] = _tax_scheme()
    return category


def _document_tax_total(
    lines: tuple[LinePayload, ...],
    *,
    currency: str,
    total_tax: Decimal,
) -> dict[str, Any]:
    """Aggregate line taxes into one TaxSubtotal per LHDN tax type code."""
    buckets: dict[str, dict[str, Decimal]] = {}
    for line in lines:
        code = tax_type_code(line.tax_type)
        bucket = buckets.setdefault(code, {"taxable": Decimal("0"), "tax": Decimal("0")})
        bucket["taxable"] += Decimal(line.line_total_excl_tax)
        bucket["tax"] += Decimal(line.tax_amount)

    subtotals = [
        {
            "TaxableAmount": _amount(values["taxable"], currency),
            "TaxAmount": _amount(values["tax"], currency),
            "TaxCategory": [_tax_category(code)],
        }
        for code, values in buckets.items()
    ]
    return {
        "TaxAmount": _amount(total_tax, currency),
        "TaxSubtotal": subtotals,
    }


# ── Lines ────────────────────────────────────────────────────────────────────


def _invoice_line(line: LinePayload, *, currency: str) -> dict[str, Any]:
    code = tax_type_code(line.tax_type)
    block: dict[str, Any] = {
        "ID": _text(str(line.line_no)),
        "InvoicedQuantity": [{"_": _qty(line.qty), "unitCode": uom_code(line.uom_code)}],
        "LineExtensionAmount": _amount(line.line_total_excl_tax, currency),
    }
    if Decimal(line.discount_amount) > 0:
        block["AllowanceCharge"] = [
            {
                "ChargeIndicator": [{"_": False}],
                "AllowanceChargeReason": _text("Discount"),
                "Amount": _amount(line.discount_amount, currency),
            }
        ]
    block["TaxTotal"] = [
        {
            "TaxAmount": _amount(line.tax_amount, currency),
            "TaxSubtotal": [
                {
                    "TaxableAmount": _amount(line.line_total_excl_tax, currency),
                    "TaxAmount": _amount(line.tax_amount, currency),
                    "TaxCategory": [
                        _tax_category(code, percent=Decimal(line.tax_rate_percent))
                    ],
                }
            ],
        }
    ]
    block["Item"] = [
        {
            "CommodityClassification": [
                {
                    "ItemClassificationCode": [
                        {
                            "_": line.classification_code or DEFAULT_CLASSIFICATION_CODE,
                            "listID": "CLASS",
                        }
                    ]
                }
            ],
            "Description": _text(line.description),
        }
    ]
    block["Price"] = [{"PriceAmount": _amount(line.unit_price_excl_tax, currency)}]
    block["ItemPriceExtension"] = [{"Amount": _amount(line.line_total_excl_tax, currency)}]
    return block


# ── Entry point ──────────────────────────────────────────────────────────────


def build_invoice_document(payload: InvoicePayload) -> dict[str, Any]:
    """Build the UBL 2.1 JSON document for a MyInvois submission."""
    currency = payload.currency
    seller = payload.seller or _fallback_party(
        tin=payload.seller_tin,
        name=payload.seller_name,
        msic_code=payload.seller_msic_code,
        sst_no=payload.seller_sst_no,
    )
    buyer = payload.buyer or _fallback_party(
        tin=payload.buyer_tin,
        name=payload.buyer_name,
        msic_code=payload.buyer_msic_code,
    )

    invoice: dict[str, Any] = {
        "ID": _text(payload.document_no),
        "IssueDate": _text(payload.business_date),
        "IssueTime": _text(payload.issue_time or datetime.now(UTC).strftime("%H:%M:%SZ")),
        "InvoiceTypeCode": [
            {"_": invoice_type_code(payload.invoice_type), "listVersionID": UBL_VERSION}
        ],
        "DocumentCurrencyCode": _text(currency),
        "TaxCurrencyCode": _text("MYR"),
    }

    # Credit / debit notes must point back at the document they adjust.
    if payload.original_uin or payload.original_document_no:
        invoice["BillingReference"] = [
            {
                "InvoiceDocumentReference": [
                    {
                        "ID": _text(_or_na(payload.original_document_no)),
                        "UUID": _text(_or_na(payload.original_uin)),
                    }
                ]
            }
        ]

    # Foreign-currency invoices must declare the rate used to reach MYR.
    if currency != "MYR":
        invoice["TaxExchangeRate"] = [
            {
                "SourceCurrencyCode": _text(currency),
                "TargetCurrencyCode": _text("MYR"),
                "CalculationRate": [{"_": float(payload.exchange_rate)}],
            }
        ]

    invoice["AccountingSupplierParty"] = [_party(seller, include_msic=True)]
    invoice["AccountingCustomerParty"] = [_party(buyer, include_msic=False)]
    invoice["TaxTotal"] = [
        _document_tax_total(payload.lines, currency=currency, total_tax=payload.tax_amount)
    ]

    line_extension = sum(
        (Decimal(line.line_total_excl_tax) for line in payload.lines), Decimal("0")
    )
    monetary: dict[str, Any] = {
        "LineExtensionAmount": _amount(line_extension, currency),
        "TaxExclusiveAmount": _amount(payload.subtotal_excl_tax, currency),
        "TaxInclusiveAmount": _amount(payload.total_incl_tax, currency),
    }
    if Decimal(payload.discount_amount) > 0:
        monetary["AllowanceTotalAmount"] = _amount(payload.discount_amount, currency)
    monetary["PayableAmount"] = _amount(payload.total_incl_tax, currency)
    invoice["LegalMonetaryTotal"] = [monetary]

    invoice["InvoiceLine"] = [
        _invoice_line(line, currency=currency) for line in payload.lines
    ]

    return {**_NS, "Invoice": [invoice]}
