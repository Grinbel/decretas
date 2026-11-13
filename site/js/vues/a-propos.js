/**
 * #/a-propos — sources, credits and licences, what the site does not do, privacy, the open
 * questions on reuse, how these texts were made, how to report an error (honestly: not yet).
 * From site/contenu/a-propos.json, plus a few sentences of the interface (textes/fr.js) about
 * what only the interface knows: the one thing kept in the browser, and the one request made to
 * another site.
 */

import { h, remplacer } from '../composants/dom.js';
import { avis } from '../composants/avis.js';
import { echecDePage } from '../composants/echec.js';
import { champs } from '../composants/carte.js';
import { lienExterne, listeDeLiens } from '../composants/lien-externe.js';

export const vueAPropos = {
  asynchrone: true,
  titre: (route, { T }) => T.aPropos.titreDocument,

  monter(conteneur, route, { T, contenu, finDeRendu, remonter }) {
    const P = T.aPropos;
    const zone = h('div', { class: 'vue vue--a-propos' }, h('p', { class: 'note', role: 'status' }, T.guides.chargement));
    conteneur.append(zone);
    let vivant = true;
    Promise.all([contenu.charger('a-propos'), contenu.liens()]).then(([ap, liens]) => {
      if (!vivant) return;
      remplacer(zone,
        h('h1', null, ap.titre),
        h('p', { class: 'chapeau' }, ap.objet),
        h('p', null, ap.promesse),

        h('h2', { id: 'sources' }, P.sources),
        (ap.sources ?? []).map((s) => h('section', { class: 'source' },
          h('h3', null, s.nom),
          champs([
            [P.utilise, s.ce_que_nous_utilisons],
            [P.donnees, s.date_des_donnees],
          ]),
          (s.licence ?? []).length > 0 ? h('div', { class: 'source__licence' },
            h('p', { class: 'repli__sous-titre' }, P.licence),
            h('ul', { class: 'enonces' }, s.licence.map((l) => h('li', null,
              h('p', null, l.texte),
              h('p', { class: 'note' }, T.actes.source, ' ', l.source),
              // a page listed below with the references is not linked twice
              l.lien && !(s.liens ?? []).includes(l.lien) ? lienExterne(liens, l.lien, {}) : null)))) : null,
          s.credit ? h('p', null, h('strong', null, P.credit), ' ', s.credit) : null,
          s.credit_exemple ? h('p', { class: 'note' }, P.exemple, ' ', s.credit_exemple) : null,
          s.credit_regle ? h('p', { class: 'note' }, s.credit_regle) : null,
          (s.liens ?? []).length > 0 ? [h('p', { class: 'repli__sous-titre' }, P.liens), listeDeLiens(liens, s.liens, {})] : null)),

        h('h2', null, P.creditsTitre),
        h('ul', null, (ap.sources ?? []).filter((s) => s.credit).map((s) => h('li', null, h('strong', null, T.formats.etiquette(s.nom)), s.credit)), h('li', null, P.creditPolices)),

        h('h2', null, P.neFaitPas),
        h('ul', { class: 'ne-fait-pas' }, (ap.ce_que_le_site_ne_fait_pas ?? []).map((x) => h('li', null, x.texte))),

        h('h2', { id: 'vie-privee' }, P.viePrivee),
        h('p', null, ap.vie_privee?.texte),
        h('p', null, P.viePriveeSite),
        h('p', null, P.viePriveeCarnet),

        h('h2', null, P.pointsOuverts),
        h('ul', { class: 'points-ouverts' }, (ap.points_ouverts ?? []).map((p) => h('li', { class: 'point-ouvert' },
          h('h3', null, p.titre, ' ', h('span', { class: `etat etat--${p.etat}` }, P.etats[p.etat] ?? p.etat)),
          h('p', null, p.texte)))),

        h('h2', null, P.methode),
        h('p', null, ap.methode?.texte),

        h('h2', null, P.erreurTitre),
        h('p', null, P.erreurTexte));
      finDeRendu();
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
