// Encode strings with docs/bpe.js, for check_hf.py.
// Usage: node encode_cli.cjs <name>   (reads a JSON array of strings on stdin, prints a JSON array of id arrays)
const fs = require('fs');
const path = require('path');
const BPE = require('../docs/bpe.js');

const name = process.argv[2];
const docs = path.join(__dirname, '..', 'docs');
const V = BPE.load(JSON.parse(fs.readFileSync(path.join(docs, `${name}.json`), 'utf8')));
if (V.kind === 'sp') V.setMerges(JSON.parse(fs.readFileSync(path.join(docs, `${name}.merges.json`), 'utf8')));
const tests = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(tests.map(t => V.encode(t))));
