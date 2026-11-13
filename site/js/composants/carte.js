/**
 * "Card" component: one self-standing item of a list (a notice found, a type of act…).
 *
 *   carte({ titre: node|string, niveau: 3, surtitre?: string, classe?: string }, ...corps)
 *
 * The title is a real heading (h2-h4) so that screen-reader users can jump from card to card.
 * Cards are never nested.
 */

import { h } from './dom.js';

/**
 * @param {{titre: Node|string, niveau?: 2|3|4, classe?: string, id?: string, attributs?: Object}} options
 * @param {...(Node|string|Array|null)} corps
 * @returns {HTMLElement}
 */
export function carte({ titre, niveau = 3, classe, id, attributs } = {}, ...corps) {
  const level = Math.min(4, Math.max(2, niveau));
  return h('article', { class: `carte${classe ? ` ${classe}` : ''}`, id: id ?? null, ...(attributs ?? {}) },
    h(`h${level}`, { class: 'carte__titre' }, titre),
    corps);
}

/** A definition list from [label, value] pairs; pairs without a value are left out. */
export function champs(paires, { classe } = {}) {
  const rows = paires.filter((p) => Array.isArray(p) && p[1] !== null && p[1] !== undefined && p[1] !== '' && p[1] !== false);
  if (rows.length === 0) return null;
  return h('dl', { class: `champs${classe ? ` ${classe}` : ''}` },
    rows.map(([label, value]) => h('div', { class: 'champs__ligne' }, h('dt', null, label), h('dd', null, value))));
}
