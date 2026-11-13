/**
 * #/decrets — the decree browser: the decrees of the Archives nationales that can only be read
 * on their images (no name typed), and those whose names are withheld here, year by year, in the
 * order of guide « an-annee-en-images » (step b2). Filters by birth year (+ the legal minimum
 * age), by range of years and by sort of decree; a count per year; for each decree its date, its
 * period title, its call number, its document number, its links (liens.json, plus the exceptions
 * copied from the inventories) and « Comment lire ce décret ».
 *
 * A checklist « décrets déjà lus » is kept in this browser only (donnees/carnet.js), so that a
 * family can read a year over several evenings; #/decrets/lus prints it.
 *
 *   #/decrets?ne=1876                 window from the year the person turned 21
 *   #/decrets?annees=1899-1912,1933   the years named by the bilan
 *   #/decrets?de=1905&a=1910&g=…&annee=1907   range, sorts of decrees, year shown
 *   #/decrets/lus                     the printable checklist
 */

import { h, icone, remplacer, viserTitre } from '../composants/dom.js';
import { avis } from '../composants/avis.js';
import { echecDePage } from '../composants/echec.js';
import { lienExterne, lienParticulier } from '../composants/lien-externe.js';
import { attendreDonneesLegeres, mot } from '../composants/chargement-leger.js';
import { formerHash } from '../routeur.js';
import { compacterAnnees, formaterDate, formaterNombre, lireAnneesCompactes } from '../logique/formats.js';
import { enoncerPeriodes } from '../logique/bilan.js';
import { lireAnnee } from '../logique/requete.js';
import {
  ETATS_A_LIRE, GROUPES, anneesDisponibles, cleDecret, comptesParAnnee, comptesParGroupe, dejaLus, fenetreDemandee,
  filtrerDecrets, groupeDeLecture, lireGroupes,
} from '../logique/decrets.js';
import { parametresPourDecretAn } from '../logique/parametres-guide.js';

const GROUPES_A_LIRE = GROUPES.filter((g) => g !== 'rejets');

/** "tol" of the address: the tolerance the name search used (1 to 100 years), or null. */
function lireTolerance(texte) {
  return /^\d{1,3}$/.test(String(texte ?? '')) && Number(texte) >= 1 && Number(texte) <= 100 ? Number(texte) : null;
}

/** What the address asks for. */
function demande(route) {
  return {
    naissance: lireAnnee(route.params.ne ?? ''),
    tolerance: lireTolerance(route.params.tol),
    de: lireAnnee(route.params.de ?? ''),
    a: lireAnnee(route.params.a ?? ''),
    annees: lireAnneesCompactes(route.params.annees),
    groupes: lireGroupes(route.params.g),
    annee: lireAnnee(route.params.annee ?? ''),
  };
}

/** Parameters of the address for a request (empty values are left out by formerHash). */
function parametres(d, extra = {}) {
  return {
    ne: d.naissance,
    tol: d.naissance !== null && d.tolerance ? d.tolerance : null,
    de: d.de,
    a: d.a,
    annees: d.de === null && d.a === null && d.annees.length > 0 ? compacterAnnees(d.annees) : null,
    g: d.groupes && d.groupes.length < GROUPES_A_LIRE.length ? d.groupes.join(',') : null,
    annee: d.annee,
    ...extra,
  };
}

function noteDate(decret, T) {
  const notes = String(decret.drapDate ?? '').split('+').filter(Boolean).map((x) => T.fiche.drapeauxDate[x] ?? x);
  return notes.length > 0 ? h('span', { class: 'note' }, ` — ${notes.join(' ')}`) : null;
}

function noteCote(decret, T) {
  if (decret.drapCote === 'suspecte-bb11') return h('span', { class: 'decret__alerte' }, T.decrets.coteAVerifier(decret.coteSuggeree));
  return null;
}

/** One decree of the list. */
function ligneDecret(decret, { T, liens, carnet, remarque, surCoche }) {
  const D = T.decrets;
  const cle = cleDecret(decret);
  const id = `lu-${decret.inv}-${decret.notice}`.replace(/[^A-Za-z0-9_-]/g, '_');
  const date = decret.date ? formaterDate(decret.date) : D.sansDate;
  const caseLu = h('input', { type: 'checkbox', id, class: 'decret__case', checked: carnet.estLu(cle) });
  caseLu.addEventListener('change', () => {
    carnet.marquer(cle, caseLu.checked);
    item.classList.toggle('decret--lu', caseLu.checked);
    surCoche();
  });
  const liensDecret = [];
  if (typeof decret.lienNoticeParticulier === 'string') liensDecret.push(lienParticulier(liens, decret.lienNoticeParticulier, D.noticeDecret));
  else if (decret.lienNoticeParticulier !== null) liensDecret.push(lienExterne(liens, 'an-notice', { inventaire: decret.inv, notice: decret.notice }, { libelle: D.noticeDecret, sansRepli: true, sansNote: Boolean(remarque) }));
  if (typeof decret.lienImagesParticulier === 'string') liensDecret.push(lienParticulier(liens, decret.lienImagesParticulier, D.imagesDecret));
  else if (decret.lienImagesParticulier !== null) liensDecret.push(lienExterne(liens, 'an-images-notice', { inventaire: decret.inv, notice: decret.notice }, { libelle: D.imagesDecret, sansRepli: true, sansNote: Boolean(remarque) }));
  const noteCommune = liensDecret.some((el) => el?.dataset.note === 'ailleurs')
    ? h('p', { class: 'decret__note-liens' }, h('span', { class: 'lien-externe__etiquette' }, T.lien.nonVerifie), ' ', remarque) : null;
  const retenu = decret.etat === 'retenu-filae';
  const guide = retenu ? 'an-noms-sur-le-site-des-an' : 'an-annee-en-images';

  const item = h('li', { class: `decret${carnet.estLu(cle) ? ' decret--lu' : ''}`, data: { cle } },
    h('div', { class: 'decret__tete' },
      h('p', { class: 'decret__date' }, h('strong', null, date), noteDate(decret, T)),
      h('p', { class: 'decret__lu' }, caseLu, h('label', { for: id }, D.lu, h('span', { class: 'sr' }, ` — ${date}`)))),
    decret.titre ? h('p', { class: 'decret__titre' }, h('q', { class: 'source-brute' }, decret.titre)) : null,
    h('p', { class: 'decret__references' },
      h('span', null, mot('cote', D.cote), ' ', decret.cote ?? D.coteAbsente), ' ', noteCote(decret, T),
      h('span', { class: 'decret__sep', aria: { hidden: 'true' } }, ' · '),
      h('span', null, decret.doc ? [mot('numero-de-document', D.document), ' ', decret.doc.replace(/^document\s+/, '')] : D.sansDocument)),
    retenu ? h('p', { class: 'decret__retenu' }, D.retenu) : null,
    liensDecret.filter(Boolean).length > 0 ? h('ul', { class: 'liens decret__liens' }, liensDecret.filter(Boolean).map((el) => h('li', null, el))) : null,
    noteCommune,
    h('p', { class: 'decret__guide' }, h('a', { href: formerHash('guides', [guide], parametresPourDecretAn(decret)) }, icone('fleche'), h('span', null, retenu ? D.guideRetenu : D.commentLire))));
  return item;
}

/** The checklist: what it keeps, where, and how to erase it. */
function blocCarnet(carnet, T) {
  const D = T.decrets;
  const compte = h('p', { class: 'carnet__compte', role: 'status', aria: { live: 'polite' } });
  const actions = h('p', { class: 'carnet__actions' });
  const dessiner = (message) => {
    compte.textContent = message ?? D.carnetCompte(carnet.taille());
    const effacer = h('button', { type: 'button', class: 'bouton bouton--lien', disabled: carnet.taille() === 0 }, D.carnetEffacer);
    effacer.addEventListener('click', () => {
      const confirmer = h('button', { type: 'button', class: 'bouton bouton--secondaire carnet__confirmer' }, D.carnetConfirmer);
      const annuler = h('button', { type: 'button', class: 'bouton bouton--lien' }, D.carnetAnnuler);
      confirmer.addEventListener('click', () => {
        carnet.effacer();
        dessiner(D.carnetEfface);
      });
      annuler.addEventListener('click', () => dessiner());
      remplacer(actions, confirmer, ' ', annuler);
      confirmer.focus();
    });
    remplacer(actions, h('a', { class: 'carnet__imprimer', href: formerHash('decrets', ['lus']) }, icone('imprimer'), h('span', null, D.carnetImprimer)), effacer);
  };
  dessiner();
  return {
    element: h('section', { class: 'carnet', aria: { labelledby: 'carnet-titre' } },
      h('h2', { id: 'carnet-titre' }, D.carnetTitre),
      h('p', null, D.carnetTexte),
      carnet.persistant ? null : avis({ ton: 'attention' }, D.carnetNonGarde),
      compte,
      actions),
    actualiser: () => dessiner(),
  };
}

function formulaire(d, fen, disponibles, comptesGroupes, T, aller) {
  const D = T.decrets;
  const champNe = h('input', { id: 'dec-ne', name: 'ne', type: 'text', inputmode: 'numeric', maxlength: '4', class: 'champ__saisie champ__saisie--annee', value: d.naissance ?? '', aria: { describedby: 'dec-ne-aide dec-ne-err' } });
  const erreur = h('p', { id: 'dec-ne-err', class: 'champ__erreur', role: 'alert' });
  const choix = (id, valeur) => h('select', { id, class: 'champ__saisie champ__saisie--choix' }, disponibles.map((y) => h('option', { value: String(y), selected: y === valeur }, String(y))));
  const de = choix('dec-de', fen.de);
  const a = choix('dec-a', fen.a);
  let deTouche = false;
  de.addEventListener('change', () => { deTouche = true; });
  const cases = GROUPES_A_LIRE.filter((g) => comptesGroupes[g] > 0 || (d.groupes ?? []).includes(g)).map((g) => {
    const id = `dec-g-${g}`;
    return h('li', null, h('input', { type: 'checkbox', id, value: g, checked: d.groupes === null || d.groupes.includes(g) }),
      h('label', { for: id }, D.groupesNoms[g], ' ', h('span', { class: 'note' }, `(${formaterNombre(comptesGroupes[g])})`)));
  });
  const form = h('form', { class: 'filtres-decrets', novalidate: true, aria: { label: D.filtres } },
    h('div', { class: 'filtres-decrets__annees' },
      h('div', { class: 'champ' },
        h('label', { class: 'champ__libelle', for: 'dec-ne' }, D.ne),
        champNe,
        h('p', { id: 'dec-ne-aide', class: 'champ__aide' }, D.neAide),
        erreur),
      h('div', { class: 'champ filtres-decrets__plage' },
        h('label', { class: 'champ__libelle', for: 'dec-de' }, D.de), de,
        h('label', { class: 'champ__libelle', for: 'dec-a' }, D.a), a)),
    h('fieldset', { class: 'filtres-decrets__groupes' },
      h('legend', { class: 'champ__libelle' }, D.groupes, ' ', h('span', { class: 'note' }, D.groupesAide)),
      h('ul', { class: 'liste-cases' }, cases)),
    h('button', { type: 'submit', class: 'bouton bouton--principal' }, D.appliquer));
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const brute = champNe.value.trim();
    const naissance = lireAnnee(brute);
    if (brute !== '' && naissance === null) {
      erreur.textContent = D.erreurAnnee;
      champNe.setAttribute('aria-invalid', 'true');
      champNe.focus();
      return;
    }
    const groupes = [...form.querySelectorAll('.liste-cases input:checked')].map((x) => x.value);
    const changeNe = naissance !== d.naissance;
    const nouvelle = {
      naissance,
      tolerance: changeNe ? null : d.tolerance,
      // a new birth year recomputes the start of the window, unless the user chose it
      de: changeNe && !deTouche ? null : Number(de.value),
      a: Number(a.value),
      annees: [],
      groupes: groupes.length === 0 || groupes.length === GROUPES_A_LIRE.length ? null : groupes,
      annee: null,
    };
    aller(formerHash('decrets', [], parametres(nouvelle)));
  });
  return form;
}

function dessinerListe(zone, route, { T, modele, guides, liens, arbre, carnet, aller }) {
  const D = T.decrets;
  const d = demande(route);
  const age = arbre.age_minimal?.decret ?? null;
  const tous = modele.decretsAn({ etats: [...ETATS_A_LIRE] });
  const disponibles = anneesDisponibles(tous);
  const fen = fenetreDemandee(d, disponibles, age);
  const groupes = d.groupes ?? GROUPES_A_LIRE;
  const dansFenetre = filtrerDecrets(tous, { annees: fen.annees, groupes: null });
  const selection = dansFenetre.filter((x) => groupes.includes(groupeDeLecture(x)));
  const rejets = dansFenetre.filter((x) => groupeDeLecture(x) === 'rejets');
  const parAnnee = comptesParAnnee(selection);
  const rejetsParAnnee = comptesParAnnee(rejets);
  const annees = fen.annees.filter((y) => parAnnee.has(y) || rejetsParAnnee.has(y));
  const courante = annees.includes(d.annee) ? d.annee : (annees[0] ?? null);
  const guide = guides.guides.find((g) => g.id === 'an-annee-en-images');
  const b2 = guide?.etapes.find((e) => e.id === 'b2');
  const couverture = modele.couverture();

  // Lead: counts and years from the data.
  const images = tous.filter((x) => x.etat === 'image').length;
  const retenus = tous.filter((x) => x.etat === 'retenu-filae').length;
  const anneesImages = enoncerPeriodes(couverture.an.annees, couverture.an.trimestres, (y) => y.lecture === 'image' || y.lecture === 'image-en-partie');
  const anneesRetenus = enoncerPeriodes(couverture.an.annees, couverture.an.trimestres, (y) => y.lecture === 'noms-aux-an' || (y.lecture === 'image-en-partie' && y.algAvecNoms > 0));

  const lusDansSelection = h('span');
  const cellulesLus = new Map();
  const recompter = () => {
    const lus = new Set(carnet.lus().keys());
    lusDansSelection.textContent = D.lusIci(dejaLus(selection, lus), selection.length);
    for (const [annee, cellule] of cellulesLus) {
      const n = dejaLus(selection.filter((x) => x.annee === annee), lus);
      cellule.textContent = n > 0 ? D.lusCourt(n) : '';
    }
    carnetBloc.actualiser();
  };
  const carnetBloc = blocCarnet(carnet, T);

  const resume = selection.length === 0
    ? avis({ ton: 'neutre' }, D.selectionVide)
    : h('div', { class: 'decrets__resume' },
      h('p', { class: 'decrets__total' }, D.selection(selection.length, fen.annees[0], fen.annees[fen.annees.length - 1], parAnnee.size)),
      h('p', null, lusDansSelection),
      guide ? h('p', null, h('strong', null, D.longueur), ' ', guide.duree) : null,
      guide?.limites?.[1] ? h('p', { class: 'note' }, guide.limites[1]) : null);

  // Years of the window, with their counts: one chip per year, the year shown marked.
  const tableau = annees.length > 0 ? h('nav', { class: 'annees-choix', aria: { label: D.tableauAnnees } },
    h('p', { class: 'annees-choix__titre' }, D.tableauAnnees),
    h('ul', { class: 'pastilles pastilles--annees' }, annees.map((y) => {
      const lus = h('span', { class: 'pastille__lus' });
      cellulesLus.set(y, lus);
      return h('li', null, h('a', { class: 'pastille pastille--annee', href: formerHash('decrets', [], parametres(d, { annee: y })), aria: { current: y === courante ? 'true' : null } },
        h('span', { class: 'pastille__annee' }, String(y)),
        h('span', { class: 'pastille__compte' }, D.aLireCourt(parAnnee.get(y)?.total ?? 0)),
        lus));
    }))) : null;

  // The year shown.
  let blocAnnee = null;
  if (courante !== null) {
    const noteLiens = liens.resoudre('an-notice', {})?.note ?? null;
    const doAnnee = selection.filter((x) => x.annee === courante);
    const rejetsAnnee = rejets.filter((x) => x.annee === courante);
    const options = { T, liens, carnet, remarque: noteLiens ? D.voirRemarque : null, surCoche: () => recompter() };
    const i = annees.indexOf(courante);
    const infos = couverture.an.annees.find((y) => y.annee === courante);
    const inventaires = (infos?.inventaires ?? []).map((inv) => lienExterne(liens, 'an-inventaire', { inventaire: inv.inv }, { libelle: inv.trim ? D.inventaireTrimestre(courante, inv.trim) : D.inventaireAnnee(courante) }));
    const navAnnees = h('nav', { class: 'annees-nav', aria: { label: D.anneesVoisines } },
      i > 0 ? h('a', { href: formerHash('decrets', [], parametres(d, { annee: annees[i - 1] })) }, icone('precedent'), h('span', null, D.anneePrecedente(annees[i - 1]))) : h('span'),
      i < annees.length - 1 ? h('a', { href: formerHash('decrets', [], parametres(d, { annee: annees[i + 1] })) }, h('span', null, D.anneeSuivante(annees[i + 1])), icone('suivant')) : h('span'));
    blocAnnee = h('section', { class: 'annee', aria: { labelledby: 'annee-titre' } },
      h('h2', { id: 'annee-titre', class: 'annee__titre' }, D.anneeTitre(courante, doAnnee.length)),
      inventaires.filter(Boolean).length > 0 ? h('ul', { class: 'liens annee__inventaires' }, inventaires.filter(Boolean).map((el) => h('li', null, el))) : null,
      noteLiens ? h('p', { class: 'annee__remarque' }, h('strong', null, `${D.remarqueLiens} — ${T.lien.nonVerifie}`), ' ', noteLiens, ' ', D.remarqueLiensSuite) : null,
      rejetsAnnee.length > 0 ? h('p', { class: 'note' }, D.rejetsEnFin(rejetsAnnee.length)) : null,
      GROUPES_A_LIRE.map((g) => {
        const liste = doAnnee.filter((x) => groupeDeLecture(x) === g);
        if (liste.length === 0) return null;
        return h('section', { class: 'groupe-decrets' },
          h('h3', { class: 'groupe-decrets__titre' }, D.groupesNoms[g], ' ', h('span', { class: 'groupe__compte' }, `(${formaterNombre(liste.length)})`)),
          D.groupesAides[g] ? h('p', { class: 'note' }, D.groupesAides[g]) : null,
          h('ol', { class: 'decrets' }, liste.map((x) => ligneDecret(x, options))));
      }),
      rejetsAnnee.length > 0 ? h('details', { class: 'groupe-decrets groupe-decrets--rejets' },
        h('summary', null, D.rejetsAPart(rejetsAnnee.length)),
        h('p', { class: 'note' }, D.groupesAides.rejets),
        h('ol', { class: 'decrets' }, rejetsAnnee.map((x) => ligneDecret(x, options)))) : null,
      navAnnees);
  }

  remplacer(zone,
    h('h1', null, D.titre),
    h('p', { class: 'chapeau' }, D.chapeauDonnees(images, anneesImages, retenus, anneesRetenus)),
    b2 ? h('details', { class: 'repli decrets__ordre' },
      h('summary', null, b2.titre),
      h('p', null, b2.instruction),
      h('p', { class: 'note' }, b2.ce_que_l_ecran_montre),
      h('p', null, h('a', { href: formerHash('guides', ['an-annee-en-images']) }, D.guideLien))) : null,
    formulaire(d, fen, disponibles, comptesParGroupe(dansFenetre), T, aller),
    fen.depuisNaissance && d.naissance !== null ? h('p', { class: 'note' }, D.depuisNaissance(d.naissance, d.tolerance ?? 0, age, d.naissance - (d.tolerance ?? 0) + age)) : null,
    resume,
    carnetBloc.element,
    tableau,
    blocAnnee);
  recompter();
  return { courante };
}

/** #/decrets/lus — the checklist, on paper. */
function dessinerLus(zone, { T, modele, carnet }) {
  const L = T.lus;
  const tous = modele.decretsAn({ etats: [...ETATS_A_LIRE] });
  const parCle = new Map(tous.map((x) => [cleDecret(x), x]));
  const lus = carnet.lus();
  const connus = [...lus.keys()].filter((k) => parCle.has(k)).map((k) => parCle.get(k));
  const inconnus = lus.size - connus.length;
  const parAnnee = new Map();
  for (const x of filtrerDecrets(connus, { annees: anneesDisponibles(connus) })) {
    if (!parAnnee.has(x.annee)) parAnnee.set(x.annee, []);
    parAnnee.get(x.annee).push(x);
  }
  const totaux = comptesParAnnee(tous);
  remplacer(zone,
    h('p', { class: 'retour' }, h('a', { href: formerHash('decrets') }, icone('retour'), h('span', null, L.versLaListe))),
    h('h1', null, L.titre),
    h('p', { class: 'chapeau' }, L.chapeau(formaterDate(new Date().toISOString().slice(0, 10)))),
    h('p', null, h('button', { type: 'button', class: 'bouton bouton--secondaire', on: { click: () => window.print() } }, icone('imprimer'), h('span', null, L.imprimer))),
    lus.size === 0 ? avis({ ton: 'neutre' }, L.vide) : null,
    inconnus > 0 ? avis({ ton: 'neutre' }, L.inconnus(inconnus)) : null,
    [...parAnnee.entries()].map(([annee, liste]) => h('section', { class: 'lus-annee' },
      h('h2', null, L.parAnnee(annee, liste.length, totaux.get(annee)?.total ?? liste.length)),
      h('table', { class: 'tableau tableau--lus tableau--empile' },
        h('thead', null, h('tr', null, [L.colDate, L.colTitre, L.colCote, L.colNotice, L.colLuLe].map((c) => h('th', { scope: 'col' }, c)))),
        h('tbody', null, liste.map((x) => h('tr', null,
          h('th', { scope: 'row', data: { libelle: L.colDate } }, x.date ? formaterDate(x.date) : T.decrets.sansDate),
          h('td', { data: { libelle: L.colTitre } }, x.titre ? h('q', { class: 'source-brute' }, x.titre) : ''),
          h('td', { data: { libelle: L.colCote } }, [x.cote ?? T.decrets.coteAbsente, x.doc ? `, ${x.doc}` : ''].join('')),
          h('td', { data: { libelle: L.colNotice } }, `${x.inv} / ${x.notice}`),
          h('td', { data: { libelle: L.colLuLe } }, lus.get(cleDecret(x)) ? formaterDate(lus.get(cleDecret(x))) : ''))))))),
    lus.size > 0 ? h('p', { class: 'note' }, L.rappel) : null);
}

let courant = null; // {zone, contexte, modele, guides, liens, arbre, route}

export const vueDecrets = {
  asynchrone: true,
  titre: (route, { T }) => (route.segments[0] === 'lus' ? T.lus.titreDocument : T.decrets.titreDocument),

  monter(conteneur, route, contexte) {
    const { T, contenu, leger, finDeRendu, remonter } = contexte;
    const zone = h('div', { class: `vue vue--decrets${route.segments[0] === 'lus' ? ' vue--lus' : ''}` });
    conteneur.append(zone);
    let vivant = true;
    const etat = { zone, contexte, route, vivant: () => vivant };
    courant = etat;
    const carnet = contexte.carnet();
    Promise.all([contenu.plusieurs('guides', 'aiguillage'), contenu.liens()]).then(([[guides, arbre], liens]) => {
      if (!vivant) return;
      attendreDonneesLegeres(zone, leger, (modele) => {
        Object.assign(etat, { modele, guides, arbre, liens, carnet });
        if (etat.route.segments[0] === 'lus') dessinerLus(zone, { T, modele, carnet });
        else dessinerListe(zone, etat.route, { T, modele, guides, liens, arbre, carnet, aller: contexte.aller });
        finDeRendu();
      }, { vivant: () => vivant });
    }).catch((error) => {
      if (!vivant) return;
      if (error?.name === 'ContenuIndisponible') echecDePage(zone, { T, erreur: error, remonter, finDeRendu });
      else throw error;
    });
    return () => {
      vivant = false;
      if (courant === etat) courant = null;
    };
  },

  // Another year of the same list: redraw in place and move to the year, not to the top.
  actualiser(route, { T }) {
    const etat = courant;
    if (!etat || !etat.modele || route.segments.length > 0 || etat.route.segments.length > 0) return false;
    const avant = demande(etat.route);
    const apres = demande(route);
    const memeListe = ['naissance', 'tolerance', 'de', 'a'].every((k) => avant[k] === apres[k])
      && avant.annees.join() === apres.annees.join() && String(avant.groupes) === String(apres.groupes);
    if (!memeListe) return false;
    etat.route = route;
    dessinerListe(etat.zone, route, { T, modele: etat.modele, guides: etat.guides, liens: etat.liens, arbre: etat.arbre, carnet: etat.carnet, aller: etat.contexte.aller });
    viserTitre(etat.zone.querySelector('#annee-titre'));
    return true;
  },
};
