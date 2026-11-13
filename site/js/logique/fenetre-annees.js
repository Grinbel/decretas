/**
 * "Que faire maintenant ?" — which years a person born about a given year could have been
 * admitted in, and how each of those years can be searched. Pure functions over the coverage
 * summary of the data layer (donnees/modele.js#couverture); no year is written here.
 */

/**
 * Years in which an admission by decree was legally possible for someone born about
 * "naissance": from the minimum age on — counted from the EARLIEST birth year the search
 * accepts (naissance − tolérance), since the name search itself keeps those notices — up to the
 * last year of the sources.
 * @param {number|null} naissance approximate birth year
 * @param {{ageMinimal: number, fin: number, tolerance?: number}} bornes ageMinimal from
 *        aiguillage.json, fin from the data, tolerance the one the search applied (0: exact)
 * @returns {{de: number, a: number}|null} null when nothing can be said (no year, or window empty)
 */
export function fenetreAdmission(naissance, { ageMinimal, fin, tolerance = 0 }) {
  if (!Number.isInteger(naissance) || !Number.isInteger(ageMinimal) || !Number.isInteger(fin)) return null;
  const de = naissance - toleranceSure(tolerance) + ageMinimal;
  return de > fin ? null : { de, a: fin };
}

const toleranceSure = (t) => (Number.isInteger(t) && t > 0 && t <= 100 ? t : 0);

/** Years whose names are typed at the Archives nationales but not published here. */
export const nomsAuxAnSeulement = (y) => y.lecture === 'noms-aux-an' || (y.lecture === 'image-en-partie' && y.algAvecNoms > 0);

const dans = (fenetre) => (y) => fenetre === null || (y >= fenetre.de && y <= fenetre.a);

/**
 * @param {Object} couverture     summary of the data layer: {an: {annees: [{annee, lecture}], dernierAnnee}, bogga: {annees: [{annee, etat…}]}}
 * @param {number|null} naissance approximate birth year, or null
 * @param {number} ageMinimal     legal minimum age for a decree
 * @param {number} [tolerance]    years around "naissance" that the search accepted
 * @returns {{
 *   naissance: number|null, anneeMin: number|null, fenetre: {de: number, a: number}|null,
 *   horsSources: boolean,
 *   imagesSeules: number[], nomsAuxAn: number[], lues: number[],
 *   bulletinLu: number[], bulletinAbsent: number[], avantSources: boolean, apresSources: boolean }}
 *   imagesSeules   years whose decrees must be read on the images (no name typed, or almost none)
 *   nomsAuxAn      years whose names exist at the Archives nationales but are not published here
 *   lues           years of the Archives nationales index that this search did read
 *   bulletinLu / bulletinAbsent   years of the printed Bulletin read by machine / missing
 */
export function conseilsPourAnnee(couverture, naissance, ageMinimal, tolerance = 0) {
  const anYears = couverture?.an?.annees ?? [];
  const boggaYears = couverture?.bogga?.annees ?? [];
  const premiere = Math.min(...boggaYears.map((y) => y.annee), ...anYears.map((y) => y.annee));
  const derniere = Math.max(...anYears.map((y) => y.annee), ...boggaYears.map((y) => y.annee));
  const connue = Number.isInteger(naissance);
  const tol = toleranceSure(tolerance);
  const anneeMin = connue ? naissance - tol + ageMinimal : null;
  const fenetre = connue ? fenetreAdmission(naissance, { ageMinimal, fin: derniere, tolerance: tol }) : null;
  const horsSources = connue && fenetre === null;
  const keep = horsSources ? () => false : dans(fenetre);
  const pick = (list, test) => list.filter((y) => test(y) && keep(y.annee)).map((y) => y.annee);
  return {
    naissance: connue ? naissance : null,
    tolerance: tol,
    anneeMin,
    fenetre,
    horsSources,
    imagesSeules: pick(anYears, (y) => y.lecture === 'image' || y.lecture === 'image-en-partie' || y.lecture === 'lue-en-partie'),
    // the same test as the sentence « Des noms saisis aux Archives nationales… » of the bilan
    nomsAuxAn: pick(anYears, nomsAuxAnSeulement),
    lues: pick(anYears, (y) => y.lecture === 'lue' || y.lecture === 'lue-en-partie'),
    bulletinLu: pick(boggaYears, (y) => y.lu === true && y.decrets > 0),
    bulletinAbsent: pick(boggaYears, (y) => y.lu !== true),
    avantSources: connue && Number.isFinite(premiere) && anneeMin < premiere,
    apresSources: connue && Number.isFinite(derniere) && anneeMin > derniere,
  };
}
