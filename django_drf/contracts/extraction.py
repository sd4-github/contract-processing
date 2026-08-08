import hashlib
from datetime import date, timedelta
from decimal import Decimal


def extract_values(content: bytes, variables: list[str]) -> dict[str, str]:
    """Deterministic mock results make retries idempotent and tests reproducible."""
    seed = int(hashlib.sha256(content).hexdigest()[:12], 16)
    values = {}
    for index, variable in enumerate(variables):
        number = seed + index
        normalized = variable.lower()
        if "date" in normalized:
            values[variable] = str(date(2024, 1, 1) + timedelta(days=number % 730))
        elif any(term in normalized for term in ("rent", "deposit", "charge", "amount", "price")):
            values[variable] = f"INR {Decimal(5000 + number % 195001):,.2f}"
        elif "period" in normalized or "notice" in normalized:
            values[variable] = f"{30 + number % 91} days"
        elif "law" in normalized:
            values[variable] = ("India", "England and Wales", "Singapore")[number % 3]
        else:
            values[variable] = f"mock-{variable}-{number % 100000}"
    return values
