/**
 * One result card = one notice. For the Archives nationales index, the rows of one household
 * (principal, spouse, children) share a card and the persons that matched are marked. The card
 * shows the name EXACTLY as the source writes it, the birth, the decree, the source, and why
 * it matched; opening it draws the full notice (composants/fiche.js), built only then.
 */

import { h, nomEcrit, texteMixte } from './dom.js';
import { carte, champs } from './carte.js';
import { detailFiche, noteNaissance } from './fiche.js';
import { T } from '../textes/index.js';
import { expliquer } from '../logique/explications.js';
import { surligner } from '../logique/menage.js';
import { formaterDate } from '../logique/formats.js';
import { formerHash } from '../routeur.js';

/** The written name, with the matched words marked. */
function nomSurligne(nom, touche) {
  const ecrits = touche ? touche.termes.filter((t) => !t.absent).map((t) => t.ecrit) : [];
  const span = nomEcrit(nom, { class: 'nom' });
  span.replaceChildren(...surligner(nom, ecrits).map((p) => (p.touche ? h('mark', null, p.texte) : document.createTextNode(p.texte))));
  return span;
}

/** Why the notice matched: one line when every term is written as typed, one line per term otherwise. */
function pourquoi(touche) {
  const lignes = expliquer(touche);
  if (lignes.length > 0 && lignes.every((e) => e.identique)) {
    return h('p', { class: 'pourquoi pourquoi--identique' }, texteMixte(T.carte.tousIdentiques(lignes.map((e) => e.ecrit))));
  }
  return h('ul', { class: 'pourquoi' }, lignes.map((e) => h('li', { class: `pourquoi__terme${e.absent ? ' pourquoi__terme--absent' : e.approchant ? ' pourquoi__terme--approchant' : ''}` },
    h('span', { class: 'pourquoi__court' }, texteMixte(e.court)),
    e.detail && !e.absent && !e.identique ? h('span', { class: 'pourquoi__detail' }, ` — ${e.detail}`) : null)));
}

function ecartAnnee(touche) {
  if (!touche?.annee) return null;
  if (touche.annee.inconnue) return T.carte.anneeInconnue;
  if (touche.annee.ecart === 0) return T.carte.anneeExacte;
  return T.carte.ecartAnnee(Math.abs(touche.annee.ecart), touche.annee.ecart > 0);
}

export function lienNotice(fiche, membre) {
  const r = fiche.ref;
  if (!r) return null;
  if (r.source === 'an') {
    const rang = membre ? fiche.membres.findIndex((m) => m.ligne === membre.ligne) : 0;
    return formerHash('notice', ['an', r.inv, r.notice], { m: rang > 0 ? rang : null });
  }
  return formerHash('notice', ['bogga', r.annee, r.feuille, r.rang]);
}

function detailsPares(fiche, contexte) {
  const corps = h('div', { class: 'carte__detail-corps' });
  const details = h('details', { class: 'carte__detail' }, h('summary', null, T.carte.ouvrir), corps);
  let built = false;
  details.addEventListener('toggle', () => {
    if (!details.open || built) return;
    built = true;
    const permalien = lienNotice(fiche);
    corps.append(detailFiche(fiche, { ...contexte, niveau: 4 }),
      permalien ? h('p', { class: 'carte__permalien' }, h('a', { href: permalien }, T.carte.pageDeLaNotice)) : null);
  });
  return details;
}

function carteAn(fiche, touches, contexte) {
  const C = T.carte;
  const parLigne = new Map(touches.map((t) => [t.ligne, t]));
  const premier = fiche.membres.find((m) => parLigne.has(m.ligne)) ?? fiche.membres[0];
  const touche = parLigne.get(premier.ligne) ?? null;
  const principal = fiche.membres[0];
  const d = fiche.decret;
  const naissance = [];
  if (Number.isInteger(premier.an)) naissance.push(C.neEn(premier.an));
  if (premier.lieu) naissance.push(C.a(premier.lieu));
  const notes = [noteNaissance(premier.prec), ecartAnnee(touche)].filter(Boolean);
  const autres = fiche.membres.filter((m) => m.ligne !== premier.ligne);
  const ligne = (classe, ...contenu) => h('span', { class: classe }, contenu);
  return carte({
    niveau: 3,
    classe: 'carte--notice',
    attributs: { data: { cle: fiche.cle, source: 'an' } },
    titre: nomSurligne(premier.nom ?? T.fiche.nomNonSaisi, touche),
  },
  premier.role !== 'principal'
    ? h('p', { class: 'carte__lien-menage' }, T.fiche.rolesDans[premier.role] ?? '', ' ', principal.nom ? nomEcrit(principal.nom, { class: 'nom' }) : T.fiche.nomNonSaisi)
    : null,
  champs([
    [C.naissance, [
      ligne('carte__valeur', naissance.length > 0 ? naissance.join(C.separateurLieu) : C.naissanceAbsente),
      notes.length > 0 ? ligne('note carte__note', notes.join(' ; ')) : null,
    ]],
    [C.decret, d ? [
      ligne('carte__valeur carte__valeur--decret', d.date ? C.decretDu(formaterDate(d.date)) : C.decretSansDate(d.annee)),
      d.titre ? ligne('carte__titre-epoque', h('q', { class: 'source-brute' }, d.titre)) : null,
      ligne('note carte__note', T.fiche.familles[d.famille] ?? d.famille),
    ] : null],
    [C.source, T.sources.an.long],
  ], { classe: 'champs--carte' }),
  touche ? [h('p', { class: 'carte__sous-titre' }, C.pourquoi), pourquoi(touche)] : null,
  autres.length > 0 ? [
    h('p', { class: 'carte__sous-titre' }, C.memeNotice),
    h('ul', { class: 'menage' }, autres.map((m) => {
      const t = parLigne.get(m.ligne) ?? null;
      return h('li', { class: t ? 'menage__membre menage__membre--touche' : 'menage__membre' },
        h('span', { class: 'menage__role' }, T.fiche.roles[m.role] ?? m.role), ' ',
        m.nom ? nomSurligne(m.nom, t) : h('em', null, T.fiche.nomNonSaisi),
        Number.isInteger(m.an) ? h('span', { class: 'note' }, ` (${m.an})`) : null,
        t ? pourquoi(t) : null);
    })),
  ] : null,
  detailsPares(fiche, contexte));
}

function carteBogga(fiche, touches, contexte) {
  const C = T.carte;
  const touche = touches[0] ?? null;
  const d = fiche.decret;
  const vol = fiche.volume;
  const naissance = [];
  if (Number.isInteger(fiche.naissance)) naissance.push(C.neEn(fiche.naissance));
  const notes = [Number.isInteger(fiche.naissance) ? C.anneeLueParMachine : null, ecartAnnee(touche)].filter(Boolean);
  const dates = (d?.dates ?? []).filter((x) => typeof x === 'string').map(formaterDate);
  const ligne = (classe, ...contenu) => h('span', { class: classe }, contenu);
  return carte({
    niveau: 3,
    classe: 'carte--notice carte--bogga',
    attributs: { data: { cle: fiche.cle, source: 'bogga' } },
    titre: nomSurligne(fiche.nom ?? '', touche),
  },
  champs([
    [C.naissance, [
      ligne('carte__valeur', naissance.length > 0 ? naissance.join(' ') : C.naissanceNonImprimee),
      notes.length > 0 ? ligne('note carte__note', notes.join(' ; ')) : null,
    ]],
    [C.residence, fiche.residence],
    [C.decret, d ? [
      ligne('carte__valeur carte__valeur--decret', dates.length > 0 ? C.decretDu(dates.join(T.formats.et)) : C.decretDateIllisible),
      ligne('note carte__note', [T.fiche.natures[d.nature] ?? d.nature, d.dateEtat !== 0 && dates.length > 0 ? C.dateAVerifier : null].filter(Boolean).join(' ; ')),
    ] : null],
    [C.source, [
      ligne('carte__valeur', T.sources.bogga.long),
      vol ? ligne('note carte__note', C.volumeEtPage(vol.annee, fiche.page)) : null,
    ]],
  ], { classe: 'champs--carte' }),
  fiche.drapeaux.some((f) => f.bit === 64 || f.bit === 4)
    ? h('p', { class: 'note' }, fiche.drapeaux.filter((f) => f.bit === 64 || f.bit === 4).map((f) => f.libelle).join(' ; '))
    : null,
  touche ? [h('p', { class: 'carte__sous-titre' }, C.pourquoi), pourquoi(touche)] : null,
  detailsPares(fiche, contexte));
}

/**
 * @param {Object} fiche     a fiche of the data layer
 * @param {Object[]} touches the correspondences that fall on this fiche (best first)
 * @param {Object} contexte  what composants/fiche.js needs: {liens, guides, vocabulaire, bilan, couverture}
 * @returns {HTMLElement}
 */
export function carteResultat(fiche, touches, contexte) {
  return fiche.source === 'an' ? carteAn(fiche, touches, contexte) : carteBogga(fiche, touches, contexte);
}
