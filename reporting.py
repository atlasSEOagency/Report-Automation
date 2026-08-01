import calendar
import re
from datetime import date, timedelta


def get_month_end_str(target_date: date) -> str:
    """Return the month-end date in DD/MM/YYYY format."""
    last_day = calendar.monthrange(target_date.year, target_date.month)[1]
    return f"{last_day:02d}/{target_date.month:02d}/{target_date.year}"


def find_month_row(values: list[list[str]], target_month: date) -> int | None:
    """Return the zero-based row containing the target month and year."""
    month_name = target_month.strftime("%B")
    pattern = (
        rf"\b0?{target_month.month}[./]{target_month.year}\b|"
        rf"\b{month_name}\s+{target_month.year}\b"
    )

    for index, row in enumerate(values):
        if row and re.search(pattern, str(row[0]), re.IGNORECASE):
            return index
    return None


def select_reporting_month(anchor_values: list[list[str]], today: date) -> date:
    """Prefer the current month, then fall back to the previous month."""
    current_month = today.replace(day=1)
    if find_month_row(anchor_values, current_month) is not None:
        return current_month

    previous_month = (current_month - timedelta(days=1)).replace(day=1)
    if find_month_row(anchor_values, previous_month) is not None:
        return previous_month

    raise ValueError(
        f"No data found for {current_month:%B %Y} or "
        f"{previous_month:%B %Y} in the anchor tab."
    )
