/**
 * Waiting for the small data files (donnees/legeres.js): a plain sentence while they come, and,
 * when they cannot be had, a clear message with a retry button. The page draws itself once the
 * model is there.
 *
 *   attendreDonneesLegeres(zone, leger, (modele) => { … draw … }, { vivant: () => true })
 */

import { h, remplacer } from './dom.js';
import { avis } from './avis.js';
import { T } from '../textes/index.js';
import { formerHash } from '../routeur.js';

/**
 * @param {HTMLElement} zone   where the status, then the page, goes
 * @param {{charger: () => Promise<Object>}} leger
 * @param {(modele: Object) => void} dessiner
 * @param {{vivant?: () => boolean}} [options] vivant: false once the page has been left
 */
export function attendreDonneesLegeres(zone, leger, dessiner, { vivant = () => true } = {}) {
  const essayer = () => {
    remplacer(zone, h('p', { class: 'chargement chargement--leger', role: 'status', aria: { live: 'polite' } }, T.donneesLegeres.chargement));
    leger.charger().then((modele) => {
      if (!vivant()) return;
      remplacer(zone);
      dessiner(modele);
    }, (error) => {
      if (!vivant()) return;
      if (error?.name !== 'ErreurDonnees') throw error;
      remplacer(zone, avis({ ton: 'attention', role: 'alert' },
        T.donneesLegeres.erreur(error.statut),
        h('p', null, h('button', { type: 'button', class: 'bouton bouton--secondaire', on: { click: essayer } }, T.donneesLegeres.reessayer))));
    });
  };
  essayer();
}

/** A word of the page, linked to its definition in « Les mots de ce site ». */
export function mot(id, texte) {
  return h('a', { class: 'mot', href: formerHash('vocabulaire', [id]), title: T.vocabulaire.terme }, texte);
}
