/**
 * Number formatting, kept free of any dependency so that both the strings module (textes/fr.js)
 * and the formatters (logique/formats.js) can use it.
 */

/** 62068 -> "62 068" (narrow no-break space, as French typography wants). */
export function formaterNombre(n) {
  if (typeof n !== 'number' || !Number.isFinite(n)) return '';
  const s = String(Math.abs(Math.trunc(n)));
  let out = '';
  for (let i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 === 0) out += ' ';
    out += s[i];
  }
  return (n < 0 ? '−' : '') + out;
}
