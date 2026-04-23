# Malaysian Postcode → State Mapping

Used for H5 hard rule (postcode / state consistency check).

## State Codes and Postcode Ranges

| State Name | Short Code | Postcode Range |
|---|---|---|
| Wilayah Persekutuan Kuala Lumpur | KL | 50000-60000 |
| Selangor | SGR | 40000-48300 |
| Wilayah Persekutuan Putrajaya | PJY | 62000-62988 |
| Negeri Sembilan | NSN | 70000-73509 |
| Melaka | MLK | 75000-78309 |
| Johor | JHR | 79000-86900 |
| Pahang | PHG | 25000-28800, 39000-39200, 49000, 69000 |
| Terengganu | TRG | 20000-24300 |
| Kelantan | KTN | 15000-18500 |
| Perak | PRK | 30000-36810 |
| Kedah | KDH | 05000-09810 |
| Pulau Pinang | PNG | 10000-14400 |
| Perlis | PLS | 01000-02800 |
| Sabah | SBH | 88000-91309 |
| Sarawak | SWK | 93000-98859 |
| Wilayah Persekutuan Labuan | LBN | 87000-87033 |

## Validation Function

```python
POSTCODE_STATE_RANGES = [
    ("01000", "02800", "Perlis"),
    ("05000", "09810", "Kedah"),
    ("10000", "14400", "Pulau Pinang"),
    ("15000", "18500", "Kelantan"),
    ("20000", "24300", "Terengganu"),
    ("25000", "28800", "Pahang"),
    ("30000", "36810", "Perak"),
    ("39000", "39200", "Pahang"),  # Cameron Highlands
    ("40000", "48300", "Selangor"),
    ("49000", "49000", "Pahang"),  # Genting Highlands
    ("50000", "60000", "Wilayah Persekutuan Kuala Lumpur"),
    ("62000", "62988", "Wilayah Persekutuan Putrajaya"),
    ("63000", "68100", "Selangor"),
    ("69000", "69000", "Pahang"),  # Genting Highlands
    ("70000", "73509", "Negeri Sembilan"),
    ("75000", "78309", "Melaka"),
    ("79000", "86900", "Johor"),
    ("87000", "87033", "Wilayah Persekutuan Labuan"),
    ("88000", "91309", "Sabah"),
    ("93000", "98859", "Sarawak"),
]

def postcode_to_state(postcode: str) -> str | None:
    """Returns canonical state name for a 5-digit postcode."""
    if not postcode or not postcode.isdigit() or len(postcode) != 5:
        return None
    for low, high, state in POSTCODE_STATE_RANGES:
        if low <= postcode <= high:
            return state
    return None

def check_postcode_state_match(postcode: str, state: str) -> bool:
    """Soft check: does postcode match given state name (case-insensitive)?"""
    expected = postcode_to_state(postcode)
    if not expected:
        return False
    # Handle common aliases
    aliases = {
        "kl": "Wilayah Persekutuan Kuala Lumpur",
        "kuala lumpur": "Wilayah Persekutuan Kuala Lumpur",
        "w.p. kuala lumpur": "Wilayah Persekutuan Kuala Lumpur",
        "penang": "Pulau Pinang",
        "kedah darul aman": "Kedah",
        "terengganu darul iman": "Terengganu",
    }
    actual = aliases.get(state.lower().strip(), state.strip())
    return actual.lower() == expected.lower()
```

## Common Cities Reference

| City | Postcode | State |
|---|---|---|
| Kuala Lumpur City Centre | 50088, 50450 | KL |
| Petaling Jaya | 46000-47500 | Selangor |
| Shah Alam | 40000-40470 | Selangor |
| Subang Jaya | 47500-47650 | Selangor |
| Georgetown | 10000-10470 | Penang |
| Bayan Lepas | 11900 | Penang |
| Butterworth | 12000-13700 | Penang |
| Johor Bahru | 80000-80900 | Johor |
| Skudai | 81300 | Johor |
| Ipoh | 30000-31650 | Perak |
| Kuantan | 25000-26100 | Pahang |
| Kota Bharu | 15000-16810 | Kelantan |
| Kota Kinabalu | 88000-88999 | Sabah |
| Kuching | 93000-93999 | Sarawak |
| Seremban | 70000-71760 | Negeri Sembilan |
| Melaka | 75000-75999 | Melaka |
| Alor Setar | 05000-05999 | Kedah |
| Kangar | 01000-02600 | Perlis |
| Kuala Terengganu | 20000-21800 | Terengganu |
