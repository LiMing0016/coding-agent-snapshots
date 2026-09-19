"""Opt-in real Docker test. Retains its own test state for inspection; no deletions."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import baseline as b


def main():
    root = Path(tempfile.mkdtemp(prefix='ab-integration-'))
    source = root / 'source'
    source.mkdir()
    remote = root / 'remote.git'
    b.run('git', 'init', '--bare', remote)
    b.run('git', 'init', '-b', 'main', source)
    b.run('git', '-C', source, 'config', 'user.name', 'Baseline Test')
    b.run('git', '-C', source, 'config', 'user.email', 'test@example.invalid')
    b.run('docker', 'pull', 'alpine:3.21')
    image = json.loads(b.run('docker', 'image', 'inspect', 'alpine:3.21'))[0]['Id']
    b.write(source / 'compose.json', {'services': {'app': {'image': image, 'command': ['sh', '-c', 'trap "exit 0" TERM; while :; do sleep 1 & wait $$!; done'],
        'environment': {'LITERAL': '$${MUST_STAY_LITERAL}'},
        'volumes': [{'type': 'volume', 'source': 'data', 'target': '/data'}]}}, 'volumes': {'data': {}}})
    (source / '.gitignore').write_text('runtime.txt\n', encoding='utf-8')
    (source / 'code.txt').write_text('baseline', encoding='utf-8')
    b.run('git', '-C', source, 'add', '.')
    b.run('git', '-C', source, 'commit', '-m', 'test initial')
    ref = b.run('git', '-C', source, 'rev-parse', 'HEAD')
    config = root / 'config.json'
    b.write(config, {'id': 'integration', 'source': str(source), 'ref': ref, 'compose': 'compose.json', 'stateDir': str(root / 'state'), 'remote': str(remote)})
    script = Path(__file__).with_name('baseline.py')
    def cli(action, *args, fail=False, cfg=config):
        result = subprocess.run([sys.executable, str(script), action, '--config', str(cfg), *map(str, args)], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if (result.returncode != 0) != fail:
            raise AssertionError(result.stdout + result.stderr)
    managers = []
    try:
        cli('init')
        m = b.Manager(config)
        m.state = b.read(m.statefile)
        managers.append(m)
        cli('start')
        assert m.compose('exec', '-T', 'app', 'printenv', 'LITERAL') == '${MUST_STAY_LITERAL}'
        m.compose('exec', '-T', 'app', 'sh', '-c', 'echo seed > /data/value')
        (m.work / 'runtime.txt').write_text('baseline-cache')
        prompt = root / 'prompt.txt'
        prompt.write_text('fixture prompt')
        cli('freeze', '--prompt', prompt)
        cli('restore-b', fail=True)  # no A receipt
        cli('start')
        m.compose('exec', '-T', 'app', 'sh', '-c', 'echo A > /data/value')
        (m.work / 'runtime.txt').write_text('A-cache')
        (m.work / 'code.txt').write_text('A-code')
        b.run('git', '-C', m.work, 'config', 'user.name', 'Baseline Test')
        b.run('git', '-C', m.work, 'config', 'user.email', 'test@example.invalid')
        b.run('git', '-C', m.work, 'add', 'code.txt')
        b.run('git', '-C', m.work, 'commit', '-m', 'A result')
        trace, recording = root / 'trace.jsonl', root / 'recording.txt'
        trace.write_text('{"test_fixture":true}\n')
        recording.write_text('TEST FIXTURE, not an actual recording')
        cli('finish-a', '--session', 'test-session', '--trace', trace, '--recording', recording, fail=True)
        b.run('git', '-C', m.work, 'push', 'origin', 'HEAD')
        cli('finish-a', '--session', 'test-session', '--trace', trace, '--recording', recording)
        cli('restore-b')
        assert (m.work / 'code.txt').read_text() == 'baseline'
        assert (m.work / 'runtime.txt').read_text() == 'baseline-cache'
        assert (m.root / 'preserved-a-work' / 'code.txt').read_text() == 'A-code'
        assert b.run('git', '-C', m.work, 'rev-parse', 'HEAD') == ref
        cli('start')
        assert m.compose('exec', '-T', 'app', 'cat', '/data/value') == 'seed'
        state = b.read(m.statefile)
        old = state['aVolumes']['data']
        assert b.run('docker', 'run', '--rm', '--network', 'none', '--mount', f'type=volume,src={old},dst=/data,readonly', image, 'cat', '/data/value') == 'A'
        second = root / 'second.json'
        other = b.read(config)
        other.update(id='second-case', stateDir=str(root / 'second-state'))
        b.write(second, other)
        cli('init', cfg=second)
        other_m = b.Manager(second)
        other_m.state = b.read(other_m.statefile)
        managers.append(other_m)
        cli('start', cfg=second)
        assert other_m.project != m.project
        assert other_m.state['volumes']['data'] not in state['volumes'].values()
        other_m.compose('exec', '-T', 'app', 'sh', '-c', 'echo other > /data/value')
        assert m.compose('exec', '-T', 'app', 'cat', '/data/value') == 'seed'
        print('PASS: full A/B restore, push/evidence gates, ignored files, preserved A volume, simultaneous isolated projects')
        print('Test artifacts:', root)
    finally:
        for manager in managers:
            try:
                manager.state = b.read(manager.statefile)
                manager.owned()
                manager.compose('stop', '--timeout', '10')
            except Exception:
                pass


if __name__ == '__main__':
    main()
