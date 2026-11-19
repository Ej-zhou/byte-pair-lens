// Verifies that docs/bpe.js (the engine the page runs) matches the reference tiktoken encoders.
// Run from scripts/:  node check_encoder.mjs
// For the Hugging Face tokenizers (Llama 3.1, Qwen3, DeepSeek-V3, Gemma 3, Mistral) see check_hf.py.
import { encode as encCl } from 'gpt-tokenizer/encoding/cl100k_base';
import { encode as encO2 } from 'gpt-tokenizer/encoding/o200k_base';
import { encode as encR5 } from 'gpt-tokenizer/encoding/r50k_base';
import { readFileSync } from 'fs';
import { createRequire } from 'module';

const BPE = createRequire(import.meta.url)('../docs/bpe.js');

const tests = [
  '今天天气很好。The weather is nice today. 날씨가 좋다 — numéro 2024!',
  'def tokenize(text: str) -> list[int]:\n    return [ord(c) for c in text]',
  '😀🎉 ≥ 1234567',
  "龘齉爨靐 I'm here, we've GONE.   \n\n  x",
  'Większość programów używa UTF-8. Привет мир. مرحبا بالعالم. नमस्ते दुनिया.',
];

let fail = 0;
for (const [enc, ref] of [['r50k_base', encR5], ['cl100k_base', encCl], ['o200k_base', encO2]]) {
  const V = BPE.load(JSON.parse(readFileSync(`../docs/${enc}.json`, 'utf8')));
  let ok = 0;
  for (const t of tests) {
    if (V.encode(t).join(',') === ref(t).join(',')) ok++;
    else { fail++; console.log(enc, 'MISMATCH', JSON.stringify(t)); }
  }
  console.log(enc, `${ok}/${tests.length} match`);
}
process.exit(fail ? 1 : 0);
