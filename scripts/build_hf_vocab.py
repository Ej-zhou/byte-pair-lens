"""Convert Hugging Face tokenizer.json files into the compact vocab JSON the site loads.

Usage:  python3 build_hf_vocab.py [name ...]      (default: all in MODELS)
Downloads into scripts/hf_cache/ (gitignored), writes docs/<name>.json and, for
SentencePiece-style models, docs/<name>.merges.json (flat [a0,b0,a1,b1,...] token ids, rank order).

Every token is stored as its RAW BYTES (GPT-2 byte alphabet, '▁' and <0xNN> decoded), so the map
treats byte-level and byte-fallback tokenizers the same way. Check the output with check_hf.py.
"""
import base64, hashlib, json, os, re, subprocess, sys
from pathlib import Path
from build_vocab import classify

HERE = Path(__file__).parent
CACHE = HERE / 'hf_cache'
OUT = HERE.parent / 'docs'

# name -> (label, official repo, ungated mirror used when the official repo is gated for us)
MODELS = {
    'llama3.1':     ('Llama 3.1',    'meta-llama/Llama-3.1-8B',    'unsloth/Llama-3.1-8B'),
    'qwen3':        ('Qwen3',        'Qwen/Qwen3-8B',              None),
    'deepseek-v3':  ('DeepSeek-V3',  'deepseek-ai/DeepSeek-V3',    None),
    'gemma3':       ('Gemma 3',      'google/gemma-3-4b-it',       'unsloth/gemma-3-4b-it'),
    'mistral-v0.3': ('Mistral v0.3', 'mistralai/Mistral-7B-v0.3',  None),
}


def fetch(name):
    """Download tokenizer.json, official repo first; returns (path, repo used)."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f'{name}.tokenizer.json'
    _, official, mirror = MODELS[name]
    token = None
    tp = Path.home() / '.cache/huggingface/token'
    if tp.exists():
        token = tp.read_text().strip()
    for repo in [official, mirror]:
        if not repo:
            continue
        # curl, not urllib: python.org builds on macOS often lack CA certificates
        cmd = ['curl', '-sL', '-o', str(path), '-w', '%{http_code}',
               f'https://huggingface.co/{repo}/resolve/main/tokenizer.json']
        if token and repo == official:
            cmd[1:1] = ['-H', f'Authorization: Bearer {token}']
        code = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
        if code == '200':
            return path, repo
        print(f'  {repo}: HTTP {code}, trying next source')
    raise SystemExit(f'{name}: no source could be downloaded')


def byte_decoder():
    """Inverse of GPT-2's bytes_to_unicode()."""
    bs = list(range(ord('!'), ord('~') + 1)) + list(range(ord('¡'), ord('¬') + 1)) + list(range(ord('®'), ord('ÿ') + 1))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return {chr(c): b for b, c in zip(bs, cs)}


def js_regex(rx):
    """Rust/Oniguruma regex -> JS 'u' regex. Only (?i:...) needs rewriting for older browsers."""
    def ci(m):
        return '(?:' + re.sub(r'[A-Za-z]', lambda c: f'[{c.group().lower()}{c.group().upper()}]', m.group(1)) + ')'
    return re.sub(r'\(\?i:([^()]*)\)', ci, rx)


def splits_of(pre):
    """Flatten the pre_tokenizer into a list of 'Isolated' split regexes (+ ByteLevel / Metaspace flags)."""
    items = pre['pretokenizers'] if pre and pre['type'] == 'Sequence' else [pre]
    splits, info = [], {}
    for p in items:
        if p is None:
            continue
        t = p['type']
        if t == 'Split':
            if 'Regex' in p['pattern']:
                assert p['behavior'] == 'Isolated' and not p['invert'], p
                splits.append(js_regex(p['pattern']['Regex']))
            else:
                info['split_string'] = p['pattern']['String']
        elif t == 'ByteLevel':
            assert not p.get('use_regex', True) or not splits, 'ByteLevel with its own regex is not supported'
            info['bytelevel'] = True
        elif t == 'Metaspace':
            info['metaspace'] = p
        else:
            raise SystemExit(f'unsupported pre_tokenizer {t}')
    return splits, info


def build(name):
    label = MODELS[name][0]
    path, repo = fetch(name)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    j = json.loads(path.read_text())
    m = j['model']
    assert m.get('type', 'BPE') == 'BPE'
    vocab = m['vocab']
    added = j.get('added_tokens', [])
    size = max(max(vocab.values()), max((a['id'] for a in added), default=-1)) + 1
    piece = [None] * size
    for p, i in vocab.items():
        piece[i] = p
    added_ids = set()
    for a in added:
        assert not (a['lstrip'] or a['rstrip'] or a['single_word']), a
        # added tokens are stored as plain text even when the model vocab also lists them
        piece[a['id']] = a['content']
        added_ids.add(a['id'])
    assert all(p is not None for p in piece), f'{name}: gaps in token ids'

    norm = j.get('normalizer')
    splits, info = splits_of(j.get('pre_tokenizer'))
    pre = {'splits': splits}
    if norm and norm['type'] == 'NFC':
        pre['normalizer'] = 'NFC'
    sp = bool(m.get('byte_fallback'))

    if not sp:
        assert info.get('bytelevel'), f'{name}: expected byte-level BPE'
        assert norm is None or norm['type'] in ('NFC',) or (norm['type'] == 'Sequence' and not norm['normalizers']), norm
        dec = byte_decoder()
        raw = [p.encode('utf-8') if i in added_ids else bytes(dec[c] for c in p) for i, p in enumerate(piece)]
        pre['ignoreMerges'] = bool(m.get('ignore_merges'))
        out = {'kind': 'bytelevel', 'tokens': [base64.b64encode(b).decode() for b in raw]}
    else:
        if norm:  # Gemma: spaces -> '▁' (its Split on ' ' then has nothing to split)
            assert norm['type'] == 'Replace' and norm['pattern'] == {'String': ' '} and norm['content'] == '▁', norm
            assert info.get('split_string') in (None, ' ')
            pre['replaceSpace'] = True
        ms = info.get('metaspace')
        if ms:  # Mistral: Metaspace, prefix '▁' at the start of the input, no splitting
            assert ms['replacement'] == '▁' and ms['prepend_scheme'] == 'first' and not ms['split'], ms
            pre['replaceSpace'] = True
            pre['prepend'] = 'first'
        raw = []
        for p in piece:
            if re.fullmatch(r'<0x[0-9A-F]{2}>', p):
                raw.append(bytes([int(p[3:5], 16)]))
            else:
                raw.append(p.replace('▁', ' ').encode('utf-8'))
        merges = []
        for mg in m['merges']:
            a, b = mg.split(' ', 1) if isinstance(mg, str) else mg
            merges += [vocab[a], vocab[b]]
        (OUT / f'{name}.merges.json').write_text(json.dumps(merges, separators=(',', ':')))
        out = {'kind': 'sp', 'pieces': piece}

    cats, idx, catids = [], {}, []
    for i, b in enumerate(raw):
        c = 'special / added token' if i in added_ids or any(a['id'] == i and a['special'] for a in added) else classify(b)
        if c not in idx:
            idx[c] = len(cats)
            cats.append(c)
        catids.append(idx[c])

    doc = {'name': name, 'label': label, 'source': f'{repo} (tokenizer.json sha256 {sha}…)',
           **out, 'pre': pre, 'cats': cats, 'cat': catids,
           'added': [[a['content'], a['id']] for a in added]}
    (OUT / f'{name}.json').write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':')))
    kb = os.path.getsize(OUT / f'{name}.json') // 1024
    print(f'{name}: {size} tokens, {"sp" if sp else "bytelevel"}, from {repo}, {kb} KB')


if __name__ == '__main__':
    for n in sys.argv[1:] or MODELS:
        build(n)
