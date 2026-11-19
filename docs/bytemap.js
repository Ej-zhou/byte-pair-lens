/* Byte map data, shared by the page (global `ByteMap`) and scripts/check_map.py (via map_cli.cjs).
   Row = every UTF-8 byte of a character except the last; column = the last byte (80–BF).
   For multi-byte characters that is exactly cp>>6 (row) and cp&63 (column), for any length. */
(function (root) {
  'use strict';
  const BPE = root.BPE || require('./bpe.js');
  const utf8 = new TextEncoder();
  const strict = new TextDecoder('utf-8', { fatal: true });

  const BLOCKS = [
    { id: 'ascii',      group: '1 byte',  name: 'ASCII',                                   lo: 0x0000,  hi: 0x007F },
    { id: 'latin',      group: '2 bytes', name: 'Latin-1 Supplement + Latin Extended-A/B', lo: 0x0080,  hi: 0x024F },
    { id: 'greek',      group: '2 bytes', name: 'Greek',                                   lo: 0x0370,  hi: 0x03FF },
    { id: 'cyrillic',   group: '2 bytes', name: 'Cyrillic',                                lo: 0x0400,  hi: 0x04FF },
    { id: 'hebrew',     group: '2 bytes', name: 'Hebrew',                                  lo: 0x0590,  hi: 0x05FF },
    { id: 'arabic',     group: '2 bytes', name: 'Arabic',                                  lo: 0x0600,  hi: 0x06FF },
    { id: 'devanagari', group: '3 bytes', name: 'Devanagari',                              lo: 0x0900,  hi: 0x097F },
    { id: 'bengali',    group: '3 bytes', name: 'Bengali',                                 lo: 0x0980,  hi: 0x09FF },
    { id: 'thai',       group: '3 bytes', name: 'Thai',                                    lo: 0x0E00,  hi: 0x0E7F },
    { id: 'kana',       group: '3 bytes', name: 'Hiragana + Katakana',                     lo: 0x3040,  hi: 0x30FF },
    { id: 'hangul',     group: '3 bytes', name: 'Hangul syllables',                        lo: 0xAC00,  hi: 0xD7A3 },
    { id: 'han',        group: '3 bytes', name: 'CJK Unified Ideographs',                  lo: 0x4E00,  hi: 0x9FFF },
    { id: 'hanA',       group: '3 bytes', name: 'CJK Extension A',                         lo: 0x3400,  hi: 0x4DBF },
    { id: 'emoji',      group: '4 bytes', name: 'Emoji & pictographs',                     lo: 0x1F300, hi: 0x1FAFF },
    { id: 'hanB',       group: '4 bytes', name: 'CJK Extension B',                         lo: 0x20000, hi: 0x2A6DF },
  ];
  const BLOCK = Object.fromEntries(BLOCKS.map(b => [b.id, b]));
  const UNASSIGNED = /^[\p{Cn}\p{Cs}]$/u;

  // raw-byte keys of every token, for "is this byte string one token?"
  function vocabKeys(V) {
    if (!V.keySet) {
      V.keySet = new Set();
      for (const b of V.bytes) V.keySet.add(BPE.key(b, 0, b.length));
    }
    return V.keySet;
  }
  function rowPrefix(cp) {
    const b = utf8.encode(String.fromCodePoint(cp));
    return b.subarray(0, b.length - 1);
  }
  // is the latin1-keyed byte string k complete UTF-8 text (not a fragment)?
  function isTextToken(k) {
    try { strict.decode(Uint8Array.from(k, c => c.charCodeAt(0))); return true; } catch (e) { return false; }
  }

  // Per (tokenizer, block): whole-token flags, tokens per character and prefix-fragment rows. Cached on V.
  function blockData(V, blk) {
    V.blockCache = V.blockCache || {};
    if (V.blockCache[blk.id]) return V.blockCache[blk.id];
    const keys = vocabKeys(V);
    const r0 = blk.lo >> 6, rows = (blk.hi >> 6) - r0 + 1;
    const state = new Uint8Array(rows * 64); // 0 empty, 1 whole, 2 split
    const ntok = new Uint8Array(rows * 64);
    const fragRow = new Uint8Array(rows);
    let assigned = 0, whole = 0, tok = 0, prefixRows = 0, prefixable = 0;
    for (let r = 0; r < rows; r++) {
      const pre = rowPrefix((r0 + r) << 6);
      if (pre.length >= 2) {
        prefixable++;
        const k = BPE.key(pre, 0, pre.length);
        if (keys.has(k) && !isTextToken(k)) { fragRow[r] = 1; prefixRows++; }
      }
      for (let c = 0; c < 64; c++) {
        const cp = ((r0 + r) << 6) | c, i = r * 64 + c;
        if (cp < blk.lo || cp > blk.hi) continue;
        const ch = String.fromCodePoint(cp);
        if (UNASSIGNED.test(ch)) continue;
        assigned++;
        const b = utf8.encode(ch);
        const isWhole = keys.has(BPE.key(b, 0, b.length));
        const n = isWhole ? 1 : V.splitChar(ch).length;
        state[i] = isWhole ? 1 : 2;
        ntok[i] = Math.min(255, n);
        whole += isWhole;
        tok += n;
      }
    }
    return (V.blockCache[blk.id] = { r0, rows, state, ntok, fragRow, assigned, whole, tok, prefixRows, prefixable });
  }

  const api = { BLOCKS, BLOCK, vocabKeys, rowPrefix, isTextToken, blockData };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ByteMap = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
