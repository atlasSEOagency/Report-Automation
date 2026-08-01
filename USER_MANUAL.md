# Auto-SEO: Agency User Manual & Standard Operating Procedure (SOP)

This document is the official rulebook for using the Auto-SEO Automation. Because this script automatically reads from and writes to live Google Sheets, **strict adherence to these rules is required** to prevent data loss or script crashes.

---

## 🛑 STRICT RULES: WHAT *NOT* TO DO

Users can easily break the automation if they change the structure of the spreadsheets. **NEVER** do the following:

1. **NEVER Rename Tabs (Worksheets)**
   - The script is hardcoded to look for specific tab names (e.g., `Profile creation`, `Off-Page Work`, `Ranks`, `Social bookmarking`).
   - If you rename a tab in Google Sheets (even adding a space at the end), the script will crash with a `WorksheetNotFound` error.

2. **NEVER Change the Row Structure of Off-Page Reports**
   - The script assumes **Rows 1, 2, and 3** contain permanent headers/titles.
   - Every month, the script **wipes all data from Row 4 downwards**. If you put important manual notes below Row 3, they will be permanently deleted when the script runs.

3. **NEVER Change Master Config Column Headers**
   - In the `Auto-SEO Master Config` sheet, Row 2 contains the headers (`Company Name`, `Active report`, `Offpage-links report`, `Looker-studio-sheet`, `Status`). Do not rename, move, or delete these columns.

4. **NEVER Type Random Text in the Looker Studio "Date" Column**
   - The script checks Column A of the `Off-Page Work` tab to prevent duplicate runs. It expects standard date formats. Typing notes like "Pending" in the Date column will break the duplicate checker.

5. **NEVER Run the Script While Manually Editing**
   - Do not trigger the GitHub Action while someone is actively typing inside the Looker Studio destination sheet. Wait until manual reporting is finished before clicking "Run".

---

## ✅ BEST PRACTICES: WHAT *TO* DO

Follow these steps to ensure smooth monthly reporting:

1. **ALWAYS Share New Sheets with the Service Account**
   - When you onboard a new client and create their 3 Google Sheets, you **must** click "Share" and invite the Service Account email address as an **Editor**.
   - If you forget this step, the script will crash because it doesn't have permission to view the file.

2. **ALWAYS Copy/Paste Exact Sheet Names**
   - When adding a new client to the Master Config, copy the Google Sheet names exactly as they appear in Google Drive. Typos are the #1 cause of failure.

3. **ALWAYS Use "Active" for Live Clients**
   - In the Master Config sheet, the script only processes rows where the Status is exactly `Active`.
   - To pause a client (e.g., they churned or paused their contract), simply change their status to `Paused`, `Inactive`, or leave it blank. You do not need to delete their row.

4. **ALWAYS Check the GitHub Logs if Something Breaks**
   - If a user breaks a rule, the script will stop and print a helpful error message.
   - Go to GitHub -> Actions -> Click the failed run -> Click the job.
   - Scroll to the bottom of the black terminal window. It will tell you exactly which client and which sheet caused the error (e.g., `Error processing RAPTOR DYNAMIC: WorksheetNotFound: 'Updated Keywords'`).

---

## 🛠️ How to Add a New Client (Checklist)

1. [ ] Create the 3 required Google Sheets for the client.
2. [ ] Ensure the tabs inside those sheets are named correctly.
3. [ ] Click "Share" on all 3 sheets and add the Service Account email as an Editor.
4. [ ] Open `Auto-SEO Master Config`.
5. [ ] Add a new row.
6. [ ] Paste the exact names of the 3 sheets.
7. [ ] Type `Active` in the Status column.
8. [ ] Go to GitHub and click **Run Workflow**!
