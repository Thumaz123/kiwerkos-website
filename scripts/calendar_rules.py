"""Calendar primitives for the KIWERK event automation.

This module deliberately does not publish or infer event details.
"""
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class RuleEvent:
    day: date
    format: str
    holiday: str | None = None


def easter_sunday(year: int) -> date:
    """Gregorian Easter, used for Lower Saxony's movable holidays."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def holidays(year: int) -> dict[date, str]:
    easter = easter_sunday(year)
    return {
        date(year, 1, 1): "Neujahr",
        easter - timedelta(days=2): "Karfreitag",
        easter + timedelta(days=1): "Ostermontag",
        date(year, 5, 1): "Tag der Arbeit",
        easter + timedelta(days=39): "Christi Himmelfahrt",
        easter + timedelta(days=50): "Pfingstmontag",
        date(year, 10, 3): "Tag der Deutschen Einheit",
        date(year, 10, 31): "Reformationstag",
        date(year, 12, 25): "1. Weihnachtstag",
        date(year, 12, 26): "2. Weihnachtstag",
    }


def rule_events(today: date, months_ahead: int = 6) -> list[RuleEvent]:
    """Return current/future rule dates through the full target month.

    Keep the event on its calendar day when no end time is known.
    Confirmed exceptions must be merged by the caller before publication.
    """
    if months_ahead < 6:
        raise ValueError("At least six months of preview are required")
    result = []
    for offset in range(months_ahead + 1):
        y, m = divmod(today.year * 12 + today.month - 1 + offset, 12)
        first = date(y, m + 1, 1)
        thursday = first + timedelta(days=(3 - first.weekday()) % 7)
        for day, kind in ((thursday, "Präsenz"), (thursday + timedelta(days=14), "Online")):
            if day >= today:
                result.append(RuleEvent(day, kind, holidays(day.year).get(day)))
    return result
