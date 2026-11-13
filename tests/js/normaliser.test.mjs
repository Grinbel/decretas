import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  fold, tokenize, k1, k2, keysOfWord, skeleton, isParticle, canonicalParticle, detachedStems, nameForms,
  KIND, KIND_NAMES, K2_MIN_LETTERS, K2_MIN_KEY,
} from '../../site/js/recherche/normaliser.js';

const key = (word) => keysOfWord(word);
const forms = (name, options) => nameForms(tokenize(name, options), options)
  .map((f) => `${KIND_NAMES[f.kind]}:${f.cle}${f.particle ? '*' : ''}`);

test('fold: case, accents and special letters', () => {
  assert.equal(fold('Châbane'), 'chabane');
  assert.equal(fold('NAÏT'), 'nait');
  assert.equal(fold('Kaçem'), 'kaçem', 'the cedilla survives folding: it changes the consonant');
  assert.equal(fold('Œuvre'), 'oeuvre');
  assert.equal(fold(null), '');
});

test('tokenize: separators, inner apostrophes, raw spelling kept', () => {
  const t = tokenize("TESTAOUI, M'Hamed ben Abd-el-Kader (dit Kaçem)");
  assert.deepEqual(t.map((x) => x.k0), ['testaoui', 'mhamed', 'ben', 'abd', 'el', 'kader', 'dit', 'kacem']);
  assert.deepEqual(t.map((x) => x.raw), ['TESTAOUI', "M'Hamed", 'ben', 'Abd', 'el', 'Kader', 'dit', 'Kaçem']);
  assert.equal(t[2].lower, true);
  assert.equal(t[0].lower, false);
  assert.deepEqual(tokenize('N’Aït Exemple').map((x) => x.k0), ['nait', 'exemple'], 'typographic apostrophe');
  assert.deepEqual(tokenize('Testaoui 1876, n° 12').map((x) => x.k0), ['testaoui', 'n'], 'digits are not words');
  assert.deepEqual(tokenize('').length, 0);
  assert.deepEqual(tokenize('بلقاسم').length, 0, 'Arabic script is not handled by the Latin tokenizer');
});

test('tokenize: OCR noise inside a word is ignored only for printed sources', () => {
  assert.deepEqual(tokenize('Moh:mmed ben Ali').map((x) => x.k0), ['moh', 'mmed', 'ben', 'ali']);
  assert.deepEqual(tokenize('Moh:mmed ben Ali', { ocr: true }).map((x) => x.k0), ['mohmmed', 'ben', 'ali']);
});

// ---------------------------------------------------------------------------------------------
// k1: spellings that MUST be the same word
// ---------------------------------------------------------------------------------------------
const K1_CLASSES = [
  ['Mohamed', 'Mohammed', 'MOHAMED'],
  ['Kacem', 'Kassem', 'Kaçem', 'Cacem', 'Kasem'],
  ['Belkacem', 'Belkassem', 'Belcacem', 'Belkaçem'],
  ['Chabane', 'Chaabane', 'Châbane', 'Châabane', 'Chaban'],
  ['Youcef', 'Youssef', 'Yousef', 'Yussef'],
  ['Fatma', 'Fatmah'],
  ['Abdallah', 'Abdalah', 'Abdalla'],
  ['Tayeb', 'Taieb', 'Taïeb'],
  ['Slimane', 'Sliman'],
  ['Kaci', 'Kassi'],
  ['Mustapha', 'Mustafa'],
  ['Yahia', 'Yahya'],
  ['Djilali', 'Djillali', 'Djilalli'],
  ['Kaddour', 'Cadour', 'Kadour'],
  ['Hassen', 'Hacene', 'Hacène', 'Hacen'],
  ['Ouahab', 'Wahab'],
  ['Cherif', 'Chérif', 'Scherif', 'Shérif'],
  ['Saadi', 'Sadi'],
  ['Hammou', 'Hamou'],
  ['Boudjema', 'Boudjemaa'],
  ['Mekki', 'Meki'],
  ['Abderrahmane', 'Abderrahman', 'Abderahman'],
  ['Eddine', 'Eddin'],
  ['Mhamed', "M'hamed", "M'Hammed", 'M’hamed'],
  ['Salah', 'Sala'],
  ['Ali', 'Aly'],
  ['Qasim', 'Kasim', 'Cassim'],
];
for (const group of K1_CLASSES) {
  test(`k1 identical: ${group.join(' = ')}`, () => {
    const keys = group.map((w) => key(w).k1);
    assert.deepEqual(keys, keys.map(() => keys[0]));
  });
}

// ---------------------------------------------------------------------------------------------
// k1: different names that must NOT be merged by the "safe" level
// ---------------------------------------------------------------------------------------------
const K1_DISTINCT = [
  ['Belhadi', 'Belhadj'], ['Mohamed', 'Mahmoud'], ['Mohamed', 'Mohand'], ['Mohamed', "M'hamed"],
  ['Amar', 'Omar'], ['Saïd', 'Saad'], ['Slimane', 'Salomon'], ['Hocine', 'Hassen'], ['Kacem', 'Kaci'],
  ['Ali', 'Allal'], ['Larbi', 'Arbi'], ['Louis', 'Louise'], ['Salah', 'Saleh'], ['Belkacem', 'Belgacem'],
  ['Brahim', 'Ibrahim'], ['Ahmed', 'Hamed'], ['Fatma', 'Fatima'], ['Chabane', 'Chebana'], ['Kader', 'Kaddour'],
  ['Zemri', 'Zemmouri'], ['Mahmoud', 'Mahmoudi'], ['Mostefa', 'Mostefaoui'], ['Khaled', 'Kaled'], ['Ghali', 'Kali'],
  ['Saïd', 'Saïdi'], ['Ahmed', 'Ahmet'], ['Zohra', 'Zahra'], ['Rabah', 'Rabia'],
];
for (const [a, b] of K1_DISTINCT) {
  test(`k1 distinct: ${a} != ${b}`, () => {
    assert.notEqual(key(a).k1, key(b).k1);
    assert.notEqual(key(a).k0, key(b).k0);
  });
}

// ---------------------------------------------------------------------------------------------
// k2: the approximate level
// ---------------------------------------------------------------------------------------------
const K2_CLASSES = [
  ['Belkacem', 'Belgacem', 'Belkassem', 'Belguecem', 'Belqacem', 'Belkecem'],
  ['Mohamed', 'Mohammed', "M'hamed", 'Mehamed', 'Mahomed', 'Mhammed'],
  ['Mustapha', 'Mostefa', 'Mustafa', 'Mostapha'],
  ['Hocine', 'Hussein', 'Houcine', 'Hossine'],
  ['Khedidja', 'Khadidja', 'Khadija', 'Kedidja'],
  ['Lakhdar', 'Lakdar', 'Lakhedar'],
  ['Seghir', 'Sghir', 'Seghier'],
  ['Salah', 'Saleh', 'Sallah'],
  ['Omar', 'Aomar', 'Amor', 'Oumar'],
  ['Othmane', 'Athmane', 'Atmane', 'Otman'],
  ['Guesmi', 'Kesmi', 'Guessmi'],
  ['Zemri', 'Semri', 'Zemeri'],
  ['Fatma', 'Fathma', 'Fatima'],
  ['Tahar', 'Taher'],
  ['Ouali', 'Wali'],
  ['Arezki', 'Areski'],
  ['Mokhtar', 'Moktar'],
  ['Brahim', 'Braham', 'Brahem', 'Brahime'],
  ['Youcef', 'Ioussef', 'Yousef'],
  ['Messaoud', 'Mesaoud', 'Messaoud'],
  ['Hadj', 'Haj'],
  ['Djemaa', 'Djema', 'Jemaa'],
];
for (const group of K2_CLASSES) {
  test(`k2 identical: ${group.join(' = ')}`, () => {
    const keys = group.map((w) => key(w).k2);
    assert.deepEqual(keys, keys.map(() => keys[0]));
  });
}

const K2_DISTINCT = [
  ['Mahmoud', 'Mahmoudi'], ['Mostefa', 'Mostefaoui'], ['Belhadi', 'Belhadj'], ['Ghali', 'Kali'], ['Ghali', 'Khali'],
  ['Mohamed', 'Mohand'], ['Fatma', 'Fatmi'], ['Zemri', 'Zemmour'], ['Seghir', 'Sekkir'], ['Ahmed', 'Hamed'],
  ['Brahim', 'Ibrahim'], ['Larbi', 'Arbi'], ['Youcef', 'Oucef'], ['Kacem', 'Kacemi'], ['Ahmed', 'Ahmet'],
];
for (const [a, b] of K2_DISTINCT) {
  test(`k2 distinct: ${a} != ${b}`, () => {
    assert.notEqual(key(a).k2, key(b).k2);
  });
}

// Documented collisions: if one of these stops colliding, docs/moteur-de-recherche.md must change.
const K2_KNOWN_COLLISIONS = [
  ['Mohamed', 'Mahmoud'], ['Slimane', 'Salomon'], ['Hocine', 'Hassan'], ['Kacem', 'Cosme'],
  ['Kader', 'Kaddour'], ['Amar', 'Omar'], ['Zemri', 'Zemmouri'], ['Benali', 'Bonelli'],
];
for (const [a, b] of K2_KNOWN_COLLISIONS) {
  test(`k2 known collision (documented): ${a} = ${b}`, () => {
    assert.equal(key(a).k2, key(b).k2);
    assert.notEqual(key(a).k1, key(b).k1);
  });
}

test('k2 guard: short words never reach the approximate level', () => {
  assert.equal(K2_MIN_LETTERS, 4);
  assert.equal(K2_MIN_KEY, 3);
  for (const w of ['Ali', 'Saïd', 'Hadj', 'Aïch', 'Laïd', 'Bou', 'Saad']) {
    assert.equal(key(w).k2ok, false, w);
  }
  for (const w of ['Belkacem', 'Omar', 'Salah', 'Chabane', 'Seghir', 'Aïssa']) {
    assert.equal(key(w).k2ok, true, w);
  }
});

test('skeleton: examples quoted in the documentation', () => {
  assert.equal(k2('belkacem'), 'blksm');
  assert.equal(k2('mohamed'), 'mhmd');
  assert.equal(k2('chabane'), 'chbn');
  assert.equal(k2('belhadi'), 'blhdi');
  assert.equal(k2('belhadj'), 'blhj');
  assert.equal(k2('mostefaoui'), 'mstfwi');
  assert.equal(k2('seghir'), 'sgr');
  assert.equal(k2('youcef'), 'ysf');
  assert.equal(k2('ouali'), 'wli');
  assert.equal(k2('aomar'), 'amr');
  assert.equal(k1('chaabane'), 'chaban');
  assert.equal(k1('kaçem'), 'kasem');
  assert.equal(k1('youcef'), 'iusef');
  assert.deepEqual(skeleton('belkacem').consonants, ['b', 'l', 'k', 's', 'm']);
  assert.deepEqual(skeleton('chabane').consonants, ['ch', 'b', 'n']);
});

// ---------------------------------------------------------------------------------------------
// Particles and glued / split forms
// ---------------------------------------------------------------------------------------------
test('particles are recognised, with their canonical spelling', () => {
  for (const p of ['ben', 'bent', 'bint', 'ould', 'oulad', 'bou', 'bel', 'el', 'al', 'abd', 'ou', 'ait', 'nait',
    'sidi', 'si', 'hadj', 'dit', 'nee', 'veuve', 'epouse', 'b', 'de']) {
    assert.equal(isParticle(p), true, p);
  }
  for (const w of ['ali', 'belhadj', 'benali', 'chabane', 'bon', 'cheikh']) assert.equal(isParticle(w), false, w);
  assert.equal(canonicalParticle('b'), 'ben');
  assert.equal(canonicalParticle('bint'), 'bent');
  assert.equal(canonicalParticle('vve'), 'veuve');
  assert.equal(isParticle(tokenize('Aït')[0].k0), true);
  assert.equal(isParticle(tokenize('Née')[0].k0), true);
  assert.equal(isParticle(tokenize('épouse')[0].k0), true);
});

test('detachedStems: a glued prefix comes off, but never down to a particle or a short word', () => {
  const stems = (w) => detachedStems(w).map((s) => `${s.prefix}+${s.stem}`);
  assert.deepEqual(stems('benchabane'), ['ben+chabane']);
  assert.deepEqual(stems('belhadi'), ['bel+hadi']);
  assert.deepEqual(stems('ezzemri'), ['ez+zemri']);
  assert.deepEqual(stems('ennacer'), ['en+nacer']);
  assert.deepEqual(stems('abdelkader'), ['abd+elkader', 'abdel+kader']);
  assert.deepEqual(stems('abderrahmane'), ['abd+errahmane', 'abder+rahmane']);
  assert.deepEqual(stems('belhadj'), [], '"Belhadj" must not become the particle "hadj"');
  assert.deepEqual(stems('elhadj'), []);
  assert.deepEqual(stems('bensidi'), []);
  assert.deepEqual(stems('benali'), [], 'three letters are not enough');
  assert.deepEqual(stems('bouzid'), []);
  assert.deepEqual(stems('albert'), [], '"al" is not detached');
  assert.deepEqual(stems('chabane'), []);
});

test('nameForms: words, glued forms and stems of a written name', () => {
  assert.deepEqual(forms('Testaoui, Belkacem ben Chabane'), [
    'mot:testaoui', 'mot:belkacem', 'decolle:kacem', 'mot:ben*', 'mot:chabane', 'colle:benchabane',
  ]);
  assert.deepEqual(forms('Bel Kaçem ben bel Hadj'), [
    'mot:bel*', 'mot:kaçem', 'colle:belkaçem', 'mot:ben*', 'mot:bel*', 'mot:hadj*', 'colle:belhadj', 'colle:benbelhadj',
  ]);
  assert.deepEqual(forms('Abd-el-Kader'), ['mot:abd*', 'mot:el*', 'mot:kader', 'colle:elkader', 'colle:abdelkader']);
  assert.deepEqual(forms('Ezzemri'), ['mot:ezzemri', 'decolle:zemri']);
  assert.deepEqual(forms("D'Exemplo"), ['mot:dexemplo', 'decolle:exemplo']);
  assert.deepEqual(forms('A. Testaoui'), ['mot:testaoui'], 'an initial is not searchable');
});

test('nameForms: "Hadj el X" is not chained through the title', () => {
  const f = forms('Hadj el Arbi');
  assert.ok(f.includes('colle:elarbi'));
  assert.ok(!f.includes('colle:hadjelarbi'));
});

test('nameForms: OCR readings of "ben" in a printed source', () => {
  const printed = forms('Ali bon Slimane ten Amar', { ocr: true });
  assert.deepEqual(printed, ['mot:ali', 'mot:slimane', 'colle:benslimane', 'mot:amar', 'colle:benamar']);
  const clean = forms('Ali bon Slimane', { ocr: false });
  assert.ok(clean.includes('mot:bon'), 'outside printed sources "bon" is an ordinary word');
  const surname = forms('Bon, Jean', { ocr: true });
  assert.deepEqual(surname, ['mot:bon', 'mot:jean'], 'a capitalised first word "Bon" stays a name');
  const last = forms('Ali ban', { ocr: true });
  assert.ok(last.includes('mot:ban'), 'a last word is not a particle');
});

test('nameForms: "ben" glued to the END of a word (Aliben Fictifi)', () => {
  const f = forms('Aliben Fictifi');
  assert.ok(f.includes('mot:aliben'));
  assert.ok(f.includes('decolle:ali'));
  assert.ok(f.includes('colle:benfictifi'));
  assert.ok(!forms('Ruben Testaoui').includes('decolle:ru'));
  const hyphens = forms('Rabah-ben-Mohamedben-Exemple');
  assert.ok(hyphens.includes('mot:rabah') && hyphens.includes('decolle:mohamed') && hyphens.includes('colle:benexemple'));
});

test('KIND constants', () => {
  assert.deepEqual([KIND.WORD, KIND.GLUED, KIND.STEM], [0, 1, 2]);
});
