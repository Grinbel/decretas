/**
 * « Graphies rapprochées par la recherche » — for each term typed, the spellings present in the
 * sources, with their number of notices, as toggles. A pressed toggle is a spelling the search
 * takes into account; pressing it again sets it aside and re-runs the search. Related names
 * (Mohamed / Mohand…) are offered unpressed: the engine never applies them by itself.
 *
 * The block is a disclosure: closed, it is one line under the field —
 * « Graphies rapprochées par la recherche : Belkassem (26), ≈ Belgacem (12)… » — so that the answer of
 * the search stays in view on a phone; open, it shows the toggles.
 */

import { h, nomEcrit } from './dom.js';
import { T } from '../textes/index.js';
import { formaterNombre, libelleGraphie } from '../logique/formats.js';

const VISIBLES = 8;
const APERCU = 4;

/** The spelling typed itself is not a toggle: it is what is searched. */
const estLaSaisie = (g, x) => x.niveau === 'k0' && x.soudure === null && !x.arabe && x.graphie.toLowerCase() === g.terme.toLowerCase();

/** Only approaching (same consonant skeleton, Arabic input, detached prefix): maybe another name. */
const estApprochante = (x) => x.niveau === 'k2' || x.arabe === true || x.soudure === 'prefixe-source' || x.soudure === 'prefixe-saisie';

/**
 * The spellings to name in the one-line preview: the most frequent ones, all terms together.
 * Pure (no DOM), tested in tests/js/ui-variantes.test.mjs.
 * @param {Object[]} graphies "graphiesTrouvees" of the engine
 * @param {number} [combien]
 * @returns {{graphie: string, occurrences: number, approchante: boolean}[]}
 *          the spellings of the same name first (k0, k1), then the approaching ones, which
 *          are marked: « Mahmoud » for « Mohamed » is a nearby name, not a spelling of it
 */
export function apercuDesGraphies(graphies, combien = APERCU) {
  const all = [];
  (graphies ?? []).forEach((g, rang) => {
    g.graphies.forEach((x, i) => {
      if (!estLaSaisie(g, x)) all.push({ graphie: libelleGraphie(x), occurrences: x.occurrences, approchante: estApprochante(x), rang, i });
    });
  });
  // Same name first, then most frequent; ties keep the engine's order (term, then closeness).
  all.sort((a, b) => Number(a.approchante) - Number(b.approchante) || b.occurrences - a.occurrences || a.rang - b.rang || a.i - b.i);
  return all.slice(0, combien).map(({ graphie, occurrences, approchante }) => ({ graphie, occurrences, approchante }));
}

/**
 * @param {Object} options
 * @param {Object[]} options.graphies     "graphiesTrouvees" of the engine, computed WITHOUT the exclusions
 * @param {Object[][]} options.apparentees related names per term
 * @param {{exclusions: Object, ajouts: Object}} options.etat
 * @param {boolean} [options.ouvert]      draw the disclosure open
 * @param {(ouvert: boolean) => void} [options.surOuverture] the visitor opened or closed it
 * @param {(rang: number, sorte: 'exclusion'|'ajout', valeurs: string[], presse: boolean) => void} options.surBascule
 * @returns {HTMLElement|null} null when there is nothing to offer
 */
export function variantes({ graphies, apparentees, etat, ouvert = false, surOuverture = () => {}, surBascule }) {
  const V = T.variantes;
  const groupes = [];
  let total = 0;
  let ecartees = 0;
  (graphies ?? []).forEach((g, rang) => {
    const exclues = new Set(etat.exclusions?.[rang] ?? []);
    const ajoutees = new Set(etat.ajouts?.[rang] ?? []);
    const autres = g.graphies.filter((x) => !estLaSaisie(g, x));
    const related = (apparentees?.[rang] ?? []);
    if (autres.length === 0 && related.length === 0) return;
    total += autres.length;

    const puce = (x) => {
      const pressed = !x.exclure.some((v) => exclues.has(v));
      if (!pressed) ecartees += 1;
      const approx = estApprochante(x);
      return h('button', {
        type: 'button', class: `graphie${approx ? ' graphie--approchante' : ''}`, aria: { pressed: String(pressed) },
        data: { cle: `${rang}:x:${x.exclure.join('+')}` },
        on: { click: () => surBascule(rang, 'exclusion', x.exclure, pressed) },
      }, nomEcrit(libelleGraphie(x), { class: 'graphie__nom' }), h('span', { class: 'graphie__n' }, formaterNombre(x.occurrences)),
      h('span', { class: 'sr' }, approx ? V.approchante : V.memeNom));
    };
    // A spelling set aside is always drawn, even beyond the first ones: it must stay reachable.
    const premiers = autres.filter((x, i) => i < VISIBLES || x.exclure.some((v) => exclues.has(v)));
    const reste = autres.filter((x) => !premiers.includes(x));
    const liste = h('ul', { class: 'graphies' }, premiers.map((x) => h('li', null, puce(x))));
    if (reste.length > 0) {
      const more = h('li', null, h('button', {
        type: 'button', class: 'graphie graphie--plus', data: { cle: `${rang}:plus` },
        on: {
          click: (event) => {
            const li = event.currentTarget.parentElement;
            const added = reste.map((x) => h('li', null, puce(x)));
            li.replaceWith(...added);
            added[0]?.querySelector('button')?.focus();
          },
        },
      }, V.autres(reste.length)));
      liste.append(more);
    }
    const bloc = h('div', { class: 'variantes__terme' },
      h('p', { class: 'variantes__libelle' }, nomEcrit(g.terme, { class: 'variantes__saisie' }), autres.length > 0 ? V.aussiEcrit : V.sansAutreGraphie));
    if (autres.length > 0) bloc.append(liste);
    if (g.tronque) bloc.append(h('p', { class: 'variantes__note' }, V.tronque));
    if (related.length > 0) {
      bloc.append(h('p', { class: 'variantes__libelle variantes__libelle--apparentes' }, V.apparentes),
        h('ul', { class: 'graphies' }, related.map((r) => {
          const pressed = ajoutees.has(r.graphie);
          return h('li', null, h('button', {
            type: 'button', class: 'graphie graphie--apparentee', aria: { pressed: String(pressed) },
            data: { cle: `${rang}:v:${r.graphie}` },
            on: { click: () => surBascule(rang, 'ajout', [r.graphie], !pressed) },
          }, nomEcrit(r.graphie, { class: 'graphie__nom' }), h('span', { class: 'graphie__n' }, formaterNombre(r.occurrences))));
        })));
    }
    groupes.push(bloc);
  });
  if (groupes.length === 0) return null;

  const apercu = apercuDesGraphies(graphies);
  const resume = h('summary', { class: 'variantes__resume' },
    h('span', { class: 'variantes__entete' },
      // not a heading: this block sits above the <h1> of the page, and the summary names it
      h('span', { class: 'variantes__titre' }, V.titre),
      apercu.length > 0
        ? h('span', { class: 'variantes__apercu' },
          apercu.map((a, i) => [i > 0 ? T.formats.virgule : '',
            a.approchante
              ? h('span', { class: 'graphie-apercu graphie-apercu--approchante' }, h('span', { aria: { hidden: 'true' } }, '≈ '), nomEcrit(a.graphie, { class: 'nom' }), h('span', { class: 'sr' }, V.approchante))
              : nomEcrit(a.graphie, { class: 'nom' }),
            ` (${formaterNombre(a.occurrences)})`]),
          total > apercu.length ? '…' : '',
          ecartees > 0 ? h('span', { class: 'variantes__ecartees' }, V.ecartees(ecartees)) : null)
        : h('span', { class: 'variantes__apercu' }, V.apparentesSeulement)));
  const details = h('details', { class: 'variantes', open: ouvert }, resume,
    h('div', { class: 'variantes__corps' },
      h('p', { class: 'variantes__aide' }, V.aide),
      h('p', { class: 'variantes__aide' }, V.legende),
      groupes));
  details.addEventListener('toggle', () => surOuverture(details.open));
  return details;
}
