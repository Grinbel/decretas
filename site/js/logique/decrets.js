/**
 * The decree browser: the decrees of the Archives nationales that can only be read on their
 * images (no name typed), and those whose names are withheld here. Which ones to read, in which
 * order, and how many that makes. Pure functions over the decrees of the data layer
 * (donnees/modele.js#decretsAn); tested in tests/js/ui-decrets.test.mjs. No year and no count
 * is written here: they come from the data.
 */

/** States of a decree that this page lists (see docs/format-donnees-an.md). */
export const ETATS_A_LIRE = Object.freeze(['image', 'retenu-filae']);

/**
 * Reading groups, in the order of guide « an-annee-en-images », step b2 (site/contenu/guides.json):
 *   before 1931, the « naturalisations algériennes » (Algerians mixed with foreigners);
 *   from 1931, the admissions whose title names Algeria, then those without a territory,
 *   then the composite decrees; the decrees about foreigners of Algeria last; rejections apart.
 */
export const GROUPES = Object.freeze([
  'naturalisations-algeriennes',
  'admission-algerie',
  'admission-sans-territoire',
  'composites',
  'etrangers-algerie',
  'autres',
  'rejets',
]);

/** Year from which the titles say « admission aux droits de citoyen français » (guide b2, types T1). */
export const ANNEE_DES_TITRES_D_ADMISSION = 1931;

const NATURALISATIONS = new Set(['naturalisation', 'naturalisation+reintegration', 'reintegration']);

/** @param {{classe: string, famille: string, annee: number}} d */
export function groupeDeLecture(d) {
  if (d.classe === 'R') return 'rejets';
  if (d.classe === 'A3') return 'composites';
  if (d.classe === 'A2') return 'admission-sans-territoire';
  if (d.classe === 'A1') {
    if (d.famille === 'admission-citoyen' || d.famille === 'composite-avec-citoyen') return 'admission-algerie';
    if (d.annee < ANNEE_DES_TITRES_D_ADMISSION && NATURALISATIONS.has(d.famille)) return 'naturalisations-algeriennes';
    return 'etrangers-algerie';
  }
  return 'autres';
}

/** "document 21" -> 21 ; anything else -> Infinity (sorted last). */
function rangDocument(doc) {
  const m = /(\d+)/.exec(String(doc ?? ''));
  return m === null ? Number.POSITIVE_INFINITY : Number(m[1]);
}

/** The stable key of a decree (row ranks change at every rebuild; inventory + notice do not). */
export function cleDecret(d) {
  return `${d.inv}/${d.notice}`;
}

/** Year, then reading group, then date (undated last), then document number, then notice. */
export function trierPourLecture(decrets) {
  return [...decrets].sort((x, y) => (x.annee - y.annee)
    || (GROUPES.indexOf(groupeDeLecture(x)) - GROUPES.indexOf(groupeDeLecture(y)))
    || (x.date === y.date ? 0 : x.date === null ? 1 : y.date === null ? -1 : x.date < y.date ? -1 : 1)
    || (rangDocument(x.doc) - rangDocument(y.doc))
    || String(x.notice).localeCompare(String(y.notice)));
}

/** Years that hold at least one decree to read, sorted. */
export function anneesDisponibles(decrets) {
  return [...new Set(decrets.map((d) => d.annee))].filter(Number.isInteger).sort((a, b) => a - b);
}

/**
 * The window of years to show.
 * @param {{de?: number|null, a?: number|null, annees?: number[], naissance?: number|null, tolerance?: number|null}} demande
 *        annees: an explicit list (from the bilan); de/a: a range; naissance: born about,
 *        tolerance: the years around it the name search accepted (the window starts from the earliest)
 * @param {number[]} disponibles years that hold decrees to read
 * @param {number} ageMinimal legal minimum age for a decree (aiguillage.json)
 * @returns {{de: number, a: number, annees: number[], depuisNaissance: boolean}}
 */
export function fenetreDemandee({ de = null, a = null, annees = [], naissance = null, tolerance = null } = {}, disponibles, ageMinimal) {
  const min = disponibles[0];
  const max = disponibles[disponibles.length - 1];
  if (disponibles.length === 0) return { de: null, a: null, annees: [], depuisNaissance: false };
  let bas = Number.isInteger(de) ? de : null;
  let haut = Number.isInteger(a) ? a : null;
  let depuisNaissance = false;
  if (bas === null && haut === null && annees.length > 0) {
    bas = Math.min(...annees);
    haut = Math.max(...annees);
  }
  if (bas === null && Number.isInteger(naissance) && Number.isInteger(ageMinimal)) {
    bas = naissance - (Number.isInteger(tolerance) && tolerance > 0 && tolerance <= 100 ? tolerance : 0) + ageMinimal;
    depuisNaissance = true;
  }
  bas = Math.max(min, bas ?? min);
  haut = Math.min(max, haut ?? max);
  if (haut < bas) return { de: bas, a: haut, annees: [], depuisNaissance };
  const liste = annees.length > 0 && !(Number.isInteger(de) || Number.isInteger(a))
    ? disponibles.filter((y) => annees.includes(y) && y >= bas && y <= haut)
    : disponibles.filter((y) => y >= bas && y <= haut);
  return { de: bas, a: haut, annees: liste, depuisNaissance };
}

/**
 * @param {Object[]} decrets
 * @param {{annees: number[], groupes?: string[]|null}} filtre groupes null: every group
 */
export function filtrerDecrets(decrets, { annees, groupes = null }) {
  const ys = new Set(annees);
  const gs = groupes === null ? null : new Set(groupes);
  return trierPourLecture(decrets.filter((d) => ys.has(d.annee) && (gs === null || gs.has(groupeDeLecture(d)))));
}

/** {annee: {total, groupes: {groupe: n}}} for the decrees given. */
export function comptesParAnnee(decrets) {
  const out = new Map();
  for (const d of decrets) {
    if (!out.has(d.annee)) out.set(d.annee, { total: 0, groupes: {} });
    const c = out.get(d.annee);
    c.total += 1;
    const g = groupeDeLecture(d);
    c.groupes[g] = (c.groupes[g] ?? 0) + 1;
  }
  return out;
}

/** How many decrees per reading group (all years together). */
export function comptesParGroupe(decrets) {
  const out = Object.fromEntries(GROUPES.map((g) => [g, 0]));
  for (const d of decrets) out[groupeDeLecture(d)] += 1;
  return out;
}

/** "inv/notice" keys of the decrees given that the checklist marks as read. */
export function dejaLus(decrets, lus) {
  return decrets.filter((d) => lus.has(cleDecret(d))).length;
}

/** Reads "A1,R" from an address into reading groups; unknown names are dropped. */
export function lireGroupes(texte) {
  if (typeof texte !== 'string' || texte === '') return null;
  const out = texte.split(',').map((s) => s.trim()).filter((g) => GROUPES.includes(g));
  return out.length > 0 ? out : null;
}
