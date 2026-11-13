/**
 * Arabic-script entry path: from a name typed in Arabic (بلقاسم بن شعبان) to the consonant
 * skeletons (k2 keys, see normaliser.js) under which French clerks may have written it.
 *
 * What it does: maps each Arabic letter to the skeleton symbol of its usual French rendering,
 * drops what French spelling does not keep (short vowels are not written in Arabic anyway),
 * recognises the particles, and proposes a small set of candidate keys per word.
 *
 * What it cannot do — say it to the user:
 *   - Arabic does not write short vowels and the skeleton drops the others: the match is ALWAYS
 *     approximate ("saisie en arabe : correspondance approchante"), even for a perfect name.
 *   - Short names give short keys and many unrelated spellings (سعيد -> "sd": Saïd, Saad, Sid…).
 *     The long vowels typed (ا و ي) are compared with the French spelling only to ORDER the
 *     results (concordant spellings first), never to hide one.
 *   - Dialect renderings that change a consonant are missed: ق written "g" is covered (g = k),
 *     but غ written "r'", ث written "ts", ذ/ظ written "z" are not.
 *   - A first ي is always read "y" (يمينة is Yamina, never Amina) and a final ي always "-i", a
 *     final ى always "-a". Exceptions, by a short list of names: يحي موسي عيسي مصطفي ليلي سلمي are
 *     also read with "-a" (Yahia, Moussa…), and يدير is also read "Idir".
 *   - "X الدين" (one or two words) is read as ONE name in "-eddine" (Noureddine). A source that
 *     writes it in two words ("Nour Eddine") is not found by this reading.
 *   - Berber names have no settled Arabic spelling; type them in Latin letters.
 */

import { skeleton } from './normaliser.js';

// Written as \uXXXX escapes: the ranges start or end on invisible characters (U+0600, U+FEFF).
const ARABIC_RE = /[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]/;
const ARABIC_WORD_RE = /[\u0621-\u064A\u066E-\u06D3]+/g; // letters only: no digits, signs or marks
const DIACRITICS_RE = /[\u064B-\u065F\u0670\u0640]/g; // harakat, dagger alif, tatweel

/** Arabic consonant -> skeleton symbol (same symbols as normaliser.js#skeleton). */
const CONSONANTS = {
  'ب': 'b', 'پ': 'p', 'ت': 't', 'ث': 't', 'ج': 'j', 'چ': 'ch', 'ح': 'h', 'خ': 'k',
  'د': 'd', 'ذ': 'd', 'ر': 'r', 'ز': 's', 'ژ': 'j', 'س': 's', 'ش': 'ch', 'ص': 's', 'ض': 'd',
  'ط': 't', 'ظ': 'd', 'غ': 'g', 'ف': 'f', 'ڤ': 'v', 'ڥ': 'v', 'ق': 'k', 'ڨ': 'k', 'ك': 'k',
  'ک': 'k', 'گ': 'k', 'ڭ': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n', 'ه': 'h',
};
const INITIAL_VOWEL = new Set(['ا', 'أ', 'إ', 'آ', 'ٱ', 'ع', 'ء']);
const WEAK = new Set(['ا', 'أ', 'إ', 'آ', 'ٱ', 'ع', 'ء', 'ؤ', 'ئ', 'و', 'ي', 'ى', 'ی']);
/** Letters that assimilate the article: الزمري is said, and written by clerks, "Ez-Zemri". */
const SUN_LETTERS = new Set('تثدذرزسشصضطظلن');
/** Names written with a bare alif whose first vowel French spelling often drops (Brahim, Smaïl, Driss). */
const DROPPABLE_INITIAL = new Set(['ابراهيم', 'اسماعيل', 'اسمعيل', 'ادريس']);
/**
 * Names that end in ى (-a) and are very often typed with a plain ي: يحي for يحيى (Yahia),
 * موسي for موسى (Moussa). For these words only, the final ي is also read "-a".
 */
const YA_FOR_MAQSURA = new Set(['يحي', 'موسي', 'عيسي', 'مصطفي', 'ليلي', 'سلمي']);
/** Names whose first ي is a vowel in French spelling (Idir, Yidir), not the consonant of "Yamina". */
const YA_AS_VOWEL = new Set(['يدير']);
/** Letters after which the article is also written fused in French: Lhocine, Lhadi (and any vowel). */
const FUSED_AFTER = new Set(['ح', 'ه']);
/** Second half of the compound names in "-eddine" (Noureddine, Azzedine, Kheireddine…). */
const DINE = 'الدين';

/** Arabic particle (hamza forms reduced to bare alif) -> canonical particle of normaliser.js. */
const PARTICLES = new Map(Object.entries({
  'بن': 'ben', 'ابن': 'ben', 'بنت': 'bent', 'ابنة': 'bent', 'ولد': 'ould', 'اولاد': 'oulad',
  'بو': 'bou', 'ابو': 'abou', 'ابي': 'abou', 'عبد': 'abd', 'ال': 'el', 'بل': 'bel',
  'سي': 'si', 'سيدي': 'sidi', 'حاج': 'hadj', 'الحاج': 'hadj', 'حاجة': 'hadja', 'الحاجة': 'hadja',
  'ايت': 'ait', 'ايث': 'ath', 'ناث': 'nait', 'نايت': 'nait', 'نايث': 'nait',
  'لالة': 'lalla', 'للا': 'lalla', 'مولاي': 'moulay',
  'المدعو': 'dit', 'المدعوة': 'dite', 'ارملة': 'veuve', 'زوجة': 'epouse', 'و': 'et',
}));

/** Skeleton of each particle when a clerk glued it to the next word (Benali -> "bn" + "li"). */
const GLUE = {
  ben: [{ lead: false, cons: ['b', 'n'] }],
  bent: [{ lead: false, cons: ['b', 'n', 't'] }],
  bel: [{ lead: false, cons: ['b', 'l'] }],
  bou: [{ lead: false, cons: ['b'] }],
  abou: [{ lead: true, cons: ['b'] }, { lead: false, cons: ['b'] }],
  abd: [{ lead: true, cons: ['b', 'd'] }],
  el: [{ lead: true, cons: ['l'] }],
  ould: [{ lead: true, cons: ['l', 'd'] }],
  ait: [{ lead: true, cons: ['t'] }],
  nait: [{ lead: false, cons: ['n', 't'] }],
  si: [{ lead: false, cons: ['s'] }],
};

/**
 * @param {string} text
 * @returns {boolean} true when the text contains Arabic script
 */
export function hasArabic(text) {
  return ARABIC_RE.test(String(text ?? ''));
}

/**
 * Arabic words of a text: presentation forms unified, vowel signs and tatweel removed.
 * @param {string} text
 * @returns {string[]}
 */
export function arabicWords(text) {
  const clean = String(text ?? '').normalize('NFKC').replace(DIACRITICS_RE, '');
  const words = clean.match(ARABIC_WORD_RE) ?? [];
  // "نور الدين" is ONE name (Noureddine): the two words are kept together, with their space.
  const out = [];
  for (const word of words) {
    const previous = out[out.length - 1];
    if (word === DINE && previous !== undefined && !previous.includes(' ') && [...previous].length >= 2
      && PARTICLES.get(bareAlif(previous)) === undefined) {
      out[out.length - 1] = `${previous} ${word}`;
    } else {
      out.push(word);
    }
  }
  return out;
}

const bareAlif = (word) => word.replace(/[أإآٱ]/g, 'ا');

/**
 * @param {string} word one Arabic word (see arabicWords)
 * @returns {string|null} canonical particle (ben, bent, ould, abd, el, hadj…) or null
 */
export function arabicParticle(word) {
  return PARTICLES.get(bareAlif(word)) ?? null;
}

/**
 * @typedef {Object} ArabicSkeleton
 * @property {boolean} lead      the word starts with a vowel carrier (ا أ إ ع): key starts with "a"
 * @property {string[]} cons     consonant symbols
 * @property {string[]} longs    longs[i] = long vowels typed after cons[i], as classes "a" "u" "i"
 * @property {string} tail       final vowel class ("a", "i", "u" or "")
 * @property {string} tailAlt    other plausible final class (final ع only: Rabia / Rabie), else ""
 */

/**
 * Letter-by-letter skeleton of one Arabic word.
 *
 *   first letter  ا أ إ آ ع -> "a" (any first vowel) ; و -> w ; ي -> y
 *   و ي ا inside  not kept (French "ou", "i", "a" are vowels), remembered as long vowels
 *   ع ء ؤ ئ inside  dropped (Messaoud مسعود -> msd)
 *   last letter   ة ا ى -> a ; ي -> i ; و -> u ; ح ه -> a (Salah, Abdallah), or the class of
 *                 the long vowel before it (Nazih نزيه -> i)
 *   ending وي     -> "wi" (Hamraoui حمراوي -> hmrwi)
 * @param {string[]} letters
 * @returns {ArabicSkeleton}
 */
export function arabicSkeleton(letters) {
  const n = letters.length;
  const cons = [];
  const longs = [];
  let lead = false;
  let tail = '';
  let tailAlt = '';
  let i = 0;
  let gap = true; // something was written since the last consonant
  const push = (symbol) => {
    if (!gap && cons.length > 0 && cons[cons.length - 1] === symbol) return;
    cons.push(symbol);
    longs.push('');
    gap = false;
  };
  const markLong = (cls) => {
    gap = true;
    if (cons.length > 0 && !longs[longs.length - 1].includes(cls)) longs[longs.length - 1] += cls;
  };

  if (n === 0) return { lead, cons, longs, tail, tailAlt };
  if (INITIAL_VOWEL.has(letters[0])) {
    lead = true;
    i = 1;
    while (i < n - 1 && WEAK.has(letters[i])) i++; // Aïssa عيسى, Ayoub أيوب: all leading vowels
  } else if (letters[0] === 'و' && n > 1) {
    push('w');
    i = 1;
  } else if ((letters[0] === 'ي' || letters[0] === 'ی') && n > 1) {
    push('y'); // always a consonant: reading يمينة as "Amina" would be a wrong match
    i = 1;
  }
  for (; i < n; i++) {
    const c = letters[i];
    const last = i === n - 1;
    if (!last && c === 'و' && (letters[i + 1] === 'ي' || letters[i + 1] === 'ی') && i + 1 === n - 1 && cons.length >= 2) {
      push('w'); // nisba ending
      tail = 'i';
      break;
    }
    if (c === 'ا' || c === 'آ' || c === 'أ' || c === 'إ' || c === 'ٱ') {
      if (last) tail = 'a';
      else if (c === 'ا' || c === 'آ') markLong('a');
      else gap = true;
    } else if (c === 'و') {
      if (last) tail = 'u';
      else markLong('u');
    } else if (c === 'ي' || c === 'ى' || c === 'ی') {
      if (last) tail = c === 'ى' ? 'a' : 'i'; // موسى ends in -a, علي in -i: no guessing between them
      else markLong('i');
    } else if (c === 'ة') {
      if (last) tail = 'a';
      else push('t');
    } else if (c === 'ع' || c === 'ء' || c === 'ؤ' || c === 'ئ') {
      gap = true;
      if (last && c === 'ع') {
        tail = 'a'; // Rabia / Rabie ربيع
        tailAlt = 'i';
      }
    } else if (last && (c === 'ح' || c === 'ه') && cons.length > 0) {
      // French keeps a vowel and often drops the h: Salah / Sala, Abdallah / Abdalla, Nazih
      const before = longs[longs.length - 1];
      tail = before.includes('i') ? 'i' : before.includes('u') ? 'u' : 'a';
      if (before !== '') longs[longs.length - 1] = before.replace(tail, '');
    } else if (CONSONANTS[c] !== undefined) {
      push(CONSONANTS[c]);
    }
  }
  return { lead, cons, longs, tail, tailAlt };
}

/**
 * @typedef {Object} ArabicCandidate
 * @property {string} key      k2 key to look up
 * @property {string[]} cons
 * @property {string[]} longs
 * @property {'entier'|'colle'} genre  'colle': typed particle(s) glued to the word (بن علي -> bnli)
 * @property {string} lecture  how the key was read: 'mot', 'article-detache', 'article-fondu',
 *                             'article-assimile', 'voyelle-initiale-omise', 'compose-eddine',
 *                             'colle:<particles>'
 */

function candidate(lead, cons, longs, tail, genre, lecture) {
  // Like the Latin skeleton, a final vowel only counts in a word of some length.
  const keepTail = (lead ? 1 : 0) + cons.length >= 2 || longs.some((l) => l !== '');
  return { key: (lead ? 'a' : '') + cons.join('') + (keepTail ? tail : ''), cons, longs, genre, lecture };
}

function joinSkeletons(prefix, lead, cons, longs) {
  const outCons = prefix.cons.slice();
  const outLongs = prefix.cons.map(() => '');
  for (let i = 0; i < cons.length; i++) {
    if (i === 0 && !lead && outCons[outCons.length - 1] === cons[0]) {
      outLongs[outLongs.length - 1] = longs[0];
      continue; // "abd" + "el" + "lah": one l
    }
    outCons.push(cons[i]);
    outLongs.push(longs[i]);
  }
  return { cons: outCons, longs: outLongs };
}

/**
 * Candidate skeletons of one Arabic word that is not a particle.
 * @param {string} word
 * @param {string[]} [before] canonical particles typed just before the word (nearest last)
 * @returns {ArabicCandidate[]} distinct keys, most direct reading first
 */
export function arabicCandidates(word, before = []) {
  const letters = [...String(word).replace(/\s+/g, '')];
  const bare = bareAlif(letters.join(''));
  const out = [];
  const seen = new Set();
  const add = (c) => {
    if (c.cons.length === 0 || seen.has(c.key)) return;
    seen.add(c.key);
    out.push(c);
  };
  const addAll = (sk, lead, genre, lecture, extraCons = [], prefix = null) => {
    const cons = extraCons.concat(sk.cons);
    const longs = extraCons.map(() => '').concat(sk.longs);
    for (const tail of sk.tailAlt ? [sk.tail, sk.tailAlt] : [sk.tail]) {
      if (prefix) {
        const j = joinSkeletons(prefix, lead, cons, longs);
        add(candidate(prefix.lead, j.cons, j.longs, tail, genre, lecture));
      } else {
        add(candidate(lead, cons, longs, tail, genre, lecture));
      }
    }
  };

  // Compound in "-eddine", typed in one or two words: نور الدين, نورالدين -> Noureddine. French
  // writes it as one word without the l of the article, so the only reading is first part + "dn".
  if (bare.endsWith(DINE) && letters.length >= DINE.length + 2) {
    const first = letters.slice(0, letters.length - DINE.length);
    const compound = arabicSkeleton(first.concat(['د', 'ي', 'ن']));
    addAll(compound, compound.lead, 'entier', 'compose-eddine');
    return out;
  }

  const whole = arabicSkeleton(letters);
  if (YA_FOR_MAQSURA.has(bare)) {
    whole.tailAlt = whole.tail;
    whole.tail = 'a';
  }
  addAll(whole, whole.lead, 'entier', 'mot');
  if (letters[0] === 'إ' || DROPPABLE_INITIAL.has(bare)) addAll(whole, false, 'entier', 'voyelle-initiale-omise');
  if (YA_AS_VOWEL.has(bare)) addAll(arabicSkeleton(letters.slice(1)), true, 'entier', 'mot');

  // عبدالرحمن typed as one word: before a "sun" letter French drops the l (Abderrahmane, Abdesselam,
  // Abdennour); the reading with the l (Abdelkader, Abdallah) is the whole word above.
  if (bare.startsWith('عبدال') && letters.length >= 7 && SUN_LETTERS.has(letters[5])) {
    const rest = arabicSkeleton(letters.slice(5));
    const joined = joinSkeletons({ lead: true, cons: ['b', 'd'] }, rest.lead, rest.cons, rest.longs);
    add(candidate(true, joined.cons, joined.longs, rest.tail, 'entier', 'article-assimile'));
  }

  // Article: الزمري -> Zemri (detached), Ezzemri (assimilated) ; العربي -> Arbi, Larbi (fused).
  // The fused reading only exists before a vowel or an h (Larbi, Lakhdar, Lhocine): reading
  // القادر as "Lkader" would bring back every Lakhdar.
  let stem = whole;
  let article = false;
  if (letters.length >= 4 && letters[0] === 'ا' && letters[1] === 'ل') {
    article = true;
    stem = arabicSkeleton(letters.slice(2));
    addAll(stem, stem.lead, 'entier', 'article-detache');
    if (stem.lead || FUSED_AFTER.has(letters[2])) addAll(stem, false, 'entier', 'article-fondu', ['l']);
    if (SUN_LETTERS.has(letters[2])) addAll(stem, true, 'entier', 'article-assimile');
  }

  // Typed particles glued by the clerk: بن علي -> Benali ; عبد القادر -> Abdelkader ; بو زيد -> Bouzid
  const run = [];
  for (let k = before.length - 1; k >= 0 && run.length < 2 && GLUE[before[k]] !== undefined; k--) run.unshift(before[k]);
  if (run.length > 0) {
    const stemNoLead = { ...stem };
    const chains = [];
    const last = run[run.length - 1];
    for (const g of GLUE[last]) {
      chains.push({ prefix: g, label: last });
      if (article) chains.push({ prefix: { lead: g.lead, cons: g.cons.concat('l') }, label: `${last}+el` });
    }
    if (run.length === 2) {
      for (const g0 of GLUE[run[0]]) {
        for (const g1 of GLUE[last]) {
          chains.push({ prefix: { lead: g0.lead, cons: g0.cons.concat(g1.cons) }, label: run.join('+') });
        }
      }
    }
    for (const ch of chains) addAll(stemNoLead, false, 'colle', `colle:${ch.label}`, [], ch.prefix);
  }
  return out;
}

/**
 * @typedef {Object} ArabicItem
 * @property {'particule'|'mot'} type
 * @property {string} saisie      the Arabic word as typed
 * @property {string} [particule] canonical particle (type 'particule')
 * @property {ArabicCandidate[]} [candidats] (type 'mot')
 */

/**
 * Read an Arabic text as a sequence of particles and name words.
 * @param {string} text
 * @returns {ArabicItem[]}
 */
export function analyzeArabic(text) {
  const items = [];
  let run = [];
  for (const word of arabicWords(text)) {
    const p = arabicParticle(word);
    if (p !== null) {
      items.push({ type: 'particule', saisie: word, particule: p });
      run.push(p);
      continue;
    }
    items.push({ type: 'mot', saisie: word, candidats: arabicCandidates(word, run) });
    run = [];
  }
  return items;
}

const LONG_CLASS = { a: 'ae', u: 'uo', i: 'ie' };

/**
 * Do the long vowels typed in Arabic appear in a French spelling that has the same skeleton?
 * Used only to order results: محمود (long u) agrees with "Mahmoud", not with "Mohamed".
 * @param {ArabicCandidate} cand
 * @param {string} cle folded French word (normaliser.js#fold)
 * @returns {boolean|null} null when nothing can be compared
 */
export function longVowelsAgree(cand, cle) {
  const sk = skeleton(cle);
  if (sk.consonants.length !== cand.cons.length) return null;
  let checked = false;
  for (let i = 0; i < cand.longs.length; i++) {
    for (const cls of cand.longs[i]) {
      checked = true;
      const written = sk.vowels[i + 1];
      const wanted = LONG_CLASS[cls];
      let found = false;
      for (const v of written) if (wanted.includes(v)) found = true;
      if (!found) return false;
    }
  }
  return checked ? true : null;
}
