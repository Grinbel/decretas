/**
 * External links. The interface never writes an external address by hand: it takes a template
 * from site/contenu/liens.json, fills its {variables} and shows its test status. This module is
 * the only place where a template becomes an address. Pure functions (no DOM).
 *
 * The data files name the inventory "{inv}"; liens.json names it "{inventaire}": pass either,
 * both are understood.
 */

import { typographier } from '../textes/typographie.js';

/** Variables copied as they are, after a strict check (liens.json: "se recopie tel quel"). */
const VERBATIM = {
  inventaire: /^FRAN_IR_\d{6}$/,
  notice: /^[A-Za-z0-9_.-]{1,200}$/,
  cb: /^cb[0-9a-z]{6,20}$/,
  ark: /^[0-9a-z]{6,40}$/,
  vue: /^\d{1,5}$/,
  annee: /^\d{4}$/,
  mois: /^\d{2}$/,
  jour: /^\d{2}$/,
  date: /^\d{8}$/,
  identifiant: /^[A-Za-z0-9_.-]{1,200}$/,
  feuillet: /^\d{1,5}$/,
  htid: /^[a-z0-9]{2,8}\.[A-Za-z0-9_.$-]{1,60}$/,
  seq: /^\d{1,5}$/,
};
/** Variables passed through encodeURIComponent (free text, or a volume name with spaces). */
const ENCODED = new Set(['mot', 'volume']);

const ALIASES = { inv: 'inventaire', leaf: 'feuillet', feuille: 'feuillet', item: 'identifiant' };

function normaliserParametres(params) {
  const out = {};
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === null || value === undefined || value === '') continue;
    out[ALIASES[key] ?? key] = String(value);
  }
  return out;
}

/** https only, and exactly the host the table announces. */
function adresseSure(url, hote) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch (error) {
    if (error instanceof TypeError) return null;
    throw error;
  }
  if (parsed.protocol !== 'https:' || parsed.hostname !== hote) return null;
  if (parsed.username !== '' || parsed.password !== '') return null;
  return parsed.href === url ? url : parsed.href;
}

/**
 * @typedef {Object} LienResolu
 * @property {string} id
 * @property {string} libelle     link text for the user
 * @property {string} hote        host name, shown next to the link
 * @property {string|null} url    null when a variable is missing or refused
 * @property {string[]} manquantes  variables that could not be filled
 * @property {string} statut      'teste-200' | 'bloque-pour-les-robots-attendu-ok-pour-un-humain' | 'non-teste'
 * @property {boolean} teste      true only for 'teste-200'
 * @property {string|null} note   honest sentence to show under a link that is not 'teste-200'
 * @property {string|null} repli  id of the fallback link
 * @property {boolean} proposer   false: never shown to the public
 */

/**
 * @param {Object} table  the parsed site/contenu/liens.json
 * @returns {{
 *   resoudre: (id: string, params?: Object) => LienResolu|null,
 *   particulier: (url: string) => LienResolu|null,
 *   hotes: Set<string>, connu: (id: string) => boolean }}
 */
export function creerLiens(table) {
  const byId = new Map();
  const hotes = new Set();
  for (const entry of Array.isArray(table?.liens) ? table.liens : []) {
    if (entry && typeof entry.id === 'string') {
      byId.set(entry.id, entry);
      if (typeof entry.hote === 'string') hotes.add(entry.hote);
    }
  }
  const statuts = table?.statuts ?? {};

  /** The sentence of the content files for a link never seen working. */
  function noteDe(entry) {
    if (entry.statut === 'teste-200') return null;
    if (typeof entry.avertissement === 'string' && entry.avertissement !== '') return entry.avertissement;
    const generic = typeof statuts[entry.statut] === 'string' ? statuts[entry.statut] : '';
    // The generic sentence ends with a pointer to fields the page does not show.
    // (\s also matches the no-break spaces that the typography puts inside « »)
    return generic.replace(/\s*Voir\s«\s*observation\s*»\s+et\s+«\s*origine\s*»\.\s*$/u, '') || null;
  }

  function resoudre(id, params) {
    const entry = byId.get(id);
    if (entry === undefined) return null;
    const given = normaliserParametres(params);
    const manquantes = [];
    let url = String(entry.gabarit ?? '').replace(/\{([a-z]+)\}/g, (whole, name) => {
      const value = given[name];
      if (value === undefined) {
        manquantes.push(name);
        return whole;
      }
      if (ENCODED.has(name)) return encodeURIComponent(value);
      const rule = VERBATIM[name];
      if (rule === undefined || !rule.test(value)) {
        manquantes.push(name);
        return whole;
      }
      return value;
    });
    url = manquantes.length > 0 ? null : adresseSure(url, entry.hote);
    return {
      id,
      libelle: typographier(entry.libelle ?? ''),
      hote: String(entry.hote ?? ''),
      url,
      manquantes,
      statut: String(entry.statut ?? 'non-teste'),
      teste: entry.statut === 'teste-200',
      note: noteDe(entry) === null ? null : typographier(noteDe(entry)),
      repli: typeof entry.repli === 'string' ? entry.repli : null,
      proposer: entry.proposer === true,
    };
  }

  /**
   * An address copied as it is from a source file ("liens_particuliers" of the data files):
   * accepted only on a host that the table already knows, and always shown as never tested.
   * The inventories write some of them in http; the table reaches every one of its hosts in
   * https, so such an address is given in https too (same host, same path).
   */
  function particulier(url) {
    if (typeof url !== 'string') return null;
    let parsed;
    try {
      parsed = new URL(url);
    } catch (error) {
      if (error instanceof TypeError) return null;
      throw error;
    }
    if ((parsed.protocol !== 'https:' && parsed.protocol !== 'http:') || !hotes.has(parsed.hostname)) return null;
    if (parsed.username !== '' || parsed.password !== '') return null;
    if (parsed.protocol === 'http:') {
      parsed.protocol = 'https:';
      if (parsed.port === '80') parsed.port = '';
    }
    return {
      id: 'particulier',
      libelle: '',
      hote: parsed.hostname,
      url: parsed.href,
      manquantes: [],
      statut: 'non-teste',
      teste: false,
      note: null,
      repli: null,
      proposer: true,
    };
  }

  return { resoudre, particulier, hotes, connu: (id) => byId.has(id) };
}

/**
 * The reader link of one leaf of a Bulletin volume, from the liens.json templates. A volume
 * item holds one volume ("ia-page") or several ("ia-page-volume"); the data file says which
 * by the address it carries ("lien_page"), so the template that reproduces that address is
 * the one used. When neither does, nothing is invented: the result has no address.
 *
 * @param {ReturnType<typeof creerLiens>} liens
 * @param {{item: string, doc: string, lienPage: string}} volume
 * @param {number} feuille
 * @returns {LienResolu|null}
 */
export function lienPageBulletin(liens, volume, feuille) {
  if (!volume || !Number.isInteger(feuille)) return null;
  const attendu = typeof volume.lienPage === 'string' ? volume.lienPage.replace('{leaf}', String(feuille)) : null;
  const simple = liens.resoudre('ia-page', { identifiant: volume.item, feuillet: feuille });
  const multiple = liens.resoudre('ia-page-volume', { identifiant: volume.item, volume: volume.doc, feuillet: feuille });
  for (const candidate of [simple, multiple]) {
    if (candidate !== null && candidate.url !== null && (attendu === null || candidate.url === attendu)) return candidate;
  }
  const fallback = simple ?? multiple;
  return fallback === null ? null : { ...fallback, url: null, manquantes: ['feuillet'] };
}

/**
 * Address of the IMAGE of one leaf, from the template carried by the data file
 * (bogga-volumes.json "image_page"). Only an https://archive.org/ address is accepted.
 * The page loads it after an explicit click only.
 */
export function imagePageBulletin(volume, feuille, largeur = 1000) {
  if (!volume || typeof volume.imagePage !== 'string' || !Number.isInteger(feuille)) return null;
  const url = volume.imagePage.replace('{leaf}', String(feuille)).replace('{largeur}', String(largeur));
  return adresseSure(url, 'archive.org');
}
