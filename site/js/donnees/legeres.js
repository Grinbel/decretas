/**
 * The small data files, for the pages that need decrees and coverage but no names: the decree
 * browser, the citation checker, « Comment marche la recherche », a guide filled for one decree.
 * About 130 kB compressed, fetched on the main thread from the site itself, once: these pages
 * never download the 3 MB name index (that stays in the worker, for the search).
 *
 *   const leger = creerDonneesLegeres();
 *   leger.charger() -> Promise<modele>   the model of donnees/modele.js, without the name files:
 *                                        decretsAn(), couverture(), publicationsDuJour(), decretBulletin()
 *
 * The model is the same code as in the worker, given empty person and entry files.
 */

import { creerModele } from './modele.js';
import { ErreurDonnees } from './client.js';

/** The files read here, relative to the site root. "cle" names them for the model. */
export const FICHIERS_LEGERS = Object.freeze([
  { cle: 'anMeta', url: 'data/an-meta.json' },
  { cle: 'anDecrets', url: 'data/an-decrets.json' },
  { cle: 'boggaMeta', url: 'data/bogga-meta.json' },
  { cle: 'boggaVolumes', url: 'data/bogga-volumes.json' },
  { cle: 'boggaDecrets', url: 'data/bogga-decrets.json' },
]);

const VIDE = Object.freeze({ champs: [], lignes: [] });

/**
 * @param {{fetch?: (url: string) => Promise<Response>}} [options]
 */
export function creerDonneesLegeres({ fetch: fetchFile = (url) => fetch(url, { credentials: 'omit' }) } = {}) {
  let attente = null;

  async function un(spec) {
    let response;
    try {
      response = await fetchFile(spec.url);
    } catch (cause) {
      throw new ErreurDonnees('chargement', { fichier: spec.url });
    }
    if (!response.ok) throw new ErreurDonnees('chargement', { fichier: spec.url, statut: response.status });
    try {
      return await response.json();
    } catch (cause) {
      if (cause instanceof SyntaxError) throw new ErreurDonnees('format', { fichier: spec.url });
      throw cause;
    }
  }

  function charger() {
    if (attente === null) {
      attente = Promise.all(FICHIERS_LEGERS.map(un)).then((contenus) => {
        const fichiers = Object.fromEntries(FICHIERS_LEGERS.map((spec, i) => [spec.cle, contenus[i]]));
        try {
          return creerModele({ ...fichiers, anPersonnes: VIDE, boggaEntrees: VIDE });
        } catch (cause) {
          if (cause instanceof TypeError) throw new ErreurDonnees('format', {});
          throw cause;
        }
      });
      // A failed download is not kept: the next call tries again.
      attente.catch(() => {
        attente = null;
      });
    }
    return attente;
  }

  return { charger };
}
