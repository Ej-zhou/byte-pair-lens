// Coverage table for every tokenizer x featured script, from docs/bytemap.js and docs/freq.json.
// Writes docs/coverage.json (loaded by the Coverage tab) and docs/coverage.csv (for the paper).
// Usage: node build_coverage.cjs
const fs = require('fs');
const path = require('path');
const BPE = require('../docs/bpe.js');
const ByteMap = require('../docs/bytemap.js');

const docs = path.join(__dirname, '..', 'docs');
const TOKENIZERS = [
  ['r50k_base', 'GPT-2/3'], ['cl100k_base', 'GPT-4'], ['o200k_base', 'GPT-4o'], ['llama3.1', 'Llama 3.1'],
  ['qwen3', 'Qwen3'], ['deepseek-v3', 'DeepSeek-V3'], ['gemma3', 'Gemma 3'], ['mistral-v0.3', 'Mistral v0.3'],
];
const freq = JSON.parse(fs.readFileSync(path.join(docs, 'freq.json'), 'utf8'));
const rows = [];
for (const [enc, short] of TOKENIZERS) {
  const V = BPE.load(JSON.parse(fs.readFileSync(path.join(docs, `${enc}.json`), 'utf8')));
  if (V.kind === 'sp') V.setMerges(JSON.parse(fs.readFileSync(path.join(docs, `${enc}.merges.json`), 'utf8')));
  for (const blk of ByteMap.FEATURED) {
    const C = ByteMap.coverage(V, blk, freq.scripts[blk.id]);
    rows.push({
      tokenizer: enc, short, script: blk.id,
      wholeAll: C.wholeAll, weighted: C.weighted ?? null, topWhole: C.topWhole ?? null, topN: C.topN ?? null,
      tokPerChar: C.tokPerChar ?? null, occurrences: C.occurrences ?? 0, distinct: C.distinct ?? 0,
    });
  }
  console.log(enc, 'done');
}
const out = { source: freq.source, top: ByteMap.TOP, tokenizers: TOKENIZERS, scripts: ByteMap.FEATURED.map(b => b.id), rows };
fs.writeFileSync(path.join(docs, 'coverage.json'), JSON.stringify(out));
const head = 'tokenizer,script,whole_rate_all_chars,weighted_coverage,top_n,top_n_whole_rate,tokens_per_char_weighted,occurrences,distinct_chars';
const f = x => (x === null ? '' : x.toFixed(4));
fs.writeFileSync(path.join(docs, 'coverage.csv'), [head, ...rows.map(r =>
  [r.tokenizer, r.script, f(r.wholeAll), f(r.weighted), r.topN ?? '', f(r.topWhole), f(r.tokPerChar), r.occurrences, r.distinct].join(','))].join('\n') + '\n');
console.log(`wrote coverage.json and coverage.csv (${rows.length} rows)`);
