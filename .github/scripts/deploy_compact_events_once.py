"""One-time targeted release of compact homepage schedule with SFTP backup."""
import hashlib
import os
import posixpath
import stat
import sys
import tempfile
from pathlib import Path

import paramiko

FILES = ("assets/css/events.css", "assets/js/events.js", "index.html")
EXPECTED_WEBROOT = "/kiwerk-os/deploy"

def required(name):
    value = os.environ.get(name, "")
    if not value:
        raise ValueError("Missing setting " + name)
    return value

def digest(data):
    return hashlib.sha256(data).digest()

def main():
    # Release only the reviewed compact schedule, preserving the cinematic homepage.
    home = Path("landingpage/index.html").read_text(encoding="utf-8")
    js = Path("landingpage/assets/js/events.js").read_text(encoding="utf-8")
    css = Path("landingpage/assets/css/events.css").read_text(encoding="utf-8")
    if not all(marker in home for marker in (
        'event-list__upcoming', 'event-list__more',
        'home.js?v=20261123-progressive',
        'events.js?v=20261123-compact', 'events.css?v=20261123-compact'
    )) or 'entries.slice(0,3)' not in js or '.event-list__more' not in css:
        raise ValueError("Compact schedule or previous cinematic release is missing")
    if required("SFTP_WEBROOT") != EXPECTED_WEBROOT:
        raise ValueError("Unexpected webroot; refusing release")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as hosts:
        hosts.write(required("SFTP_KNOWN_HOSTS") + "\n")
        hosts.flush()
        ssh = paramiko.SSHClient()
        ssh.load_host_keys(hosts.name)
        ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
        ssh.connect(hostname=required("SFTP_HOST"),
                    port=int(os.environ.get("SFTP_PORT") or "22"),
                    username=required("SFTP_USER"), password=required("SFTP_PASSWORD"),
                    look_for_keys=False, allow_agent=False, timeout=20)
        try:
            with ssh.open_sftp() as sftp:
                webroot = sftp.normalize(EXPECTED_WEBROOT)
                if webroot != EXPECTED_WEBROOT or not stat.S_ISDIR(sftp.stat(webroot).st_mode):
                    raise ValueError("Unexpected normalized live path")
                updates = []
                for name in FILES:
                    local = Path("landingpage") / name
                    if not local.is_file() or local.is_symlink():
                        raise ValueError("Missing or invalid generated file: " + name)
                    remote = posixpath.join(webroot, name)
                    if not stat.S_ISREG(sftp.lstat(remote).st_mode):
                        raise ValueError("Remote file is not regular: " + name)
                    data = local.read_bytes()
                    with sftp.open(remote, "rb") as f:
                        original = f.read()
                    if digest(data) != digest(original):
                        updates.append((remote, data, original))
                if not updates:
                    print("Compact homepage event files already match; no upload needed.")
                    return
                backup = "/kiwerk-compact-events-backup-" + required("GITHUB_RUN_ID")
                sftp.mkdir(backup)
                for remote, data, original in updates:
                    name = posixpath.relpath(remote, webroot)
                    # Flatten private backup filenames: nested asset directories
                    # need no additional SFTP mkdir permissions.
                    dest = posixpath.join(backup, name.replace("/", "__"))
                    with sftp.open(dest, "wb") as f:
                        f.write(original)
                    with sftp.open(dest, "rb") as f:
                        if digest(f.read()) != digest(original):
                            raise ValueError("Backup verification failed")
                changed = []
                try:
                    # index.html last; visitors never see new homepage before meeting page is uploaded.
                    for remote, data, _ in sorted(updates, key=lambda r: r[0].endswith("/index.html") and r[0] == webroot + "/index.html"):
                        name = posixpath.relpath(remote, webroot)
                        tmp = remote + ".kiwerk-" + required("GITHUB_RUN_ID") + ".tmp"
                        with sftp.open(tmp, "wb") as f:
                            f.write(data)
                        with sftp.open(tmp, "rb") as f:
                            if digest(f.read()) != digest(data):
                                raise ValueError("Upload verification failed")
                        # Paramiko POSIX rename can atomically replace an existing file on IONOS.
                        sftp.posix_rename(tmp, remote)
                        changed.append((remote, name))
                        with sftp.open(remote, "rb") as f:
                            if digest(f.read()) != digest(data):
                                raise ValueError("Live verification failed")
                except Exception:
                    for remote, name in changed:
                        back = posixpath.join(backup, name.replace("/", "__"))
                        with sftp.open(back, "rb") as f:
                            original = f.read()
                        with sftp.open(remote, "wb") as f:
                            f.write(original)
                    raise
                print("Published and verified", len(changed), "compact event files; original backups stored on server.")
        finally:
            ssh.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("KIWERK compact events deployment failed: " + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
