"""Native image loading contracts; command stand-ins never contact Docker or a cluster."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ImageImportTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.log = self.folder / 'commands.jsonl'
        tags = set()
        for fixture in (ROOT / 'scenarios').glob('*/fixtures/*.yaml'):
            for line in fixture.read_text().splitlines():
                if 'image:' in line:
                    tags.add(line.split()[-1])
        tags.update(['busybox:1.36', 'registry.trustfall.internal/platform/lab-target:1',
                     'registry.trustfall.internal/platform/debug:1'])
        def canonical(tag):
            first = tag.split('/')[0]
            if '/' not in tag: return 'docker.io/library/' + tag
            return tag if '.' in first or ':' in first or first == 'localhost' else 'docker.io/' + tag
        script = f'#!{sys.executable}\n' + '''import json,os,sys
from pathlib import Path
name=Path(sys.argv[0]).name; args=sys.argv[1:]
with Path(os.environ['IMAGE_TEST_LOG']).open('a') as f: f.write(json.dumps([name,*args])+'\\n')
if name=='kubectl':
 if 'current-context' in args: print(os.environ.get('IMAGE_TEST_CONTEXT','k3d-sc2632-test'))
 sys.exit(0)
if name=='docker':
 if args[:2]==['ps','-a']:
  print('k3d-sc2632-test-server-0 server running')
  print('k3d-sc2632-test-agent-0 agent running')
 elif args[:1]==['version']: print('linux/arm64')
 elif args[:2]==['image','inspect']: print('linux/arm64 null')
 elif args[:3]==['image','save','--help']: print('--platform')
 elif args[:1]==['exec']:
  tags=json.loads(os.environ['IMAGE_TEST_TAGS'])
  if args[1].endswith('agent-0') and os.environ.get('IMAGE_TEST_MISSING')=='1':
   tags.remove('docker.io/library/busybox:1.36')
  print('\\n'.join(tags))
 sys.exit(0)
sys.exit(0)
'''
        for name in ['docker', 'kubectl', 'k3d']:
            p = self.folder / name
            p.write_text(script); p.chmod(0o700)
        self.env = {**os.environ, 'PATH': str(self.folder) + os.pathsep + os.environ.get('PATH', ''),
                    'IMAGE_TEST_LOG': str(self.log), 'IMAGE_TEST_TAGS': json.dumps(sorted(set(map(canonical, tags)))),
                    'CLUSTER': 'sc2632-test', 'RUNTIME': 'k3d', 'BASE': 'busybox:1.36',
                    'IMAGE_PLATFORM': 'linux/arm64', 'TRUSTFALL_LAB_OK': ''}

    def run_build(self, **env):
        r = subprocess.run(['/bin/bash', str(ROOT / 'lab/images/build.sh')], cwd=ROOT,
                           env={**self.env, **env}, capture_output=True, text=True, timeout=15)
        commands = [json.loads(x) for x in self.log.read_text().splitlines()]
        return r, commands

    def test_successful_import_exit_is_not_proof_of_every_node(self):
        r, commands = self.run_build(IMAGE_TEST_MISSING='1')
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn('not fully downloaded and unpacked on k3d-sc2632-test-agent-0', r.stderr)
        self.assertTrue(any(c[:3] == ['k3d', 'image', 'import'] for c in commands))
        self.assertNotIn('loaded and verified:', r.stdout)

    def test_cached_base_works_without_pull_and_is_never_overwritten(self):
        r, commands = self.run_build()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(any(c[:2] == ['docker', 'pull'] for c in commands))
        busybox_aliases = {'busybox:1.36', 'docker.io/library/busybox:1.36', 'index.docker.io/library/busybox:1.36'}
        self.assertFalse(any(c[:2] == ['docker', 'tag'] and c[-1] in busybox_aliases for c in commands))
        self.assertEqual(sum(c[:2] == ['docker', 'exec'] for c in commands), 2)

    def test_native_platform_archive_is_used_for_direct_import(self):
        r, commands = self.run_build()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        save = next(c for c in commands if c[:3] == ['docker', 'image', 'save'] and '--output' in c)
        self.assertEqual(save[save.index('--platform')+1], 'linux/arm64')
        imported = next(c for c in commands if c[:3] == ['k3d', 'image', 'import'])
        self.assertEqual(imported[imported.index('--mode')+1], 'direct')
        self.assertEqual(imported[-1], save[save.index('--output')+1])
        self.assertFalse(Path(imported[-1]).exists(), 'The temporary image archive must be removed')

    def test_wrong_context_refuses_before_docker_writes(self):
        r, commands = self.run_build(IMAGE_TEST_CONTEXT='existing-production-context')
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertFalse(any(c[0] in ['docker', 'k3d'] for c in commands))


if __name__ == '__main__': unittest.main()
