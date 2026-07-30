from datetime import date
import os
import pandas as pd 
import gspread as gs
import re
import json
import time

GCREDS = os.environ.get("GCREDS")
if GCREDS == None:
    gc = gs.service_account('.env/sound-repeater-373205-94c780c6a3b8.json')
else:
    gc = gs.service_account_from_dict(json.loads(GCREDS))

config_sh = gc.open('Auto-SEO Master Config')
config_wks = config_sh.sheet1
raw_config = config_wks.get_all_values()
if len(raw_config) > 2:
    headers = raw_config[1]
    company_info = [dict(zip(headers, row)) for row in raw_config[2:]]
else:
    company_info = []

sh = None
of_sh = None
write_sh = None

def counter(sheet_name):
    wks = sh.worksheet(sheet_name)
    raw_data = wks.get_all_values()
    df = pd.DataFrame(raw_data)

    now = date.today()
    month_name = now.strftime('%B')
    month_row = None
    for x,val in enumerate(df[0]): 
        if re.search(rf"0?{now.month}[./]{now.year}\b|{month_name}",str(val),re.IGNORECASE):
            month_row = x+1
            break         
    month_data =df[6].iloc[month_row :]
    total_url = month_data[month_data.str.startswith('htt',na=False)].count()
    
    if month_row is None:
        raise ValueError("No match")

    return total_url,month_row


def write_counter(sheet_name,counts):
    now = date.today()
    write_wks = write_sh.worksheet(sheet_name)
    write_data = write_wks.get_all_records(1)
    df2 = pd.DataFrame(write_data)
    count_val = list(counts.values())
    count_key = list(counts.keys())
    rows_insert =[[],[],[]]
    for x in range(len(counts)):
        rows_insert[0].append(f"30/{now.month}/{now.year}")
        rows_insert[2].append(count_val[x])
        rows_insert[1].append(count_key[x])

    formatted_rows_to_insert = list(map(list, zip(*rows_insert)))
    write_wks.append_rows(formatted_rows_to_insert)

def get_ranks (sheet_name):
    rank_wks = sh.worksheet(sheet_name)
    rank_data = rank_wks.get_all_values()
    rank_df = pd.DataFrame(rank_data)
    rank_df= rank_df.iloc[3:-7].reset_index(drop=True)
    rank_df.drop(columns=0, inplace=True)

    ranks =  rank_df.iloc[:, -4 : ]
    keywords =  rank_df.iloc[:, : 2  ]
    rank_df = pd.concat([keywords,ranks],axis=1)
    now = date.today()
    formatted_rank_rows = rank_df.values.tolist()
    for x in range(len(formatted_rank_rows)):
        if formatted_rank_rows[x][1] != "":
            formatted_rank_rows[x].insert(0,f"{now.day}/{now.month}/{now.year}")
    return formatted_rank_rows


def write_ranks(sheet_namee,formatted_rank_rows):
    ranks_write_wks = write_sh.worksheet(sheet_namee)
    ranks_write_wks.append_rows(formatted_rank_rows)

def get_offpage_links(sheet_name,month_row):
    offpage_wks = sh.worksheet(sheet_name)
    offpage_df = pd.DataFrame(offpage_wks.get_all_values())
    offpage_df =offpage_df.iloc[month_row:,:]
    offpage_df.drop(columns=[0,2,3,4,5],inplace=True)

    offpage_df = offpage_df[offpage_df[6].str.startswith('htt',na=False)]
    offpage_df.head(15)

    formatted_offpage_rows = offpage_df.values.tolist()
    return formatted_offpage_rows

def write_offpage(sheet_name,formatted_offpage_rows):
    sheet=sheet_name
    of_wks = of_sh.worksheet(sheet)
    
    # Delete everything below row 3
    if of_wks.row_count > 3:
        of_wks.batch_clear([f'A4:Z{of_wks.row_count}'])
        
    if formatted_offpage_rows:
        of_wks.append_rows(formatted_offpage_rows)


#------#
# MAIN LOOP
#------#
for company in company_info:
    try:
        if str(company.get("Status", "")).strip().lower() == "active":
            print(f"\n--- Processing {company['Company Name']} ---")
            
            # Reassign global sheets for this company
            sh = gc.open(company["Active report"])
            of_sh = gc.open(company["Offpage-links report"])
            write_sh = gc.open(company["Looker-studio-sheet"])
            
            # --- DUPLICATE CHECK ---
            summary_wks = write_sh.worksheet('test2')
            existing_dates = summary_wks.col_values(1)
            
            now = date.today()
            month_name = now.strftime('%B')
            
            already_run = False
            for val in existing_dates:
                if re.search(rf"0?{now.month}[./]{now.year}\b|{month_name}", str(val), re.IGNORECASE):
                    already_run = True
                    break
                    
            if already_run:
                print(f"Report already generated for {company['Company Name']} this month. Skipping!")
                continue
            # -----------------------

            # counting & offpage links
            sheets=['Profile creation', 'Social bookmarking' , 'Image submission', 'Microblog submission', 'Article submission', 'Classified ads submission', 'Article Promotion', 'PDF submission', 'PPT submission', 'Blog Promotion']
            counts = {}

            for sheet_name in sheets:
                try:
                    total_url, month_row = counter(sheet_name)
                    counts[sheet_name] = str(total_url)
                    write_offpage(sheet_name, get_offpage_links(sheet_name, month_row))
                except ValueError:
                    print(f"No data for {sheet_name}, skipping offpage links...")
                
                # Sleep to prevent hitting Google Sheets 60 requests/minute rate limit
                time.sleep(1.5)

            # Write the final summary counts
            write_counter('test2', counts)
                
            # Rankings
            write_ranks("test3", get_ranks("Updated Keywords"))
            
            print(f"Finished processing {company['Company Name']}!")
            
    except Exception as e:
        print(f"Error processing {company.get('Company Name', 'Unknown')}: {e}")
