#!/usr/bin/env python3
"""Fetch the locked public sources and replay inputs into an ignored local cache."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent


def checksum(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            value.update(chunk)
    return value.hexdigest()


def safe_member(name):
    path = Path(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe archive member')
    return path


def fetch(base):
    lock = json.loads((HERE/'sources.lock.json').read_text())
    base.mkdir(parents=True, exist_ok=True)
    for source in lock['sources']:
        repo = base/source['name']
        if not repo.exists():
            subprocess.run(['git', 'init', str(repo)], check=True, capture_output=True)
            subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin', source['url']], check=True)
            subprocess.run(['git', '-C', str(repo), 'fetch', '--depth', '1', 'origin', source['revision']], check=True)
            subprocess.run(['git', '-C', str(repo), 'checkout', '--detach', source['revision']], check=True)
        revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
        dirty = subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain'], text=True)
        if revision != source['revision'] or dirty or checksum(repo/'LICENSE') != source['license_sha256']:
            raise ValueError('Existing source differs from lock; use a fresh cache directory: '+source['name'])
        print(json.dumps({'source': source['name'], 'revision': revision}), flush=True)
    downloads = base/'downloads'
    downloads.mkdir(exist_ok=True)
    for item in lock['downloads']:
        path = downloads/item['name']
        if not path.exists():
            partial = path.with_suffix(path.suffix+'.partial')
            with urllib.request.urlopen(item['url'], timeout=60) as response, partial.open('xb') as output:
                total = 0
                while chunk := response.read(1048576):
                    total += len(chunk)
                    if total > item['bytes']:
                        raise ValueError('Download exceeds locked size')
                    output.write(chunk)
            if checksum(partial) != item['sha256']:
                raise ValueError('Download hash mismatch; partial input preserved')
            partial.rename(path)
        if path.stat().st_size != item['bytes'] or checksum(path) != item['sha256']:
            raise ValueError('Cached download differs from lock')
        if path.name.endswith('.zip'):
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    relative = safe_member(member.filename)
                    if member.is_dir() or relative.suffix != '.scap':
                        continue
                    if stat.S_ISLNK(member.external_attr >> 16) or member.file_size > 600000000:
                        raise ValueError('Unexpected replay archive member')
                    target = base/'captures'/relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        with archive.open(member) as stream:
                            expected = hashlib.file_digest(stream, 'sha256').hexdigest()
                        if target.stat().st_size != member.file_size or checksum(target) != expected:
                            raise ValueError('Existing extracted capture differs')
                    else:
                        with archive.open(member) as stream, target.open('xb') as output:
                            shutil.copyfileobj(stream, output)
        else:
            with tarfile.open(path) as archive:
                member = archive.getmember('kyverno')
                if not member.isfile():
                    raise ValueError('Expected a regular Kyverno binary')
                data = archive.extractfile(member).read()
                target = base/'bin/kyverno'
                target.parent.mkdir(exist_ok=True)
                if target.exists() and target.read_bytes() != data:
                    raise ValueError('Existing CLI differs from locked binary')
                target.write_bytes(data)
                target.chmod(0o755)
        print(json.dumps({'download': item['name'], 'bytes': item['bytes'], 'sha256': item['sha256']}), flush=True)
    config = base/'replay.yaml'
    if config.exists() and config.read_bytes() != (HERE/'replay.yaml').read_bytes():
        raise ValueError('Existing replay configuration differs')
    shutil.copyfile(HERE/'replay.yaml', config)
    print(json.dumps({'cache': str(base), 'verified_sources': len(lock['sources']), 'verified_downloads': len(lock['downloads'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    fetch(parser.parse_args().base.resolve())
