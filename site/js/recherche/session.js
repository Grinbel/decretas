/**
 * Message protocol of the search worker, kept free of any Worker global so that it runs in a
 * Web Worker (worker.js) and in Node tests alike. Nothing here touches the network except the
 * "fetch" function it is given, used only to download the site's own data files.
 *
 * Messages IN (to the worker)                      Messages OUT
 * ------------------------------------------------------------------------------------------
 * { type: 'charger',                               { type: 'progression', fichier, etape, recus, total, numero, sur }
 *   base?: string,                                    fichier: the "url" as given in the message
 *   fichiers: [ { url, groupe,                        etape: 'telechargement' | 'lecture' | 'index'
 *                 champNom?, champId?,                telechargement: recus/total in bytes; total is null when
 *                                                     unknown (no length announced, or compressed transfer)
 *                 champAnnee?, ocr? } ],           { type: 'pret', index: {occurrences, formes, parGroupe, …},
 *   groupesOcr?: string[] }                           fichiers: [ {url, groupe, lignes, occurrences, sansNom, colonnes} ] }
 *
 * { type: 'chercher', id,                          { type: 'correspondances', id, correspondances, bilan }
 *   requete: string | {texte?, termes?, annee?,       (see chercher.js#search)
 *                      tolerance?, limite?},
 *   options?: {limite?, partielles?} }
 *
 * { type: 'suggerer', id, terme, limite? }         { type: 'suggestions', id, suggestions }   (suggestions.js)
 *
 * { type: 'etat' }                                 { type: 'etat', charge: boolean, enCours: boolean,
 *                                                    index: {...}|null, fichiers: [...] }
 *
 * "url" may be relative: it is resolved against "base" when the message gives one, else against
 * the site root (worker.js; in a worker the browser would otherwise resolve it against the
 * worker script). "fichier" and "fichiers[].url" in the replies repeat the url as given.
 *
 * Any failure:                                     { type: 'erreur', id?, code, message }
 *   codes: 'message-inconnu', 'chargement', 'format', 'non-charge', 'interne'
 *   "message" is a French sentence that can be shown as is; it never contains a stack trace.
 *
 * A search never leaves the device: "chercher" and "suggerer" only read the in-memory index.
 */

import { buildIndex, occurrencesFromColumns, indexSummary, DataFormatError } from './index.js';
import { search } from './chercher.js';
import { suggestVariants } from './suggestions.js';

/** Thrown when a data file cannot be downloaded. */
export class LoadError extends Error {
  constructor(message, options) {
    super(message, options);
    this.name = 'LoadError';
  }
}

/**
 * Read a response as text, reporting progress in bytes.
 * The announced length is only usable when the transfer is not compressed: with
 * "Content-Encoding: gzip" the header counts compressed bytes while the stream yields the
 * decompressed ones, and "received" would overtake "total". The total is then unknown (null).
 */
async function readBody(response, onProgress) {
  const header = response.headers?.get?.('content-length');
  const encoding = response.headers?.get?.('content-encoding');
  const compressed = typeof encoding === 'string' && encoding !== '' && encoding.toLowerCase() !== 'identity';
  const announced = header && !compressed ? Number(header) : NaN;
  const total = Number.isFinite(announced) && announced > 0 ? announced : null;
  if (!response.body || typeof response.body.getReader !== 'function') {
    // No stream to follow: one event, counted in bytes like the others.
    const text = await response.text();
    onProgress(new TextEncoder().encode(text).length, null);
    return text;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let received = 0;
  let text = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    received += value.byteLength;
    text += decoder.decode(value, { stream: true });
    onProgress(received, total);
  }
  return text + decoder.decode();
}

/**
 * Absolute address of a data file. A relative "url" is resolved against the base of the
 * "charger" message, else against the base of the session (worker.js gives the site root);
 * without any base it is passed to fetch as it is.
 * @param {string} url
 * @param {string|null|undefined} base
 * @returns {string}
 * @throws {LoadError} when the address cannot be read
 */
export function resolveUrl(url, base) {
  if (typeof url !== 'string' || url === '') throw new LoadError('Un fichier de données est indiqué sans adresse.');
  if (typeof base !== 'string' || base === '') return url;
  try {
    return new URL(url, base).href;
  } catch (cause) {
    if (cause instanceof TypeError) throw new LoadError(`L'adresse du fichier ${url} n'est pas lisible.`, { cause });
    throw cause;
  }
}

/**
 * @param {{post: (message: Object) => void, fetch: (url: string) => Promise<Response>, base?: string|null}} env
 *        base: address against which relative data URLs are resolved (see resolveUrl)
 * @returns {{handle: (message: Object) => Promise<void>}}
 */
export function createSession({ post, fetch: fetchFile, base: sessionBase = null }) {
  let index = null;
  let files = [];
  let loading = false;

  const fail = (code, message, id) => post(id === undefined ? { type: 'erreur', code, message } : { type: 'erreur', id, code, message });

  async function load(message) {
    const list = Array.isArray(message.fichiers) ? message.fichiers : [];
    if (list.length === 0) {
      fail('chargement', 'Aucun fichier de données à charger.');
      return;
    }
    loading = true;
    try {
      const all = [];
      const loaded = [];
      const base = typeof message.base === 'string' && message.base !== '' ? message.base : sessionBase;
      for (let k = 0; k < list.length; k++) {
        const spec = list[k] ?? {};
        const address = resolveUrl(spec.url, base);
        const where = { fichier: spec.url, numero: k + 1, sur: list.length };
        post({ type: 'progression', ...where, etape: 'telechargement', recus: 0, total: null });
        let response;
        try {
          response = await fetchFile(address);
        } catch (cause) {
          throw new LoadError(`Le fichier ${spec.url} n'a pas pu être téléchargé (pas de réponse).`, { cause });
        }
        if (!response.ok) throw new LoadError(`Le fichier ${spec.url} n'a pas pu être téléchargé (réponse ${response.status}).`);
        const text = await readBody(response, (recus, total) => post({ type: 'progression', ...where, etape: 'telechargement', recus, total }));
        post({ type: 'progression', ...where, etape: 'lecture', recus: text.length, total: text.length }); // characters
        let data;
        try {
          data = JSON.parse(text);
        } catch (cause) {
          if (cause instanceof SyntaxError) throw new DataFormatError(`Le fichier ${spec.url} n'est pas du JSON lisible.`);
          throw cause;
        }
        const adapted = occurrencesFromColumns(data, spec);
        for (const o of adapted.occurrences) all.push(o);
        loaded.push({ url: spec.url, groupe: spec.groupe, lignes: adapted.lignes, occurrences: adapted.occurrences.length, sansNom: adapted.sansNom, colonnes: adapted.colonnes });
      }
      post({ type: 'progression', fichier: null, numero: list.length, sur: list.length, etape: 'index', recus: all.length, total: all.length });
      const ocrGroups = new Set(Array.isArray(message.groupesOcr) ? message.groupesOcr : []);
      for (const spec of list) if (spec.ocr === true) ocrGroups.add(spec.groupe);
      index = buildIndex(all, { groupesOcr: [...ocrGroups] });
      files = loaded;
      post({ type: 'pret', index: indexSummary(index), fichiers: files });
    } catch (error) {
      if (error instanceof DataFormatError) fail('format', error.message);
      else if (error instanceof LoadError) fail('chargement', error.message);
      else fail('interne', "Le chargement des données a échoué pour une raison inattendue.");
    } finally {
      loading = false;
    }
  }

  async function handle(message) {
    const type = message && typeof message === 'object' ? message.type : undefined;
    if (type === 'charger') {
      await load(message);
    } else if (type === 'etat') {
      post({ type: 'etat', charge: index !== null, enCours: loading, index: index ? indexSummary(index) : null, fichiers: files });
    } else if (type === 'chercher' || type === 'suggerer') {
      if (index === null) {
        fail('non-charge', "Les données ne sont pas encore chargées.", message.id);
        return;
      }
      try {
        if (type === 'chercher') {
          const { correspondances, bilan } = search(index, message.requete, message.options ?? {});
          post({ type: 'correspondances', id: message.id, correspondances, bilan });
        } else {
          post({ type: 'suggestions', id: message.id, suggestions: suggestVariants(index, message.terme, { limite: message.limite }) });
        }
      } catch (error) {
        if (error instanceof RangeError || error instanceof TypeError) {
          fail('interne', "La recherche a échoué pour une raison inattendue.", message.id);
        } else {
          throw error;
        }
      }
    } else {
      fail('message-inconnu', `Message non reconnu : ${String(type)}.`);
    }
  }

  return { handle };
}
