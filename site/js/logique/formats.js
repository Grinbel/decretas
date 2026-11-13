/**
 * Formatters shared by the views: numbers, ISO dates, lists of years. Pure functions; the
 * words (month names, "à", "et") come from the strings module so that a translation can
 * replace them.
 */

import { T } from '../textes/index.js';

export { formaterNombre } from '../textes/nombres.js';

const ISO_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

/**
 * "1913-03-21" -> "21 mars 1913" ; "1913-01-01" -> "1er janvier 1913".
 * Anything that is not a full ISO date is returned as it is (never invented).
 * @param {string|null|undefined} iso
 * @returns {string}
 */
export function formaterDate(iso) {
  if (typeof iso !== 'string') return '';
  const m = ISO_RE.exec(iso);
  if (m === null) return iso;
  const month = Number(m[2]);
  const day = Number(m[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return iso;
  return T.formats.date(day, T.formats.mois[month - 1], Number(m[1]));
}

/** Year of an ISO date, or null. */
export function anneeDe(iso) {
  if (typeof iso !== 'string') return null;
  const m = /^(\d{4})/.exec(iso);
  return m === null ? null : Number(m[1]);
}

/**
 * Sorted, de-duplicated years -> ranges. [1883, 1884, 1885, 1899] -> [[1883, 1885], [1899, 1899]]
 * @param {Iterable<number>} annees
 * @returns {Array<[number, number]>}
 */
export function plagesAnnees(annees) {
  const sorted = [...new Set(annees)].filter((y) => Number.isInteger(y)).sort((a, b) => a - b);
  const out = [];
  for (const y of sorted) {
    const last = out[out.length - 1];
    if (last !== undefined && y === last[1] + 1) last[1] = y;
    else out.push([y, y]);
  }
  return out;
}

/** ["a", "b", "c"] -> "a, b et c" */
export function enumerer(items) {
  const list = items.filter((x) => typeof x === 'string' && x !== '');
  if (list.length <= 1) return list.join('');
  return `${list.slice(0, -1).join(T.formats.virgule)}${T.formats.et}${list[list.length - 1]}`;
}

/** [1883..1897, 1913..1927] -> "1883 à 1897 et 1913 à 1927" ; a two-year range reads "1883 et 1884". */
export function enoncerAnnees(annees) {
  const parts = [];
  for (const [de, a] of plagesAnnees(annees)) {
    if (de === a) parts.push(String(de));
    else if (a === de + 1) parts.push(String(de), String(a));
    else parts.push(T.formats.plage(de, a));
  }
  return enumerer(parts);
}

/** Compact form for a URL parameter: [1899, 1933, 1934, 1935] -> "1899,1933-1935" */
export function compacterAnnees(annees) {
  return plagesAnnees(annees).map(([de, a]) => (de === a ? String(de) : `${de}-${a}`)).join(',');
}

/** Inverse of compacterAnnees; unreadable parts are dropped. Bounded to a sane span. */
export function lireAnneesCompactes(text) {
  const out = [];
  for (const part of String(text ?? '').split(',')) {
    const m = /^(\d{4})(?:-(\d{4}))?$/.exec(part.trim());
    if (m === null) continue;
    const de = Number(m[1]);
    const a = m[2] === undefined ? de : Number(m[2]);
    if (a < de || a - de > 200) continue;
    for (let y = de; y <= a; y++) out.push(y);
  }
  return [...new Set(out)].sort((x, y) => x - y);
}

/**
 * Quarters of one year -> months, merging neighbours: [2, 3, 4] -> "avril à décembre".
 * @param {number[]} trimestres 1..4
 * @returns {string[]} one text per run of consecutive quarters
 */
export function enoncerTrimestres(trimestres) {
  const sorted = [...new Set(trimestres)].filter((q) => q >= 1 && q <= 4).sort((a, b) => a - b);
  const runs = [];
  for (const q of sorted) {
    const last = runs[runs.length - 1];
    if (last !== undefined && q === last[1] + 1) last[1] = q;
    else runs.push([q, q]);
  }
  return runs.map(([de, a]) => T.formats.plageMois(T.formats.mois[(de - 1) * 3], T.formats.mois[a * 3 - 1]));
}

/** Replace {name} placeholders of a content template; an unknown name is left visible. */
export function remplirGabarit(gabarit, variables) {
  return String(gabarit ?? '').replace(/\{([a-z_]+)\}/g, (whole, name) => {
    const v = variables?.[name];
    return v === undefined || v === null ? whole : String(v);
  });
}

/**
 * A long paragraph of the content files, cut after its first sentence so that the page can
 * set that sentence apart. The text itself is unchanged: joining the parts with a space gives
 * it back.
 * @param {string} texte
 * @returns {string[]} one or two parts
 */
export function enDeuxTemps(texte) {
  const m = /^(.+?[.!?])\s+(\S.*)$/s.exec(String(texte ?? ''));
  return m === null ? [String(texte ?? '')] : [m[1], m[2]];
}

/**
 * What a toggle shows. The engine gathers on one line the several written words that one
 * spelling stands for (a glued prefix: "Benfictif, Fictifben", one line, one count); in a
 * comma-separated preview that comma reads as two spellings, the first one without its count.
 * They are shown joined by a slash instead. Used by the toggles and the bilan;
 * pure, tested in tests/js/ui-variantes.test.mjs.
 * @param {{graphie: string, exclure?: string[]}} x one entry of "graphiesTrouvees[].graphies"
 * @returns {string}
 */
export function libelleGraphie(x) {
  if (!x || typeof x.graphie !== 'string') return '';
  return (x.exclure?.length ?? 0) > 1 ? x.graphie.split(/\s*,\s*/).filter(Boolean).join(' / ') : x.graphie;
}
