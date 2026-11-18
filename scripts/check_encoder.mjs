// Verifies that the in-browser BPE in docs/index.html matches the reference gpt-tokenizer output.
// Run from scripts/:  node check_encoder.mjs
import { encode as encCl } from 'gpt-tokenizer/encoding/cl100k_base';
import { encode as encO2 } from 'gpt-tokenizer/encoding/o200k_base';
import { encode as encR5 } from 'gpt-tokenizer/encoding/r50k_base';
import { readFileSync } from 'fs';

const html = readFileSync('../docs/index.html', 'utf8');
const js = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'));
const PAT = eval('(' + js.match(/const PAT=(\{[\s\S]*?\});\nconst TOKCOL/)[1] + ')');

const tests = [
  '今天天气很好。The weather is nice today. 날씨가 좋다 — numéro 2024!',
  'def tokenize(text: str) -> list[int]:\n    return [ord(c) for c in text]',
  '😀🎉 ≥ 1234567',
  "龘齉爨靐 I'm here, we've GONE.   \n\n  x",
  'Większość programów używa UTF-8. Привет мир. مرحبا بالعالم. नमस्ते दुनिया.',
];

let fail = 0;
for (const [enc, ref] of [['r50k_base', encR5], ['cl100k_base', encCl], ['o200k_base', encO2]]) {
  const j = JSON.parse(readFileSync(`../docs/${enc}.json`, 'utf8'));
  const bytes = j.tokens.map(s => Buffer.from(s, 'base64'));
  const key = (b, i, k) => b.subarray(i, k).toString('latin1');
  const ranks = new Map(); bytes.forEach((b, i) => ranks.set(key(b, 0, b.length), i));
  const bpe = b => { let p = []; for (let i = 0; i < b.length; i++) p.push([i, i + 1]); while (p.length > 1) { let best = -1, br = Infinity; for (let i = 0; i < p.length - 1; i++) { const r = ranks.get(key(b, p[i][0], p[i + 1][1])); if (r !== undefined && r < br) { br = r; best = i; } } if (best < 0) break; p.splice(best, 2, [p[best][0], p[best + 1][1]]); } return p.map(([a, c]) => ranks.get(key(b, a, c))); };
  const encode = s => { const ids = []; for (const m of s.matchAll(PAT[enc])) { const b = Buffer.from(m[0], 'utf8'); const d = ranks.get(key(b, 0, b.length)); if (d !== undefined) ids.push(d); else ids.push(...bpe(b)); } return ids; };
  let ok = 0;
  for (const t of tests) { const a = encode(t).join(','), b = ref(t).join(','); if (a === b) ok++; else { fail++; console.log(enc, 'MISMATCH', JSON.stringify(t)); } }
  console.log(enc, `${ok}/${tests.length} match`);
}
process.exit(fail ? 1 : 0);
