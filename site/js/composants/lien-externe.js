/**
 * "External link" component. Takes a link id of site/contenu/liens.json and the parameters of
 * its template; never an address written by hand. It shows where the link goes (the host name,
 * in clear), opens it in a new tab without passing the referrer, and — when the link has never
 * been seen working — the honest sentence of the content files, with the fallback link.
 *
 *   lienExterne(liens, 'an-notice', { inventaire: 'FRAN_IR_000000', notice: 'XY000001' })
 *   listeDeLiens(liens, ['an-notice', 'an-inventaire'], params)
 *   lienParticulier(liens, 'http://…', 'Images du décret')   // address copied from a data file
 *
 * A link whose "proposer" is false is never drawn. A link whose variables cannot be filled is
 * drawn as plain text, saying so. An address never reaches href unless logique/liens.js built
 * it from the table (https, on the host the table announces).
 */

import { h, icone } from './dom.js';
import { T } from '../textes/index.js';

function ancre(resolu, libelle) {
  const site = T.lien.sites[resolu.hote];
  return [
    h('a', { class: 'lien-externe__a', href: resolu.url, target: '_blank', rel: 'noopener noreferrer' },
      h('span', { class: 'lien-externe__libelle' }, libelle || resolu.libelle),
      icone('externe'),
      h('span', { class: 'sr' }, T.lien.nouvelOnglet)),
    h('span', { class: 'lien-externe__hote' }, site ? T.lien.ouvreSurSite(site) : T.lien.ouvreSur, ' ', h('span', { class: 'lien-externe__domaine' }, resolu.hote)),
  ];
}

/**
 * @param {ReturnType<import('../logique/liens.js').creerLiens>} liens
 * @param {string} id
 * @param {Object} [params]
 * @param {{libelle?: string, sansRepli?: boolean, deja?: Set<string>, notesVues?: Set<string>}} [options]
 *        libelle: text of the link, when the generic label of the table is too general here
 *        deja: ids already drawn next to this one (their fallback is not repeated)
 *        notesVues: notes already written just above (the same sentence is not repeated in
 *                   full: the link keeps its « Lien non vérifié » label and points to it)
 *        remarque: the note of this link is written once elsewhere on the page (a long list of
 *                  links of the same kind): this short sentence points to it instead
 *        sansNote: the caller writes that short pointer itself, once for several links
 * @returns {HTMLElement|null}
 */
export function lienExterne(liens, id, params = {}, { libelle, sansRepli = false, deja = new Set(), notesVues = null, remarque = null, sansNote = false } = {}) {
  const resolu = liens.resoudre(id, params);
  if (resolu === null || !resolu.proposer) return null;
  const box = h('span', { class: 'lien-externe', data: { lien: id, statut: resolu.statut } });
  if (resolu.url === null) {
    box.classList.add('lien-externe--vide');
    box.append(h('span', { class: 'lien-externe__libelle' }, libelle || resolu.libelle), h('span', { class: 'lien-externe__hote' }, T.lien.aRemplir(resolu.hote)));
    return box;
  }
  box.append(...ancre(resolu, libelle));
  if (!resolu.teste && resolu.note && sansNote) {
    box.dataset.note = 'ailleurs';
  } else if (!resolu.teste && resolu.note && remarque) {
    box.append(h('span', { class: 'lien-externe__note' }, h('span', { class: 'lien-externe__etiquette' }, T.lien.nonVerifie), ' ', remarque));
  } else if (!resolu.teste && resolu.note) {
    const repeated = notesVues !== null && notesVues.has(resolu.note);
    notesVues?.add(resolu.note);
    box.append(h('span', { class: 'lien-externe__note' }, h('span', { class: 'lien-externe__etiquette' }, T.lien.nonVerifie), ' ', repeated ? T.lien.memeRemarque : resolu.note));
    if (!sansRepli && !repeated && resolu.repli !== null && !deja.has(resolu.repli)) {
      const repli = lienExterne(liens, resolu.repli, params, { sansRepli: true });
      if (repli !== null) box.append(h('span', { class: 'lien-externe__repli' }, T.lien.repli, ' ', repli));
    }
  }
  return box;
}

/** Several links of one step, as a list; fallbacks already in the list are not repeated. */
export function listeDeLiens(liens, ids, params = {}, { libelles = {}, notesVues = new Set() } = {}) {
  const deja = new Set(ids);
  const items = ids.map((id) => lienExterne(liens, id, params, { deja, libelle: libelles[id], notesVues })).filter((el) => el !== null);
  if (items.length === 0) return null;
  return h('ul', { class: 'liens' }, items.map((el) => h('li', null, el)));
}

/**
 * An address copied as it is from a source file (never tested by definition).
 * @returns {HTMLElement|null} null when the address is not on a host the link table knows
 */
export function lienParticulier(liens, url, libelle) {
  const resolu = liens.particulier(url);
  if (resolu === null) return null;
  return h('span', { class: 'lien-externe', data: { lien: 'particulier', statut: resolu.statut } },
    ...ancre(resolu, libelle),
    h('span', { class: 'lien-externe__note' }, h('span', { class: 'lien-externe__etiquette' }, T.lien.nonVerifie), ' ', T.lien.copieDeLaSource));
}
