# Auto-SEO Reporting Automation

This Python application reads monthly off-page SEO data from Google Sheets and writes counts, backlinks, and keyword ranks to reporting sheets.

## Features

- Multi-company processing from `Auto-SEO Master Config`.
- Current-month reporting with previous-month fallback when the current month is absent.
- Backlink refresh from row 4 onward in off-page destination tabs.
- Duplicate prevention using the selected month-end date.
- GitHub Actions workflow with visible failures for unexpected errors.

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

For local runs, place the service-account JSON at `.env/sound-repeater-373205-94c780c6a3b8.json`. For GitHub Actions, set the `GCREDS` repository secret.

## Master Config

The `Auto-SEO Master Config` sheet uses row 2 for these headers:

`Company Name`, `Active report`, `Offpage-links report`, `Looker-studio-sheet`, `Status`

Rows with `Status` set to `Active` are processed.

Each active report must contain the expected tabs, including `Profile creation`, the fixed month-selection anchor. In GitHub Actions, a missing requested month fails the workflow; local runs use the fallback behavior described below.

## Month Selection

When running the script via GitHub Actions, you **must** explicitly select the `report_year` and `report_month` inputs from the dropdown menu (e.g., `2026` and `07`). The script will strictly process only the month you request. If the requested month is missing from the `Profile creation` tab, the workflow will explicitly fail.

When running locally without the `REPORT_MONTH` environment variable, the script falls back to checking `Profile creation` for the current month. If the current month is missing (e.g., on August 1st before data is entered), it automatically falls back to July. Output dates use the selected month’s true month-end date, such as `31/07/2026`.

## Running

Run locally:

```bash
python main.py
```

Run from GitHub: open Actions, select the Auto-SEO workflow, and choose **Run workflow**. You are required to select the target reporting year and month from the dropdowns (e.g., `2026` and `07`).

## Important notes

- Do not rename required tabs or change the Master Config headers.
- Share every configured spreadsheet with the service account as an editor.
- Rows 1–3 in off-page destination tabs contain permanent headers. The script clears data below row 3 before writing links.
- Check the GitHub Actions log when a workflow fails. Unexpected errors return a non-zero exit code.
