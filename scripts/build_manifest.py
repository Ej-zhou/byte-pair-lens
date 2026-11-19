"""Write docs/manifest.json (content hash + size of every data file) and version the script tags in index.html.

Usage:  python3 build_manifest.py          (run after any build_*.py / build_coverage.cjs)
        python3 build_manifest.py --check  (exit 1 if the manifest or script versions are stale)

The page fetches data as <file>?v=<hash> and keeps it in the browser's Cache Storage, so repeat
visits load from disk and an update can never mix a new page with an old vocabulary file.
"""
import hashlib, json, re, sys
from pathlib import Path

DOCS = Path(__file__).parent.parent / 'docs'


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def build():
    files = {p.name: {'v': digest(p), 'size': p.stat().st_size}
             for p in sorted(DOCS.glob('*.json')) if p.name != 'manifest.json'}
    files['coverage.csv'] = {'v': digest(DOCS / 'coverage.csv'), 'size': (DOCS / 'coverage.csv').stat().st_size}
    manifest = json.dumps({'files': files}, indent=1, sort_keys=True) + '\n'
    html = (DOCS / 'index.html').read_text()
    for js in ['bpe.js', 'bytemap.js']:
        html = re.sub(rf'<script src="{re.escape(js)}(\?v=[0-9a-f]+)?"></script>',
                      f'<script src="{js}?v={digest(DOCS / js)}"></script>', html)
    return manifest, html


if __name__ == '__main__':
    manifest, html = build()
    mp, hp = DOCS / 'manifest.json', DOCS / 'index.html'
    if '--check' in sys.argv:
        stale = [p.name for p, new in [(mp, manifest), (hp, html)] if not p.exists() or p.read_text() != new]
        print('manifest up to date' if not stale else f'stale: {stale}; run python3 build_manifest.py')
        sys.exit(1 if stale else 0)
    mp.write_text(manifest)
    hp.write_text(html)
    print(f'manifest: {len(json.loads(manifest)["files"])} files; script tags versioned')
