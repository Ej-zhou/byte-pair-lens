"""Character frequencies per featured script, from a fixed Wikipedia sample. Writes docs/freq.json.

Usage:  uv run --with pyarrow --with fsspec --with aiohttp --with requests python build_freq.py

Method (the same for every script, recorded in the output):
- Wikipedia dump 20231101 from the Hugging Face dataset `wikimedia/wikipedia` (parquet conversion).
- For each language, the first parquet shard; ROW_GROUPS row groups evenly spaced through it
  (each row group is ~1,000 articles), so the sample is not just the oldest articles.
- Scripts written in several languages (Latin, Cyrillic, Arabic) split the row groups between them
  (at least two per language).
- Count every character whose code point is in the script's block. Han Extension A/B use the
  Chinese sample. Emoji have no Wikipedia-like corpus and are left without frequencies.
"""
import json
from collections import Counter
from pathlib import Path
import fsspec
import pyarrow.parquet as pq

DUMP = '20231101'
ROW_GROUPS = 8
URL = 'https://huggingface.co/datasets/wikimedia/wikipedia/resolve/refs%2Fconvert%2Fparquet/{dump}.{lang}/train/0000.parquet'

# script id (as in docs/bytemap.js FEATURED) -> (lo, hi, languages)
SCRIPTS = {
    'ascii':      (0x0000, 0x007F, ['en']),
    'latin':      (0x0080, 0x024F, ['fr', 'de', 'es', 'pl', 'cs', 'hu', 'tr', 'pt']),
    'greek':      (0x0370, 0x03FF, ['el']),
    'cyrillic':   (0x0400, 0x04FF, ['ru', 'uk']),
    'hebrew':     (0x0590, 0x05FF, ['he']),
    'arabic':     (0x0600, 0x06FF, ['ar', 'fa']),
    'devanagari': (0x0900, 0x097F, ['hi']),
    'bengali':    (0x0980, 0x09FF, ['bn']),
    'thai':       (0x0E00, 0x0E7F, ['th']),
    'kana':       (0x3040, 0x30FF, ['ja']),
    'hangul':     (0xAC00, 0xD7A3, ['ko']),
    'han':        (0x4E00, 0x9FFF, ['zh']),
    'hanA':       (0x3400, 0x4DBF, ['zh']),
    'hanB':       (0x20000, 0x2A6DF, ['zh']),
}

_cache = {}


def sample(lang, groups):
    """Character counts of `groups` evenly spaced row groups of a language's first shard."""
    key = (lang, groups)
    if key in _cache:
        return _cache[key]
    f = pq.ParquetFile(fsspec.open(URL.format(dump=DUMP, lang=lang), 'rb', block_size=2 ** 20).open())
    n = f.num_row_groups
    picks = sorted({round(i * (n - 1) / max(1, groups - 1)) for i in range(groups)})
    counts, articles = Counter(), 0
    for g in picks:
        texts = f.read_row_group(g, columns=['text']).column('text').to_pylist()
        articles += len(texts)
        for t in texts:
            counts.update(t)
    _cache[key] = (counts, articles, picks, n)
    print(f'  {lang}: row groups {picks} of {n}, {articles} articles, {sum(counts.values()):,} characters')
    return _cache[key]


def main():
    out = {'source': f'Wikipedia {DUMP} (wikimedia/wikipedia on Hugging Face), {ROW_GROUPS} evenly spaced '
                     'row groups of the first parquet shard per script, split across its languages',
           'scripts': {}}
    for sid, (lo, hi, langs) in SCRIPTS.items():
        per = max(2, ROW_GROUPS // len(langs))  # at least two spread-out row groups per language
        total, parts = Counter(), []
        for lang in langs:
            counts, articles, picks, n = sample(lang, per)
            total.update({ch: c for ch, c in counts.items() if lo <= ord(ch) <= hi})
            parts.append({'lang': lang, 'articles': articles, 'rowGroups': picks, 'of': n})
        chars = sorted(((ord(ch), c) for ch, c in total.items()), key=lambda x: (-x[1], x[0]))
        out['scripts'][sid] = {'langs': parts, 'total': sum(c for _, c in chars), 'chars': chars}
        print(f'{sid}: {len(chars):,} distinct characters, {sum(c for _, c in chars):,} occurrences')
    path = Path(__file__).parent.parent / 'docs' / 'freq.json'
    path.write_text(json.dumps(out, separators=(',', ':')))
    print(f'wrote {path} ({path.stat().st_size // 1024} KB)')


if __name__ == '__main__':
    main()
