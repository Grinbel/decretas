import { test } from 'node:test';
import assert from 'node:assert/strict';

import { BUDGET, CLASSES, PAS, fenetresDeCartes, grouperParNotice, surligner } from '../../site/js/logique/menage.js';

const c = (cle, ligne, classe) => ({ cle, ligne, classe, termes: [] });

test('household: the rows of one notice share one card, in the class of its best correspondence', () => {
  const parClasse = grouperParNotice([
    c('an:0', 0, 'correspondance'),
    c('bogga:7', 7, 'correspondance'),
    c('an:0', 2, 'graphie-approchante'),   // a child of the same notice, approximate
    c('an:4', 4, 'graphie-approchante'),
    c('an:0', 1, 'partielle'),             // the spouse, partial
    c('an:9', 9, 'partielle'),
  ]);
  assert.deepEqual(parClasse.correspondance.map((k) => k.cle), ['an:0', 'bogga:7']);
  assert.deepEqual(parClasse['graphie-approchante'].map((k) => k.cle), ['an:4']);
  assert.deepEqual(parClasse.partielle.map((k) => k.cle), ['an:9']);
  assert.deepEqual(parClasse.correspondance[0].touches.map((t) => t.ligne), [0, 2, 1]);
});

test('household: a row keeps its best correspondence only; junk is ignored', () => {
  const parClasse = grouperParNotice([c('an:0', 0, 'correspondance'), c('an:0', 0, 'partielle'), null, { cle: 3 }, c('an:1', 1, 'inconnue')]);
  assert.equal(parClasse.correspondance[0].touches.length, 1);
  assert.equal(CLASSES.every((k) => Array.isArray(parClasse[k])), true);
  assert.deepEqual(grouperParNotice(undefined), { correspondance: [], 'graphie-approchante': [], partielle: [] });
});

test('cards: each class starts with a few cards and never more than the budget is in the page', () => {
  const totaux = { correspondance: 99, 'graphie-approchante': 21, partielle: 300 };
  let w = fenetresDeCartes(totaux);
  assert.deepEqual(w, { correspondance: { debut: 0, fin: PAS }, 'graphie-approchante': { debut: 0, fin: PAS }, partielle: { debut: 0, fin: PAS } });
  const shown = (x) => CLASSES.reduce((sum, k) => sum + x[k].fin - x[k].debut, 0);
  for (let i = 0; i < 12; i++) {
    w = fenetresDeCartes(totaux, w, { classe: 'correspondance', action: 'plus' });
    assert.ok(shown(w) <= BUDGET, `step ${i}: ${shown(w)} cards`);
  }
  assert.equal(w.correspondance.fin, 99);
  assert.ok(w.correspondance.debut > 0, 'the start of the list gave way');
  w = fenetresDeCartes(totaux, w, { classe: 'correspondance', action: 'debut' });
  assert.deepEqual(w.correspondance, { debut: 0, fin: PAS });
});

test('cards: a short class is shown whole, an empty one is empty', () => {
  const w = fenetresDeCartes({ correspondance: 3, partielle: 0 });
  assert.deepEqual(w.correspondance, { debut: 0, fin: 3 });
  assert.deepEqual(w.partielle, { debut: 0, fin: 0 });
  assert.deepEqual(fenetresDeCartes({ correspondance: 3 }, w, { classe: 'correspondance', action: 'plus' }).correspondance, { debut: 0, fin: 3 });
});

test('highlight: the written name is cut around the matched words and never altered', () => {
  const nom = 'Testaoui, Belgacem ben Exemplane';
  const pieces = surligner(nom, ['Belgacem', 'Exemplane']);
  assert.equal(pieces.map((p) => p.texte).join(''), nom);
  assert.deepEqual(pieces.filter((p) => p.touche).map((p) => p.texte), ['Belgacem', 'Exemplane']);
});

test('highlight: whole words only; a word matched twice is marked once; several written words stay together', () => {
  assert.deepEqual(surligner('Benali, Ali', ['Ali']).filter((p) => p.touche).map((p) => p.texte), ['Ali']);
  assert.equal(surligner('Benali, Ali', ['Ali'])[0].texte, 'Benali, ');
  assert.deepEqual(surligner('Mohamed ben Mohamed', ['Mohamed']).filter((p) => p.touche).length, 1);
  assert.deepEqual(surligner('Bel Kaçem ben Ali', ['Bel Kaçem']).filter((p) => p.touche).map((p) => p.texte), ['Bel Kaçem']);
  assert.deepEqual(surligner('Nom', []), [{ texte: 'Nom', touche: false }]);
  assert.deepEqual(surligner(null, ['x']), []);
});
