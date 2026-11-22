"""Regression tests for the website rollforward and publication markup."""
import unittest
from datetime import date
from rollforward_website import events, row, thursday, german

CONFIG = {
    "start": "2026-11-05", "city": "Osnabrück", "price": None,
    "online": {"start": "2026-11-19", "label": "Online", "price": 0},
    "overrides": {"2026-12-03": {"price": 10}}
}

class WebsiteRollforwardTests(unittest.TestCase):
    def test_expired_november_meeting_removed(self):
        upcoming = events(date(2026, 11, 22), CONFIG)
        days = [e["date"] for e in upcoming]
        self.assertNotIn("2026-11-19", days)
        self.assertEqual(days[:4], ["2026-12-03", "2026-12-17", "2027-01-07", "2027-01-21"])

    def test_after_thursday_rollforward(self):
        upcoming = events(date(2026, 12, 4), CONFIG)
        self.assertEqual(upcoming[0]["date"], "2026-12-17")
        self.assertEqual(next(e["date"] for e in upcoming if e["format"] == "Präsenz"), "2027-01-07")

    def test_same_day_is_still_visible(self):
        upcoming = events(date(2026, 12, 3), CONFIG)
        self.assertEqual(upcoming[0]["date"], "2026-12-03")

    def test_holiday_flagged_without_moving_it(self):
        upcoming = events(date(2027, 5, 1), CONFIG)
        x = next(e for e in upcoming if e["date"] == "2027-05-06")
        self.assertEqual(x["holiday"], "Christi Himmelfahrt")
        self.assertIn("Feiertagskonflikt", row(x))

    def test_private_teams_url_never_exported(self):
        cfg = dict(CONFIG)
        cfg["online"] = dict(CONFIG["online"], access="https://teams.microsoft.com/private-secret")
        upcoming = events(date(2026, 12, 1), cfg)
        online = next(e for e in upcoming if e["format"] == "Online")
        self.assertNotIn("teams.microsoft.com", row(online))
        self.assertIn("E-Mail", row(online))

    def test_html_escaping(self):
        e = {"date": "2027-01-07", "format": "Präsenz", "venue": '<script>alert("x")</script>',
             "price": None, "time": None, "holiday": None, "status": "planned"}
        text = row(e)
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)

if __name__ == "__main__":
    unittest.main()
