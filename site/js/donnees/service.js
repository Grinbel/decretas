/**
 * The data service: downloads the site's own data files, builds the name index, answers
 * searches and hands out plain objects ("fiches") to the page. It is kept free of any Worker
 * global so that it runs in a Web Worker (donnees/worker.js) and in Node tests alike.
 *
 * Everything heavy lives here, off the main thread: the 10 MB of names are parsed once, in
 * the worker; the index is given names, birth years and row ranks only
 * (recherche/index.js#occurrencesFromColumns); the page receives the few rows it shows.
 *
 * Messages IN                                         Messages OUT
 * ---------------------------------------------------------------------------------------------
 * { type: 'charger', base?: string }                  { type: 'progression', etape, recus, total }
 *                                                        etape: 'telechargement' (bytes, all files together;
 *                                                        total is null when no size is known), 'lecture', 'index'
 *                                                     { type: 'pret', resume: {index, couverture, fichiers} }
 * { type: 'chercher', id, etat, limite? }             { type: 'correspondances', id, correspondances, fiches,
 *     etat: see logique/requete.js#preparerRequete       bilan, apparentees, fidele }
 * { type: 'fiche', id, ref }                          { type: 'fiche', id, fiche }           (null when not found)
 * { type: 'decrets-an', id, filtre }                  { type: 'decrets-an', id, decrets }
 * Any failure:                                        { type: 'erreur', id?, code, fichier?, statut? }
 *     codes: 'chargement' (a file could not be downloaded), 'format' (a file is not what is
 *     expected), 'non-charge', 'message-inconnu', 'interne'. The page writes the sentence.
 *
 * The only network access is the download of the files below, from the site itself. A search
 * only reads the in-memory index: it never leaves the device.
 */

import { buildIndex, occurrencesFromColumns, indexSummary, DataFormatError } from '../recherche/index.js';
import { search } from '../recherche/chercher.js';
import { suggestVariants } from '../recherche/suggestions.js';
import { creerModele } from './modele.js';
import { preparerRequete } from '../logique/requete.js';

/** The data files, relative to the site root. "cle" names them for the model. */
export const FICHIERS = Object.freeze([
  { cle: 'anMeta', url: 'data/an-meta.json', meta: true },
  { cle: 'boggaMeta', url: 'data/bogga-meta.json', meta: true },
  { cle: 'anPersonnes', url: 'data/an-personnes.json' },
  { cle: 'anDecrets', url: 'data/an-decrets.json' },
  { cle: 'boggaEntrees', url: 'data/bogga-entrees.json' },
  { cle: 'boggaDecrets', url: 'data/bogga-decrets.json' },
  { cle: 'boggaVolumes', url: 'data/bogga-volumes.json' },
]);

/**
 * Birth-year precisions (an-personnes "prec") that the index must not filter on:
 *   'suspecte'  an impossible year as typed (1949 under an 1886 decree: a slip for 1849);
 *   'position'  a child's date paired with a first name by its rank in a list, never checked.
 * The year stays on the card with its caveat; the search keeps the notice as "year unknown"
 * instead of setting it aside when the visitor gives a birth year.
 */
export const PRECISIONS_SANS_FILTRE = Object.freeze(['suspecte', 'position']);

/**
 * The same occurrences, without the birth year where it cannot be compared.
 * @param {Object[]} occurrences  from recherche/index.js#occurrencesFromColumns (rows of anPersonnes)
 * @param {{champs: string[], tables?: Object, lignes: Array[]}} anPersonnes
 */
export function sansAnneesDouteuses(occurrences, anPersonnes) {
  const i = anPersonnes.champs.indexOf('prec');
  if (i < 0) return occurrences;
  const table = anPersonnes.tables?.prec;
  const douteuse = (row) => {
    const v = row?.[i];
    return PRECISIONS_SANS_FILTRE.includes(Array.isArray(table) && Number.isInteger(v) ? table[v] : v);
  };
  return occurrences.map((o) => (o.anneeNaissance !== null && douteuse(anPersonnes.lignes[o.ligne]) ? { ...o, anneeNaissance: null } : o));
}

class LoadError extends Error {
  constructor(fichier, statut, options) {
    super(`Download failed: ${fichier}`, options);
    this.name = 'LoadError';
    this.fichier = fichier;
    this.statut = statut;
  }
}

class FormatError extends Error {
  constructor(fichier, options) {
    super(`Unexpected format: ${fichier}`, options);
    this.name = 'FormatError';
    this.fichier = fichier;
  }
}

/** Read a response as text, reporting the bytes received (decompressed bytes when compressed). */
async function lireCorps(response, onBytes) {
  if (!response.body || typeof response.body.getReader !== 'function') {
    const text = await response.text();
    onBytes(new TextEncoder().encode(text).length);
    return text;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let text = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    text += decoder.decode(value, { stream: true });
    onBytes(value.byteLength);
  }
  return text + decoder.decode();
}

/** Sizes announced by the two meta files for the big files (decompressed bytes), by file name. */
function taillesAnnoncees(anMeta, boggaMeta) {
  const out = new Map();
  for (const meta of [anMeta, boggaMeta]) {
    for (const [name, info] of Object.entries(meta?.fichiers ?? {})) {
      if (Number.isFinite(info?.octets) && info.octets > 0) out.set(name, info.octets);
    }
  }
  return out;
}

/**
 * @param {{post: (message: Object) => void, fetch: (url: string) => Promise<Response>, base?: string|null,
 *          maintenant?: () => number}} env   base: address the relative file URLs are resolved against
 * @returns {{handle: (message: Object) => Promise<void>}}
 */
export function creerService({ post, fetch: fetchFile, base: defaultBase = null, maintenant = () => Date.now() }) {
  let index = null;
  let modele = null;
  let resume = null;
  let loading = false;

  const fail = (code, extra = {}) => post({ type: 'erreur', code, ...extra });

  async function telecharger(spec, base, onBytes) {
    const address = base ? new URL(spec.url, base).href : spec.url;
    let response;
    try {
      response = await fetchFile(address);
    } catch (cause) {
      throw new LoadError(spec.url, null, { cause });
    }
    if (!response.ok) throw new LoadError(spec.url, response.status);
    let text;
    try {
      text = await lireCorps(response, onBytes);
    } catch (cause) {
      throw new LoadError(spec.url, null, { cause });
    }
    try {
      return JSON.parse(text);
    } catch (cause) {
      if (cause instanceof SyntaxError) throw new FormatError(spec.url, { cause });
      throw cause;
    }
  }

  async function charger(message) {
    if (loading) return;
    if (index !== null) {
      post({ type: 'pret', resume });
      return;
    }
    loading = true;
    const base = typeof message.base === 'string' && message.base !== '' ? message.base : defaultBase;
    try {
      let recus = 0;
      let total = null;
      let last = 0;
      const report = (force) => {
        const now = maintenant();
        if (!force && now - last < 80) return; // the big file arrives in hundreds of blocks
        last = now;
        post({ type: 'progression', etape: 'telechargement', recus, total });
      };
      const count = (bytes) => {
        recus += bytes;
        report(false);
      };
      report(true);
      const data = {};
      const metas = FICHIERS.filter((f) => f.meta);
      const [anMeta, boggaMeta] = await Promise.all(metas.map((f) => telecharger(f, base, () => {})));
      data.anMeta = anMeta;
      data.boggaMeta = boggaMeta;
      const sizes = taillesAnnoncees(anMeta, boggaMeta);
      const big = FICHIERS.filter((f) => !f.meta);
      const known = big.map((f) => sizes.get(f.url.split('/').pop()));
      // A real total only when the two big files at least announce their size.
      total = known.filter((s) => s !== undefined).length >= 3 ? known.reduce((sum, s) => sum + (s ?? 0), 0) : null;
      report(true);
      const loaded = await Promise.all(big.map((f) => telecharger(f, base, count)));
      big.forEach((f, i) => {
        data[f.cle] = loaded[i];
      });
      if (total !== null && recus > total) total = recus;
      report(true);

      post({ type: 'progression', etape: 'lecture', recus, total });
      let all;
      try {
        const an = occurrencesFromColumns(data.anPersonnes, { groupe: 'an' });
        const bogga = occurrencesFromColumns(data.boggaEntrees, { groupe: 'bogga', ocr: true });
        all = sansAnneesDouteuses(an.occurrences, data.anPersonnes).concat(bogga.occurrences);
        modele = creerModele(data);
      } catch (cause) {
        if (cause instanceof DataFormatError || cause instanceof TypeError) throw new FormatError('data/', { cause });
        throw cause;
      }
      post({ type: 'progression', etape: 'index', recus, total });
      index = buildIndex(all, { groupesOcr: ['bogga'] });
      resume = {
        index: indexSummary(index),
        couverture: modele.couverture(),
        fichiers: FICHIERS.map((f) => f.url),
      };
      post({ type: 'pret', resume });
    } catch (error) {
      index = null;
      modele = null;
      if (error instanceof LoadError) fail('chargement', { fichier: error.fichier, statut: error.statut });
      else if (error instanceof FormatError) fail('format', { fichier: error.fichier });
      else fail('interne');
    } finally {
      loading = false;
    }
  }

  function chercher(message) {
    const etat = message.etat ?? {};
    const { entree, fidele } = preparerRequete(etat);
    const limite = Number.isInteger(message.limite) ? message.limite : 100;
    const { correspondances, bilan } = search(index, entree, { limite });
    const fiches = {};
    const light = correspondances.map((c) => {
      const ligne = c.occurrence.ligne;
      const cle = modele.cleDe(c.groupe, ligne);
      if (!(cle in fiches)) fiches[cle] = modele.fiche(cle);
      return {
        cle,
        ligne,
        groupe: c.groupe,
        nom: c.nom,
        classe: c.classe,
        termes: c.termes,
        termeAbsent: c.termeAbsent,
        anneeNaissance: c.anneeNaissance,
        annee: c.annee,
      };
    });
    // Related names (Mohamed / Mohand…): never applied by the engine, only offered.
    const apparentees = bilan.termes.map((t) => {
      const typed = t.variantes[0]?.saisie;
      if (typeof typed !== 'string' || typed === '') return [];
      const taken = new Set(t.variantes.map((v) => v.saisie.toLowerCase()));
      return suggestVariants(index, typed, { limite: 8 }).apparentees
        .filter((s) => !/\s/.test(s.graphie) && !taken.has(s.graphie.toLowerCase()))
        .map((s) => ({ graphie: s.graphie, occurrences: s.occurrences, raison: s.raison ?? null }));
    });
    post({ type: 'correspondances', id: message.id, correspondances: light, fiches, bilan, apparentees, fidele });
  }

  async function handle(message) {
    const type = message && typeof message === 'object' ? message.type : undefined;
    if (type === 'charger') {
      await charger(message);
      return;
    }
    if (type !== 'chercher' && type !== 'fiche' && type !== 'decrets-an') {
      fail('message-inconnu');
      return;
    }
    if (index === null || modele === null) {
      fail('non-charge', { id: message.id });
      return;
    }
    try {
      if (type === 'chercher') chercher(message);
      else if (type === 'fiche') post({ type: 'fiche', id: message.id, fiche: modele.ficheParReference(message.ref) });
      else post({ type: 'decrets-an', id: message.id, decrets: modele.decretsAn(message.filtre ?? {}) });
    } catch (error) {
      if (error instanceof RangeError || error instanceof TypeError) fail('interne', { id: message.id });
      else throw error;
    }
  }

  return { handle };
}
