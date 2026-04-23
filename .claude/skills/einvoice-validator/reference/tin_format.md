# TIN Format Reference (Malaysia)

TIN (Tax Identification Number) issued by LHDN (Inland Revenue Board of Malaysia).

## Format Types

### 1. Corporate TIN
- Prefix `C` + 10 digits
- Regex: `^C\d{10}$`
- Example: `C1234567890`, `C9876543210`
- Used for: Sdn Bhd, Berhad, Enterprise (registered entities)

### 2. Individual TIN
- Same as NRIC (MyKad) without dashes: 12 digits
- Regex: `^\d{12}$`
- Format: `YYMMDD-PB-XXXX` → digits only
  - `YYMMDD`: Date of birth
  - `PB`: Place of birth code (01-16 states)
  - `XXXX`: Serial + gender (odd = M, even = F)
- Example: `800101015234`, `920415086721`

### 3. Special Cases

| Case | TIN Value |
|---|---|
| General Public (Consolidated e-Invoice) | `EI00000000010` |
| Non-resident individual | `IG00000000010` |
| Government | `IG00000000020` |

### 4. Foreign TIN (Non-resident)
- Prefix `F` + 10 digits for foreign corporations
- Prefix `G` + 10 digits for foreign individuals
- Example: `F1000000001`, `G2000000001`

## Validation Rules

```python
import re
from datetime import date

TIN_PATTERNS = {
    "CORP":    re.compile(r"^C\d{10}$"),
    "INDIV":   re.compile(r"^\d{12}$"),
    "FOREIGN_CORP":  re.compile(r"^F\d{10}$"),
    "FOREIGN_INDIV": re.compile(r"^G\d{10}$"),
}

GENERAL_PUBLIC_TIN = "EI00000000010"
NON_RESIDENT_INDIV_TIN = "IG00000000010"
GOVERNMENT_TIN = "IG00000000020"

def validate_tin(tin: str) -> tuple[bool, str]:
    """Returns (is_valid, tin_type)."""
    if tin in {GENERAL_PUBLIC_TIN, NON_RESIDENT_INDIV_TIN, GOVERNMENT_TIN}:
        return True, "SPECIAL"
    for tin_type, pattern in TIN_PATTERNS.items():
        if pattern.match(tin):
            if tin_type == "INDIV" and not _is_valid_nric_date(tin):
                return False, "INDIV_INVALID_DATE"
            return True, tin_type
    return False, "UNKNOWN"

def _is_valid_nric_date(nric: str) -> bool:
    """Check if first 6 digits form a valid date."""
    yy = int(nric[:2])
    mm = int(nric[2:4])
    dd = int(nric[4:6])
    # YY: < 40 → 2000s, >= 40 → 1900s (approximate)
    year = 2000 + yy if yy < 40 else 1900 + yy
    try:
        date(year, mm, dd)
        return True
    except ValueError:
        return False
```

## Common Errors

| Wrong | Right | Issue |
|---|---|---|
| `c1234567890` | `C1234567890` | Prefix must be uppercase |
| `C-1234567890` | `C1234567890` | No dashes |
| `12345678` | invalid | Too short |
| `800101-01-5234` | `800101015234` | Remove dashes |
| `C12345678901` | `C1234567890` | Corp TIN is 10 digits after C |

## Sources
- LHDN e-Invoice Specific Guideline v2.3
- Income Tax Act 1967
