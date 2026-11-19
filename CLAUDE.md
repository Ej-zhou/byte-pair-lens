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

# one-time setup for scripts (gpt-tokenizer bundles the .tiktoken files)
cd scripts && npm install

# regenerate docs/*.json from the .tiktoken files
cd scripts && python3 build_vocab.py node_modules/gpt-tokenizer/data ../docs

# correctness check — must print N/N match for all three encodings, exits 1 on mismatch
cd scripts && node check_encoder.mjs
```

There is no build step, bundler, linter or test framework. `check_encoder.mjs` is the only test; add new test strings to its `tests` array.

## Architecture

- `docs/` is the deployable site, served as-is (GitHub Pages from `/docs`). `docs/index.html` is the entire app: HTML + CSS + one IIFE of vanilla JS, no dependencies. Keep it dependency-free.
- Vocab JSON (`docs/<enc>.json`): `{name, cats, cat, tokens}` where `tokens[i]` is base64 of token id `i`'s raw bytes (rank order = merge order) and `cat[i]` indexes into `cats`. Categories are computed offline by `classify()` in `scripts/build_vocab.py`; the browser does not reclassify, so changing script buckets means regenerating the JSON.
- Tokenizer in the browser: `load(enc)` decodes tokens to `Uint8Array`s and builds `ranks: Map<latin1-string-of-bytes, id>` (bytes → string via `String.fromCharCode` per byte, the `key()` helper). `encode()` pre-tokenises with `PAT[enc]` (regexes copied from tiktoken), looks up each piece directly, else runs `bpe()` (repeatedly merge the lowest-rank adjacent pair). `V` is the currently loaded vocab and `curEnc` its name; `bpe`/`encode` read these globals.
- CJK map: `BLOCKS` defines code-point ranges; `buildSets()` computes `hanSet` (code points whose 3-byte UTF-8 is a single token) and `prefixSet` (2-byte prefixes that are tokens); `drawMap()` renders to `<canvas>` reading colours via `getComputedStyle`, so it follows the theme. `buildSets()` currently assumes 3-byte characters (`b.length===3`).
- Theming: CSS custom properties on `:root`, dark mode via `prefers-color-scheme` and `[data-theme]`.

## Gotchas

- `check_encoder.mjs` does **not** execute `index.html`'s `bpe`/`encode`. It extracts only the `PAT` object by regex (`/const PAT=(\{[\s\S]*?\});\nconst TOKCOL/`) and uses its own copy of the BPE loop. So:
  - `const PAT={...};` must stay immediately followed by a line starting `const TOKCOL`, or the check breaks.
  - If you change the BPE/encode logic in `index.html`, mirror it in `check_encoder.mjs` (or refactor so both share code), otherwise the check passes without testing your change.
- The tool's credibility rests on the browser tokenizer being byte-identical to the reference; keep `check_encoder.mjs` passing and extend it when adding tokenizers.
- HF byte-level BPE `tokenizer.json` files store tokens in GPT-2's bytes-to-unicode alphabet; decode back to raw bytes before building `ranks`.
- Vocab JSON is large (o200k ≈ 3.1 MB). If adding 4-byte blocks (e.g. Ext B, 42k chars) to the map, cache an offscreen canvas per (enc, block) instead of redrawing.
