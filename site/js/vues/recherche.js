/**
 * Results page: #/recherche?q=…&ne=1876&tol=5&x=…&v=…
 * The whole state of the search is in the address (after "#", so never sent to a server).
 * Under the form: the spellings found in the sources, one line that opens on the toggles.
 * Then the heading (it takes the focus after a search), the engine's warnings, the
 * correspondences grouped by class, and — always — the « bilan de recherche ».
 */

import { h, nomEcrit, remplacer, texteMixte, viserTitre, icone } from '../composants/dom.js';
import { formulaireRecherche } from '../composants/formulaire-recherche.js';
import { etatChargement } from '../composants/chargement.js';
import { variantes } from '../composants/variantes.js';
import { avis } from '../composants/avis.js';
import { carteResultat } from '../composants/carte-resultat.js';
import { dessinerBilan } from '../composants/bilan.js';
import { formerHash } from '../routeur.js';
import { LONGUEUR_MAX, basculer, etatDepuisParametres, parametresDepuisEtat, titreCourt } from '../logique/requete.js';
import { CLASSES, PAS, fenetresDeCartes, grouperParNotice } from '../logique/menage.js';
import { avertissements } from '../logique/explications.js';
import { composerBilan } from '../logique/bilan.js';
import { enDeuxTemps } from '../logique/formats.js';
import { fenetresSauvees } from '../logique/position.js';

const TOLERANCES = [5, 10, 20];

/** The visitor's own date (not the UTC one), as AAAA-MM-JJ. */
const dateLocale = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

/** The sentence for a failed search: the precise one of the loading step when there is one. */
export function messageDEchec(error, T) {
  if (error?.name === 'ContenuIndisponible') return T.erreurs.contenu;
  if (['chargement', 'format', 'worker'].includes(error?.code)) return T.chargement.erreur(error.code, error.statut);
  return T.erreurs.recherche;
}

function creer(conteneur, contexte) {
  const { T, donnees, contenu, aller, finDeRendu, memoriser, restauration } = contexte;
  const R = T.resultats;
  let etat = null;        // state read from the address
  let numero = 0;         // to ignore the answer of an outdated search
  let dernier = null;     // last answer drawn
  let fenetres = null;    // which cards of each class are in the page
  let ressources = null;  // content files, loaded once

  const formulaire = formulaireRecherche({
    compact: true,
    surIntention: () => donnees.charger(),
    surSoumission: ({ texte, annee }) => naviguer({ texte, annee, anneeSaisie: annee === null ? '' : String(annee), tolerance: null, exclusions: {}, ajouts: {} }, { viser: true }),
  });
  // A failed download is said once, in the results area, with its own retry button.
  const chargement = etatChargement(donnees, { discret: true, sansErreur: true });
  const zoneVariantes = h('div', { class: 'recherche-tete__variantes' });
  // Closed at first, at every width: the answer of the search must start in the first screen.
  let variantesOuvertes = false;
  const annonce = h('p', { class: 'sr', role: 'status', aria: { live: 'polite' } });
  const zoneResultats = h('div', { class: 'resultats' });
  const zoneBilan = h('div', { class: 'bilan-zone' });
  // 'page': the first drawing of the page (app.js decides: back in history, first visit…);
  // true: after the visitor's own search, the heading takes the focus; false: stay where you are.
  let viserApres = 'page';

  conteneur.append(h('div', { class: 'vue vue--recherche' },
    h('div', { class: 'recherche-tete' }, formulaire.element, chargement.element, zoneVariantes),
    annonce, zoneResultats, zoneBilan));

  function naviguer(nouvel, { viser = false, remplacer: rep = false } = {}) {
    viserApres = viser;
    aller(formerHash('recherche', [], parametresDepuisEtat(nouvel)), { remplacer: rep });
  }

  function chargerRessources() {
    ressources ??= Promise.all([
      contenu.plusieurs('bilan', 'guides', 'vocabulaire', 'aiguillage'),
      contenu.liens(),
    ]).then(([[bilan, guides, vocabulaire, aiguillage], liens]) => ({ bilan, guides, vocabulaire, aiguillage, liens }));
    ressources.catch(() => {
      ressources = null;
    });
    return ressources;
  }

  function titre(texte) {
    return h('h1', { class: 'resultats__titre' }, texte);
  }

  function dessinerAttente() {
    const avaitLeFocus = zoneResultats.contains(document.activeElement);
    zoneResultats.dataset.etatRecherche = 'en-cours';
    const h1 = titre(R.enCours);
    remplacer(zoneResultats, h1, h('p', { class: 'resultats__resume' }, R.enCoursTexte));
    remplacer(zoneBilan);
    if (avaitLeFocus) viserTitre(h1);
  }

  function dessinerEchec(error, { viser = false } = {}) {
    zoneResultats.dataset.etatRecherche = 'echec';
    const h1 = titre(T.erreurs.titre);
    const avaitLeFocus = zoneResultats.contains(document.activeElement);
    // The retry starts the download again (donnees/client.js forgets a failed load), then the search.
    remplacer(zoneResultats, h1,
      avis({ ton: 'attention', role: 'alert' }, messageDEchec(error, T)),
      h('p', null, h('button', { type: 'button', class: 'bouton bouton--secondaire', on: { click: () => lancer({ viser: true }) } }, T.chargement.reessayer)));
    remplacer(zoneBilan);
    // The button that had the focus is gone: the reader is put on the heading, not on <body>.
    if (viser === 'page' && !avaitLeFocus) finDeRendu(h1);
    else if (viser || avaitLeFocus) viserTitre(h1);
  }

  function dessinerVide() {
    zoneResultats.dataset.etatRecherche = 'fini';
    remplacer(zoneVariantes);
    remplacer(zoneResultats, titre(R.saisieVideTitre), h('p', { class: 'resultats__resume' }, R.saisieVide));
    remplacer(zoneBilan);
    formulaire.champNom.focus();
  }

  function groupe(classe, cartes, comptes, tronque, ctxFiche) {
    const C = T.classes[classe];
    const w = fenetres[classe];
    const total = cartes.length;
    const noms = comptes.parClasse[classe] ?? 0;
    if (noms === 0) return null;
    const liste = h('ol', { class: 'cartes' }, cartes.slice(w.debut, w.fin).map((c) => h('li', null, carteResultat(dernier.fiches[c.cle], c.touches, ctxFiche))));
    const pied = [];
    if (w.debut > 0) {
      pied.push(h('p', { class: 'groupe__retour' }, R.premieresMasquees(w.debut), ' ',
        h('button', { type: 'button', class: 'bouton bouton--lien', on: { click: () => plus(classe, 'debut') } }, R.revenirAuDebut)));
    }
    if (w.fin < total) {
      pied.push(h('p', { class: 'groupe__plus' }, h('button', { type: 'button', class: 'bouton bouton--secondaire', data: { plus: classe }, on: { click: () => plus(classe, 'plus') } }, R.afficherPlus(Math.min(PAS, total - w.fin), total - w.fin))));
    } else if (tronque) {
      pied.push(h('p', { class: 'note' }, R.listeCoupee(noms, dernier.bilan.limiteParClasse)));
    }
    return h('section', { class: `groupe groupe--${classe}`, data: { classe } },
      h('h2', { class: 'groupe__titre' }, C.titre, ' ', h('span', { class: 'groupe__compte' }, R.compte(noms, tronque ? null : total))),
      h('p', { class: 'groupe__explication' }, C.explication),
      w.debut > 0 ? pied.shift() : null,
      liste,
      pied);
  }

  function plus(classe, action) {
    const totaux = Object.fromEntries(CLASSES.map((c) => [c, dernier.parClasse[c].length]));
    const avant = fenetres[classe].fin;
    fenetres = fenetresDeCartes(totaux, fenetres, { classe, action });
    memoriser({ texte: etat.texte, fenetres });
    dessinerResultats({ viser: false });
    // Keep the reader where they were: on the first card just added, or on the group title.
    const section = zoneResultats.querySelector(`[data-classe="${classe}"]`);
    const cible = action === 'plus' ? section?.querySelectorAll('.cartes > li')[avant - fenetres[classe].debut]?.querySelector('.carte__titre') : section?.querySelector('.groupe__titre');
    if (cible) {
      cible.setAttribute('tabindex', '-1');
      cible.focus({ preventScroll: action === 'plus' });
    }
  }

  function controleAnnee(bilanMoteur) {
    if (!bilanMoteur.annee) return null;
    const y = bilanMoteur.annee;
    const e = bilanMoteur.comptes.ecarteesParAnnee ?? {};
    const ecartees = (e.correspondance ?? 0) + (e['graphie-approchante'] ?? 0) + (e.partielle ?? 0);
    const options = TOLERANCES.filter((t) => t !== y.tolerance).map((t) => h('li', null,
      h('a', { href: formerHash('recherche', [], parametresDepuisEtat({ ...etat, tolerance: t })) }, R.aNAnsPres(t))));
    options.push(h('li', null, h('a', { href: formerHash('recherche', [], parametresDepuisEtat({ ...etat, annee: null, anneeSaisie: '', tolerance: null })) }, R.sansAnnee)));
    return h('div', { class: 'filtre-annee' },
      h('p', null, R.filtreAnnee(y.valeur, y.tolerance, y.de, y.a), ecartees > 0 ? [' ', h('strong', null, R.ecartees(ecartees))] : null),
      h('ul', { class: 'filtre-annee__choix', aria: { label: R.elargir } }, options));
  }

  function dessinerResultats({ viser }) {
    const { bilan: bilanMoteur, parClasse, composition, res, fidele } = dernier;
    const comptes = bilanMoteur.comptes;
    const aucunTerme = bilanMoteur.termes.length === 0;
    const total = comptes.total ?? 0;
    const ctxFiche = { liens: res.liens, guides: res.guides, vocabulaire: res.vocabulaire, bilan: res.bilan, couverture: donnees.etat().resume.couverture };
    const notes = avertissements(bilanMoteur.avertissements);

    let h1;
    let resume;
    if (aucunTerme) {
      h1 = titre(R.aucunTermeTitre);
      resume = h('p', { class: 'resultats__resume' }, R.aucunTerme);
    } else if (total === 0) {
      // Nothing found: the sentence of the content file, whole, then the bilan — never a dead end.
      h1 = titre(R.aucuneTitre);
      const [premiere, suite] = enDeuxTemps(composition.resume);
      resume = h('div', { class: 'resultats__resume resultats__resume--aucune' }, h('p', null, texteMixte(premiere)), suite ? h('p', { class: 'resultats__suite' }, texteMixte(suite)) : null);
    } else {
      const pleines = (comptes.parClasse.correspondance ?? 0) + (comptes.parClasse['graphie-approchante'] ?? 0);
      h1 = titre(pleines > 0 ? R.titre(pleines) : R.titrePartielles(comptes.parClasse.partielle ?? 0));
      resume = h('p', { class: 'resultats__resume' }, texteMixte(composition.resume));
    }
    // Screen readers: the heading is read when it takes the focus; otherwise announce the count.
    annonce.textContent = viser === true ? '' : h1.textContent;

    const versBilan = (cible, libelle, classe) => h('button', {
      type: 'button', class: `bouton ${classe}`,
      on: { click: () => viserTitre(zoneBilan.querySelector(cible)) },
    }, h('span', null, libelle), icone('fleche'));

    zoneResultats.dataset.etatRecherche = 'fini';
    remplacer(zoneResultats,
      h1,
      h('p', { class: 'resultats__saisie' }, R.pour, nomEcrit(etat.texte, { class: 'nom' }), etat.annee !== null ? R.neVers(etat.annee) : ''),
      // What changes the meaning of the answer is said before the answer.
      notes.filter((n) => n.important && n.code !== 'aucun-terme').map((n) => avis({ ton: 'attention', role: 'status' }, n.texte)),
      resume,
      notes.filter((n) => !n.important).length > 0 ? avis({ ton: 'info' }, h('ul', { class: 'liste-simple' }, notes.filter((n) => !n.important).map((n) => h('li', null, n.texte)))) : null,
      fidele === false ? avis({ ton: 'attention' }, T.variantes.nonAppliquees) : null,
      etat.coupe ? avis({ ton: 'attention' }, R.saisieCoupee(LONGUEUR_MAX)) : null,
      aucunTerme ? null : controleAnnee(bilanMoteur),
      aucunTerme ? null : h('p', { class: 'resultats__vers-bilan' },
        // Nothing found: the bilan is right below; the useful jump is to the next steps.
        total === 0 ? versBilan('#bilan-que-faire', R.versQueFaire, 'bouton--secondaire') : versBilan('.bilan__titre', R.versLeBilan, 'bouton--lien')),
      aucunTerme ? null : CLASSES.map((c) => groupe(c, parClasse[c], comptes, bilanMoteur.tronque?.[c] === true, ctxFiche)));
    if (viser === 'page') finDeRendu(h1);
    else if (viser) viserTitre(h1);
  }

  function dessinerTete() {
    const { complet, apparentees } = dernier;
    const actif = document.activeElement?.dataset?.cle ?? null;
    const bloc = variantes({
      graphies: complet.graphiesTrouvees,
      apparentees,
      etat,
      ouvert: variantesOuvertes,
      surOuverture: (ouvert) => {
        variantesOuvertes = ouvert;
      },
      surBascule: (rang, sorte, valeurs, ajouter) => {
        const suivant = { ...etat };
        if (sorte === 'exclusion') suivant.exclusions = basculer(etat.exclusions, rang, valeurs, ajouter);
        else suivant.ajouts = basculer(etat.ajouts, rang, valeurs, ajouter);
        variantesOuvertes = true;
        naviguer(suivant, { viser: false, remplacer: true });
      },
    });
    remplacer(zoneVariantes, bloc);
    if (actif) zoneVariantes.querySelector(`[data-cle="${CSS.escape(actif)}"]`)?.focus();
  }

  async function lancer({ viser }) {
    const mien = ++numero;
    if (etat.texte.trim() === '') {
      dessinerVide();
      return;
    }
    if (dernier === null || zoneResultats.dataset.etatRecherche === 'echec') dessinerAttente();
    try {
      const sansExclusions = { ...etat, exclusions: {} };
      const aDesExclusions = Object.keys(etat.exclusions).length > 0;
      const [reponse, complet, res] = await Promise.all([
        donnees.chercher(etat),
        // The full list of spellings, so that an unticked one stays visible and can be ticked again.
        aDesExclusions ? donnees.chercher(sansExclusions, 0) : null,
        chargerRessources(),
      ]);
      if (mien !== numero) return;
      const couverture = donnees.etat().resume.couverture;
      const composition = composerBilan({ bilanMoteur: reponse.bilan, couverture, contenu: res.bilan, etat, ageMinimal: res.aiguillage.age_minimal?.decret });
      const parClasse = grouperParNotice(reponse.correspondances);
      dernier = { ...reponse, complet: (complet ?? reponse).bilan, parClasse, composition, res };
      const totaux = Object.fromEntries(CLASSES.map((c) => [c, parClasse[c].length]));
      // Back on this page through the history: the same cards as when the visitor left it.
      const sauvees = viser === 'page' ? restauration()?.vue : null;
      fenetres = (sauvees?.texte === etat.texte ? fenetresSauvees(sauvees.fenetres, totaux) : null) ?? fenetresDeCartes(totaux);
      memoriser({ texte: etat.texte, fenetres });
      dessinerTete();
      dessinerResultats({ viser });
      if (reponse.bilan.termes.length > 0) {
        remplacer(zoneBilan, dessinerBilan(composition, {
          guides: res.guides, liens: res.liens, couverture, etat, champAnnee: formulaire.champAnnee, aujourdhui: dateLocale(new Date()),
        }));
      } else {
        remplacer(zoneBilan);
      }
    } catch (error) {
      if (mien !== numero) return;
      if (error?.name === 'ErreurDonnees' || error?.name === 'ContenuIndisponible') dessinerEchec(error, { viser });
      else throw error;
    }
  }

  // The index came back after a failure (a retry from another button, the form): search again.
  let phasePrecedente = donnees.etat().phase;
  const desabonner = donnees.abonner((e) => {
    const avant = phasePrecedente;
    phasePrecedente = e.phase;
    if (e.phase === 'pret' && avant !== 'pret' && zoneResultats.dataset.etatRecherche === 'echec' && etat !== null) {
      lancer({ viser: zoneResultats.contains(document.activeElement) });
    }
  });

  function actualiser(route) {
    const precedent = etat;
    etat = etatDepuisParametres(route.params);
    formulaire.remplir(etat);
    if (precedent === null || precedent.texte !== etat.texte) {
      dernier = null;
      variantesOuvertes = false; // another name: its spellings start folded
    }
    const viser = viserApres;
    viserApres = true;
    lancer({ viser }).catch((error) => {
      dessinerEchec(error, { viser });
      throw error;
    });
  }

  return { actualiser, detruire: () => {
    numero++;
    desabonner();
    chargement.detruire();
  } };
}

let instance = null;

export const vueRecherche = {
  asynchrone: true,
  titre(route, { T }) {
    const q = titreCourt(route.params.q);
    return q === '' ? T.resultats.titreDocumentVide : T.resultats.titreDocument(q);
  },
  monter(conteneur, route, contexte) {
    instance = creer(conteneur, contexte);
    instance.actualiser(route);
    return () => {
      instance?.detruire();
      instance = null;
    };
  },
  /** Same page, other parameters (a toggle, a wider year): redraw in place, keep the focus. */
  actualiser(route) {
    if (instance === null) return false;
    instance.actualiser(route);
    return true;
  },
};
