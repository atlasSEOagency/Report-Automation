import json
import os
import sys
import time
from datetime import date

import gspread as gs
import pandas as pd
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound

from reporting import find_month_row, get_month_end_str, select_reporting_month


def counter(raw_data, reporting_month):
    df = pd.DataFrame(raw_data)

    header_row = find_month_row(raw_data, reporting_month)
    if header_row is None:
        raise ValueError("No match")

    data_start_row = header_row + 1
    month_data = df[6].iloc[data_start_row:]
    total_url = month_data[month_data.str.startswith("htt", na=False)].count()
    return total_url, data_start_row


def write_counter(write_sh, sheet_name, counts, reporting_month):
    if not counts:
        return

    write_wks = write_sh.worksheet(sheet_name)
    rows_insert = [[], [], []]
    month_end_date = get_month_end_str(reporting_month)
    for key, value in counts.items():
        rows_insert[0].append(month_end_date)
        rows_insert[1].append(key)
        rows_insert[2].append(value)

    write_wks.append_rows(list(map(list, zip(*rows_insert))))


def get_ranks(sh, sheet_name, reporting_month):
    rank_wks = sh.worksheet(sheet_name)
    rank_df = pd.DataFrame(rank_wks.get_all_values())
    rank_df = rank_df.iloc[3:-7].reset_index(drop=True)
    rank_df.drop(columns=0, inplace=True)

    rank_df = pd.concat([rank_df.iloc[:, :2], rank_df.iloc[:, -4:]], axis=1)
    formatted_rows = rank_df.values.tolist()
    month_end_date = get_month_end_str(reporting_month)
    for row in formatted_rows:
        if row[1] != "":
            row.insert(0, month_end_date)
    return formatted_rows


def write_ranks(write_sh, sheet_name, formatted_rows):
    if formatted_rows:
        write_sh.worksheet(sheet_name).append_rows(formatted_rows)


def get_offpage_links(raw_data, data_start_row):
    offpage_df = pd.DataFrame(raw_data)
    offpage_df = offpage_df.iloc[data_start_row:, :]
    offpage_df.drop(columns=[0, 2, 3, 4, 5], inplace=True)
    offpage_df = offpage_df[offpage_df[6].str.startswith("htt", na=False)]
    return offpage_df.values.tolist()


def write_offpage(of_sh, sheet_name, formatted_rows):
    worksheet = of_sh.worksheet(sheet_name)
    if worksheet.row_count > 3:
        worksheet.batch_clear([f"A4:Z{worksheet.row_count}"])
    if formatted_rows:
        worksheet.append_rows(formatted_rows)


def main():
    gcreds = os.environ.get("GCREDS")
    if gcreds is None:
        gc = gs.service_account(".env/sound-repeater-373205-94c780c6a3b8.json")
    else:
        gc = gs.service_account_from_dict(json.loads(gcreds))

    try:
        config_wks = gc.open("Auto-SEO Master Config").sheet1
    except SpreadsheetNotFound:
        print("CRITICAL ERROR: Could not find 'Auto-SEO Master Config'.")
        sys.exit(1)

    raw_config = config_wks.get_all_values()
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
        try:
            print(f"\n--- Processing {company['Company Name']} ---")
            sh = gc.open(company["Active report"])
            of_sh = gc.open(company["Offpage-links report"])
            write_sh = gc.open(company["Looker-studio-sheet"])

            anchor_values = sh.worksheet("Profile creation").get_all_values()
            try:
                reporting_month = select_reporting_month(anchor_values, date.today())
            except ValueError as error:
                print(f"Skipping {company['Company Name']}: {error}")
                continue

            month_end_date = get_month_end_str(reporting_month)
            print(f"Selected reporting month ending: {month_end_date}")
            if month_end_date in [str(value).strip() for value in write_sh.sheet1.col_values(1)]:
                print(f"Report already generated for {company['Company Name']} for {month_end_date}. Skipping!")
                continue

            counts = {}
            for sheet_name in sheets:
                try:
                    raw_data = sh.worksheet(sheet_name).get_all_values()
                    total_url, data_start_row = counter(raw_data, reporting_month)
                    counts[sheet_name] = str(total_url)
                    write_offpage(of_sh, sheet_name, get_offpage_links(raw_data, data_start_row))
                except ValueError:
                    print(f"No data for {sheet_name}, skipping offpage links...")
                except WorksheetNotFound:
                    print(f"ERROR: Missing tab '{sheet_name}'.")
                time.sleep(1.5)

            try:
                write_counter(write_sh, "Off-Page Work", counts, reporting_month)
            except WorksheetNotFound:
                print("ERROR: Missing tab 'Off-Page Work'.")

            try:
                write_ranks(write_sh, "Ranks", get_ranks(sh, "Keywords", reporting_month))
            except WorksheetNotFound:
                print("ERROR: Missing 'Keywords' or 'Ranks' tab.")

            print(f"Finished processing {company['Company Name']}!")
            time.sleep(3)
        except Exception as error:
            print(f"Unexpected error processing {company.get('Company Name', 'Unknown')}: {error}")
            unexpected_errors += 1

    if unexpected_errors:
        print(f"Completed with {unexpected_errors} unexpected errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
