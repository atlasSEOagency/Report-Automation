# Auto-SEO Agency Manual

## Rules

1. Keep required tab names unchanged: `Profile creation`, `Off-Page Work`, `Ranks`, `Keywords`, and the off-page activity tabs.
2. Keep rows 1–3 of off-page destination tabs reserved for headers. The script clears data below row 3 before writing links.
3. Keep the Master Config headers unchanged:
   `Company Name`, `Active report`, `Offpage-links report`, `Looker-studio-sheet`, `Status`.
4. Use standard dates in the `Off-Page Work` date column.
5. Do not run the workflow while someone is editing the destination sheets.

## Month and Cycle selection

When generating the report in GitHub Actions, you **must explicitly select the reporting year, month, and reporting cycle from the dropdown menus** (e.g., `2026`, `07`, and `15-15`).

- The script will strictly process only the month and cycle you request.
- If data for your requested month does not exist, the workflow will intentionally fail and alert you, preventing empty or inaccurate reports from being generated.
- Source sheets may use full dates (e.g. `16/07/2026`) or month/day labels (e.g. `July 16`). Each date label applies to the URL rows below it until the next date label. Malformed dates or URL rows with no preceding date will fail that company.

## Client setup

1. Create the active, off-page, and Looker Studio spreadsheets.
2. Add the required tabs.
3. Share all three spreadsheets with the service account as an editor.
4. Add the exact spreadsheet names to `Auto-SEO Master Config`.
5. Set `Status` to `Active`.
6. Run the GitHub Actions workflow and select the target reporting year, month, and cycle from the dropdowns.

## Troubleshooting

Open GitHub Actions and inspect the failed job log. Missing tabs, missing permissions, invalid configuration, and other unexpected errors produce a failed workflow. Fix the reported sheet or configuration, then run the workflow again.
