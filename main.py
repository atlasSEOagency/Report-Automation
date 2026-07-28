from datetime import date
import os
import pandas as pd 
import gspread as gs
import re
import json
from datetime import date


GCREDS = os.environ.get("GCREDS")
if GCREDS == None:
    gc = gs.service_account('.env/sound-repeater-373205-94c780c6a3b8.json')
else:
    gc = gs.service_account_from_dict(json.loads(GCREDS))

sh = gc.open("RAPTOR DYNAMIC  Offpage Worksheet")
write_sh = gc.open("Raptor report -Draft")





    
def counter (sheet_name):

    wks = sh.worksheet(sheet_name)
    raw_data = wks.get_all_values()
    df = pd.DataFrame(raw_data)

    now = date.today()
    month_row = None
    for x,val in enumerate(df[0]): 
        if re.search(rf"{now.month}[./]{now.year}\b",str(val),re.IGNORECASE):
            month_row = x+1
            break         
    month_data =df[6].iloc[month_row :]
    total_url = month_data[month_data.str.startswith('htt',na=False)].count()
    

    if month_row is None:
        return 0
    return total_url


def write(sheet_name,counts):
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
    ranks_write_data = ranks_write_wks.get_all_records(2)
    ranks_write_df = pd.DataFrame(ranks_write_data)
    ranks_write_wks.append_rows(formatted_rank_rows)





# counting 
sheets=['Profile creation', 'Social bookmarking' , 'Image submission', 'Microblog submission', 'Article submission', 'Classified ads submission', 'Article Promotion', 'PDF submission', 'PPT submission', 'Blog Promotion']
counts = {}
for sheet_name in sheets:
    counts[sheet_name] = int(counter(sheet_name))
write('test2',counts)

# Rankings
write_ranks("test3",get_ranks("Updated 40 Keywords"))

# Offpage links













    

