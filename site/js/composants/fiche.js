/**
 * The full notice ("fiche") of a person found: every field as the source writes it, the
 * decree, the hint about the person (always labelled "indice"), the publication in the
 * Bulletin officiel when one exists, the step-by-step guide to the document itself, and the
 * citation block (what a verifiable citation is, what is held, what is still missing).
 *
 * Used inside an opened result card and by the notice page (vues/notice.js).
 *
 *   detailFiche(fiche, { liens, guides, vocabulaire, bilan, couverture, niveau })
 *
 *   fiche        a plain object of the data layer (donnees/modele.js: ficheAn, ficheBogga)
 *   liens        the link resolver (logique/liens.js)
 *   guides       parsed guides.json ; vocabulaire: parsed vocabulaire.json ; bilan: parsed bilan.json
 *   couverture   coverage summary of the data layer
 *   niveau       heading level of the blocks (default 4)
 */

import { h, icone, nomEcrit } from './dom.js';
import { champs } from './carte.js';
import { avis } from './avis.js';
import { etapesGuide } from './etapes-guide.js';
import { lienExterne, lienParticulier } from './lien-externe.js';
import { T } from '../textes/index.js';
import { anneeDe, formaterDate, formaterNombre, remplirGabarit } from '../logique/formats.js';
import { imagePageBulletin, lienPageBulletin } from '../logique/liens.js';
import { formerHash } from '../routeur.js';
import { parametresPourDecretAn, parametresPourPageBulletin } from '../logique/parametres-guide.js';

/** The same guide on its own page, filled for this notice: to print it, or to keep its address. */
function guidePagePropre(id, params) {
  return h('p', { class: 'detail__renvoi detail__page-guide' }, h('a', { href: formerHash('guides', [id], params) }, icone('imprimer'), h('span', null, T.fiche.guidePagePropre)));
}

const bloc = (niveau, titre, ...contenu) => h('section', { class: 'detail__bloc' }, h(`h${niveau}`, { class: 'detail__titre' }, titre), contenu);
const cite = (text) => h('q', { class: 'source-brute' }, text);

/** "né en 1874 — date conventionnelle : comparez l'année, pas le jour" */
export function noteNaissance(prec) {
  return T.fiche.precisions[prec] ?? null;
}

/**
 * « ne-en-algerie(explicite)+prenom-musulman » -> « naissance en Algérie écrite dans la notice ;
 * prénom de forme arabe ou berbère ». A fragment without a French phrase is named generically.
 */
export function regleEnClair(regle) {
  const R = T.fiche.regles;
  return String(regle ?? '').split('+').filter(Boolean).map((x) => {
    if (Object.hasOwn(R, x)) return R[x];
    const pays = /^ne-([a-z-]+)$/.exec(x);
    return pays ? R.neAilleurs : R.autre;
  }).join(T.explications.separateur);
}

function guideParId(guides, id) {
  return (guides?.guides ?? []).find((g) => g.id === id) ?? null;
}

function introGuide(guides, guide, niveau) {
  return [
    h('p', { class: 'detail__chapeau' }, guide.pour_qui, ' ', h('span', { class: 'detail__duree' }, T.guide.duree(guide.duree))),
    guides.franchise ? h('p', { class: 'detail__franchise' }, guides.franchise) : null,
  ];
}

function suiteGuide(guides, guide) {
  const next = (guide.suite ?? []).map((id) => guideParId(guides, id)).filter((g) => g !== null);
  if (next.length === 0) return null;
  return h('div', { class: 'detail__suite' },
    h('p', null, T.guide.ensuite),
    h('ul', { class: 'liens-internes liens-internes--guides' }, next.map((g) => h('li', null, h('a', { href: formerHash('guides', [g.id]) }, icone('fleche'), h('span', null, g.titre))))));
}

/** One publication of a decree in the printed Bulletin, with its page link. */
function publicationBulletin(liens, decret) {
  const F = T.fiche;
  const vol = decret.volume;
  const lien = vol ? lienPageBulletin(liens, vol, decret.feuille) : null;
  const dates = decret.dates.filter((d) => typeof d === 'string').map(formaterDate);
  const parts = [];
  if (vol) parts.push(F.bulletinAnnee(vol.annee));
  if (Number.isInteger(decret.page)) parts.push(F.page(decret.page));
  const livraison = [];
  if (Number.isInteger(decret.livraison)) livraison.push(F.livraisonNumero(decret.livraison));
  if (decret.livraisonDate) livraison.push(F.livraisonDate(formaterDate(decret.livraisonDate)));
  const reserves = [];
  if (decret.dateEtat !== 0) reserves.push(F.reserveDateDecret);
  if (decret.livraisonDate && decret.livraisonDateEtat !== 0) reserves.push(F.reserveDatePublication);
  if (!decret.livraisonDate) reserves.push(F.publicationNonLue);
  return h('li', { class: 'publication' },
    h('p', { class: 'publication__ref' }, parts.join(T.formats.virgule)),
    h('p', { class: 'publication__detail' },
      F.natures[decret.nature] ?? decret.nature,
      dates.length > 0 ? F.decretDu(dates.join(T.formats.et)) : '',
      livraison.length > 0 ? ` — ${livraison.join(T.formats.virgule)}` : ''),
    reserves.length > 0 ? h('p', { class: 'publication__reserve' }, reserves.join(' ')) : null,
    lien && lien.url ? lienExterne(liens, lien.id, { identifiant: vol.item, volume: vol.doc, feuillet: decret.feuille }, { libelle: F.ouvrirLaPage(decret.page) }) : null);
}

/** First year whose decrees the site sends to the Journal officiel rather than to the Bulletin. */
const PREMIERE_ANNEE_DU_JOURNAL = 1927;

/**
 * The Archives nationales' sentence on what proves a decree (« publiés au Journal officiel »).
 * For a decree published in the Bulletin officiel (up to 1926), its precaution goes with it:
 * the quotation alone would suggest that a Bulletin page is worth nothing.
 */
function citationOfficielle(liens, bilan, annee) {
  const c = (bilan?.citations_officielles?.principales ?? [])[0];
  if (!c) return null;
  const avantLeJournal = !Number.isInteger(annee) || annee < PREMIERE_ANNEE_DU_JOURNAL;
  return h('figure', { class: 'citation-officielle' },
    h('blockquote', null, h('p', null, T.formats.cite(c.texte))),
    h('figcaption', null, `${c.auteur} — ${c.date}`, c.lien ? [' ', lienExterne(liens, c.lien, {}, { libelle: T.fiche.lireLaPage })] : null),
    avantLeJournal && c.precaution ? h('p', { class: 'note citation-officielle__precaution' }, c.precaution) : null);
}

function definitionCitation(vocabulaire) {
  const terme = (vocabulaire?.termes ?? []).find((t) => t.id === 'citation');
  return terme ? h('p', { class: 'citation__definition' }, h('strong', null, T.formats.etiquette(terme.terme)), terme.definition) : null;
}

// ---------------------------------------------------------------------------------------------
// Archives nationales
// ---------------------------------------------------------------------------------------------

function detailAn(fiche, { liens, guides, vocabulaire, bilan, couverture, niveau }) {
  const F = T.fiche;
  const d = fiche.decret;
  const out = [];

  // 1. The notice, as typed in the inventory.
  // Adults get every field; children are listed compactly (first names and the raw birth), with
  // each caveat about their dates said once.
  const adultes = fiche.membres.filter((m) => m.role !== 'enfant');
  const enfants = fiche.membres.filter((m) => m.role === 'enfant');
  const personnes = adultes.map((m) => h('div', { class: 'personne' },
    h('p', { class: 'personne__nom' }, h('span', { class: 'personne__role' }, F.roles[m.role] ?? m.role), ' ',
      m.nom ? nomEcrit(m.nom, { class: 'nom' }) : h('em', null, F.nomNonSaisi)),
    champs([
      [F.naissanceBrute, m.naiss ? cite(m.naiss) : null],
      [F.anneeNaissance, Number.isInteger(m.an) ? [String(m.an), noteNaissance(m.prec) ? h('span', { class: 'note' }, ` — ${noteNaissance(m.prec)}`) : null] : null],
      [F.lieuNaissance, m.lieu],
      [F.residence, m.res],
      [F.profession, m.prof],
    ])));
  if (enfants.length > 0) {
    const reserves = [...new Set(enfants.map((m) => noteNaissance(m.prec)).filter(Boolean))];
    personnes.push(h('div', { class: 'personne personne--enfants' },
      h('p', { class: 'personne__role' }, F.enfants(enfants.length)),
      h('ul', { class: 'enfants' }, enfants.map((m) => h('li', null,
        m.nom ? nomEcrit(m.nom, { class: 'nom' }) : h('em', null, F.nomNonSaisi),
        m.naiss ? [' — ', cite(m.naiss)] : (Number.isInteger(m.an) ? ` — ${m.an}` : null)))),
      reserves.map((r) => h('p', { class: 'note' }, r))));
  }
  const absents = [
    fiche.prochesNonAffiches > 0 ? F.prochesNonAffiches(fiche.prochesNonAffiches) : null,
    fiche.mentionsNonNoms > 0 ? F.mentionsNonNoms(fiche.mentionsNonNoms) : null,
  ].filter(Boolean);
  if (absents.length > 0) personnes.push(h('p', { class: 'note personne__absents' }, absents.join(' ')));
  const liensNotice = [];
  const notesVues = new Set();
  if (d && fiche.notice) {
    if (typeof fiche.lienNoticeParticulier === 'string') liensNotice.push(lienParticulier(liens, fiche.lienNoticeParticulier, F.liens.noticePersonne));
    else if (fiche.lienNoticeParticulier !== null) liensNotice.push(lienExterne(liens, 'an-notice', { inventaire: d.inv, notice: fiche.notice }, { libelle: F.liens.noticePersonne, sansRepli: true, notesVues }));
    if (fiche.aSesImages) {
      if (typeof fiche.lienImagesParticulier === 'string') liensNotice.push(lienParticulier(liens, fiche.lienImagesParticulier, F.liens.imagesPersonne));
      else if (fiche.lienImagesParticulier !== null) liensNotice.push(lienExterne(liens, 'an-images-notice', { inventaire: d.inv, notice: fiche.notice }, { libelle: F.liens.imagesPersonne, sansRepli: true, notesVues }));
    }
    // The fallback of both: the inventory of the year, the one link seen working.
    liensNotice.push(lienExterne(liens, 'an-inventaire', { inventaire: d.inv }, { libelle: F.liens.inventaire(d.annee) }));
  }
  out.push(bloc(niveau, F.titres.noticeAn,
    h('p', { class: 'detail__chapeau' }, F.noticeAnChapeau),
    personnes,
    champs([
      [F.dossier, fiche.dossier],
      [F.coteDossier, fiche.coteDossier],
      [F.identifiantNotice, d && fiche.notice ? `${d.inv} / ${fiche.notice}` : null],
    ], { classe: 'champs--references' }),
    liensNotice.filter(Boolean).length > 0 ? h('ul', { class: 'liens' }, liensNotice.filter(Boolean).map((el) => h('li', null, el))) : null,
    fiche.dossier ? h('p', { class: 'detail__renvoi' }, h('a', { href: formerHash('guides', ['dossier-pierrefitte']) }, F.guideDossier)) : null));

  // 2. The decree.
  if (d) {
    const drapeaux = String(d.drapDate).split('+').filter((x) => x !== '').map((x) => F.drapeauxDate[x] ?? x);
    const coteNotes = [];
    if (d.drapCote === 'suspecte-bb11') coteNotes.push(F.coteSuspecte(d.coteSuggeree));
    if (d.drapCote === 'absente') coteNotes.push(F.coteAbsente);
    out.push(bloc(niveau, F.titres.decretAn,
      champs([
        [F.dateDecret, d.date ? [formaterDate(d.date), drapeaux.length > 0 ? h('span', { class: 'note' }, ` — ${drapeaux.join(' ')}`) : null] : h('span', { class: 'note' }, drapeaux.join(' ') || F.dateInconnue)],
        [F.titreEpoque, d.titre ? cite(d.titre) : null],
        [F.ceQueDitLeTitre, [F.familles[d.famille] ?? d.famille, d.classeLibelle && d.classe !== '-' ? h('span', { class: 'note' }, ` — ${F.classement(d.classeLibelle)}`) : null]],
        [F.coteDecret, d.cote ? [d.cote, coteNotes.length > 0 ? h('span', { class: 'note' }, ` — ${coteNotes.join(' ')}`) : null] : (coteNotes[0] ?? null)],
        [F.document, d.doc],
        [F.registre, d.contexte],
        [F.etatSaisie, F.etats[d.etat] ?? d.etat],
        [F.personnesDuDecret, Number.isInteger(d.nPersonnes) ? formaterNombre(d.nPersonnes) : null],
      ])));
  }

  // 3. The hint. Never a fact.
  if (fiche.indice) {
    const lieux = [];
    if (fiche.neEnAlgerie) lieux.push(F.neEnAlgerie[fiche.neEnAlgerie] ?? null);
    if (fiche.resideEnAlgerie) lieux.push(F.resideEnAlgerie[fiche.resideEnAlgerie] ?? null);
    out.push(bloc(niveau, F.titres.indice,
      avis({ ton: 'neutre', classe: 'indice' },
        h('p', null, h('strong', null, F.indiceEtiquette), ' ', fiche.indice.libelle ?? fiche.indice.code),
        lieux.filter(Boolean).length > 0 ? h('p', null, lieux.filter(Boolean).join(' ')) : null,
        fiche.indice.regle ? h('p', { class: 'note' }, F.regle, ' ', regleEnClair(fiche.indice.regle)) : null,
        couverture?.an?.avertissements?.[0] ? h('p', { class: 'note' }, couverture.an.avertissements[0]) : null)));
  }

  // 4. Publication in the printed Bulletin: the citation with value of proof.
  const annee = d ? (anneeDe(d.date) ?? d.annee) : null;
  const anneeBulletin = annee !== null ? (couverture?.bogga?.annees ?? []).find((y) => y.annee === annee) : undefined;
  // A date is shared by several decrees: only one where the machine read the name is offered as
  // THE publication; the others of that day stay listed apart, to be opened by hand.
  const reconnues = fiche.publications.filter((p) => p.nomReconnu === true);
  const autres = fiche.publications.filter((p) => p.nomReconnu !== true);
  if (fiche.publications.length > 0) {
    const autresDuJour = autres.length > 0 ? h('details', { class: 'repli publications__autres' },
      h('summary', null, F.autresDuJour(autres.length)),
      h('ul', { class: 'publications' }, autres.map((p) => publicationBulletin(liens, p)))) : null;
    out.push(bloc(niveau, F.titres.publication,
      reconnues.length > 0
        ? [h('p', { class: 'detail__chapeau' }, F.publicationChapeau(formaterDate(d.date), reconnues.length)),
          h('ul', { class: 'publications' }, reconnues.map((p) => publicationBulletin(liens, p))),
          autresDuJour]
        : [h('p', { class: 'detail__chapeau' }, F.publicationSansNom(formaterDate(d.date), autres.length)),
          h('ul', { class: 'publications' }, autres.filter((p) => p.natureCompatible !== false).map((p) => publicationBulletin(liens, p))),
          autres.some((p) => p.natureCompatible === false) ? h('details', { class: 'repli publications__autres' },
            h('summary', null, F.autreNature(autres.filter((p) => p.natureCompatible === false).length)),
            h('ul', { class: 'publications' }, autres.filter((p) => p.natureCompatible === false).map((p) => publicationBulletin(liens, p)))) : null],
      h('p', { class: 'note' }, F.publicationReserve)));
  } else if (anneeBulletin !== undefined) {
    out.push(bloc(niveau, F.titres.publication,
      h('p', null, anneeBulletin.lu ? F.publicationNonReconnue(annee) : F.publicationAnneeAbsente(annee)),
      !anneeBulletin.lu && anneeBulletin.queFaire ? h('p', { class: 'note' }, anneeBulletin.queFaire) : null));
  }

  // 5. The document itself: the step-by-step guide.
  const guide = guideParId(guides, 'an-annee-indexee');
  if (guide && d) {
    const remplacements = {};
    if (typeof d.lienNoticeParticulier === 'string') remplacements['an-notice'] = () => lienParticulier(liens, d.lienNoticeParticulier, F.liens.noticeDecret);
    else if (d.lienNoticeParticulier === null) remplacements['an-notice'] = () => null;
    if (typeof d.lienImagesParticulier === 'string') remplacements['an-images-notice'] = () => lienParticulier(liens, d.lienImagesParticulier, F.liens.imagesDecret);
    else if (d.lienImagesParticulier === null) remplacements['an-images-notice'] = () => null;
    out.push(bloc(niveau, F.titres.voirLeDocument,
      introGuide(guides, guide, niveau),
      etapesGuide(guide, {
        liens,
        params: { inventaire: d.inv, notice: d.notice },
        legende: guides.legende,
        ecrans: guides.ecrans_communs,
        libelles: { 'an-notice': F.liens.noticeDecret, 'an-inventaire': F.liens.inventaire(d.annee), 'an-images-notice': F.liens.imagesDecret },
        remplacements,
        niveau: niveau + 1,
        // the note of the notice links, written in full above, is not repeated in every step
        notesVues,
      }),
      guidePagePropre('an-annee-indexee', parametresPourDecretAn(d)),
      suiteGuide(guides, guide)));
  }

  // 6. The citation.
  if (d) {
    const tenu = [];
    if (d.date) tenu.push(F.tenu.dateDecret(formaterDate(d.date)));
    if (d.cote) tenu.push(F.tenu.cote(d.cote, d.doc));
    if (fiche.dossier) tenu.push(F.tenu.dossier(fiche.dossier));
    const manque = reconnues.length > 0 ? [F.manque.confirmerPublication] : [F.manque.publication];
    const reference = d.date
      ? F.referenceOriginal(formaterDate(d.date), [d.cote, d.doc].filter(Boolean).join(T.formats.virgule))
      : null;
    out.push(bloc(niveau, F.titres.citation,
      definitionCitation(vocabulaire),
      h('div', { class: 'citation' },
        h('p', { class: 'citation__sous-titre' }, F.ceQueVousTenez),
        tenu.length > 0 ? h('ul', null, tenu.map((x) => h('li', null, x))) : h('p', null, F.rienDeSur),
        h('p', { class: 'citation__sous-titre' }, F.ceQuiManque),
        h('ul', null, manque.map((x) => h('li', null, x))),
        reference ? h('p', { class: 'citation__reference' }, h('span', { class: 'citation__etiquette' }, F.referenceEtiquette), ' ', reference) : null),
      citationOfficielle(liens, bilan, annee)));
  }

  // 7. The mandatory credit.
  if (d && fiche.credit.gabarit) {
    const date = [d.date ? F.creditDecretDu(formaterDate(d.date)) : null, fiche.credit.dateDesInformations ? F.creditReleve(formaterDate(fiche.credit.dateDesInformations)) : null].filter(Boolean).join(' ');
    out.push(h('p', { class: 'credit' }, h('span', { class: 'credit__etiquette' }, F.source), ' ',
      remplirGabarit(fiche.credit.gabarit, { cote: d.cote ?? F.coteAbsenteCourt, lieu: fiche.credit.lieu ?? '', date })));
  }
  return out;
}

// ---------------------------------------------------------------------------------------------
// Printed Bulletin officiel
// ---------------------------------------------------------------------------------------------

let numeroDePage = 0;

/** « Afficher la page imprimée »: the image is asked from archive.org only after this click. */
function pageImprimee(fiche, liens) {
  const F = T.fiche;
  const vol = fiche.volume;
  const src = imagePageBulletin(vol, fiche.feuille, 1000);
  const lien = lienPageBulletin(liens, vol, fiche.feuille);
  const zone = h('div', { class: 'page-imprimee__zone' });
  const etat = h('p', { class: 'page-imprimee__etat', role: 'status', aria: { live: 'polite' } });
  const idAvant = `page-imprimee-avant-${++numeroDePage}`;
  // The warning (« archive.org verra… ») is read with the button itself.
  const bouton = src === null ? null : h('button', { type: 'button', class: 'bouton bouton--secondaire', aria: { describedby: idAvant } }, icone('image'), h('span', null, F.afficherLaPage));
  let enCours = false;
  bouton?.addEventListener('click', () => {
    // Never disabled while it has the focus (the focus would fall to <body>): busy instead.
    if (enCours) return;
    enCours = true;
    bouton.setAttribute('aria-disabled', 'true');
    etat.textContent = F.pageEnChargement;
    const img = h('img', { class: 'page-imprimee__image', alt: F.altPage(fiche.page, vol.annee), referrerpolicy: 'no-referrer', decoding: 'async' });
    // On a phone the page is too small to read: one button doubles it inside a scrolling frame.
    const loupe = h('button', { type: 'button', class: 'bouton bouton--secondaire page-imprimee__loupe', hidden: true, aria: { pressed: 'false' } }, F.agrandir);
    loupe.addEventListener('click', () => {
      const grande = img.classList.toggle('page-imprimee__image--grande');
      loupe.setAttribute('aria-pressed', String(grande));
    });
    const cadre = h('div', { class: 'page-imprimee__cadre', tabindex: '0', role: 'group', aria: { label: F.cadreImage } }, img);
    img.addEventListener('load', () => {
      const avaitLeFocus = document.activeElement === bouton;
      etat.textContent = '';
      loupe.hidden = false;
      bouton.hidden = true;
      // The button is gone: the reader is put on the image it asked for.
      if (avaitLeFocus) cadre.focus({ preventScroll: true });
    });
    img.addEventListener('error', () => {
      etat.textContent = F.pageIndisponible;
      enCours = false;
      bouton.removeAttribute('aria-disabled');
      img.remove();
    });
    zone.replaceChildren(h('figure', { class: 'page-imprimee__figure' }, cadre, loupe,
      h('figcaption', null, F.creditImage(vol.annee, fiche.page, vol.item), vol.bibliotheque ? ` ${vol.bibliotheque}.` : '')));
    img.src = src; // the only request this site ever makes to another host, after an explicit click
  });
  return h('div', { class: 'page-imprimee' },
    h('p', null, F.pageEtFeuille(fiche.page, fiche.feuille)),
    bouton ? h('p', { class: 'page-imprimee__avant', id: idAvant }, F.avantImage) : null,
    bouton,
    etat,
    zone,
    lien && lien.url ? lienExterne(liens, lien.id, { identifiant: vol.item, volume: vol.doc, feuillet: fiche.feuille }, { libelle: F.ouvrirLaLiseuse }) : null,
    vol.lienVerifie === 'non vérifié' ? h('p', { class: 'note' }, F.lienPageNonVerifie) : null);
}

function detailBogga(fiche, { liens, guides, vocabulaire, niveau }) {
  const F = T.fiche;
  const d = fiche.decret;
  const vol = fiche.volume;
  const out = [];

  out.push(bloc(niveau, F.titres.entreeBulletin,
    avis({ ton: 'attention' }, F.texteMachine),
    champs([
      [F.nomLu, fiche.nom ? nomEcrit(fiche.nom, { class: 'nom' }) : null],
      [F.texteLu, fiche.texte ? h('q', { class: 'source-brute source-brute--longue' }, fiche.texte) : null],
      [F.anneeNaissanceLue, Number.isInteger(fiche.naissance) ? String(fiche.naissance) : null],
      [F.residenceLue, fiche.residence],
      [F.nationaliteImprimee, fiche.nationalite],
      [F.motsImprimes, fiche.marqueurs.length > 0 ? [h('ul', { class: 'liste-simple' }, fiche.marqueurs.map((m) => h('li', null, m.libelle))), h('span', { class: 'note' }, F.motsImprimesNote)] : null],
      [F.signalements, fiche.drapeaux.length > 0 ? h('ul', { class: 'liste-simple' }, fiche.drapeaux.map((m) => h('li', null, m.libelle))) : null],
    ])));

  if (d) {
    const dates = d.dates.map((x) => (typeof x === 'string' ? formaterDate(x) : F.dateIllisible));
    const etatDate = fiche.etatsDates?.[String(d.dateEtat)] ?? null;
    out.push(bloc(niveau, F.titres.decretBulletin,
      champs([
        [F.dateDecret, [dates.length > 0 ? dates.join(T.formats.et) : F.dateInconnue, etatDate && d.dateEtat !== 0 ? h('span', { class: 'note' }, ` — ${etatDate}`) : null]],
        [F.dateTelleQueLue, d.dateBrute ? cite(d.dateBrute) : null],
        [F.nature, F.natures[d.nature] ?? d.nature],
        [F.entete, d.entete ? h('q', { class: 'source-brute source-brute--longue' }, d.entete) : null],
        [F.article, d.article ? [d.article, h('span', { class: 'note' }, ` — ${F.articlePeuFiable}`)] : null],
        [F.livraison, Number.isInteger(d.livraison) ? [String(d.livraison), d.livraisonEtat !== 0 && fiche.etatsLivraison?.[String(d.livraisonEtat)] ? h('span', { class: 'note' }, ` — ${fiche.etatsLivraison[String(d.livraisonEtat)]}`) : null] : null],
        [F.datePublication, d.livraisonDate
          ? [formaterDate(d.livraisonDate), d.livraisonDateEtat !== 0 && fiche.etatsDates?.[String(d.livraisonDateEtat)] ? h('span', { class: 'note' }, ` — ${fiche.etatsDates[String(d.livraisonDateEtat)]}`) : null]
          : h('span', { class: 'note' }, F.publicationNonLue)],
        [F.pageDuDecret, Number.isInteger(d.page) ? String(d.page) : null],
        [F.personnesAnnoncees, Number.isInteger(d.totalImprime) ? F.annonceesEtDecoupees(d.totalImprime, d.entrees) : (Number.isInteger(d.entrees) ? F.decoupees(d.entrees) : null)],
        [F.republication, d.doublonDe ? F.dejaPublie(d.doublonDe.page) : null],
      ])));
  }

  if (vol) out.push(bloc(niveau, F.titres.pageImprimee, pageImprimee(fiche, liens)));

  const guide = guideParId(guides, 'bogga-internet-archive');
  if (guide && vol) {
    const page = lienPageBulletin(liens, vol, fiche.feuille);
    const params = { identifiant: vol.item, volume: vol.doc, feuillet: fiche.feuille };
    // "hathitrust-page" needs a sequence number the data does not hold: it is drawn as text.
    const remplacements = {};
    for (const id of ['ia-page', 'ia-page-volume']) {
      remplacements[id] = () => (page && page.url && page.id === id ? lienExterne(liens, id, params, { libelle: F.ouvrirLaPage(fiche.page) }) : null);
    }
    out.push(bloc(niveau, F.titres.voirLeDocument,
      introGuide(guides, guide, niveau),
      etapesGuide(guide, { liens, params, legende: guides.legende, ecrans: guides.ecrans_communs, remplacements, libelles: { 'ia-volume': F.liens.volume(vol.annee) }, niveau: niveau + 1 }),
      guidePagePropre('bogga-internet-archive', parametresPourPageBulletin(fiche)),
      suiteGuide(guides, guide)));
  }

  if (d && vol) {
    const tenu = [];
    const aConfirmer = [];
    const datesLues = d.dates.filter((x) => typeof x === 'string');
    if (datesLues.length > 0) tenu.push(F.tenu.dateDecret(datesLues.map(formaterDate).join(T.formats.et)));
    else aConfirmer.push(F.manque.dateDecret);
    if (d.dateEtat !== 0 && datesLues.length > 0) aConfirmer.push(F.manque.dateDecretALire);
    tenu.push(F.tenu.bulletin(vol.annee));
    if (Number.isInteger(fiche.page)) tenu.push(F.tenu.page(fiche.page));
    else aConfirmer.push(F.manque.page);
    if (d.livraisonDate) {
      tenu.push(F.tenu.datePublication(formaterDate(d.livraisonDate)));
      if (d.livraisonDateEtat !== 0) aConfirmer.push(F.manque.datePublicationALire);
    } else aConfirmer.push(F.manque.datePublication);
    aConfirmer.push(F.manque.lireLImage);
    const reference = datesLues.length > 0 && Number.isInteger(fiche.page)
      ? F.citationBulletin(datesLues.map(formaterDate).join(T.formats.et), vol.annee, fiche.page, d.livraisonDate ? formaterDate(d.livraisonDate) : null)
      : null;
    out.push(bloc(niveau, F.titres.citation,
      definitionCitation(vocabulaire),
      h('div', { class: 'citation' },
        h('p', { class: 'citation__sous-titre' }, F.ceQueVousTenez),
        h('ul', null, tenu.map((x) => h('li', null, x))),
        h('p', { class: 'citation__sous-titre' }, F.aConfirmerSurLImage),
        h('ul', null, aConfirmer.map((x) => h('li', null, x))),
        reference ? h('p', { class: 'citation__reference' }, h('span', { class: 'citation__etiquette' }, F.citationEtiquette), ' ', reference) : null)));
  }

  if (vol) {
    out.push(h('p', { class: 'credit' }, h('span', { class: 'credit__etiquette' }, F.source), ' ',
      F.creditImage(vol.annee, fiche.page, vol.item), fiche.credit.texte ? ` ${fiche.credit.texte}.` : '', vol.droits ? ` ${vol.droits}` : ''));
  }
  return out;
}

/**
 * @param {Object} fiche
 * @param {{liens: Object, guides: Object, vocabulaire: Object, bilan: Object, couverture: Object, niveau?: number}} contexte
 * @returns {HTMLElement}
 */
export function detailFiche(fiche, contexte) {
  const ctx = { niveau: 4, ...contexte };
  const blocs = fiche.source === 'an' ? detailAn(fiche, ctx) : detailBogga(fiche, ctx);
  return h('div', { class: `detail detail--${fiche.source}` }, blocs);
}
