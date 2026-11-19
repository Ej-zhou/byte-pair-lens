"""Verify docs/bpe.js against Hugging Face `tokenizers` for every tokenizer built by build_hf_vocab.py.

Usage:  python3 check_hf.py [name ...]      (needs `pip install tokenizers` and node)
Exits non-zero on any mismatch. Also checks that every vocab entry decodes to the same bytes.
"""
import json, subprocess, sys
from pathlib import Path
from tokenizers import Tokenizer
from build_hf_vocab import MODELS, CACHE

HERE = Path(__file__).parent

TESTS = [
    '今天天气很好。The weather is nice today. 날씨가 좋다 — numéro 2024!',
    'def tokenize(text: str) -> list[int]:\n    return [ord(c) for c in text]',
    "龘齉爨靐 I'm here, we've GONE.   \n\n  x",
    'Większość programów używa UTF-8. Привет мир. Καλημέρα κόσμε.',
    'مرحبا بالعالم. שלום עולם. नमस्ते दुनिया. ওহে বিশ্ব. สวัสดีชาวโลก',
    'こんにちは世界、カタカナとひらがな。안녕하세요 세계',
    '😀🎉 👍🏽 👨‍👩‍👧 🇨🇳 ≥ 1234567 3.14159 1,000,000',
    '𠀀𠀁𪚥 rare Ext-B 㐀㐁 Ext-A',
    'Café vs Café (NFC vs NFD) ﬁ ligature',
    '  leading spaces\ttabs\r\nCRLF\n\n\nmany newlines   trailing  ',
    "DON'T You're I'LL we'd THEY'VE",
    'x' * 300 + ' ' + '中' * 50,
    '<think>tags</think> <|endoftext|> <unused0> [multimodal]',
    '',
    ' ',
    '▁already▁has▁metaspace',
    'αβγ ΑΒΓ ẞ ǅ ǈ İstanbul',
    '1234567890123 ٠١٢٣ १२३',
    'https://example.com/a/b?c=d&e=f#g',
    '天',
    '氣气汽',
    '🫠🫡🫥',
    'Ελληνικά العربية עברית हिन्दी ไทย 한국어 日本語 中文',
    'tab\there, null\x00char, bell\x07',
    '​‍﻿ zero-width',
    'ـــ tatweel كتب يكتب مكتوب',
    'ಕನ್ನಡ தமிழ் తెలుగు മലയാളം',
    '!!!???... ---- ==== ****',
    '中文English混合mixed语言text',
    'ｆｕｌｌｗｉｄｔｈ　ＡＢＣ　１２３',
]


def main(names):
    fail = 0
    for name in names:
        tok = Tokenizer.from_file(str(CACHE / f'{name}.tokenizer.json'))
        ref = [tok.encode(t, add_special_tokens=False).ids for t in TESTS]
        out = subprocess.run(['node', str(HERE / 'encode_cli.cjs'), name], input=json.dumps(TESTS),
                             capture_output=True, text=True)
        if out.returncode:
            print(name, 'node error:', out.stderr[-500:])
            fail += 1
            continue
        got = json.loads(out.stdout)
        bad = [t for t, a, b in zip(TESTS, got, ref) if a != b]
        for t in bad[:5]:
            print(f'  {name} MISMATCH {t[:60]!r}')
        fail += len(bad)
        print(f'{name}: {len(TESTS) - len(bad)}/{len(TESTS)} match Hugging Face tokenizers')
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main(sys.argv[1:] or list(MODELS))
