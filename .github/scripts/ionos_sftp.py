"""Manueller SFTP-Check und Upload ohne Löschvorgänge."""
import os
import posixpath
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import paramiko


def required(name):
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"GitHub Secret {name} fehlt")
    return value


def path_setting(name):
    value = required(name)
    if not value.startswith("/") or ".." in value.split("/"):
        raise ValueError(f"{name} muss ein absoluter Pfad ohne '..' sein")
    return posixpath.normpath(value)


def overlapping(a, b):
    return a == b or a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/")


def site_files():
    checkout = Path("site")
    root = checkout / "landingpage"
    tracked = subprocess.check_output(["git", "-C", str(checkout), "ls-files", "-z", "--", "landingpage/"]).decode("utf-8").split("\0")
    files = []
    for name in filter(None, tracked):
        path = Path(name).relative_to("landingpage")
        local = root / path
        if local.is_symlink() or not local.is_file():
            raise ValueError("Website enthält eine unzulässige Datei")
        files.append((local, path.as_posix()))
    if not any(name == "index.html" for _, name in files):
        raise ValueError("index.html fehlt in der gewählten Version")
    # Große Bildsequenzen vor HTML übertragen; die Startseite zuletzt.
    return sorted(files, key=lambda item: (item[1] == "index.html", item[1].endswith(".html"), item[1]))


def ensure_directory(sftp, base, relative):
    current = base
    for part in relative.split("/") if relative else []:
        current = posixpath.join(current, part)
        try:
            attrs = sftp.lstat(current)
        except FileNotFoundError:
            sftp.mkdir(current)
            attrs = sftp.lstat(current)
        if not stat.S_ISDIR(attrs.st_mode):
            raise ValueError("Zielverzeichnis ist kein reguläres Verzeichnis")


def main():
    mode = required("DEPLOY_MODE")
    if mode not in {"check", "test", "production"}:
        raise ValueError("Ungültiger Modus")
    webroot = path_setting("SFTP_WEBROOT")
    testroot = path_setting("SFTP_TEST_ROOT") if mode != "check" else None
    files = site_files()
    host, user, password = required("SFTP_HOST"), required("SFTP_USER"), required("SFTP_PASSWORD")
    port = int(os.environ.get("SFTP_PORT") or "22")
    known_hosts = required("SFTP_KNOWN_HOSTS")
    client = paramiko.SSHClient()
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as known_file:
        known_file.write(known_hosts + "\n")
        known_file.flush()
        client.load_host_keys(known_file.name)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(hostname=host, port=port, username=user, password=password, look_for_keys=False, allow_agent=False, timeout=20)
        try:
            with client.open_sftp() as sftp:
                webroot = sftp.normalize(webroot)
                if webroot == "/" or not stat.S_ISDIR(sftp.stat(webroot).st_mode):
                    raise ValueError("Webroot muss ein bestehendes Verzeichnis außer '/' sein")
                if mode == "check":
                    print(f"Verbindung und Webroot geprüft; {len(files)} Website-Dateien ausgewählt.")
                    return
                testroot = sftp.normalize(testroot)
                if testroot == "/" or overlapping(webroot, testroot):
                    raise ValueError("Webroot und Testordner müssen getrennte, bestehende Verzeichnisse sein")
                if not stat.S_ISDIR(sftp.stat(testroot).st_mode):
                    raise ValueError("Zielverzeichnis fehlt")
                print(f"Verbindung und Zielverzeichnisse geprüft; {len(files)} Website-Dateien ausgewählt.")
                base = webroot if mode == "production" else posixpath.join(testroot, "run-" + required("GITHUB_RUN_ID") + "-" + required("GITHUB_RUN_ATTEMPT"))
                if mode == "test":
                    sftp.mkdir(base)  # Muss neu sein; kein bestehender Test wird überschrieben.
                for local, name in files:
                    ensure_directory(sftp, base, posixpath.dirname(name))
                    dest = posixpath.join(base, name)
                    try:
                        attrs = sftp.lstat(dest)
                    except FileNotFoundError:
                        attrs = None
                    if attrs is not None and not stat.S_ISREG(attrs.st_mode):
                        raise ValueError("Zieldatei ist keine reguläre Datei")
                    sftp.put(str(local), dest, confirm=True)
                print(f"{len(files)} Dateien übertragen; keine Dateien gelöscht.")
        finally:
            client.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Keine Serverantworten, Pfade oder Zugangsdaten in Actions-Protokollen ausgeben.
        print(f"SFTP-Vorgang fehlgeschlagen ({type(exc).__name__}). Prüfe Secrets, Hostschlüssel und Verzeichnisse.", file=sys.stderr)
        sys.exit(1)
