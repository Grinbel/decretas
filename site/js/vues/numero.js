/**
 * #/numero — « On m'a donné un numéro de décret ». What a verifiable citation is (the date of
 * the decree, the publication, the date and page of the publication), then a small form: the
 * person copies what they were given, and the page says what FORM it has (logique/numero.js) and
 * what each form can lead to. A date is looked up in the decrees of the data; a call number too.
 *
 * Nothing leaves the device. The page never says whether a paper is genuine, never accuses
 * anyone, and never concludes anything about an ancestor.
 *
 *   #/numero?t=<what was typed>   (the text stays after the "#", which is never sent)
 */

import { h, icone, remplacer, viserTitre } from '../composants/dom.js';
import { avis } from '../composants/avis.js';
import { echecDePage } from '../composants/echec.js';
import { lienExterne, listeDeLiens } from '../composants/lien-externe.js';
import { mot } from '../composants/chargement-leger.js';
import { formerHash } from '../routeur.js';
import { formaterDate, enoncerAnnees } from '../logique/formats.js';
import { lienPageBulletin } from '../logique/liens.js';
import { classerSaisie, situerDate } from '../logique/numero.js';
import { parametresPourDecretAn } from '../logique/parametres-guide.js';

const LIMITE = 400;

/** An issue of the content ({si, signifie, faire}) as a quiet block. */
function issue(x, ton = 'neutre') {
  if (!x) return null;
  return avis({ ton, titre: x.si }, h('p', null, x.signifie, ' ', h('strong', null, x.faire)));
}

function guidePour(decret) {
  return decret.etat === 'indexe' || decret.etat === 'partiel' ? 'an-annee-indexee' : decret.etat === 'retenu-filae' ? 'an-noms-sur-le-site-des-an' : 'an-annee-en-images';
}

function decretEnBref(decret, T) {
  const N = T.numero;
  return h('li', { class: 'decret-bref' },
    h('p', null, h('strong', null, decret.date ? formaterDate(decret.date) : T.decrets.sansDate),
      decret.drapDate ? h('span', { class: 'note' }, ` — ${N.dateDouteuse}`) : null),
    decret.titre ? h('p', null, h('q', { class: 'source-brute' }, decret.titre)) : null,
    h('p', { class: 'note' }, [decret.cote, decret.doc].filter(Boolean).join(T.formats.virgule), ` — ${T.fiche.etats[decret.etat] ?? ''}`),
    h('p', null, h('a', { href: formerHash('guides', [guidePour(decret)], parametresPourDecretAn(decret)) }, icone('fleche'), h('span', null, N.guidePourCeDecret))));
}

/** What a recognised form can lead to, looked up in the data when it can be. */
function suiteDeForme(forme, { modele, liens, formes, T }) {
  const N = T.numero;
  if (!modele) return null;
  if (forme.code === 'cote-bb34') {
    const decrets = modele.decretsAn({}).filter((d) => d.cote === forme.valeur || d.coteSuggeree === forme.valeur);
    if (decrets.length === 0) return null;
    const docs = formes.filter((f) => f.code === 'document').map((f) => f.valeur);
    const exacts = docs.length > 0 ? decrets.filter((d) => docs.includes(d.doc)) : [];
    return [
      h('p', { class: 'note' }, N.decretsDeLaCote(decrets.length, enoncerAnnees(decrets.map((d) => d.annee)))),
      exacts.length > 0 ? h('ul', { class: 'decrets-brefs' }, exacts.map((d) => decretEnBref(d, T))) : null,
    ];
  }
  if (forme.code === 'inventaire') {
    const annee = modele.couverture().an.annees.find((y) => y.inventaires.some((inv) => inv.inv === forme.valeur));
    const lien = lienExterne(liens, 'an-inventaire', { inventaire: forme.valeur }, annee ? { libelle: T.decrets.inventaireAnnee(annee.annee) } : {});
    return lien ? h('p', null, lien) : null;
  }
  return null;
}

function blocDate(iso, { modele, liens, k2, bornes, T }) {
  const N = T.numero;
  const lieu = situerDate(iso, bornes);
  const out = [h('h3', null, N.dateTitre(formaterDate(iso)))];
  if (lieu.dansAn) {
    const decrets = modele.decretsAn({ annees: [lieu.annee] }).filter((d) => d.date === iso);
    if (decrets.length > 0) {
      out.push(h('p', null, N.decretsDuJour(decrets.length)), h('ul', { class: 'decrets-brefs' }, decrets.map((d) => decretEnBref(d, T))));
      out.push(issue(k2.issues_possibles[0]), issue(k2.issues_possibles[1]));
    } else {
      out.push(issue(k2.issues_possibles[2]));
    }
  } else {
    out.push(issue(k2.issues_possibles[3]));
  }
  if (lieu.dansBulletin) {
    const publications = modele.publicationsDuJour(iso);
    const annee = modele.couverture().bogga.annees.find((y) => y.annee === lieu.annee);
    if (publications.length > 0) {
      out.push(h('p', null, N.publicationsDuJour(publications.length)), h('ul', { class: 'liens' }, publications.map((p) => {
        const lien = p.volume ? lienPageBulletin(liens, p.volume, p.feuille) : null;
        const libelle = `${T.fiche.bulletinAnnee(p.volume?.annee ?? lieu.annee)}${Number.isInteger(p.page) ? `, ${N.page(p.page)}` : ''}`;
        return h('li', null, lien && lien.url ? lienExterne(liens, lien.id, { identifiant: p.volume.item, volume: p.volume.doc, feuillet: p.feuille }, { libelle }) : libelle);
      })), h('p', { class: 'note' }, T.fiche.publicationReserve));
    } else if (annee?.lu) {
      out.push(h('p', { class: 'note' }, N.aucunDecretBulletin));
    }
  }
  return h('section', { class: 'numero__date' }, out);
}

function dessinerResultat(zoneResultat, texte, ctx) {
  const { T, guide, liens, leger, vivant } = ctx;
  const N = T.numero;
  const [k1, k2, k3, k4] = guide.etapes;
  const r = classerSaisie(texte);
  if (r.vide) {
    remplacer(zoneResultat);
    return;
  }
  const titre = h('h2', { id: 'numero-resultat' }, N.resultatTitre);
  const corps = h('div', { class: 'numero__corps' });
  remplacer(zoneResultat, titre, corps);

  const dessiner = (modele) => {
    const bornes = modele ? (() => {
      const c = modele.couverture();
      const an = c.an.annees.map((y) => y.annee);
      const bu = c.bogga.annees.filter((y) => y.lu).map((y) => y.annee);
      return { an: { de: Math.min(...an), a: Math.max(...an) }, bulletin: { de: Math.min(...bu), a: Math.max(...bu) } };
    })() : null;
    const valeurDe = (code) => r.formes.find((f) => f.code === code)?.texte ?? null;
    const datesDuDecret = r.formes.filter((f) => f.code === 'date' && f.role !== 'publication');
    const datePublication = r.formes.find((f) => f.code === 'date' && f.role === 'publication')?.texte ?? null;
    const elements = [
      ['date', r.elements.date ? datesDuDecret[0].texte : null],
      ['publication', valeurDe('publication')],
      ['pageOuDatePublication', r.elements.pageOuDatePublication ? [valeurDe('page'), datePublication ?? datesDuDecret[1]?.texte].filter(Boolean).join(T.formats.virgule) : null],
    ];
    // The guide's own sentences, except for a lone number: its guide answer sends to a step
    // ("la troisième étape") that this page does not have.
    const resume = { complete: k1.issues_possibles[0], 'date-sans-publication': k1.issues_possibles[1], 'numero-seul': N.numeroSeul, 'publication-sans-date': N.publicationSansDate }[r.bilan]
      ?? (r.formes.some((f) => ['dossier', 'cote-bb34', 'cote-bb11', 'document', 'inventaire'].includes(f.code)) ? k3.issues_possibles[0] : k3.issues_possibles[1]);
    remplacer(corps,
      r.formes.length === 0 ? h('p', null, N.rien) : h('ul', { class: 'formes' }, r.formes.map((f) => {
        const def = N.formes[f.role === 'publication' ? 'date-publication' : f.code];
        return h('li', { class: `forme forme--${f.code}` },
          h('p', { class: 'forme__tete' }, h('q', { class: 'forme__extrait' }, f.texte), ' ', h('span', { class: 'forme__nom' }, def.nom)),
          h('p', null, def.texte),
          suiteDeForme(f, { modele, liens, formes: r.formes, T }));
      })),
      h('h3', null, N.elementsTitre),
      h('ul', { class: 'elements' }, elements.map(([cle, v]) => h('li', { class: `element element--${v !== null ? 'present' : 'absent'}` },
        icone(v !== null ? 'coche' : 'info'),
        h('span', null, h('span', { class: 'element__nom' }, N.elements[cle]), ' — ', v !== null ? (v ? N.presentLu(v) : N.present) : N.absent)))),
      issue(resume, r.bilan === 'complete' || r.bilan === 'publication-sans-date' ? 'info' : 'neutre'),
      r.bilan === 'numero-seul' ? h('p', null, k3.instruction) : null,
      modele && bornes ? r.dates.map((iso) => blocDate(iso, { modele, liens, k2, bornes, T })) : null,
      h('section', { class: 'numero__mesure' },
        h('h3', null, k4.titre),
        h('p', null, k4.instruction),
        listeDeLiens(liens, k4.liens ?? [], {})));
  };

  // The decrees are needed for a date or a call number only.
  const besoin = r.formes.some((f) => ['date', 'cote-bb34', 'inventaire'].includes(f.code));
  if (!besoin) {
    dessiner(null);
    return titre;
  }
  corps.append(h('p', { class: 'note', role: 'status' }, T.donneesLegeres.chargement));
  leger.charger().then((modele) => {
    if (vivant()) dessiner(modele);
  }, (error) => {
    if (!vivant()) return;
    if (error?.name !== 'ErreurDonnees') throw error;
    dessiner(null);
    corps.prepend(avis({ ton: 'attention', role: 'alert' }, T.donneesLegeres.erreur(error.statut)));
  });
  return titre;
}

let courant = null;

export const vueNumero = {
  asynchrone: true,
  titre: (route, { T }) => T.numero.titreDocument,

  monter(conteneur, route, { T, contenu, leger, aller, finDeRendu, remonter }) {
    const N = T.numero;
    const zone = h('div', { class: 'vue vue--numero' }, h('p', { class: 'note', role: 'status' }, T.guides.chargement));
    conteneur.append(zone);
    let vivant = true;
    const etat = { zoneResultat: null, ctx: null, champ: null };
    courant = etat;
    Promise.all([contenu.plusieurs('guides', 'vocabulaire'), contenu.liens()]).then(([[guides, vocabulaire], liens]) => {
      if (!vivant) return;
      const guide = guides.guides.find((g) => g.id === 'numero-a-verifier');
      const [k1] = guide.etapes;
      const citation = vocabulaire.termes.find((t) => t.id === 'citation');
      const texte = String(route.params.t ?? '').slice(0, LIMITE);
      const champ = h('textarea', { id: 'numero-texte', name: 't', class: 'champ__saisie champ__saisie--texte', rows: '3', maxlength: String(LIMITE), spellcheck: 'false', autocomplete: 'off', aria: { describedby: 'numero-aide' } });
      champ.value = texte;
      const zoneResultat = h('section', { class: 'numero__resultat', aria: { labelledby: 'numero-resultat' } });
      const form = h('form', { class: 'numero__formulaire', novalidate: true },
        h('label', { class: 'champ__libelle', for: 'numero-texte' }, N.champ),
        champ,
        h('p', { id: 'numero-aide', class: 'champ__aide' }, N.champAide),
        h('p', { class: 'numero__boutons' },
          h('button', { type: 'submit', class: 'bouton bouton--principal' }, N.lire),
          h('button', { type: 'button', class: 'bouton bouton--lien', on: { click: () => { champ.value = ''; aller(formerHash('numero'), { remplacer: true }); champ.focus(); } } }, N.effacer)));
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        aller(formerHash('numero', [], { t: champ.value.trim().slice(0, LIMITE) }));
      });
      remplacer(zone,
        h('h1', null, N.titre),
        h('section', { class: 'numero__citation', aria: { labelledby: 'numero-citation' } },
          h('h2', { id: 'numero-citation' }, N.citationTitre),
          citation ? h('p', { class: 'chapeau' }, citation.definition, ' ', mot('citation', T.vocabulaire.terme)) : null,
          h('p', null, k1.instruction),
          h('p', { class: 'numero__exemple' }, k1.ce_que_l_ecran_montre)),
        h('section', { class: 'numero__saisie', aria: { labelledby: 'numero-form' } },
          h('h2', { id: 'numero-form' }, N.formulaireTitre),
          form,
          h('p', { class: 'note' }, N.perimetre)),
        zoneResultat,
        h('section', { class: 'numero__ensuite', aria: { labelledby: 'numero-ensuite' } },
          h('h2', { id: 'numero-ensuite' }, N.ensuiteTitre),
          h('ul', { class: 'liens-internes liens-internes--guides' },
            h('li', null, h('a', { href: formerHash('') }, icone('loupe'), h('span', null, N.rechercherParNom))),
            h('li', null, h('a', { href: formerHash('guides', ['numero-a-verifier']) }, icone('fleche'), h('span', null, N.guideComplet))))));
      Object.assign(etat, { zoneResultat, champ, ctx: { T, guide, liens, leger, vivant: () => vivant } });
      dessinerResultat(zoneResultat, texte, etat.ctx);
      // A shared or reloaded address keeps the reader at the top, with the explanation first.
      finDeRendu(texte ? zoneResultat.querySelector('h2') : null);
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

  // A new text: redraw the answer only, and move to it.
  actualiser(route) {
    const etat = courant;
    if (!etat?.ctx) return false;
    const texte = String(route.params.t ?? '').slice(0, LIMITE);
    if (etat.champ.value.trim() !== texte) etat.champ.value = texte;
    const titre = dessinerResultat(etat.zoneResultat, texte, etat.ctx);
    if (titre) viserTitre(titre);
    return true;
  },
};
