/* Convert a Hugging Face tokenizer.json into the site's vocab format, in the browser.
   A JavaScript port of scripts/build_hf_vocab.py + build_vocab.classify; scripts/check_import.cjs
   checks that both give identical output for every tokenizer we ship. Global `HFImport`, or require().
   Supports BPE models: byte-level (GPT-2 alphabet) and SentencePiece-style with byte fallback. */
(function (root) {
  'use strict';
  const utf8 = new TextEncoder();
  const strict = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }) // ignoreBOM: keep a leading U+FEFF, some tokens start with one;

  // GPT-2's bytes_to_unicode, inverted: char -> byte
  const BYTE_OF = (() => {
    const bs = [];
    for (let b = 33; b <= 126; b++) bs.push(b);
    for (let b = 161; b <= 172; b++) bs.push(b);
    for (let b = 174; b <= 255; b++) bs.push(b);
    const cs = bs.slice();
    let n = 0;
    for (let b = 0; b < 256; b++) if (!bs.includes(b)) { bs.push(b); cs.push(256 + n); n++; }
    const m = new Map();
    bs.forEach((b, i) => m.set(String.fromCharCode(cs[i]), b));
    return m;
  })();
  // the regex tiktoken/GPT-2 use when ByteLevel splits by itself (use_regex: true)
  const GPT2_RE = String.raw`'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+`;

  function jsRegex(rx) { // (?i:...) -> explicit [aA] classes, so older browsers work
    return rx.replace(/\(\?i:([^()]*)\)/g, (_, body) => '(?:' + body.replace(/[A-Za-z]/g, c => `[${c.toLowerCase()}${c.toUpperCase()}]`) + ')');
  }

  // --- category, identical to build_vocab.classify ---
  // Python's str.isspace() set (written as escapes: U+2028/2029 would end the line)
  const PY_SPACE = new RegExp('[\\t\\n\\x0b\\x0c\\r\\x1c-\\x1f \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000]');
  function pyStrip(s) {
    const a = Array.from(s);
    let i = 0, j = a.length;
    while (i < j && PY_SPACE.test(a[i])) i++;
    while (j > i && PY_SPACE.test(a[j - 1])) j--;
    return a.slice(i, j);
  }
  function classify(b) {
    let s;
    try { s = strict.decode(b); } catch (e) { return 'partial-UTF-8 / byte fragment'; }
    if (b.length === 1 && b[0] < 128) return 'single ASCII byte';
    const chars = pyStrip(s);
    if (!chars.length) return 'whitespace only';
    const counts = new Map();
    const add = k => counts.set(k, (counts.get(k) || 0) + 1);
    for (const ch of chars) {
      const o = ch.codePointAt(0);
      if (o < 128) add(/[A-Za-z]/.test(ch) ? 'ASCII' : /[0-9]/.test(ch) ? 'ASCII-digit' : 'ASCII-punct');
      else if ((o >= 0x4E00 && o <= 0x9FFF) || (o >= 0x3400 && o <= 0x4DBF) || (o >= 0x20000 && o <= 0x3134F) || (o >= 0xF900 && o <= 0xFAFF)) add('CJK Han');
      else if ((o >= 0x3040 && o <= 0x30FF) || (o >= 0x31F0 && o <= 0x31FF)) add('Japanese kana');
      else if ((o >= 0xAC00 && o <= 0xD7AF) || (o >= 0x1100 && o <= 0x11FF) || (o >= 0x3130 && o <= 0x318F)) add('Korean hangul');
      else if (o >= 0x0400 && o <= 0x04FF) add('Cyrillic');
      else if ((o >= 0x0600 && o <= 0x06FF) || (o >= 0x0750 && o <= 0x077F)) add('Arabic');
      else if (o >= 0x0590 && o <= 0x05FF) add('Hebrew');
      else if (o >= 0x0370 && o <= 0x03FF) add('Greek');
      else if (o >= 0x0900 && o <= 0x0DFF) add('Indic');
      else if (o >= 0x0E00 && o <= 0x0E7F) add('Thai');
      else if (o >= 0x00C0 && o <= 0x024F) add('Latin extended (accented)');
      else if ((o >= 0x3000 && o <= 0x303F) || (o >= 0xFF00 && o <= 0xFFEF)) add('CJK punctuation / fullwidth');
      else add(/\p{S}/u.test(ch) ? 'emoji/symbol' : 'other non-ASCII');
    }
    let best = null, bestN = 0;
    for (const [k, n] of counts) if (!k.startsWith('ASCII') && n > bestN) { best = k; bestN = n; }
    if (best) return best;
    if (counts.get('ASCII')) return 'ASCII word/subword';
    if (counts.get('ASCII-digit')) return 'ASCII digits';
    return 'ASCII punctuation/mixed';
  }

  function unsupported(msg) { throw new Error('Unsupported tokenizer.json: ' + msg); }

  // returns {vocab, merges|null}: vocab is the JSON BPE.load takes; merges the flat id list (sp only)
  function convert(j, name, label) {
    const m = j.model || {};
    if ((m.type || 'BPE') !== 'BPE') unsupported(`model type ${m.type} (only BPE is supported)`);
    if (!m.vocab || !m.merges) unsupported('no BPE vocab/merges');
    const vocab = m.vocab, added = j.added_tokens || [];
    let size = 0;
    for (const id of Object.values(vocab)) size = Math.max(size, id + 1);
    for (const a of added) size = Math.max(size, a.id + 1);
    const piece = new Array(size);
    for (const [p, i] of Object.entries(vocab)) piece[i] = p;
    const addedIds = new Set(), specialIds = new Set();
    for (const a of added) {
      if (a.lstrip || a.rstrip || a.single_word) unsupported(`added token ${a.content} uses lstrip/rstrip/single_word`);
      piece[a.id] = a.content; addedIds.add(a.id); if (a.special) specialIds.add(a.id);
    }
    for (let i = 0; i < size; i++) if (piece[i] === undefined) unsupported(`token id ${i} is missing`);

    // pre-tokeniser -> list of split regexes + flags
    const preTok = j.pre_tokenizer;
    const items = preTok && preTok.type === 'Sequence' ? preTok.pretokenizers : [preTok];
    const splits = [];
    let byteLevel = null, metaspace = null, splitString = null;
    for (const p of items) {
      if (!p) continue;
      if (p.type === 'Split') {
        if ('Regex' in p.pattern) {
          if (p.behavior !== 'Isolated' || p.invert) unsupported(`Split behavior ${p.behavior}${p.invert ? ' (inverted)' : ''}`);
          splits.push(jsRegex(p.pattern.Regex));
        } else splitString = p.pattern.String;
      } else if (p.type === 'ByteLevel') byteLevel = p;
      else if (p.type === 'Metaspace') metaspace = p;
      else unsupported(`pre_tokenizer ${p.type}`);
    }
    const norm = j.normalizer;
    const pre = { splits };
    if (norm && norm.type === 'NFC') pre.normalizer = 'NFC';
    const sp = !!m.byte_fallback;
    let out, merges = null;
    let raw;
    if (!sp) {
      if (!byteLevel) unsupported('BPE without ByteLevel or byte fallback');
      if (byteLevel.use_regex !== false) { // ByteLevel does the splitting itself (GPT-2 style)
        if (splits.length) unsupported('ByteLevel with its own regex after a Split');
        splits.push(GPT2_RE);
      }
      if (norm && !(norm.type === 'NFC' || (norm.type === 'Sequence' && !norm.normalizers.length))) unsupported(`normalizer ${norm.type}`);
      raw = piece.map((p, i) => {
        if (addedIds.has(i)) return utf8.encode(p);
        const b = new Uint8Array(p.length);
        for (let k = 0; k < p.length; k++) { const x = BYTE_OF.get(p[k]); if (x === undefined) unsupported(`token ${i} is not in the byte-level alphabet`); b[k] = x; }
        return b;
      });
      // merge rank must equal token id order (true for every byte-level tokenizer we have seen)
      let last = -1;
      for (const mg of m.merges) {
        const [a, b] = typeof mg === 'string' ? mg.split(' ') : mg;
        const id = vocab[a + b];
        if (id === undefined || id < last) unsupported('merges are not in token-id order');
        last = id;
      }
      pre.ignoreMerges = !!m.ignore_merges;
      out = { kind: 'bytelevel', tokens: raw.map(b => { let s = ''; for (const x of b) s += String.fromCharCode(x); return btoa(s); }) };
    } else {
      if (norm) {
        if (!(norm.type === 'Replace' && norm.pattern && norm.pattern.String === ' ' && norm.content === '▁')) unsupported(`normalizer ${norm.type}`);
        if (splitString !== null && splitString !== ' ') unsupported(`Split on "${splitString}"`);
        pre.replaceSpace = true;
      }
      if (metaspace) {
        if (metaspace.replacement !== '▁' || metaspace.prepend_scheme !== 'first' || metaspace.split) unsupported('Metaspace settings');
        pre.replaceSpace = true;
        pre.prepend = 'first';
      }
      raw = piece.map(p => (/^<0x[0-9A-F]{2}>$/.test(p) ? new Uint8Array([parseInt(p.slice(3, 5), 16)]) : utf8.encode(p.replace(/▁/g, ' '))));
      merges = [];
      for (const mg of m.merges) {
        const [a, b] = typeof mg === 'string' ? [mg.slice(0, mg.indexOf(' ')), mg.slice(mg.indexOf(' ') + 1)] : mg;
        merges.push(vocab[a], vocab[b]);
      }
      out = { kind: 'sp', pieces: piece };
    }
    const cats = [], idx = new Map(), cat = new Array(size);
    raw.forEach((b, i) => {
      const c = addedIds.has(i) || specialIds.has(i) ? 'special / added token' : classify(b);
      if (!idx.has(c)) { idx.set(c, cats.length); cats.push(c); }
      cat[i] = idx.get(c);
    });
    return {
      vocab: { name, label: label || name, ...out, pre, cats, cat, added: added.map(a => [a.content, a.id]) },
      merges,
    };
  }

  const api = { convert, classify };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.HFImport = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
