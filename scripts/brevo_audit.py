#!/usr/bin/env python3
"""Read-only Brevo account audit. Never prints contacts, API keys, or Teams links."""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.brevo.com/v3"
LIST_NAME = "KIWERK OS – Terminverteiler"
SENDER = "hallo@kiwerk-os.de"

def get(endpoint, key, params=None):
    url = BASE + endpoint + (("?" + urllib.parse.urlencode(params)) if params else "")
    req = urllib.request.Request(url, headers={"api-key": key, "accept": "application/json", "User-Agent": "KIWERK-setup-audit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as ex:
        # Never expose raw response bodies (may contain personal data).
        raise RuntimeError("Brevo endpoint " + endpoint + " returned HTTP " + str(ex.code)) from None

def get_lists(key):
    lists = []
    offset = 0
    while True:
        page = get("/contacts/lists", key, {"limit": 50, "offset": offset})
        chunk = page.get("lists") or []
        lists += chunk
        if len(chunk) < 50 or offset >= 4950:
            break
        offset += 50
    matches = [l for l in lists if l.get("name", "").strip().casefold() == LIST_NAME.casefold()]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one matching KIWERK Terminverteiler list, found " + str(len(matches)))
    return matches[0]

def main():
    key = os.environ.get("BREVO_API_KEY")
    if not key:
        raise RuntimeError("GitHub Actions secret BREVO_API_KEY missing")
    mailing_list = get_lists(key)
    print("Brevo Terminverteiler list identified; ID:", mailing_list.get("id"))
    try:
        senders = get("/senders", key).get("senders") or []
        matches = [s for s in senders if (s.get("email") or "").casefold() == SENDER]
        if len(matches) != 1 or not matches[0].get("active"):
            print("Brevo sender hallo@kiwerk-os.de is not verified/active (or not uniquely configured).")
        else:
            print("Brevo sender hallo@kiwerk-os.de is active; ID:", matches[0].get("id"))
    except RuntimeError as exc:
        print("Sender status unavailable; API permissions may not include senders. " + str(exc))
    try:
        campaigns = get("/emailCampaigns", key, {"status": "draft", "limit": 30, "excludeHtmlContent": "true"})
        kiwerk = [c for c in (campaigns.get("campaigns") or []) if "KIWERK" in c.get("name", "").upper()]
        print("KIWERK campaign drafts found (first page):", len(kiwerk))
    except RuntimeError as exc:
        print("Draft listing unavailable: " + str(exc))

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, urllib.error.URLError, ValueError) as exc:
        print("Brevo read-only verification failed: " + str(exc), file=sys.stderr)
        sys.exit(1)
