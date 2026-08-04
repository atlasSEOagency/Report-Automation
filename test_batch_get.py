import json
import gspread as gs
gc = gs.service_account(".env/auto-report-504013-af953f806f88.json")
sh = gc.open("TOTAL GROUP OF COMPANIES Offpage Worksheet")
res = sh.values_batch_get(["'Profile creation'", "'Social bookmarking'"])
print(res.keys())
print(res['valueRanges'][0]['valueRange']['values'][0:2])
