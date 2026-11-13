/**
 * Variant suggestions: instead of asking the user to guess how a clerk spelled a name, show
 * the spellings ACTUALLY PRESENT in the index that share the typed term's keys, with how
 * often each occurs, so that the user can untick the ones that are another name.
 *
 *   "Belkacem"  ->  même écriture (k1) : Belkacem (50), Belkassem (10)
 *                   squelette (k2)     : Belgacem (25), Belguecem (1)
 *                   avec un préfixe    : …
 *                   noms apparentés    : Boulkacem (2)        (never applied automatically)
 */

import { keysOfWord, keysOf, tokenize, detachedStems, canonicalParticle, KIND } from './normaliser.js';
import { hasArabic, analyzeArabic, longVowelsAgree } from './arabe.js';
import { writtenCount, displayForm } from './index.js';

/**
 * Names that are the same name in another language or form, which no spelling rule can
 * bring together. Hand-written, short on purpose, and only ever SUGGESTED: the user ticks them.
 */
export const RELATED_NAMES = Object.freeze([
  { noms: ['Mohamed', 'Mohand', "M'hamed", 'Mhand', 'Mohend', 'Mahmed'], raison: 'formes arabe et kabyle du même prénom' },
  { noms: ['Ahmed', 'Ahmet', 'Hamed'], raison: 'graphies voisines, parfois confondues par les commis' },
  { noms: ['Brahim', 'Ibrahim', 'Braham'], raison: 'même prénom, avec ou sans voyelle initiale' },
  { noms: ['Smaïl', 'Ismaïl', 'Smaïn'], raison: 'même prénom, avec ou sans voyelle initiale' },
  { noms: ['Driss', 'Idriss'], raison: 'même prénom, avec ou sans voyelle initiale' },
  { noms: ['Larbi', 'Arbi', 'Elarbi'], raison: "article « el » fondu dans le nom (L'Arbi)" },
  { noms: ['Lakhdar', 'Akhdar'], raison: "article « el » fondu dans le nom" },
  { noms: ['Lahcen', 'Hassen', 'Lhassen'], raison: "article « el » fondu dans le nom" },
  { noms: ['Embarek', "M'barek", 'Mebarek', 'Mobarek'], raison: 'même prénom, voyelle initiale ajoutée' },
  { noms: ['Belkacem', 'Boulkacem', 'Aboulkacem', 'Kacem'], raison: 'Belkacem est la contraction de Abou el Kacem' },
  { noms: ['Abdelkader', 'Kader', 'Kaddour', 'Kouider'], raison: 'formes courtes et diminutifs du même prénom' },
  { noms: ['Fatma', 'Fatima', 'Fatna', 'Fathma'], raison: 'formes du même prénom' },
  { noms: ['Aïssa', 'Issa'], raison: 'même prénom' },
  { noms: ['Saïd', 'Essaïd', 'Saïdi'], raison: 'avec article ou suffixe' },
]);

const relatedKeys = RELATED_NAMES.map((g) => g.noms.map((nom) => keysOfWord(nom)));

function entry(index, fid, niveau, extra = {}) {
  return { graphie: displayForm(index, fid), forme: index.formK0[fid], niveau, occurrences: writtenCount(index, fid), ...extra };
}

function wordCount(index, fid) {
  const w = index.postings[fid * 3 + KIND.WORD];
  return w ? w.length : 0;
}

const byCount = (a, b) => b.occurrences - a.occurrences || (a.forme < b.forme ? -1 : a.forme > b.forme ? 1 : 0);

/**
 * @param {import('./index.js').NameIndex} index
 * @param {string} typed one term as typed (Latin or Arabic script; leading particles ignored)
 * @param {{limite?: number}} [options] limite: entries per list (default 30)
 * @returns {{
 *   terme: string, ecriture: 'latin'|'arabe'|null,
 *   cles: {k0: string, k1: string, k2: string|null}|null, squelettes: string[]|null,
 *   exactes: Object[], memeEcriture: Object[], squelette: Object[], avecPrefixe: Object[],
 *   apparentees: Object[], tronque: boolean }}
 *   exactes        same folded spelling (k0)                      — applied by a search
 *   memeEcriture   other spellings with the same k1               — applied, class "correspondance"
 *   squelette      other spellings with the same k2               — applied, class "graphie-approchante"
 *   avecPrefixe    written words that contain the term after a glued prefix — applied, "graphie-approchante"
 *   apparentees    related names (RELATED_NAMES) present in the index — NOT applied; to add as variants
 *   Every entry: {graphie, forme, niveau, occurrences} ; "forme" is what to pass in "exclues".
 */
export function suggestVariants(index, typed, { limite = 30 } = {}) {
  const out = {
    terme: String(typed ?? ''), ecriture: null, cles: null, squelettes: null,
    exactes: [], memeEcriture: [], squelette: [], avecPrefixe: [], apparentees: [], tronque: false,
  };
  const seen = new Set();
  const usable = (fid) => !index.formParticle[fid] && !seen.has(fid) && writtenCount(index, fid) > 0;

  if (hasArabic(out.terme)) {
    const word = analyzeArabic(out.terme).filter((it) => it.type === 'mot').pop();
    if (!word) return out;
    out.ecriture = 'arabe';
    out.squelettes = word.candidats.map((c) => c.key);
    for (const cand of word.candidats) {
      for (const fid of index.byK2.get(cand.key) ?? []) {
        if (!usable(fid)) continue;
        seen.add(fid);
        out.squelette.push(entry(index, fid, 'k2', { voyellesLongues: longVowelsAgree(cand, index.formCle[fid]), lecture: cand.lecture }));
      }
    }
    const rank = (e) => (e.voyellesLongues === true ? 0 : e.voyellesLongues === null ? 1 : 2);
    out.squelette.sort((a, b) => rank(a) - rank(b) || byCount(a, b));
    out.tronque = out.squelette.length > limite;
    out.squelette.length = Math.min(out.squelette.length, limite);
    return out;
  }

  const tokens = tokenize(out.terme).filter((t) => canonicalParticle(t.k0) === null && t.k0.length > 1);
  if (tokens.length === 0) return out;
  const tok = tokens[tokens.length - 1];
  const k = keysOf(tok.cle);
  out.ecriture = 'latin';
  out.cles = { k0: k.k0, k1: k.k1, k2: k.k2ok ? k.k2 : null };

  for (const fid of index.byK0.get(k.k0) ?? []) {
    if (usable(fid)) { seen.add(fid); out.exactes.push(entry(index, fid, 'k0')); }
  }
  for (const fid of index.byK1.get(k.k1) ?? []) {
    if (usable(fid)) { seen.add(fid); out.memeEcriture.push(entry(index, fid, 'k1')); }
  }
  if (k.k2ok) {
    for (const fid of index.byK2.get(k.k2) ?? []) {
      if (usable(fid) && index.formK2ok[fid]) { seen.add(fid); out.squelette.push(entry(index, fid, 'k2')); }
    }
  }

  // Written words that reduce to the term once a glued prefix is detached (Ezzemri for Zemri),
  // and words the term reduces to (Chabane for Benchabane).
  const prefixed = new Set();
  for (const fid of index.byK1.get(k.k1) ?? []) {
    if (index.postings[fid * 3 + KIND.STEM] === undefined) continue;
    for (const src of index.stemSources.get(fid) ?? []) prefixed.add(src);
  }
  for (const s of detachedStems(tok.cle)) {
    for (const fid of index.byK1.get(keysOf(s.stem).k1) ?? []) {
      if (index.postings[fid * 3 + KIND.WORD] !== undefined) prefixed.add(fid);
    }
  }
  for (const fid of prefixed) {
    if (usable(fid) && wordCount(index, fid) > 0) {
      seen.add(fid);
      out.avecPrefixe.push(entry(index, fid, 'k1', { occurrences: wordCount(index, fid) }));
    }
  }

  relatedKeys.forEach((group, gi) => {
    const mine = group.some((m) => m.k1 === k.k1 || (k.k2ok && m.k2ok && m.k2 === k.k2));
    if (!mine) return;
    for (const m of group) {
      // Related names are fetched by their writing key only: their skeleton would bring in
      // the collisions of another name (Kacem -> Cosme).
      for (const fid of index.byK1.get(m.k1) ?? []) {
        if (usable(fid)) { seen.add(fid); out.apparentees.push(entry(index, fid, 'apparente', { raison: RELATED_NAMES[gi].raison })); }
      }
    }
  });

  for (const name of ['exactes', 'memeEcriture', 'squelette', 'avecPrefixe', 'apparentees']) {
    out[name].sort(byCount);
    if (out[name].length > limite) {
      out.tronque = true;
      out[name].length = limite;
    }
  }
  return out;
}
