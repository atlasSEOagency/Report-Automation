# Auto-SEO Agency Manual

## Rules

1. Keep required tab names unchanged: `Profile creation`, `Off-Page Work`, `Ranks`, `Keywords`, and the off-page activity tabs.
2. Keep rows 1–3 of off-page destination tabs reserved for headers. The script clears data below row 3 before writing links.
3. Keep the Master Config headers unchanged:
   `Company Name`, `Active report`, `Offpage-links report`, `Looker-studio-sheet`, `Status`.
4. Use standard dates in the `Off-Page Work` date column.
5. Do not run the workflow while someone is editing the destination sheets.

## Month selection

The script uses `Profile creation` as the month anchor. It selects the current month when that month exists. If the current month has no header, it selects the previous month. For example, a run on August 1 can produce a July report dated `31/07/2026`.

If neither month exists, the script skips that company and writes nothing. It continues with other companies.

## Client setup

1. Create the active, off-page, and Looker Studio spreadsheets.
2. Add the required tabs.
3. Share all three spreadsheets with the service account as an editor.
4. Add the exact spreadsheet names to `Auto-SEO Master Config`.
5. Set `Status` to `Active`.
6. Run the GitHub Actions workflow.

## Troubleshooting

Open GitHub Actions and inspect the failed job log. Missing tabs, missing permissions, invalid configuration, and other unexpected errors produce a failed workflow. Fix the reported sheet or configuration, then run the workflow again.
