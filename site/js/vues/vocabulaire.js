/**
 * #/vocabulaire — « Les mots de ce site » (site/contenu/vocabulaire.json): the terms by family,
 * the abbreviations, and the wordings the site uses on purpose. #/vocabulaire/<term id> opens on
 * one term: the other pages link their words there (composants/chargement-leger.js#mot).
 *
 * "a_eviter" and "ne_pas_dire" hold, by definition, wordings the site refuses: they are shown
 * only in the table of wordings, struck through and labelled, never as running text.
 */

import { h, remplacer, viserTitre } from '../composants/dom.js';
import { avis } from '../composants/avis.js';
import { echecDePage } from '../composants/echec.js';
import { formerHash } from '../routeur.js';

export const vueVocabulaire = {
  asynchrone: true,
  titre: (route, { T }) => T.vocabulaire.titreDocument,

  monter(conteneur, route, { T, contenu, finDeRendu, remonter }) {
    const V = T.vocabulaire;
    const zone = h('div', { class: 'vue vue--vocabulaire' }, h('p', { class: 'note', role: 'status' }, T.guides.chargement));
    conteneur.append(zone);
    let vivant = true;
    contenu.charger('vocabulaire').then((voc) => {
      if (!vivant) return;
      const parId = new Map(voc.termes.map((t) => [t.id, t]));
      const cible = route.segments[0] ?? null;
      const familles = Object.entries(voc.familles ?? {}).filter(([cle]) => voc.termes.some((t) => t.famille === cle));
      const aller = (id) => (event) => {
        event.preventDefault();
        const el = zone.querySelector(`#${CSS.escape(id)}`);
        if (el) viserTitre(el);
      };
      remplacer(zone,
        h('h1', null, voc.titre),
        h('p', { class: 'chapeau' }, voc.chapeau),
        h('nav', { class: 'sommaire', aria: { label: V.sommaire } },
          h('ul', { class: 'pastilles' },
            familles.map(([cle, libelle]) => h('li', null, h('a', { class: 'pastille', href: `#famille-${cle}`, on: { click: aller(`famille-${cle}`) } }, libelle))),
            h('li', null, h('a', { class: 'pastille', href: '#sigles', on: { click: aller('sigles') } }, V.sigles)),
            h('li', null, h('a', { class: 'pastille', href: '#formulations', on: { click: aller('formulations') } }, V.formulations)))),
        familles.map(([cle, libelle]) => h('section', { class: 'famille', aria: { labelledby: `famille-${cle}` } },
          h('h2', { id: `famille-${cle}` }, libelle),
          h('dl', { class: 'termes' }, voc.termes.filter((t) => t.famille === cle).map((t) => h('div', { class: `terme${t.id === cible ? ' terme--cible' : ''}`, id: `terme-${t.id}`, tabindex: '-1' },
            h('dt', { class: 'terme__nom' }, t.terme),
            h('dd', null,
              h('p', null, t.definition),
              (t.voir ?? []).filter((id) => parId.has(id)).length > 0 ? h('p', { class: 'note' }, V.voir, ' ',
                (t.voir ?? []).filter((id) => parId.has(id)).map((id, i) => [i > 0 ? T.formats.virgule : '', h('a', { href: formerHash('vocabulaire', [id]) }, parId.get(id).terme)])) : null)))))),
        h('section', { class: 'famille', aria: { labelledby: 'sigles' } },
          h('h2', { id: 'sigles' }, V.sigles),
          h('table', { class: 'tableau tableau--empile tableau--texte' },
            h('thead', null, h('tr', null, h('th', { scope: 'col' }, V.colSigle), h('th', { scope: 'col' }, V.colDeveloppe), h('th', { scope: 'col' }, V.colExplication))),
            h('tbody', null, (voc.sigles ?? []).map((s) => h('tr', null,
              h('th', { scope: 'row', data: { libelle: V.colSigle } }, h('abbr', { title: s.developpe }, s.sigle)),
              h('td', { data: { libelle: V.colDeveloppe } }, s.developpe),
              h('td', { data: { libelle: V.colExplication } }, s.explication)))))),
        h('section', { class: 'famille', aria: { labelledby: 'formulations' } },
          h('h2', { id: 'formulations' }, V.formulations),
          h('ul', { class: 'formulations' }, (voc.formulations ?? []).map((f) => h('li', { class: 'formulation' },
            h('p', null, h('span', { class: 'formulation__etiquette' }, V.nousEcrivons), ' ', h('strong', null, f.dire)),
            h('p', { class: 'note' }, h('span', { class: 'formulation__etiquette' }, V.plutotQue), ' ', h('del', null, f.ne_pas_dire)),
            h('p', { class: 'note' }, h('span', { class: 'formulation__etiquette' }, V.pourquoi), ' ', f.pourquoi))))));
      const el = cible ? zone.querySelector(`#terme-${CSS.escape(cible)}`) : null;
      finDeRendu(el, { ancre: el !== null });
    }).catch((error) => {
      if (!vivant) return;
      if (error?.name === 'ContenuIndisponible') echecDePage(zone, { T, erreur: error, remonter, finDeRendu });
      else throw error;
    });
    return () => {
      vivant = false;
    };
  },
};
