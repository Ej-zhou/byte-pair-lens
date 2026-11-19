"""Recompute the byte map's numbers independently and compare them with docs/bytemap.js.

Usage:  python3 check_map.py [name ...]
For each tokenizer and block, checks: which characters are whole tokens, how many row prefixes are
fragment tokens, and the total tokens needed for the block's characters on their own. Hugging Face
models are checked through the `tokenizers` library itself (vocab lookup and model.tokenize, which
skips normalisation and pre-tokenisation like the map does); tiktoken files through their raw bytes.
Exits non-zero on any mismatch. Unicode-version differences in "assigned" counts are reported.
"""
import base64, json, subprocess, sys, unicodedata
from pathlib import Path
from tokenizers import Tokenizer
from build_hf_vocab import MODELS, CACHE, byte_decoder

HERE = Path(__file__).parent
DOCS = HERE.parent / 'docs'
TIKTOKEN = ['r50k_base', 'cl100k_base', 'o200k_base']
BLOCKS = {  # must match docs/bytemap.js
    'ascii': (0x0000, 0x007F), 'latin': (0x0080, 0x024F), 'greek': (0x0370, 0x03FF), 'cyrillic': (0x0400, 0x04FF),
    'hebrew': (0x0590, 0x05FF), 'arabic': (0x0600, 0x06FF), 'devanagari': (0x0900, 0x097F), 'bengali': (0x0980, 0x09FF),
    'thai': (0x0E00, 0x0E7F), 'kana': (0x3040, 0x30FF), 'hangul': (0xAC00, 0xD7A3), 'han': (0x4E00, 0x9FFF),
    'hanA': (0x3400, 0x4DBF), 'emoji': (0x1F300, 0x1FAFF), 'hanB': (0x20000, 0x2A6DF),
}
B2U = {b: c for c, b in byte_decoder().items()}


def tiktoken_oracle(name):
    raw = [base64.b64decode(t) for t in json.load(open(DOCS / f'{name}.json'))['tokens']]
    rank = {b: i for i, b in reversed(list(enumerate(raw)))}

    def bpe(bs):  # textbook BPE with rank = token id, written independently of bpe.js
        parts = [bytes([x]) for x in bs]
        while len(parts) > 1:
            pairs = [(rank.get(parts[i] + parts[i + 1]), i) for i in range(len(parts) - 1)]
            pairs = [p for p in pairs if p[0] is not None]
            if not pairs:
                break
            _, i = min(pairs)
            parts[i:i + 2] = [parts[i] + parts[i + 1]]
        return len(parts)
    return (lambda bs: bs in rank), bpe


def hf_oracle(name):
    tok = Tokenizer.from_file(str(CACHE / f'{name}.tokenizer.json'))
    j = json.loads((CACHE / f'{name}.tokenizer.json').read_text())
    sp = bool(j['model'].get('byte_fallback'))
    if sp:
        def has(bs):
            # one byte is always one token via <0xNN> byte fallback (e.g. '\n' is <0x0A>)
            if len(bs) == 1 and tok.token_to_id('<0x%02X>' % bs[0]) is not None:
                return True
            try:
                s = bs.decode('utf-8')
            except UnicodeDecodeError:
                return False
            return tok.token_to_id(s.replace(' ', '\u2581')) is not None
    else:
        def has(bs):
            return tok.token_to_id(''.join(B2U[x] for x in bs)) is not None

    def ntok(bs):
        return len(tok.model.tokenize(bs.decode('utf-8') if sp else ''.join(B2U[x] for x in bs)))
    return has, ntok


def oracle_stats(has, ntok):
    out = {}
    for bid, (lo, hi) in BLOCKS.items():
        assigned = whole = tok = prefix_rows = prefixable = 0
        whole_cps = []
        for row in range(lo >> 6, (hi >> 6) + 1):
            pre = chr(row << 6).encode()[:-1]
            if len(pre) >= 2:
                prefixable += 1
                prefix_rows += has(pre)
            for cp in range(max(lo, row << 6), min(hi, (row << 6) | 63) + 1):
                if unicodedata.category(chr(cp)) in ('Cn', 'Cs', 'Co'):
                    continue
                assigned += 1
                bs = chr(cp).encode()
                w = has(bs)
                whole += w
                tok += 1 if w else ntok(bs)
                if w:
                    whole_cps.append(cp)
        out[bid] = dict(assigned=assigned, whole=whole, tok=tok, prefixRows=prefix_rows, prefixable=prefixable, wholeCps=whole_cps)
    return out


def main(names):
    print(f'Python Unicode database {unicodedata.unidata_version}')
    fail = 0
    for name in names:
        js = json.loads(subprocess.run(['node', str(HERE / 'map_cli.cjs'), name], capture_output=True, text=True, check=True).stdout)
        exp = oracle_stats(*(tiktoken_oracle(name) if name in TIKTOKEN else hf_oracle(name)))
        bad, notes = [], []
        for bid, e in exp.items():
            g = js[bid]
            gw, ew = set(g['wholeCps']), set(e['wholeCps'])
            only_assigned_diff = gw - ew == set() and all(unicodedata.category(chr(c)) in ('Cn', 'Cs') for c in ew - gw)
            if gw != ew and not only_assigned_diff:
                bad.append(f'{bid}: whole sets differ ({len(gw ^ ew)} chars, e.g. {sorted(gw ^ ew)[:3]})')
            if (g['prefixRows'], g['prefixable']) != (e['prefixRows'], e['prefixable']):
                bad.append(f"{bid}: prefix rows {g['prefixRows']}/{g['prefixable']} vs {e['prefixRows']}/{e['prefixable']}")
            if g['assigned'] != e['assigned']:
                notes.append(f"{bid}: assigned {g['assigned']} (JS) vs {e['assigned']} (Python), Unicode version difference")
            elif g['tok'] != e['tok']:
                bad.append(f"{bid}: total tokens {g['tok']} vs {e['tok']}")
        has = (tiktoken_oracle(name) if name in TIKTOKEN else hf_oracle(name))[0]
        # Coverage tab: weighted coverage from docs/coverage.json vs the oracle and docs/freq.json
        freq = json.load(open(DOCS / 'freq.json'))['scripts']
        cov = {r['script']: r for r in json.load(open(DOCS / 'coverage.json'))['rows'] if r['tokenizer'] == name}
        for sid, F in freq.items():
            exp_w = sum(c for cp, c in F['chars'] if has(chr(cp).encode())) / F['total']
            if abs(cov[sid]['weighted'] - exp_w) > 1e-9:
                bad.append(f"coverage {sid}: weighted {cov[sid]['weighted']:.6f} vs {exp_w:.6f}")
        # whole of Unicode (the overview): compare characters assigned in both Unicode versions
        ow = set(js['_overview']['wholeCps'])
        py_assigned = [cp for cp in range(0x110000) if not 0xD800 <= cp <= 0xDFFF and unicodedata.category(chr(cp)) not in ('Cn', 'Co')]
        ew = {cp for cp in py_assigned if has(chr(cp).encode())}
        ow_common = {cp for cp in ow if unicodedata.category(chr(cp)) not in ('Cn', 'Co')}
        if ow_common != ew:
            bad.append(f'overview: whole sets differ ({len(ow_common ^ ew)} chars, e.g. {sorted(ow_common ^ ew)[:3]})')
        notes.append(f"overview: {js['_overview']['totW']:,} / {js['_overview']['totA']:,} whole (JS, Unicode 17); {len(ew):,} / {len(py_assigned):,} (Python, Unicode {unicodedata.unidata_version})")
        fail += len(bad)
        print(f"{name}: {'OK' if not bad else 'MISMATCH'} across {len(exp)} blocks")
        for line in bad + notes:
            print('  ', line)
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main(sys.argv[1:] or TIKTOKEN + list(MODELS))
