/**
 * Regression tests for the defects found by the review of 2026-11-11. One test per defect; the
 * comment above each says what went wrong. Every name is invented (Testaoui, Exemplaoui,
 * Fictifi) or a very common given name.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { occurrencesFromColumns, buildIndex } from '../../site/js/recherche/index.js';
import { search, parseQuery } from '../../site/js/recherche/chercher.js';
import { fold, tokenize, nameForms, fusedArticleForm, KIND_NAMES } from '../../site/js/recherche/normaliser.js';
import { analyzeArabic, arabicWords } from '../../site/js/recherche/arabe.js';
import { keysOfWord } from '../../site/js/recherche/normaliser.js';
import { suggestVariants } from '../../site/js/recherche/suggestions.js';
import { createSession } from '../../site/js/recherche/session.js';
import { indexOf, classes, classOf } from './aide.mjs';

const A = 'correspondance';
const B = 'graphie-approchante';
const C = 'partielle';

// ---------------------------------------------------------------------------------------------
// Data adapter
// ---------------------------------------------------------------------------------------------

// The printed-bulletin file names its birth-year column "naissance" (an integer). It was not
// detected: every printed entry was labelled "année de naissance inconnue" and escaped the filter.
test('adapter: the birth-year column of bogga-entrees.json ("naissance") is detected', () => {
  const bogga = {
    champs: ['id', 'volume', 'decret', 'nom', 'texte', 'marqueurs', 'nationalite', 'naissance', 'residence', 'page', 'feuille', 'drapeaux'],
    lignes: [
      [0, 3, 12, 'Testaoui (Belkacem ben Chabane)', 'Testaoui (Belkacem ben Chabane), cultivateur, né en 1846 à Exempleville.', 1, null, 1846, 'Exempleville', 61, 116, 0],
      [1, 3, 12, 'Testaoui (Belkacem ben Chabane)', 'Testaoui (Belkacem ben Chabane), demeurant à Exempleville.', 1, null, null, 'Exempleville', 61, 116, 0],
      [2, 3, 12, 'Testaoui (Belkacem ben Chabane)', 'Testaoui (Belkacem ben Chabane), né en 1820.', 1, null, 1820, null, 62, 117, 0],
    ],
  };
  const { occurrences, colonnes } = occurrencesFromColumns(bogga, { groupe: 'bogga', ocr: true });
  assert.deepEqual(colonnes, { nom: ['nom'], id: 'id', annee: 'naissance' });
  assert.deepEqual(occurrences.map((o) => o.anneeNaissance), [1846, null, 1820]);
  const { correspondances, bilan } = search(buildIndex(occurrences), { texte: 'Testaoui Belkacem Chabane', annee: 1846 });
  assert.deepEqual(correspondances.map((r) => [r.id, r.annee.ecart, r.annee.inconnue]), [[0, 0, false], [1, null, true]]);
  assert.equal(bilan.comptes.ecarteesParAnnee.correspondance, 1);
  assert.equal(bilan.comptes.sansAnneeDeNaissance, 1);
});

test('adapter: "an" wins over a free-text birth column, and free text alone gives no year', () => {
  const an = { champs: ['id', 'nom', 'an', 'naiss'], lignes: [[0, 'Testaoui, Ali', 1882, '1 janvier 1882 (Exempleville)']] };
  assert.equal(occurrencesFromColumns(an, { groupe: 'an' }).colonnes.annee, 'an');
  const text = { champs: ['id', 'nom', 'naissance'], lignes: [[0, 'Testaoui, Ali', 'le 1er mai 1843'], [1, 'Testaoui, Amar', '1843-05-01']] };
  assert.deepEqual(occurrencesFromColumns(text, { groupe: 'x' }).occurrences.map((o) => o.anneeNaissance), [null, 1843]);
});

// ---------------------------------------------------------------------------------------------
// Unticking a spelling
// ---------------------------------------------------------------------------------------------

// Unticking the bare word "Kacem" (proposed "avec préfixe" for Belkacem) also removed the
// notices that write "Bel Kacem" in two words: a silent loss of true correspondences.
test('unticking the bare word does not remove the name written in two words', () => {
  const index = indexOf(['Testaoui, Bel Kacem', 'Testaoui, Kacem', 'Testaoui, Belkacem', 'Benkacem, Testaoui']);
  const before = classes(index, 'Belkacem Testaoui');
  assert.deepEqual(before[A], ['Testaoui, Bel Kacem', 'Testaoui, Belkacem']);
  assert.deepEqual(before[B], ['Testaoui, Kacem']);
  const after = classes(index, 'Belkacem|-Kacem Testaoui');
  assert.deepEqual(after[A], ['Testaoui, Bel Kacem', 'Testaoui, Belkacem'], '"Bel Kacem" is still a full correspondence');
  assert.deepEqual(after[B], []);
  assert.ok(after[C].includes('Testaoui, Kacem'), 'the bare Kacem only remains as a partial correspondence');
  // A written word unticked is still refused when reached through its stem.
  const stem = classes(index, { termes: [{ variantes: ['Kacem'], exclues: ['benkacem'] }, 'Testaoui'] });
  assert.ok(!stem[B].includes('Benkacem, Testaoui'));
  assert.ok(stem[A].includes('Testaoui, Kacem'));
});

// ---------------------------------------------------------------------------------------------
// Article fused with the name
// ---------------------------------------------------------------------------------------------

// "Larbi" and "El Arbi" (Lakhdar / El Akhdar, Laïd / El Aïd) were never reconciled: a notice
// "… ben Hadj el Arbi" was only a partial correspondence for "Larbi".
const FUSED_PAIRS = [
  ['Testaoui, Mohamed ben el Arbi', 'Mohamed Larbi Testaoui', A],
  ['Testaoui, Larbi', 'El Arbi Testaoui', A],
  ['Testaoui, El Akhdar', 'Lakhdar Testaoui', A],
  ['Testaoui, El Aïd', 'Laïd Testaoui', A],
  ['Testaoui, Laïd', 'El Aïd Testaoui', A],
  ['Testaoui, El Houcine', 'Lhoucine Testaoui', A],
  ['Testaoui, El Houcine', 'Lhocine Testaoui', B], // fused, then skeleton
  ['Testaoui, Al Amine', 'Lamine Testaoui', A],
  // Not fused: another consonant than h, a title, a word glued in the source, a short word.
  ['Testaoui, El Kader', 'Lkader Testaoui', C],
  ['Testaoui, El Hadj Ahmed', 'Lhadj Ahmed Testaoui', C],
  ['Testaoui, Elisabeth', 'Lisabeth Testaoui', C],
  ['Testaoui, El Ou', 'Lou Testaoui', C],
];
for (const [name, query, expected] of FUSED_PAIRS) {
  test(`fused article: « ${name} » for query « ${query} » -> ${expected}`, () => {
    assert.equal(classOf(name, query), expected);
  });
}

test('fused article: the explanation names it and does not call the spelling exact', () => {
  assert.equal(fusedArticleForm('el', 'arbi'), 'larbi');
  assert.equal(fusedArticleForm('el', 'kader'), null);
  assert.equal(fusedArticleForm('ben', 'arbi'), null);
  const forms = nameForms(tokenize('Hadj el Arbi')).map((f) => `${KIND_NAMES[f.kind]}:${f.cle}${f.fused ? ':fondu' : ''}`);
  assert.ok(forms.includes('colle:elarbi') && forms.includes('colle:larbi:fondu'));

  const source = search(indexOf(['Testaoui, Ali ben el Arbi']), 'Larbi Ali Testaoui').correspondances[0];
  assert.deepEqual(
    [source.termes[0].ecrit, source.termes[0].soudure, source.termes[0].prefixe, source.termes[0].niveau, source.termes[0].exact],
    ['el Arbi', 'article-fondu', 'el', 'k0', false],
  );
  assert.equal(source.termesExacts, 2, 'Ali and Testaoui only');

  const typed = search(indexOf(['Testaoui, Ali ben Larbi']), 'El Arbi Ali Testaoui').correspondances[0];
  assert.deepEqual(
    [typed.termes[0].ecrit, typed.termes[0].soudure, typed.termes[0].prefixe, typed.termes[0].exact],
    ['Larbi', 'article-fondu', 'el', false],
  );
});

// "Sid Ahmed" and "Sidahmed" were not reconciled ("sid" was a particle that could not be glued).
test('"Sid Ahmed" and "Sidahmed" are the same name, both ways', () => {
  assert.equal(classOf('Testaoui, Sid Ahmed', 'Sidahmed Testaoui'), A);
  assert.equal(classOf('Testaoui, Sidahmed', 'Sid Ahmed Testaoui'), A);
});

// ---------------------------------------------------------------------------------------------
// Bilan
// ---------------------------------------------------------------------------------------------

// The same written word was listed twice for one term: once for itself, once as the carrier
// of a detached prefix ("Benchabane (1), Benchabane (1, avec préfixe)").
test('bilan: a written word is listed once per term', () => {
  const index = indexOf(['Benchabane, Ali', 'Testaoui, Chabane', 'Bouchabane, Ali']);
  const found = search(index, 'ben Chabane').bilan.graphiesTrouvees[0].graphies.map((g) => [g.graphie, g.soudure, g.occurrences]);
  assert.deepEqual(found, [['Chabane', null, 1], ['Benchabane', 'colle', 1], ['Bouchabane', 'prefixe-source', 1]]);
});

// The line of a detached prefix gave "forme: chabane": passing it in "exclues" unticked the
// exact spelling Chabane instead of the written word Benchabane.
test('bilan: every line says what to exclude to untick it, and that removes exactly that line', () => {
  const index = indexOf(['Benchabane, Ali', 'Testaoui, Chabane ben Ali', 'Bouchabane, Ali', 'Testaoui, Chaabane ben Ali']);
  const lines = search(index, 'Chabane Ali').bilan.graphiesTrouvees[0].graphies;
  assert.deepEqual(lines.map((g) => [g.graphie, g.soudure, g.exclure]), [
    ['Chabane', null, ['chabane']], ['Chaabane', null, ['chaabane']], ['Benchabane, Bouchabane', 'prefixe-source', ['benchabane', 'bouchabane']],
  ]);
  const without = (line) => classes(index, { termes: [{ variantes: ['Chabane'], exclues: line.exclure }, 'Ali'] });
  const noPrefix = without(lines[2]);
  assert.deepEqual(noPrefix[A], ['Testaoui, Chabane ben Ali', 'Testaoui, Chaabane ben Ali'], 'the exact spellings stay');
  assert.deepEqual(noPrefix[B], []);
  const noExact = without(lines[0]);
  assert.deepEqual(noExact[A], ['Testaoui, Chaabane ben Ali']);
  assert.deepEqual(noExact[B], ['Benchabane, Ali', 'Bouchabane, Ali'], 'the carriers of the prefix stay');
});

// A malformed structured query threw a TypeError instead of being ignored.
test('a malformed structured query never throws', () => {
  const index = indexOf(['Testaoui, Ali']);
  for (const bad of [{ termes: [null, 3, { variantes: 'x' }, { variantes: [null, 3, {}], exclues: 7 }] }, { termes: 'x' }, { texte: 42 }, 42, null]) {
    assert.doesNotThrow(() => search(index, bad), JSON.stringify(bad));
    assert.doesNotThrow(() => parseQuery(bad));
  }
  assert.doesNotThrow(() => suggestVariants(index, null));
});

// ---------------------------------------------------------------------------------------------
// Arabic script
// ---------------------------------------------------------------------------------------------
const word = (text) => analyzeArabic(text).filter((it) => it.type === 'mot').pop();
const reaches = (arabic, french) => word(arabic).candidats.some((c) => c.key === keysOfWord(french).k2);

// عبد القادر was also read "Lkader", whose skeleton is that of Lakhdar: every Lakhdar came back.
test('Arabic: the article is fused only before a vowel or an h', () => {
  assert.equal(reaches('عبد القادر', 'Lakhdar'), false);
  assert.equal(reaches('القادر', 'Lakhdar'), false);
  assert.equal(reaches('عبد القادر', 'Abdelkader'), true);
  assert.equal(reaches('العربي', 'Larbi'), true);
  assert.equal(reaches('الأخضر', 'Lakhdar'), true);
  assert.equal(reaches('الحسين', 'Lhocine'), true);
  assert.equal(reaches('الهادي', 'Lhadi'), true);
  const index = indexOf(['Testaoui, Lakhdar', 'Testaoui, Abdelkader']);
  assert.deepEqual(classes(index, 'عبد القادر')[B], ['Testaoui, Abdelkader']);
});

// عبدالرحمن typed as one word found nothing: French drops the l before r, s, n… (Abderrahmane).
const GLUED_ABD = [
  ['عبدالرحمن', 'Abderrahmane'], ['عبدالرحمان', 'Abderrahman'], ['عبدالسلام', 'Abdesselam'], ['عبدالنور', 'Abdennour'],
  ['عبدالرزاق', 'Abderrezak'], ['عبدالقادر', 'Abdelkader'], ['عبدالله', 'Abdallah'], ['عبدالعزيز', 'Abdelaziz'],
];
for (const [arabic, french] of GLUED_ABD) {
  test(`Arabic: ${arabic} typed as one word reaches ${french}`, () => {
    assert.ok(reaches(arabic, french), `${word(arabic).candidats.map((c) => c.key)} / ${keysOfWord(french).k2}`);
  });
}

// "X الدين" was read as two terms, which French almost always writes as ONE word (Noureddine).
const EDDINE = [
  ['نور الدين', 'Noureddine'], ['نورالدين', 'Nourredine'], ['عز الدين', 'Azzedine'], ['خير الدين', 'Kheireddine'],
  ['محي الدين', 'Mahieddine'], ['صلاح الدين', 'Salaheddine'], ['نصر الدين', 'Nasreddine'], ['بدر الدين', 'Badreddine'],
];
for (const [arabic, french] of EDDINE) {
  test(`Arabic: ${arabic} is one name, ${french}`, () => {
    assert.deepEqual(arabicWords(arabic).length, 1);
    assert.ok(reaches(arabic, french), `${word(arabic).candidats.map((c) => c.key)} / ${keysOfWord(french).k2}`);
    assert.equal(word(arabic).candidats[0].lecture, 'compose-eddine');
  });
}

test('Arabic: "X الدين" inside a free-text query is one term, and the particle rule still holds', () => {
  const q = parseQuery('نور الدين بن علي');
  assert.deepEqual(q.termes.map((t) => t.libelle), ['نور الدين', 'علي']);
  assert.deepEqual(q.particulesIgnorees.map((p) => p.particule), ['ben']);
  const index = indexOf(['Testaoui, Noureddine ben Ali', 'Testaoui, Nour ben Ali']);
  assert.deepEqual(classes(index, 'نور الدين بن علي')[B], ['Testaoui, Noureddine ben Ali']);
  assert.deepEqual(parseQuery('الدين').termes.map((t) => t.libelle), ['الدين'], 'alone, it is an ordinary word');
  assert.deepEqual(arabicWords('بن الدين'), ['بن', 'الدين'], 'never joined to a particle');
});

// يحي (the usual Algerian spelling of Yahia) and موسي found nothing; يدير did not find Idir.
test('Arabic: names in -a typed with a final ي, and Idir', () => {
  assert.ok(reaches('يحي', 'Yahia'));
  assert.ok(reaches('يحيى', 'Yahia'));
  assert.ok(reaches('موسي', 'Moussa'));
  assert.ok(reaches('مصطفي', 'Mustapha'));
  assert.ok(reaches('عيسي', 'Aïssa'));
  assert.ok(reaches('يدير', 'Idir'));
  assert.ok(reaches('يدير', 'Yidir'));
  assert.equal(reaches('علي', 'Alla'), false, 'the rule is a list of names, not a general reading of ي');
  assert.equal(reaches('يمينة', 'Amina'), false);
});

// ---------------------------------------------------------------------------------------------
// Robustness of the source text
// ---------------------------------------------------------------------------------------------

// Two rules depended on invisible characters typed raw in the source (combining marks, U+FEFF).
test('folding does not depend on how the accent is encoded', () => {
  assert.equal(fold('Kaçem'), 'kaçem', 'c + combining cedilla');
  assert.equal(fold('Kaçem'), 'kaçem', 'precomposed ç');
  assert.equal(fold('Châbane'), 'chabane');
  assert.equal(keysOfWord('Kaçem').k1, keysOfWord('Kassem').k1);
});

// ---------------------------------------------------------------------------------------------
// Worker session
// ---------------------------------------------------------------------------------------------

// With a compressed transfer the announced length counts compressed bytes: "recus" overtook
// "total" and a progress bar went past 100 %.
test('progress: no total when the transfer is compressed, or when there is no stream', async () => {
  const text = JSON.stringify({ champs: ['id', 'nom'], lignes: [[1, 'Testaoui, Ali ben Exemple'], [2, 'Exemplaoui, Aïcha']] });
  const bytes = new TextEncoder().encode(text);
  const serve = (headers, streamed) => async () => {
    if (!streamed) return { ok: true, status: 200, headers: new Map(headers), text: async () => text };
    const body = new ReadableStream({
      start(controller) {
        for (let i = 0; i < bytes.length; i += 30) controller.enqueue(bytes.slice(i, i + 30));
        controller.close();
      },
    });
    return { ok: true, status: 200, headers: new Map(headers), body };
  };
  const load = async (headers, streamed) => {
    const out = [];
    const s = createSession({ post: (m) => out.push(m), fetch: serve(headers, streamed) });
    await s.handle({ type: 'charger', fichiers: [{ url: 'data/x.json', groupe: 'an' }] });
    assert.equal(out[out.length - 1].type, 'pret');
    return out.filter((m) => m.type === 'progression' && m.etape === 'telechargement');
  };
  const gzip = await load([['content-length', '20'], ['content-encoding', 'gzip']], true);
  assert.ok(gzip.every((m) => m.total === null), 'compressed: the total is unknown');
  assert.equal(gzip[gzip.length - 1].recus, bytes.length);
  const plain = await load([['content-length', String(bytes.length)]], true);
  assert.equal(plain[plain.length - 1].total, bytes.length);
  assert.ok(plain.every((m) => m.total === null || m.recus <= m.total));
  const whole = await load([['content-length', String(bytes.length)]], false);
  assert.deepEqual([whole[whole.length - 1].recus, whole[whole.length - 1].total], [bytes.length, null], 'bytes, not characters');
});

// In a real browser a worker resolves a relative URL against its own script: the documented
// call ({url: 'data/an-personnes.json'}) asked for js/recherche/data/an-personnes.json — 404.
// (Seen in headless Chromium and Firefox; the Node stand-ins could not show it.)
test('worker session: relative data URLs are resolved against a base, never left to the worker script', async () => {
  const data = JSON.stringify({ champs: ['id', 'nom'], lignes: [[1, 'Testaoui, Ali']] });
  const asked = [];
  const fetchFile = async (url) => {
    asked.push(url);
    return { ok: true, status: 200, headers: new Map(), text: async () => data };
  };
  const out = [];
  const s = createSession({ post: (m) => out.push(m), fetch: fetchFile, base: 'https://exemple.invalid/decretas/' });
  await s.handle({ type: 'charger', fichiers: [{ url: 'data/an-personnes.json', groupe: 'an' }] });
  await s.handle({
    type: 'charger',
    base: 'https://exemple.invalid/autre/page.html',
    fichiers: [{ url: 'data/x.json', groupe: 'an' }, { url: 'https://exemple.invalid/absolu.json', groupe: 'bogga' }],
  });
  assert.deepEqual(asked, [
    'https://exemple.invalid/decretas/data/an-personnes.json',
    'https://exemple.invalid/autre/data/x.json',
    'https://exemple.invalid/absolu.json',
  ]);
  const ready = out.filter((m) => m.type === 'pret');
  assert.deepEqual(ready[0].fichiers.map((f) => f.url), ['data/an-personnes.json'], 'replies repeat the url as given');
  assert.ok(out.filter((m) => m.type === 'progression').every((m) => m.fichier === null || !m.fichier.includes('decretas/')));

  const bare = [];
  const none = createSession({ post: () => {}, fetch: async (url) => { bare.push(url); return { ok: true, status: 200, headers: new Map(), text: async () => data }; } });
  await none.handle({ type: 'charger', fichiers: [{ url: 'data/x.json', groupe: 'an' }] });
  assert.deepEqual(bare, ['data/x.json'], 'without a base the url is passed as it is');

  const bad = [];
  const broken = createSession({ post: (m) => bad.push(m), fetch: fetchFile, base: 'https://exemple.invalid/' });
  await broken.handle({ type: 'charger', fichiers: [{ groupe: 'an' }] });
  await broken.handle({ type: 'charger', fichiers: [null] });
  assert.deepEqual(bad.map((m) => [m.type, m.code]), [['erreur', 'chargement'], ['erreur', 'chargement']]);
  assert.match(bad[0].message, /sans adresse/);
});

test('worker.js: the default base is the site root, two levels above the script', async () => {
  const data = JSON.stringify({ champs: ['id', 'nom'], lignes: [[1, 'Testaoui, Ali']] });
  const asked = [];
  const posted = [];
  const previous = { self: globalThis.self, fetch: globalThis.fetch };
  globalThis.self = {
    location: { href: 'https://exemple.invalid/decretas/js/recherche/worker.js' },
    postMessage: (m) => posted.push(m),
    onmessage: null,
  };
  globalThis.fetch = async (url) => {
    asked.push(String(url));
    return { ok: true, status: 200, headers: new Map(), text: async () => data };
  };
  try {
    await import('../../site/js/recherche/worker.js?racine'); // the query string gives a fresh module instance
    globalThis.self.onmessage({ data: { type: 'charger', fichiers: [{ url: 'data/an-personnes.json', groupe: 'an' }] } });
    for (let i = 0; i < 200 && !posted.some((m) => m.type === 'pret' || m.type === 'erreur'); i++) await new Promise((r) => setTimeout(r, 5));
    assert.deepEqual(asked, ['https://exemple.invalid/decretas/data/an-personnes.json']);
    assert.equal(posted[posted.length - 1].type, 'pret');
  } finally {
    globalThis.self = previous.self;
    globalThis.fetch = previous.fetch;
  }
});

// Readings of "ben" and "ou" seen in the printed entries built on 2026-11-11 and not yet read
// as particles: "bea" (ben), "on" (ou).
test('printed sources: "bea" is read "ben" and "on" is read "ou", between two words only', () => {
  const printed = (name) => indexOf([[name, null, 'bogga']]);
  assert.equal(search(printed('Fictif bea Exemple'), 'Fictif Benexemple').correspondances[0]?.classe, A);
  assert.equal(search(printed('Saïd ben Mohamed on Exemple'), 'Saïd Mohamed Ouexemple').correspondances[0]?.classe, A);
  assert.equal(search(printed('Saïd ben Mohamed on Exemple'), 'On').correspondances.length, 0, 'the OCR particle is not a name');
  assert.equal(search(printed('On, Fictif'), 'On Fictif').correspondances.length, 1, 'a capitalised word stays a name');
  assert.equal(classOf('Saïd ben Mohamed on Exemple', 'Saïd Mohamed Ouexemple'), B, 'archival source: "on" is a word, the prefix is detached from the query');
  assert.equal(search(indexOf(['Saïd ben Mohamed on Exemple']), 'On').correspondances.length, 1, 'archival source: "on" is an ordinary word');
});

// The engine files end in ".js" and nothing said they were ES modules: Node only loaded them
// thanks to its syntax detection (on by default from 22.7 only). With detection switched off
// every import failed. site/js/recherche/package.json now says {"type": "module"}.
test('the engine loads as ES modules without relying on Node syntax detection', async () => {
  const { spawnSync } = await import('node:child_process');
  const { fileURLToPath } = await import('node:url');
  const { readFileSync } = await import('node:fs');
  const tool = fileURLToPath(new URL('../../tools/chercher.mjs', import.meta.url));
  const r = spawnSync(process.execPath, ['--no-experimental-detect-module', tool, '--aide'], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /Usage : node tools\/chercher\.mjs/);
  const pkg = JSON.parse(readFileSync(new URL('../../site/js/recherche/package.json', import.meta.url), 'utf8'));
  assert.equal(pkg.type, 'module');
});

test('bilan: a spelling only found with its article apart is listed as a fused article', () => {
  const index = indexOf(['Testaoui, El Arbi', 'Testaoui, Bel Hadi']);
  const lines = (query) => search(index, query).bilan.graphiesTrouvees[0].graphies.map((g) => [g.graphie, g.soudure, g.exclure]);
  assert.deepEqual(lines('Larbi'), [['El Arbi', 'article-fondu', ['larbi']]]);
  assert.deepEqual(lines('Belhadi')[0], ['Bel Hadi', 'colle', ['belhadi']], 'plain gluing keeps its own label');
});
