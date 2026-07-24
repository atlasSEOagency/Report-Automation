import pandas as pd 
import gspread as gs
import re
import os
import json
from datetime import datetime

# Read from GitHub Secrets in production, fallback to local file in development
credentials_json = os.environ.get("GOOGLE_CREDENTIALS")
if credentials_json:
    creds_dict = json.loads(credentials_json)
    gc = gs.service_account_from_dict(creds_dict)
else:
    gc = gs.service_account(".env/sound-repeater-373205-94c780c6a3b8.json")

sh = gc.open("RAPTOR DYNAMIC  Offpage Worksheet")
write_sh = gc.open("Raptor report -Draft")

def counter (sheet_name,month,year):
    wks = sh.worksheet(sheet_name)
    raw_data = wks.get_all_values()
    df = pd.DataFrame(raw_data)

    month_row = None
    for x,val in enumerate(df[0]): 
        if re.search(rf"{month}[./]{year}\b",str(val),re.IGNORECASE):
            month_row = x+1
            break         
    month_data =df[6].iloc[month_row :]
    total_url = month_data[month_data.str.startswith('htt',na=False)].count()
    
    if month_row is None:
        return 0
    return total_url

def write(sheet_name,month,year,counts):
    write_wks = write_sh.worksheet(sheet_name)
    write_data = write_wks.get_all_records(1)
    df2 = pd.DataFrame(write_data)
    count_val = list(counts.values())
    count_key = list(counts.keys())
    rows_insert =[[],[],[]]
    for x in range(len(counts)):
        rows_insert[0].append(f"30/{month}/{year}")
        rows_insert[2].append(count_val[x])
        rows_insert[1].append(count_key[x])

    formatted_rows_to_insert = list(map(list, zip(*rows_insert)))
    print(formatted_rows_to_insert)
    write_wks.append_rows(formatted_rows_to_insert)

sheets=['Profile creation', 'Social bookmarking' , 'Image submission', 'Microblog submission', 'Article submission', 'Classified ads submission', 'Article Promotion', 'PDF submission', 'PPT submission', 'Blog Promotion']
counts = {}

# Dynamically get the current month and year
now = datetime.now()
month = now.strftime("%m")  # e.g., '07'
year = now.strftime("%Y")   # e.g., '2026'

print(f"Running SEO Report for {month}/{year}...")

for sheet_name in sheets:
    counts[sheet_name] = int(counter(sheet_name,month,year))

# Ensure we have data before writing
if sum(counts.values()) > 0:
    write('test2',month,year,counts)
    print("Report written successfully!")
else:
    print("No data found for this month, skipping write.")
