/**
 * #/quel-acte — « Quel acte chercher ? »: the decision tree of site/contenu/aiguillage.json, one
 * question per screen. The answers given are the address (#/quel-acte?r=d-ancetre,f-musulmane):
 * the browser's "back" goes back one question, the trail can be changed at any step, and an
 * outcome can be kept or sent. #/quel-acte/<outcome id> names an outcome directly.
 *
 * Every sentence comes from the content files; this file only arranges them.
 */

import { h, icone, remplacer } from '../composants/dom.js';
import { aConfirmer, avis } from '../composants/avis.js';
import { echecDePage } from '../composants/echec.js';
import { listeDeLiens } from '../composants/lien-externe.js';
import { formerHash } from '../routeur.js';
import { epoquesPour, issueParId, lireReponses, parcourir } from '../logique/aiguillage.js';
import { lireAnnee } from '../logique/requete.js';

const hashReponses = (ids, extra = {}) => formerHash('quel-acte', [], { r: ids.join(','), ...extra });

/** Where the main road of an outcome is followed: on this site when it can be. */
function actionDeVoie(voie, guides, T) {
  const Q = T.quelActe;
  if (voie.id === 'recherche-par-nom') return { href: formerHash(''), texte: Q.actions[voie.id] };
  if (voie.id === 'recherche-guidee-images') return { href: formerHash('decrets'), texte: Q.actions[voie.id] };
  if (voie.id === 'verification-d-une-citation') return { href: formerHash('numero'), texte: Q.actions[voie.id] };
  const guide = (voie.guides ?? []).map((id) => guides.get(id)).find(Boolean);
  return guide ? { href: formerHash('guides', [guide.id]), texte: Q.suivreLeGuide(guide.titre) } : null;
}

function listeGuides(ids, guides) {
  const list = (ids ?? []).map((id) => guides.get(id)).filter(Boolean);
  if (list.length === 0) return null;
  return h('ul', { class: 'liens-internes liens-internes--guides' }, list.map((g) => h('li', null,
    h('a', { href: formerHash('guides', [g.id]) }, icone('fleche'), h('span', null, g.titre)))));
}

function fil(chemin, T) {
  if (chemin.length === 0) return null;
  return h('nav', { class: 'fil', aria: { label: T.quelActe.vosReponses } },
    h('p', { class: 'fil__titre' }, T.quelActe.vosReponses),
    h('ol', { class: 'fil__liste' }, chemin.map((pas, i) => h('li', { class: 'fil__pas' },
      h('span', { class: 'fil__question' }, pas.question.question),
      h('span', { class: 'fil__reponse' }, pas.reponse.libelle),
      pas.reponse.precision ? h('span', { class: 'fil__precision' }, pas.reponse.precision) : null,
      h('a', { class: 'fil__changer', href: hashReponses(chemin.slice(0, i).map((p) => p.reponse.id)) }, T.quelActe.changer)))));
}

function ecranQuestion(question, chemin, arbre, T) {
  const Q = T.quelActe;
  const ids = chemin.map((p) => p.reponse.id);
  return [
    h('h1', { class: 'question__titre' }, question.question),
    chemin.length === 0 ? h('p', { class: 'chapeau' }, arbre.chapeau) : null,
    h('p', { class: 'question__aide' }, question.aide ? `${question.aide} ` : '', h('span', { class: 'question__rang' }, Q.question(chemin.length + 1))),
    h('ul', { class: 'reponses' }, (question.reponses ?? []).map((r) => h('li', null,
      h('a', { class: 'reponse', href: hashReponses([...ids, r.id]) }, h('span', { class: 'reponse__libelle' }, r.libelle), icone('fleche'))))),
    chemin.length === 0 ? h('p', { class: 'note' }, arbre.regle) : null,
    chemin.length > 0 ? h('p', { class: 'retour' }, h('a', { href: hashReponses(ids.slice(0, -1)) }, icone('retour'), h('span', null, Q.precedente))) : null,
  ];
}

function sectionEpoques(arbre, route, issueId, ids, T, aller, guides) {
  const Q = T.quelActe;
  const naissance = lireAnnee(route.params.ne ?? '');
  const epoques = epoquesPour(arbre, naissance);
  const champ = h('input', { id: 'qa-ne', name: 'ne', type: 'text', inputmode: 'numeric', maxlength: '4', class: 'champ__saisie champ__saisie--annee', value: naissance ?? '', aria: { describedby: 'qa-ne-aide' } });
  const formulaire = h('form', { class: 'filtre-epoques', novalidate: true },
    h('label', { class: 'champ__libelle', for: 'qa-ne' }, Q.epoquesFiltre),
    h('div', { class: 'filtre-epoques__ligne' }, champ, h('button', { type: 'submit', class: 'bouton bouton--secondaire' }, Q.epoquesFiltrer)),
    h('p', { id: 'qa-ne-aide', class: 'champ__aide' }, Q.epoquesAide));
  formulaire.addEventListener('submit', (event) => {
    event.preventDefault();
    const annee = lireAnnee(champ.value.trim());
    const base = route.segments.length > 0 ? formerHash('quel-acte', [issueId], { ne: annee }) : hashReponses(ids, { ne: annee });
    aller(base, { remplacer: true });
  });
  const voies = new Map((arbre.voies ?? []).map((v) => [v.id, v]));
  return h('section', { class: 'quel-acte__bloc', aria: { labelledby: 'qa-epoques' } },
    h('h2', { id: 'qa-epoques' }, Q.epoquesTitre),
    h('p', null, arbre.epoques_intro),
    formulaire,
    naissance !== null ? h('p', { class: 'note' }, Q.epoquesFiltrees(naissance, naissance + (arbre.age_minimal?.decret ?? 0)), ' ',
      h('a', { href: route.segments.length > 0 ? formerHash('quel-acte', [issueId]) : hashReponses(ids) }, Q.toutesLesEpoques)) : null,
    h('ol', { class: 'epoques' }, epoques.map((e) => h('li', { class: 'epoque' },
      h('h3', { class: 'epoque__titre' }, e.libelle),
      h('p', null, e.texte),
      aConfirmer(e.verification),
      voies.get(e.voie) ? (() => {
        const action = actionDeVoie(voies.get(e.voie), guides, T);
        return h('p', { class: 'epoque__voie' }, action ? h('a', { href: action.href }, voies.get(e.voie).libelle) : voies.get(e.voie).libelle);
      })() : null))));
}

function ecranIssue(issue, arbre, contenus, route, ids, T, aller) {
  const Q = T.quelActe;
  const { types, guides, bilan, liens, vocabulaire } = contenus;
  // words of the outcome explained in « Les mots de ce site » (« statut personnel »…)
  const mots = (issue.vocabulaire ?? []).map((id) => (vocabulaire?.termes ?? []).find((t) => t.id === id)).filter(Boolean);
  const voies = new Map((arbre.voies ?? []).map((v) => [v.id, v]));
  const voie = voies.get(issue.voie);
  const action = voie ? actionDeVoie(voie, guides, T) : null;
  const typesDeLIssue = (issue.types ?? []).map((id) => types.types.find((t) => t.id === id)).filter(Boolean);
  const secondaires = (issue.voies_secondaires ?? []).map((id) => voies.get(id)).filter(Boolean);

  return [
    h('h1', { class: 'issue__titre' }, issue.titre),
    h('p', { class: 'chapeau' }, issue.message),
    aConfirmer(issue.verification),
    (issue.points ?? []).length > 0 ? h('ul', { class: 'issue__points' }, issue.points.map((p) => h('li', null, p))) : null,
    mots.length > 0 ? h('p', { class: 'note' }, T.vocabulaire.voir, ' ', mots.map((t, i) => [i > 0 ? T.formats.virgule : '', h('a', { href: formerHash('vocabulaire', [t.id]) }, t.terme)])) : null,
    issue.rappel_jugement && bilan.rappel_jugement?.court ? avis({ ton: 'neutre' }, bilan.rappel_jugement.court) : null,

    voie ? h('section', { class: 'quel-acte__bloc voie voie--principale', aria: { labelledby: 'qa-voie' } },
      h('h2', { id: 'qa-voie' }, Q.parOuCommencer),
      h('p', { class: 'voie__libelle' }, voie.libelle),
      h('p', null, voie.description),
      action ? h('p', null, h('a', { class: 'bouton bouton--principal', href: action.href }, h('span', null, action.texte), icone('fleche'))) : null) : null,

    (issue.guides ?? []).length > 0 ? h('section', { class: 'quel-acte__bloc', aria: { labelledby: 'qa-guides' } },
      h('h2', { id: 'qa-guides' }, Q.guidesUtiles),
      listeGuides(issue.guides, guides)) : null,

    secondaires.length > 0 ? h('section', { class: 'quel-acte__bloc', aria: { labelledby: 'qa-pistes' } },
      h('h2', { id: 'qa-pistes' }, Q.autresPistes),
      h('ul', { class: 'pistes' }, secondaires.map((v) => {
        const a = actionDeVoie(v, guides, T);
        return h('li', { class: 'piste' },
          // « Hors du champ de ce site » says it already: no « Hors de ce site » badge after it
          h('p', { class: 'piste__titre' }, v.libelle, v.id === 'hors-perimetre' ? null : [' ', h('span', { class: 'piste__lieu' }, v.sur_ce_site ? Q.surCeSite : Q.horsSite)]),
          h('p', null, v.description),
          a ? h('p', null, h('a', { href: a.href }, a.texte)) : null);
      }))) : null,

    typesDeLIssue.length > 0 ? h('section', { class: 'quel-acte__bloc', aria: { labelledby: 'qa-types' } },
      h('h2', { id: 'qa-types' }, Q.actesPossibles),
      h('ul', { class: 'actes-brefs' }, typesDeLIssue.map((t) => h('li', { class: 'acte-bref' },
        h('p', { class: 'acte-bref__titre' }, h('a', { href: formerHash('actes', [t.id]) }, t.titre_court)),
        h('p', { class: 'note' }, t.periode?.texte),
        // one line per kind of coverage: two sentences glued together read as a contradiction
        h('ul', { class: 'liste-simple note' }, (t.sur_ce_site?.couvertures ?? []).map((c) => types.couvertures?.[c]).filter(Boolean).map((x) => h('li', null, x))))))) : null,

    (issue.liens ?? []).length > 0 && liens ? h('section', { class: 'quel-acte__bloc', aria: { labelledby: 'qa-liens' } },
      h('h2', { id: 'qa-liens' }, Q.aLire),
      listeDeLiens(liens, issue.liens, {})) : null,

    issue.montrer_echelle && bilan.echelle ? h('section', { class: 'quel-acte__bloc', aria: { labelledby: 'qa-echelle' } },
      h('h2', { id: 'qa-echelle' }, bilan.echelle.titre),
      h('p', null, bilan.echelle.texte),
      // each figure with its detail and its reservation: a count is never shown without its limits
      h('ul', { class: 'echelle' }, (bilan.echelle.chiffres ?? []).map((c) => h('li', null, h('strong', null, c.valeur), ' ', c.libelle,
        [c.detail, c.reserve].filter((x) => typeof x === 'string' && x.trim() !== '').map((x) => h('span', { class: 'note echelle__precision' }, ` ${x}`)),
        c.source ? h('span', { class: 'note' }, ` — ${c.source}${c.etat && c.etat !== 'verifie' ? ` (${T.actes.sourcePartielle})` : ''}`) : null)))) : null,

    issue.montrer_epoques ? sectionEpoques(arbre, route, issue.id, ids, T, aller, guides) : null,

    h('p', { class: 'note quel-acte__adresse' }, Q.adresseAGarder),
    h('ul', { class: 'liens-internes quel-acte__navigation' },
      ids.length > 0 ? h('li', null, h('a', { href: hashReponses(ids.slice(0, -1)) }, icone('retour'), h('span', null, Q.precedente))) : null,
      h('li', null, h('a', { href: formerHash('quel-acte') }, Q.recommencer))),
  ];
}

export const vueQuelActe = {
  asynchrone: true,
  titre: (route, { T }) => T.quelActe.titreDocument,

  monter(conteneur, route, { T, contenu, aller, finDeRendu, remonter }) {
    const zone = h('div', { class: 'vue vue--quel-acte' }, h('p', { class: 'note', role: 'status' }, T.guides.chargement));
    conteneur.append(zone);
    let vivant = true;
    Promise.all([contenu.plusieurs('aiguillage', 'types-d-actes', 'guides', 'bilan', 'vocabulaire'), contenu.liens()]).then(([[arbre, types, guidesJson, bilan, vocabulaire], liens]) => {
      if (!vivant) return;
      const guides = new Map(guidesJson.guides.map((g) => [g.id, g]));
      const contenus = { types, guides, bilan, liens, vocabulaire };
      const nommee = route.segments[0];
      if (nommee) {
        const issue = issueParId(arbre, nommee);
        if (issue) remplacer(zone, ecranIssue(issue, arbre, contenus, route, [], T, aller));
        else remplacer(zone, avis({ ton: 'attention' }, T.quelActe.issueInconnue), ecranQuestion(parcourir(arbre, []).question, [], arbre, T));
      } else {
        const ids = lireReponses(route.params.r);
        const etat = parcourir(arbre, ids);
        const suivies = etat.chemin.map((p) => p.reponse.id);
        remplacer(zone,
          fil(etat.chemin, T),
          etat.ignorees.length > 0 ? avis({ ton: 'neutre' }, T.quelActe.adresseIgnoree) : null,
          etat.issue ? ecranIssue(etat.issue, arbre, contenus, route, suivies, T, aller) : ecranQuestion(etat.question, etat.chemin, arbre, T));
        if (etat.issue) document.title = T.app.titreDocument(etat.issue.titre);
      }
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
