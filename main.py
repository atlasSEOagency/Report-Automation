import os
import pandas as pd 
import gspread as gs
import re
import json

GCREDS = os.environ.get("gcreds")
if GCREDS == None:
    gc = gs.service_account('.env/sound-repeater-373205-94c780c6a3b8.json')
else:
    gc = gs.service_account_from_dict(json.loads(GCREDS))

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
    write_wks.append_rows(formatted_rows_to_insert)





sheets=['Profile creation', 'Social bookmarking' , 'Image submission', 'Microblog submission', 'Article submission', 'Classified ads submission', 'Article Promotion', 'PDF submission', 'PPT submission', 'Blog Promotion']
counts = {}
month = '07'
year = '2026'
for sheet_name in sheets:
    counts[sheet_name] = int(counter(sheet_name,month,year))
write('test2',month,year,counts)

















    

