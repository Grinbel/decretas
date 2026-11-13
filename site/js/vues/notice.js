/**
 * Page of ONE notice, with an address that can be kept:
 *   #/notice/an/<inventaire>/<notice>[?m=<rank of the person in the notice>]
 *   #/notice/bogga/<year of the volume>/<leaf>/<rank on the leaf>
 * The address holds identifiers of the sources, not the row ranks of the data files (which
 * change at every rebuild). For the Bulletin the rank on the leaf may shift if the page is cut
 * differently by a later build: the page says so when the notice is not found.
 */

import { h, nomEcrit, remplacer, icone } from '../composants/dom.js';
import { etatChargement } from '../composants/chargement.js';
import { detailFiche } from '../composants/fiche.js';
import { avis } from '../composants/avis.js';
import { echecDePage } from '../composants/echec.js';
import { formerHash } from '../routeur.js';

function referenceDepuisRoute(route) {
  const [source, a, b, c] = route.segments;
  if (source === 'an' && a && b) return { source: 'an', inv: a, notice: b };
  if (source === 'bogga' && /^\d{4}$/.test(a ?? '') && /^\d+$/.test(b ?? '') && /^\d+$/.test(c ?? '')) {
    return { source: 'bogga', annee: Number(a), feuille: Number(b), rang: Number(c) };
  }
  return null;
}

export const vueNotice = {
  asynchrone: true,
  titre: (route, { T }) => T.notice.titreDocument,

  monter(conteneur, route, { T, donnees, contenu, retourPossible, finDeRendu, remonter }) {
    const N = T.notice;
    const zone = h('div', { class: 'notice__corps' });
    // A failed download is said once, below, with its retry button.
    const chargement = etatChargement(donnees, { discret: true, sansErreur: true });
    const retour = h('p', { class: 'retour' }, h('a', {
      href: formerHash(''),
      on: {
        click: (event) => {
          // Back to the results when the visitor came from them; to the home page otherwise.
          if (retourPossible()) {
            event.preventDefault();
            window.history.back();
          }
        },
      },
    }, icone('retour'), h('span', null, N.retour)));
    conteneur.append(h('div', { class: 'vue vue--notice' }, retour, chargement.element, zone));
    remplacer(zone, h('h1', null, N.chargement));
    let vivant = true;

    const ref = referenceDepuisRoute(route);
    if (ref === null) {
      remplacer(zone, h('h1', null, N.introuvableTitre), avis({ ton: 'attention' }, N.adresseIllisible));
      finDeRendu();
      return () => chargement.detruire();
    }

    Promise.all([donnees.fiche(ref), contenu.plusieurs('bilan', 'guides', 'vocabulaire'), contenu.liens()]).then(([fiche, [bilan, guides, vocabulaire], liens]) => {
      if (!vivant) return;
      if (fiche === null) {
        remplacer(zone, h('h1', null, N.introuvableTitre), avis({ ton: 'attention' }, N.introuvable));
        finDeRendu();
        return;
      }
      const rang = /^\d+$/.test(route.params.m ?? '') ? Number(route.params.m) : 0;
      const personne = fiche.source === 'an' ? (fiche.membres[rang] ?? fiche.membres[0]) : null;
      const nom = fiche.source === 'an' ? (personne.nom ?? T.fiche.nomNonSaisi) : fiche.nom;
      const principal = fiche.source === 'an' ? fiche.membres[0] : null;
      const titre = h('h1', { class: 'notice__titre' }, nomEcrit(nom, { class: 'nom' }));
      remplacer(zone,
        titre,
        h('p', { class: 'notice__source' }, T.sources[fiche.source].long),
        personne && personne.role !== 'principal' ? h('p', { class: 'carte__lien-menage' }, T.fiche.rolesDans[personne.role] ?? '', ' ', nomEcrit(principal.nom ?? T.fiche.nomNonSaisi, { class: 'nom' })) : null,
        avis({ ton: 'neutre' }, N.rappel),
        detailFiche(fiche, { liens, guides, vocabulaire, bilan, couverture: donnees.etat().resume.couverture, niveau: 2 }));
      document.title = T.app.titreDocument(N.titreDocumentNom(nom));
      finDeRendu(titre);
    }).catch((error) => {
      if (!vivant) return;
      if (error?.name === 'ErreurDonnees' || error?.name === 'ContenuIndisponible') {
        echecDePage(zone, { T, erreur: error, remonter, finDeRendu });
      } else {
        throw error;
      }
    });

    return () => {
      vivant = false;
      chargement.detruire();
    };
  },
};
