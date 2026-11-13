/**
 * Entry point: builds the shared context, registers the views, starts the router.
 * See js/README.md for the map of the modules and how to add a page.
 */

import { T, langue, direction } from './textes/index.js';
import { h, icone, remplacer, viserTitre } from './composants/dom.js';
import { demarrerRouteur, formerHash } from './routeur.js';
import { enregistrer, trouver } from './vues/registre.js';
import { creerClientDonnees } from './donnees/client.js';
import { creerContenu } from './donnees/contenu.js';
import { creerDonneesLegeres } from './donnees/legeres.js';
import { creerCarnet } from './donnees/carnet.js';
import { avecPosition, lirePosition } from './logique/position.js';
import { vueAccueil } from './vues/accueil.js';
import { vueRecherche } from './vues/recherche.js';
import { vueNotice } from './vues/notice.js';
import { vueGuides } from './vues/guides.js';
import { vueQuelActe } from './vues/quel-acte.js';
import { vueDecrets } from './vues/decrets.js';
import { vueNumero } from './vues/numero.js';
import { vueActes } from './vues/actes.js';
import { vueVocabulaire } from './vues/vocabulaire.js';
import { vueMethode } from './vues/methode.js';
import { vueAPropos } from './vues/a-propos.js';

// ----- views ---------------------------------------------------------------------------------
enregistrer('', vueAccueil);
enregistrer('recherche', vueRecherche);
enregistrer('notice', vueNotice);
enregistrer('guides', vueGuides);
enregistrer('quel-acte', vueQuelActe);
enregistrer('decrets', vueDecrets);
enregistrer('numero', vueNumero);
enregistrer('actes', vueActes);
enregistrer('vocabulaire', vueVocabulaire);
enregistrer('a-propos', vueAPropos);
enregistrer('methode', vueMethode);

// ----- shell ---------------------------------------------------------------------------------
document.documentElement.lang = langue;
document.documentElement.dir = direction;

const principal = document.getElementById('contenu');
// The skip link must not change the hash (the hash is the route): it moves the focus itself.
document.querySelector('.evitement')?.addEventListener('click', (event) => {
  event.preventDefault();
  principal.focus();
});
const entete = document.getElementById('entete');
const pied = document.getElementById('pied');

const NAVIGATION = [
  { nom: '', libelle: T.app.nav.recherche },
  { nom: 'quel-acte', libelle: T.app.nav.quelActe },
  { nom: 'guides', libelle: T.app.nav.guides },
  { nom: 'a-propos', libelle: T.app.nav.aPropos },
];
const PIED = [
  { nom: 'actes', libelle: T.app.nav.actes },
  { nom: 'vocabulaire', libelle: T.app.nav.vocabulaire },
  { nom: 'methode', libelle: T.app.nav.methode },
  { nom: 'a-propos', libelle: T.app.nav.aPropos },
];

const liensNav = NAVIGATION.map((item) => h('a', { href: formerHash(item.nom), data: { vue: item.nom } }, item.libelle));
const liste = h('ul', { class: 'nav__liste', id: 'nav-liste' }, liensNav.map((a) => h('li', null, a)));
const bascule = h('button', { type: 'button', class: 'nav__bascule', aria: { expanded: 'false', controls: 'nav-liste' } }, T.app.menu);
bascule.addEventListener('click', () => {
  const open = bascule.getAttribute('aria-expanded') !== 'true';
  bascule.setAttribute('aria-expanded', String(open));
  liste.classList.toggle('nav__liste--ouverte', open);
});
// Escape closes the open menu and gives the focus back to its button.
entete.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape' || bascule.getAttribute('aria-expanded') !== 'true') return;
  bascule.setAttribute('aria-expanded', 'false');
  liste.classList.remove('nav__liste--ouverte');
  bascule.focus();
});
// The search is one tap away on every page, also on a phone where the navigation is folded.
// On the home page itself the shortcut goes to the name field.
const raccourci = h('a', { class: 'entete__chercher', href: formerHash('') }, icone('loupe'), h('span', null, T.app.chercher));
raccourci.addEventListener('click', (event) => {
  const champ = courante.nom === '' ? principal.querySelector('input[name="q"]') : null;
  if (champ) {
    event.preventDefault();
    champ.focus();
  }
});
remplacer(entete,
  h('a', { class: 'marque', href: formerHash('') }, h('span', { class: 'marque__nom' }, T.app.nom), h('span', { class: 'marque__devise' }, T.app.devise)),
  h('div', { class: 'entete__actions' }, raccourci, bascule),
  h('nav', { class: 'nav', aria: { label: T.app.navigation } }, liste));
remplacer(pied,
  h('p', { class: 'pied__independance' }, T.app.independance),
  h('p', { class: 'pied__credits' }, T.app.credits, ' ', h('a', { href: formerHash('a-propos') }, T.app.creditsLien)),
  h('nav', { aria: { label: T.app.navigationPied } }, h('ul', { class: 'pied__liens' }, PIED.map((item) => h('li', null, h('a', { href: formerHash(item.nom) }, item.libelle))))),
  h('p', { class: 'pied__vie-privee' }, T.app.viePrivee));

// ----- context shared by every view ------------------------------------------------------------
const contexte = {
  T,
  donnees: creerClientDonnees(),
  contenu: creerContenu(),
  // the decrees and the coverage without the names (decree browser, citation checker, method)
  leger: creerDonneesLegeres(),
  // « décrets déjà lus »: created on first use only, so that no page touches browser storage
  // unless the visitor opens the decree browser
  carnet: () => {
    carnet ??= creerCarnet();
    return carnet;
  },
  aller: (hash, options) => {
    memoriserPosition();
    routeur.aller(hash, options);
  },
  /** True when this tab already showed another page of the site: "back" stays on the site. */
  retourPossible: () => pagesVues > 1,
  /**
   * To be called by a view once its content is drawn (after its own downloads):
   *   - back on a page through the history: the reader is put back where they were;
   *   - after a navigation inside the site: the focus goes to "cible" (default: the h1);
   *   - on the first page of a visit (typed address, shared link, reload): nothing moves, so
   *     that the site header stays in view and the skip link stays the first Tab stop —
   *     unless "ancre" says the address itself names a place in the page (#/actes/T7).
   */
  finDeRendu: (cible = null, { ancre = false } = {}) => finDeRendu(cible, ancre),
  /** What the view wants found again on "back" (merged into this page's history entry). */
  memoriser: (vue) => ecrirePosition({ vue }),
  /** What was saved for this page when the visitor comes back to it through the history. */
  restauration: () => positionDeLEntree,
  /** Draw the current page again from scratch (the « Réessayer » of a page that failed). */
  remonter: () => {
    courante.demonter?.();
    courante = { nom: null, vue: null, demonter: null };
    afficher(routeur.route());
  },
};

let carnet = null;
let courante = { nom: null, vue: null, demonter: null };
let pagesVues = 0;

// ----- the reader's place on a page, for the browser's "back" -----------------------------------
// The browser cannot restore the scroll of a page that draws itself after its downloads: the
// site keeps it in each history entry (logique/position.js) and puts it back itself.
try {
  window.history.scrollRestoration = 'manual';
} catch (error) {
  if (!(error instanceof TypeError)) throw error;
}
let positionDeLEntree = null; // what the entry shown held when it was opened
let aRestaurer = null;        // the same, until the view has drawn itself
const pause = () => new Promise((resolve) => { window.setTimeout(resolve, 0); });

function ecrirePosition(patch) {
  try {
    window.history.replaceState(avecPosition(window.history.state, patch), '');
  } catch (error) {
    // a browser may refuse too many replaceState calls in a row: the position is a convenience
    if (error?.name !== 'SecurityError' && error?.name !== 'DataCloneError') throw error;
  }
}

function memoriserPosition(cible) {
  if (aRestaurer !== null) return; // the page is still being put back: do not overwrite what it needs
  const ouverts = [...principal.querySelectorAll('.carte__detail[open]')].map((d) => d.closest('[data-cle]')?.dataset.cle).filter(Boolean);
  ecrirePosition(cible === undefined ? { y: window.scrollY, ouverts } : { y: window.scrollY, ouverts, cible });
}

let minuteurPosition = null;
const memoriserBientot = () => {
  window.clearTimeout(minuteurPosition);
  minuteurPosition = window.setTimeout(() => memoriserPosition(), 300);
};
window.addEventListener('scroll', memoriserBientot, { passive: true });
principal.addEventListener('toggle', memoriserBientot, true);
// The link followed inside a card or a decree: focus comes back to it on "back".
principal.addEventListener('click', (event) => {
  const a = event.target instanceof Element ? event.target.closest('a[href]') : null;
  if (!a || !principal.contains(a)) return;
  const porteur = a.closest('[data-cle]');
  memoriserPosition(porteur ? { cle: porteur.dataset.cle, href: a.getAttribute('href') } : null);
}, true);

async function restaurerPosition(position) {
  for (const cle of position.ouverts) {
    const details = principal.querySelector(`[data-cle="${CSS.escape(cle)}"] .carte__detail`);
    if (details) details.open = true;
  }
  // the cards draw their content on "toggle", a task after this one
  await pause();
  await pause();
  window.scrollTo(0, position.y);
  const porteur = position.cible ? principal.querySelector(`[data-cle="${CSS.escape(position.cible.cle)}"]`) : null;
  const lien = porteur && position.cible.href ? [...porteur.querySelectorAll('a[href]')].find((a) => a.getAttribute('href') === position.cible.href) : null;
  (lien ?? porteur?.querySelector('a[href], summary'))?.focus({ preventScroll: true });
}

function finDeRendu(cible, ancre) {
  const position = aRestaurer;
  aRestaurer = null;
  if (position !== null) {
    restaurerPosition(position);
    return;
  }
  if (pagesVues > 1 && !principal.contains(document.activeElement)) viserTitre(cible ?? principal.querySelector('h1'));
  else if (pagesVues <= 1 && ancre && cible) viserTitre(cible);
}

function afficher(route) {
  pagesVues += 1;
  const vue = trouver(route.nom);
  for (const a of liensNav) {
    if (a.dataset.vue === route.nom || (route.nom === 'recherche' && a.dataset.vue === '') || (route.nom === 'notice' && a.dataset.vue === '')) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  }
  bascule.setAttribute('aria-expanded', 'false');
  liste.classList.remove('nav__liste--ouverte');

  if (vue === null) {
    courante.demonter?.();
    courante = { nom: null, vue: null, demonter: null };
    document.title = T.app.titreDocument(T.app.pageInconnue.titre);
    remplacer(principal, h('div', { class: 'vue' }, h('h1', null, T.app.pageInconnue.titre), h('p', null, T.app.pageInconnue.texte), h('p', null, h('a', { href: formerHash('') }, T.app.pageInconnue.retour))));
    return;
  }
  document.title = T.app.titreDocument(vue.titre(route, contexte));
  // Same page, other parameters: let the view redraw in place (it keeps the focus where it is).
  if (courante.vue === vue && typeof vue.actualiser === 'function' && vue.actualiser(route, contexte) !== false) return;
  courante.demonter?.();
  // An entry the visitor comes back to holds a position; a new entry holds none.
  positionDeLEntree = lirePosition(window.history.state);
  aRestaurer = positionDeLEntree;
  remplacer(principal);
  window.scrollTo(0, 0);
  const demonter = vue.monter(principal, route, contexte);
  courante = { nom: route.nom, vue, demonter: typeof demonter === 'function' ? demonter : null };
  // A view that draws itself at once is done; the others call finDeRendu() when they are.
  if (vue.asynchrone !== true) finDeRendu(null, false);
}

// Paper cannot be unfolded: everything that is collapsed on screen is opened for printing,
// then closed again as it was.
let ouvertsPourImpression = [];
window.addEventListener('beforeprint', () => {
  ouvertsPourImpression = [...principal.querySelectorAll('.bilan details:not([open]), .carte__detail[open] details:not([open]), .vue--notice details:not([open]), .vue--guide details:not([open]), .vue--quel-acte details:not([open]), .vue--actes details:not([open]), .vue--numero details:not([open]), .vue--methode details:not([open]), .vue--decrets details:not([open])')];
  for (const d of ouvertsPourImpression) d.open = true;
});
window.addEventListener('afterprint', () => {
  for (const d of ouvertsPourImpression) d.open = false;
  ouvertsPourImpression = [];
});

// The modules have run: js/demarrage.js stops watching (and the first screen is replaced below).
document.documentElement.dataset.pret = '';
const routeur = demarrerRouteur({ surRoute: afficher });
