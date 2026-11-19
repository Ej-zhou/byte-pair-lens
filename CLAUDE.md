# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Byte Pair Lens: a client-side visualiser for byte-level BPE tokenizers (r50k / cl100k / o200k), focused on how CJK text is split into UTF-8 bytes and merges. Target is a NAACL 2027 System Demonstrations submission (deadline 4 Dec 2026 AoE: live URL + ≤2.5-min video + ≤6-page paper). `HANDOFF.md` has the prioritised roadmap (HF `tokenizer.json` loading, non-Han script maps, coverage metrics table/CSV, side-by-side view) — read it before starting feature work.

## Branches and deployment

- Work on the `ethanpany` branch; merge to `master` via PR to publish.
- `master` auto-deploys to GitHub Pages (branch `master`, folder `/docs`) at https://ethanpany.github.io/byte-pair-lens/. Anything merged to `master` is public within a minute or two.
- Do **not** deploy to `byte-pair-lens.vercel.app`. It is deliberately kept on the original version during development and is not connected to the repo; it gets updated once, by hand, before submission.

## Commands

```bash
# run the site (fetch() of the vocab JSON needs http, not file://)
cd docs && python3 -m http.server 8000

# one-time setup for scripts (gpt-tokenizer bundles the .tiktoken files; checks need `pip install tokenizers`)
cd scripts && npm install

# regenerate the tiktoken vocabs (r50k/cl100k/o200k)
cd scripts && python3 build_vocab.py node_modules/gpt-tokenizer/data ../docs
# regenerate the Hugging Face vocabs (all, or name some: llama3.1 qwen3 deepseek-v3 gemma3 mistral-v0.3)
cd scripts && python3 build_hf_vocab.py [name ...]

# checks: all must pass before merging; each exits 1 on mismatch
cd scripts && node check_encoder.mjs      # bpe.js vs tiktoken, 3 tokenizers
cd scripts && python3 check_hf.py [name]  # bpe.js vs Hugging Face tokenizers, 30 strings each
cd scripts && python3 check_map.py [name] # bytemap.js vs an independent recount, 15 blocks each
```

No bundler, linter or test framework. To test one tokenizer, pass its name. Add test strings to `TESTS` in `check_hf.py` (and `tests` in `check_encoder.mjs`). The emoji block's "assigned" count depends on the Unicode version of the JS engine vs Python; `check_map.py` reports it but doesn't fail on it.

## Architecture

- `docs/` is the deployable site, served as-is (GitHub Pages from `/docs`). `docs/index.html` is the entire app: HTML + CSS + one IIFE of vanilla JS, no dependencies. Keep it dependency-free.
- Vocab JSON (`docs/<enc>.json`): `{name, cats, cat, tokens}` where `tokens[i]` is base64 of token id `i`'s raw bytes (rank order = merge order) and `cat[i]` indexes into `cats`. Categories are computed offline by `classify()` in `scripts/build_vocab.py`; the browser does not reclassify, so changing script buckets means regenerating the JSON.
- Tokenizer engine: `docs/bpe.js` (classic script exposing global `BPE`; also `require`-able from Node). `BPE.load(json)` builds a vocab object with `bytes`, `text`, `encode()`. Two families: `bytelevel` (tiktoken files and HF byte-level BPE; merge rank = token id, verified for every file we ship) and `sp` (SentencePiece-style BPE with byte fallback; merge rank = merges-list order, loaded from a separate `<enc>.merges.json`). The three original tiktoken JSONs have no `kind`/`pre`, so their regexes live in `BPE.TIKTOKEN`. `docs/bytemap.js` (global `ByteMap`) holds the map's block list and per-block counts, shared with `check_map.py`. `index.html` holds only UI code; `V` is the loaded vocab and `curEnc` its name.
- CJK map: `BLOCKS` defines code-point ranges; `buildSets()` computes `hanSet` (code points whose 3-byte UTF-8 is a single token) and `prefixSet` (2-byte prefixes that are tokens); `drawMap()` renders to `<canvas>` reading colours via `getComputedStyle`, so it follows the theme. `buildSets()` currently assumes 3-byte characters (`b.length===3`).
- Theming: CSS custom properties on `:root`, dark mode via `prefers-color-scheme` and `[data-theme]`.

## Gotchas

- Both checks import `docs/bpe.js` directly, so they test the code the page runs. Change tokenisation only in `bpe.js`.
- The tool's credibility rests on the browser tokenizer being byte-identical to the reference; keep `check_encoder.mjs` passing and extend it when adding tokenizers.
- HF byte-level BPE `tokenizer.json` files store tokens in GPT-2's bytes-to-unicode alphabet; decode back to raw bytes before building `ranks`.
- Vocab JSON is large (o200k ≈ 3.1 MB). If adding 4-byte blocks (e.g. Ext B, 42k chars) to the map, cache an offscreen canvas per (enc, block) instead of redrawing.
