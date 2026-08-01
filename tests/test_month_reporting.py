import unittest
from datetime import date

from main import write_counter
from reporting import find_month_row, get_month_end_str, select_reporting_month


class TestMonthReporting(unittest.TestCase):
    def test_find_month_row_matches_target(self):
        values = [[""], ["August 2026"], [""], ["17/08/2026"]]
        self.assertEqual(find_month_row(values, date(2026, 8, 1)), 1)
        self.assertEqual(find_month_row(values, date(2026, 8, 20)), 1)

    def test_find_month_row_rejects_wrong_year(self):
        values = [[""], ["August 2025"], [""], ["17/08/2025"]]
        self.assertIsNone(find_month_row(values, date(2026, 8, 1)))

    def test_find_month_row_numeric_format(self):
        values = [[""], ["08/2026"], [""], ["17/08/2026"]]
        self.assertEqual(find_month_row(values, date(2026, 8, 1)), 1)

    def test_select_reporting_month_current(self):
        selected = select_reporting_month([[""], ["August 2026"]], date(2026, 8, 1))
        self.assertEqual(selected, date(2026, 8, 1))

    def test_select_reporting_month_fallback(self):
        selected = select_reporting_month([[""], ["July 2026"]], date(2026, 8, 1))
        self.assertEqual(selected, date(2026, 7, 1))

    def test_select_reporting_month_no_data(self):
        with self.assertRaises(ValueError):
            select_reporting_month([[""], ["June 2026"]], date(2026, 8, 1))

    def test_month_end_calculation(self):
        self.assertEqual(get_month_end_str(date(2026, 7, 1)), "31/07/2026")
        self.assertEqual(get_month_end_str(date(2026, 2, 1)), "28/02/2026")
        self.assertEqual(get_month_end_str(date(2024, 2, 1)), "29/02/2024")


class FakeWorksheet:
    def __init__(self):
        self.appended_rows = None

    def append_rows(self, rows):
        self.appended_rows = rows


class FakeSpreadsheet:
    def __init__(self):
        self.worksheet_obj = FakeWorksheet()

    def worksheet(self, name):
        return self.worksheet_obj


class TestOutputGuards(unittest.TestCase):
    def test_empty_counts_do_not_append_blank_rows(self):
        write_sh = FakeSpreadsheet()
        write_counter(write_sh, "Off-Page Work", {}, date(2026, 7, 1))
        self.assertIsNone(write_sh.worksheet_obj.appended_rows)
