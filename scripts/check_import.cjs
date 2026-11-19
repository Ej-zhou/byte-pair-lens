// Checks docs/hfimport.js (the in-browser "load your own tokenizer.json") against the Python build:
// converting each cached tokenizer.json in JS must give exactly docs/<name>.json (and .merges.json).
// Usage: node check_import.cjs   (after python3 build_hf_vocab.py has filled scripts/hf_cache/)
const fs = require('fs');
const path = require('path');
const HFImport = require('../docs/hfimport.js');

const docs = path.join(__dirname, '..', 'docs');
let fail = 0;
for (const name of ['llama3.1', 'qwen3', 'deepseek-v3', 'gemma3', 'mistral-v0.3']) {
  const j = JSON.parse(fs.readFileSync(path.join(__dirname, 'hf_cache', `${name}.tokenizer.json`), 'utf8'));
  const want = JSON.parse(fs.readFileSync(path.join(docs, `${name}.json`), 'utf8'));
  const { vocab, merges } = HFImport.convert(j, name, want.label);
  const bad = [];
  for (const k of Object.keys(want)) {
    if (k === 'source') continue;
    if (k === 'cat') { // categories may be numbered differently; compare names per token
      const diff = want.cat.filter((c, i) => want.cats[c] !== vocab.cats[vocab.cat[i]]).length;
      if (diff) bad.push(`cat: ${diff} tokens differ`);
      continue;
    }
    if (k === 'cats') { if ([...want.cats].sort().join() !== [...vocab.cats].sort().join()) bad.push('cats'); continue; }
    if (JSON.stringify(want[k]) !== JSON.stringify(vocab[k])) bad.push(k);
  }
  if (merges) {
    const wm = JSON.parse(fs.readFileSync(path.join(docs, `${name}.merges.json`), 'utf8'));
    if (JSON.stringify(wm) !== JSON.stringify(merges)) bad.push('merges');
  }
  fail += bad.length;
  console.log(`${name}: ${bad.length ? 'MISMATCH ' + bad.join(', ') : 'identical to the Python build'}`);
}
process.exit(fail ? 1 : 0);
