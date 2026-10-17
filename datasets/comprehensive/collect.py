#!/usr/bin/env python3
"""Acquire immutable public sources without running downloaded project code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request

HERE = Path(__file__).resolve().parent


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_source(path, source):
    revision = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(path), 'status', '--porcelain'], text=True)
    if revision != source['revision'] or dirty:
        raise ValueError('Source differs from lock: ' + source['name'])
    for item in source['license_files']:
        if sha(path/item['path']) != item['sha256']:
            raise ValueError('Source notice differs: ' + source['name'])


def fetch_object(url, path, item):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        partial=path.with_name(path.name+'.partial')
        with urllib.request.urlopen(url,timeout=60) as response,partial.open('xb') as output:
            size=0
            while chunk:=response.read(1048576):
                size+=len(chunk)
                if size>item['bytes']:raise ValueError('Object exceeds locked size')
                output.write(chunk)
        if partial.stat().st_size!=item['bytes'] or sha(partial)!=item['sha256']:
            raise ValueError('Downloaded object differs from source digest')
        partial.rename(path)
    if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:
        raise ValueError('Cached object differs from lock')


def collect(cache, legacy=None):
    lock = json.loads((HERE/'sources.lock.json').read_text())
    cache.mkdir(parents=True, exist_ok=True)
    for source in lock['sources']:
        path = cache/source['name']
        if not path.exists() and legacy and (legacy/source['name']).exists():
            path=legacy/source['name']
        if not path.exists():
            subprocess.run(['git', 'init', str(path)], check=True, capture_output=True)
            subprocess.run(['git', '-C', str(path), 'remote', 'add', 'origin', source['url']], check=True)
            sparse = source['sparse_paths']
            command = ['git', '-C', str(path), 'fetch', '--depth', '1']
            if sparse:
                subprocess.run(['git', '-C', str(path), 'config', 'remote.origin.promisor', 'true'], check=True)
                subprocess.run(['git', '-C', str(path), 'config', 'remote.origin.partialclonefilter', 'blob:none'], check=True)
                command += ['--filter=blob:none']
                subprocess.run(['git', '-C', str(path), 'sparse-checkout', 'init', '--cone'], check=True)
                subprocess.run(['git', '-C', str(path), 'sparse-checkout', 'set', *sparse], check=True)
            subprocess.run(command + ['origin', source['revision']], check=True, timeout=300)
            subprocess.run(['git', '-C', str(path), 'checkout', '--detach', source['revision']], check=True, timeout=300,
                           env=dict(os.environ,GIT_LFS_SKIP_SMUDGE='1'))
        verify_source(path, source)
        for item in source.get('large_files',[]):
            url=source['url'].removesuffix('.git').replace('https://github.com/','https://media.githubusercontent.com/media/')+'/'+source['revision']+'/'+item['path']
            fetch_object(url,cache/'large-objects'/item['sha256'],item)
        print(json.dumps({'name': source['name'], 'revision': source['revision'], 'verified': True}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--legacy-cache', type=Path)
    args=parser.parse_args()
    collect(args.cache.resolve(),args.legacy_cache.resolve() if args.legacy_cache else None)
