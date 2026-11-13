/**
 * "Guide steps" component: draws the steps of one guide of site/contenu/guides.json as a
 * numbered list. For each step: what to do, the links (filled from liens.json with the
 * parameters of the notice at hand), what the screen should show, what else can happen and
 * what to do then; and, when nobody has seen that screen yet, the discreet « À confirmer »
 * note of the content file.
 *
 *   etapesGuide(guide, { liens, params, legende, ecrans, libelles, niveau })
 *
 *   guide     one element of guides.json "guides"
 *   liens     the link resolver (logique/liens.js#creerLiens)
 *   params    values for the link templates ({inventaire, notice, identifiant, feuillet…});
 *             without them, a link that needs them is shown as text, not as a dead link
 *   legende   guides.json "legende" (label of the « À confirmer » note)
 *   ecrans    guides.json "ecrans_communs" (the shared help screens a step refers to)
 *   libelles  {linkId: text} to name a link more precisely than the table does
 *   paramsParLien {linkId: params} when one link of the guide needs other values than "params"
 *   remplacements {linkId: () => Node|null} to draw a link yourself (an address copied from a
 *             data file, for instance) or to leave it out (null) where it does not apply
 *   niveau    heading level of the step titles (default 4)
 *   notesVues a Set shared with the rest of the page: an honest note already written in full
 *             above is not written again (default: one note per step)
 */

import { h } from './dom.js';
import { listeDeLiens } from './lien-externe.js';
import { T } from '../textes/index.js';

function ecranCommun(ecran) {
  return h('details', { class: 'etape__ecran' },
    h('summary', null, ecran.titre),
    h('p', null, h('strong', null, T.guide.vousVoyez), ' ', ecran.ce_que_vous_voyez),
    h('p', null, h('strong', null, T.guide.celaVeutDire), ' ', ecran.ce_que_cela_veut_dire),
    h('p', null, h('strong', null, T.guide.queFaire), ' ', ecran.que_faire),
    ecran.verifie === false && ecran.a_confirmer ? h('p', { class: 'a-confirmer' }, h('span', { class: 'a-confirmer__etiquette' }, T.guide.aConfirmer), ' ', ecran.a_confirmer) : null);
}

/**
 * @returns {HTMLOListElement}
 */
export function etapesGuide(guide, { liens, params = {}, legende = {}, ecrans = [], libelles = {}, paramsParLien = {}, remplacements = {}, niveau = 4, notesVues: notesDeLaPage = null } = {}) {
  const ecransParId = new Map(ecrans.map((e) => [e.id, e]));
  const etiquette = legende.libelle_a_confirmer ?? T.guide.aConfirmer;
  const level = Math.min(6, Math.max(2, niveau));
  return h('ol', { class: 'etapes' }, (guide.etapes ?? []).map((etape) => {
    const ids = (etape.liens ?? []);
    let links = null;
    if (liens && ids.length > 0) {
      const replaced = ids.filter((id) => typeof remplacements[id] === 'function');
      const own = ids.filter((id) => paramsParLien[id] !== undefined && !replaced.includes(id));
      const shared = ids.filter((id) => paramsParLien[id] === undefined && !replaced.includes(id));
      const lists = [];
      const notesVues = notesDeLaPage ?? new Set(); // one honest note per step (or per page), not one per link
      const custom = replaced.map((id) => remplacements[id]()).filter((node) => node !== null && node !== undefined);
      if (custom.length > 0) lists.push(h('ul', { class: 'liens' }, custom.map((node) => h('li', null, node))));
      if (shared.length > 0) lists.push(listeDeLiens(liens, shared, params, { libelles, notesVues }));
      for (const id of own) lists.push(listeDeLiens(liens, [id], paramsParLien[id], { libelles, notesVues }));
      links = lists.filter((el) => el !== null);
    }
    const issues = etape.issues_possibles ?? [];
    const communs = (etape.ecrans_communs ?? []).map((id) => ecransParId.get(id)).filter((e) => e !== undefined);
    return h('li', { class: `etape${etape.verifie === false ? ' etape--a-confirmer' : ''}`, data: { etape: `${guide.id}/${etape.id}` } },
      h(`h${level}`, { class: 'etape__titre' }, etape.titre),
      h('p', { class: 'etape__instruction' }, etape.instruction),
      links,
      (etape.ce_que_l_ecran_montre || issues.length > 0 || communs.length > 0)
        ? h('details', { class: 'etape__suite' },
          h('summary', null, T.guide.ceQueVousDevezVoir),
          etape.ce_que_l_ecran_montre ? h('p', null, etape.ce_que_l_ecran_montre) : null,
          issues.length > 0 ? h('dl', { class: 'issues' }, issues.map((issue) => h('div', { class: 'issues__cas' },
            h('dt', null, issue.si),
            h('dd', null, issue.signifie, ' ', h('strong', null, issue.faire))))) : null,
          communs.map(ecranCommun))
        : null,
      etape.verifie === false && etape.a_confirmer
        ? h('p', { class: 'a-confirmer' }, h('span', { class: 'a-confirmer__etiquette' }, etiquette), ' ', etape.a_confirmer)
        : null);
  }));
}
