/**
 * Parameters of a guide page (#/guides/<id>?inventaire=…&notice=…). A result card or the decree
 * browser opens a guide filled with ITS decree, so that the links of the steps point to that
 * decree's notice. Pure functions; tested in tests/js/ui-parametres-guide.test.mjs.
 *
 * The address can be typed or forwarded by anyone: only identifiers of a known shape are kept,
 * and the page never shows a date or a call number read from the address as a fact — it shows
 * the decree it finds in the data, or says that it found none.
 */

/** Accepted keys and the shape of their value. */
const FORMES = {
  inventaire: /^FRAN_IR_\d{6}$/,
  notice: /^[A-Za-z0-9_.-]{1,200}$/,
  annee: /^\d{4}$/,
  feuillet: /^\d{1,5}$/,
  page: /^\d{1,5}$/,
  date: /^\d{4}-\d{2}-\d{2}$/,
  cote: /^BB\/\d{1,3}\/\d{1,6}$/,
  document: /^document \d{1,5}$/,
  cb: /^cb[0-9a-z]{6,20}$/,
  ark: /^[0-9a-z]{6,40}$/,
  vue: /^\d{1,5}$/,
};

export const CLES_GUIDE = Object.freeze(Object.keys(FORMES));

/**
 * @param {Object<string, string>} params the parameters of the route
 * @returns {Object<string, string>} the accepted ones only
 */
export function lireParametresGuide(params) {
  const out = {};
  for (const [cle, forme] of Object.entries(FORMES)) {
    const v = params?.[cle];
    if (typeof v === 'string' && forme.test(v.trim())) out[cle] = v.trim();
  }
  return out;
}

/** True when the parameters designate one decree of the Archives nationales. */
export function designeUnDecretAn(p) {
  return typeof p.inventaire === 'string' && typeof p.notice === 'string';
}

/** True when the parameters designate one leaf of a Bulletin volume. */
export function designeUnePageBulletin(p) {
  return typeof p.annee === 'string' && typeof p.feuillet === 'string';
}

/**
 * Values for the link templates of liens.json, from the accepted parameters: {date} of the
 * templates is AAAAMMJJ, {annee}/{mois}/{jour} come from the date when it is given.
 */
export function variablesDeLiens(p) {
  const out = {};
  for (const cle of ['inventaire', 'notice', 'annee', 'feuillet', 'cb', 'ark', 'vue']) if (p[cle] !== undefined) out[cle] = p[cle];
  if (p.date) {
    const [a, m, j] = p.date.split('-');
    out.date = `${a}${m}${j}`;
    out.annee ??= a;
    out.mois = m;
    out.jour = j;
  }
  return out;
}

/** Parameters of the guide for a decree of the Archives nationales (from the data layer). */
export function parametresPourDecretAn(decret) {
  if (!decret) return {};
  return {
    inventaire: decret.inv ?? null,
    notice: decret.notice ?? null,
    annee: Number.isInteger(decret.annee) ? decret.annee : null,
    date: typeof decret.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(decret.date) ? decret.date : null,
    cote: typeof decret.cote === 'string' && FORMES.cote.test(decret.cote) ? decret.cote : null,
    document: typeof decret.doc === 'string' && FORMES.document.test(decret.doc) ? decret.doc : null,
  };
}

/** Parameters of the Bulletin guide for one entry (from the data layer). */
export function parametresPourPageBulletin(fiche) {
  if (!fiche?.volume || !Number.isInteger(fiche.feuille)) return {};
  return { annee: fiche.volume.annee, feuillet: fiche.feuille, page: Number.isInteger(fiche.page) ? fiche.page : null };
}
