/**
 * « On m'a donné un numéro de décret » — what the FORM of what someone was given looks like.
 * Pure functions, no DOM, no network; tested in tests/js/ui-numero.test.mjs.
 *
 * This module never says whether a paper is genuine and never concludes anything about an
 * ancestor: it only recognises shapes that exist in these sources (a date, a file number
 * "0000 X 19", a call number "BB/34/…", a document or article number, a page, the name of an
 * official publication) and sets apart what looks like none of them.
 */

const MOIS = {
  janvier: 1, janv: 1, fevrier: 2, fevr: 2, fev: 2, mars: 3, avril: 4, avr: 4, mai: 5, juin: 6,
  juillet: 7, juil: 7, aout: 8, septembre: 9, sept: 9, octobre: 10, oct: 10, novembre: 11, nov: 11,
  decembre: 12, dec: 12,
};

const sansAccents = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '');

/** A real calendar date between 1800 and 1999, as ISO, or null. */
function dateIso(annee, mois, jour) {
  if (!(annee >= 1800 && annee <= 1999 && mois >= 1 && mois <= 12 && jour >= 1 && jour <= 31)) return null;
  const d = new Date(Date.UTC(annee, mois - 1, jour));
  if (d.getUTCMonth() !== mois - 1) return null;
  return `${String(annee).padStart(4, '0')}-${String(mois).padStart(2, '0')}-${String(jour).padStart(2, '0')}`;
}

/**
 * The recognisers, in order of priority. Each returns the matches of one form; a part of the
 * text claimed by an earlier form is not read again by a later one.
 */
const FORMES = [
  {
    code: 'inventaire',
    re: /\bFRAN_IR_\d{6}\b/gi,
    valeur: (m) => m[0].toUpperCase(),
  },
  {
    code: 'cote-bb34',
    re: /\bBB\s*[/ .-]\s*34\s*[/ .-]\s*(\d{1,5})\b/gi,
    valeur: (m) => `BB/34/${Number(m[1])}`,
  },
  {
    code: 'cote-bb11',
    re: /\bBB\s*[/ .-]\s*11\s*[/ .-]\s*(\d{1,6})\b/gi,
    valeur: (m) => `BB/11/${Number(m[1])}`,
  },
  {
    code: 'cote-autre',
    re: /\bBB\s*[/ .-]\s*\d{1,3}(?:\s*[/ .-]\s*\d{1,6})?\b/gi,
    valeur: (m) => m[0].replace(/\s+/g, ''),
  },
  {
    code: 'dossier',
    // "1234 X 85", "1234X85", "1234 x 1885" is not this form (two digits for the year)
    re: /\b(\d{1,6})\s*[xX]\s*(\d{2})\b(?![./-]?\d)/g,
    valeur: (m) => `${m[1]} X ${m[2]}`,
  },
  {
    code: 'date',
    re: /\b(1er|\d{1,2})\s*(?:er)?\s+([a-zA-ZÀ-ÿ]{3,9})\.?\s+(\d{4})\b/g,
    valeur: (m) => {
      const mois = MOIS[sansAccents(m[2]).toLowerCase()];
      const jour = m[1] === '1er' ? 1 : Number(m[1]);
      return mois ? dateIso(Number(m[3]), mois, jour) : null;
    },
  },
  {
    code: 'date',
    re: /\b(\d{4})-(\d{1,2})-(\d{1,2})\b/g,
    valeur: (m) => dateIso(Number(m[1]), Number(m[2]), Number(m[3])),
  },
  {
    code: 'date',
    re: /\b(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{4})\b/g,
    valeur: (m) => dateIso(Number(m[3]), Number(m[2]), Number(m[1])),
  },
  {
    code: 'document',
    re: /\bdoc(?:ument|\.)?\s*(?:n\s*[°ºo]\.?\s*)?(\d{1,5})\b/gi,
    valeur: (m) => `document ${Number(m[1])}`,
  },
  {
    code: 'page',
    re: /\b(?:p\.|pp\.|pages?)\s*(\d{1,5})\b/gi,
    valeur: (m) => Number(m[1]),
  },
  {
    code: 'article',
    // "N° 350"; never the first half of a compound number ("N° 262-1412" is one number)
    re: /(?:\b|^)n\s*[°º]\s*(\d{1,6})\b(?!\s*[-/]\s*\d)/gi,
    valeur: (m) => Number(m[1]),
  },
  {
    code: 'publication',
    re: /\b(?:bulletin\s+officiel|journal\s+officiel|bulletin\s+des\s+lois|BOGGA|JORF|JOA|J\.\s?O\.)/gi,
    valeur: (m) => m[0].replace(/\s+/g, ' '),
  },
  {
    // "JO" in capitals only: in lower case it is too often something else
    code: 'publication',
    re: /\bJO\b/g,
    valeur: (m) => m[0],
  },
  {
    code: 'annee',
    re: /(?<!\d\s*[-/.]\s*)\b(1[89]\d{2})\b(?![./-]?\d)/g,
    valeur: (m) => Number(m[1]),
  },
];

/** What remains: groups of digits (with the separators people put between them). */
const NOMBRE = /\d+(?:\s*[-/.\s]\s*\d+)*/g;

/**
 * @param {string} texte what the person typed, as it is on the paper
 * @returns {{
 *   vide: boolean,
 *   formes: Array<{code: string, texte: string, valeur: *, role?: 'publication'}>,   in the order of the text
 *   dates: string[],      the ISO dates that may be the date of the decree
 *   datesPublication: string[],  dates written right after the name of a publication
 *                         (« JO du 7 février 1927 »): the date of that issue, not of the decree
 *   elements: {date: boolean, publication: boolean, pageOuDatePublication: boolean},
 *   bilan: 'complete' | 'date-sans-publication' | 'publication-sans-date' | 'numero-seul' | 'autre' | 'vide' }}
 */
export function classerSaisie(texte) {
  const source = String(texte ?? '').slice(0, 400);
  if (source.trim() === '') return { vide: true, formes: [], dates: [], datesPublication: [], elements: { date: false, publication: false, pageOuDatePublication: false }, bilan: 'vide' };
  const pris = new Array(source.length).fill(false);
  const libre = (debut, fin) => {
    for (let i = debut; i < fin; i++) if (pris[i]) return false;
    return true;
  };
  const formes = [];
  for (const forme of FORMES) {
    forme.re.lastIndex = 0;
    for (const m of source.matchAll(forme.re)) {
      const debut = m.index;
      const fin = m.index + m[0].length;
      if (!libre(debut, fin)) continue;
      const valeur = forme.valeur(m);
      if (valeur === null || valeur === undefined) continue;
      for (let i = debut; i < fin; i++) pris[i] = true;
      formes.push({ code: forme.code, texte: m[0].trim(), valeur, debut, fin });
    }
  }
  for (const m of source.matchAll(NOMBRE)) {
    const debut = m.index;
    const fin = m.index + m[0].length;
    let a = debut;
    while (a < fin && pris[a]) a++;
    let b = fin;
    while (b > a && pris[b - 1]) b--;
    const morceau = source.slice(a, b).replace(/^[\s\-/.]+|[\s\-/.]+$/g, '');
    if (morceau === '' || !/\d/.test(morceau) || !libre(a, b)) continue;
    for (let i = a; i < b; i++) pris[i] = true;
    formes.push({ code: 'nombre-nu', texte: morceau, valeur: morceau, debut: a, fin: b });
  }
  formes.sort((x, y) => x.debut - y.debut);
  // « JO du 7 février 1927 », « Bulletin officiel, n° 12 du 3 mars 1903 »: that date is the issue's.
  formes.forEach((f, i) => {
    if (f.code !== 'date' || i === 0) return;
    const avant = formes[i - 1];
    const entre = source.slice(avant.fin, f.debut);
    if (avant.code === 'publication' && /^[\s,]*(?:du|des|de|en date du)?\s*$/i.test(entre)) f.role = 'publication';
    if (avant.code === 'article' && i > 1 && formes[i - 2].code === 'publication' && /^[\s,]*(?:du|des)\s*$/i.test(entre)) f.role = 'publication';
  });
  const dates = formes.filter((f) => f.code === 'date' && f.role !== 'publication').map((f) => f.valeur);
  const datesPublication = formes.filter((f) => f.code === 'date' && f.role === 'publication').map((f) => f.valeur);
  const elements = {
    date: dates.length > 0,
    publication: formes.some((f) => f.code === 'publication'),
    pageOuDatePublication: formes.some((f) => f.code === 'page') || datesPublication.length > 0 || dates.length > 1,
  };
  let bilan = 'autre';
  if (elements.date && elements.publication && elements.pageOuDatePublication) bilan = 'complete';
  else if (elements.date) bilan = 'date-sans-publication';
  else if (elements.publication && elements.pageOuDatePublication) bilan = 'publication-sans-date';
  else if (formes.length > 0 && formes.every((f) => f.code === 'nombre-nu' || f.code === 'article' || f.code === 'annee')) bilan = 'numero-seul';
  return {
    vide: false,
    formes: formes.map(({ code, texte: t, valeur, role }) => (role ? { code, texte: t, valeur, role } : { code, texte: t, valeur })),
    dates: [...new Set(dates)],
    datesPublication: [...new Set(datesPublication)],
    elements,
    bilan,
  };
}

/**
 * Where a date stands against the collections read by this site.
 * @param {string} iso
 * @param {{an: {de: number, a: number}, bulletin: {de: number, a: number}}} bornes from the data
 * @returns {{annee: number, dansAn: boolean, dansBulletin: boolean}}
 */
export function situerDate(iso, bornes) {
  const annee = Number(String(iso).slice(0, 4));
  const dans = (b) => Boolean(b) && annee >= b.de && annee <= b.a;
  return { annee, dansAn: dans(bornes?.an), dansBulletin: dans(bornes?.bulletin) };
}
