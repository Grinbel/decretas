/**
 * A page that could not draw itself because a file of the site did not come: one title that
 * says so, one message, one « Réessayer » button that draws the page again (the content cache
 * forgets a failed download, so the retry asks for it again).
 *
 *   echecDePage(zone, { T, erreur, remonter, finDeRendu })
 */

import { h, remplacer } from './dom.js';
import { avis } from './avis.js';

/**
 * @param {HTMLElement} zone
 * @param {{T: Object, erreur?: Error, remonter: () => void, finDeRendu?: (cible: Element) => void}} options
 */
export function echecDePage(zone, { T, erreur = null, remonter, finDeRendu }) {
  const titre = h('h1', null, T.erreurs.titrePage);
  remplacer(zone, titre,
    avis({ ton: 'attention', role: 'alert' }, erreur?.name === 'ErreurDonnees' ? T.erreurs.donnees : T.erreurs.contenu),
    h('p', null, h('button', { type: 'button', class: 'bouton bouton--secondaire', on: { click: () => remonter() } }, T.chargement.reessayer)));
  finDeRendu?.(titre);
}
