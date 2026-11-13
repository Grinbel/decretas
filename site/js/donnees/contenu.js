/**
 * The guidance content (site/contenu/*.json): fetched on demand, once, from the site itself.
 * These files are small and hold no personal data; the page reads them on the main thread.
 */

import { creerLiens } from '../logique/liens.js';
import { saufTechniques, typographierTout } from '../textes/typographie.js';

/** Fields that are identifiers or addresses, not sentences: copied as they are. */
const TECHNIQUES = new Set(['id', 'cle', 'schema', 'gabarit', 'exemple', 'hote', 'preuves', 'variables', 'repli', 'liens', 'lien', 'guides', 'voie', 'voies', 'voies_secondaires', 'types', 'suite', 'statut', 'origine', 'vers', 'depart', 'source_id', 'ecrans_communs', 'ecran', 'actes_possibles', 'natures', 'couvertures', 'volumes', 'cb', 'htid']);

const NOMS = Object.freeze(['a-propos', 'aiguillage', 'bilan', 'guides', 'liens', 'types-d-actes', 'vocabulaire']);

export class ContenuIndisponible extends Error {
  constructor(nom, options) {
    super(`Content file unavailable: ${nom}`, options);
    this.name = 'ContenuIndisponible';
    this.nom = nom;
  }
}

/**
 * @param {{base?: string, fetch?: typeof fetch}} [options]
 * @returns {{charger: (nom: string) => Promise<Object>, plusieurs: (...noms: string[]) => Promise<Object[]>, liens: () => Promise<ReturnType<typeof creerLiens>>}}
 */
export function creerContenu({ base = 'contenu/', fetch: fetchFile = (url) => fetch(url, { credentials: 'omit' }) } = {}) {
  const cache = new Map();
  let liens = null;

  function charger(nom) {
    if (!NOMS.includes(nom)) return Promise.reject(new ContenuIndisponible(nom));
    if (!cache.has(nom)) {
      const pending = (async () => {
        let response;
        try {
          response = await fetchFile(`${base}${nom}.json`);
        } catch (cause) {
          throw new ContenuIndisponible(nom, { cause });
        }
        if (!response.ok) throw new ContenuIndisponible(nom);
        try {
          return typographierTout(await response.json(), saufTechniques(TECHNIQUES));
        } catch (cause) {
          if (cause instanceof SyntaxError) throw new ContenuIndisponible(nom, { cause });
          throw cause;
        }
      })();
      // A failed download is not kept: the next call tries again.
      pending.catch(() => cache.delete(nom));
      cache.set(nom, pending);
    }
    return cache.get(nom);
  }

  return {
    charger,
    plusieurs: (...noms) => Promise.all(noms.map(charger)),
    /** The link table, ready to fill templates (logique/liens.js). */
    liens() {
      liens ??= charger('liens').then(creerLiens);
      liens.catch(() => {
        liens = null;
      });
      return liens;
    },
  };
}
