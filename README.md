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

## Reporting Month & Cycle

When running the script, you **must** supply both `REPORT_MONTH` and `REPORT_CYCLE` environment variables.

- **`REPORT_MONTH`**: Must strictly be in `YYYY-MM` format (e.g., `2026-08`).
- **`REPORT_CYCLE`**: Must strictly be `All`, `1-1`, or `15-15`.

The script processes companies based on the `REPORT_CYCLE`:
- **`All`**: Processes both `client info 1-1` and `client info 15-15` tabs from the Master Config.
- **`1-1`**: Processes only the `client info 1-1` tab. Uses a standard month boundaries (day 1 to month-end).
- **`15-15`**: Processes only the `client info 15-15` tab. Uses boundaries from the 15th of the previous month to the 15th of the selected month (e.g. `15/07/2026` to `15/08/2026`).

Date rows may use full dates (e.g. `16/07/2026`) or month/day labels used by the source sheets (e.g. `July 16`). A date label applies to following URL rows until the next date label. The selected reporting window still resolves the year and applies inclusive boundaries. A URL row with a malformed date or no preceding date fails the company.

## Running

Run locally:

```bash
export REPORT_MONTH=2026-08
export REPORT_CYCLE=15-15
python main.py
```

Run from GitHub: open Actions, select the Auto-SEO workflow, and choose **Run workflow**. You are required to select the target reporting year, month, and reporting cycle from the dropdowns.

## Important notes

- Do not rename required tabs or change the Master Config headers.
- Share every configured spreadsheet with the service account as an editor.
- Rows 1–3 in off-page destination tabs contain permanent headers. The script clears data below row 3 before writing links.
- Check the GitHub Actions log when a workflow fails. Unexpected errors return a non-zero exit code.
