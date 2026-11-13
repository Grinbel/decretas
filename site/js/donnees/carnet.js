/**
 * « Décrets déjà lus »: a checklist kept ONLY in this browser, so that a family can read the
 * decrees of a year over several evenings. Nothing else of the site is stored, and this list is
 * never sent anywhere: it lives in the browser's localStorage, under one key, and the page says
 * so next to the boxes, with a button that erases it.
 *
 * This is the only module of the site that touches browser storage (tests/js/ui-coquille.test.mjs
 * checks it). Every access is wrapped: in a private window, with storage blocked, or when the
 * quota is full, the checklist still works for the page that is open and says it will not be kept.
 *
 *   const carnet = creerCarnet();
 *   carnet.persistant            true when the list survives a reload
 *   carnet.estLu('FRAN_IR_000001/DEC001'), carnet.marquer(cle, true|false), carnet.lus() -> Map(cle -> ISO date)
 *   carnet.effacer(), carnet.abonner(fn) -> unsubscribe
 */

export const CLE_STOCKAGE = 'decretas.decrets-lus.v1';

/** Only keys of this shape are kept: "FRAN_IR_" + six digits, "/", a notice id. */
const CLE_RE = /^FRAN_IR_\d{6}\/[A-Za-z0-9_.-]{1,200}$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const MAXIMUM = 5000;

/** The browser's storage, or null when it cannot be used. */
export function stockageDuNavigateur() {
  try {
    const s = globalThis.localStorage;
    if (!s) return null;
    const probe = `${CLE_STOCKAGE}.essai`;
    s.setItem(probe, '1');
    s.removeItem(probe);
    return s;
  } catch (error) {
    // SecurityError (storage blocked), QuotaExceededError, or no window at all
    return null;
  }
}

function lire(stockage) {
  if (stockage === null) return new Map();
  let brut;
  try {
    brut = stockage.getItem(CLE_STOCKAGE);
  } catch (error) {
    return new Map();
  }
  if (typeof brut !== 'string') return new Map();
  let objet;
  try {
    objet = JSON.parse(brut);
  } catch (error) {
    if (error instanceof SyntaxError) return new Map();
    throw error;
  }
  const out = new Map();
  const lus = objet && typeof objet === 'object' && objet.v === 1 && objet.lus && typeof objet.lus === 'object' ? objet.lus : {};
  for (const [cle, date] of Object.entries(lus)) {
    if (out.size >= MAXIMUM) break;
    if (CLE_RE.test(cle)) out.set(cle, typeof date === 'string' && DATE_RE.test(date) ? date : null);
  }
  return out;
}

/**
 * @param {{stockage?: Storage|null, aujourdhui?: () => string}} [options]
 *        stockage: injected in tests; aujourdhui: ISO date of today (the date a box was ticked)
 */
export function creerCarnet({ stockage = stockageDuNavigateur(), aujourdhui = () => new Date().toISOString().slice(0, 10) } = {}) {
  let lus = lire(stockage);
  let persistant = stockage !== null;
  const abonnes = new Set();

  function ecrire() {
    if (stockage === null) return;
    try {
      if (lus.size === 0) stockage.removeItem(CLE_STOCKAGE);
      else stockage.setItem(CLE_STOCKAGE, JSON.stringify({ v: 1, lus: Object.fromEntries(lus) }));
    } catch (error) {
      // quota full, or storage withdrawn while the page was open: keep the list in memory
      persistant = false;
    }
  }

  const publier = () => {
    for (const fn of abonnes) fn();
  };

  return {
    get persistant() {
      return persistant;
    },
    estLu: (cle) => lus.has(cle),
    lus: () => new Map(lus),
    taille: () => lus.size,
    marquer(cle, lu) {
      if (!CLE_RE.test(cle)) return false;
      if (lu) {
        if (!lus.has(cle) && lus.size >= MAXIMUM) return false;
        lus.set(cle, aujourdhui());
      } else lus.delete(cle);
      ecrire();
      publier();
      return true;
    },
    effacer() {
      lus = new Map();
      ecrire();
      publier();
    },
    /** Read again (another tab of the same site may have changed the list). */
    relire() {
      lus = lire(stockage);
      publier();
    },
    abonner(fn) {
      abonnes.add(fn);
      return () => abonnes.delete(fn);
    },
  };
}
