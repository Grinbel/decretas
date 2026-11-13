/**
 * From the state of a search (what the user typed, the spellings unticked, the related names
 * ticked) to the query given to the engine, and from the address bar to that state.
 *
 * The typed text stays what the user typed. Unticking a spelling or ticking a related name is
 * expressed with the engine's own text syntax, added to the word that carries the term:
 *   "Belkacem ben Chabane"  + untick "belgacem" on term 0  ->  "Belkacem|-belgacem ben Chabane"
 * Keeping the text form (rather than rebuilding term objects) keeps the particle context:
 * "ben Chabane" is still also looked for as "Benchabane". The rewriting is checked: if the
 * rewritten text is not understood as the same terms, it is given up and said (fidele: false).
 */

import { parseQuery } from '../recherche/chercher.js';
import { tokenize } from '../recherche/normaliser.js';

// The engine's own splitting of a typed text (chercher.js#parseText).
const CHUNK_RE = /"([^"]*)"|«\s*([^»]*?)\s*»|([^\s,;()[\]"«»]+)/g;

function decouper(texte) {
  const chunks = [];
  const src = String(texte ?? '').replace(/\s*\|\s*/g, '|');
  CHUNK_RE.lastIndex = 0;
  let m;
  while ((m = CHUNK_RE.exec(src)) !== null) {
    const quoted = m[1] ?? m[2];
    chunks.push(quoted !== undefined ? { cite: true, contenu: quoted } : { cite: false, contenu: m[3] });
  }
  return chunks;
}

const ecrire = (chunk) => (chunk.cite ? `"${chunk.contenu}"` : chunk.contenu);
const assembler = (chunks) => chunks.map(ecrire).join(' ');

function libelles(texte) {
  return parseQuery({ texte }).termes.map((t) => t.libelle);
}

/** For each term, the rank of the chunk that completes it (-1 when not found). */
function proprietaires(chunks) {
  const owners = [];
  let previous = [];
  for (let k = 0; k < chunks.length; k++) {
    const now = libelles(assembler(chunks.slice(0, k + 1)));
    for (let i = 0; i < now.length; i++) if (now[i] !== previous[i]) owners[i] = k;
    previous = now;
  }
  return owners;
}

function signature(texte) {
  return JSON.stringify(parseQuery({ texte }).termes.map((t) => [
    t.exige,
    t.variantes[0].saisie,
    t.variantes[0].ecriture === 'latin' ? t.variantes[0].formes.map((f) => `${f.genre}:${f.k0}`) : t.variantes[0].candidats.map((c) => c.key),
  ]));
}

const propre = (list) => [...new Set((Array.isArray(list) ? list : []).map((x) => String(x).trim()).filter((x) => x !== '' && !/[|"«»\s]/.test(x)))];

/**
 * @param {Object} etat
 * @param {string} etat.texte           the name as typed
 * @param {number|null} [etat.annee]    approximate birth year
 * @param {number|null} [etat.tolerance]
 * @param {Object<number, string[]>} [etat.exclusions]  term rank -> spellings unticked ("exclure" of the bilan)
 * @param {Object<number, string[]>} [etat.ajouts]      term rank -> related names ticked
 * @returns {{entree: Object, fidele: boolean}} entree: what to give to search()
 */
export function preparerRequete({ texte, annee = null, tolerance = null, exclusions = {}, ajouts = {} }) {
  const base = String(texte ?? '');
  const entree = { texte: base };
  if (annee !== null && annee !== undefined && annee !== '') entree.annee = annee;
  if (tolerance !== null && tolerance !== undefined && tolerance !== '') entree.tolerance = tolerance;

  const wanted = new Map();
  for (const [key, list] of Object.entries(exclusions ?? {})) {
    const clean = propre(list);
    if (clean.length > 0) wanted.set(Number(key), { moins: clean, plus: [] });
  }
  for (const [key, list] of Object.entries(ajouts ?? {})) {
    const clean = propre(list);
    if (clean.length === 0) continue;
    const slot = wanted.get(Number(key)) ?? { moins: [], plus: [] };
    slot.plus = clean;
    wanted.set(Number(key), slot);
  }
  if (wanted.size === 0) return { entree, fidele: true };

  let chunks = decouper(base);
  let owners = proprietaires(chunks);
  // A chunk that carries several terms ("Jean-Pierre") is split into its words first.
  const counts = new Map();
  for (const k of owners) counts.set(k, (counts.get(k) ?? 0) + 1);
  if ([...counts.values()].some((c) => c > 1)) {
    chunks = chunks.flatMap((chunk, k) => ((counts.get(k) ?? 0) > 1 && !chunk.cite && !chunk.contenu.includes('|')
      ? tokenize(chunk.contenu).map((tok) => ({ cite: false, contenu: tok.raw }))
      : [chunk]));
    owners = proprietaires(chunks);
  }
  const reference = libelles(assembler(chunks));
  if (signature(assembler(chunks)) !== signature(base)) return { entree, fidele: false };

  const rewritten = chunks.map((chunk) => ({ ...chunk }));
  for (const [rank, { moins, plus }] of wanted) {
    const k = owners[rank];
    if (!Number.isInteger(rank) || k === undefined || rank >= reference.length) return { entree, fidele: false };
    if (owners.filter((o) => o === k).length !== 1) return { entree, fidele: false };
    rewritten[k].contenu += plus.map((p) => `|${p}`).join('') + moins.map((x) => `|-${x}`).join('');
  }
  const text = assembler(rewritten);
  // Same terms, in the same order, read from the same first variant: otherwise give up.
  const after = parseQuery({ texte: text }).termes;
  const before = parseQuery({ texte: assembler(chunks) }).termes;
  const same = after.length === before.length && after.every((t, i) => {
    const a = t.variantes[0];
    const b = before[i].variantes[0];
    if (t.exige !== before[i].exige || a.ecriture !== b.ecriture) return false;
    const keys = (v) => (v.ecriture === 'latin' ? v.formes.map((f) => `${f.genre}:${f.k0}`) : v.candidats.map((c) => c.key)).join(',');
    return keys(a) === keys(b);
  });
  if (!same) return { entree, fidele: false };
  return { entree: { ...entree, texte: text }, fidele: true };
}

// ---------------------------------------------------------------------------------------------
// Address bar <-> state   (#/recherche?q=…&ne=1876&tol=5&x=0.belgacem~1.chaban&v=0.Mohand)
// ---------------------------------------------------------------------------------------------

function lireListes(text) {
  const out = {};
  for (const part of String(text ?? '').split('~')) {
    const m = /^(\d{1,2})\.(.+)$/.exec(part);
    if (m === null) continue;
    (out[Number(m[1])] ??= []).push(m[2]);
  }
  return out;
}

function ecrireListes(map) {
  const parts = [];
  for (const key of Object.keys(map ?? {}).map(Number).sort((a, b) => a - b)) {
    for (const value of propre(map[key])) parts.push(`${key}.${value}`);
  }
  return parts.join('~');
}

/** Birth year as typed -> integer in a plausible span, or null. */
export function lireAnnee(text) {
  const m = /^\s*(\d{4})\s*$/.exec(String(text ?? ''));
  if (m === null) return null;
  const y = Number(m[1]);
  return y >= 1700 && y <= 1962 ? y : null;
}

/** Longest name the search reads; what an address carries beyond it is left out, and said so. */
export const LONGUEUR_MAX = 300;

/** A short form of the name for the title of the browser tab. */
export function titreCourt(texte, max = 80) {
  const s = String(texte ?? '').trim().slice(0, LONGUEUR_MAX);
  return s.length > max ? `${s.slice(0, max - 1).trimEnd()}…` : s;
}

/**
 * @param {Object<string, string>} params parameters of the route
 * @returns {{texte: string, coupe: boolean, annee: number|null, anneeSaisie: string, tolerance: number|null, exclusions: Object, ajouts: Object}}
 *          coupe: the name of the address was longer than LONGUEUR_MAX and was cut
 */
export function etatDepuisParametres(params) {
  const tol = /^\d{1,3}$/.test(params?.tol ?? '') ? Math.min(100, Number(params.tol)) : null;
  const brut = String(params?.q ?? '');
  return {
    texte: brut.slice(0, LONGUEUR_MAX),
    coupe: brut.length > LONGUEUR_MAX,
    annee: lireAnnee(params?.ne),
    anneeSaisie: String(params?.ne ?? '').slice(0, 12),
    tolerance: tol,
    exclusions: lireListes(params?.x),
    ajouts: lireListes(params?.v),
  };
}

/** Inverse of etatDepuisParametres; empty values are left out. */
export function parametresDepuisEtat(etat) {
  const out = {};
  if (etat.texte) out.q = etat.texte;
  const ne = etat.annee ?? etat.anneeSaisie;
  if (ne !== null && ne !== undefined && String(ne) !== '') out.ne = String(ne);
  if (etat.tolerance !== null && etat.tolerance !== undefined) out.tol = String(etat.tolerance);
  const x = ecrireListes(etat.exclusions);
  if (x !== '') out.x = x;
  const v = ecrireListes(etat.ajouts);
  if (v !== '') out.v = v;
  return out;
}

/** Tick or untick values in one of the two maps; returns a new map. */
export function basculer(map, rang, valeurs, actif) {
  const out = {};
  for (const [key, list] of Object.entries(map ?? {})) out[key] = [...list];
  const current = new Set(out[rang] ?? []);
  for (const v of valeurs) {
    if (actif) current.add(v);
    else current.delete(v);
  }
  if (current.size > 0) out[rang] = [...current];
  else delete out[rang];
  return out;
}
