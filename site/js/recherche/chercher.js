/**
 * Query model and matching.
 *
 * A query is a list of TERMS (one element of the ancestor's name each). A term has one or
 * more VARIANTS (spellings typed by the user). Rule, from CONTEXT.md: an occurrence is a
 * correspondence when at least one variant of EVERY term is found in it, in any order, each
 * term on a different written word. Particles are never required.
 *
 * Result classes — there is no similarity score, every result says why it is there:
 *   "correspondance"       every term found at k0 or k1 (same spelling up to case, accents,
 *                          spacing, fused article "El Arbi" = "Larbi", and safe writing equivalences)
 *   "graphie-approchante"  every term found, at least one only approximately: consonant
 *                          skeleton (k2), a detached prefix (Zemri / Ezzemri), or Arabic input
 *   "partielle"            exactly one term missing (named), the others found at k0/k1;
 *                          only for queries of two terms or more
 * Nothing looser is ever returned.
 *
 * Order, in words: class; then distance to the birth year asked (unknown years last);
 * then number of terms written exactly as typed; then, for Arabic input, number of terms
 * whose long vowels agree; then the order of the sources.
 *
 * Free-text syntax:  Belkacem ben Chabane Testaoui     three terms, "ben" ignored
 *                    Belkacem|Belgacem Chabane         variants of one term
 *                    Belkacem|-Belkassem               "-" removes a spelling found in the index
 *                    "Hadj" Ali                        quotes force a word, even a particle
 *                    بلقاسم بن شعبان                    Arabic script (always approximate)
 */

import {
  tokenize, keysOf, detachedStems, canonicalParticle, isAttachable, isTitle, nameForms, fusedArticleForm,
  KIND, K2_MIN_LETTERS, K2_MIN_KEY, particleList,
} from './normaliser.js';
import { hasArabic, arabicWords, arabicParticle, arabicCandidates, longVowelsAgree } from './arabe.js';
import { MAX_WORDS, FUSED_BIT, STEM_SOURCES_MAX, displayForm, indexSummary } from './index.js';

export const CLASSES = Object.freeze(['correspondance', 'graphie-approchante', 'partielle']);
export const DEFAULT_TOLERANCE = 5;
export const DEFAULT_LIMIT = 100;
export const MAX_TERMS = 12;
const LEVELS = ['k0', 'k1', 'k2'];
const COST_PREFIX = 100;
const COST_K2 = 200;

// ---------------------------------------------------------------------------------------------
// Query parsing
// ---------------------------------------------------------------------------------------------

function latinForms(token, run) {
  const forms = [{ ...keysOf(token.cle), genre: 'entier', prefixe: null }];
  let glue = '';
  for (let j = run.length - 1, depth = 0; j >= 0 && depth < 2; j--, depth++) {
    if (!isAttachable(run[j])) break;
    if (depth === 1 && isTitle(run[j])) break;
    glue = run[j] + glue;
    forms.push({ ...keysOf(glue + token.cle), genre: 'colle', prefixe: glue });
    // "El Arbi" typed in two words is also looked for as "Larbi" (article fused).
    const fused = depth === 0 ? fusedArticleForm(run[j], token.cle) : null;
    if (fused !== null) forms.push({ ...keysOf(fused), genre: 'colle', prefixe: run[j], fondu: true });
  }
  for (const s of detachedStems(token.cle)) forms.push({ ...keysOf(s.stem), genre: 'decolle', prefixe: s.prefix });
  if (token.elided) forms.push({ ...keysOf(token.elided), genre: 'decolle', prefixe: token.k0[0] });
  return forms;
}

function newQuery(saisie) {
  return { saisie, termes: [], particulesIgnorees: [], avertissements: [], annee: null, tolerance: DEFAULT_TOLERANCE };
}

function warn(q, code, detail) {
  if (!q.avertissements.some((a) => a.code === code && a.detail === detail)) q.avertissements.push({ code, detail });
}

function pushParticle(q, state, saisie, particule) {
  q.particulesIgnorees.push({ saisie, particule });
  const prev = state.run[state.run.length - 1];
  if (isTitle(particule) && prev !== undefined && isAttachable(prev) && !isTitle(prev)) {
    // "Bel Hadj" typed in two words is read as two particles; glued, it is a family name.
    warn(q, 'compose-de-particules', prev + particule);
  }
  state.run.push(particule);
}

function pushTerm(q, state, term) {
  state.run = [];
  if (q.termes.length >= MAX_TERMS) {
    warn(q, 'trop-de-termes', term.libelle);
    return;
  }
  q.termes.push(term);
}

function walkLatin(q, state, text) {
  for (const tok of tokenize(text)) {
    const p = canonicalParticle(tok.k0);
    if (p !== null) {
      pushParticle(q, state, tok.raw, p);
    } else if (tok.k0.length < 2) {
      warn(q, 'initiale-ignoree', tok.raw);
    } else {
      pushTerm(q, state, {
        libelle: tok.raw,
        exige: false,
        exclues: [],
        variantes: [{ saisie: tok.raw, ecriture: 'latin', formes: latinForms(tok, state.run) }],
      });
    }
  }
}

function walkArabic(q, state, text) {
  for (const word of arabicWords(text)) {
    const p = arabicParticle(word);
    if (p !== null) {
      pushParticle(q, state, word, p);
      continue;
    }
    const candidats = arabicCandidates(word, state.run);
    if (candidats.length === 0) continue;
    pushTerm(q, state, { libelle: word, exige: false, exclues: [], variantes: [{ saisie: word, ecriture: 'arabe', candidats }] });
  }
}

function walkText(q, state, text) {
  // Split a mixed text into runs of one script.
  const parts = String(text).split(/([\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF][\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF\s\u2060]*)/);
  for (const part of parts) {
    if (part === '') continue;
    if (hasArabic(part)) walkArabic(q, state, part);
    else walkLatin(q, state, part);
  }
}

function explicitTerm(q, state, variants, { exige = false, exclues = [] } = {}) {
  const term = { libelle: '', exige, exclues: [], variantes: [] };
  for (const x of exclues) {
    const t = tokenize(String(x));
    if (t.length > 0) term.exclues.push(t.map((k) => k.k0).join(''));
  }
  for (const raw of variants) {
    const saisie = String(raw).trim();
    if (saisie === '') continue;
    if (saisie.startsWith('-')) {
      const t = tokenize(saisie.slice(1));
      if (t.length > 0) term.exclues.push(t.map((k) => k.k0).join(''));
      continue;
    }
    if (hasArabic(saisie)) {
      const words = arabicWords(saisie);
      const names = words.filter((w) => arabicParticle(w) === null);
      if (names.length === 0) {
        warn(q, 'variante-sans-nom', saisie);
        continue;
      }
      if (names.length > 1) warn(q, 'variante-plusieurs-mots', saisie);
      const name = names[names.length - 1];
      const inner = words.slice(0, words.lastIndexOf(name)).map((w) => arabicParticle(w)).filter((p) => p !== null);
      const candidats = arabicCandidates(name, inner.length > 0 ? inner : state.run);
      if (candidats.length > 0) term.variantes.push({ saisie, ecriture: 'arabe', candidats });
      continue;
    }
    const tokens = tokenize(saisie);
    if (tokens.length === 0) continue;
    if (exige) {
      // A forced word is taken literally: no particle filtering, no prefix detaching.
      const cle = tokens.map((t) => t.cle).join('');
      term.variantes.push({ saisie, ecriture: 'latin', formes: [{ ...keysOf(cle), genre: 'entier', prefixe: null }] });
      continue;
    }
    const names = tokens.filter((t) => canonicalParticle(t.k0) === null && t.k0.length > 1);
    if (names.length === 0) {
      warn(q, 'variante-sans-nom', saisie);
      continue;
    }
    if (names.length > 1) {
      // Several name words in one variant: only their glued form can be one term.
      warn(q, 'variante-plusieurs-mots', saisie);
      const cle = tokens.map((t) => t.cle).join('');
      term.variantes.push({ saisie, ecriture: 'latin', formes: [{ ...keysOf(cle), genre: 'entier', prefixe: null }] });
      continue;
    }
    const at = tokens.indexOf(names[0]);
    const inner = tokens.slice(0, at).map((t) => canonicalParticle(t.k0)).filter((p) => p !== null);
    term.variantes.push({ saisie, ecriture: 'latin', formes: latinForms(names[0], inner.length > 0 ? inner : state.run) });
  }
  if (term.variantes.length === 0) return;
  term.libelle = term.variantes[0].saisie;
  pushTerm(q, state, term);
}

// "نور الدين" is one name (Noureddine): a word joiner keeps the two words in one token, and
// arabe.js#arabicWords reads them as one compound.
const DINE_JOIN_RE = /([\u0621-\u064A])\s+(\u0627\u0644\u062F\u064A\u0646)(?![\u0621-\u064A])/g;

function parseText(q, state, text) {
  const src = String(text).replace(/\s*\|\s*/g, '|').replace(DINE_JOIN_RE, '$1\u2060$2');
  const re = /"([^"]*)"|«\s*([^»]*?)\s*»|([^\s,;()[\]"«»]+)/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    const quoted = m[1] ?? m[2];
    if (quoted !== undefined) {
      explicitTerm(q, state, quoted.split('|'), { exige: true });
    } else if (m[3].includes('|')) {
      explicitTerm(q, state, m[3].split('|'));
    } else if (/^\d+$/.test(m[3])) {
      warn(q, 'nombre-ignore', m[3]);
    } else {
      walkText(q, state, m[3]);
    }
  }
}

/**
 * @typedef {Object} Query
 * @property {string} saisie
 * @property {Object[]} termes               {libelle, exige, exclues: string[], variantes: [...]}
 * @property {{saisie: string, particule: string}[]} particulesIgnorees
 * @property {{code: string, detail: string}[]} avertissements
 * @property {number|null} annee
 * @property {number} tolerance
 */

/**
 * Understand a query.
 * @param {string|Object} input free text, or
 *   { texte?: string,
 *     termes?: Array<string | {variantes: string[], exclues?: string[], exige?: boolean}>,
 *     annee?: number|string|null, tolerance?: number }
 *   A string in "termes" is read like free text; an object is ONE term whose variants may be
 *   written in several words ("Bel Hadi", "Abd el Kader").
 * @returns {Query}
 */
export function parseQuery(input) {
  const src = typeof input === 'string' ? { texte: input } : (input ?? {});
  const q = newQuery(typeof src.texte === 'string' ? src.texte : '');
  const state = { run: [] };
  if (typeof src.texte === 'string') parseText(q, state, src.texte);
  if (Array.isArray(src.termes)) {
    for (const t of src.termes) {
      state.run = [];
      if (typeof t === 'string') parseText(q, state, t);
      else if (t && Array.isArray(t.variantes)) explicitTerm(q, state, t.variantes, { exige: t.exige === true, exclues: Array.isArray(t.exclues) ? t.exclues : [] });
    }
    if (q.saisie === '') {
      q.saisie = src.termes
        .map((t) => (typeof t === 'string' ? t : (Array.isArray(t?.variantes) ? t.variantes.join('|') : '')))
        .filter((t) => t !== '')
        .join(' ');
    }
  }
  if (src.annee !== undefined && src.annee !== null && src.annee !== '') {
    const y = Number(src.annee);
    if (Number.isInteger(y) && y >= 1000 && y <= 2100) q.annee = y;
    else warn(q, 'annee-illisible', String(src.annee));
  }
  if (src.tolerance !== undefined && src.tolerance !== null && src.tolerance !== '') {
    const tol = Number(src.tolerance);
    if (Number.isInteger(tol) && tol >= 0 && tol <= 100) q.tolerance = tol;
    else warn(q, 'tolerance-illisible', String(src.tolerance));
  }
  if (q.termes.length === 0) warn(q, 'aucun-terme', '');
  return q;
}

// ---------------------------------------------------------------------------------------------
// Matching
// ---------------------------------------------------------------------------------------------

function popcount(x) {
  let c = 0;
  for (let v = x; v !== 0; v &= v - 1) c++;
  return c;
}

/**
 * For one term, every (index form, kind) that satisfies it, with the best way it does.
 * @returns {Map<number, Object>} key = formId * 3 + kind
 */
function termOptions(index, term, t) {
  const best = new Map();
  const excluded = new Set(term.exclues);
  const consider = (fid, kind, opt) => {
    const key = fid * 3 + kind;
    if (index.postings[key] === undefined) return;
    const prev = best.get(key);
    if (prev === undefined || opt.cost < prev.cost) best.set(key, opt);
  };
  const usable = (fid) => !(index.formParticle[fid] && !term.exige);
  // A spelling unticked by the user is refused as a written word and as a glued form. Its
  // use as the stem of ANOTHER written word ("chabane" inside Benchabane) is a different line
  // of the bilan, unticked by the carrier word (see collect).
  const unticked = (fid) => excluded.has(index.formK0[fid]);

  term.variantes.forEach((v, vi) => {
    if (v.ecriture === 'arabe') {
      v.candidats.forEach((cand, ci) => {
        for (const fid of index.byK2.get(cand.key) ?? []) {
          if (!usable(fid)) continue;
          const off = unticked(fid);
          const accord = longVowelsAgree(cand, index.formCle[fid]);
          const base = { t, vi, fi: ci, niveau: 2, arabe: true, accord, strict: false, exact: false };
          const cost = COST_K2 + (accord === false ? 2 : accord === null ? 1 : 0);
          if (cand.genre === 'entier') {
            if (!off) consider(fid, KIND.WORD, { ...base, soudure: null, cost });
            if (!off) consider(fid, KIND.GLUED, { ...base, soudure: 'colle', cost: cost + 0.25 });
            consider(fid, KIND.STEM, { ...base, soudure: 'prefixe-source', cost: cost + COST_PREFIX });
          } else if (!off) {
            consider(fid, KIND.WORD, { ...base, soudure: 'colle', cost: cost + 0.25 });
          }
        }
      });
      return;
    }
    v.formes.forEach((f, fi) => {
      const seen = new Set();
      for (let level = 0; level < 3; level++) {
        let fids;
        if (level === 0) fids = index.byK0.get(f.k0);
        else if (level === 1) fids = index.byK1.get(f.k1);
        else if (f.k2ok && f.genre !== 'decolle' && !term.exige && (f.genre !== 'colle' || v.formes[0].k2ok)) {
          fids = index.byK2.get(f.k2); // a glued form is approximate only if its own word may be
        }
        if (fids === undefined) continue;
        for (const fid of fids) {
          if (seen.has(fid)) continue;
          seen.add(fid);
          if (!usable(fid)) continue;
          if (level === 2 && !index.formK2ok[fid]) continue;
          const off = unticked(fid);
          const base = { t, vi, fi, niveau: level, arabe: false, accord: null };
          const lc = level === 2 ? COST_K2 : level;
          if (f.genre === 'entier') {
            if (!off) consider(fid, KIND.WORD, { ...base, soudure: null, cost: lc, strict: level < 2, exact: level === 0 });
            if (!off && (level < 2 || index.formGluedApprox[fid])) {
              consider(fid, KIND.GLUED, { ...base, soudure: 'colle', cost: lc + 0.25, strict: level < 2, exact: level === 0 });
            }
            if (level < 2 && !term.exige) {
              consider(fid, KIND.STEM, { ...base, soudure: 'prefixe-source', cost: lc + COST_PREFIX, strict: false, exact: false });
            }
          } else if (off) {
            // an unticked spelling is not looked for as a written word
          } else if (f.genre === 'colle') {
            const fondu = f.fondu === true;
            consider(fid, KIND.WORD, {
              ...base, soudure: fondu ? 'article-fondu' : 'colle', cost: lc + (fondu ? 0.5 : 0.25), strict: level < 2, exact: level === 0 && !fondu,
            });
          } else if (level < 2) {
            consider(fid, KIND.WORD, { ...base, soudure: 'prefixe-saisie', cost: lc + COST_PREFIX, strict: false, exact: false });
          }
        }
      }
    });
  });
  return best;
}

/**
 * Best assignment of terms to distinct written words of one occurrence: the cheapest one that
 * leaves exactly "maxSkip" terms out (0 for a correspondence, 1 for a partial one). Among equal
 * costs the first found wins, and options are tried in the order of the written name, so the
 * choice is deterministic.
 * @returns {Array|null} flat [option, entry, option, entry, …] per term; option null = term left out
 */
function assign(ctx, strictOnly, maxSkip) {
  ctx.strictOnly = strictOnly;
  ctx.maxSkip = maxSkip;
  ctx.bestCost = Infinity;
  ctx.best = null;
  assignFrom(ctx, 0, 0, 0);
  return ctx.best;
}

function assignFrom(ctx, t, cost, skipped) {
  if (cost >= ctx.bestCost) return;
  const n = ctx.n;
  if (t === n) {
    if (skipped !== ctx.maxSkip) return;
    ctx.bestCost = cost;
    const best = new Array(2 * n);
    for (let i = 0; i < n; i++) {
      best[2 * i] = ctx.chosenO[i];
      best[2 * i + 1] = ctx.chosenE[i];
    }
    ctx.best = best;
    return;
  }
  const os = ctx.optO[t];
  const es = ctx.optE[t];
  const entMeta = ctx.entMeta;
  for (let k = 0; k < os.length; k++) {
    const o = os[k];
    if (ctx.strictOnly && !o.strict) continue;
    const pos = entMeta[es[k]] & 255;
    let taken = false;
    for (let u = 0; u < t; u++) if (ctx.usedPos[u] === pos) taken = true;
    if (taken) continue;
    ctx.usedPos[t] = pos;
    ctx.chosenO[t] = o;
    ctx.chosenE[t] = es[k];
    assignFrom(ctx, t + 1, cost + o.cost, skipped);
  }
  if (skipped < ctx.maxSkip) {
    ctx.usedPos[t] = -1;
    ctx.chosenO[t] = null;
    ctx.chosenE[t] = -1;
    assignFrom(ctx, t + 1, cost, skipped + 1);
  }
}

/**
 * Find and classify every occurrence that satisfies the query; fills the counts.
 * Step 1, per term: the index forms that satisfy it (termOptions) and, through their posting
 * lists, one bit per term on each occurrence. Step 2, per occurrence with enough bits: the
 * assignment of terms to written words, hence the class.
 */
function collect(index, q, withPartial, comptes, applied) {
  const terms = q.termes;
  const n = terms.length;
  const records = [];
  const all = index.scratchAll;
  const strictMask = index.scratchStrict;
  if (index.scratchSlot === undefined) index.scratchSlot = new Int32Array(index.formCount * 3);
  const slot = index.scratchSlot; // (form, kind) -> 1 + position of its option list
  const lists = [];
  const usedKeys = [];
  const touched = [];
  for (let t = 0; t < n; t++) {
    const best = termOptions(index, terms[t], t);
    applied.push(best);
    const bit = 1 << t;
    for (const [key, opt] of best) {
      if (slot[key] === 0) {
        lists.push([]);
        slot[key] = lists.length;
        usedKeys.push(key);
      }
      lists[slot[key] - 1].push(opt);
      const posting = index.postings[key];
      for (let k = 0; k < posting.length; k++) {
        const occ = posting[k];
        if (all[occ] === 0) touched.push(occ);
        all[occ] |= bit;
        if (opt.strict) strictMask[occ] |= bit;
      }
    }
  }

  const fullMask = (1 << n) - 1;
  const { occStart, entForm, entMeta, years, groupOf } = index;
  const ctx = {
    n, entMeta, optO: [], optE: [], usedPos: new Array(n).fill(-1), chosenO: new Array(n).fill(null), chosenE: new Array(n).fill(-1),
    strictOnly: false, maxSkip: 0, bestCost: Infinity, best: null,
  };
  for (let t = 0; t < n; t++) {
    ctx.optO.push([]);
    ctx.optE.push([]);
  }
  const anyExcluded = terms.some((term) => term.exclues.length > 0);

  for (let k = 0; k < touched.length; k++) {
    const occ = touched[k];
    const maskAll = all[occ];
    const maskStrict = strictMask[occ];
    all[occ] = 0;
    strictMask[occ] = 0;
    const full = maskAll === fullMask;
    const partialPossible = withPartial && n >= 2 && popcount(maskStrict) >= n - 1;
    if (!full && !partialPossible) continue;

    for (let t = 0; t < n; t++) {
      ctx.optO[t].length = 0;
      ctx.optE[t].length = 0;
    }
    for (let e = occStart[occ]; e < occStart[occ + 1]; e++) {
      const meta = entMeta[e];
      const kind = (meta >> 10) & 3;
      const at = slot[entForm[e] * 3 + kind];
      if (at === 0) continue;
      const opts = lists[at - 1];
      for (let j = 0; j < opts.length; j++) {
        const o = opts[j];
        if (kind === KIND.GLUED && o.niveau === 2 && !o.arabe && (meta & 0x1000) === 0) continue;
        ctx.optO[o.t].push(o);
        ctx.optE[o.t].push(e);
      }
    }
    if (anyExcluded) {
      // A spelling unticked by the user is also refused when reached through its stem
      // ("Benchabane" unticked: its stem "chabane" no longer counts). Only stems are checked
      // here: a word or a glued form is refused by its own spelling in termOptions, and
      // unticking the bare word "Kacem" must not remove "Bel Kacem" written in two words.
      const tokens = tokenize(index.occurrences[occ].nom, { ocr: occurrenceOcr(index, occ) });
      for (let t = 0; t < n; t++) {
        const excl = terms[t].exclues;
        if (excl.length === 0) continue;
        const os = [];
        const es = [];
        for (let j = 0; j < ctx.optO[t].length; j++) {
          const meta = entMeta[ctx.optE[t][j]];
          const tok = ((meta >> 10) & 3) === KIND.STEM ? tokens[meta & 255] : undefined;
          if (tok && excl.includes(tok.k0)) continue;
          os.push(ctx.optO[t][j]);
          es.push(ctx.optE[t][j]);
        }
        ctx.optO[t] = os;
        ctx.optE[t] = es;
      }
    }

    let cls = -1;
    let chosen = full ? assign(ctx, false, 0) : null;
    if (chosen !== null) {
      cls = 0;
      for (let t = 0; t < n; t++) if (!chosen[2 * t].strict) cls = 1;
    } else if (partialPossible) {
      chosen = assign(ctx, true, 1);
      if (chosen !== null) cls = 2;
    }
    if (cls < 0) continue;

    const y = years[occ];
    let ecart = null;
    if (q.annee !== null && y !== 0) {
      ecart = y - q.annee;
      if (Math.abs(ecart) > q.tolerance) {
        comptes.ecarteesParAnnee[CLASSES[cls]]++;
        continue;
      }
    }
    let exact = 0;
    let agree = 0;
    let missing = -1;
    for (let t = 0; t < n; t++) {
      const o = chosen[2 * t];
      if (o === null) missing = t;
      else {
        // An article fused by us ("El Arbi" read as "Larbi") is not "written exactly as typed".
        if (o.exact && (entMeta[chosen[2 * t + 1]] & FUSED_BIT) === 0) exact++;
        if (o.accord === true) agree++;
      }
    }
    const cname = CLASSES[cls];
    comptes.parClasse[cname]++;
    comptes.parGroupe[index.groups[groupOf[occ]]][cname]++;
    comptes.total++;
    if (q.annee !== null && y === 0) comptes.sansAnneeDeNaissance++;
    records.push({ occ, cls, yearKey: q.annee === null ? 0 : (y === 0 ? q.tolerance + 1 : Math.abs(ecart)), exact, agree, missing, chosen, ecart });
  }
  for (let k = 0; k < usedKeys.length; k++) slot[usedKeys[k]] = 0;
  return records;
}

function describeTerm(term) {
  return {
    saisie: term.libelle,
    exige: term.exige,
    graphiesExclues: term.exclues.slice(),
    variantes: term.variantes.map((v) => (v.ecriture === 'arabe'
      ? { saisie: v.saisie, ecriture: 'arabe', squelettes: v.candidats.map((c) => ({ cle: c.key, lecture: c.lecture })) }
      : {
        saisie: v.saisie,
        ecriture: 'latin',
        formes: v.formes.map((f) => ({
          forme: f.k0, genre: f.genre, prefixe: f.prefixe, k0: f.k0, k1: f.k1, k2: f.k2ok && f.genre !== 'decolle' ? f.k2 : null,
        })),
      })),
  };
}

function emptyCounts() {
  return { correspondance: 0, 'graphie-approchante': 0, partielle: 0 };
}

/**
 * Search the index.
 *
 * @param {import('./index.js').NameIndex} index
 * @param {string|Object} input see parseQuery; an object may also carry "limite"
 * @param {{limite?: number, partielles?: boolean}} [options]
 *        limite: results returned PER CLASS (default 100; counts are always complete)
 *        partielles: false to skip partial correspondences
 * @returns {{correspondances: Object[], bilan: Object}}
 *
 * A result:
 *   { id, nom, groupe, anneeNaissance, occurrence,          // "occurrence": the object given at build
 *     classe: 'correspondance' | 'graphie-approchante' | 'partielle',
 *     termes: [ { terme, variante, niveau: 'k0'|'k1'|'k2',
 *                 soudure: null|'colle'|'article-fondu'|'prefixe-source'|'prefixe-saisie',
 *                 prefixe, ecrit, position, exact, arabe, lecture, voyellesLongues }
 *             | { terme, absent: true } ],
 *     termeAbsent: string|null, termesExacts: number,
 *     annee: { ecart: number|null, inconnue: boolean } | null }
 */
export function search(index, input, options = {}) {
  const started = performance.now();
  const q = parseQuery(input);
  const limite = Number.isInteger(options.limite) ? options.limite
    : (input && typeof input === 'object' && Number.isInteger(input.limite) ? input.limite : DEFAULT_LIMIT);
  const withPartial = options.partielles !== false;
  const n = q.termes.length;
  const terms = q.termes;

  const comptes = {
    parClasse: emptyCounts(),
    parGroupe: {},
    ecarteesParAnnee: emptyCounts(),
    sansAnneeDeNaissance: 0,
    total: 0,
  };
  for (const g of index.groups) comptes.parGroupe[g] = emptyCounts();

  const applied = [];
  const records = n > 0 ? collect(index, q, withPartial, comptes, applied) : [];

  records.sort((a, b) => a.cls - b.cls || a.yearKey - b.yearKey || b.exact - a.exact || b.agree - a.agree || a.occ - b.occ);

  const kept = [0, 0, 0];
  const correspondances = [];
  for (const r of records) {
    if (kept[r.cls] >= limite) continue;
    kept[r.cls]++;
    correspondances.push(explain(index, q, r));
  }

  const bilan = {
    saisie: q.saisie,
    termes: terms.map(describeTerm),
    particulesIgnorees: q.particulesIgnorees,
    avertissements: q.avertissements,
    annee: q.annee === null ? null : { valeur: q.annee, tolerance: q.tolerance, de: q.annee - q.tolerance, a: q.annee + q.tolerance },
    regles: {
      niveaux: LEVELS,
      k2: { lettresMin: K2_MIN_LETTERS, cleMin: K2_MIN_KEY },
      partielles: withPartial && n >= 2,
      ordre: ['classe', 'ecart-annee', 'termes-exacts', 'voyelles-longues', 'ordre-des-sources'],
      particules: particleList(),
    },
    graphiesTrouvees: terms.map((term, t) => foundSpellings(index, term, applied[t])),
    comptes,
    tronque: {
      correspondance: comptes.parClasse.correspondance > kept[0],
      'graphie-approchante': comptes.parClasse['graphie-approchante'] > kept[1],
      partielle: comptes.parClasse.partielle > kept[2],
    },
    limiteParClasse: limite,
    index: indexSummary(index),
    dureeMs: Math.round((performance.now() - started) * 100) / 100,
  };
  return { correspondances, bilan };
}

function occurrenceOcr(index, occ) {
  const o = index.occurrences[occ];
  return typeof o.ocr === 'boolean' ? o.ocr : index.groupOcr[index.groupOf[occ]];
}

function explain(index, q, r) {
  const o = index.occurrences[r.occ];
  const ocr = occurrenceOcr(index, r.occ);
  const tokens = tokenize(o.nom, { ocr });
  if (tokens.length > MAX_WORDS) tokens.length = MAX_WORDS;
  const forms = nameForms(tokens, { ocr });
  const start = index.occStart[r.occ];
  const termes = q.termes.map((term, t) => {
    const o = r.chosen[2 * t];
    if (o === null) return { terme: term.libelle, absent: true };
    const e = r.chosen[2 * t + 1];
    const meta = index.entMeta[e];
    const c = { o, pos: meta & 255, span: (meta >> 8) & 3 };
    const variant = term.variantes[o.vi];
    const form = forms[e - start];
    const written = [];
    for (let w = c.pos - c.span; w <= c.pos; w++) written.push(tokens[w].raw);
    // The article fused by us in the written name ("El Arbi" read as "Larbi") is said as such.
    const fusedInSource = (meta & FUSED_BIT) !== 0;
    const soudure = fusedInSource ? 'article-fondu' : c.o.soudure;
    let prefixe = null;
    if (soudure === 'prefixe-source') prefixe = form.prefix;
    else if (soudure === 'prefixe-saisie') prefixe = variant.formes[c.o.fi].prefixe;
    else if (soudure === 'colle' || soudure === 'article-fondu') {
      prefixe = c.span > 0 ? form.prefix : (variant.ecriture === 'latin' ? variant.formes[c.o.fi].prefixe : null);
    }
    return {
      terme: term.libelle,
      variante: variant.saisie,
      niveau: LEVELS[c.o.niveau],
      soudure,
      prefixe,
      ecrit: written.join(' '),
      position: c.pos,
      exact: c.o.exact && !fusedInSource,
      arabe: c.o.arabe,
      lecture: c.o.arabe ? variant.candidats[c.o.fi].lecture : null,
      voyellesLongues: c.o.arabe ? c.o.accord : null,
    };
  });
  const y = index.years[r.occ];
  return {
    id: o.id,
    nom: o.nom,
    groupe: index.groups[index.groupOf[r.occ]],
    anneeNaissance: y === 0 ? null : y,
    occurrence: o,
    classe: CLASSES[r.cls],
    termes,
    termeAbsent: r.missing >= 0 ? q.termes[r.missing].libelle : null,
    termesExacts: r.exact,
    annee: q.annee === null ? null : { ecart: r.ecart, inconnue: y === 0 },
  };
}

/**
 * Spellings present in the index that satisfy a term, for the bilan (40 most relevant).
 * A spelling reached through a detached prefix is listed on its own line.
 * Each line: {graphie, forme, exclure, niveau, soudure, arabe, voyellesLongues, occurrences};
 * "exclure" holds the values to pass in the term's "exclues" to untick that line.
 */
function foundSpellings(index, term, best) {
  const lines = new Map();
  for (const [key, opt] of best) {
    const fid = Math.floor(key / 3);
    const viaPrefix = opt.soudure === 'prefixe-source' || opt.soudure === 'prefixe-saisie';
    const id = viaPrefix ? -fid - 1 : fid;
    const count = index.postings[key].length;
    const prev = lines.get(id);
    if (prev === undefined) lines.set(id, { fid, opt, count });
    else {
      prev.count += count;
      if (opt.cost < prev.opt.cost) prev.opt = opt;
    }
  }
  // A stem reached through a detached prefix is shown by the written words that carry it
  // ("Benchabane" for "chabane"). A word already listed for itself ("Benchabane" found for
  // "ben Chabane") is not listed a second time, nor counted twice.
  const carriers = (fid) => {
    const sources = index.stemSources.get(fid) ?? [];
    if (sources.length === 0 || sources.length >= STEM_SOURCES_MAX) return null; // list not known in full
    return sources.filter((src) => !lines.has(src));
  };
  for (const [id, line] of lines) {
    if (id >= 0 || line.opt.soudure !== 'prefixe-source') continue;
    const left = carriers(line.fid);
    if (left === null) continue;
    if (left.length === 0) {
      lines.delete(id);
      continue;
    }
    line.sources = left;
    line.count = left.reduce((sum, src) => sum + (index.postings[src * 3 + KIND.WORD]?.length ?? 0), 0);
  }
  const spelling = ({ fid, opt, sources }) => {
    if (opt.soudure !== 'prefixe-source') return displayForm(index, fid);
    const shown = (sources ?? index.stemSources.get(fid) ?? []).slice(0, 3).map((src) => displayForm(index, src));
    return shown.length > 0 ? shown.join(', ') : displayForm(index, fid);
  };
  // What to put in "exclues" to untick the line: the spelling itself, or, for a detached
  // prefix, the written words that carry it (unticking "chabane" would remove Chabane itself).
  const toExclude = ({ fid, opt, sources }) => {
    if (opt.soudure !== 'prefixe-source') return [index.formK0[fid]];
    const words = sources ?? index.stemSources.get(fid) ?? [];
    return [...new Set(words.map((src) => index.formK0[src]))];
  };
  // A form only ever written with its article apart ("El Arbi" for larbi) is said as such.
  const fusedOnly = ({ fid, opt }) => opt.soudure === 'colle' && index.formFused[fid] === 1
    && index.postings[fid * 3 + KIND.WORD] === undefined;
  const list = [...lines.values()].map((line) => ({
    graphie: spelling(line),
    forme: index.formK0[line.fid],
    exclure: toExclude(line),
    niveau: LEVELS[line.opt.niveau],
    soudure: fusedOnly(line) ? 'article-fondu' : line.opt.soudure,
    arabe: line.opt.arabe,
    voyellesLongues: line.opt.arabe ? line.opt.accord : null,
    occurrences: line.count,
    cout: line.opt.cost,
  }));
  list.sort((a, b) => a.cout - b.cout || b.occurrences - a.occurrences || (a.forme < b.forme ? -1 : a.forme > b.forme ? 1 : 0));
  return {
    terme: term.libelle,
    nombre: list.length,
    tronque: list.length > 40,
    graphies: list.slice(0, 40).map(({ cout, ...rest }) => rest),
  };
}
