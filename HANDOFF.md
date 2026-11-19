# Hand-off notes

Target: NAACL 2027 System Demonstrations, deadline **4 Dec 2026 (AoE)**. Submission needs a live URL, a ≤2.5-min video and a ≤6-page paper.

## 1. Hosting (done)

Live at **https://ethanpany.github.io/byte-pair-lens/** — GitHub Pages, deploy from branch `master`, folder `/docs`. Every merge to `master` redeploys automatically. Day-to-day work happens on the `ethanpany` branch.

`byte-pair-lens.vercel.app` is a separate, manual deploy of the original version. It is not connected to this repo and stays untouched until submission.

JSON files total ~5.4 MB; o200k alone is 3.1 MB. Pages serves gzip, which gets it to ~1.5 MB. If that's too slow, see §3.

## 2. Code orientation

One file, `docs/index.html`, ~360 lines, vanilla JS, no dependencies:

| Function | Does |
|---|---|
| `load(enc)` | fetches `<enc>.json`, decodes base64 → `Uint8Array` per token, builds `ranks: Map<latin1 string, id>` |
| `PAT` | the pre-tokeniser regexes, copied from tiktoken for each encoding |
| `bpe(bytes)` / `encode(str)` | the actual tokenizer: pre-tokenise, then greedy lowest-rank pair merging. Verified equal to the reference (`scripts/check_encoder.mjs`) |
| `render()` | token strip + stats |
| `renderBars()` | script breakdown bars + Han coverage panel |
| `renderTable()` | paged, searchable vocab browser |
| `buildSets()` / `drawMap()` | CJK map on a `<canvas>`; `hanSet` = code points that are whole 3-byte tokens, `prefixSet` = 2-byte fragment tokens |
| `showDetail(cp)` | hover panel for one character |

Theme: CSS custom properties on `:root`, dark via `prefers-color-scheme` and `[data-theme]`. Canvas reads colours with `getComputedStyle`, so it follows the theme.

## 3. Planned work for the demo (priority order)

1. **Load any HuggingFace `tokenizer.json`** (byte-level BPE first; SentencePiece-BPE with byte fallback second). Preload ~8: GPT-2, cl100k, o200k, Llama 2, Llama 3, Qwen2.5, Gemma 2, DeepSeek-V3. Note HF byte-level BPE stores tokens in the GPT-2 "bytes-to-unicode" alphabet, so decode that back to raw bytes before building `ranks`. Pre-tokeniser regex comes from `pre_tokenizer` in the JSON.
2. **Generalise the map beyond Han**: Hangul, Kana, Cyrillic, Arabic, Devanagari, Bengali, Thai, Hebrew, Greek, Latin-ext. `BLOCKS` is the only place to add ranges; `buildSets()` currently assumes 3-byte chars (`b.length===3`) — generalise to 2- and 4-byte.
3. **Coverage metrics table**: per script × tokenizer: whole-token rate, frequency-weighted coverage, fragment count, tokens/char on a fixed sample. Plus a heatmap. CSV export (the paper's tables come from this).
4. **Side-by-side**: same input, 2–4 tokenizers stacked.
5. Nice-to-have: frequency overlay on the map, permalinks (`#enc=…&block=…&cp=…`), PNG export of map/heatmap, merge-tree view for a token.

## 4. Performance notes

- `ranks` as a `Map` of latin1 strings is fine at 200k; loading o200k takes ~300 ms after fetch.
- `drawMap` redraws the whole block on every change; fine at 328 rows × 64, but if you add 4-byte blocks (Ext B is 42k chars) consider drawing to an offscreen canvas once per (enc, block) and caching.
- If JSON size becomes a problem: vocab files could be a binary blob (uint8 lengths + concatenated bytes) at roughly half the size, or lazy-load per tokenizer (already the case) with a service-worker cache.

## 5. Don't break

- `scripts/check_encoder.mjs` must keep passing. The whole credibility of the tool is that the browser tokenizer is exactly the reference tokenizer.
- Keep it dependency-free or close to it; reviewers will open the repo.
