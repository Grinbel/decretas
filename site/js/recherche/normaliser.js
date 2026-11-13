/**
 * Name normalisation for French transliterations of Arabic and Berber names (1865-1962).
 *
 * No dependency, no network, usable in a browser, a Web Worker and Node >= 22.
 * The plain-language version of these rules is docs/moteur-de-recherche.md.
 *
 * A written word is compared at three levels, from strict to loose:
 *
 *   k0  folded spelling      lower-case, accents and inner apostrophes removed
 *                            "M'Hamed" -> mhamed ; "Châbane" -> chabane ; "Kaçem" -> kacem
 *   k1  writing equivalences k0 + French transliteration habits that do not change the name
 *                            Mohammed = Mohamed ; Kassem = Kacem = Kaçem ; Chaabane = Chabane ;
 *                            Youcef = Youssef ; Fatmah = Fatma        (Belhadi != Belhadj)
 *   k2  consonant skeleton   k1 + vowels dropped, q/k/g/kh merged, z = s, th = t, dj = j
 *                            Belkacem = Belgacem = Belkassem (blksm) ; Mohamed = M'hamed (mhmd)
 *
 * k2 is an APPROXIMATE level. Known collisions (different names, same skeleton):
 *   Mohamed = Mahmoud (mhmd) ; Hocine = Hassan = Hassen (hsn) ; Slimane = Salomon (slmn) ;
 *   Kacem = Cosme (ksm) ; Aïssa = Assia (asa) ; Amar = Omar = Ameur (amr) ; Kader = Kaddour (kdr).
 * Guards, enforced here and in chercher.js:
 *   - k2 is only used when the word has at least K2_MIN_LETTERS letters and its skeleton at
 *     least K2_MIN_KEY symbols (so "Ali", "Saïd", "Hadj", "Aïch" never match at k2);
 *   - a k2 match is never combined with a detached prefix (except for Arabic-script input,
 *     which is approximate by nature, see arabe.js), never accepted in a partial
 *     correspondence, and always reported in its own class with both spellings.
 */

export const K2_MIN_LETTERS = 4;
export const K2_MIN_KEY = 3;

/** How a searchable form was derived from the written words. */
export const KIND = Object.freeze({ WORD: 0, GLUED: 1, STEM: 2 });
export const KIND_NAMES = Object.freeze(['mot', 'colle', 'decolle']);

// ---------------------------------------------------------------------------------------------
// Folding and tokenisation
// ---------------------------------------------------------------------------------------------

const SPECIAL_LETTERS = { 'œ': 'oe', 'æ': 'ae', 'ß': 'ss', 'ø': 'o', 'ł': 'l', 'đ': 'd', 'ð': 'd', 'þ': 'th', 'ı': 'i' };
const SPECIAL_RE = /[œæßøłđðþı]/g;
const MARKS_RE = /[\u0300-\u036F]/g; // combining marks, written as escapes (invisible in an editor)
const APOSTROPHES = "'’‘ʼʻ`´";
const WORD_RE = new RegExp(`[\\p{L}\\p{M}]+(?:[${APOSTROPHES}][\\p{L}\\p{M}]+)*`, 'gu');
// Printed sources: a stray sign inside a word is OCR noise, not a separator ("Moh:mmed").
const WORD_OCR_RE = new RegExp(`[\\p{L}\\p{M}]+(?:[${APOSTROPHES}:;!|$*][\\p{L}\\p{M}]+)*`, 'gu');
const ELISION_RE = new RegExp(`^[dl][${APOSTROPHES}](.{4,})$`);
const NOT_KEY_RE = /[^a-zç]/g;

/**
 * Lower-case and strip accents. The cedilla is the one diacritic that changes a consonant
 * ("ç" is always /s/), so it is kept here and only dropped when k0 is derived.
 * @param {string} text
 * @returns {string}
 */
export function fold(text) {
  return String(text ?? '')
    .toLowerCase()
    .replace(SPECIAL_RE, (c) => SPECIAL_LETTERS[c])
    .normalize('NFD')
    .replace(/c\u0327/g, '\u00E7') // c + combining cedilla -> ç, before the other marks are dropped
    .replace(MARKS_RE, '');
}

/**
 * @typedef {Object} Token
 * @property {string} raw     the word exactly as written ("M'Hamed", "Kaçem")
 * @property {string} cle     folded word, cedilla kept ("mhamed", "kaçem") — identity of a form
 * @property {string} k0      folded word ("mhamed", "kacem")
 * @property {number} pos     position among the tokens of the name (0-based)
 * @property {boolean} lower  true when the written word starts with a lower-case letter
 * @property {string|null} elided  "alesio" for "D'Alesio" (French d'/l' elision), else null
 */

/**
 * Split a name into words. Spaces, hyphens, commas, brackets, digits and dots separate;
 * an apostrophe INSIDE a word is removed, not split ("M'Hamed" -> mhamed, "N'Aït" -> nait).
 * Words in a non-Latin script are skipped here (see arabe.js for Arabic input).
 * @param {string} text
 * @param {{ocr?: boolean}} [options] ocr: tolerate OCR noise signs inside a word
 * @returns {Token[]}
 */
export function tokenize(text, { ocr = false } = {}) {
  const out = [];
  const re = ocr ? WORD_OCR_RE : WORD_RE;
  re.lastIndex = 0;
  const source = String(text ?? '');
  let m;
  while ((m = re.exec(source)) !== null) {
    const raw = m[0];
    const w = wordInfo(raw);
    if (w.cle === '') continue;
    out.push({ raw, cle: w.cle, k0: w.k0, pos: out.length, lower: w.lower, elided: w.elided });
  }
  return out;
}

const ASCII_WORD_RE = /^[A-Za-z]+$/;
const wordCache = new Map();
const WORD_CACHE_MAX = 400000;

/** Folded reading of one written word (memoised: given names repeat a lot). */
function wordInfo(raw) {
  let w = wordCache.get(raw);
  if (w !== undefined) return w;
  const first = raw[0];
  const lower = first === first.toLowerCase() && first !== first.toUpperCase();
  if (ASCII_WORD_RE.test(raw)) {
    const cle = raw.toLowerCase();
    w = { cle, k0: cle, lower, elided: null };
  } else {
    const folded = fold(raw);
    const cle = folded.replace(NOT_KEY_RE, '');
    const el = ELISION_RE.exec(folded);
    w = { cle, k0: cle.includes('ç') ? cle.replace(/ç/g, 'c') : cle, lower, elided: el ? el[1].replace(NOT_KEY_RE, '') : null };
  }
  if (wordCache.size >= WORD_CACHE_MAX) wordCache.clear();
  wordCache.set(raw, w);
  return w;
}

// ---------------------------------------------------------------------------------------------
// Keys
// ---------------------------------------------------------------------------------------------

/**
 * k1 before its two end-of-word rules (shared by k1 and by the skeleton).
 *
 *   ç -> s                      Kaçem = Kassem ; Haçan = Hassan
 *   sch, tch, sh -> ch          Schérif = Chérif ; Tchaker = Chaker
 *   ph -> f                     Mustapha = Mustafa
 *   y -> i                      Yahya = Yahia ; Tayeb = Taïeb
 *   c before e, i -> s          Kacem = Kasem ; Hocine = Hossine ; Youcef = Youssef
 *   ck, cq, q, qu+vowel, hard c -> k   Cadi = Kadi ; Qasim = Kasim ; Jacques = Jaques ("ch" is kept)
 *   ou, oo, w -> u              Daoud = Dawd ; Wahab = Ouahab
 *   doubled letter -> single    Mohammed = Mohamed ; Chaabane = Chabane ; Kassem = Kasem
 * @param {string} cle folded word (see fold)
 * @returns {string}
 */
export function k1Core(cle) {
  // Each rule is skipped when its letters are absent: this runs once per distinct word.
  let t = cle;
  if (t.includes('ç')) t = t.replace(/ç/g, 's');
  if (t.includes('h')) t = t.replace(/sch|tch|sh/g, 'ch').replace(/ph/g, 'f');
  if (t.includes('y')) t = t.replace(/y/g, 'i');
  if (t.includes('c') || t.includes('q')) {
    t = t.replace(/c(?=[ei])/g, 's').replace(/c?q(?:u(?=[aeio]))?|ck|c(?!h)/g, 'k');
  }
  if (t.includes('o') || t.includes('w')) t = t.replace(/ou|oo|w/g, 'u');
  return DOUBLED_RE.test(t) ? t.replace(/(.)\1+/g, '$1') : t;
}

const DOUBLED_RE = /(.)\1/;

/**
 * k1, the "writing equivalences" key: k1Core, then
 *   mute final e after n (4+ letters) Chabane = Chaban ; Slimane = Sliman ; Eddine = Eddin
 *                                     (only after "n": Louise != Louis, Saïde != Saïd at k1)
 *   final h after a vowel             Fatmah = Fatma ; Abdallah = Abdalla ; Salah = Sala
 * Known k1 conflations, accepted: Jean = Jeanne, Simon = Simone (French feminine in -ne).
 * @param {string} cle
 * @returns {string}
 */
export function k1(cle) {
  let t = k1Core(cle);
  let n = t.length;
  if (n >= 4 && t[n - 1] === 'e' && t[n - 2] === 'n') t = t.slice(0, --n);
  if (n >= 2 && t[n - 1] === 'h' && isVowel(t[n - 2])) t = t.slice(0, n - 1);
  return t;
}

const isVowel = (c) => c === 'a' || c === 'e' || c === 'i' || c === 'o' || c === 'u';

function tailClass(vowel, beforeDroppedH) {
  if (vowel === 'a') return 'a';
  if (vowel === 'o' || vowel === 'u') return 'u';
  if (vowel === 'e' && beforeDroppedH) return 'a'; // Saleh = Salah
  return 'i';
}

/**
 * @typedef {Object} Skeleton
 * @property {string} key          the k2 key
 * @property {string[]} consonants consonant symbols, in order ("ch" is one symbol)
 * @property {string[]} vowels     vowels[0] = vowels before the first consonant,
 *                                 vowels[i] = vowels written after consonants[i-1]
 * @property {number} symbols      number of symbols in the key ("ch" counts for one)
 */

/**
 * k2, the consonant skeleton. Starting from k1Core:
 *
 *   kh -> k ; hard g, gu+e/i -> k     Khaled = Kaled ; Belgacem = Belkacem ; Guesmi = Kesmi
 *   gh -> g (kept apart)              Seghir = Sghir, but Ghali != Kali != Khali
 *   soft g (ge, gi), dj -> j          Hadj = Haj ; Djilali = Jilali
 *   dh -> d ; th -> t ; z -> s        Fathma = Fatma ; Zemri = Semri
 *   final -aoui / -oui -> "wi"        Mostefaoui (mstfwi) stays distinct from Mostefa (mstfa)
 *   vowels inside the word dropped    Mustapha = Mostefa ; Hocine = Hussein
 *   first vowel -> "a"                Aomar = Omar = Amar ; Athmane = Othmane ; Aïssa = Issa
 *   first i/y or ou/w + vowel -> y, w Youcef (ysf) ; Ouali = Wali (wli)
 *   mute final e dropped (4+ letters) Brahime = Brahim
 *   final vowel kept as a class       a | i (i, e) | u (o, ou) : Mahmoudi != Mahmoud ;
 *                                     Fatma != Fatmi ; "-ah" = "-eh" = "-a" (Saleh = Salah)
 * @param {string} cle
 * @returns {Skeleton}
 */
export function skeleton(cle) {
  let t = k1Core(cle);
  let droppedH = false;
  if (t.length > 2 && t[t.length - 1] === 'h' && isVowel(t[t.length - 2])) {
    t = t.slice(0, -1);
    droppedH = true;
  }
  let gh = false;
  if (t.includes('h')) {
    gh = t.includes('gh');
    t = t.replace(/kh/g, 'k').replace(/dh/g, 'd').replace(/th/g, 't');
    if (gh) t = t.replace(/gh/g, 'q'); // placeholder: must not be read as a soft g ("Seghir")
  }
  if (t.includes('j')) t = t.replace(/dj/g, 'j');
  if (t.includes('g')) t = t.replace(/gu(?=[ei])/g, 'k').replace(/g(?=[ei])/g, 'j').replace(/g/g, 'k');
  if (gh) t = t.replace(/q/g, 'g'); // "g" in a key always means gh (ghayn)
  if (t.includes('z')) t = t.replace(/z/g, 's');
  if (DOUBLED_RE.test(t)) t = t.replace(/([^aeiou])\1+/g, '$1');
  if (t.length >= 5 && t[t.length - 1] === 'i' && (t[t.length - 2] === 'u' || t[t.length - 2] === 'o')) {
    t = `${t.slice(0, -2)}wi`;
  }
  if (!droppedH && t.length > 3 && t.endsWith('e')) t = t.slice(0, -1);

  const consonants = [];
  const vowels = [''];
  let lead = '';
  let i = 0;
  if (t.length > 0 && isVowel(t[0])) {
    if ((t[0] === 'i' || t[0] === 'u') && t.length > 1 && isVowel(t[1])) {
      consonants.push(t[0] === 'i' ? 'y' : 'w');
      vowels.push('');
      i = 1;
    } else {
      lead = 'a';
      while (i < t.length && isVowel(t[i])) vowels[0] += t[i++];
    }
  }
  for (; i < t.length; i++) {
    const c = t[i];
    if (isVowel(c)) {
      vowels[vowels.length - 1] += c;
    } else if (c === 'c' && t[i + 1] === 'h') {
      consonants.push('ch');
      vowels.push('');
      i++;
    } else {
      consonants.push(c);
      vowels.push('');
    }
  }
  let tail = '';
  const last = vowels[vowels.length - 1];
  if (consonants.length > 0 && last !== '' && t.length >= 3) {
    tail = tailClass(last[last.length - 1], droppedH);
  }
  return {
    key: lead + consonants.join('') + tail,
    consonants,
    vowels,
    symbols: (lead === '' ? 0 : 1) + consonants.length + (tail === '' ? 0 : 1),
  };
}

/**
 * @param {string} cle
 * @returns {string} the k2 key
 */
export function k2(cle) {
  return skeleton(cle).key;
}

/**
 * @typedef {Object} Keys
 * @property {string} cle
 * @property {string} k0
 * @property {string} k1
 * @property {string} k2
 * @property {boolean} k2ok  false when the word is too short for the approximate level
 */

const keyCache = new Map();
const KEY_CACHE_MAX = 400000;

/**
 * The three keys of a folded word (memoised).
 * @param {string} cle
 * @returns {Keys}
 */
export function keysOf(cle) {
  let k = keyCache.get(cle);
  if (k === undefined) {
    const k0 = cle.includes('ç') ? cle.replace(/ç/g, 'c') : cle;
    const sk = skeleton(cle);
    k = { cle, k0, k1: k1(cle), k2: sk.key, k2ok: k0.length >= K2_MIN_LETTERS && sk.symbols >= K2_MIN_KEY };
    if (keyCache.size >= KEY_CACHE_MAX) keyCache.clear();
    keyCache.set(cle, k);
  }
  return k;
}

/**
 * Keys of one word as a user would write it ("Châbane", "M'hamed").
 * @param {string} word
 * @returns {Keys|null} null when the word has no Latin letter
 */
export function keysOfWord(word) {
  const cle = fold(word).replace(NOT_KEY_RE, '');
  return cle === '' ? null : keysOf(cle);
}

// ---------------------------------------------------------------------------------------------
// Particles
// ---------------------------------------------------------------------------------------------

/**
 * Particles: filiation words, articles, honorifics and civil-status words. A correspondence
 * never REQUIRES them and they are never searched on their own (unless the user forces the
 * word with double quotes). Value = canonical spelling used when gluing ("b." -> ben).
 */
const PARTICLE_TABLE = {
  // filiation
  ben: 'ben', bn: 'ben', b: 'ben', bin: 'ben', ibn: 'ben', ebn: 'ben',
  bent: 'bent', bint: 'bent', bt: 'bent',
  ould: 'ould', oulid: 'ould', oult: 'oult', oulad: 'oulad', ouled: 'ouled',
  ou: 'ou', u: 'ou', ait: 'ait', ath: 'ath', at: 'at', nait: 'nait', n: 'n',
  fils: 'fils', fille: 'fille',
  // articles, and name-forming prefixes when written as separate words
  el: 'el', al: 'al', l: 'l', ed: 'ed', es: 'es', en: 'en', er: 'er', ez: 'ez', et: 'et', ech: 'ech',
  bel: 'bel', bou: 'bou', abou: 'abou', abd: 'abd', abdel: 'abdel',
  // honorifics
  si: 'si', sid: 'sid', sidi: 'sidi', hadj: 'hadj', hadja: 'hadja', lalla: 'lalla', moulay: 'moulay',
  // civil status
  dit: 'dit', dite: 'dite', alias: 'alias', ne: 'ne', nee: 'nee', veuve: 'veuve', vve: 'veuve',
  femme: 'femme', epouse: 'epouse', ep: 'epouse',
  // European particles
  de: 'de', du: 'du', des: 'des', d: 'd', di: 'di', da: 'da', del: 'del', della: 'della',
  van: 'van', von: 'von', le: 'le', la: 'la',
};
const PARTICLES = new Map(Object.entries(PARTICLE_TABLE));

/** Particles that are also found glued to the next word: "Bel Kacem" / "Belkacem". */
const ATTACHABLE = new Set([
  'ben', 'bent', 'ould', 'oulad', 'ouled', 'ou', 'ait', 'ath', 'nait',
  'el', 'al', 'ed', 'es', 'en', 'er', 'ez', 'et', 'ech', 'bel', 'bou', 'abou', 'abd', 'abdel',
  'si', 'sid', 'sidi', 'hadj',
  'de', 'du', 'des', 'di', 'da', 'del', 'della', 'van', 'von', 'le', 'la',
]);

/** Honorifics that also end a family name: "Bel Hadj" = "Belhadj". */
const TITLES = new Set(['hadj', 'hadja', 'sidi']);

/** The article that French spelling also fuses with a following vowel or h: "El Arbi" = "Larbi". */
const FUSABLE = new Set(['el', 'al']);
const FUSED_START_RE = /^[aeiouh]/;

/**
 * Fused-article spelling of "el" + word: El Arbi -> larbi, El Akhdar -> lakhdar, El Aïd -> laïd,
 * El Houcine -> lhoucine. Only before a vowel or an h (the article is not fused with another
 * consonant in French spelling), and never on a word of fewer than three letters.
 * @param {string} particle canonical particle typed or written just before the word
 * @param {string} cle folded word
 * @returns {string|null}
 */
export function fusedArticleForm(particle, cle) {
  return FUSABLE.has(particle) && cle.length >= 3 && FUSED_START_RE.test(cle) ? `l${cle}` : null;
}

/**
 * Prefixes that may be DETACHED from a glued word: "Benchabane" -> "chabane".
 * "al", "si"-like European look-alikes are limited by the 4-letter rule and by never
 * producing a particle; "al" itself is not detached (Albert, Alfred).
 */
const DETACHABLE = ['abou', 'abd', 'bent', 'ben', 'bel', 'bou', 'ould', 'nait', 'ait', 'el', 'si', 'ou'];
const MIN_STEM = 4;

/**
 * OCR readings of particles in the printed bulletins. Only trusted in a printed source, written
 * in lower case, between two other words.
 *   "ben": "bon", "ban", "ten" (research report, volumes of 1873 and 1888) ; "bea", "hen", "beu"
 *          (seen in the entries built on 2026-11-11: bon 4, ten 2, bea 2, hen 1, beu 1, every one
 *          of them a real "ben") ; "bcn" by analogy only, never observed.
 *   "ou":  "on" (seen 3 times: "… ben Mohammed on Kassi").
 */
const OCR_PARTICLES = new Map([
  ['bon', 'ben'], ['ban', 'ben'], ['ten', 'ben'], ['bea', 'ben'], ['hen', 'ben'], ['beu', 'ben'], ['bcn', 'ben'],
  ['on', 'ou'],
]);

/**
 * @param {string} k0
 * @returns {boolean}
 */
export function isParticle(k0) {
  return PARTICLES.has(k0);
}

/**
 * @param {string} k0
 * @returns {string|null} canonical particle ("b" -> "ben") or null
 */
export function canonicalParticle(k0) {
  return PARTICLES.get(k0) ?? null;
}

/**
 * @param {string} particle canonical particle
 * @returns {boolean}
 */
export function isAttachable(particle) {
  return ATTACHABLE.has(particle);
}

/**
 * @param {string} particle canonical particle
 * @returns {boolean}
 */
export function isTitle(particle) {
  return TITLES.has(particle);
}

/** @returns {string[]} every particle spelling, sorted (for the documentation and the bilan) */
export function particleList() {
  return [...PARTICLES.keys()].sort();
}

/**
 * Particle reading of token i of a name, or null. Single letters other than the listed
 * abbreviations are initials: not particles, simply not searchable.
 * @param {Token[]} tokens
 * @param {number} i
 * @param {boolean} ocr printed source: accept OCR readings of "ben" and "ou"
 * @returns {string|null} canonical particle
 */
export function particleAt(tokens, i, ocr = false) {
  const t = tokens[i];
  const p = PARTICLES.get(t.k0);
  if (p !== undefined) return p;
  if (ocr && t.lower && i > 0 && i < tokens.length - 1) return OCR_PARTICLES.get(t.k0) ?? null;
  return null;
}

function stripArticle(s) {
  if (s.startsWith('el') && s.length - 2 >= MIN_STEM) return { stem: s.slice(2), article: 'el' };
  const m = /^([ea])([dnrstz])\2/.exec(s); // assimilated article: ez-Zemri, en-Nacer, ed-Dine
  if (m) return { stem: s.slice(2), article: m[1] + m[2] };
  if (/^[ea]chch/.test(s)) return { stem: s.slice(3), article: 'ech' };
  return null;
}

/**
 * Words obtained by detaching a glued prefix. Never returns a particle and never a word
 * shorter than 4 letters: "Belhadj" does not become "hadj", "Benali" does not become "ali".
 *
 *   benchabane -> chabane (ben)        belkacem -> kacem (bel)        ezzemri -> zemri (ez)
 *   abdelkader -> elkader (abd), kader (abdel)      abderrahmane -> rahmane (abder)
 * @param {string} cle folded word
 * @returns {{stem: string, prefix: string}[]}
 */
export function detachedStems(cle) {
  const out = [];
  const add = (stem, prefix) => {
    if (stem.length < MIN_STEM || PARTICLES.has(stem.replace(/ç/g, 'c'))) return;
    if (out.some((s) => s.stem === stem)) return;
    out.push({ stem, prefix });
  };
  for (const p of DETACHABLE) {
    if (!cle.startsWith(p)) continue;
    const rest = cle.slice(p.length);
    add(rest, p);
    const a = stripArticle(rest);
    if (a) add(a.stem, p + a.article);
  }
  const a = stripArticle(cle);
  if (a && a.article !== 'el') add(a.stem, a.article);
  return out;
}

/**
 * @typedef {Object} NameForm
 * @property {string} cle       folded form (identity in the index)
 * @property {number} kind      KIND.WORD | KIND.GLUED | KIND.STEM
 * @property {number} pos       position of the written word the form belongs to
 * @property {number} span      number of preceding written words glued in (KIND.GLUED), else 0
 * @property {string|null} prefix  detached prefix (KIND.STEM), glued particles (KIND.GLUED)
 * @property {boolean} particle true for a particle indexed as itself (only forced terms match it)
 * @property {boolean} [fused]  true for a glued form whose article is fused ("El Arbi" -> larbi)
 */

/**
 * Every searchable form of a written name.
 *
 *   word   each word as written                               "Chabane" -> chabane
 *   glued  attachable particle(s) + the next word             "Bel Kaçem" -> belkaçem ;
 *          (two particles at most)                            "Abd el Kader" -> elkader, abdelkader ;
 *                                                             "Bel Hadj" -> belhadj
 *          article fused with a vowel or an h                 "El Arbi" -> elarbi, larbi
 *   stem   a word without its glued prefix                    "Benchabane" -> chabane ;
 *          or without a glued "ben" at its end                "Ezzemri" -> zemri ; "Aliben" -> ali
 * @param {Token[]} tokens
 * @param {{ocr?: boolean}} [options]
 * @returns {NameForm[]}
 */
export function nameForms(tokens, { ocr = false } = {}) {
  const n = tokens.length;
  const out = [];
  const particles = new Array(n);
  const tailBen = new Array(n).fill(null); // "Aliben Fictifi": word i carries a glued ben
  for (let i = 0; i < n; i++) particles[i] = particleAt(tokens, i, ocr);

  const pushGlued = (i) => {
    let glue = '';
    let j = i - 1;
    let depth = 0;
    if (j >= 0 && tailBen[j] !== null) {
      out.push({ cle: tailBen[j] + tokens[i].cle, kind: KIND.GLUED, pos: i, span: 1, prefix: tailBen[j], particle: false });
      return;
    }
    for (; j >= 0 && depth < 2; j--, depth++) {
      const p = particles[j];
      if (p === null || !ATTACHABLE.has(p)) break;
      if (depth === 1 && TITLES.has(p)) break; // "Hadj el Arbi" is not glued into "hadjelarbi"
      glue = p + glue;
      out.push({ cle: glue + tokens[i].cle, kind: KIND.GLUED, pos: i, span: i - j, prefix: glue, particle: false });
      // "El Arbi" is also written "Larbi". Not for a title: "El Hadj" must stay a particle.
      const fused = depth === 0 && particles[i] === null ? fusedArticleForm(p, tokens[i].cle) : null;
      if (fused !== null) out.push({ cle: fused, kind: KIND.GLUED, pos: i, span: 1, prefix: p, particle: false, fused: true });
    }
  };

  for (let i = 0; i < n; i++) {
    const t = tokens[i];
    const p = particles[i];
    if (p !== null) {
      if (t.k0.length > 1 && PARTICLES.has(t.k0)) {
        out.push({ cle: t.cle, kind: KIND.WORD, pos: i, span: 0, prefix: null, particle: true });
      }
      if (TITLES.has(p)) pushGlued(i);
      continue;
    }
    if (t.k0.length < 2) continue; // an initial
    out.push({ cle: t.cle, kind: KIND.WORD, pos: i, span: 0, prefix: null, particle: false });
    for (const s of detachedStems(t.cle)) {
      out.push({ cle: s.stem, kind: KIND.STEM, pos: i, span: 0, prefix: s.prefix, particle: false });
    }
    if (t.elided !== null) {
      out.push({ cle: t.elided, kind: KIND.STEM, pos: i, span: 0, prefix: t.k0[0], particle: false });
    }
    if (i < n - 1) {
      const m = /^([a-zç]{3,}?)(bent?)$/.exec(t.cle);
      if (m && !PARTICLES.has(m[1])) {
        tailBen[i] = m[2];
        out.push({ cle: m[1], kind: KIND.STEM, pos: i, span: 0, prefix: `-${m[2]}`, particle: false });
      }
    }
    pushGlued(i);
  }
  return out;
}
