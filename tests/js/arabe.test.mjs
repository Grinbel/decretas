import { test } from 'node:test';
import assert from 'node:assert/strict';

import { hasArabic, arabicWords, arabicParticle, arabicCandidates, analyzeArabic, longVowelsAgree } from '../../site/js/recherche/arabe.js';
import { keysOfWord } from '../../site/js/recherche/normaliser.js';
import { search } from '../../site/js/recherche/chercher.js';
import { suggestVariants } from '../../site/js/recherche/suggestions.js';
import { indexOf, classes } from './aide.mjs';

/** Last name word of an Arabic text, with its candidate skeletons. */
const word = (text) => analyzeArabic(text).filter((it) => it.type === 'mot').pop();
const candidateFor = (arabic, french) => word(arabic).candidats.find((c) => c.key === keysOfWord(french).k2);

// Common given names and usual family-name shapes: Arabic spelling -> French spellings a clerk
// used. Each French spelling must be reachable from the Arabic one.
const NAMES = [
  ['محمد', ['Mohamed', 'Mohammed', "M'hamed"]],
  ['أحمد', ['Ahmed']],
  ['احمد', ['Ahmed']],
  ['علي', ['Ali']],
  ['عمر', ['Omar', 'Aomar', 'Amor']],
  ['عمار', ['Amar', 'Ammar']],
  ['بلقاسم', ['Belkacem', 'Belgacem', 'Belkassem']],
  ['قاسم', ['Kacem', 'Kassem']],
  ['شعبان', ['Chabane', 'Chaabane', 'Châbane']],
  ['عيسى', ['Aïssa', 'Issa']],
  ['موسى', ['Moussa']],
  ['يوسف', ['Youcef', 'Youssef']],
  ['إبراهيم', ['Brahim', 'Ibrahim']],
  ['ابراهيم', ['Brahim', 'Ibrahim']],
  ['إسماعيل', ['Smaïl', 'Ismaïl']],
  ['مصطفى', ['Mustapha', 'Mostefa']],
  ['سليمان', ['Slimane', 'Sliman']],
  ['حسين', ['Hocine', 'Hussein']],
  ['حسن', ['Hassen', 'Hassan']],
  ['سعيد', ['Saïd']],
  ['مسعود', ['Messaoud']],
  ['صالح', ['Salah', 'Saleh']],
  ['رابح', ['Rabah']],
  ['الطاهر', ['Tahar', 'Taher']],
  ['العربي', ['Larbi', 'Arbi']],
  ['الأخضر', ['Lakhdar', 'Lakdar']],
  ['الحسن', ['Lahcen', 'Hassen']],
  ['الهادي', ['Hadi']],
  ['بلهادي', ['Belhadi']],
  ['بلحاج', ['Belhadj']],
  ['قدور', ['Kaddour']],
  ['عبدالقادر', ['Abdelkader']],
  ['جيلالي', ['Djilali']],
  ['ميلود', ['Miloud']],
  ['مختار', ['Mokhtar', 'Moktar']],
  ['بشير', ['Bachir']],
  ['رمضان', ['Ramdane']],
  ['عثمان', ['Othmane', 'Athmane']],
  ['مبارك', ['Mebarek', "M'barek"]],
  ['بوزيد', ['Bouzid']],
  ['فاطمة', ['Fatma', 'Fatima', 'Fathma']],
  ['عائشة', ['Aïcha']],
  ['خديجة', ['Khedidja', 'Khadidja']],
  ['زهرة', ['Zohra']],
  ['يمينة', ['Yamina']],
  ['حمراوي', ['Hamraoui']],
  ['الزمري', ['Zemri', 'Ezzemri']],
  ['الصغير', ['Seghir', 'Sghir']],
  ['شريف', ['Cherif']],
  ['يحيى', ['Yahia']],
];
for (const [arabic, french] of NAMES) {
  test(`Arabic ${arabic} reaches ${french.join(', ')}`, () => {
    for (const f of french) {
      assert.ok(candidateFor(arabic, f), `${arabic} should give the skeleton of ${f} (${keysOfWord(f).k2}); got ${word(arabic).candidats.map((c) => c.key)}`);
    }
  });
}

test('at least 25 distinct names are covered by the table above', () => {
  assert.ok(new Set(NAMES.map(([a]) => a)).size >= 25);
});

test('Arabic particles are recognised and never become terms', () => {
  assert.equal(hasArabic('بلقاسم'), true);
  assert.equal(hasArabic('Belkacem'), false);
  assert.equal(arabicParticle('بن'), 'ben');
  assert.equal(arabicParticle('ابن'), 'ben');
  assert.equal(arabicParticle('إبن'), 'ben');
  assert.equal(arabicParticle('بنت'), 'bent');
  assert.equal(arabicParticle('ولد'), 'ould');
  assert.equal(arabicParticle('بو'), 'bou');
  assert.equal(arabicParticle('عبد'), 'abd');
  assert.equal(arabicParticle('ال'), 'el');
  assert.equal(arabicParticle('الحاج'), 'hadj');
  assert.equal(arabicParticle('بلقاسم'), null);
  const items = analyzeArabic('بلقاسم بن شعبان');
  assert.deepEqual(items.map((it) => it.type), ['mot', 'particule', 'mot']);
});

test('vowel signs and tatweel are ignored', () => {
  assert.deepEqual(arabicWords('مُحَمَّد'), ['محمد']);
  assert.deepEqual(arabicWords('محـــمد'), ['محمد']);
});

test('typed particles are also tried glued, as a clerk may have written them', () => {
  assert.ok(candidateFor('بن علي', 'Benali'));
  assert.ok(candidateFor('عبد القادر', 'Abdelkader'));
  assert.ok(candidateFor('عبد الرحمان', 'Abderrahmane'));
  assert.ok(candidateFor('عبد الله', 'Abdallah'));
  assert.ok(candidateFor('بو زيد', 'Bouzid'));
  assert.ok(candidateFor('أبو القاسم', 'Belkacem'));
  assert.equal(candidateFor('بن علي', 'Benali').genre, 'colle');
});

test('a first ي is a consonant: يمينة is never read as Amina', () => {
  assert.equal(candidateFor('يمينة', 'Amina'), undefined);
  assert.equal(arabicCandidates('أحمد').some((c) => c.key === keysOfWord('Hamed').k2), false, 'Ahmed does not become Hamed');
});

test('long vowels typed in Arabic are compared with the French spelling', () => {
  const mahmoud = word('محمود').candidats[0];
  assert.equal(longVowelsAgree(mahmoud, 'mahmoud'), true);
  assert.equal(longVowelsAgree(mahmoud, 'mohamed'), false);
  const mohamed = word('محمد').candidats[0];
  assert.equal(longVowelsAgree(mohamed, 'mohamed'), null, 'no long vowel typed: nothing to compare');
  const said = word('سعيد').candidats[0];
  assert.equal(longVowelsAgree(said, 'said'), true);
  assert.equal(longVowelsAgree(said, 'saad'), false);
});

const INDEX = indexOf([
  ['Testaoui, Belkacem ben Chabane', 1876],
  ['TESTAOUI, Belgacem ben Chaabane', 1879],
  ['Bel Kaçem ben Châbane Exemplaoui', null, 'bogga'],
  ['Fictifi, Mahmoud ben Saad', 1850],
  ['Fictifi, Mohamed ben Saïd', 1851],
  ['Exemplaoui, Abdelkader ben Ali', 1860],
  ['Benali, Larbi', 1861],
]);

test('search in Arabic: every result is approximate and says so', () => {
  const { correspondances, bilan } = search(INDEX, 'بلقاسم بن شعبان');
  assert.deepEqual(correspondances.map((r) => r.nom), [
    'Testaoui, Belkacem ben Chabane', 'TESTAOUI, Belgacem ben Chaabane', 'Bel Kaçem ben Châbane Exemplaoui',
  ]);
  for (const r of correspondances) {
    assert.equal(r.classe, 'graphie-approchante');
    for (const t of r.termes) {
      assert.equal(t.arabe, true);
      assert.equal(t.niveau, 'k2');
      assert.equal(t.exact, false);
    }
  }
  assert.deepEqual(bilan.particulesIgnorees, [{ saisie: 'بن', particule: 'ben' }]);
  assert.equal(bilan.termes[0].variantes[0].ecriture, 'arabe');
  assert.ok(bilan.termes[0].variantes[0].squelettes.some((s) => s.cle === 'blksm'));
  assert.equal(bilan.comptes.parClasse.correspondance, 0);
});

test('search in Arabic: spellings whose long vowels agree come first', () => {
  const mahmoud = search(INDEX, 'محمود').correspondances.map((r) => r.nom);
  assert.deepEqual(mahmoud, ['Fictifi, Mahmoud ben Saad', 'Fictifi, Mohamed ben Saïd']);
  const said = search(INDEX, 'سعيد').correspondances;
  assert.deepEqual(said.map((r) => r.nom), ['Fictifi, Mohamed ben Saïd', 'Fictifi, Mahmoud ben Saad']);
  assert.equal(said[0].termes[0].voyellesLongues, true);
  assert.equal(said[1].termes[0].voyellesLongues, false);
});

test('search in Arabic: glued and split forms', () => {
  assert.deepEqual(classes(INDEX, 'عبد القادر')['graphie-approchante'], ['Exemplaoui, Abdelkader ben Ali']);
  assert.deepEqual(classes(INDEX, 'عبدالقادر')['graphie-approchante'], ['Exemplaoui, Abdelkader ben Ali']);
  assert.deepEqual(classes(INDEX, 'بن علي العربي')['graphie-approchante'], ['Benali, Larbi']);
});

test('search in Arabic: no partial correspondence (it would stack two approximations)', () => {
  const c = classes(INDEX, 'بلقاسم بن شعبان الزمري');
  assert.deepEqual(c, { correspondance: [], 'graphie-approchante': [], partielle: [] });
});

test('mixed input: Latin and Arabic terms in one query', () => {
  const { correspondances } = search(INDEX, 'Testaoui بلقاسم');
  assert.deepEqual(correspondances.map((r) => r.nom), ['Testaoui, Belkacem ben Chabane', 'TESTAOUI, Belgacem ben Chaabane']);
  assert.equal(correspondances[0].classe, 'graphie-approchante');
  assert.equal(correspondances[0].termes[0].niveau, 'k0');
  assert.equal(correspondances[0].termes[1].arabe, true);
});

test('suggestions for an Arabic term list the French spellings present, concordant first', () => {
  const s = suggestVariants(INDEX, 'محمود');
  assert.equal(s.ecriture, 'arabe');
  assert.deepEqual(s.squelette.map((e) => e.graphie), ['Mahmoud', 'Mohamed']);
  assert.equal(s.squelette[0].voyellesLongues, true);
});
