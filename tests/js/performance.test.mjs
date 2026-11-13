import { test } from 'node:test';
import assert from 'node:assert/strict';

import { buildIndex } from '../../site/js/recherche/index.js';
import { search } from '../../site/js/recherche/chercher.js';
import { suggestVariants } from '../../site/js/recherche/suggestions.js';
import { syntheticOccurrences } from './aide.mjs';

const COUNT = 150000;
const BUILD_BUDGET_MS = 2000; // the contract: 150,000 occurrences "well under 2 s"
const QUERY_BUDGET_MS = 10; // "a few ms" for a usual query (median of 30 runs)
const HEAVY_BUDGET_MS = 80; // queries that bring back more than 10,000 occurrences

function median(fn, runs = 30) {
  const times = [];
  let last;
  for (let i = 0; i < runs; i++) {
    const start = performance.now();
    last = fn();
    times.push(performance.now() - start);
  }
  times.sort((a, b) => a - b);
  return { ms: times[runs >> 1], max: times[runs - 1], last };
}

test(`performance: ${COUNT} synthetic occurrences are indexed and searched within budget`, (t) => {
  const occurrences = syntheticOccurrences(COUNT);
  const index = buildIndex(occurrences, { groupesOcr: ['bogga'] });
  // A second build, once the engine is warm, is what a page reload costs.
  const warm = buildIndex(occurrences, { groupesOcr: ['bogga'] });
  t.diagnostic(`index of ${COUNT} occurrences: ${index.buildMs.toFixed(0)} ms cold, ${warm.buildMs.toFixed(0)} ms warm, ${index.formCount} forms`);
  assert.equal(index.size, COUNT);
  assert.ok(index.buildMs < BUILD_BUDGET_MS, `index built in ${index.buildMs.toFixed(0)} ms (budget ${BUILD_BUDGET_MS})`);

  // Usual queries: three terms, or names that are not among the most common of the corpus.
  const usual = [
    { texte: 'Belkacem ben Chabane Bouzidaoui', annee: 1876 },
    { texte: 'Mohamed ben Ahmed ben Larbi', annee: 1870 },
    { texte: 'Bouzidaoui Khedidja|Khadidja' },
    { texte: 'بلقاسم بن شعبان بن علي' },
    { texte: 'Khedidja bent Slimane Benchabane', annee: 1890, tolerance: 10 },
  ];
  for (const q of usual) {
    const m = median(() => search(index, q));
    const c = m.last.bilan.comptes.parClasse;
    t.diagnostic(`« ${q.texte} »: median ${m.ms.toFixed(2)} ms, max ${m.max.toFixed(2)} ms — ${c.correspondance}/${c['graphie-approchante']}/${c.partielle}`);
    assert.ok(m.ms < QUERY_BUDGET_MS, `« ${q.texte} » answered in ${m.ms.toFixed(2)} ms (budget ${QUERY_BUDGET_MS})`);
  }

  // Dense queries: this corpus draws every given name from 45 values, so two very common
  // given names bring back tens of thousands of partial correspondences — far denser than the
  // real sources. They must still be classified, counted and ordered quickly.
  const dense = [{ texte: 'Mohamed ben Ahmed' }, { texte: 'Belkacem|Belgacem Chabane' }, { texte: 'Mohamed' }, { texte: 'محمد' }];
  for (const q of dense) {
    const m = median(() => search(index, q), 10);
    t.diagnostic(`dense « ${q.texte} »: median ${m.ms.toFixed(2)} ms — ${m.last.bilan.comptes.total} counted, ${m.last.correspondances.length} returned`);
    assert.ok(m.last.bilan.comptes.total > 10000);
    assert.ok(m.ms < HEAVY_BUDGET_MS, `« ${q.texte} » answered in ${m.ms.toFixed(2)} ms (budget ${HEAVY_BUDGET_MS})`);
  }

  const sugg = median(() => suggestVariants(index, 'Belkacem'));
  t.diagnostic(`suggestions for « Belkacem »: median ${sugg.ms.toFixed(2)} ms`);
  assert.ok(sugg.ms < QUERY_BUDGET_MS);
  assert.ok(sugg.last.exactes[0].occurrences > 1000);
});

test('performance: the synthetic corpus is deterministic and made of invented names', () => {
  const a = syntheticOccurrences(50);
  const b = syntheticOccurrences(50);
  assert.deepEqual(a, b);
  assert.notDeepEqual(a, syntheticOccurrences(50, 7));
});
