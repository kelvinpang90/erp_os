"""ORM → MyInvois payload mapping.

Lives in the service layer, not in ``app/integrations``: the adapters must stay
provider-agnostic and free of SQLAlchemy imports. Both the Invoice and the
Credit Note services build their payload here so the seller/buyer/line mapping
has exactly one definition.

Every field is read off the already-loaded object graph — callers must fetch
through ``InvoiceRepository.get_detail`` / ``CreditNoteRepository.get_detail``,
which eager-load the relationships used here (rule E1, no N+1).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.integrations.myinvois import InvoicePayload, LinePayload, PartyInfo
from app.models.invoice import CreditNote, Invoice
from app.models.organization import Organization
from app.models.partner import Customer

# LHDN's designated TIN for buyers who did not supply one (walk-in retail).
CONSUMER_TIN = "EI00000000010"


def _seller_party(org: Optional[Organization], *, tin: str) -> PartyInfo:
    if org is None:
        return PartyInfo(tin=tin, name="")
    return PartyInfo(
        tin=tin,
        name=org.name,
        registration_no=org.registration_no,
        sst_no=org.sst_registration_no,
        msic_code=org.msic_code,
        address_line1=org.address_line1,
        address_line2=org.address_line2,
        city=org.city,
        state=org.state,
        postcode=org.postcode,
        country=org.country or "MY",
        phone=org.phone,
        email=org.email,
    )


def _buyer_party(customer: Optional[Customer], *, tin: str) -> PartyInfo:
    if customer is None:
        return PartyInfo(tin=tin, name="")
    return PartyInfo(
        tin=tin,
        name=customer.name,
        registration_no=customer.registration_no,
        sst_no=customer.sst_registration_no,
        msic_code=customer.msic_code,
        address_line1=customer.address_line1,
        address_line2=customer.address_line2,
        city=customer.city,
        state=customer.state,
        postcode=customer.postcode,
        country=customer.country or "MY",
        phone=customer.phone,
        email=customer.email,
    )


def build_invoice_payload(invoice: Invoice) -> InvoicePayload:
    """Map an Invoice (with lines, org and customer loaded) to an InvoicePayload."""
    org = invoice.organization
    cust = invoice.customer
    # Prefer the TIN snapshot baked onto the invoice at draft creation; fall
    # back to live org/customer TIN only for legacy rows written before the
    # snapshot migration. This keeps the submitted TIN the one that was legally
    # in force when the invoice was issued.
    seller_tin = invoice.seller_tin or (org.tin if org else "") or ""
    buyer_tin = invoice.buyer_tin or (cust.tin if cust else None) or CONSUMER_TIN

    lines = tuple(
        LinePayload(
            line_no=line.line_no,
            description=line.description,
            qty=line.qty,
            uom_code=line.uom.code if line.uom else "",
            unit_price_excl_tax=line.unit_price_excl_tax,
            tax_type=line.tax_rate.tax_type.value if line.tax_rate else "",
            tax_rate_percent=line.tax_rate_percent,
            tax_amount=line.tax_amount,
            line_total_excl_tax=line.line_total_excl_tax,
            discount_amount=line.discount_amount or Decimal("0"),
        )
        for line in sorted(invoice.lines or [], key=lambda ln: ln.line_no)
    )

    return InvoicePayload(
        document_no=invoice.document_no,
        invoice_type=invoice.invoice_type.value,
        business_date=invoice.business_date.isoformat(),
        currency=invoice.currency,
        exchange_rate=invoice.exchange_rate,
        seller_tin=seller_tin,
        seller_name=org.name if org else "",
        seller_msic_code=org.msic_code if org else None,
        seller_sst_no=org.sst_registration_no if org else None,
        buyer_tin=buyer_tin,
        buyer_name=cust.name if cust else "",
        buyer_msic_code=cust.msic_code if cust else None,
        subtotal_excl_tax=invoice.subtotal_excl_tax,
        tax_amount=invoice.tax_amount,
        total_incl_tax=invoice.total_incl_tax,
        line_count=len(invoice.lines or []),
        seller=_seller_party(org, tin=seller_tin),
        buyer=_buyer_party(cust, tin=buyer_tin),
        lines=lines,
        discount_amount=invoice.discount_amount or Decimal("0"),
    )


def build_credit_note_payload(cn: CreditNote) -> InvoicePayload:
    """Map a Credit Note to an InvoicePayload (LHDN document type "02").

    CN lines carry no tax-rate row of their own; the tax type is inherited from
    the invoice line being credited.
    """
    org = cn.organization
    cust = cn.customer
    seller_tin = (org.tin or "") if org else ""
    buyer_tin = (cust.tin or CONSUMER_TIN) if cust else CONSUMER_TIN

    lines = tuple(
        LinePayload(
            line_no=line.line_no,
            description=line.description,
            qty=line.qty,
            uom_code=line.uom.code if line.uom else "",
            unit_price_excl_tax=line.unit_price_excl_tax,
            tax_type=(
                line.invoice_line.tax_rate.tax_type.value
                if line.invoice_line and line.invoice_line.tax_rate
                else ""
            ),
            tax_rate_percent=line.tax_rate_percent,
            tax_amount=line.tax_amount,
            line_total_excl_tax=line.line_total_excl_tax,
        )
        for line in sorted(cn.lines or [], key=lambda ln: ln.line_no)
    )

    original = cn.invoice
    return InvoicePayload(
        document_no=cn.document_no,
        invoice_type="CREDIT_NOTE",
        business_date=cn.business_date.isoformat(),
        currency=cn.currency,
        exchange_rate=cn.exchange_rate,
        seller_tin=seller_tin,
        seller_name=org.name if org else "",
        seller_msic_code=(org.msic_code or None) if org else None,
        seller_sst_no=(org.sst_registration_no or None) if org else None,
        buyer_tin=buyer_tin,
        buyer_name=cust.name if cust else "",
        buyer_msic_code=(cust.msic_code or None) if cust else None,
        subtotal_excl_tax=cn.subtotal_excl_tax,
        tax_amount=cn.tax_amount,
        total_incl_tax=cn.total_incl_tax,
        line_count=len(cn.lines or []),
        seller=_seller_party(org, tin=seller_tin),
        buyer=_buyer_party(cust, tin=buyer_tin),
        lines=lines,
        # LHDN requires both the original document's UIN and its internal ID.
        original_uin=original.uin if original else None,
        original_document_no=original.document_no if original else None,
    )
