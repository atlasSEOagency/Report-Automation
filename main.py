import json
import os
import sys
import time
from datetime import date, datetime

import gspread as gs
import pandas as pd
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound

from reporting import (
    ExplicitMonthMissingError,
    find_month_row,
    get_month_end_str,
    select_reporting_month,
)
from retry_helper import (
    batch_clear_with_retry,
    col_values_with_retry,
    get_all_values_with_retry,
    get_worksheets_with_retry,
    open_sheet_with_retry,
)

def get_cached_tab(tabs_dict, tab_name):
    if tab_name not in tabs_dict:
        raise WorksheetNotFound(tab_name)
    return tabs_dict[tab_name]

def normalize_row(row, min_length=7):
    return row + [""] * max(0, min_length - len(row))

def counter(raw_data, reporting_month):
    normalized_data = [normalize_row(row) for row in raw_data]
    df = pd.DataFrame(normalized_data)

    header_row = find_month_row(raw_data, reporting_month)
    if header_row is None:
        raise ValueError("No match")

    data_start_row = header_row + 1
    month_data = df[6].iloc[data_start_row:]
    total_url = month_data[month_data.str.startswith("htt", na=False)].count()
    return total_url, data_start_row


def write_counter(write_wks, counts, reporting_month):
    if not counts:
        return

    rows_insert = [[], [], []]
    month_end_date = get_month_end_str(reporting_month)
    for key, value in counts.items():
        rows_insert[0].append(month_end_date)
        rows_insert[1].append(key)
        rows_insert[2].append(value)

    write_wks.append_rows(list(map(list, zip(*rows_insert))))


def get_ranks(rank_wks, reporting_month):
    rank_df = pd.DataFrame(get_all_values_with_retry(rank_wks))
    rank_df = rank_df.iloc[3:-7].reset_index(drop=True)
    rank_df.drop(columns=0, inplace=True)

    rank_df = pd.concat([rank_df.iloc[:, :2], rank_df.iloc[:, -4:]], axis=1)
    formatted_rows = rank_df.values.tolist()
    month_end_date = get_month_end_str(reporting_month)
    for row in formatted_rows:
        if row[1] != "":
            row.insert(0, month_end_date)
    return formatted_rows


def write_ranks(rank_wks, formatted_rows):
    if formatted_rows:
        rank_wks.append_rows(formatted_rows)


def get_offpage_links(raw_data, data_start_row):
    normalized_data = [normalize_row(row) for row in raw_data]
    offpage_df = pd.DataFrame(normalized_data)
    offpage_df = offpage_df.iloc[data_start_row:, :]
    offpage_df.drop(columns=[0, 2, 3, 4, 5], inplace=True)
    offpage_df = offpage_df[offpage_df[6].str.startswith("htt", na=False)]
    return offpage_df.values.tolist()


def write_offpage(worksheet, formatted_rows):
    if formatted_rows:
        worksheet.append_rows(formatted_rows)


def main():
    report_month_str = os.environ.get("REPORT_MONTH")
    explicit_month = None
    if report_month_str:
        try:
            explicit_month = datetime.strptime(report_month_str, "%m-%Y").date()
        except ValueError:
            print(f"CRITICAL ERROR: Invalid REPORT_MONTH format '{report_month_str}'. Must be MM-YYYY.")
            sys.exit(1)

    gcreds = os.environ.get("GCREDS")
    if gcreds is None:
        gc = gs.service_account(".env/auto-report-504013-af953f806f88.json")
    else:
        gc = gs.service_account_from_dict(json.loads(gcreds))

    try:
        config_sh = open_sheet_with_retry(gc, "Auto-SEO Master Config")
        config_wks = get_worksheets_with_retry(config_sh)[0]
    except (SpreadsheetNotFound, IndexError):
        print("CRITICAL ERROR: Could not find 'Auto-SEO Master Config'.")
        sys.exit(1)

    raw_config = get_all_values_with_retry(config_wks)
    company_info = (
        [dict(zip(raw_config[1], row)) for row in raw_config[2:]]
        if len(raw_config) > 2
        else []
    )
    unexpected_errors = 0
    sheets = [
        "Profile creation", "Social bookmarking", "Image submission",
        "Microblog submission", "Article submission", "Classified ads submission",
        "Article Promotion", "PDF submission", "PPT submission", "Blog Promotion",
    ]

    for company in company_info:
        if str(company.get("Status", "")).strip().lower() != "active":
            continue
        current_tab = "None"
        current_op = "open_spreadsheet"
        try:
            print(f"\n--- Processing {company['Company Name']} ---")
            sh = open_sheet_with_retry(gc, company["Active report"])
            of_sh = open_sheet_with_retry(gc, company["Offpage-links report"])
            write_sh = open_sheet_with_retry(gc, company["Looker-studio-sheet"])

            current_op = "get_worksheets"
            source_tabs = {ws.title: ws for ws in get_worksheets_with_retry(sh)}
            offpage_tabs = {ws.title: ws for ws in get_worksheets_with_retry(of_sh)}
            output_tabs = {ws.title: ws for ws in get_worksheets_with_retry(write_sh)}

            current_tab = "Profile creation"
            current_op = "source.get_all_values"
            anchor_wks = get_cached_tab(source_tabs, current_tab)
            anchor_values = get_all_values_with_retry(anchor_wks)

            try:
                reporting_month = select_reporting_month(anchor_values, date.today(), explicit_month=explicit_month)
            except ValueError as error:
                print(f"Skipping {company['Company Name']}: {error}")
                continue
            except ExplicitMonthMissingError as error:
                print(f"ERROR: {company['Company Name']}: {error}")
                unexpected_errors += 1
                continue

            print(f"Selected reporting month: {reporting_month.strftime('%B %Y')}")
            month_end_date = get_month_end_str(reporting_month)

            current_tab = "Summary (sheet1)"
            current_op = "col_values_with_retry"
            summary_wks = list(output_tabs.values())[0]
            summary_col_dates = col_values_with_retry(summary_wks, 1)

            if month_end_date in [str(value).strip() for value in summary_col_dates]:
                print(f"Report already generated for {company['Company Name']} for {month_end_date}. Skipping!")
                continue

            print("Clearing old data from all offpage tabs...")
            for sheet_name in sheets:
                if sheet_name in offpage_tabs:
                    of_wks = offpage_tabs[sheet_name]
                    current_tab = sheet_name
                    current_op = "batch_clear"
                    if of_wks.row_count > 3:
                        batch_clear_with_retry(of_wks, [f"A4:Z{of_wks.row_count}"])

            counts = {}
            for sheet_name in sheets:
                current_tab = sheet_name
                try:
                    if sheet_name == "Profile creation":
                        raw_data = anchor_values
                    else:
                        current_op = "source.get_all_values"
                        wks = get_cached_tab(source_tabs, sheet_name)
                        raw_data = get_all_values_with_retry(wks)

                    current_op = "counter"
                    total_url, data_start_row = counter(raw_data, reporting_month)
                    counts[sheet_name] = str(total_url)

                    current_op = "write_offpage"
                    of_wks = get_cached_tab(offpage_tabs, sheet_name)
                    write_offpage(of_wks, get_offpage_links(raw_data, data_start_row))
                except ValueError:
                    print(f"No data for {sheet_name}, skipping offpage links...")
                except WorksheetNotFound:
                    print(f"ERROR: Missing tab '{sheet_name}'.")
                time.sleep(1.5)

            try:
                current_tab = "Off-Page Work"
                current_op = "append_rows"
                offpage_work_wks = get_cached_tab(output_tabs, current_tab)
                write_counter(offpage_work_wks, counts, reporting_month)
            except WorksheetNotFound:
                print("ERROR: Missing tab 'Off-Page Work'.")

            try:
                current_tab = "Ranks"
                current_op = "source.get_all_values"
                kw_wks = get_cached_tab(source_tabs, "Keywords")
                rank_df = get_ranks(kw_wks, reporting_month)

                current_op = "append_rows"
                out_ranks_wks = get_cached_tab(output_tabs, current_tab)
                write_ranks(out_ranks_wks, rank_df)
            except WorksheetNotFound:
                print("ERROR: Missing 'Keywords' or 'Ranks' tab.")

            print(f"Finished processing {company['Company Name']}!")
            time.sleep(3)
        except Exception as error:
            print(f"{company.get('Company Name', 'Unknown')} | tab={current_tab} | operation={current_op}")
            print(f"Unexpected error: {error}")
            unexpected_errors += 1

    if unexpected_errors:
        print(f"Completed with {unexpected_errors} unexpected errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
