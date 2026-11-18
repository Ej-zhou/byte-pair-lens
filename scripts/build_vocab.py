"""Convert tiktoken .tiktoken vocab files into the compact JSON the site loads.

Usage:  python3 build_vocab.py <data_dir> <out_dir>
Each output JSON: {name, cats: [category names], cat: [cat index per token], tokens: [base64 bytes per token]}
"""
import base64, json, sys, unicodedata
from collections import Counter
from pathlib import Path

ENCODINGS = ['r50k_base', 'cl100k_base', 'o200k_base']


def classify(b: bytes) -> str:
    try:
        s = b.decode('utf-8')
    except UnicodeDecodeError:
        return 'partial-UTF-8 / byte fragment'
    if len(b) == 1 and b[0] < 128:
        return 'single ASCII byte'
    s2 = s.strip()
    if not s2:
        return 'whitespace only'
    scripts = Counter()
    for ch in s2:
        o = ord(ch)
        if ch.isascii():
            scripts['ASCII' if ch.isalpha() else ('ASCII-digit' if ch.isdigit() else 'ASCII-punct')] += 1
        elif 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0x20000 <= o <= 0x3134F or 0xF900 <= o <= 0xFAFF:
            scripts['CJK Han'] += 1
        elif 0x3040 <= o <= 0x30FF or 0x31F0 <= o <= 0x31FF:
            scripts['Japanese kana'] += 1
        elif 0xAC00 <= o <= 0xD7AF or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F:
            scripts['Korean hangul'] += 1
        elif 0x0400 <= o <= 0x04FF:
            scripts['Cyrillic'] += 1
        elif 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F:
            scripts['Arabic'] += 1
        elif 0x0590 <= o <= 0x05FF:
            scripts['Hebrew'] += 1
        elif 0x0370 <= o <= 0x03FF:
            scripts['Greek'] += 1
        elif 0x0900 <= o <= 0x0DFF:
            scripts['Indic'] += 1
        elif 0x0E00 <= o <= 0x0E7F:
            scripts['Thai'] += 1
        elif 0x00C0 <= o <= 0x024F:
            scripts['Latin extended (accented)'] += 1
        elif 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF:
            scripts['CJK punctuation / fullwidth'] += 1
        else:
            cat = unicodedata.category(ch)
            scripts['emoji/symbol' if cat.startswith('S') else 'other non-ASCII'] += 1
    nonascii = {k: v for k, v in scripts.items() if not k.startswith('ASCII')}
    if nonascii:
        return max(nonascii, key=nonascii.get)
    if scripts.get('ASCII'):
        return 'ASCII word/subword'
    if scripts.get('ASCII-digit'):
        return 'ASCII digits'
    return 'ASCII punctuation/mixed'


def main(data_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ENCODINGS:
        toks = [base64.b64decode(line.split()[0]) for line in open(data_dir / f'{name}.tiktoken')]
        cats, idx, catids = [], {}, []
        for b in toks:
            c = classify(b)
            if c not in idx:
                idx[c] = len(cats); cats.append(c)
            catids.append(idx[c])
        json.dump({'name': name, 'cats': cats, 'cat': catids,
                   'tokens': [base64.b64encode(b).decode() for b in toks]},
                  open(out_dir / f'{name}.json', 'w'), separators=(',', ':'))
        print(name, len(toks), 'tokens')


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]))
