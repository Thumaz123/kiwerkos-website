"""Calendar primitives for the KIWERK event automation.

This module deliberately does not publish or infer event details.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from collections.abc import Iterable


@dataclass(frozen=True)
class RuleEvent:
    day: date
    format: str
    holiday: str | None = None


@dataclass(frozen=True)
class ConfirmedException:
    """A decision tied to its original rule slot, not inferred from a new date."""
    original_day: date
    format: str
    new_day: date | None = None
    cancelled: bool = False


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


def apply_exceptions(events: Iterable[RuleEvent], exceptions: Iterable[ConfirmedException],
                     today: date) -> list[RuleEvent]:
    """Apply explicit decisions, rejecting ambiguous slots and collisions.

    Callers must supply all relevant rule slots, including past original dates
    for events moved into the future. Cancellations are omitted from this list.
    """
    events = list(events)
    by_key = {(event.day, event.format): event for event in events}
    if len(by_key) != len(events):
        raise ValueError("Duplicate rule slots")
    used = set()
    for decision in exceptions:
        key = (decision.original_day, decision.format)
        if key in used or key not in by_key:
            raise ValueError("Duplicate or unknown exception slot")
        if decision.cancelled and decision.new_day is not None:
            raise ValueError("Cancellation cannot specify a new date")
        used.add(key)
        old = by_key.pop(key)
        if not decision.cancelled:
            day = decision.new_day or old.day
            new_key = (day, old.format)
            if new_key in by_key:
                raise ValueError("Exception collides with another event")
            by_key[new_key] = RuleEvent(day, old.format, holidays(day.year).get(day))
    return sorted((event for event in by_key.values() if event.day >= today),
                  key=lambda event: (event.day, event.format))
