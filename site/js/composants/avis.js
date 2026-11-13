/**
 * "Notice" component: a boxed message. Tones: 'info' (a fact worth reading), 'attention'
 * (something that changes what the result means), 'neutre' (a quiet reminder).
 *
 *   avis({ ton: 'attention', titre: 'Deux particules se suivent' }, 'Texte…', node)
 */

import { h, icone } from './dom.js';
import { T } from '../textes/index.js';
import { noteDeVerification } from '../logique/verification.js';

const ICONES = { info: 'info', attention: 'attention', neutre: null };

/**
 * @param {{ton?: 'info'|'attention'|'neutre', titre?: string, role?: string, classe?: string}} options
 * @param {...(Node|string|Array|null)} contenu
 */
export function avis({ ton = 'info', titre, role, classe } = {}, ...contenu) {
  const nom = ICONES[ton];
  return h('div', { class: `avis avis--${ton}${classe ? ` ${classe}` : ''}`, role: role ?? null },
    nom ? icone(nom) : null,
    h('div', { class: 'avis__corps' },
      titre ? h('p', { class: 'avis__titre' }, titre) : null,
      contenu.map((c) => (typeof c === 'string' ? h('p', null, c) : c))));
}

/**
 * The discreet « À confirmer » line of a statement of the content files that is not verified
 * (logique/verification.js); null for a verified one. Same look as in the guides.
 * @param {{etat?: string, note?: string}|null|undefined} verification
 * @returns {HTMLElement|null}
 */
export function aConfirmer(verification) {
  const note = noteDeVerification(verification);
  return note === null ? null : h('p', { class: 'a-confirmer' }, h('span', { class: 'a-confirmer__etiquette' }, T.guide.aConfirmer), ' ', note);
}
