"""LHDN MyInvois code-list mappings.

Pure lookup tables — no IO, no settings, no ORM. Everything here comes from the
LHDN e-Invoice SDK code lists (https://sdk.myinvois.hasil.gov.my/codes/).

Kept separate from the document builder so the mappings can be reviewed and
unit-tested on their own; they are the part most likely to drift as LHDN
publishes new code-list versions.
"""

from __future__ import annotations

from typing import Optional

# ── Malaysian state codes (UBL CountrySubentityCode) ─────────────────────────
# Keys are lower-cased and stripped so lookup tolerates the free-text `state`
# column on organizations/customers.
_STATE_CODES: dict[str, str] = {
    "johor": "01",
    "kedah": "02",
    "kelantan": "03",
    "melaka": "04",
    "malacca": "04",
    "negeri sembilan": "05",
    "pahang": "06",
    "pulau pinang": "07",
    "penang": "07",
    "perak": "08",
    "perlis": "09",
    "selangor": "10",
    "terengganu": "11",
    "sabah": "12",
    "sarawak": "13",
    "wp kuala lumpur": "14",
    "kuala lumpur": "14",
    "wilayah persekutuan kuala lumpur": "14",
    "wp labuan": "15",
    "labuan": "15",
    "wp putrajaya": "16",
    "putrajaya": "16",
}

# LHDN code for "Not Applicable" — used for non-Malaysian or unknown states.
STATE_NOT_APPLICABLE = "17"

# ── Country codes: ISO 3166-1 alpha-2 → alpha-3 ──────────────────────────────
# Only the countries this ERP realistically trades with. Unknown codes fall
# back to the input padded/uppercased, which LHDN will reject loudly rather
# than silently mis-file.
_COUNTRY_ALPHA3: dict[str, str] = {
    "MY": "MYS",
    "SG": "SGP",
    "CN": "CHN",
    "TH": "THA",
    "ID": "IDN",
    "VN": "VNM",
    "PH": "PHL",
    "BN": "BRN",
    "HK": "HKG",
    "TW": "TWN",
    "JP": "JPN",
    "KR": "KOR",
    "IN": "IND",
    "AU": "AUS",
    "NZ": "NZL",
    "GB": "GBR",
    "US": "USA",
    "DE": "DEU",
    "NL": "NLD",
    "AE": "ARE",
}

# ── Tax type codes (LHDN "Tax Types" code list) ──────────────────────────────
# 01 Sales Tax / 02 Service Tax / 03 Tourism / 04 High-Value Goods /
# 05 Low Value Goods / 06 Not Applicable / E Tax exemption.
_TAX_TYPE_CODES: dict[str, str] = {
    "SALES_TAX": "01",
    "SERVICE_TAX": "02",
    "EXEMPT": "E",
}

TAX_TYPE_NOT_APPLICABLE = "06"

# When a line carries the "E" (exemption) category LHDN requires a free-text
# reason. The ERP has no per-line exemption reason field, so a generic one is
# sent; refine when a customer needs itemised exemption certificates.
DEFAULT_TAX_EXEMPTION_REASON = "Exempt supply under Sales Tax (Goods Exempted) Order"

# ── Document type codes (LHDN "e-Invoice Types") ─────────────────────────────
# Consolidated B2C invoices are ordinary invoices ("01") that aggregate
# receipts; LHDN has no separate type code for them.
_INVOICE_TYPE_CODES: dict[str, str] = {
    "INVOICE": "01",
    "CONSOLIDATED": "01",
    "CREDIT_NOTE": "02",
    "DEBIT_NOTE": "03",
    "REFUND_NOTE": "04",
    "SELF_BILLED": "11",
}

# ── UOM: local code → UN/ECE Recommendation 20 ───────────────────────────────
_UOM_CODES: dict[str, str] = {
    "PCS": "C62",
    "PC": "C62",
    "UNIT": "C62",
    "EA": "C62",
    "BOX": "XBX",
    "CTN": "CT",
    "CARTON": "CT",
    "PACK": "XPK",
    "PKT": "XPK",
    "SET": "SET",
    "PAIR": "PR",
    "DOZEN": "DZN",
    "KG": "KGM",
    "G": "GRM",
    "GRAM": "GRM",
    "TON": "TNE",
    "L": "LTR",
    "LTR": "LTR",
    "ML": "MLT",
    "M": "MTR",
    "CM": "CMT",
    "MM": "MMT",
    "M2": "MTK",
    "M3": "MTQ",
    "ROLL": "RO",
    "BTL": "BO",
    "BOTTLE": "BO",
    "BAG": "BG",
    "DAY": "DAY",
    "HOUR": "HUR",
    "MONTH": "MON",
}

UOM_FALLBACK = "C62"    # "one/each" — safe default for discrete goods

# ── B2C consumer fallbacks ───────────────────────────────────────────────────
# LHDN's designated TIN for buyers who did not provide one (walk-in retail /
# consolidated e-Invoices).
CONSUMER_TIN = "EI00000000010"
NOT_APPLICABLE = "NA"

# ── Item classification (LHDN "Classification" code list) ────────────────────
# 022 = "Others". The ERP has no LHDN classification field on SKUs yet, so
# lines default to Others unless a caller supplies one.
DEFAULT_CLASSIFICATION_CODE = "022"


# ── Lookup helpers ───────────────────────────────────────────────────────────


def state_code(state: Optional[str], *, country: str = "MY") -> str:
    """Map a free-text state name to a UBL CountrySubentityCode.

    Non-Malaysian addresses and unrecognised names both resolve to "17"
    (Not Applicable), which LHDN accepts.
    """
    if (country or "MY").upper() != "MY" or not state:
        return STATE_NOT_APPLICABLE
    return _STATE_CODES.get(state.strip().lower(), STATE_NOT_APPLICABLE)


def country_alpha3(country: Optional[str]) -> str:
    """Map ISO 3166-1 alpha-2 to alpha-3; defaults to Malaysia."""
    code = (country or "MY").strip().upper()
    return _COUNTRY_ALPHA3.get(code, code)


def tax_type_code(tax_type: Optional[str]) -> str:
    """Map ``app.enums.TaxType`` values to LHDN tax type codes."""
    if not tax_type:
        return TAX_TYPE_NOT_APPLICABLE
    return _TAX_TYPE_CODES.get(tax_type.strip().upper(), TAX_TYPE_NOT_APPLICABLE)


def invoice_type_code(invoice_type: Optional[str]) -> str:
    """Map ``app.enums.InvoiceType`` values to LHDN document type codes."""
    if not invoice_type:
        return "01"
    return _INVOICE_TYPE_CODES.get(invoice_type.strip().upper(), "01")


def uom_code(code: Optional[str]) -> str:
    """Map a local UOM code to UN/ECE Rec 20; falls back to "each"."""
    if not code:
        return UOM_FALLBACK
    return _UOM_CODES.get(code.strip().upper(), UOM_FALLBACK)
