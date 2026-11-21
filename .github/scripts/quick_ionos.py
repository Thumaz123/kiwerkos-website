"""One-time release of the approved KIWERK changes, preserving previous files."""
import hashlib
import os
import posixpath
import stat
import sys
import tempfile
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path.cwd()))
import build_deploy

FILES = (
    'assets/css/site.css', 'community/index.html', 'impressum/index.html',
    'praxis/index.html', 'rueckblicke/2026-09-02/index.html',
    'rueckblicke/2026-10-07/index.html', 'rueckblicke/index.html',
    'treffen/index.html', 'ueber-kiwerk/index.html',
)


def need(name):
    value = os.environ.get(name, '')
    if not value:
        raise ValueError('Missing required environment setting: ' + name)
    return value


def digest(data):
    return hashlib.sha256(data).digest()


def main():
    with tempfile.TemporaryDirectory() as temp:
        build_deploy.ZIEL = os.path.join(temp, 'site')
        build_deploy.bauen()
        root = Path(build_deploy.ZIEL)
        files = {name: (root / name).read_bytes() for name in FILES}
        ssh = paramiko.SSHClient()
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8') as hosts:
            hosts.write(need('SFTP_KNOWN_HOSTS') + '\n')
            hosts.flush()
            ssh.load_host_keys(hosts.name)
            ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
            ssh.connect(hostname=need('SFTP_HOST'), port=int(os.environ.get('SFTP_PORT') or '22'),
                        username=need('SFTP_USER'), password=need('SFTP_PASSWORD'),
                        look_for_keys=False, allow_agent=False, timeout=20)
            try:
                with ssh.open_sftp() as sftp:
                    webroot = sftp.normalize(need('SFTP_WEBROOT'))
                    if webroot != '/kiwerk-os/deploy':
                        raise ValueError('Unexpected webroot')
                    backup = '/kiwerkos-quick-backup-' + need('GITHUB_RUN_ID')
                    sftp.mkdir(backup)
                    originals = {}
                    for name in FILES:
                        parts = name.split('/')
                        current = webroot
                        for part in parts[:-1]:
                            current = posixpath.join(current, part)
                            if not stat.S_ISDIR(sftp.lstat(current).st_mode):
                                raise ValueError('Unexpected live directory')
                        remote = posixpath.join(webroot, name)
                        if not stat.S_ISREG(sftp.lstat(remote).st_mode):
                            raise ValueError('Live file is not regular')
                        with sftp.open(remote, 'rb') as f:
                            originals[name] = f.read()
                        current = backup
                        for part in parts[:-1]:
                            current = posixpath.join(current, part)
                            try:
                                sftp.mkdir(current)
                            except OSError:
                                if not stat.S_ISDIR(sftp.lstat(current).st_mode):
                                    raise
                        copy = posixpath.join(backup, name)
                        with sftp.open(copy, 'wb') as f:
                            f.write(originals[name])
                        with sftp.open(copy, 'rb') as f:
                            if digest(f.read()) != digest(originals[name]):
                                raise ValueError('Backup verification failed')
                    print('Nine existing files backed up and verified.', flush=True)
                    written = []
                    try:
                        for name, data in files.items():
                            written.append(name)
                            with sftp.open(posixpath.join(webroot, name), 'wb') as f:
                                f.write(data)
                            with sftp.open(posixpath.join(webroot, name), 'rb') as f:
                                if digest(f.read()) != digest(data):
                                    raise ValueError('Upload verification failed')
                        print('Nine changed files uploaded and verified. No files deleted.', flush=True)
                    except Exception:
                        for name in written:
                            with sftp.open(posixpath.join(webroot, name), 'wb') as f:
                                f.write(originals[name])
                        print('Upload failed; attempted to restore changed files.', flush=True)
                        raise
            finally:
                ssh.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Release failed: ' + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
