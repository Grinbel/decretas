/**
 * #/actes — the sixteen sorts of acts that existed from 1865 to 1962 (site/contenu/types-d-actes.json),
 * filterable by period (the periods of aiguillage.json). #/actes/T7 opens on one card.
 *   #/actes?epoque=e-1899-1912
 */

import { h, icone, remplacer } from '../composants/dom.js';
import { avis } from '../composants/avis.js';
import { echecDePage } from '../composants/echec.js';
import { champs } from '../composants/carte.js';
import { formerHash } from '../routeur.js';

/** A card overlaps a period when its years cross the period's years (an open end runs on). */
export function dansEpoque(type, epoque) {
  if (!epoque) return true;
  const debut = type.periode?.debut ?? -Infinity;
  const fin = type.periode?.fin ?? Infinity;
  return debut <= epoque.annees.fin && fin >= epoque.annees.debut;
}

function enonces(liste, T) {
  return h('ul', { class: 'enonces' }, liste.map((e) => h('li', null,
    h('p', null, e.texte),
    h('p', { class: 'note' }, T.actes.source, ' ', e.source, e.etat && e.etat !== 'verifie' ? ` (${T.actes.sourcePartielle})` : ''))));
}

function carteActe(type, types, guides, T, ouvert) {
  const A = T.actes;
  const couvertures = (type.sur_ce_site?.couvertures ?? []).map((c) => types.couvertures?.[c]).filter(Boolean);
  const guidesDuType = (type.sur_ce_site?.guides ?? []).map((id) => guides.get(id)).filter(Boolean);
  return h('article', { class: `acte${ouvert ? ' acte--cible' : ''}`, id: `acte-${type.id}`, tabindex: '-1' },
    h('h2', { class: 'acte__titre' }, type.titre_court),
    h('p', { class: 'acte__periode' }, type.periode?.texte),
    champs([
      [A.qui, type.qui],
      [A.nature, type.nature_texte],
      [A.nominatif, type.nominatif ? A.oui : A.non],
      [A.publie, types.valeurs_publie?.[type.publie] ?? type.publie],
    ]),
    h('div', { class: 'acte__site' },
      h('p', { class: 'acte__site-titre' }, A.surCeSite),
      couvertures.length > 0 ? h('ul', { class: 'liste-simple acte__couvertures' }, couvertures.map((c) => h('li', null, c))) : null,
      type.sur_ce_site?.texte ? h('p', null, type.sur_ce_site.texte) : null,
      guidesDuType.length > 0 ? h('ul', { class: 'liens-internes liens-internes--guides' }, guidesDuType.map((g) => h('li', null,
        h('a', { href: formerHash('guides', [g.id]) }, icone('fleche'), h('span', null, g.titre))))) : null),
    (type.a_savoir ?? []).length > 0 ? h('div', null, h('p', { class: 'acte__site-titre' }, A.aSavoir), h('ul', null, type.a_savoir.map((x) => h('li', null, x)))) : null,
    h('details', { class: 'repli', open: ouvert || null },
      h('summary', null, A.ouPublieConserve),
      type.ou_publie ? h('p', null, h('strong', null, A.ouPublie), ' ', type.ou_publie) : null,
      type.ou_conserve ? h('p', null, h('strong', null, A.ouConserve), ' ', type.ou_conserve) : null),
    type.fondement ? h('details', { class: 'repli' }, h('summary', null, A.fondement), h('p', { class: 'source-brute' }, type.fondement)) : null,
    (type.etablit ?? []).length > 0 || (type.n_etablit_pas ?? []).length > 0 ? h('details', { class: 'repli' },
      h('summary', null, A.etablit),
      (type.etablit ?? []).length > 0 ? enonces(type.etablit, T) : null,
      (type.n_etablit_pas ?? []).length > 0 ? [h('p', { class: 'repli__sous-titre' }, A.nEtablitPas), enonces(type.n_etablit_pas, T)] : null) : null);
}

export const vueActes = {
  asynchrone: true,
  titre: (route, { T }) => T.actes.titreDocument,

  monter(conteneur, route, { T, contenu, finDeRendu, remonter }) {
    const A = T.actes;
    const zone = h('div', { class: 'vue vue--actes' }, h('p', { class: 'note', role: 'status' }, T.guides.chargement));
    conteneur.append(zone);
    let vivant = true;
    contenu.plusieurs('types-d-actes', 'aiguillage', 'guides').then(([types, arbre, guidesJson]) => {
      if (!vivant) return;
      const guides = new Map(guidesJson.guides.map((g) => [g.id, g]));
      const cible = route.segments[0] ?? null;
      const epoque = (arbre.epoques ?? []).find((e) => e.id === route.params.epoque) ?? null;
      const liste = types.types.filter((t) => dansEpoque(t, epoque) || t.id === cible);
      remplacer(zone,
        h('h1', null, types.titre),
        h('p', { class: 'chapeau' }, types.chapeau),
        avis({ ton: 'neutre' }, types.note_vocabulaire),
        h('nav', { class: 'filtre-epoque', aria: { label: A.filtre } },
          h('p', { class: 'filtre-epoque__titre' }, A.filtre),
          h('ul', { class: 'pastilles' },
            h('li', null, h('a', { class: 'pastille', href: formerHash('actes'), aria: { current: epoque === null ? 'true' : null } }, A.toutes)),
            (arbre.epoques ?? []).map((e) => h('li', null, h('a', { class: 'pastille', href: formerHash('actes', [], { epoque: e.id }), aria: { current: epoque?.id === e.id ? 'true' : null } }, e.libelle))))),
        h('p', { class: 'note', role: 'status' }, A.compte(liste.length, types.types.length)),
        epoque ? h('p', { class: 'note' }, epoque.texte) : null,
        h('div', { class: 'actes' }, liste.map((t) => carteActe(t, types, guides, T, t.id === cible))));
      const el = cible ? zone.querySelector(`#acte-${CSS.escape(cible)}`) : null;
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
