import datetime
import os
import gspread
from gspread.exceptions import WorksheetNotFound
from retry_helper import get_all_values_with_retry, open_sheet_with_retry, paced_append_rows, paced_update

class RunLedger:
    def __init__(self, gc: gspread.Client):
        self.gc = gc
        self.sh = open_sheet_with_retry(gc, "Auto-SEO Master Config")
        self.tab_name = "Run Logs"
        self.headers = ["Key", "Status", "Started At", "Completed At", "Error", "GitHub Run ID"]
        try:
            self.wks = self.sh.worksheet(self.tab_name)
        except WorksheetNotFound:
            self.wks = self.sh.add_worksheet(title=self.tab_name, rows=1000, cols=10)
            paced_append_rows(self.wks, [self.headers])
        
        self.dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"

    def _get_all(self):
        return get_all_values_with_retry(self.wks)

    def _find_row_idx(self, key):
        data = self._get_all()
        for idx, row in enumerate(data):
            if row and row[0] == key:
                return idx + 1  # 1-indexed for gspread
        return None

    def get_entry(self, key):
        data = self._get_all()
        if not data:
            return None
        
        headers = data[0]
        for row in data[1:]:
            if row and row[0] == key:
                # Pad row to match headers length
                padded_row = row + [""] * (len(headers) - len(row))
                return dict(zip(headers, padded_row))
        return None

    def _find_next_empty_row(self):
        data = self._get_all()
        return len(data) + 1

    def log_start(self, key, run_id):
        if self.dry_run:
            print(f"[DRY RUN] Ledger: log_start({key}, {run_id})")
            return
            
        now = datetime.datetime.utcnow().isoformat() + "Z"
        row_idx = self._find_row_idx(key)
        new_row = [key, "STARTED", now, "", "", str(run_id)]
        
        if row_idx:
            paced_update(self.wks, f"A{row_idx}:F{row_idx}", [new_row])
        else:
            next_idx = self._find_next_empty_row()
            paced_update(self.wks, f"A{next_idx}:F{next_idx}", [new_row])

    def log_success(self, key):
        if self.dry_run:
            print(f"[DRY RUN] Ledger: log_success({key})")
            return
            
        now = datetime.datetime.utcnow().isoformat() + "Z"
        row_idx = self._find_row_idx(key)
        if not row_idx:
            print(f"Warning: Tried to log_success for {key} but not found in ledger.")
            return
            
        # Get existing row to preserve 'Started At' and 'Run ID'
        row_data = self.wks.row_values(row_idx)
        padded = row_data + [""] * (6 - len(row_data))
        padded[1] = "COMPLETED"
        padded[3] = now
        padded[4] = "" # Clear errors
        
        paced_update(self.wks, f"A{row_idx}:F{row_idx}", [padded])

    def log_failure(self, key, error_msg):
        if self.dry_run:
            print(f"[DRY RUN] Ledger: log_failure({key}, {error_msg})")
            return
            
        now = datetime.datetime.utcnow().isoformat() + "Z"
        row_idx = self._find_row_idx(key)
        if not row_idx:
            print(f"Warning: Tried to log_failure for {key} but not found in ledger.")
            return
            
        row_data = self.wks.row_values(row_idx)
        padded = row_data + [""] * (6 - len(row_data))
        padded[1] = "FAILED"
        padded[3] = now
        padded[4] = str(error_msg)
        
        self.wks.update(f"A{row_idx}:F{row_idx}", [padded])
