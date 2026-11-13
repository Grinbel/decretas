/**
 * Shared helpers for the JavaScript tests. Every name below is INVENTED (family names such as
 * "Testaoui", "Exemplaoui", "Fictifi") or a very common given name: no real person from the
 * archives appears in this directory.
 */

import { buildIndex } from '../../site/js/recherche/index.js';
import { search } from '../../site/js/recherche/chercher.js';

/**
 * @param {Array<[string, number|null, string?]|string>} rows [name, birth year, group]
 * @param {Object} [options] passed to buildIndex
 */
export function indexOf(rows, options = { groupesOcr: ['bogga'] }) {
  const occurrences = rows.map((row, i) => {
    const [nom, annee = null, groupe = 'an'] = Array.isArray(row) ? row : [row];
    return { id: `t${i + 1}`, nom, anneeNaissance: annee, groupe };
  });
  return buildIndex(occurrences, options);
}

/** Names found for a query, per class: {correspondance: [...], 'graphie-approchante': [...], partielle: [...]} */
export function classes(index, query, options) {
  const { correspondances } = search(index, query, options);
  const out = { correspondance: [], 'graphie-approchante': [], partielle: [] };
  for (const r of correspondances) out[r.classe].push(r.nom);
  return out;
}

/** Class of the single-name index for a query, or null when the name is not returned. */
export function classOf(name, query, options) {
  const index = indexOf([name], options);
  const { correspondances } = search(index, query);
  return correspondances.length === 0 ? null : correspondances[0].classe;
}

/** Deterministic pseudo-random generator (mulberry32). */
export function prng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const GIVEN = ['Mohamed', 'Mohammed', 'Ahmed', 'Ali', 'Belkacem', 'Belgacem', 'Chabane', 'Chaabane', 'Saïd', 'Amar', 'Omar',
  'Slimane', 'Rabah', 'Larbi', 'Kaddour', 'Brahim', 'Youcef', 'Youssef', 'Mustapha', 'Mostefa', 'Hocine', 'Hassen', 'Tahar',
  'Lakhdar', 'Salah', 'Messaoud', 'Abdelkader', 'Abdallah', 'Fatma', 'Aïcha', 'Khedidja', 'Zohra', 'Yamina', 'Djilali', 'Miloud',
  'Marie', 'Jean', 'Joseph', 'Antoine', 'Louis', 'Pierre', 'Vincent', 'François', 'Salvador', 'Giovanni'];
const ONSETS = ['b', 'd', 'f', 'g', 'h', 'k', 'l', 'm', 'n', 'r', 's', 't', 'z', 'ch', 'dj', 'kh', 'gh', 'br', 'tr', 'sl', 'gu', 'bou', 'ben', 'bel'];
const VOWELS = ['a', 'e', 'i', 'o', 'ou', 'aï', 'é'];
const ENDINGS = ['aoui', 'i', 'ane', 'ine', 'oun', 'ar', 'el', 'ini', 'ez', 'at', 'ène', 'ouche', 'a'];

/**
 * A synthetic corpus of invented names in the real formats of the sources:
 * "Nom, Prénom ben Père", "NOM, Prénom", "Prénom ben Père ben Grand-père", "Nom (Prénom ben Père)".
 * @param {number} count
 * @param {number} [seed]
 */
export function syntheticOccurrences(count, seed = 20261111) {
  const rnd = prng(seed);
  const pick = (list) => list[Math.floor(rnd() * list.length)];
  const surname = () => {
    let s = '';
    const syllables = 2 + Math.floor(rnd() * 2);
    for (let k = 0; k < syllables; k++) s += pick(ONSETS) + pick(VOWELS);
    s += pick(ENDINGS);
    return s[0].toUpperCase() + s.slice(1);
  };
  const out = new Array(count);
  for (let i = 0; i < count; i++) {
    const shape = rnd();
    const fam = surname();
    let nom;
    if (shape < 0.35) nom = `${fam}, ${pick(GIVEN)} ben ${pick(GIVEN)}`;
    else if (shape < 0.6) nom = `${fam.toUpperCase()}, ${pick(GIVEN)} ${pick(GIVEN)}`;
    else if (shape < 0.75) nom = `${pick(GIVEN)} ben ${pick(GIVEN)} ben ${pick(GIVEN)}`;
    else if (shape < 0.9) nom = `${fam} (${pick(GIVEN)} ben ${pick(GIVEN)})`;
    else nom = `${fam} née ${surname()}, ${pick(GIVEN)} bent ${pick(GIVEN)}`;
    out[i] = {
      id: `s${i}`,
      nom,
      anneeNaissance: rnd() < 0.15 ? null : 1820 + Math.floor(rnd() * 100),
      groupe: rnd() < 0.8 ? 'an' : 'bogga',
    };
  }
  return out;
}
