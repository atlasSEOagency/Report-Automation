import json
import os
import sys
import time
import re
from datetime import date, datetime

import gspread as gs
import pandas as pd
import traceback
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from dateutil import parser as date_parser

from reporting import find_month_row, get_reporting_window, is_month_header_row, InvalidDataRowError

from retry_helper import (
    open_sheet_with_retry,
    get_worksheets_with_retry,
    get_all_values_with_retry,
    col_values_with_retry,
    batch_clear_with_retry,
    paced_append_rows
)

DATE_COLUMN = 0
URL_COLUMN = 6
MONTH_NAMES = {
    name.lower(): index
    for index, name in enumerate(
        (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ),
        1,
    )
}

def get_cached_tab(tab_dict, title):
    if title in tab_dict:
        return tab_dict[title]

    # Adaptive matching: ignore case and all whitespace using regex
    target = re.sub(r'\s+', '', title).lower()
    for sheet_title, ws in tab_dict.items():
        current = re.sub(r'\s+', '', sheet_title).lower()
        if current == target:
            return ws

    raise WorksheetNotFound(f"Worksheet {title} not found")

def parse_strict_date(date_str: str) -> date:
    """Parse a date string, enforcing that it contains a year."""
    text = str(date_str).strip() if date_str is not None else ""
    if not text:
        raise ValueError("Empty date")
    # Require 4 consecutive digits for the year
    year_match = re.search(r"\b20\d{2}\b", text)
    if not year_match:
        raise ValueError(f"Date missing year: {date_str}")

    # Reject month/year-only values. dateutil otherwise fills the missing day
    # from today's date, which would corrupt reporting-window boundaries.
    without_year = text[:year_match.start()] + " " + text[year_match.end():]
    has_month_name = re.search(
        r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?)\b",
        without_year,
        re.IGNORECASE,
    )
    numeric_parts = [int(value) for value in re.findall(r"\b\d{1,2}\b", without_year)]
    if (has_month_name and not any(1 <= value <= 31 for value in numeric_parts)) or (
        not has_month_name and len(numeric_parts) < 2
    ):
        raise ValueError(f"Date missing day: {date_str}")

    # Parse flexible full-date forms such as 16/07/2026 and July 16, 2026.
    try:
        dt = date_parser.parse(text, fuzzy=True, dayfirst=True)
        return dt.date()
    except Exception as e:
        raise ValueError(f"Invalid date format: {date_str}") from e

def parse_partial_date(date_str: str, start_date: date, end_date: date) -> date | None:
    """Resolve a month/day row without a year against the reporting window."""
    text = str(date_str).strip()
    month_pattern = "|".join(MONTH_NAMES)
    match = re.fullmatch(
        rf"(?i)(?:(?P<month>{month_pattern})\s+(?P<day>\d{{1,2}})|"
        rf"(?P<day2>\d{{1,2}})\s+(?P<month2>{month_pattern}))"
        rf"(?:st|nd|rd|th)?",
        text,
    )
    if not match:
        return None

    month_name = match.group("month") or match.group("month2")
    day_text = match.group("day") or match.group("day2")
    month = MONTH_NAMES[month_name.lower()]
    day = int(day_text)

    candidates = []
    for year in range(start_date.year - 1, end_date.year + 2):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}") from None

    def distance(candidate):
        if candidate < start_date:
            return (start_date - candidate).days
        if candidate > end_date:
            return (candidate - end_date).days
        return 0

    return min(candidates, key=distance)

def resolve_row_date(date_str: str, start_date: date, end_date: date) -> date | None:
    """Parse a full date or a month/day date header; ignore sequence numbers."""
    text = str(date_str).strip()
    if not text:
        return None
    try:
        return parse_strict_date(text)
    except ValueError as full_error:
        partial = parse_partial_date(text, start_date, end_date)
        if partial is not None:
            return partial
        if re.search(r"\b20\d{2}\b", text):
            raise full_error
        return None

def filter_rows_by_date(raw_data, start_date, end_date):
    valid_rows = []
    current_date = None

    for idx, row in enumerate(raw_data):
        if is_month_header_row(row):
            continue

        date_str = str(row[DATE_COLUMN]).strip() if len(row) > DATE_COLUMN else ""
        url_val = str(row[URL_COLUMN]).strip() if len(row) > URL_COLUMN else ""

        if date_str:
            try:
                current_date = resolve_row_date(date_str, start_date, end_date) or current_date
            except ValueError as error:
                if url_val.startswith("http"):
                    raise InvalidDataRowError(f"Row {idx + 1}: {error}") from error

        if url_val.startswith("http"):
            if current_date is not None:
                if start_date <= current_date <= end_date:
                    valid_rows.append(row)
            else:
                print(f"Warning: Skipping Row {idx + 1} (URL found but no preceding daily date)")

    return valid_rows

def counter(raw_data, start_date, end_date):
    valid_rows = filter_rows_by_date(raw_data, start_date, end_date)
    return len(valid_rows), valid_rows

def write_counter(write_wks, counts, month_end_date_str):
    if not counts:
        return

    rows_insert = [[], [], []]
    for key, value in counts.items():
        rows_insert[0].append(month_end_date_str)
        rows_insert[1].append(key)
        rows_insert[2].append(value)

    paced_append_rows(write_wks, list(map(list, zip(*rows_insert))))

def get_ranks(rank_wks, month_end_date_str):
    rank_df = pd.DataFrame(get_all_values_with_retry(rank_wks))
    if rank_df.empty or len(rank_df.columns) < 3:
        return []

    # Keywords data starts on row 4. The old fixed `:-7` slice dropped valid
    # Bloom rows because that sheet has no seven-row footer.
    rank_df = rank_df.iloc[3:].copy()
    rank_df = rank_df[rank_df[0].astype(str).str.fullmatch(r"\d+")]
    rank_df = rank_df.reset_index(drop=True)
    if rank_df.empty:
        return []

    rank_df.drop(columns=0, inplace=True)

    rank_df = pd.concat([rank_df.iloc[:, :2], rank_df.iloc[:, -4:]], axis=1)
    formatted_rows = rank_df.values.tolist()
    for row in formatted_rows:
        if row[1] != "":
            row.insert(0, month_end_date_str)
    return formatted_rows

def write_ranks(rank_wks, formatted_rows):
    if formatted_rows:
        paced_append_rows(rank_wks, formatted_rows)

def get_offpage_links(valid_rows):
    if not valid_rows:
        return []
    offpage_df = pd.DataFrame(valid_rows)
    # Ensure it has enough columns
    for i in range(7):
        if i not in offpage_df.columns:
            offpage_df[i] = ""
    # Drop columns 0, 2, 3, 4, 5
    offpage_df.drop(columns=[0, 2, 3, 4, 5], inplace=True)
    return offpage_df.values.tolist()

def write_offpage(worksheet, formatted_rows):
    if formatted_rows:
        paced_append_rows(worksheet, formatted_rows)

def main():
    report_month_str = os.environ.get("REPORT_MONTH")
    report_cycle = os.environ.get("REPORT_CYCLE")

    if not report_month_str or not re.match(r"^\d{4}-\d{2}$", report_month_str):
        print(f"CRITICAL ERROR: Invalid or missing REPORT_MONTH: '{report_month_str}'. Must be YYYY-MM.")
        sys.exit(1)

    if report_cycle not in ["All", "1-1", "15-15"]:
        print(f"CRITICAL ERROR: Invalid or missing REPORT_CYCLE: '{report_cycle}'. Must be 'All', '1-1', or '15-15'.")
        sys.exit(1)

    target_month_date = datetime.strptime(report_month_str, "%Y-%m").date()

    gcreds = os.environ.get("GCREDS")
    if gcreds is None:
        gc = gs.service_account(".env/auto-report-504013-af953f806f88.json")
    else:
        gc = gs.service_account_from_dict(json.loads(gcreds))

    try:
        config_sh = open_sheet_with_retry(gc, "Auto-SEO Master Config")
        config_worksheets = get_worksheets_with_retry(config_sh)
        config_tabs_dict = {ws.title: ws for ws in config_worksheets}
    except SpreadsheetNotFound:
        print("CRITICAL ERROR: Could not find 'Auto-SEO Master Config'.")
        sys.exit(1)

    tabs_to_process = []
    if report_cycle in ["All", "1-1"]:
        try:
            tabs_to_process.append(("1-1", get_cached_tab(config_tabs_dict, "client info 1-1")))
        except WorksheetNotFound:
            print("CRITICAL ERROR: Missing 'client info 1-1' tab in Config.")
            sys.exit(1)

    if report_cycle in ["All", "15-15"]:
        try:
            tabs_to_process.append(("15-15", get_cached_tab(config_tabs_dict, "client info 15-15")))
        except WorksheetNotFound:
            print("CRITICAL ERROR: Missing 'client info 15-15' tab in Config.")
            sys.exit(1)

    unexpected_errors = 0
    sheets = [
        "Profile creation", "Social bookmarking", "Image submission",
        "Microblog submission", "Article submission", "Classified ads submission",
        "Article Promotion", "PDF submission", "PPT submission", "Blog Promotion",
    ]

    for cycle_type, config_wks in tabs_to_process:
        raw_config = get_all_values_with_retry(config_wks)
        company_info = (
            [dict(zip(raw_config[1], row)) for row in raw_config[2:]]
            if len(raw_config) > 2
            else []
        )

        start_date, end_date = get_reporting_window(target_month_date, cycle_type)
        month_end_date_str = end_date.strftime("%d/%m/%Y")

        for company in company_info:
            if str(company.get("Status", "")).strip().lower() != "active":
                continue

            current_tab = "None"
            current_op = "open_spreadsheet"
            try:
                print(f"\n--- Processing {company['Company Name']} (Cycle: {cycle_type}) ---")
                try:
                    sh = open_sheet_with_retry(gc, company["Active report"])
                except SpreadsheetNotFound:
                    raise InvalidDataRowError(f"Spreadsheet not found or missing permissions: {company['Active report']}")
                try:
                    of_sh = open_sheet_with_retry(gc, company["Offpage-links report"])
                except SpreadsheetNotFound:
                    raise InvalidDataRowError(f"Spreadsheet not found or missing permissions: {company['Offpage-links report']}")
                try:
                    write_sh = open_sheet_with_retry(gc, company["Looker-studio-sheet"])
                except SpreadsheetNotFound:
                    raise InvalidDataRowError(f"Spreadsheet not found or missing permissions: {company['Looker-studio-sheet']}")

                print(f"Selected reporting window: {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}")

                current_op = "get_worksheets"
                source_tabs = {ws.title: ws for ws in get_worksheets_with_retry(sh)}
                offpage_tabs = {ws.title: ws for ws in get_worksheets_with_retry(of_sh)}
                output_tabs = {ws.title: ws for ws in get_worksheets_with_retry(write_sh)}

                current_tab = "Summary (sheet1)"
                current_op = "col_values_with_retry"
                summary_wks = list(output_tabs.values())[0]
                summary_col_dates = col_values_with_retry(summary_wks, 1)

                if month_end_date_str in [str(value).strip() for value in summary_col_dates]:
                    print(f"Report already generated for {company['Company Name']} for {month_end_date_str}. Skipping!")
                    continue

                print("Clearing old data from all offpage tabs...")
                for sheet_name in sheets:
                    if sheet_name in offpage_tabs:
                        of_wks = get_cached_tab(offpage_tabs, sheet_name)
                        current_tab = sheet_name
                        current_op = "batch_clear"
                        if of_wks.row_count > 3:
                            batch_clear_with_retry(of_wks, [f"A4:Z{of_wks.row_count}"])

                counts = {}

                # Fetch anchor tab data first so we can use it
                current_tab = "Profile creation"
                current_op = "source.get_all_values"
                anchor_wks = get_cached_tab(source_tabs, current_tab)
                anchor_values = get_all_values_with_retry(anchor_wks)

                for sheet_name in sheets:
                    current_tab = sheet_name
                    try:
                        if sheet_name == "Profile creation":
                            raw_data = anchor_values
                        else:
                            current_op = "source.get_all_values"
                            wks = get_cached_tab(source_tabs, sheet_name)
                            raw_data = get_all_values_with_retry(wks)

                        # Extract data globally using the stateful daily upload dates
                        current_op = "counter"
                        total_url, valid_rows = counter(raw_data, start_date, end_date)
                        counts[sheet_name] = str(total_url)

                        current_op = "write_offpage"
                        of_wks = get_cached_tab(offpage_tabs, sheet_name)
                        write_offpage(of_wks, get_offpage_links(valid_rows))

                    except ValueError as ve:
                        # ValueErrors like empty date are handled in InvalidDataRowError, but missing data logic from counter might still throw it, no we caught InvalidDataRowError.
                        print(f"No data for {sheet_name} ({ve}), skipping offpage links...")
                    except WorksheetNotFound:
                        print(f"ERROR: Missing tab '{sheet_name}'.")
                    time.sleep(1.5)

                try:
                    current_tab = "Off-Page Work"
                    current_op = "append_rows"
                    offpage_work_wks = get_cached_tab(output_tabs, current_tab)
                    write_counter(offpage_work_wks, counts, month_end_date_str)
                except WorksheetNotFound:
                    print("ERROR: Missing tab 'Off-Page Work'.")

                try:
                    current_tab = "Ranks"
                    current_op = "source.get_all_values"
                    kw_wks = get_cached_tab(source_tabs, "Keywords")
                    rank_df = get_ranks(kw_wks, month_end_date_str)

                    current_op = "append_rows"
                    out_ranks_wks = get_cached_tab(output_tabs, current_tab)
                    write_ranks(out_ranks_wks, rank_df)
                except WorksheetNotFound:
                    print("ERROR: Missing 'Keywords' or 'Ranks' tab.")

                print(f"Finished processing {company['Company Name']}!")
                time.sleep(3)

            except InvalidDataRowError as ide:
                print(f"{company.get('Company Name', 'Unknown')} | tab={current_tab} | operation={current_op}")
                print(f"CRITICAL ERROR: {ide}")
                unexpected_errors += 1
            except Exception as error:
                print(f"{company.get('Company Name', 'Unknown')} | tab={current_tab} | operation={current_op}")
                print(f"Unexpected error: {error}")
                traceback.print_exc()
                unexpected_errors += 1

    if unexpected_errors:
        print(f"Completed with {unexpected_errors} unexpected errors.")
        sys.exit(1)

if __name__ == "__main__":
    main()
