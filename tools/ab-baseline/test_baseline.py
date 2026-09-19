import unittest
from pathlib import Path
import tempfile
import baseline


class IsolationTests(unittest.TestCase):
    def test_compose_literal_variables_preserved(self):
        self.assertEqual(baseline.escape_compose({'command': ['echo ${VALUE} $!'], 'n': 3}),
                         {'command': ['echo $${VALUE} $$!'], 'n': 3})

    def test_external_volume_rejected(self):
        with self.assertRaises(ValueError):
            baseline.isolate({'services': {}, 'volumes': {'db': {'external': True}}}, Path.cwd(), 'ab-test', {})

    def test_foreign_bind_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'work'
            root.mkdir()
            with self.assertRaises(ValueError):
                baseline.isolate({'services': {'app': {'volumes': [{'type': 'bind', 'source': temp, 'target': '/x'}]}}}, root, 'ab-test', {})

    def test_volume_and_ports_isolated(self):
        config = {'services': {'app': {'image': 'test', 'ports': [{'target': 80, 'published': '80'}],
                  'volumes': [{'type': 'volume', 'source': 'db', 'target': '/data'}]}}, 'volumes': {'db': {}}, 'networks': {'default': {}}}
        result = baseline.isolate(config, Path.cwd(), 'ab-one', {'ports': {'app:80': 18080}})
        self.assertEqual(result['volumes']['db']['name'], 'ab-one-a-db')
        self.assertEqual(result['services']['app']['ports'][0]['published'], '18080')
        self.assertEqual(result['services']['app']['ports'][0]['host_ip'], '127.0.0.1')

    def test_snapshot_tampering_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'file').write_text('original')
            manifest = baseline.hash_tree(root)
            (root / 'file').write_text('changed')
            with self.assertRaises(ValueError):
                baseline.verify_tree(root, manifest)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'target').write_text('x')
            try:
                (root / 'link').symlink_to(root / 'target')
            except OSError:
                self.skipTest('Symlink privilege unavailable')
            with self.assertRaises(ValueError):
                baseline.hash_tree(root)


if __name__ == '__main__':
    unittest.main()
