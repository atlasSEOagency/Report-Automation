# Auto-SEO Agency Manual

## Rules

1. Keep required tab names unchanged: `Profile creation`, `Off-Page Work`, `Ranks`, `Keywords`, and the off-page activity tabs.
2. Keep rows 1–3 of off-page destination tabs reserved for headers. The script clears data below row 3 before writing links.
3. Keep the Master Config headers unchanged:
   `Company Name`, `Active report`, `Offpage-links report`, `Looker-studio-sheet`, `Status`.
4. Use standard dates in the `Off-Page Work` date column.
5. Do not run the workflow while someone is editing the destination sheets.

## Month selection

When generating the report in GitHub Actions, you **must explicitly select the reporting year and month from the dropdown menus** (e.g., `2026` and `07`). The script will verify that exact month exists in `Profile creation`. If data for your requested month does not exist, the workflow will intentionally fail and alert you, preventing empty or inaccurate reports from being generated.

*(Note for developers running the script locally without the month specified: it automatically falls back to checking the current month, and if empty, the previous month. If neither exists, it silently skips the company.)*

## Client setup

1. Create the active, off-page, and Looker Studio spreadsheets.
2. Add the required tabs.
3. Share all three spreadsheets with the service account as an editor.
4. Add the exact spreadsheet names to `Auto-SEO Master Config`.
5. Set `Status` to `Active`.
6. Run the GitHub Actions workflow and select the target reporting year and month from the dropdowns (e.g., `2026` and `07`).

## Troubleshooting

Open GitHub Actions and inspect the failed job log. Missing tabs, missing permissions, invalid configuration, and other unexpected errors produce a failed workflow. Fix the reported sheet or configuration, then run the workflow again.
