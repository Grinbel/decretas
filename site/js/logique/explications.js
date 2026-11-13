/**
 * Why a notice matched, in words. The engine reports, for each term, the written word it was
 * recognised in, the level of the comparison and what was glued or detached
 * (docs/moteur-de-recherche.md § 13); this module turns that into sentences. No score exists
 * and none is invented here.
 */

import { T } from '../textes/index.js';

/**
 * @param {Object} t one entry of "termes" of a correspondence
 * @returns {{terme: string, ecrit: string|null, absent: boolean, approchant: boolean,
 *            identique: boolean, court: string, detail: string}}
 *   identique: written as typed (case, accents and spacing apart)
 *   court:  the short form shown on a card ("Belgacem ≈ Belkacem", "Chabane = Chabane")
 *   detail: the rule, in a sentence
 */
export function expliquerTerme(t) {
  const E = T.explications;
  if (t.absent) {
    return { terme: t.terme, ecrit: null, absent: true, approchant: false, identique: false, court: E.absentCourt(t.terme), detail: E.absent(t.terme) };
  }
  const viaVariante = t.variante !== undefined && t.variante !== t.terme;
  const cherche = viaVariante ? t.variante : t.terme;
  const parts = [];
  let approchant = false;
  if (t.arabe) {
    approchant = true;
    parts.push(E.arabe);
    if (t.voyellesLongues === true) parts.push(E.voyellesOui);
    else if (t.voyellesLongues === false) parts.push(E.voyellesNon);
  } else if (t.niveau === 'k2') {
    approchant = true;
    parts.push(E.k2);
  } else if (t.niveau === 'k1') {
    parts.push(E.k1);
  } else if (t.exact) {
    parts.push(E.exact);
  } else {
    parts.push(E.k0);
  }
  if (t.soudure === 'colle') parts.push(E.colle);
  else if (t.soudure === 'article-fondu') parts.push(E.articleFondu(t.prefixe));
  else if (t.soudure === 'prefixe-source') {
    approchant = true;
    parts.push(E.prefixeSource(t.prefixe));
  } else if (t.soudure === 'prefixe-saisie') {
    approchant = true;
    parts.push(E.prefixeSaisie(t.prefixe));
  }
  if (viaVariante) parts.push(E.variante(t.variante));
  const same = !approchant && t.exact === true;
  return {
    terme: t.terme,
    ecrit: t.ecrit,
    absent: false,
    approchant,
    identique: same,
    court: approchant ? E.courtApprochant(t.ecrit, cherche) : same ? E.courtExact(t.ecrit) : E.courtEgal(t.ecrit, cherche),
    detail: parts.join(E.separateur),
  };
}

/** Every term of a correspondence, in the order typed. */
export function expliquer(correspondance) {
  return (correspondance?.termes ?? []).map(expliquerTerme);
}

/** The engine's warnings, as sentences; "important" marks the ones to show prominently. */
export function avertissements(liste) {
  const A = T.avertissements;
  const out = [];
  for (const a of Array.isArray(liste) ? liste : []) {
    const make = A[a.code];
    if (typeof make !== 'function') continue;
    out.push({ code: a.code, texte: make(a.detail ?? ''), important: a.code === 'compose-de-particules' || a.code === 'aucun-terme' });
  }
  return out;
}
