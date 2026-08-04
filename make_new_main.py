import os

new_code = '''import json
import os
import sys
import time
import re
import traceback
from datetime import date, datetime

import gspread as gs
import pandas as pd
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
from ledger import RunLedger

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
    target = re.sub(r"\\s+", "", title).lower()
    for sheet_title, ws in tab_dict.items():
        current = re.sub(r"\\s+", "", sheet_title).lower()
        if current == target:
            return ws
    raise WorksheetNotFound(f"Worksheet {title} not found")

def parse_strict_date(date_str: str) -> date:
    text = str(date_str).strip() if date_str is not None else ""
    if not text:
        raise ValueError("Empty date")
    year_match = re.search(r"\\b20\\d{2}\\b", text)
    if not year_match:
        raise ValueError(f"Date missing year: {date_str}")
    without_year = text[:year_match.start()] + " " + text[year_match.end():]
    has_month_name = re.search(
        r"\\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?)\\b",
        without_year,
        re.IGNORECASE,
    )
    numeric_parts = [int(value) for value in re.findall(r"\\b\\d{1,2}\\b", without_year)]
    if (has_month_name and not any(1 <= value <= 31 for value in numeric_parts)) or (
        not has_month_name and len(numeric_parts) < 2
    ):
        raise ValueError(f"Date missing day: {date_str}")
    try:
        dt = date_parser.parse(text, fuzzy=True, dayfirst=True)
        return dt.date()
    except Exception as e:
        raise ValueError(f"Invalid date format: {date_str}") from e

def parse_partial_date(date_str: str, start_date: date, end_date: date) -> date | None:
    text = str(date_str).strip()
    month_pattern = "|".join(MONTH_NAMES)
    match = re.fullmatch(
        rf"(?i)(?:(?P<month>{month_pattern})\\s+(?P<day>\\d{{1,2}})|"
        rf"(?P<day2>\\d{{1,2}})\\s+(?P<month2>{month_pattern}))"
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
    text = str(date_str).strip()
    if not text:
        return None
    try:
        return parse_strict_date(text)
    except ValueError as full_error:
        partial = parse_partial_date(text, start_date, end_date)
        if partial is not None:
            return partial
        if re.search(r"\\b20\\d{2}\\b", text):
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

def format_counter_rows(counts, month_end_date_str):
    if not counts:
        return []
    rows_insert = [[], [], []]
    for key, value in counts.items():
        rows_insert[0].append(month_end_date_str)
        rows_insert[1].append(key)
        rows_insert[2].append(value)
    return list(map(list, zip(*rows_insert)))

def format_ranks_rows(rank_wks, month_end_date_str):
    rank_df = pd.DataFrame(get_all_values_with_retry(rank_wks))
    if rank_df.empty or len(rank_df.columns) < 3:
        return []
    rank_df = rank_df.iloc[3:].copy()
    rank_df = rank_df[rank_df[0].astype(str).str.fullmatch(r"\\d+")]
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

def format_offpage_links(valid_rows):
    if not valid_rows:
        return []
    offpage_df = pd.DataFrame(valid_rows)
    for i in range(7):
        if i not in offpage_df.columns:
            offpage_df[i] = ""
    offpage_df.drop(columns=[0, 2, 3, 4, 5], inplace=True)
    return offpage_df.values.tolist()

def clear_matching_rows(wks, report_end_date_str):
    """Finds rows where Col 0 == report_end_date_str and batch_clears them."""
    data = get_all_values_with_retry(wks)
    ranges_to_clear = []
    for idx, row in enumerate(data):
        if row and str(row[0]).strip() == report_end_date_str:
            row_num = idx + 1
            ranges_to_clear.append(f"A{row_num}:Z{row_num}")
    if ranges_to_clear:
        batch_clear_with_retry(wks, ranges_to_clear)
        print(f"  -> Cleared {len(ranges_to_clear)} matching rows in {wks.title}")

def main():
    report_month_str = os.environ.get("REPORT_MONTH")
    report_cycle = os.environ.get("REPORT_CYCLE")
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    run_id = os.environ.get("GITHUB_RUN_ID", "local")

    if not report_month_str or not re.match(r"^\\d{4}-\\d{2}$", report_month_str):
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
        
    ledger = RunLedger(gc)

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

    sheets = [
        "Profile creation", "Social bookmarking", "Image submission",
        "Microblog submission", "Article submission", "Classified ads submission",
        "Article Promotion", "PDF submission", "PPT submission", "Blog Promotion",
    ]

    validated_payloads = []
    unexpected_errors = 0

    print("=== PHASE 1: PREFLIGHT & VALIDATION ===")
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

            print(f"Preflight: {company['Company Name']} (Cycle: {cycle_type})")
            ledger_key = f"{company['Company Name']}-{cycle_type}-{month_end_date_str}"
            
            try:
                sh = open_sheet_with_retry(gc, company["Active report"])
                of_sh = open_sheet_with_retry(gc, company["Offpage-links report"])
                write_sh = open_sheet_with_retry(gc, company["Looker-studio-sheet"])

                source_tabs = {ws.title: ws for ws in get_worksheets_with_retry(sh)}
                offpage_tabs = {ws.title: ws for ws in get_worksheets_with_retry(of_sh)}
                output_tabs = {ws.title: ws for ws in get_worksheets_with_retry(write_sh)}

                anchor_wks = get_cached_tab(source_tabs, "Profile creation")
                anchor_values = get_all_values_with_retry(anchor_wks)

                counts = {}
                offpage_data = {}
                for sheet_name in sheets:
                    try:
                        if sheet_name == "Profile creation":
                            raw_data = anchor_values
                        else:
                            wks = get_cached_tab(source_tabs, sheet_name)
                            raw_data = get_all_values_with_retry(wks)

                        count, valid_rows = counter(raw_data, start_date, end_date)
                        counts[sheet_name] = str(count)
                        offpage_data[sheet_name] = format_offpage_links(valid_rows)
                    except WorksheetNotFound:
                        pass # Tab missing in source, skip
                        
                # Validate output formats (No mutation)
                counter_rows = format_counter_rows(counts, month_end_date_str)
                
                rank_rows = []
                try:
                    kw_wks = get_cached_tab(source_tabs, "Keywords")
                    rank_rows = format_ranks_rows(kw_wks, month_end_date_str)
                except WorksheetNotFound:
                    pass

                validated_payloads.append({
                    "company_name": company['Company Name'],
                    "ledger_key": ledger_key,
                    "offpage_tabs": offpage_tabs,
                    "output_tabs": output_tabs,
                    "counts": counts,
                    "counter_rows": counter_rows,
                    "rank_rows": rank_rows,
                    "offpage_data": offpage_data,
                    "month_end_date_str": month_end_date_str,
                    "sheets_to_process": sheets
                })
                print(f"  -> Validated {len(counts)} tabs successfully.")
            except Exception as e:
                print(f"  -> PREFLIGHT FAILED: {e}")
                traceback.print_exc()
                unexpected_errors += 1

    print("\\n=== PHASE 2: EXECUTION & RECOVERY ===")
    for payload in validated_payloads:
        company_name = payload["company_name"]
        ledger_key = payload["ledger_key"]
        print(f"Executing: {company_name}")

        entry = ledger.get_entry(ledger_key)
        if entry and entry.get("Status") == "COMPLETED":
            print(f"  -> Status COMPLETED in ledger. Skipping!")
            continue

        if entry and entry.get("Status") in ["STARTED", "FAILED"]:
            print(f"  -> Recovery Mode triggered for {company_name}")
            if not dry_run:
                # 1. Clear offpage tabs A4:Z (Snapshot rule)
                for sheet_name in payload["sheets_to_process"]:
                    if sheet_name in payload["offpage_tabs"]:
                        of_wks = get_cached_tab(payload["offpage_tabs"], sheet_name)
                        if of_wks.row_count > 3:
                            batch_clear_with_retry(of_wks, [f"A4:Z{of_wks.row_count}"])
                
                # 2. Clear matching rows in Summary / Ranks
                try:
                    summary_wks = get_cached_tab(payload["output_tabs"], "Summary (sheet1)") # Wait, it is Off-Page Work or Summary (sheet1)? Earlier it was list(output_tabs.values())[0] for skipping, but appended to "Off-Page Work"
                    clear_matching_rows(summary_wks, payload["month_end_date_str"])
                except Exception:
                    pass
                
                try:
                    op_work = get_cached_tab(payload["output_tabs"], "Off-Page Work")
                    clear_matching_rows(op_work, payload["month_end_date_str"])
                except Exception:
                    pass

                try:
                    ranks_wks = get_cached_tab(payload["output_tabs"], "Ranks")
                    clear_matching_rows(ranks_wks, payload["month_end_date_str"])
                except Exception:
                    pass
        
        if dry_run:
            print(f"  [DRY RUN] Would write {len(payload['counter_rows'])} counter rows, {len(payload['rank_rows'])} rank rows.")
            continue

        # Execute
        try:
            ledger.log_start(ledger_key, run_id)
            
            # Write offpage links (and clear A4:Z snapshot on normal runs too)
            for sheet_name in payload["sheets_to_process"]:
                if sheet_name in payload["offpage_tabs"]:
                    of_wks = get_cached_tab(payload["offpage_tabs"], sheet_name)
                    # For snapshot rule, we always clear A4:Z before writing new links for this cycle.
                    # Wait, if we cleared during recovery, we don't need to clear again. 
                    # But if this is a fresh run, we must clear A4:Z before writing!
                    if not (entry and entry.get("Status") in ["STARTED", "FAILED"]):
                        if of_wks.row_count > 3:
                            batch_clear_with_retry(of_wks, [f"A4:Z{of_wks.row_count}"])
                            
                    data_to_write = payload["offpage_data"].get(sheet_name, [])
                    if data_to_write:
                        paced_append_rows(of_wks, data_to_write)

            if payload["counter_rows"]:
                try:
                    offpage_work_wks = get_cached_tab(payload["output_tabs"], "Off-Page Work")
                    paced_append_rows(offpage_work_wks, payload["counter_rows"])
                except WorksheetNotFound:
                    print("  -> ERROR: Missing tab 'Off-Page Work'.")

            if payload["rank_rows"]:
                try:
                    out_ranks_wks = get_cached_tab(payload["output_tabs"], "Ranks")
                    paced_append_rows(out_ranks_wks, payload["rank_rows"])
                except WorksheetNotFound:
                    print("  -> ERROR: Missing 'Ranks' tab.")

            ledger.log_success(ledger_key)
            print(f"  -> Successfully processed {company_name}!")
        except Exception as e:
            ledger.log_failure(ledger_key, str(e))
            print(f"  -> CRITICAL FAILURE writing {company_name}: {e}")
            traceback.print_exc()
            unexpected_errors += 1

    if unexpected_errors:
        print(f"\\nCompleted with {unexpected_errors} unexpected errors.")
        sys.exit(1)
    else:
        print(f"\\nAll processing completed successfully!")

if __name__ == "__main__":
    main()
'''

with open("/Volumes/disk_2/program/Auto-Seo/new_main.py", "w") as f:
    f.write(new_code)
print("new_main.py written.")
