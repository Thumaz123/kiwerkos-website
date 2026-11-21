#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Packt zwei IONOS-taugliche ZIPs aus landingpage/ und prüft das Ergebnis.

landingpage/ ist der einzige Arbeitsordner. Alles wird dort bearbeitet. Dieses
Skript stellt daraus die Dateien zusammen, die tatsächlich auf den Webspace
gehören, prüft sie und teilt sie in deploy-1.zip und deploy-2.zip. Der
Zwischenstand entsteht in einem temporären Ordner und wird danach wieder
gelöscht, damit es keine zweite Kopie der Seite gibt, die von der Quelle
abweichen kann.

    python build_deploy.py           prüfen und zwei ZIPs schreiben
    python build_deploy.py --check   nur prüfen, keine ZIP schreiben

Warum die Prüfung nötig ist, obwohl die Seite lokal läuft: Der Webspace ist
Linux und unterscheidet Groß- und Kleinschreibung, Windows nicht. Ein Verweis
auf „Assets/site.CSS" funktioniert hier und wirft dort einen 404. Deshalb wird
jedes Pfadsegment gegen den echten Verzeichniseintrag verglichen.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
import zipfile

HIER = os.path.dirname(os.path.abspath(__file__))
QUELLE = os.path.join(HIER, "landingpage")
ALTES_PAKET = os.path.join(HIER, "deploy.zip")
PAKET_1 = os.path.join(HIER, "deploy-1.zip")
PAKET_2 = os.path.join(HIER, "deploy-2.zip")
DOMAIN = "https://www.kiwerk-os.de"

# Paket 2 enthält nur die großen Mobil- und Fernseher-Sequenzen. Paket 1
# enthält die eigentliche Website und die Desktop-Sequenz. Bei IONOS zuerst
# Paket 2, dann Paket 1 entpacken: Erst das zweite Entpacken schaltet die neue
# HTML-/JS-Version sichtbar, nachdem alle zusätzlichen Frames vorhanden sind.
PAKET_2_PREFIXE = (
    "assets/images/home-rebuild/mobile/",
    "assets/images/home-rebuild/board/",
)

# Wird in main() auf den temporären Bauordner gesetzt. Existiert nur währenddessen.
ZIEL = ""

# Was hochgeladen wird. Ausschließlich diese Dateien.
WHITELIST = [
    "index.html",
    "treffen/index.html",
    "praxis/index.html",
    "community/index.html",
    "ueber-kiwerk/index.html",
    "rueckblicke/index.html",
    "rueckblicke/2026-09-02/index.html",
    "rueckblicke/2026-10-07/index.html",
    "impressum/index.html",
    "datenschutz/index.html",
    "assets/css/events.css",
    "assets/css/wow-real.css",
    "assets/css/site.css",
    "assets/js/events-data.js",
    "assets/js/events.js",
    "assets/js/site.js",
    "assets/fonts/archivo-latin.woff2",
    "assets/fonts/archivo-latin-ext.woff2",
    "assets/fonts/OFL.txt",        # SIL OFL verlangt, dass die Lizenz mitgeht
    "assets/images/share.png",     # Sharing-Bild, per og:image absolut verlinkt
    "assets/images/mark.svg",
    "assets/images/meetings/2026-09-02/raum-rueckblick.jpg",
    "assets/images/meetings/2026-09-02/raum-treffen.jpg",
    "assets/images/meetings/2026-09-02/telegram-pruefung.jpg",
    "assets/images/meetings/2026-09-02/telegram-quellen.jpg",
    "assets/images/meeting-preview/group.webp",
    "assets/images/meeting-preview/conversation-poster.webp",
    "assets/images/meeting-preview/conversation.mp4",
    "assets/downloads/kiwerk-os-automatisierungsideen-01.pdf",
    "sitemap.xml",
    "robots.txt",
    ".htaccess",                   # http-auf-https und Sicherheitskopfzeilen
]

# Kamerafahrt der aktuellen Startseite. Desktop und Mobil haben 180 Frames,
# die Board-Variante 157. Jede Variante besitzt vier Bildebenen und zwei
# Projektionsdateien.
HOME_FRAMES = {
    f"assets/images/home-rebuild/{variant}{kind}-{frame:04d}.webp"
    for variant in ("", "mobile/")
    for kind in ("frame", "mask", "glass", "laptops")
    for frame in range(1, 181)
}
HOME_FRAMES |= {
    f"assets/images/home-rebuild/board/{kind}-{frame:04d}.webp"
    for kind in ("frame", "mask", "glass", "laptops")
    for frame in range(1, 158)
}
HOME_FRAMES |= {
    f"assets/images/home-rebuild/{variant}{name}.json"
    for variant in ("", "mobile/", "board/")
    for name in ("projection", "screens")
}
WHITELIST += ["assets/css/home.css", "assets/js/home.js"] + sorted(HOME_FRAMES)

PLATZHALTER = {"thomas.jpg", "hero-osnabrueck.mp4"}
# Fremdtext, der nicht angefasst werden darf.
UNVERAENDERT = {"assets/fonts/OFL.txt"}

# Fest benannte Herstellerdateien; keine Website-Texte. Die Lizenzkoepfe bleiben
# unveraendert. Import-Scanner und Vendor-Hashpruefung folgen erst in Phase B.
WOW_VENDOR = {
    "assets/vendor/three.module.js", "assets/vendor/three.core.js",
    "assets/vendor/gsap.min.js", "assets/vendor/scrolltrigger.min.js",
    "assets/vendor/three-license.txt", "assets/vendor/gsap-license.txt",
}
UNVERAENDERT |= WOW_VENDOR

befunde: list[str] = []


def fehler(wo: str, was: str) -> None:
    befunde.append(f"{wo}: {was}")


def sha(pfad: str) -> str:
    with open(pfad, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ═════════════════════════════════════════════════════════════════  Bauen  ══
def offene_punkte_entfernen(text: str) -> tuple[str, int]:
    """Entfernt Kommentarblöcke mit einem offenen „[ ]“ aus dem HTML.

    Die Kommentare in der Quelle sind die Dokumentation der Seite und bleiben
    dort. Was nicht online gehört, sind die unerledigten Punkte: Ein Satz wie
    „[ ] Auftragsverarbeitungsvertrag abschließen“ ist über „Seitenquelltext
    anzeigen“ für jeden lesbar und damit eine schriftliche Selbstauskunft über
    eine offene Pflicht. Erklärende Kommentare ohne [ ] bleiben erhalten.
    """
    entfernt = 0

    def ersetzen(treffer: re.Match) -> str:
        nonlocal entfernt
        if "[ ]" not in treffer.group(0):
            return treffer.group(0)
        entfernt += 1
        return ""

    text = re.sub(r"[ \t]*<!--.*?-->\n?", ersetzen, text, flags=re.S)
    return text, entfernt


def bauen() -> None:
    if os.path.exists(ZIEL):
        shutil.rmtree(ZIEL)
    offen_gesamt = 0
    for rel in WHITELIST:
        q = os.path.join(QUELLE, rel.replace("/", os.sep))
        z = os.path.join(ZIEL, rel.replace("/", os.sep))
        if not os.path.exists(q):
            raise SystemExit(f"Fehlt in der Quelle: {rel}")
        os.makedirs(os.path.dirname(z), exist_ok=True)

        if rel.endswith(".html"):
            roh = open(q, encoding="utf-8").read()
            sauber, entfernt = offene_punkte_entfernen(roh)
            offen_gesamt += entfernt
            with open(z, "w", encoding="utf-8", newline="") as fh:
                fh.write(sauber)
            if "[ ]" in open(z, encoding="utf-8").read():
                raise SystemExit(f"Offener Punkt bleibt im Paket: {rel}")
        else:
            shutil.copy2(q, z)
            if sha(q) != sha(z):
                raise SystemExit(f"Kopie weicht ab: {rel}")

    print(f"zusammengestellt: {len(WHITELIST)} Dateien")
    if offen_gesamt:
        print(f"  {offen_gesamt} Kommentarblöcke mit offenen Punkten entfernt")


# ═══════════════════════════════════════════════════════════════  Prüfen  ══
def echte_schreibweise(basis: str, rel: str):
    """Löst rel unter basis auf und meldet Abweichungen in der Schreibweise."""
    cur = basis
    for teil in rel.replace("\\", "/").split("/"):
        if teil in ("", "."):
            continue
        if teil == "..":
            cur = os.path.dirname(cur)
            continue
        try:
            eintraege = os.listdir(cur)
        except (NotADirectoryError, FileNotFoundError):
            return None, f"Pfad existiert nicht: {rel}"
        if teil in eintraege:
            cur = os.path.join(cur, teil)
            continue
        treffer = [e for e in eintraege if e.lower() == teil.lower()]
        if treffer:
            return None, f"Schreibweise weicht ab: „{teil}“ heißt auf der Platte „{treffer[0]}“"
        return None, f"Datei fehlt: {rel}"
    return cur, None


def pruefen() -> None:
    vorhanden = set()
    for dp, dn, fn in os.walk(ZIEL):
        for f in fn:
            vorhanden.add(os.path.relpath(os.path.join(dp, f), ZIEL).replace(os.sep, "/"))

    if "index.html" not in vorhanden:
        fehler("Paket", "index.html fehlt im Wurzelverzeichnis")

    seiten = sorted(r for r in vorhanden if r.endswith("index.html"))
    verwiesen: set[str] = set()

    for rel in sorted(vorhanden):
        if not rel.endswith((".html", ".css")):
            continue
        pfad = os.path.join(ZIEL, rel.replace("/", os.sep))
        roh = open(pfad, encoding="utf-8").read()
        basis = os.path.dirname(pfad)

        if rel.endswith(".html"):
            text = re.sub(r"<!--.*?-->", "", roh, flags=re.S)   # Kommentare zählen nicht
            refs = re.findall(r'(?:href|src|poster)="([^"]+)"', text)
            # og:image und canonical stehen in content="…" und zeigen absolut
            refs += [u for u in re.findall(r'content="([^"]+)"', text) if u.startswith(DOMAIN)]
        else:
            refs = re.findall(r'url\(["\']?([^"\')]+)["\']?\)', roh)

        for r in refs:
            if r.startswith(DOMAIN):                            # eigene absolute URL
                lokal = r[len(DOMAIN):].lstrip("/").split("?")[0].split("#")[0]
                if not lokal:
                    continue
                ziel = lokal + "index.html" if lokal.endswith("/") else lokal
                verwiesen.add(ziel)
                if ziel not in vorhanden:
                    fehler(rel, f"eigene URL zeigt auf nichts im Paket: {r}")
                continue
            if r.startswith(("http://", "https://")):
                if "wa.me" in r and f"wa.me/4917661305799?text=" not in r:
                    fehler(rel, f"WhatsApp-Link abweichend: {r[:70]}")
                continue
            if r.startswith("mailto:"):
                klar = urllib.parse.unquote(r.replace("&amp;", "&"))
                if not klar.startswith("mailto:hallo@kiwerk-os.de"):
                    fehler(rel, f"Mail-Adresse abweichend: {klar[:50]}")
                if "—" in klar or "–" in klar:
                    fehler(rel, "Gedankenstrich im Mailto (kodiert), erscheint in Betreff oder Text")
                continue
            if r.startswith(("data:", "tel:", "#")) or not r:
                continue

            # Cache-Buster gehören zur URL, nicht zum Dateinamen auf dem Webspace.
            zielrel = r.split("?")[0].split("#")[0]
            if not zielrel:
                continue
            aufgeloest, problem = echte_schreibweise(basis, zielrel)
            if problem:
                if os.path.basename(zielrel) in PLATZHALTER:
                    continue
                fehler(rel, f"{r}: {problem}")
                continue
            if not os.path.abspath(aufgeloest).startswith(os.path.abspath(ZIEL)):
                fehler(rel, f"Verweis verlässt das Paket: {r}")
                continue
            if os.path.isdir(aufgeloest):
                aufgeloest = os.path.join(aufgeloest, "index.html")
                if not os.path.exists(aufgeloest):
                    fehler(rel, f"Ordner ohne index.html: {r}")
            verwiesen.add(os.path.relpath(aufgeloest, ZIEL).replace(os.sep, "/"))

    # ── Nichts Überflüssiges im Paket
    # Dateien, auf die naturgemäß kein href oder src zeigt.
    ohne_verweis = {"robots.txt", "sitemap.xml", "index.html", "assets/fonts/OFL.txt", ".htaccess"}
    # Phase A: lokale JS-Abhaengigkeiten werden gezielt benannt. Sie werden erst
    # auf geeigneten Desktop-Geraeten dynamisch geladen, nicht im HTML verlinkt.
    ohne_verweis |= HOME_FRAMES | WOW_VENDOR
    for rel in sorted(vorhanden):
        if rel not in verwiesen and rel not in ohne_verweis and not rel.endswith("index.html"):
            fehler("Paket", f"liegt im Paket, wird aber nirgends gebraucht: {rel}")

    # ── Keine Gedankenstriche, keine Entwicklungsspuren, kein Build nötig
    for rel in sorted(vorhanden):
        if not rel.endswith((".html", ".css", ".js", ".xml", ".txt")) or rel in UNVERAENDERT:
            continue
        t = open(os.path.join(ZIEL, rel.replace("/", os.sep)), encoding="utf-8").read()
        # Ohne Kommentare: hier geht es um echte Aufrufe. Ein Kommentar, der
        # „kein Aufruf an fonts.googleapis.com" dokumentiert, ist kein Aufruf.
        ohne = re.sub(r"<!--.*?-->", "", t, flags=re.S)
        ohne = re.sub(r"/\*.*?\*/", "", ohne, flags=re.S)

        for muster, was in (   # gilt auch für Kommentare
            (r"—|–", "Gedankenstrich"),
            (r"%E2%80%9[34]", "kodierter Gedankenstrich"),
            (r"localhost|127\.0\.0\.1", "localhost-Verweis"),
            (r"file:///|[A-Z]:\\\\", "absoluter lokaler Pfad"),
            (r"sourceMappingURL|\.js\.map|\.css\.map", "Sourcemap"),
            (r"node_modules|package\.json|webpack|vite", "Build-Werkzeug"),
        ):
            if re.search(muster, t):
                fehler(rel, f"{was} gefunden")

        for muster, was in (   # nur echte Aufrufe und Elemente
            (r'(?:href|src)="[^"]*\.md"', "Verweis auf eine Markdown-Datei"),
            (r"fonts\.(googleapis|gstatic)", "Google Fonts"),
            (r"<form\b", "Formular"),
            (r"google-analytics|googletagmanager|connect\.facebook|matomo", "Tracking"),
        ):
            if re.search(muster, ohne):
                fehler(rel, f"{was} gefunden")

    # ── Dateinamen: klein, ohne Leerzeichen, ohne Sonderzeichen
    for dp, dn, fn in os.walk(ZIEL):
        for n in dn + fn:
            if " " in n:
                fehler("Dateiname", f"Leerzeichen in {n}")
            if any(ord(c) > 127 for c in n):
                fehler("Dateiname", f"Sonderzeichen in {n}")
            if n != n.lower() and n not in ("OFL.txt",):
                fehler("Dateiname", f"Großbuchstaben in {n}")

    # ── SEO-Pflichtangaben je Seite
    titel, beschr = {}, {}
    for s in seiten:
        t = open(os.path.join(ZIEL, s.replace("/", os.sep)), encoding="utf-8").read()
        url = DOMAIN + "/" + ("" if s == "index.html" else s[: -len("index.html")])
        if t.count("<h1") != 1:
            fehler(s, f"{t.count('<h1')} H1 (genau 1 erwartet)")
        if f'rel="canonical" href="{url}"' not in t:
            fehler(s, f"canonical fehlt oder zeigt nicht auf {url}")
        if 'name="description"' not in t:
            fehler(s, "meta description fehlt")
        if 'rel="icon" href="data:image/svg+xml' not in t:
            fehler(s, "Favicon fehlt")
        for pflicht in ("impressum/", "datenschutz/"):
            if pflicht not in t:
                fehler(s, f"Pflichtlink fehlt: {pflicht}")
        ti = re.search(r"<title>(.*?)</title>", t, re.S)
        de = re.search(r'name="description" content="(.*?)"', t, re.S)
        for kasten, wert, name in ((titel, ti and ti.group(1), "Titel"), (beschr, de and de.group(1), "Description")):
            if not wert:
                fehler(s, f"{name} fehlt")
            elif wert in kasten:
                fehler(s, f"{name} doppelt mit {kasten[wert]}")
            else:
                kasten[wert] = s

    # ── sitemap.xml und robots.txt
    sm = open(os.path.join(ZIEL, "sitemap.xml"), encoding="utf-8").read()
    for s in seiten:
        url = DOMAIN + "/" + ("" if s == "index.html" else s[: -len("index.html")])
        if f"<loc>{url}</loc>" not in sm:
            fehler("sitemap.xml", f"{url} fehlt")
    if sm.count("<loc>") != len(seiten):
        fehler("sitemap.xml", f"{sm.count('<loc>')} Einträge, {len(seiten)} Seiten im Paket")
    rt = open(os.path.join(ZIEL, "robots.txt"), encoding="utf-8").read()
    if f"Sitemap: {DOMAIN}/sitemap.xml" not in rt:
        fehler("robots.txt", "Sitemap-Zeile fehlt oder zeigt woanders hin")

    groesse = sum(os.path.getsize(os.path.join(ZIEL, r.replace("/", os.sep))) for r in vorhanden)
    print(f"geprüft: {len(vorhanden)} Dateien, {len(seiten)} Seiten, {groesse / 1024:.0f} KB")


def packen() -> None:
    """Teilt den geprüften Bauordner verlustfrei auf zwei ZIP-Dateien auf.

    Die Dateien liegen im Archiv direkt auf oberster Ebene, nicht in einem
    Unterordner. Beide Archive werden im selben Webroot entpackt und ergeben
    zusammen exakt den zuvor vollständig geprüften Bauordner.
    """
    alle = sorted(
        os.path.relpath(os.path.join(dp, name), ZIEL).replace(os.sep, "/")
        for dp, _, namen in os.walk(ZIEL)
        for name in namen
    )
    teil_2 = [rel for rel in alle if rel.startswith(PAKET_2_PREFIXE)]
    teil_1 = [rel for rel in alle if rel not in teil_2]

    if not teil_1 or not teil_2:
        raise SystemExit("Paketaufteilung ist leer oder unvollständig")
    if set(teil_1) & set(teil_2) or set(teil_1) | set(teil_2) != set(alle):
        raise SystemExit("Paketaufteilung ist nicht disjunkt und vollständig")

    # Das alte Ein-Paket-Artefakt darf nach einem erfolgreichen Neubau nicht
    # neben den zwei aktuellen Paketen liegen und versehentlich hochgeladen
    # werden. Alle drei Dateien sind reproduzierbare Build-Artefakte.
    for pfad in (ALTES_PAKET, PAKET_1, PAKET_2):
        if os.path.exists(pfad):
            os.remove(pfad)

    for pfad, dateien in ((PAKET_1, teil_1), (PAKET_2, teil_2)):
        with zipfile.ZipFile(
            pfad, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archiv:
            for rel in dateien:
                archiv.write(
                    os.path.join(ZIEL, rel.replace("/", os.sep)), arcname=rel
                )
        with zipfile.ZipFile(pfad) as archiv:
            if set(archiv.namelist()) != set(dateien):
                raise SystemExit(f"Archivinhalt unvollständig: {os.path.basename(pfad)}")
        print(
            f"{os.path.basename(pfad)} geschrieben: {len(dateien)} Dateien, "
            f"{os.path.getsize(pfad) / 1024:.0f} KB"
        )


def main() -> int:
    global ZIEL
    nur_pruefen = "--check" in sys.argv
    ZIEL = tempfile.mkdtemp(prefix="kiwerk-build-")
    try:
        bauen()
        pruefen()
        if befunde:
            print(f"\n{len(befunde)} BEFUNDE:")
            for b in befunde:
                print("  !", b)
            print("\nNichts geschrieben, solange Befunde offen sind.")
            return 1
        if nur_pruefen:
            print("\nAlles in Ordnung. Keine ZIP geschrieben (--check).")
            return 0
        packen()
    finally:
        shutil.rmtree(ZIEL, ignore_errors=True)
    print("\nAlles in Ordnung. Bei IONOS zuerst deploy-2.zip und danach deploy-1.zip im selben Webroot entpacken.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
