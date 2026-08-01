# Smart Monthly Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Generate July reports automatically on August 1 when August source data does not exist, while preventing silent successful runs.

**Architecture:** Move pure month logic into an import-safe module. Select one deterministic reporting period per company before processing; pass it to counting and all writers. Preserve existing Google Sheets calls and tab layout.

**Tech Stack:** Python 3.10, pandas, gspread, stdlib `unittest`, GitHub Actions.

## Global Constraints

- Do not write to Google Sheets during tests.
- Current month is preferred; previous month is fallback only when current-month source data is absent.
- Use the selected reporting month for duplicate detection and output dates.
- Preserve rows 1–3 in off-page destination tabs.
- Unexpected exceptions must produce a non-zero workflow exit.

---

### Task 1: Add pure month-selection tests

**Files:**
- Create: `tests/test_month_reporting.py`
- Create: `reporting.py` only after tests fail

**Interfaces:**
- `find_month_row(values, target_month) -> int | None`
- `select_reporting_month(sheet_values, today) -> date`

- [ ] Test `find_month_row()` matches the target month/year and rejects the same month in another year.
- [ ] Test a missing current month with July data selects July 2026.
- [ ] Test no current or previous month raises a clear `ValueError`.
- [ ] Run: `env/bin/python -m unittest tests/test_month_reporting.py -v`
- [ ] Confirm initial failures are caused by missing helpers.

### Task 2: Implement safe month selection

**Files:**
- Modify: `reporting.py`
- Modify: `main.py:34-52`

**Interfaces:**
- `counter(sheet_name, reporting_month) -> tuple[int, int]`
- `find_month_row(values, target_month) -> int | None`

- [ ] Implement matching without slicing when no row exists.
- [ ] Use `Profile creation` as the explicit per-company anchor tab; select current month if present, otherwise previous calendar month.
- [ ] Count URLs only after a valid row is found.
- [ ] Run the focused tests; expected: PASS.

### Task 3: Propagate the selected period to all outputs

**Files:**
- Modify: `main.py:54-89, 141-184`
- Modify: `tests/test_month_reporting.py`

- [ ] Check duplicate runs against the selected month, not always `date.today()`.
- [ ] Pass `reporting_month` into `write_counter()` and `get_ranks()`.
- [ ] Write the selected month’s date into Off-Page Work and Ranks.
- [ ] Continue skipping tabs with no selected-month data, while processing tabs that do have data.
- [ ] Add tests asserting July fallback produces July output dates.
- [ ] Run: `env/bin/python -m unittest tests/test_month_reporting.py -v`

### Task 4: Make workflow failures visible

**Files:**
- Modify: `main.py:116-186`
- Modify: `tests/test_month_reporting.py`

- [ ] Move credential loading, config loading, and the company loop into `main()`; keep imports side-effect free.
- [ ] Track unexpected company errors.
- [ ] Re-raise or exit non-zero after processing so GitHub Actions cannot report a false success.
- [ ] Keep expected missing-tab/no-data handling non-fatal.
- [ ] Test that an unexpected exception causes a non-zero result.

### Task 5: Update operational documentation

**Files:**
- Modify: `README.md`
- Modify: `USER_MANUAL.md`

- [ ] Document current-month preference and previous-month fallback on month boundaries.
- [ ] Document that unexpected errors fail the workflow and must be reviewed in Actions logs.
- [ ] Remove wording that implies every run always reports the current calendar month.

### Task 6: Full verification and handoff

- [ ] Run: `env/bin/python -m unittest discover -s tests -v`.
- [ ] Run: `env/bin/python -m py_compile main.py`.
- [ ] Run injected fake-gspread tests proving tests never open or write live sheets.
- [ ] Inspect `git diff` and confirm only intended files changed.
- [ ] Commit with: `git commit -m "fix: fallback to previous month when source data is missing"`.
- [ ] Trigger GitHub Actions manually and verify logs show the selected month, non-empty counts, and successful sheet writes.
