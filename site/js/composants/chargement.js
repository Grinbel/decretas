/**
 * Loading status of the name index: a plain sentence, a real progress bar, and — when the
 * download fails — a clear message with a retry button. Bound to the data client
 * (donnees/client.js). Only changes of step are announced to screen readers; the percentage
 * moves silently.
 *
 *   const { element, detruire } = etatChargement(donnees, { discret: true });
 */

import { h, remplacer } from './dom.js';
import { T } from '../textes/index.js';

/**
 * @param {ReturnType<import('../donnees/client.js').creerClientDonnees>} donnees
 * @param {{discret?: boolean, sansErreur?: boolean}} [options] discret: say nothing once the
 *        index is ready; sansErreur: say nothing on a failure either, because the page shows
 *        the failure (and its retry button) itself — one message, one button
 */
export function etatChargement(donnees, { discret = false, sansErreur = false } = {}) {
  const phrase = h('p', { class: 'chargement__phrase', role: 'status', aria: { live: 'polite' } });
  const pourcent = h('span', { class: 'chargement__pourcent', aria: { hidden: 'true' } });
  const barre = h('progress', { class: 'chargement__barre', max: '100', aria: { label: T.chargement.barre } });
  const actions = h('div', { class: 'chargement__actions' });
  const element = h('div', { class: 'chargement', hidden: true }, phrase, h('div', { class: 'chargement__ligne' }, barre, pourcent), actions);
  let annonce = '';

  const dire = (text) => {
    if (text !== annonce) {
      annonce = text;
      phrase.textContent = text;
    }
  };

  function dessiner(etat) {
    element.dataset.phase = etat.phase;
    element.hidden = etat.phase === 'repos' || (etat.phase === 'pret' && discret) || (etat.phase === 'erreur' && sansErreur);
    barre.hidden = etat.phase !== 'chargement';
    pourcent.hidden = etat.phase !== 'chargement';
    remplacer(actions);
    if (etat.phase === 'chargement') {
      const p = etat.progression ?? {};
      if (p.etape === 'telechargement') {
        dire(T.chargement.telechargement);
        if (Number.isFinite(p.total) && p.total > 0) {
          const pct = Math.min(100, Math.round((p.recus / p.total) * 100));
          barre.value = pct;
          pourcent.textContent = T.chargement.pourcent(pct);
        } else {
          barre.removeAttribute('value'); // size unknown: an honest "busy" bar, not a fake number
          pourcent.textContent = '';
        }
      } else {
        dire(T.chargement.preparation);
        barre.value = 100;
        pourcent.textContent = '';
      }
    } else if (etat.phase === 'pret') {
      dire(T.chargement.pret(etat.resume?.index?.occurrences ?? 0));
    } else if (etat.phase === 'erreur' && !sansErreur) {
      const e = etat.erreur;
      dire(T.chargement.erreur(e?.code, e?.statut));
      actions.append(h('button', { type: 'button', class: 'bouton bouton--secondaire', on: { click: () => donnees.reessayer() } }, T.chargement.reessayer));
    }
  }

  const desabonner = donnees.abonner(dessiner);
  dessiner(donnees.etat());
  return { element, detruire: desabonner };
}
