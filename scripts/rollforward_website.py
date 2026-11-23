#!/usr/bin/env python3
"""Update KIWERK static HTML from the approved monthly Thursday rule.

Only event-marked HTML and the dated meeting meta description are changed.
The existing browser-side events.js continues to enhance the same page.
No secrets, attendees, or Teams links are ever written here.
"""
from __future__ import annotations
import argparse
import calendar
import html
import json
import re
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from calendar_rules import holidays  # existing tested, deterministic calendar rule

HOME = ROOT / "landingpage/index.html"
MEETING = ROOT / "landingpage/treffen/index.html"
DATA = ROOT / "landingpage/assets/js/events-data.js"

def month_n(d: date, n: int) -> tuple[int, int]:
    y, m = divmod(d.year * 12 + d.month - 1 + n, 12)
    return y, m + 1

def thursday(y: int, m: int, nth: int) -> date:
    start = date(y, m, 1)
    return start + timedelta(days=(3 - start.weekday()) % 7 + 7 * (nth - 1))

def events(today: date, config: dict) -> list[dict]:
    rows = []
    online = config.get("online") or {}
    for n in range(7):
        y, m = month_n(today, n)
        for kind, nth in (("Präsenz", 1), ("Online", 3)):
            day = thursday(y, m, nth)
            iso = day.isoformat()
            if day < today:
                continue
            if kind == "Online":
                if iso < online.get("start", "9999-12-31") or iso in online.get("excluded", []):
                    continue
                info = {"date": iso, "format": kind, "price": online.get("price"), "time": online.get("time"),
                        "status": "planned", "access": online.get("access", "Teilnahmelink per E-Mail erhalten")}
            else:
                if iso < config.get("start", "0001-01-01"):
                    continue
                info = {"date": iso, "format": kind, "price": config.get("price"), "time": None,
                        "status": "planned", "city": config.get("city", "Osnabrück")}
                info.update((config.get("overrides") or {}).get(iso, {}))
                if info.get("visibility") == "hidden" or info.get("status") == "cancelled":
                    continue
            info["holiday"] = holidays(day.year).get(day)
            rows.append(info)
    return sorted(rows, key=lambda x: (x["date"], x["format"]))

def esc(s) -> str:
    return html.escape(str(s), quote=True)

def german(iso: str) -> str:
    return iso[8:10] + "." + iso[5:7] + "." + iso[:4]

def row(e: dict) -> str:
    iso = e["date"]
    online = e["format"] == "Online"
    price = e.get("price")
    price_text = "kostenlos" if price == 0 else (f"{price} € pro Person" if price is not None else "")
    meta = ("Online" if online else "Osnabrück") + (" · " + price_text if price_text else "") + " · geplant"
    holiday = f"<p class=\"event-details\">Feiertagskonflikt: {esc(e['holiday'])}. Termin noch zu bestätigen.</p>" if e["holiday"] else ""
    if online:
        details = ["Online über Microsoft Teams", e.get("time") or "Uhrzeit folgt", "Teilnahmelink wird per E-Mail verschickt."]
        button = '<a class="ticket-button" href="#termin-erinnerung">Link per E-Mail erhalten</a>'
    else:
        details = [e.get("venue") or "Ort folgt", e.get("time") or "Uhrzeit folgt", "Details und Tickets folgen."]
        button = '<button class="ticket-button" type="button" disabled>Details folgen</button>'
        # Never reuse an old ticket URL automatically, unless confirmation and verification exist.
        if e.get("ticket_verified") and e.get("status") == "confirmed" and e.get("venue") and e.get("time"):
            url = str(e.get("ticket_url") or "")
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.scheme == "https" and parsed.hostname in {"eventfrog.de", "www.eventfrog.de", "eventfrog.ch", "www.eventfrog.ch"}:
                button = f'<a class="ticket-button" href="{esc(url)}" rel="noopener noreferrer">Tickets buchen</a>'
    detail = "<br>".join(esc(x) for x in details)
    return ('<article class="event-row' + (' event-row--online' if online else '') +
            f'"><div><time datetime="{iso}">{german(iso)}</time><p>{esc(meta)}</p></div>'
            f'<div><p class="event-details">{detail}</p>{holiday}{button}</div></article>')

def event_list_markup(future: list[dict], today: date) -> str:
    """Show three soonest dates on the landing page, with the rest in a disclosure."""
    immediate = "".join(map(row, future[:3]))
    remaining = "".join(map(row, future[3:]))
    more = (
        '<details class="event-list__more"><summary>Weitere Termine anzeigen</summary>'
        '<div class="event-list__additional">' + remaining + '</div></details>'
    ) if remaining else ""
    return ('<section class="event-list" id="termine"><h2>Termine &amp; Tickets</h2>'
            '<p>Jeden ersten Donnerstag im Monat vor Ort in Osnabrück, zwei Wochen später online. '
            'Beim jeweiligen Termin steht, wie die Teilnahme funktioniert.</p>'
            '<div class="event-list__upcoming">' + immediate + '</div>'
            + more +
            f'<noscript><p>Terminstand: {today.isoformat()}. Termine werden täglich aktualisiert.</p></noscript></section>')


def rewrite(today: date) -> bool:
    match = re.match(r"\s*window\.KIWERK_EVENTS\s*=\s*(\{.*\})\s*;\s*$", DATA.read_text(encoding="utf-8"), re.S)
    if not match:
        raise ValueError("Cannot parse existing website event configuration")
    cfg = json.loads(match.group(1))
    future = events(today, cfg)
    physical = [e for e in future if e["format"] == "Präsenz"]
    if not future or not physical:
        raise ValueError("No eligible future meetings")
    next_p = physical[0]
    home = HOME.read_text(encoding="utf-8")
    termin_list = event_list_markup(future, today)
    home, c1 = re.subn(r'<section class="event-list" id="termine">.*?</section>', lambda _: termin_list, home, count=1, flags=re.S)
    if c1 != 1:
        raise ValueError("Event list marker not found exactly once")
    home, c2 = re.subn(r'<span data-next-date>[^<]*</span>', '<span data-next-date>' + german(next_p["date"]) + '</span>', home)
    if c2 != 1:
        raise ValueError("Homepage next-date marker is ambiguous")
    home, c3 = re.subn(r'<time class="event-date" datetime="[^"]*">.*?</time>',
                        lambda _: f'<time class="event-date" datetime="{next_p["date"]}">{next_p["date"][8:10]}.{next_p["date"][5:7]}.<span>Donnerstag · {next_p["date"][:4]} · geplant</span></time>', home, count=1, flags=re.S)
    if c3 != 1:
        raise ValueError("Homepage hero time marker missing")
    # The hero is enhanced by browser JS, but the no-JS fallback also must not advertise old details.
    home, c4 = re.subn(r'<div class="event-place"><strong>.*?</strong><span>.*?</span></div>',
                        lambda _: '<div class="event-place"><strong>Osnabrück</strong><span>' +
                        (esc(str(next_p["price"]) + " € pro Person") if next_p.get("price") is not None else "Teilnahme folgt") +
                        '</span></div>', home, count=1, flags=re.S)
    if c4 != 1:
        raise ValueError("Hero event-place marker missing")
    home, c5 = re.subn(r'<p class="event-details">.*?</p>',
                        lambda _: '<p class="event-details">' +
                        esc(next_p.get("venue") or "Ort folgt") + '<br>' +
                        esc(next_p.get("time") or "Uhrzeit folgt") +
                        '<br>Teilnahmedetails folgen.</p>', home, count=1, flags=re.S)
    if c5 != 1:
        raise ValueError("Hero event-details missing")
    meet = MEETING.read_text(encoding="utf-8")
    meet, c6 = re.subn(r'Nächstes Treffen vor Ort am \d{2}\.\d{2}\.\d{4}',
                        lambda _: 'Nächstes Treffen vor Ort am ' + german(next_p["date"]), meet)
    if c6 < 1:
        raise ValueError("Meeting page metadata marker missing")
    changed = False
    for path, new in ((HOME, home), (MEETING, meet)):
        if path.read_text(encoding="utf-8") != new:
            path.write_text(new, encoding="utf-8")
            changed = True
    print("Upcoming from", today, "first physical", next_p["date"], "events", len(future), "changed", changed)
    return changed

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", help="YYYY-MM-DD override for dry-run/testing")
    a = parser.parse_args()
    today = date.fromisoformat(a.today) if a.today else __import__("datetime").datetime.now(ZoneInfo("Europe/Berlin")).date()
    rewrite(today)
