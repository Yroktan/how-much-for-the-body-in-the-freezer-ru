import argparse
import hashlib
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--game-dir', type=Path, required=True)
parser.add_argument('--build-dir', type=Path, required=True)
parser.add_argument('--package-dir', type=Path, required=True)
parser.add_argument('--xdelta3', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
metadata = json.loads((root / 'sources.json').read_text(encoding='utf-8'))
args.package_dir.mkdir(parents=True, exist_ok=True)
(args.package_dir / 'payload').mkdir(exist_ok=True)
manifest = {'version': '0.1.0', 'appid': metadata['appid'], 'buildid': metadata['buildid'], 'files': []}
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
for index, (relative, expected) in enumerate(metadata['files'].items()):
    source = args.game_dir / relative
    target = args.build_dir / relative
    if digest(source) != expected:
        raise ValueError('Unsupported source: ' + relative)
    patch = 'payload/' + str(index) + '.xdelta'
    subprocess.run([str(args.xdelta3.resolve()), '-f', '-9', '-B', '536870912', '-e', '-s', str(source.resolve()), str(target.resolve()), str((args.package_dir / patch).resolve())], check=True)
    manifest['files'].append({'path': relative, 'source_sha256': expected, 'target_sha256': digest(target), 'patch': patch})
(args.package_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
