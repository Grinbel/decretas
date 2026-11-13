/**
 * The « Bilan de recherche », drawn from the structure assembled by logique/bilan.js. It
 * always follows the results — and is the result when nothing is found: what was searched,
 * how, what was not and why, and what to do now. Printable.
 */

import { h, icone, nomEcrit, texteMixte } from './dom.js';
import { aConfirmer, avis } from './avis.js';
import { lienExterne } from './lien-externe.js';
import { T } from '../textes/index.js';
import { compacterAnnees, enoncerAnnees, formaterDate, formaterNombre } from '../logique/formats.js';
import { lienPageBulletin } from '../logique/liens.js';
import { formerHash } from '../routeur.js';

function liensGuides(guides, ids) {
  const list = (ids ?? []).map((id) => (guides?.guides ?? []).find((g) => g.id === id)).filter(Boolean);
  if (list.length === 0) return null;
  return h('ul', { class: 'liens-internes' }, list.map((g) => h('li', null,
    h('a', { href: formerHash('guides', [g.id]) }, icone('fleche'), h('span', null, g.titre)))));
}

function queFaire(bilan, { guides, liens, couverture, champAnnee }) {
  const B = T.bilan;
  const c = bilan.conseils;
  const items = [];
  if (c.naissance === null) {
    items.push(h('li', null, h('p', null, B.sansAnnee),
      champAnnee ? h('p', null, h('button', { type: 'button', class: 'bouton bouton--lien', on: { click: () => champAnnee.focus() } }, B.indiquerAnnee)) : null));
  } else if (c.horsSources) {
    const apres = bilan.nonCouvert.lignes.find((l) => l.id === 'apres-1948');
    items.push(h('li', null, h('p', null, B.fenetreHorsSources(c.naissance, c.tolerance, bilan.ageMinimal, c.anneeMin, apres?.titre ?? null))));
  } else {
    items.push(h('li', null, h('p', null, B.fenetre(c.naissance, c.tolerance, bilan.ageMinimal, c.anneeMin, c.fenetre.de, c.fenetre.a))));
    if (c.imagesSeules.length > 0) {
      const decrets = (couverture.an.annees ?? []).filter((y) => c.imagesSeules.includes(y.annee)).reduce((sum, y) => sum + (y.algDecrets ?? 0), 0);
      items.push(h('li', { class: 'a-faire a-faire--principal' },
        h('p', null, h('strong', null, B.imagesTitre(enoncerAnnees(c.imagesSeules))), ' ', B.imagesTexte(decrets)),
        h('p', null, h('a', { class: 'bouton bouton--secondaire', href: formerHash('decrets', [], { annees: compacterAnnees(c.imagesSeules), ne: c.naissance, tol: c.tolerance || null }) },
          h('span', null, B.imagesLien), icone('fleche'))),
        liensGuides(guides, ['an-annee-en-images'])));
    }
    if (c.nomsAuxAn.length > 0) {
      const inventaires = (couverture.an.annees ?? []).filter((y) => c.nomsAuxAn.includes(y.annee)).flatMap((y) => y.inventaires.map((inv) => ({ ...inv, annee: y.annee })));
      items.push(h('li', { class: 'a-faire' },
        h('p', null, h('strong', null, B.nomsAuxAnTitre(enoncerAnnees(c.nomsAuxAn))), ' ', B.nomsAuxAnTexte),
        liens && inventaires.length > 0 ? h('details', { class: 'repli' },
          h('summary', null, B.inventairesParAnnee(inventaires.length)),
          h('ul', { class: 'liens' }, inventaires.map((inv) => h('li', null,
            lienExterne(liens, 'an-inventaire', { inventaire: inv.inv }, { libelle: inv.trim ? B.inventaireTrimestre(inv.annee, inv.trim) : B.inventaireAnnee(inv.annee) }))))) : null,
        liensGuides(guides, ['an-noms-sur-le-site-des-an'])));
    }
    if (c.lues.length > 0 || c.bulletinLu.length > 0) {
      const parts = [];
      if (c.lues.length > 0) parts.push(B.dejaLuesAn(enoncerAnnees(c.lues)));
      if (c.bulletinLu.length > 0) parts.push(B.dejaLuesBulletin(enoncerAnnees(c.bulletinLu)));
      items.push(h('li', { class: 'a-faire' }, h('p', null, h('strong', null, B.dejaFouille), ' ', parts.join(' '))));
    }
    if (c.bulletinAbsent.length > 0) {
      items.push(h('li', { class: 'a-faire' }, h('p', null, h('strong', null, B.bulletinAbsentTitre(enoncerAnnees(c.bulletinAbsent))), ' ', B.bulletinAbsentTexte),
        liensGuides(guides, ['bogga-internet-archive'])));
    }
  }
  if (bilan.rappelJugement) {
    items.push(h('li', { class: 'a-faire' }, h('p', null, h('strong', null, bilan.rappelJugement.titre), ' ', bilan.rappelJugement.texte),
      liensGuides(guides, bilan.rappelJugement.guides)));
  }
  return h('section', { class: 'bilan__bloc bilan__bloc--que-faire' },
    h('h3', { id: 'bilan-que-faire' }, B.titres.queFaire),
    h('ul', { class: 'a-faire-liste' }, items),
    h('h4', null, bilan.demarches.titre),
    h('ul', { class: 'demarches' }, (bilan.demarches.lignes ?? []).map((l) => h('li', null, h('p', null, l.texte), liensGuides(guides, l.guides)))));
}

/**
 * @param {Object} bilan     result of logique/bilan.js#composerBilan
 * @param {Object} contexte  {guides, liens, couverture, etat, champAnnee?, aujourdhui?: string (ISO date)}
 * @returns {HTMLElement}
 */
export function dessinerBilan(bilan, contexte) {
  const B = T.bilan;
  const { guides, liens, etat } = contexte;
  const idTitre = 'bilan-titre';

  const fouille = h('section', { class: 'bilan__bloc' },
    h('h3', null, bilan.fouille.titre),
    h('ul', { class: 'bilan__liste' }, bilan.fouille.lignes.map((l) => h('li', null, h('p', null, l.texte), l.precisions.map((p) => h('p', { class: 'note' }, p))))),
    h('p', { class: 'note' }, bilan.fouille.note));

  // Rows are the classes and columns the sources: two short columns fit a phone, four do not.
  const comment = h('section', { class: 'bilan__bloc' },
    h('h3', null, B.titres.comment),
    // In its own frame: on a narrow screen, or with enlarged text, it scrolls inside the bilan
    // instead of pushing the page sideways.
    h('div', { class: 'tableau-cadre', tabindex: '0', role: 'region', aria: { label: B.parSource } },
      h('table', { class: 'tableau' },
        h('caption', null, B.parSource),
        h('thead', null, h('tr', null, h('th', { scope: 'col' }, h('span', { class: 'sr' }, B.colClasse)), bilan.parSource.map((s) => h('th', { scope: 'col' }, B.colonnesSources[s.groupe] ?? s.libelle)))),
        h('tbody', null, [['correspondance', 'correspondance'], ['graphie-approchante', 'approchante'], ['partielle', 'partielle']].map(([classe, champ]) => h('tr', null,
          h('th', { scope: 'row' }, T.classes[classe].court),
          bilan.parSource.map((s) => h('td', null, formaterNombre(s[champ])))))))),
    h('details', { class: 'repli' },
      h('summary', null, B.reglesAppliquees(bilan.regles.length)),
      h('ul', { class: 'bilan__liste' }, bilan.regles.map((r) => h('li', null, texteMixte(r))))),
    bilan.graphies.some((g) => g.graphies.length > 0) ? h('details', { class: 'repli' },
      h('summary', null, B.graphiesTrouvees),
      h('dl', { class: 'champs' }, bilan.graphies.map((g) => h('div', { class: 'champs__ligne' },
        h('dt', null, nomEcrit(g.terme)),
        h('dd', null, g.graphies.length === 0 ? B.aucuneGraphie : g.graphies.map((x, i) => [i > 0 ? T.formats.virgule : '', nomEcrit(x.graphie), ` (${formaterNombre(x.occurrences)}${x.approchante ? B.suffixeApprochante : ''})`]), g.tronque ? ' …' : ''))))) : null);

  // One line per thing not covered: the title says what; opening it says why and what to do.
  // (Everything is opened for printing: see app.js.)
  const nc = bilan.nonCouvert;
  const pages = nc.pagesALireALaMain;
  const nonCouvert = h('section', { class: 'bilan__bloc' },
    h('h3', null, nc.titre),
    h('p', { class: 'note bilan__aide-ecran' }, B.nonCouvertAide),
    h('ul', { class: 'non-couvert' }, nc.lignes.map((l) => h('li', { class: 'non-couvert__ligne', data: { id: l.id } },
      h('details', null,
        h('summary', { class: 'non-couvert__titre' }, h('span', null, l.titre)),
        h('div', { class: 'non-couvert__corps' },
          h('p', null, l.texte, ' ', l.pourquoi),
          h('p', null, h('strong', null, B.queFaireEtiquette), ' ', l.queFaire),
          aConfirmer(l.verification),
          liensGuides(guides, l.guides))))),
    (pages.length > 0 || nc.volumesSansDecret.length > 0 || nc.anneesAbsentes.length > 0) ? h('li', { class: 'non-couvert__ligne', data: { id: 'bulletin-limites' } }, h('details', null,
      h('summary', { class: 'non-couvert__titre' }, h('span', null, B.detailBulletin(pages.length))),
      h('div', { class: 'non-couvert__corps' },
        nc.avertissementsBulletin.length > 0 ? h('ul', { class: 'bilan__liste' }, nc.avertissementsBulletin.map((a) => h('li', null, a))) : null,
        pages.length > 0 ? [
          h('p', { class: 'repli__sous-titre' }, B.pagesALaMain),
          h('ul', { class: 'liens' }, pages.map((p) => {
            const lien = liens && p.volume && Number.isInteger(p.feuille) ? lienPageBulletin(liens, p.volume, p.feuille) : null;
            const libelle = B.pageALire(p.annee, p.page);
            return h('li', null,
              lien && lien.url ? lienExterne(liens, lien.id, { identifiant: p.volume.item, volume: p.volume.doc, feuillet: p.feuille }, { libelle }) : h('span', null, libelle),
              p.raison ? h('span', { class: 'note' }, p.raison) : null);
          })),
        ] : null,
        nc.volumesSansDecret.length > 0 || nc.anneesAbsentes.length > 0 ? [
          h('p', { class: 'repli__sous-titre' }, B.anneesSansRien),
          h('ul', { class: 'bilan__liste' }, [...nc.volumesSansDecret, ...nc.anneesAbsentes].sort((x, y) => x.annee - y.annee).map((y) => h('li', null, h('strong', null, T.formats.etiquette(y.annee)), y.texte))),
        ] : null))) : null));

  const gardes = bilan.misesEnGarde ? h('section', { class: 'bilan__bloc' },
    h('h3', null, bilan.misesEnGarde.titre),
    h('p', null, bilan.misesEnGarde.texte),
    h('ul', { class: 'bilan__liste' }, (bilan.misesEnGarde.points ?? []).map((p) => h('li', null, p.texte)))) : null;

  const tronques = Object.entries(bilan.tronque).filter(([, v]) => v).map(([k]) => T.classes[k]?.titre ?? k);

  return h('section', { class: 'bilan', aria: { labelledby: idTitre } },
    h('div', { class: 'bilan__tete' },
      h('h2', { id: idTitre, class: 'bilan__titre' }, B.titre),
      h('button', { type: 'button', class: 'bouton bouton--secondaire bilan__imprimer', on: { click: () => window.print() } }, icone('imprimer'), h('span', null, B.imprimer))),
    h('p', { class: 'bilan__principe' }, bilan.principe),
    h('p', { class: 'bilan__objet' }, B.objetDebut, nomEcrit(etat.texte, { class: 'nom' }), B.objetFin(etat.annee, contexte.aujourdhui ? formaterDate(contexte.aujourdhui) : null)),
    tronques.length > 0 ? avis({ ton: 'info' }, B.tronque(tronques, bilan.limiteParClasse)) : null,
    fouille,
    comment,
    nonCouvert,
    queFaire(bilan, contexte),
    gardes,
    h('p', { class: 'bilan__pied' }, bilan.pied));
}
