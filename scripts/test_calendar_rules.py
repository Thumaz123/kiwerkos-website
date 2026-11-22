import unittest
from datetime import date

from calendar_rules import easter_sunday, rule_events


class CalendarRulesTest(unittest.TestCase):
    def test_known_dates_and_holiday(self):
        events = rule_events(date(2026, 11, 22))
        self.assertEqual([(e.day.isoformat(), e.format) for e in events[:4]], [
            ("2026-12-03", "Präsenz"), ("2026-12-17", "Online"),
            ("2027-01-07", "Präsenz"), ("2027-01-21", "Online"),
        ])
        self.assertEqual(next(e for e in events if e.day == date(2027, 5, 6)).holiday, "Christi Himmelfahrt")

    def test_day_after_and_same_day(self):
        self.assertEqual(rule_events(date(2026, 12, 3))[0].day, date(2026, 12, 3))
        self.assertEqual(rule_events(date(2026, 12, 4))[0].day, date(2026, 12, 17))

    def test_preview_deduplication_and_year_boundary(self):
        events = rule_events(date(2026, 12, 31))
        self.assertEqual((events[-1].day.year, events[-1].day.month), (2027, 6))
        self.assertEqual(len(events), len({(e.day, e.format) for e in events}))
        self.assertTrue(all(e.day.weekday() == 3 for e in events))

    def test_easter_and_invalid_horizon(self):
        self.assertEqual(easter_sunday(2027), date(2027, 3, 28))
        with self.assertRaises(ValueError):
            rule_events(date(2026, 1, 1), 5)


if __name__ == "__main__":
    unittest.main()
