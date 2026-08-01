# Auto-SEO Reporting Automation

This repository contains an automated Python application designed to process monthly Off-Page SEO reports, calculate submission metrics across multiple platforms, extract valid backlinks, and automatically push the summarized data into a Master Looker Studio Google Sheet.

It is built for **scale**, meaning you can manage an unlimited number of clients without ever touching the Python code.

## 🌟 Key Features
- **Multi-Company Architecture**: Driven by a central "Master Config" Google Sheet. Add or remove clients by simply updating rows in the spreadsheet.
- **Smart Data Wiping**: Automatically clears out previous month's link data (preserving your headers) before inserting the fresh batch of keywords.
- **Duplicate Run Prevention**: Safely scans the Looker Studio summary sheet before processing. If a report for the current month has already been generated, it skips it to prevent duplicate data entries.
- **API Rate-Limit Protection**: Intelligently pauses between Google Sheet API requests (`time.sleep`) to prevent hitting Google's `429 Quota Exceeded` errors.
- **Semi-Automated Cloud Trigger**: Fully integrated with GitHub Actions. You can trigger the script on-demand straight from your browser.

---

## ⚙️ Setup & Configuration

### 1. Service Account Credentials
This script uses `gspread` to interact with Google Sheets. You must have a Google Cloud Service Account with the Google Sheets API enabled.
- **Local Development**: Save your service account JSON file inside the `.env/` folder (this folder is ignored by git).
- **GitHub Actions**: Copy the exact contents of your Service Account JSON file and add it as a Repository Secret in GitHub:
  - Go to **Settings > Secrets and variables > Actions**
  - Add a New Secret named `GCREDS`.

### 2. The "Master Config" Sheet
The entire script is controlled by a Google Sheet named exactly: **`Auto-SEO Master Config`**.
Ensure your service account email is invited as an Editor to this sheet.

**Sheet Structure:**
- **Row 1**: (Optional) Title / Instructions
- **Row 2**: Exact Headers: `Company Name`, `Active report`, `Offpage-links report`, `Looker-studio-sheet`, `Status`
- **Rows 3+**: Your client data. (If `Status` is set to `Active`, the script will process them).

### 3. Client Sheet Requirements
For each client, the script expects 3 Google Sheets (defined in the Master Config):
1. **Active report**: Contains tabs like `Profile creation`, `Social bookmarking`, etc.
2. **Offpage-links report**: The script will clear everything below Row 3 on these tabs and paste the new links.
3. **Looker-studio-sheet**: The destination for the final metric counts and Keyword Ranks.

---

## 🚀 How to Run the Script

### Option A: Running on GitHub Actions (Recommended)
You do not need to use the terminal to run this script. Non-technical team members can execute it directly from GitHub:
1. Go to the **Actions** tab in this GitHub repository.
2. Click on the **Auto-SEO Processor** workflow on the left sidebar.
3. Click the **Run workflow** dropdown button on the right side of the screen.
4. Click **Run workflow** to start the process. 
5. You can click into the job to watch the terminal logs in real-time.

### Option B: Running Locally
If you want to test the script on your local machine:
1. Ensure you have Python installed.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the script:
   ```bash
   python main.py
   ```

---

## ⚠️ Important Notes & Troubleshooting

- **Renaming Tabs**: The script currently expects specific tab names in your client sheets. For example, it searches for a tab named exactly **`Keywords`** to pull ranks. If you rename these tabs in Google Sheets, the script will crash. You must update `main.py` to match the new tab names.
- **Missing Data**: If a client didn't do any "Blog Promotion" for a specific month, the script will gracefully print `"No data for Blog Promotion... Skipping"` and move on without crashing.
- **Clearing Data**: The `write_offpage` function is hardcoded to clear data from **Row 4 downwards**. It assumes Rows 1, 2, and 3 contain permanent headers. Do not put data you wish to keep below Row 3.
