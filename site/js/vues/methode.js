/**
 * #/methode — « Comment marche la recherche »: the rules of the name search in plain French
 * (distilled from docs/moteur-de-recherche.md into textes/fr.js), then what the index holds:
 * the Archives nationales year by year (and quarter by quarter where the inventories are cut so),
 * the printed Bulletin volume by volume with its quality-control rates and the pages to read by
 * hand. Every year and every count is read from the meta files (donnees/legeres.js).
 */

import { h, remplacer, viserTitre } from '../composants/dom.js';
import { avis } from '../composants/avis.js';
import { lienExterne } from '../composants/lien-externe.js';
import { attendreDonneesLegeres } from '../composants/chargement-leger.js';
import { formaterDate, formaterNombre } from '../logique/formats.js';
import { lienPageBulletin } from '../logique/liens.js';

/** Rows of the Archives nationales table: one per year, or one per quarter when the year is cut. */
export function lignesAn(couverture) {
  const parAnnee = new Map();
  for (const q of couverture.an.trimestres ?? []) {
    if (!parAnnee.has(q.annee)) parAnnee.set(q.annee, []);
    parAnnee.get(q.annee).push(q);
  }
  const out = [];
  for (const y of couverture.an.annees ?? []) {
    const qs = parAnnee.get(y.annee);
    if (qs && qs.length > 0) {
      for (const q of qs.sort((a, b) => a.trim - b.trim)) out.push({ annee: y.annee, trim: q.trim, lecture: q.lecture, algDecrets: q.algDecrets, algAvecNoms: q.algAvecNoms, publies: q.personnesExportees ?? null });
    } else {
      out.push({ annee: y.annee, trim: null, lecture: y.lecture, algDecrets: y.algDecrets, algAvecNoms: y.algAvecNoms, publies: y.personnesExportees });
    }
  }
  return out;
}

/** Rows of the Bulletin table, with the number of pages to read by hand in each volume. */
export function lignesBulletin(couverture) {
  const pages = new Map();
  for (const p of couverture.bogga.pagesALireALaMain ?? []) pages.set(p.annee, (pages.get(p.annee) ?? 0) + 1);
  return (couverture.bogga.annees ?? []).map((y) => ({ ...y, pagesALaMain: pages.get(y.annee) ?? 0 }));
}

const cellule = (libelle, contenu, attrs = {}) => h('td', { ...attrs, data: { libelle } }, contenu);

function tableauAn(couverture, T) {
  const M = T.methode;
  return h('div', { class: 'tableau-cadre', tabindex: '0', role: 'region', aria: { label: M.anTitre } },
    h('table', { class: 'tableau tableau--empile' },
      h('caption', { class: 'sr' }, M.anTitre),
      h('thead', null, h('tr', null, [M.colAnnee, M.colLecture, M.colDecretsAlg, M.colAvecNoms, M.colNomsPublies].map((c) => h('th', { scope: 'col' }, c)))),
      h('tbody', null, lignesAn(couverture).map((l) => h('tr', { class: `ligne-lecture ligne-lecture--${l.lecture}` },
        h('th', { scope: 'row', data: { libelle: M.colAnnee } }, l.trim ? M.trimestre(l.annee, l.trim) : String(l.annee)),
        cellule(M.colLecture, M.lectures[l.lecture] ?? l.lecture, { class: 'tableau__texte' }),
        cellule(M.colDecretsAlg, Number.isInteger(l.algDecrets) ? formaterNombre(l.algDecrets) : M.sansObjet),
        cellule(M.colAvecNoms, Number.isInteger(l.algAvecNoms) ? formaterNombre(l.algAvecNoms) : M.sansObjet),
        cellule(M.colNomsPublies, Number.isInteger(l.publies) ? formaterNombre(l.publies) : M.sansObjet))))));
}

function tableauBulletin(couverture, T) {
  const M = T.methode;
  const taux = (x) => (Number.isFinite(x) ? M.pourcent(x) : M.sansObjet);
  return h('div', { class: 'tableau-cadre', tabindex: '0', role: 'region', aria: { label: M.boggaTitre } },
    h('table', { class: 'tableau tableau--empile' },
      h('caption', { class: 'sr' }, M.boggaTitre),
      h('thead', null, h('tr', null, [M.colVolume, M.colEtat, M.colDecrets, M.colEntrees, M.colTable, M.colListes, M.colPages].map((c) => h('th', { scope: 'col' }, c)))),
      h('tbody', null, lignesBulletin(couverture).map((y) => h('tr', { class: y.lu ? null : 'ligne-lecture--absente' },
        h('th', { scope: 'row', data: { libelle: M.colVolume } }, String(y.annee)),
        cellule(M.colEtat, y.etat, { class: 'tableau__texte' }),
        cellule(M.colDecrets, y.lu ? formaterNombre(y.decrets) : M.sansObjet),
        cellule(M.colEntrees, y.lu ? formaterNombre(y.entrees) : M.sansObjet),
        cellule(M.colTable, taux(y.tauxPagesTable)),
        cellule(M.colListes, taux(y.tauxListesNumerotees)),
        cellule(M.colPages, y.pagesALaMain > 0 ? formaterNombre(y.pagesALaMain) : M.sansObjet))))));
}

export const vueMethode = {
  titre: (route, { T }) => T.methode.titreDocument,

  monter(conteneur, route, { T, contenu, leger }) {
    const M = T.methode;
    const zoneDonnees = h('div', { class: 'methode__donnees' });
    const zone = h('div', { class: 'vue vue--methode' },
      h('h1', null, M.titre),
      h('p', { class: 'chapeau' }, M.chapeau),
      M.sections.map((s) => h('section', { class: 'methode__section' },
        h('h2', null, s.titre),
        h('ul', { class: 'methode__points' }, s.points.map((p) => h('li', null, p))))),
      h('h2', { id: 'couverture' }, M.couvertureTitre),
      zoneDonnees);
    conteneur.append(zone);
    let vivant = true;
    contenu.liens().then((liens) => {
      if (!vivant) return;
      attendreDonneesLegeres(zoneDonnees, leger, (modele) => {
        const c = modele.couverture();
        const pages = c.bogga.pagesALireALaMain;
        remplacer(zoneDonnees,
          h('p', { class: 'note' }, M.couvertureGeneree(formaterDate(String(c.an.genereLe ?? '').slice(0, 10)), formaterDate(String(c.bogga.genereLe ?? '').slice(0, 10)))),
          h('section', { class: 'methode__couverture', aria: { labelledby: 'cv-an' } },
            h('h3', { id: 'cv-an' }, M.anTitre),
            h('p', null, M.anChapeau(formaterDate(c.an.releveLe))),
            h('details', { class: 'repli methode__tableau' }, h('summary', null, M.afficherTableau(lignesAn(c).length)), tableauAn(c, T))),
          h('section', { class: 'methode__couverture', aria: { labelledby: 'cv-bogga' } },
            h('h3', { id: 'cv-bogga' }, M.boggaTitre),
            h('p', null, M.boggaChapeau),
            h('ul', { class: 'methode__points' }, h('li', null, M.controleTable), h('li', null, M.controleListes)),
            h('details', { class: 'repli methode__tableau' }, h('summary', null, M.afficherTableau(lignesBulletin(c).length)), tableauBulletin(c, T)),
            (c.bogga.avertissements ?? []).length > 0 ? h('ul', { class: 'methode__points note' }, c.bogga.avertissements.map((a) => h('li', null, a))) : null),
          pages.length > 0 ? h('section', { class: 'methode__couverture', aria: { labelledby: 'cv-pages' } },
            h('h3', { id: 'cv-pages' }, M.pagesTitre(pages.length)),
            h('p', null, M.pagesChapeau),
            h('ul', { class: 'liens' }, pages.map((p) => {
              const lien = p.volume && Number.isInteger(p.feuille) ? lienPageBulletin(liens, p.volume, p.feuille) : null;
              const libelle = T.bilan.pageALire(p.annee, p.page);
              return h('li', null,
                lien && lien.url ? lienExterne(liens, lien.id, { identifiant: p.volume.item, volume: p.volume.doc, feuillet: p.feuille }, { libelle }) : h('span', null, libelle),
                p.raison ? h('span', { class: 'note' }, ` — ${p.raison}`) : null);
            }))) : null);
      }, { vivant: () => vivant });
    }).catch((error) => {
      if (!vivant) return;
      if (error?.name === 'ContenuIndisponible') remplacer(zoneDonnees, avis({ ton: 'attention', role: 'alert' }, T.erreurs.contenu));
      else throw error;
    });
    if (route.segments[0] === 'couverture') viserTitre(zone.querySelector('#couverture'));
    return () => {
      vivant = false;
    };
  },
};
