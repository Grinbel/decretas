/**
 * Home page = the search. One obvious action: type a name. The index starts loading when the
 * field gets the focus, or once the browser is idle — never before the first paint, and not
 * at all on idle when the visitor asked to save data.
 */

import { h, icone } from '../composants/dom.js';
import { formulaireRecherche } from '../composants/formulaire-recherche.js';
import { etatChargement } from '../composants/chargement.js';
import { formerHash } from '../routeur.js';
import { parametresDepuisEtat } from '../logique/requete.js';

export const vueAccueil = {
  titre: (route, { T }) => T.accueil.titreDocument,

  monter(conteneur, route, { T, donnees, aller }) {
    const A = T.accueil;
    const formulaire = formulaireRecherche({
      surIntention: () => donnees.charger(),
      surSoumission: ({ texte, annee }) => aller(formerHash('recherche', [], parametresDepuisEtat({ texte, annee, exclusions: {}, ajouts: {} }))),
    });
    const chargement = etatChargement(donnees);

    conteneur.append(
      h('div', { class: 'vue vue--accueil' },
        h('header', { class: 'accueil__tete' },
          h('h1', { class: 'accueil__titre' }, A.titre),
          h('p', { class: 'accueil__promesse' }, A.promesse)),
        formulaire.element,
        chargement.element,
        h('ul', { class: 'engagements' }, A.engagements.map((e) => h('li', null, h('strong', null, e.titre), h('span', null, e.texte)))),
        h('nav', { class: 'entrees', aria: { label: A.autresEntrees } },
          h('a', { class: 'entree', href: formerHash('quel-acte') },
            h('span', { class: 'entree__texte' }, h('span', { class: 'entree__titre' }, A.quelActe.titre), h('span', { class: 'entree__detail' }, A.quelActe.texte)), icone('fleche')),
          h('a', { class: 'entree', href: formerHash('numero') },
            h('span', { class: 'entree__texte' }, h('span', { class: 'entree__titre' }, A.numero.titre), h('span', { class: 'entree__detail' }, A.numero.texte)), icone('fleche'))),
        h('p', { class: 'accueil__independance' }, A.independance)));

    // Warm the index when the browser has nothing better to do, unless data saving is on.
    const econome = navigator.connection?.saveData === true;
    let attente = null;
    if (!econome) {
      if (typeof window.requestIdleCallback === 'function') {
        const id = window.requestIdleCallback(() => donnees.charger(), { timeout: 4000 });
        attente = () => window.cancelIdleCallback(id);
      } else {
        const id = window.setTimeout(() => donnees.charger(), 2500);
        attente = () => window.clearTimeout(id);
      }
    }
    return () => {
      attente?.();
      chargement.detruire();
    };
  },
};
