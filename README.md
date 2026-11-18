# Byte Pair Lens

Interactive visualiser for how byte-level BPE tokenizers (GPT-2 / GPT-4 / GPT-4o) cut text into UTF-8 bytes and merges, with a vocabulary breakdown by script and a code-point coverage map for CJK.

Everything runs client-side. No build step, no server.

## Layout

```
docs/                 the website (deploy this folder as-is)
  index.html          single-file app: HTML + CSS + JS
  r50k_base.json      GPT-2/3 vocab (50,256 tokens)
  cl100k_base.json    GPT-4 vocab (100,256 tokens)
  o200k_base.json     GPT-4o vocab (199,998 tokens)
scripts/
  build_vocab.py      regenerates the JSON files from tiktoken .tiktoken vocab files
  check_encoder.mjs   asserts the in-browser BPE matches the reference encoder
HANDOFF.md            notes for whoever hosts / extends the site
```

## Run locally

Any static server works; `fetch()` of the JSON files needs http(s), not `file://`.

```
cd docs && python3 -m http.server 8000
# open http://localhost:8000
```

## Vocab JSON format

```json
{"name": "cl100k_base",
 "cats": ["single ASCII byte", "partial-UTF-8 / byte fragment", ...],
 "cat":  [0, 0, 0, ..., 12, 3],      // category index per token, by rank
 "tokens": ["IQ==", "Ig==", ...]}    // base64 of each token's raw bytes, by rank
```

Rank order is merge order, so `tokens[i]` is token id `i`.

## Regenerate / verify

```
cd scripts
npm install                      # pulls gpt-tokenizer, which bundles the .tiktoken files
python3 build_vocab.py node_modules/gpt-tokenizer/data ../docs
node check_encoder.mjs           # expect N/N match for all three
```

## What it shows

- **Tokenizer tab:** token strip with rank and bytes for each token; byte-fragment tokens (not a complete UTF-8 character) highlighted; chars / bytes / tokens / tokens-per-char.
- **Vocabulary by script:** every vocab entry bucketed by Unicode range; click a bar to browse that bucket.
- **Han coverage:** how many Han characters are whole tokens, and how many of the 300 most frequent Chinese characters are.
- **CJK map tab:** U+4E00–9FFF (or Ext A) as a 64-column grid, one row per 2-byte UTF-8 prefix; blue = whole token, grey = falls back to byte fragments; orange marker = the prefix itself is a fragment token. Hover/tap for the exact split.

## Licence

MIT. Vocabulary data is from [tiktoken](https://github.com/openai/tiktoken) (MIT), redistributed via the `gpt-tokenizer` npm package.
