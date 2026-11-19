// Print byte-map stats for one tokenizer from docs/bytemap.js, for check_map.py.
// Usage: node map_cli.cjs <name>   -> JSON {block: {assigned, whole, tok, prefixRows, prefixable, wholeCps}}
const fs = require('fs');
const path = require('path');
const BPE = require('../docs/bpe.js');
const ByteMap = require('../docs/bytemap.js');

const name = process.argv[2];
const docs = path.join(__dirname, '..', 'docs');
const V = BPE.load(JSON.parse(fs.readFileSync(path.join(docs, `${name}.json`), 'utf8')));
if (V.kind === 'sp') V.setMerges(JSON.parse(fs.readFileSync(path.join(docs, `${name}.merges.json`), 'utf8')));
const out = {};
for (const blk of ByteMap.FEATURED) {
  const D = ByteMap.blockData(V, blk);
  const wholeCps = [];
  D.state.forEach((s, i) => { if (s === 1) wholeCps.push(((D.r0 + (i >> 6)) << 6) | (i & 63)); });
  out[blk.id] = { assigned: D.assigned, whole: D.whole, tok: D.tok, prefixRows: D.prefixRows, prefixable: D.prefixable, wholeCps };
}
const O = ByteMap.overviewData(V);
const keys = ByteMap.vocabKeys(V), enc = new TextEncoder();
const overviewWhole = [];
for (let cp = 0; cp < 0x110000; cp++) {
  if (cp >= 0xD800 && cp <= 0xDFFF) continue;
  const ch = String.fromCodePoint(cp);
  if (ByteMap.NONCHAR.test(ch)) continue;
  const b = enc.encode(ch);
  if (keys.has(BPE.key(b, 0, b.length))) overviewWhole.push(cp);
}
if (overviewWhole.length !== O.totW) throw new Error('overview total disagrees with its own per-group counts');
out._overview = { totA: O.totA, totW: O.totW, wholeCps: overviewWhole };
process.stdout.write(JSON.stringify(out));
