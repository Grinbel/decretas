/**
 * In-memory name index, built once in the browser (or in Node) from name occurrences.
 *
 * An OCCURRENCE is one written name with where it comes from:
 *   { id, nom, anneeNaissance: number|null, groupe: string, ocr?: boolean, ...anything }
 * "groupe" names the source family ("an", "bogga"…). Extra properties are kept untouched and
 * come back with the results. The caller decides what an occurrence is (a person notice, a
 * spouse, a printed entry): the terms of a query must all be found inside ONE occurrence.
 *
 * The index stores, for every distinct searchable form (see normaliser.js#nameForms), its
 * three keys and the list of occurrences where it appears as a written word ("mot"), as
 * particle + word glued by us ("colle"), or as a word minus its glued prefix ("decolle").
 */

import { tokenize, nameForms, keysOf, isParticle, KIND } from './normaliser.js';

/** Thrown when a data file does not have the expected {champs, lignes} shape. */
export class DataFormatError extends Error {
  constructor(message) {
    super(message);
    this.name = 'DataFormatError';
  }
}

export const MAX_WORDS = 250;
/** Written words remembered per detached stem ("chabane" <- Benchabane, Bouchabane…), at most. */
export const STEM_SOURCES_MAX = 64;
/** Flag of an index entry (entMeta): glued form whose article is fused ("El Arbi" = "Larbi"). */
export const FUSED_BIT = 0x2000;
const NAME_FIELDS = ['nom', 'nom_brut', 'nomBrut', 'nom_complet', 'nomComplet', 'name', 'texte'];
const ID_FIELDS = ['id', 'identifiant', 'notice_id', 'noticeId', 'cle'];
// "annee" alone is deliberately absent: in a source file it may be the year of the decree.
// "an" is the birth year of an-personnes.json, "naissance" the birth year of bogga-entrees.json
// (an integer there). A column that holds free text ("1 janvier 1882 (Alger)") gives no year:
// only a number, or a text that STARTS with four digits, is read (see toYear).
const YEAR_FIELDS = ['anneeNaissance', 'annee_naissance', 'naissance_annee', 'naissanceAnnee', 'an_naissance', 'an', 'naissance', 'ne_en'];

function displayOf(raw) {
  if (raw.length > 1 && raw === raw.toUpperCase() && raw !== raw.toLowerCase()) {
    return raw[0] + raw.slice(1).toLowerCase();
  }
  return raw;
}

function toYear(value) {
  if (typeof value === 'number') return Number.isInteger(value) && value >= 1000 && value <= 2100 ? value : null;
  if (typeof value === 'string') {
    const m = /^\s*(\d{4})\b/.exec(value);
    if (m) return toYear(Number(m[1]));
  }
  return null;
}

/**
 * @typedef {Object} NameIndex
 * @property {number} size                 number of occurrences
 * @property {Object[]} occurrences        the occurrences, as given
 * @property {string[]} groups             group names, in order of first appearance
 * @property {number[]} groupCounts        occurrences per group
 * @property {boolean[]} groupOcr          true for a printed (OCR) group
 * @property {number} formCount            number of distinct forms
 * @property {number} buildMs              time spent building
 * (the other properties are internal to chercher.js and suggestions.js)
 */

/**
 * Build the index.
 * @param {Object[]} occurrences {id, nom, anneeNaissance|null, groupe, ocr?}
 * @param {{groupesOcr?: string[]}} [options] groupesOcr: groups read by OCR from print, where
 *        "bon"/"ban"/"ten"… between two names is read as "ben" ("on" as "ou") and stray signs inside a word
 *        are ignored. An occurrence may override with its own boolean "ocr".
 * @returns {NameIndex}
 */
export function buildIndex(occurrences, { groupesOcr = [] } = {}) {
  const started = performance.now();
  const n = occurrences.length;
  const years = new Int16Array(n);
  const groupOf = new Uint8Array(n);
  const groups = [];
  const groupIds = new Map();
  const groupCounts = [];
  const groupOcr = [];
  const ocrSet = new Set(groupesOcr);

  const formCle = [];
  const formDisplay = [];
  const formDisplayKind = [];
  const formGluedApprox = [];
  const formFused = []; // 1 when the form was obtained by fusing an article ("El Arbi" -> larbi)
  const byCle = new Map();
  const postings = [];
  const stemSources = new Map();
  const occStart = new Uint32Array(n + 1);
  const entForm = [];
  const entMeta = [];

  for (let i = 0; i < n; i++) {
    const o = occurrences[i];
    const groupName = String(o.groupe ?? '');
    let g = groupIds.get(groupName);
    if (g === undefined) {
      if (groups.length >= 255) throw new RangeError('Trop de groupes de sources (255 au plus).');
      g = groups.length;
      groupIds.set(groupName, g);
      groups.push(groupName);
      groupCounts.push(0);
      groupOcr.push(ocrSet.has(groupName));
    }
    groupOf[i] = g;
    groupCounts[g]++;
    years[i] = toYear(o.anneeNaissance) ?? 0;

    const ocr = typeof o.ocr === 'boolean' ? o.ocr : groupOcr[g];
    const tokens = tokenize(o.nom, { ocr });
    if (tokens.length > MAX_WORDS) tokens.length = MAX_WORDS;
    const forms = nameForms(tokens, { ocr });
    occStart[i] = entForm.length;
    let wordFid = -1;
    for (let k = 0; k < forms.length; k++) {
      const f = forms[k];
      let fid = byCle.get(f.cle);
      if (fid === undefined) {
        fid = formCle.length;
        byCle.set(f.cle, fid);
        formCle.push(f.cle);
        formDisplay.push('');
        formDisplayKind.push(3);
        formGluedApprox.push(0);
        formFused.push(0);
      }
      if (f.fused) formFused[fid] = 1;
      entForm.push(fid);
      // Bit 12: a glued form may be compared at k2 only when its own word is long enough
      // ("ben Ali" glued into "benali" must not be an approximate "Bonelli").
      let approx = 0;
      if (f.kind === KIND.GLUED) {
        const own = tokens[f.pos];
        approx = keysOf(own.cle).k2ok || isParticle(own.k0) ? 0x1000 : 0;
        if (approx) formGluedApprox[fid] = 1;
      }
      // Bit 13: glued form with a fused article ("El Arbi" read as "larbi"), see FUSED_BIT.
      entMeta.push(f.pos | (f.span << 8) | (f.kind << 10) | approx | (f.fused ? FUSED_BIT : 0));
      const key = fid * 3 + f.kind;
      let p = postings[key];
      if (p === undefined) postings[key] = p = [];
      if (p.length === 0 || p[p.length - 1] !== i) p.push(i);
      if (f.kind === KIND.WORD) {
        wordFid = fid;
        if (formDisplayKind[fid] > KIND.WORD) {
          formDisplay[fid] = displayOf(tokens[f.pos].raw);
          formDisplayKind[fid] = KIND.WORD;
        }
      } else if (f.kind === KIND.GLUED) {
        if (formDisplayKind[fid] > KIND.GLUED) {
          const parts = [];
          for (let w = f.pos - f.span; w <= f.pos; w++) parts.push(displayOf(tokens[w].raw));
          formDisplay[fid] = parts.join(' ');
          formDisplayKind[fid] = KIND.GLUED;
        }
      } else if (wordFid >= 0) {
        let src = stemSources.get(fid);
        if (src === undefined) stemSources.set(fid, (src = []));
        if (src.length < STEM_SOURCES_MAX && !src.includes(wordFid)) src.push(wordFid);
      }
    }
  }
  occStart[n] = entForm.length;

  const formCount = formCle.length;
  const formK0 = new Array(formCount);
  const formK1 = new Array(formCount);
  const formK2 = new Array(formCount);
  const formK2ok = new Uint8Array(formCount);
  const formParticle = new Uint8Array(formCount);
  const byK0 = new Map();
  const byK1 = new Map();
  const byK2 = new Map();
  const addTo = (map, key, fid) => {
    const list = map.get(key);
    if (list === undefined) map.set(key, [fid]);
    else list.push(fid);
  };
  for (let fid = 0; fid < formCount; fid++) {
    const k = keysOf(formCle[fid]);
    formK0[fid] = k.k0;
    formK1[fid] = k.k1;
    formK2[fid] = k.k2;
    formK2ok[fid] = k.k2ok ? 1 : 0;
    formParticle[fid] = isParticle(k.k0) ? 1 : 0;
    addTo(byK0, k.k0, fid);
    addTo(byK1, k.k1, fid);
    addTo(byK2, k.k2, fid);
  }

  return {
    size: n,
    occurrences,
    groups,
    groupCounts,
    groupOcr,
    formCount,
    years,
    groupOf,
    formCle,
    formK0,
    formK1,
    formK2,
    formK2ok,
    formParticle,
    formDisplay,
    formGluedApprox,
    formFused,
    byCle,
    byK0,
    byK1,
    byK2,
    postings,
    stemSources,
    occStart,
    entForm: Int32Array.from(entForm),
    entMeta: Uint16Array.from(entMeta),
    scratchAll: new Uint32Array(n),
    scratchStrict: new Uint32Array(n),
    buildMs: performance.now() - started,
  };
}

/**
 * Number of occurrences where a form is written, as one word or as particle + word.
 * @param {NameIndex} index
 * @param {number} fid
 * @returns {number}
 */
export function writtenCount(index, fid) {
  const w = index.postings[fid * 3 + KIND.WORD];
  const g = index.postings[fid * 3 + KIND.GLUED];
  return (w ? w.length : 0) + (g ? g.length : 0);
}

/**
 * Spelling to show for a form ("Belkacem", "Bel Kaçem"), as first seen in the sources.
 * @param {NameIndex} index
 * @param {number} fid
 * @returns {string}
 */
export function displayForm(index, fid) {
  return index.formDisplay[fid] || index.formCle[fid];
}

/**
 * Summary of an index for the "bilan de recherche".
 * @param {NameIndex} index
 * @returns {{occurrences: number, formes: number, parGroupe: Object<string, number>, groupesOcr: string[], dureeConstructionMs: number}}
 */
export function indexSummary(index) {
  const parGroupe = {};
  index.groups.forEach((g, i) => {
    parGroupe[g] = index.groupCounts[i];
  });
  return {
    occurrences: index.size,
    formes: index.formCount,
    parGroupe,
    groupesOcr: index.groups.filter((g, i) => index.groupOcr[i]),
    dureeConstructionMs: Math.round(index.buildMs),
  };
}

function pickField(champs, wanted, candidates, label, required) {
  if (wanted !== undefined && wanted !== null && wanted !== '') {
    const idx = champs.indexOf(wanted);
    if (idx < 0) {
      throw new DataFormatError(`Colonne « ${wanted} » absente (${label}). Colonnes présentes : ${champs.join(', ')}.`);
    }
    return idx;
  }
  for (const c of candidates) {
    const idx = champs.indexOf(c);
    if (idx >= 0) return idx;
  }
  if (required) {
    throw new DataFormatError(`Aucune colonne reconnue pour ${label}. Colonnes présentes : ${champs.join(', ')}.`);
  }
  return -1;
}

/**
 * Generic adapter for the site data files, whose shape is columnar:
 *   { "champs": ["id", "nom", …], "lignes": [[…], […], …] }
 * Column names are read at run time; when not given, the usual names are tried.
 * Rows with an empty name are skipped. Each occurrence keeps "ligne", its row number.
 *
 * @param {{champs: string[], lignes: Array[]}} data
 * @param {Object} options
 * @param {string} options.groupe          source family of every row ("an", "bogga"…)
 * @param {string|string[]} [options.champNom]   name column(s); several columns give several
 *                                         occurrences per row (each keeps "champ")
 * @param {string} [options.champId]       identifier column (default: detected, else row number)
 * @param {string} [options.champAnnee]    birth-year column (number or text starting with a year)
 * @param {boolean} [options.ocr]          printed source read by OCR
 * @returns {{occurrences: Object[], colonnes: {nom: string[], id: string|null, annee: string|null}, lignes: number, sansNom: number}}
 * @throws {DataFormatError}
 */
export function occurrencesFromColumns(data, { groupe, champNom, champId, champAnnee, ocr } = {}) {
  if (data === null || typeof data !== 'object' || !Array.isArray(data.champs) || !Array.isArray(data.lignes)) {
    throw new DataFormatError('Format inattendu : il faut un objet {"champs": […], "lignes": […]}.');
  }
  const champs = data.champs.map(String);
  const wantedNames = Array.isArray(champNom) ? champNom : champNom ? String(champNom).split(',').map((s) => s.trim()).filter(Boolean) : [];
  const nameIdx = wantedNames.length > 0
    ? wantedNames.map((w) => pickField(champs, w, [], 'le nom', true))
    : [pickField(champs, null, NAME_FIELDS, 'le nom', true)];
  const idIdx = pickField(champs, champId, ID_FIELDS, "l'identifiant", false);
  const yearIdx = pickField(champs, champAnnee, YEAR_FIELDS, "l'année de naissance", false);

  const occurrences = [];
  let sansNom = 0;
  for (let r = 0; r < data.lignes.length; r++) {
    const row = data.lignes[r];
    if (!Array.isArray(row)) throw new DataFormatError(`Ligne ${r} : un tableau est attendu.`);
    let any = false;
    for (const ni of nameIdx) {
      const nom = row[ni];
      if (typeof nom !== 'string' || nom.trim() === '') continue;
      any = true;
      const occ = {
        id: idIdx >= 0 ? row[idIdx] : r,
        nom,
        anneeNaissance: yearIdx >= 0 ? toYear(row[yearIdx]) : null,
        groupe,
        ligne: r,
      };
      if (nameIdx.length > 1) occ.champ = champs[ni];
      if (typeof ocr === 'boolean') occ.ocr = ocr;
      occurrences.push(occ);
    }
    if (!any) sansNom++;
  }
  return {
    occurrences,
    colonnes: {
      nom: nameIdx.map((i) => champs[i]),
      id: idIdx >= 0 ? champs[idIdx] : null,
      annee: yearIdx >= 0 ? champs[yearIdx] : null,
    },
    lignes: data.lignes.length,
    sansNom,
  };
}
