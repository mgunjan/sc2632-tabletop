#!/usr/bin/env python3
"""Fetch the locked offline CLIs; never extract arbitrary archive paths."""
import argparse
import json
from pathlib import Path
import tarfile

from collect import HERE, fetch_object, sha


def fetch(cache,legacy):
    lock=json.loads((HERE/'runtime.lock.json').read_text())
    for item in lock['artifacts']:
        archive=cache/'downloads'/item['name']
        fetch_object(item['url'],archive,item)
        root=legacy if item['destination']=='legacy' else cache
        target=root/'bin'/item['executable'];target.parent.mkdir(parents=True,exist_ok=True)
        with tarfile.open(archive) as source:
            matches=[m for m in source.getmembers() if m.isfile() and Path(m.name).name==item['executable']]
            if len(matches)!=1:raise ValueError('Expected one regular CLI executable')
            data=source.extractfile(matches[0]).read()
        if target.exists() and target.read_bytes()!=data:raise ValueError('Existing CLI differs')
        target.write_bytes(data);target.chmod(0o755)
        if sha(target)!=item['binary_sha256']:raise ValueError('CLI checksum differs')
        print(json.dumps({'executable':item['executable'],'sha256':sha(target)}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,required=True);p.add_argument('--legacy-cache',type=Path,required=True)
    a=p.parse_args();fetch(a.cache.resolve(),a.legacy_cache.resolve())
