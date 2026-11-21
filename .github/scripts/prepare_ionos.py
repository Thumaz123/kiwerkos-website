"""Create an isolated rollback copy and test directory over SFTP, without deleting."""
import hashlib
import os
import posixpath
import stat
import sys
import tempfile

import paramiko


def req(name):
    value = os.environ.get(name, '')
    if not value:
        raise ValueError('Missing configuration')
    return value


def main():
    client = paramiko.SSHClient()
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8') as host_file:
        host_file.write(req('SFTP_KNOWN_HOSTS') + '\n')
        host_file.flush()
        client.load_host_keys(host_file.name)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(hostname=req('SFTP_HOST'), port=int(os.getenv('SFTP_PORT') or 22),
                       username=req('SFTP_USER'), password=req('SFTP_PASSWORD'),
                       allow_agent=False, look_for_keys=False, timeout=20)
        try:
            with client.open_sftp() as sftp:
                source = sftp.normalize(req('SFTP_WEBROOT'))
                if source != '/kiwerk-os/deploy':
                    raise ValueError('Unexpected live directory')
                backup = '/kiwerkos-rollback-' + req('GITHUB_RUN_ID')
                test = '/kiwerkos-test-' + req('GITHUB_RUN_ID')
                if not stat.S_ISDIR(sftp.stat(source).st_mode):
                    raise ValueError('Missing live directory')
                sftp.mkdir(backup)
                sftp.mkdir(test)
                count = 0

                def copy_tree(src, dst):
                    nonlocal count
                    for entry in sftp.listdir_attr(src):
                        if entry.filename in ('.', '..'):
                            continue
                        origin = posixpath.join(src, entry.filename)
                        target = posixpath.join(dst, entry.filename)
                        if stat.S_ISDIR(entry.st_mode):
                            sftp.mkdir(target)
                            copy_tree(origin, target)
                        elif stat.S_ISREG(entry.st_mode):
                            before = hashlib.sha256()
                            with sftp.open(origin, 'rb') as reader, sftp.open(target, 'wb') as writer:
                                while True:
                                    chunk = reader.read(1024 * 1024)
                                    if not chunk:
                                        break
                                    before.update(chunk)
                                    writer.write(chunk)
                            after = hashlib.sha256()
                            with sftp.open(target, 'rb') as reader:
                                while True:
                                    chunk = reader.read(1024 * 1024)
                                    if not chunk:
                                        break
                                    after.update(chunk)
                            if before.digest() != after.digest():
                                raise ValueError('Backup verification failed')
                            count += 1
                        else:
                            raise ValueError('Unsupported server entry')

                copy_tree(source, backup)
                if not count:
                    raise ValueError('Empty backup')
                print(f'Sicherung erstellt und mit SHA-256 geprüft: {count} Dateien.')
                print('Testordner bereit: ' + test)
                print('Sicherungsordner: ' + backup)
        finally:
            client.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Sicherung fehlgeschlagen ({type(exc).__name__}); kein Live-Upload erfolgt.', file=sys.stderr)
        sys.exit(1)
