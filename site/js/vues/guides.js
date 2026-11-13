/**
 * #/guides — the list of the step-by-step guides; #/guides/<id> — one guide, as numbered steps.
 *
 * A guide accepts parameters in the address, so that a result card or the decree browser opens
 * it filled with ITS decree (#/guides/an-annee-indexee?inventaire=…&notice=…&annee=…): the links
 * of the steps then point to that decree's notice. What the page says about the decree is read
 * in the data (donnees/legeres.js), never in the address: an address can be forged, the data
 * cannot. Progress boxes are kept in memory only. A print button gives the guide on paper.
 */

import { h, icone, remplacer } from '../composants/dom.js';
import { etapesGuide } from '../composants/etapes-guide.js';
import { avis } from '../composants/avis.js';
import { echecDePage } from '../composants/echec.js';
import { champs } from '../composants/carte.js';
import { lienExterne, lienParticulier } from '../composants/lien-externe.js';
import { formerHash } from '../routeur.js';
import { formaterDate } from '../logique/formats.js';
import { lienPageBulletin } from '../logique/liens.js';
import { designeUnDecretAn, designeUnePageBulletin, lireParametresGuide, variablesDeLiens } from '../logique/parametres-guide.js';

/** Guides whose links are filled from a decree of the Archives nationales. */
const GUIDES_AN = new Set(['an-annee-indexee', 'an-annee-en-images', 'an-noms-sur-le-site-des-an', 'numero-a-verifier']);
const GUIDES_BULLETIN = new Set(['bogga-internet-archive']);

function listeDesGuides(guides, T) {
  return [
    h('h1', null, guides.titre),
    h('p', { class: 'chapeau' }, guides.chapeau),
    h('ul', { class: 'liens-internes liens-internes--liste guides-liste' }, guides.guides.map((g) => h('li', null,
      h('a', { href: formerHash('guides', [g.id]) }, h('span', null, g.titre)),
      h('p', { class: 'note' }, g.pour_qui)))),
  ];
}

/** The decree the parameters designate, as the data knows it, or null. */
function trouverDecret(modele, p) {
  if (!modele || !designeUnDecretAn(p)) return null;
  const annee = Number(p.annee);
  const candidats = modele.decretsAn(Number.isInteger(annee) ? { annees: [annee] } : {});
  return candidats.find((d) => d.inv === p.inventaire && d.notice === p.notice)
    ?? (Number.isInteger(annee) ? modele.decretsAn({}).find((d) => d.inv === p.inventaire && d.notice === p.notice) : undefined)
    ?? null;
}

function volumeDuBulletin(modele, annee) {
  return modele && Number.isInteger(annee) ? modele.volumeDeLAnnee(annee) : null;
}

function blocDecret(decret, T, F) {
  const coteNote = decret.drapCote === 'suspecte-bb11' ? T.decrets.coteAVerifier(decret.coteSuggeree) : null;
  return h('section', { class: 'guide__decret', aria: { labelledby: 'guide-decret' } },
    h('h2', { id: 'guide-decret' }, T.guides.rempliPour),
    champs([
      [F.dateDecret, decret.date ? formaterDate(decret.date) : T.decrets.sansDate],
      [F.titreEpoque, decret.titre ? h('q', { class: 'source-brute' }, decret.titre) : null],
      [F.coteDecret, decret.cote ? [decret.cote, coteNote ? h('span', { class: 'note' }, ` — ${coteNote}`) : null] : T.decrets.coteAbsente],
      [F.document, decret.doc],
      [F.identifiantNotice, `${decret.inv} / ${decret.notice}`],
    ]),
    h('p', { class: 'note' }, T.guides.rempliChapeau));
}

function unGuide(guide, guides, p, modele, liens, T) {
  const G = T.guides;
  const F = T.fiche;
  const options = { liens, legende: guides.legende, ecrans: guides.ecrans_communs, niveau: 3, params: variablesDeLiens(p), libelles: {}, remplacements: {} };
  let rempli = null;

  if (GUIDES_AN.has(guide.id) && designeUnDecretAn(p)) {
    const decret = trouverDecret(modele, p);
    if (decret) {
      rempli = blocDecret(decret, T, F);
      options.params = { ...options.params, inventaire: decret.inv, notice: decret.notice, annee: decret.annee };
      options.libelles = { 'an-notice': F.liens.noticeDecret, 'an-inventaire': F.liens.inventaire(decret.annee), 'an-images-notice': F.liens.imagesDecret };
      if (typeof decret.lienNoticeParticulier === 'string') options.remplacements['an-notice'] = () => lienParticulier(liens, decret.lienNoticeParticulier, F.liens.noticeDecret);
      else if (decret.lienNoticeParticulier === null) options.remplacements['an-notice'] = () => null;
      if (typeof decret.lienImagesParticulier === 'string') options.remplacements['an-images-notice'] = () => lienParticulier(liens, decret.lienImagesParticulier, F.liens.imagesDecret);
      else if (decret.lienImagesParticulier === null) options.remplacements['an-images-notice'] = () => null;
    } else {
      rempli = avis({ ton: 'attention' }, G.decretInconnu);
    }
  } else if (GUIDES_BULLETIN.has(guide.id) && designeUnePageBulletin(p)) {
    const annee = Number(p.annee);
    const feuille = Number(p.feuillet);
    const volTrouve = volumeDuBulletin(modele, annee);
    // A leaf the scanned volume does not have designates nothing.
    const vol = volTrouve && Number.isInteger(feuille) && feuille >= 0 && (volTrouve.feuilles === null || feuille <= volTrouve.feuilles) ? volTrouve : null;
    // The page number shown is the one the data read for that leaf; the one of the address is
    // only repeated as such, unchecked (an address can be forged or mistyped).
    const page = vol ? modele.pageDeLaFeuille(vol.annee, feuille) : null;
    const pageAdresse = page === null && /^\d{1,5}$/.test(String(p.page ?? '')) ? Number(p.page) : null;
    if (vol) {
      const lien = lienPageBulletin(liens, vol, feuille);
      options.params = { identifiant: vol.item, volume: vol.doc, feuillet: feuille };
      options.libelles = { 'ia-volume': F.liens.volume(vol.annee) };
      for (const id of ['ia-page', 'ia-page-volume']) {
        options.remplacements[id] = () => (lien && lien.url && lien.id === id ? lienExterne(liens, id, options.params, { libelle: F.ouvrirLaPage(page) }) : null);
      }
      rempli = h('section', { class: 'guide__decret', aria: { labelledby: 'guide-decret' } },
        h('h2', { id: 'guide-decret' }, G.rempliPourPage),
        h('p', null, G.pageDuBulletin(vol.annee, page, feuille)),
        pageAdresse !== null ? h('p', { class: 'note' }, G.pageDeLAdresse(pageAdresse)) : null,
        h('p', { class: 'note' }, G.rempliChapeau));
    } else {
      rempli = avis({ ton: 'attention' }, G.pageInconnue);
    }
  } else if (GUIDES_AN.has(guide.id) && guide.id !== 'numero-a-verifier') {
    rempli = avis({ ton: 'neutre' }, G.sansDecret, h('p', null, h('a', { href: formerHash('decrets') }, G.versLaListe)));
  }

  // Progress boxes, in memory only.
  const etapes = etapesGuide(guide, options);
  const total = etapes.children.length;
  const avancement = h('p', { class: 'guide__avancement', role: 'status', aria: { live: 'polite' } }, G.avancement(0, total));
  const recompter = () => {
    avancement.textContent = G.avancement(etapes.querySelectorAll('.etape__case:checked').length, total);
  };
  [...etapes.children].forEach((li, i) => {
    const id = `etape-faite-${i + 1}`;
    li.append(h('p', { class: 'etape__fait' },
      h('input', { type: 'checkbox', id, class: 'etape__case', on: { change: (e) => { li.classList.toggle('etape--faite', e.target.checked); recompter(); } } }),
      h('label', { for: id }, G.cocher)));
  });

  const suite = (guide.suite ?? []).map((s) => guides.guides.find((g) => g.id === s)).filter(Boolean);
  // A following guide keeps the decree when it uses one (the same notice, the same page).
  const paramsSuite = (g) => ((GUIDES_AN.has(g.id) && designeUnDecretAn(p)) || (GUIDES_BULLETIN.has(g.id) && designeUnePageBulletin(p)) ? p : {});

  return [
    h('p', { class: 'retour' }, h('a', { href: formerHash('guides') }, icone('retour'), h('span', null, G.tous))),
    h('h1', null, guide.titre),
    h('p', { class: 'chapeau' }, guide.pour_qui),
    champs([[G.duree, guide.duree]], { classe: 'guide__duree' }),
    h('p', { class: 'guide__actions' }, h('button', { type: 'button', class: 'bouton bouton--secondaire guide__imprimer', on: { click: () => window.print() } }, icone('imprimer'), h('span', null, G.imprimer))),
    avis({ ton: 'neutre' }, guides.franchise),
    rempli,
    (guide.ce_qu_il_vous_faut ?? []).length > 0 ? [h('h2', null, G.ilVousFaut), h('ul', null, guide.ce_qu_il_vous_faut.map((x) => h('li', null, x)))] : null,
    h('h2', null, G.etapes),
    avancement,
    h('p', { class: 'note guide__cases' }, G.casesNonGardees),
    etapes,
    guide.resultat ? [h('h2', null, G.resultat), h('p', null, guide.resultat)] : null,
    (guide.limites ?? []).length > 0 ? [h('h2', null, G.limites), h('ul', null, guide.limites.map((x) => h('li', null, x)))] : null,
    suite.length > 0 ? [h('h2', null, G.ensuite), h('ul', { class: 'liens-internes liens-internes--guides' }, suite.map((g) => h('li', null,
      h('a', { href: formerHash('guides', [g.id], paramsSuite(g)) }, icone('fleche'), h('span', null, g.titre)))))] : null,
  ];
}

export const vueGuides = {
  asynchrone: true,
  titre: (route, { T }) => T.guides.titreDocument,

  monter(conteneur, route, { T, contenu, leger, finDeRendu, remonter }) {
    const G = T.guides;
    const zone = h('div', { class: 'vue vue--guide' }, h('p', { class: 'note', role: 'status' }, G.chargement));
    conteneur.append(zone);
    let vivant = true;
    const p = lireParametresGuide(route.params);
    const id = route.segments[0];
    const besoinDonnees = Boolean(id) && (designeUnDecretAn(p) || designeUnePageBulletin(p));
    // The decree is looked up in the small data files; if they cannot be had, the guide is
    // still drawn, with the links composed from the address and the honest warning.
    const donnees = besoinDonnees ? leger.charger().catch((error) => {
      if (error?.name === 'ErreurDonnees') return null;
      throw error;
    }) : Promise.resolve(null);
    Promise.all([contenu.charger('guides'), contenu.liens(), donnees]).then(([guides, liens, modele]) => {
      if (!vivant) return;
      const guide = id ? guides.guides.find((g) => g.id === id) : null;
      if (id && !guide) {
        remplacer(zone, h('h1', null, G.introuvable), h('p', null, G.introuvableTexte), listeDesGuides(guides, T).slice(1));
      } else if (!guide) {
        remplacer(zone, listeDesGuides(guides, T));
      } else {
        remplacer(zone, unGuide(guide, guides, p, modele, liens, T));
        document.title = T.app.titreDocument(guide.titre);
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
