/**
 * Data layer: from the columnar files of site/data/ to plain objects for the views.
 *
 *   persons  -> decree -> coverage of the year        (Archives nationales index)
 *   entries  -> decree as published -> volume         (printed Bulletin officiel)
 *   Archives nationales decree -> publication(s) of the same date in the Bulletin (1883-1888)
 *
 * Pure functions, no network, no DOM: it runs inside the data worker (donnees/service.js) and
 * in Node tests. File formats: docs/format-donnees-an.md and docs/format-donnees-bogga.md.
 * Row ranks ("ligne") change at every rebuild of the data: they are valid for one session
 * only. What may be kept in an address is the "ref" of a fiche.
 */

import { isParticle, k1, tokenize } from '../recherche/normaliser.js';
import { typographier } from '../textes/typographie.js';

/** Our own sentences in the meta files (labels, warnings): French typography, like the interface. */
const phrase = (v) => (typeof v === 'string' ? typographier(v) : v ?? null);
const phrases = (list) => (Array.isArray(list) ? list.map(phrase) : []);

/**
 * Reader of one columnar file {champs, tables?, lignes}.
 * @param {{champs: string[], tables?: Object, lignes: Array[]}} data
 */
export function lecteurColonnes(data) {
  if (data === null || typeof data !== 'object' || !Array.isArray(data.champs) || !Array.isArray(data.lignes)) {
    throw new TypeError('Columnar file expected: {"champs": […], "lignes": […]}.');
  }
  const rang = new Map(data.champs.map((name, i) => [String(name), i]));
  const tables = data.tables && typeof data.tables === 'object' ? data.tables : {};
  const brut = (ligne, champ) => {
    const row = data.lignes[ligne];
    const i = rang.get(champ);
    return row === undefined || i === undefined ? undefined : row[i];
  };
  return {
    taille: data.lignes.length,
    a: (champ) => rang.has(champ),
    brut,
    /** Value of a field; a field named like a table is an index into that table. */
    valeur(ligne, champ) {
      const v = brut(ligne, champ);
      const table = tables[champ];
      if (Array.isArray(table) && Number.isInteger(v)) return table[v] ?? null;
      return v ?? null;
    },
    /** Position of a value in a table (to compare raw cells quickly), or -1. */
    indexTable(champ, valeur) {
      const table = tables[champ];
      return Array.isArray(table) ? table.indexOf(valeur) : -1;
    },
    particulier(sorte, ligne) {
      const map = data.liens_particuliers?.[sorte];
      return map && Object.hasOwn(map, String(ligne)) ? map[String(ligne)] : undefined;
    },
  };
}

/**
 * Sorts of printed decree (bogga-decrets "nature") that can publish a decree of each family of
 * the Archives nationales titles. A family not listed here is not compared.
 */
const NATURES_COMPATIBLES = {
  reintegration: ['reintegration', 'titre'],
  naturalisation: ['admission', 'naturalisation', 'titre'],
  'admission-citoyen': ['admission', 'naturalisation', 'titre'],
  'composite-avec-citoyen': ['admission', 'naturalisation', 'reintegration', 'titre'],
  'naturalisation+reintegration': ['admission', 'naturalisation', 'reintegration', 'titre'],
};

/** Can a printed decree of this nature be the publication of an AN decree of this family? */
export function natureCompatible(famille, nature) {
  const ok = NATURES_COMPATIBLES[famille];
  return ok === undefined || typeof nature !== 'string' || ok.includes(nature);
}

const motUtile = (t) => t.k0.length >= 3 && !isParticle(t.k0);

/**
 * The words that can find a household in a printed list: the surname (before the comma) of
 * every member; when the inventory writes no surname, every word of the principal's name, all
 * of which must then be found.
 * @param {{nom: string|null}[]} membres principal first
 * @returns {{cles: Set<string>, tous: boolean}}
 */
export function motsDuMenage(membres) {
  const cles = new Set();
  for (const m of membres ?? []) {
    const nom = typeof m?.nom === 'string' ? m.nom : '';
    const virgule = nom.indexOf(',');
    if (virgule <= 0) continue;
    for (const t of tokenize(nom.slice(0, virgule))) if (motUtile(t)) cles.add(k1(t.cle));
  }
  if (cles.size > 0) return { cles, tous: false };
  for (const t of tokenize(membres?.[0]?.nom ?? '')) if (motUtile(t)) cles.add(k1(t.cle));
  return { cles, tous: true };
}

/** Is the household named in the words read on a printed decree? */
export function menageReconnu(mots, clesDuDecret) {
  if (mots.cles.size === 0 || !clesDuDecret || clesDuDecret.size === 0) return false;
  const present = [...mots.cles].map((c) => clesDuDecret.has(c));
  return mots.tous ? mots.cles.size >= 2 && present.every(Boolean) : present.some(Boolean);
}

function tableEnObjets(table) {
  if (!table || !Array.isArray(table.champs) || !Array.isArray(table.lignes)) return [];
  return table.lignes.map((row) => Object.fromEntries(table.champs.map((name, i) => [name, row[i]])));
}

const bits = (value, libelles) => {
  const out = [];
  if (!Number.isInteger(value)) return out;
  for (const [key, libelle] of Object.entries(libelles ?? {})) {
    const bit = Number(key);
    if (Number.isInteger(bit) && (value & bit) !== 0) out.push({ bit, libelle: String(libelle) });
  }
  return out;
};

/**
 * How a year of the Archives nationales index can be searched from this site:
 *   'lue'              names typed and published here: a name search reads it
 *   'lue-en-partie'    names published here, but typed for part of the decrees only
 *   'noms-aux-an'      names typed at the Archives nationales, not published here
 *   'image-en-partie'  a few names typed at the Archives nationales (not published here); most decrees are images only
 *   'image'            no name typed anywhere: images only
 */
export function lectureAnnee({ etat, noms_exportes: exportes }) {
  if (etat === 'image') return 'image';
  if (exportes) return etat === 'indexe' ? 'lue' : 'lue-en-partie';
  return etat === 'indexe' ? 'noms-aux-an' : 'image-en-partie';
}

/**
 * @param {Object} fichiers parsed data files:
 *        anDecrets, anPersonnes, anMeta, boggaVolumes, boggaDecrets, boggaEntrees, boggaMeta
 */
export function creerModele({ anDecrets, anPersonnes, anMeta, boggaVolumes, boggaDecrets, boggaEntrees, boggaMeta }) {
  const P = lecteurColonnes(anPersonnes);
  const D = lecteurColonnes(anDecrets);
  const V = lecteurColonnes(boggaVolumes);
  const B = lecteurColonnes(boggaDecrets);
  const E = lecteurColonnes(boggaEntrees);
  const metaAn = anMeta ?? {};
  const metaBogga = boggaMeta ?? {};

  const anneesAn = tableEnObjets(metaAn.couverture_annees).map((y) => ({ ...y, lecture: lectureAnnee(y) }));
  const trimestresAn = tableEnObjets(metaAn.couverture_trimestres).map((y) => ({ ...y, lecture: lectureAnnee(y) }));
  const inventaires = tableEnObjets(metaAn.inventaires);
  const couvertureParAnnee = new Map(anneesAn.map((y) => [y.annee, y]));
  const couvertureParTrimestre = new Map(trimestresAn.map((y) => [`${y.annee}/${y.trim}`, y]));

  // ----- Bulletin: volumes, decrees -------------------------------------------------------

  function volume(ligne) {
    if (!Number.isInteger(ligne) || ligne < 0 || ligne >= V.taille) return null;
    return {
      ligne,
      annee: V.valeur(ligne, 'annee'),
      item: V.valeur(ligne, 'item'),
      doc: V.valeur(ligne, 'doc'),
      famille: V.valeur(ligne, 'famille'),
      lienVolume: V.valeur(ligne, 'lien_volume'),
      lienPage: V.valeur(ligne, 'lien_page'),
      imagePage: V.valeur(ligne, 'image_page'),
      // "non vérifié", or a sentence starting with "oui :", "partiel :" or "non :"
      lienVerifie: V.valeur(ligne, 'lien_verifie'),
      bibliotheque: V.valeur(ligne, 'bibliotheque'),
      droits: V.valeur(ligne, 'droits'),
      // number of leaves of the scanned volume (leaf numbers above it do not exist)
      feuilles: Number.isInteger(V.valeur(ligne, 'pagination')?.feuilles) ? V.valeur(ligne, 'pagination').feuilles : null,
    };
  }

  function decretBulletin(ligne, { suivreDoublon = true } = {}) {
    if (!Number.isInteger(ligne) || ligne < 0 || ligne >= B.taille) return null;
    const doublonDe = B.valeur(ligne, 'doublon_de');
    return {
      ligne,
      volume: volume(B.valeur(ligne, 'volume')),
      nature: B.valeur(ligne, 'nature'),
      dates: B.valeur(ligne, 'dates') ?? [],
      dateEtat: B.valeur(ligne, 'date_etat'),
      dateBrute: B.valeur(ligne, 'date_brute'),
      entete: B.valeur(ligne, 'entete'),
      article: B.valeur(ligne, 'article'),
      livraison: B.valeur(ligne, 'livraison'),
      livraisonEtat: B.valeur(ligne, 'livraison_etat'),
      livraisonDate: B.valeur(ligne, 'livraison_date'),
      livraisonDateEtat: B.valeur(ligne, 'livraison_date_etat'),
      page: B.valeur(ligne, 'page'),
      feuille: B.valeur(ligne, 'feuille'),
      derniereFeuille: B.valeur(ligne, 'derniere_feuille'),
      entrees: B.valeur(ligne, 'entrees'),
      totalImprime: B.valeur(ligne, 'total_imprime'),
      drapeaux: bits(B.valeur(ligne, 'drapeaux'), metaBogga.drapeaux_decrets),
      // The first publication, when this one is a republication (both citations are kept).
      doublonDe: suivreDoublon && Number.isInteger(doublonDe) ? decretBulletin(doublonDe, { suivreDoublon: false }) : null,
    };
  }

  let clesParDecret = null;
  /** The words (k1 keys) the machine read in the entries of one printed decree. */
  function clesDuDecretBulletin(ligne) {
    if (clesParDecret === null) {
      clesParDecret = new Map();
      for (let i = 0; i < E.taille; i++) {
        const d = E.brut(i, 'decret');
        if (!Number.isInteger(d)) continue;
        if (!clesParDecret.has(d)) clesParDecret.set(d, new Set());
        const set = clesParDecret.get(d);
        for (const champ of ['nom', 'texte']) {
          for (const t of tokenize(E.valeur(i, champ) ?? '', { ocr: true })) if (motUtile(t)) set.add(k1(t.cle));
        }
      }
    }
    return clesParDecret.get(ligne) ?? null;
  }

  /**
   * The decrees printed on the date of an AN decree, each said whether the machine read the
   * household's name in it ("nomReconnu") and whether its sort fits the AN title
   * ("natureCompatible"): recognised first, then the compatible ones, then the others. Several
   * decrees bear the same date; a date alone never makes a publication.
   */
  function publicationsDuMenage(decret, membres) {
    if (decret === null) return [];
    const mots = motsDuMenage(membres);
    const rang = (p) => (p.nomReconnu ? 0 : p.natureCompatible ? 1 : 2);
    return publicationsDuJour(decret.date)
      .map((p) => ({ ...p, nomReconnu: menageReconnu(mots, clesDuDecretBulletin(p.ligne)), natureCompatible: natureCompatible(decret.famille, p.nature) }))
      .map((p, i) => ({ p, i }))
      .sort((x, y) => rang(x.p) - rang(y.p) || x.i - y.i)
      .map((x) => x.p);
  }

  let parDate = null;
  /** Decrees printed in the Bulletin that bear this date (ISO), in file order. */
  function publicationsDuJour(dateIso) {
    if (typeof dateIso !== 'string') return [];
    if (parDate === null) {
      parDate = new Map();
      for (let i = 0; i < B.taille; i++) {
        for (const d of B.valeur(i, 'dates') ?? []) {
          if (typeof d !== 'string') continue;
          if (!parDate.has(d)) parDate.set(d, []);
          parDate.get(d).push(i);
        }
      }
    }
    return (parDate.get(dateIso) ?? []).map((i) => decretBulletin(i));
  }

  // ----- Archives nationales: decrees, households -----------------------------------------

  function couvertureDe(annee, trim) {
    const y = (trim !== null && trim !== undefined ? couvertureParTrimestre.get(`${annee}/${trim}`) : undefined) ?? couvertureParAnnee.get(annee);
    return y === undefined ? null : { annee: y.annee, trim: y.trim ?? null, etat: y.etat, lecture: y.lecture, filae: y.filae === true };
  }

  function decretAn(ligne) {
    if (!Number.isInteger(ligne) || ligne < 0 || ligne >= D.taille) return null;
    const classe = D.valeur(ligne, 'classe');
    const annee = D.valeur(ligne, 'annee');
    const trim = D.valeur(ligne, 'trim');
    const date = D.valeur(ligne, 'date');
    return {
      ligne,
      inv: D.valeur(ligne, 'inv'),
      notice: D.valeur(ligne, 'notice'),
      date,
      drapDate: D.valeur(ligne, 'drap_date') ?? '',
      titre: D.valeur(ligne, 'titre'),
      famille: D.valeur(ligne, 'famille'),
      classe,
      classeLibelle: phrase(metaAn.classes?.[classe]),
      cote: D.valeur(ligne, 'cote'),
      drapCote: D.valeur(ligne, 'drap_cote') ?? '',
      coteSuggeree: D.valeur(ligne, 'cote_sug'),
      doc: D.valeur(ligne, 'doc'),
      etat: D.valeur(ligne, 'etat'),
      nPersonnes: D.valeur(ligne, 'n_pers'),
      nExportees: D.valeur(ligne, 'n_exp'),
      annee,
      trim,
      contexte: D.valeur(ligne, 'contexte'),
      // undefined: follow the template; null: no link at all; string: the address of the source
      lienNoticeParticulier: D.particulier('notice', ligne),
      lienImagesParticulier: D.particulier('images', ligne),
      couverture: couvertureDe(annee, trim),
    };
  }

  function membre(ligne) {
    return {
      ligne,
      role: P.valeur(ligne, 'role'),
      nom: P.valeur(ligne, 'nom'),
      an: P.valeur(ligne, 'an'),
      prec: P.valeur(ligne, 'prec') ?? '',
      naiss: P.valeur(ligne, 'naiss'),
      lieu: P.valeur(ligne, 'lieu'),
      res: P.valeur(ligne, 'res'),
      prof: P.valeur(ligne, 'prof'),
    };
  }

  const principalDe = (ligne) => {
    const p = P.brut(ligne, 'princ');
    return Number.isInteger(p) && p >= 0 && p < P.taille ? p : ligne;
  };

  /** The whole notice of a person of the Archives nationales index, from any of its rows. */
  function ficheAn(ligne) {
    if (!Number.isInteger(ligne) || ligne < 0 || ligne >= P.taille) return null;
    const princ = principalDe(ligne);
    const membres = [membre(princ)];
    for (let i = princ + 1; i < P.taille && P.brut(i, 'princ') === princ; i++) membres.push(membre(i));
    const decret = decretAn(P.brut(princ, 'dec'));
    const indice = P.valeur(princ, 'ind');
    const noticeId = P.valeur(princ, 'notice');
    return {
      source: 'an',
      cle: `an:${princ}`,
      ref: decret !== null && typeof noticeId === 'string' ? { source: 'an', inv: decret.inv, notice: noticeId } : null,
      membres,
      dossier: P.valeur(princ, 'dossier'),
      coteDossier: P.valeur(princ, 'cote'),
      notice: noticeId,
      aSesImages: P.valeur(princ, 'img') === 1,
      lienNoticeParticulier: P.particulier('notice', princ),
      lienImagesParticulier: P.particulier('images', princ),
      // A heuristic ranking, never a fact: always shown under the word "indice".
      indice: typeof indice === 'string' ? { code: indice, libelle: phrase(metaAn.indices?.[indice]), regle: P.valeur(princ, 'regle') } : null,
      // Relatives named by the inventory but withheld here (possibly alive), and mentions typed
      // in place of a name: counts only, so that the notice can say that something is missing.
      prochesNonAffiches: Number(metaAn.vie_privee?.apparentes_retenus_par_principal?.[String(princ)] ?? 0) || 0,
      mentionsNonNoms: Number(metaAn.noms_inexploitables?.par_principal?.[String(princ)] ?? 0) || 0,
      neEnAlgerie: P.valeur(princ, 'nea') ?? '',
      resideEnAlgerie: P.valeur(princ, 'rea') ?? '',
      decret,
      publications: publicationsDuMenage(decret, membres),
      credit: {
        gabarit: metaAn.credit?.gabarit ?? null,
        lieu: metaAn.credit?.lieu_de_conservation ?? null,
        dateDesInformations: metaAn.credit?.date_des_informations ?? null,
      },
    };
  }

  // ----- Bulletin: entries -----------------------------------------------------------------

  let lignesParPage = null;
  const clePage = (ligne) => `${V.valeur(E.brut(ligne, 'volume'), 'annee')}/${E.brut(ligne, 'feuille')}`;
  /** Rows of the entries printed on one leaf, in file order (they are not always contiguous). */
  function entreesDeLaPage(cle) {
    if (lignesParPage === null) {
      lignesParPage = new Map();
      for (let i = 0; i < E.taille; i++) {
        const key = clePage(i);
        if (!lignesParPage.has(key)) lignesParPage.set(key, []);
        lignesParPage.get(key).push(i);
      }
    }
    return lignesParPage.get(cle) ?? [];
  }

  function ficheBogga(ligne) {
    if (!Number.isInteger(ligne) || ligne < 0 || ligne >= E.taille) return null;
    const vol = volume(E.valeur(ligne, 'volume'));
    const feuille = E.valeur(ligne, 'feuille');
    const rang = entreesDeLaPage(clePage(ligne)).indexOf(ligne);
    return {
      source: 'bogga',
      cle: `bogga:${ligne}`,
      ref: vol !== null && Number.isInteger(feuille) ? { source: 'bogga', annee: vol.annee, feuille, rang } : null,
      ligne,
      nom: E.valeur(ligne, 'nom'),
      texte: E.valeur(ligne, 'texte'),
      marqueurs: bits(E.valeur(ligne, 'marqueurs'), metaBogga.marqueurs),
      nationalite: E.valeur(ligne, 'nationalite'),
      naissance: E.valeur(ligne, 'naissance'),
      residence: E.valeur(ligne, 'residence'),
      page: E.valeur(ligne, 'page'),
      feuille,
      drapeaux: bits(E.valeur(ligne, 'drapeaux'), metaBogga.drapeaux_entrees),
      decret: decretBulletin(E.valeur(ligne, 'decret')),
      volume: vol,
      credit: { texte: metaBogga.credit ?? null },
      etatsDates: metaBogga.etats_dates ?? {},
      etatsLivraison: metaBogga.etats_numeros_livraison ?? {},
    };
  }

  // ----- Lookups ---------------------------------------------------------------------------

  /** Key of the card a search result belongs to. */
  function cleDe(groupe, ligne) {
    return groupe === 'an' ? `an:${principalDe(ligne)}` : `${groupe}:${ligne}`;
  }

  function fiche(cle) {
    const m = /^(an|bogga):(\d+)$/.exec(String(cle));
    if (m === null) return null;
    return m[1] === 'an' ? ficheAn(Number(m[2])) : ficheBogga(Number(m[2]));
  }

  let parNotice = null;
  /** A fiche from the stable reference kept in an address (see "ref" of a fiche). */
  function ficheParReference(ref) {
    if (ref?.source === 'an') {
      if (parNotice === null) {
        parNotice = new Map();
        const principal = P.indexTable('role', 'principal');
        for (let i = 0; i < P.taille; i++) {
          if (P.brut(i, 'role') !== principal) continue;
          const id = P.brut(i, 'notice');
          if (typeof id === 'string') parNotice.set(`${D.valeur(P.brut(i, 'dec'), 'inv')}/${id}`, i);
        }
      }
      const ligne = parNotice.get(`${ref.inv}/${ref.notice}`);
      return ligne === undefined ? null : ficheAn(ligne);
    }
    if (ref?.source === 'bogga') {
      const rang = Number(ref.rang);
      if (!Number.isInteger(rang) || rang < 0) return null;
      const ligne = entreesDeLaPage(`${ref.annee}/${ref.feuille}`)[rang];
      return ligne === undefined ? null : ficheBogga(ligne);
    }
    return null;
  }

  /**
   * Decrees of the Archives nationales index, for the decree browser.
   * @param {{annees?: number[], classes?: string[], etats?: string[]}} [filtre]
   */
  function decretsAn({ annees, classes, etats } = {}) {
    const years = Array.isArray(annees) ? new Set(annees) : null;
    const cls = Array.isArray(classes) ? new Set(classes) : null;
    const sts = Array.isArray(etats) ? new Set(etats) : null;
    const out = [];
    for (let i = 0; i < D.taille; i++) {
      if (years !== null && !years.has(D.valeur(i, 'annee'))) continue;
      if (cls !== null && !cls.has(D.valeur(i, 'classe'))) continue;
      if (sts !== null && !sts.has(D.valeur(i, 'etat'))) continue;
      out.push(decretAn(i));
    }
    return out;
  }

  /**
   * The printed page number of one leaf, as the data read it (a decree or an entry printed on
   * that leaf), or null when the data hold none: never computed, never taken from an address.
   */
  function pageDeLaFeuille(annee, feuille) {
    if (!Number.isInteger(annee) || !Number.isInteger(feuille)) return null;
    for (let i = 0; i < B.taille; i++) {
      if (B.brut(i, 'feuille') === feuille && V.valeur(B.brut(i, 'volume'), 'annee') === annee && Number.isInteger(B.brut(i, 'page'))) return B.brut(i, 'page');
    }
    for (const ligne of entreesDeLaPage(`${annee}/${feuille}`)) {
      if (Number.isInteger(E.brut(ligne, 'page'))) return E.brut(ligne, 'page');
    }
    return null;
  }

  /** The Bulletin volume of one year (the guide filled for one page needs its identifiers). */
  function volumeDeLAnnee(annee) {
    for (let i = 0; i < V.taille; i++) if (V.valeur(i, 'annee') === annee) return volume(i);
    return null;
  }

  // ----- Coverage: what a search reads, and what it does not ---------------------------------

  function couverture() {
    const inventairesParAnnee = new Map();
    for (const inv of inventaires) {
      if (!inventairesParAnnee.has(inv.annee)) inventairesParAnnee.set(inv.annee, []);
      inventairesParAnnee.get(inv.annee).push({ inv: inv.inv, trim: inv.trim ?? null, titre: inv.titre, cotes: inv.cotes });
    }
    const an = {
      genereLe: metaAn.genere_le ?? null,
      releveLe: metaAn.source?.telecharges_au ?? metaAn.source?.telecharges_du ?? null,
      noms: metaAn.comptes?.exporte?.occurrences_de_noms ?? null,
      principaux: metaAn.comptes?.exporte?.principaux ?? null,
      // person notices of the WHOLE index (all territories): the site keeps the Algeria part only
      noticesIndex: metaAn.comptes?.corpus?.notices_de_personnes ?? null,
      epouses: metaAn.comptes?.exporte?.epouses ?? null,
      enfants: metaAn.comptes?.exporte?.enfants ?? null,
      annees: anneesAn.map((y) => ({
        annee: y.annee,
        etat: y.etat,
        lecture: y.lecture,
        filae: y.filae === true,
        decrets: y.decrets,
        decretsAvecNoms: y.decrets_avec_noms,
        algDecrets: y.alg_decrets,
        algAvecNoms: y.alg_avec_noms,
        personnesExportees: y.personnes_exportees,
        inventaires: inventairesParAnnee.get(y.annee) ?? [],
      })),
      // Only the years cut into quarters, with the state of each quarter.
      trimestres: trimestresAn.map((y) => ({
        annee: y.annee, trim: y.trim, etat: y.etat, lecture: y.lecture, algDecrets: y.alg_decrets, algAvecNoms: y.alg_avec_noms, personnesExportees: y.personnes_exportees,
      })),
      avertissements: phrases(metaAn.avertissements),
      credit: metaAn.credit ?? null,
    };
    const volumeParAnnee = new Map();
    for (let i = 0; i < V.taille; i++) volumeParAnnee.set(V.valeur(i, 'annee'), i);
    const bogga = {
      genereLe: metaBogga.genere_le ?? null,
      entrees: metaBogga.totaux?.entrees ?? null,
      decrets: metaBogga.totaux?.decrets ?? null,
      annees: (Array.isArray(metaBogga.couverture) ? metaBogga.couverture : []).map((y) => ({
        annee: y.annee,
        etat: y.etat,
        // "lu": a volume was read by machine for this year (it may hold no decree at all).
        lu: Number.isInteger(y.volume),
        decrets: y.decrets ?? 0,
        entrees: y.entrees ?? 0,
        queFaire: phrase(y.que_faire || null),
        tauxPagesTable: y.taux_pages_table ?? null,
        tauxListesNumerotees: y.taux_listes_numerotees ?? null,
      })),
      pagesALireALaMain: (Array.isArray(metaBogga.pages_a_lire_a_la_main) ? metaBogga.pages_a_lire_a_la_main : []).map((p) => ({
        annee: p.annee,
        page: p.page ?? null,
        feuille: p.feuille ?? null,
        raison: phrase(p.raison),
        volume: volume(p.volume ?? volumeParAnnee.get(p.annee)),
      })),
      avertissements: phrases(metaBogga.avertissements),
      credit: metaBogga.credit ?? null,
      bibliotheques: Array.isArray(metaBogga.bibliotheques) ? metaBogga.bibliotheques : [],
    };
    return { an, bogga };
  }

  return { cleDe, fiche, ficheAn, ficheBogga, ficheParReference, decretsAn, decretBulletin, publicationsDuJour, volumeDeLAnnee, pageDeLaFeuille, couverture, tailles: { anPersonnes: P.taille, anDecrets: D.taille, boggaEntrees: E.taille, boggaDecrets: B.taille } };
}
