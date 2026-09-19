"""Local-only, non-destructive serial A/B baseline manager (Python 3.10+)."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import uuid


def run(*args):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        # Do not echo environment-expanded Compose or container logs (may contain credentials).
        raise RuntimeError(f'{args[0]} {args[1]} failed (exit {result.returncode}); inspect locally. {result.stderr[-400:]}')
    return result.stdout.strip()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, data):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def escape_compose(value):
    # User-supplied overrides are literal; escape them for Compose interpolation.
    # Compose's own `config` output already preserves its required escaping.
    if isinstance(value, str):
        return value.replace('$', '$$')
    if isinstance(value, list):
        return [escape_compose(v) for v in value]
    if isinstance(value, dict):
        return {k: escape_compose(v) for k, v in value.items()}
    return value


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def linked(path):
    if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
        return True
    return path.exists() and bool(getattr(path.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0))


def within(path, root):
    path, root = Path(path).absolute(), Path(root).absolute()
    if not path.is_relative_to(root):
        raise ValueError('Path escapes managed workspace')
    for part in [path, *path.parents]:
        if linked(part):
            raise ValueError('Symlinks/junctions are unsupported')
        if part == root:
            break
    return path


def hash_tree(root):
    root = Path(root)
    files = {}
    for parent, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            path = Path(parent) / name
            if linked(path):
                raise ValueError('Snapshot contains a symlink/junction')
        for name in names:
            path = Path(parent) / name
            files[path.relative_to(root).as_posix()] = sha(path)
    return files


def verify_tree(root, manifest):
    if hash_tree(root) != manifest:
        raise ValueError('Baseline backup changed; restore refused')


def isolate(config, work, project, options):
    c = copy.deepcopy(config)
    c.pop('name', None)
    for kind in ('volumes', 'networks'):
        for key, item in c.get(kind, {}).items():
            item = item or {}
            if item.get('external') or item.get('driver_opts') or item.get('driver', 'local' if kind == 'volumes' else 'bridge') not in ('local', 'bridge'):
                raise ValueError('External/custom storage or networks unsupported')
            item['name'] = f'{project}-a-{key}' if kind == 'volumes' else f'{project}-{key}'
            item['labels'] = {'ab.baseline.owner': project}
            c[kind][key] = item
    used_ports = set()
    for name in list(c.get('services', {})):
        s = c['services'][name]
        if s.get('profiles'):
            del c['services'][name]  # default profile only, explicit profile support is deferred
            continue
        for forbidden in ('network_mode', 'volumes_from', 'devices', 'secrets', 'configs', 'develop', 'extends', 'env_file'):
            if s.get(forbidden):
                raise ValueError(f'{name}: unsupported {forbidden}')
        if s.get('privileged') or s.get('pid') or s.get('ipc') or s.get('cap_add'):
            raise ValueError('Host/privileged sharing unsupported')
        s.pop('container_name', None)
        s['restart'] = 'no'
        s['labels'] = {'ab.baseline.owner': project}
        s.setdefault('environment', {}).update(escape_compose(options.get('environment', {}).get(name, {})))
        if isinstance(s.get('build'), dict):
            within(s['build']['context'], work)
            if s['build'].get('additional_contexts'):
                raise ValueError('Additional build contexts unsupported')
        for mount in s.get('volumes', []):
            if mount['type'] == 'bind':
                within(mount['source'], work)
            elif mount['type'] == 'volume':
                if not mount.get('source') or mount['source'] not in c.get('volumes', {}):
                    raise ValueError('Anonymous/unmanaged volumes unsupported')
            else:
                raise ValueError('Unsupported mount type')
        for port in s.get('ports', []):
            key = f'{name}:{port["target"]}'
            published = int(options.get('ports', {}).get(key, port.get('published', 0)))
            if not 1024 <= published <= 65535 or (published, port.get('protocol', 'tcp')) in used_ports:
                raise ValueError('Invalid or duplicate host port')
            used_ports.add((published, port.get('protocol', 'tcp')))
            port.update(published=str(published), host_ip='127.0.0.1')
    used_volumes = {m['source'] for s in c.get('services', {}).values() for m in s.get('volumes', []) if m['type'] == 'volume'}
    c['volumes'] = {k: v for k, v in c.get('volumes', {}).items() if k in used_volumes}
    return c


class Manager:
    def __init__(self, config_path):
        self.config_path = Path(config_path).resolve()
        self.config = read(self.config_path)
        self.root = Path(self.config['stateDir'])
        if not self.root.is_absolute() or not re.fullmatch(r'[a-z][a-z0-9-]{2,35}', self.config['id']):
            raise ValueError('Use an absolute stateDir and lowercase project id')
        self.root = self.root.absolute()
        self.source = Path(self.config['source']).resolve()
        if self.root.is_relative_to(self.source) or self.source.is_relative_to(self.root):
            raise ValueError('State directory and source must be disjoint')
        if self.config_path.is_relative_to(self.root):
            raise ValueError('Keep configuration outside stateDir')
        within(self.root, self.root.anchor)
        self.work = self.root / 'work'
        self.statefile = self.root / 'state.json'
        self.runtime = self.root / 'runtime.json'
        self.project = 'ab-' + self.config['id'] + '-' + hashlib.sha256(str(self.root).lower().encode()).hexdigest()[:8]

    def git(self, *args):
        return run('git', '-C', self.work, *args)

    def compose(self, *args):
        return run('docker', 'compose', '--project-directory', self.work, '-p', self.project, '-f', self.runtime, *args)

    def save(self):
        write(self.statefile, self.state)

    def owned(self):
        ids = run('docker', 'ps', '-aq', '--filter', f'label=com.docker.compose.project={self.project}').split()
        existing = set(run('docker', 'volume', 'ls', '-q').split())
        for volume in self.state['volumes'].values():
            if volume in existing:
                info = json.loads(run('docker', 'volume', 'inspect', volume))[0]
                if (info.get('Labels') or {}).get('ab.baseline.owner') != self.project:
                    raise ValueError('Foreign volume name collision')
                users = set(run('docker', 'ps', '-q', '--no-trunc', '--filter', f'volume={volume}').split())
                own_full = {c['Id'] for c in json.loads(run('docker', 'inspect', *ids))} if ids else set()
                if users - own_full:
                    raise ValueError('Another running container uses this volume')
        if ids:
            containers = json.loads(run('docker', 'inspect', *ids))
            allowed = set(self.state['volumes'].values())
            for container in containers:
                if container['Config']['Labels'].get('ab.baseline.owner') != self.project:
                    raise ValueError('Foreign container detected')
                for mount in container['Mounts']:
                    if mount['Type'] == 'volume' and mount['Name'] not in allowed:
                        raise ValueError('Unmanaged volume detected')
                    if mount['Type'] == 'bind':
                        # Docker Desktop may normalize drive letters to /run/desktop/mnt/host/.
                        permitted = [m['source'] for s in read(self.runtime)['services'].values() for m in s.get('volumes', []) if m['type'] == 'bind']
                        def norm(p):
                            p = p.replace('\\', '/').lower().replace('/run/desktop/mnt/host/', '')
                            return p.replace(':/', '/')
                        if norm(mount['Source']) not in [norm(p) for p in permitted]:
                            raise ValueError('Unmanaged bind mount detected')
            return containers
        return []

    def init(self):
        if self.statefile.exists() or any(p.name != '.lock' for p in self.root.iterdir()):
            raise ValueError('init requires an empty stateDir')
        commit = run('git', '-C', self.source, 'rev-parse', self.config['ref'] + '^{commit}')
        run('git', 'clone', '--no-hardlinks', '--no-checkout', self.source, self.work)
        self.git('checkout', '--detach', commit)
        if self.config.get('remote'):
            self.git('remote', 'set-url', 'origin', self.config['remote'])
        composefile = within(self.work / self.config['compose'], self.work)
        rendered = json.loads(run('docker', 'compose', '--project-directory', self.work, '-f', composefile, 'config', '--format', 'json'))
        config = isolate(rendered, self.work, self.project, self.config)
        write(self.runtime, config)
        self.state = {'phase': 'prepared', 'commit': commit, 'project': self.project,
                      'volumes': {k: v['name'] for k, v in config.get('volumes', {}).items()},
                      'configHash': sha(self.config_path), 'runtimeHash': sha(self.runtime)}
        self.save()

    def start(self):
        if self.state['phase'] not in ('prepared', 'frozen', 'a-ready', 'a-running', 'b-ready', 'b-running'):
            raise ValueError('Cannot start in this phase')
        self.owned()
        if self.state['phase'] == 'frozen':
            verify_tree(self.work, self.state['workHashes'])
            self.git('switch', '-c', f'eval/{self.config["id"]}/a')
            self.state['phase'] = 'a-ready'
            self.save()
        self.compose('up', '-d', '--wait', '--wait-timeout', '900', *(['--no-build', '--pull', 'never'] if self.state['phase'] != 'prepared' else ['--build']))
        if self.state['phase'] == 'a-ready':
            self.state['phase'] = 'a-running'
        elif self.state['phase'] == 'b-ready':
            self.state['phase'] = 'b-running'
        self.save()

    def freeze(self, prompt):
        if self.state['phase'] != 'prepared' or self.git('status', '--porcelain'):
            raise ValueError('freeze requires prepared phase and clean tracked/untracked files')
        if self.git('rev-parse', 'HEAD') != self.state['commit']:
            raise ValueError('Source commit changed; re-init a new case')
        containers = self.owned()
        runtime = read(self.runtime)
        by_service = {c['Config']['Labels']['com.docker.compose.service']: c for c in containers}
        if set(by_service) != set(runtime['services']):
            raise ValueError('Start all configured services before freeze')
        for name, service in runtime['services'].items():
            c = by_service[name]
            if not c['State']['Running'] or c['State'].get('Health', {}).get('Status', 'healthy') != 'healthy':
                raise ValueError('Services must be running/healthy before freeze')
            service.pop('build', None)
            service['image'] = c['Image']
        self.compose('stop', '--timeout', '60')
        if any(c['State']['Running'] for c in self.owned()):
            raise ValueError('Containers not stopped')
        snapshot = self.root / 'snapshot'
        if snapshot.exists():
            raise ValueError('Incomplete snapshot exists; inspect or use a new stateDir')
        snapshot.mkdir()
        hash_tree(self.work)
        shutil.copytree(self.work, snapshot / 'work')
        hashes = hash_tree(snapshot / 'work')
        verify_tree(self.work, hashes)
        run('docker', 'pull', 'alpine:3.21')
        helper = json.loads(run('docker', 'image', 'inspect', 'alpine:3.21'))[0]['Id']
        archives = {}
        for key, volume in self.state['volumes'].items():
            if not re.fullmatch(r'[a-zA-Z0-9_.-]+', key):
                raise ValueError('Unsupported volume key')
            info = json.loads(run('docker', 'volume', 'inspect', volume))[0]
            if (info.get('Labels') or {}).get('ab.baseline.owner') != self.project:
                raise ValueError('Volume ownership mismatch')
            archive = key + '.tar'
            run('docker', 'run', '--rm', '--network', 'none', '--mount', f'type=volume,src={volume},dst=/data,readonly', '--mount', f'type=bind,src={snapshot},dst=/backup', helper, 'tar', '-cpf', '/backup/' + archive, '-C', '/data', '.')
            archives[key] = sha(snapshot / archive)
        shutil.copyfile(prompt, snapshot / 'prompt.txt')
        write(snapshot / 'runtime.json', runtime)
        self.state.update(phase='frozen', workHashes=hashes, archives=archives, helper=helper,
                          snapshotRuntimeHash=sha(snapshot / 'runtime.json'), promptHash=sha(snapshot / 'prompt.txt'))
        write(self.runtime, runtime)
        self.state['runtimeHash'] = sha(self.runtime)
        self.save()

    def finish_a(self, args):
        if self.state['phase'] != 'a-running' or self.git('status', '--porcelain'):
            raise ValueError('A must be running and all source changes committed (ignored runtime files allowed)')
        head = self.git('rev-parse', 'HEAD')
        self.git('merge-base', '--is-ancestor', self.state['commit'], head)
        branch = self.git('symbolic-ref', '--short', 'HEAD')
        expected_remote = self.config.get('remote', str(self.source))
        if self.git('remote', 'get-url', 'origin') != expected_remote or branch != f'eval/{self.config["id"]}/a':
            raise ValueError('A branch or remote differs from configured destination')
        remote = self.git('ls-remote', 'origin', f'refs/heads/{branch}').split()
        if not remote or remote[0] != head:
            raise ValueError('Push current A branch to origin before saving A')
        if not args.session or not args.trace or not args.recording:
            raise ValueError('Provide --session, --trace and --recording')
        for source in (args.trace, args.recording):
            path = Path(source).resolve()
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError('Evidence file missing or empty')
        evidence = self.root / 'evidence-a'
        evidence.mkdir(exist_ok=False)
        for name, source in [('trace', args.trace), ('recording', args.recording)]:
            path = Path(source).resolve()
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError('Evidence file missing or empty')
            shutil.copyfile(path, evidence / name)
        receipt = {'sha': head, 'branch': branch, 'session': args.session, 'promptHash': self.state['promptHash'], 'hashes': hash_tree(evidence)}
        write(evidence / 'receipt.json', receipt)
        self.state.update(phase='a-saved', a=receipt)
        self.save()

    def restore_b(self):
        if self.state['phase'] != 'a-saved':
            raise ValueError('Save/push A and evidence first')
        if self.git('rev-parse', 'HEAD') != self.state['a']['sha'] or self.git('status', '--porcelain'):
            raise ValueError('A changed after saving')
        if self.git('remote', 'get-url', 'origin') != self.config.get('remote', str(self.source)):
            raise ValueError('Remote changed after saving')
        remote = self.git('ls-remote', 'origin', 'refs/heads/' + self.state['a']['branch']).split()
        if not remote or remote[0] != self.state['a']['sha']:
            raise ValueError('Remote A no longer matches receipt')
        for name, digest in self.state['a']['hashes'].items():
            if sha(self.root / 'evidence-a' / name) != digest:
                raise ValueError('A evidence changed')
        snapshot = self.root / 'snapshot'
        verify_tree(snapshot / 'work', self.state['workHashes'])
        if sha(snapshot / 'runtime.json') != self.state['snapshotRuntimeHash'] or sha(snapshot / 'prompt.txt') != self.state['promptHash']:
            raise ValueError('Baseline configuration or prompt changed')
        for key, digest in self.state['archives'].items():
            if sha(snapshot / (key + '.tar')) != digest:
                raise ValueError('Volume backup changed')
        self.owned()
        self.compose('down', '--timeout', '60')  # never --volumes
        self.state['phase'] = 'restoring-b'
        self.save()  # interrupted recovery fails closed; A and snapshot remain intact
        self.work.rename(self.root / 'preserved-a-work')
        shutil.copytree(snapshot / 'work', self.work)
        verify_tree(self.work, self.state['workHashes'])
        runtime = read(snapshot / 'runtime.json')
        new_volumes = {}
        for key in self.state['archives']:
            name = f'{self.project}-b-{uuid.uuid4().hex[:10]}-{key}'
            run('docker', 'volume', 'create', '--label', f'ab.baseline.owner={self.project}', name)
            run('docker', 'run', '--rm', '--network', 'none', '--mount', f'type=volume,src={name},dst=/data', '--mount', f'type=bind,src={snapshot},dst=/backup,readonly', self.state['helper'], 'tar', '-xpf', '/backup/' + key + '.tar', '-C', '/data')
            runtime['volumes'][key]['name'] = name
            new_volumes[key] = name
        write(self.runtime, runtime)
        self.git('switch', '-c', f'eval/{self.config["id"]}/b')
        if self.git('rev-parse', 'HEAD') != self.state['commit']:
            raise ValueError('Restored HEAD mismatch')
        self.state.update(phase='b-ready', aVolumes=self.state['volumes'], volumes=new_volumes, runtimeHash=sha(self.runtime))
        self.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'start', 'freeze', 'finish-a', 'restore-b', 'stop', 'status'])
    parser.add_argument('--config', required=True)
    parser.add_argument('--prompt')
    parser.add_argument('--session')
    parser.add_argument('--trace')
    parser.add_argument('--recording')
    args = parser.parse_args()
    m = Manager(args.config)
    m.root.mkdir(parents=True, exist_ok=True)
    lock = m.root / '.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode())
        if args.action == 'init':
            m.init()
        else:
            m.state = read(m.statefile)
            if m.state['project'] != m.project or sha(m.config_path) != m.state['configHash'] or sha(m.runtime) != m.state['runtimeHash']:
                raise ValueError('Configuration changed; use a new case/stateDir')
            if args.action == 'start': m.start()
            elif args.action == 'freeze':
                if not args.prompt: raise ValueError('--prompt required')
                m.freeze(Path(args.prompt).resolve())
            elif args.action == 'finish-a': m.finish_a(args)
            elif args.action == 'restore-b': m.restore_b()
            elif args.action == 'stop':
                m.owned()
                m.compose('stop', '--timeout', '60')
            elif args.action == 'status': print(json.dumps({'phase': m.state['phase'], 'commit': m.state['commit'], 'project': m.project, 'work': str(m.work)}, ensure_ascii=False))
        print('OK:', args.action)
    finally:
        os.close(fd)
        lock.unlink()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
