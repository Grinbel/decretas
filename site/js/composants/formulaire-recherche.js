/**
 * The search form: ONE large field for the name, a small optional field for the approximate
 * birth year, one button. Used large on the home page and compact above the results.
 * Nothing is sent anywhere: submitting only changes the part of the address after "#".
 */

import { h, estArabe } from './dom.js';
import { T } from '../textes/index.js';
import { lireAnnee } from '../logique/requete.js';

let compteur = 0;

/**
 * @param {Object} options
 * @param {{texte?: string, anneeSaisie?: string}} [options.valeurs]
 * @param {boolean} [options.compact]
 * @param {(saisie: {texte: string, annee: number|null}) => void} options.surSoumission
 * @param {() => void} [options.surIntention]  the user is about to search (focus, typing): start loading the index
 * @returns {{element: HTMLFormElement, champNom: HTMLInputElement, champAnnee: HTMLInputElement, remplir: (v: Object) => void}}
 */
export function formulaireRecherche({ valeurs = {}, compact = false, surSoumission, surIntention = () => {} }) {
  const n = ++compteur;
  const ids = { nom: `rech-nom-${n}`, aideNom: `rech-aide-nom-${n}`, erreurNom: `rech-err-nom-${n}`, annee: `rech-annee-${n}`, aideAnnee: `rech-aide-annee-${n}`, erreurAnnee: `rech-err-annee-${n}` };
  const F = T.formulaire;

  const champNom = h('input', {
    id: ids.nom, name: 'q', type: 'text', class: 'champ__saisie champ__saisie--nom', dir: 'auto',
    autocomplete: 'off', autocapitalize: 'words', autocorrect: 'off', spellcheck: 'false', enterkeyhint: 'search',
    maxlength: '300', required: true, value: valeurs.texte ?? '', aria: { describedby: `${ids.aideNom} ${ids.erreurNom}` },
  });
  const champAnnee = h('input', {
    id: ids.annee, name: 'ne', type: 'text', class: 'champ__saisie champ__saisie--annee', inputmode: 'numeric',
    autocomplete: 'off', maxlength: '4', pattern: '[0-9]{4}', value: valeurs.anneeSaisie ?? '', aria: { describedby: `${ids.aideAnnee} ${ids.erreurAnnee}` },
  });
  const erreurNom = h('p', { id: ids.erreurNom, class: 'champ__erreur', role: 'alert' });
  const erreurAnnee = h('p', { id: ids.erreurAnnee, class: 'champ__erreur', role: 'alert' });

  const marquerLangue = () => {
    if (estArabe(champNom.value)) champNom.setAttribute('lang', 'ar');
    else champNom.removeAttribute('lang');
  };
  marquerLangue();
  champNom.addEventListener('input', () => {
    marquerLangue();
    erreurNom.textContent = '';
    champNom.removeAttribute('aria-invalid');
    surIntention();
  });
  champAnnee.addEventListener('input', () => {
    erreurAnnee.textContent = '';
    champAnnee.removeAttribute('aria-invalid');
  });
  champNom.addEventListener('focus', surIntention);
  champAnnee.addEventListener('focus', surIntention);

  const element = h('form', { class: `recherche${compact ? ' recherche--compacte' : ''}`, role: 'search', novalidate: true, aria: { label: F.titre } },
    h('div', { class: 'champ champ--nom' },
      h('label', { class: 'champ__libelle', for: ids.nom }, F.nom),
      champNom,
      // Above the results the help is kept for screen readers only: the page must get to the answer.
      h('p', { id: ids.aideNom, class: compact ? 'sr' : 'champ__aide' }, compact ? F.aideNomCourte : F.aideNom),
      erreurNom),
    h('div', { class: 'recherche__bas' },
      h('div', { class: 'champ champ--annee' },
        h('label', { class: 'champ__libelle', for: ids.annee }, F.annee),
        champAnnee,
        h('p', { id: ids.aideAnnee, class: compact ? 'sr' : 'champ__aide' }, F.aideAnnee),
        erreurAnnee),
      h('button', { type: 'submit', class: 'bouton bouton--principal recherche__bouton' }, F.chercher)));

  element.addEventListener('submit', (event) => {
    event.preventDefault();
    for (const [champ, erreur] of [[champNom, erreurNom], [champAnnee, erreurAnnee]]) {
      erreur.textContent = '';
      champ.removeAttribute('aria-invalid');
    }
    const texte = champNom.value.trim();
    const brute = champAnnee.value.trim();
    const annee = lireAnnee(brute);
    if (texte === '') {
      erreurNom.textContent = F.erreurNomVide;
      champNom.setAttribute('aria-invalid', 'true');
      champNom.focus();
      return;
    }
    if (brute !== '' && annee === null) {
      erreurAnnee.textContent = F.erreurAnnee;
      champAnnee.setAttribute('aria-invalid', 'true');
      champAnnee.focus();
      return;
    }
    surSoumission({ texte, annee });
  });

  return {
    element,
    champNom,
    champAnnee,
    remplir(v) {
      champNom.value = v.texte ?? '';
      champAnnee.value = v.anneeSaisie ?? '';
      erreurNom.textContent = '';
      erreurAnnee.textContent = '';
      marquerLangue();
    },
  };
}
