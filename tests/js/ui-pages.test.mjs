import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { lignesAn, lignesBulletin } from '../../site/js/vues/methode.js';
import { dansEpoque } from '../../site/js/vues/actes.js';
import { creerModele } from '../../site/js/donnees/modele.js';
import { creerDonneesLegeres, FICHIERS_LEGERS } from '../../site/js/donnees/legeres.js';
import { fichiers } from './ui-aide.mjs';

const lire = (nom) => JSON.parse(readFileSync(new URL(`../../site/contenu/${nom}.json`, import.meta.url), 'utf8'));

test('méthode: one row per year, one per quarter where the inventories are cut, counts from the data', () => {
  const couverture = creerModele(fichiers()).couverture();
  const lignes = lignesAn(couverture);
  const annees = couverture.an.annees.map((y) => y.annee);
  const coupees = new Set(couverture.an.trimestres.map((q) => q.annee));
  assert.equal(lignes.length, annees.filter((y) => !coupees.has(y)).length + couverture.an.trimestres.length);
  for (const l of lignes) assert.ok(Number.isInteger(l.annee) && typeof l.lecture === 'string');
  const bulletin = lignesBulletin(couverture);
  assert.equal(bulletin.length, couverture.bogga.annees.length);
  assert.equal(bulletin.reduce((s, y) => s + y.pagesALaMain, 0), couverture.bogga.pagesALireALaMain.length);
});

test('actes: a card belongs to every period its years cross; an open end runs on', () => {
  const types = lire('types-d-actes').types;
  const epoques = lire('aiguillage').epoques;
  const par = (id) => epoques.find((e) => e.id === id);
  const ids = (e) => types.filter((t) => dansEpoque(t, e)).map((t) => t.id);
  assert.equal(ids(null).length, 16);
  assert.ok(ids(par('e-1899-1912')).includes('T1'));
  assert.ok(!ids(par('e-1899-1912')).includes('T7'), 'judgments start in 1919');
  assert.ok(ids(par('e-1949-1962')).includes('T16') === false, 'after 1962 only');
  for (const e of epoques) assert.ok(ids(e).length > 0, e.id);
});

test('données légères: the small files only, without credentials; a failed download is tried again', async () => {
  const data = fichiers();
  const parUrl = { 'data/an-meta.json': data.anMeta, 'data/an-decrets.json': data.anDecrets, 'data/bogga-meta.json': data.boggaMeta, 'data/bogga-volumes.json': data.boggaVolumes, 'data/bogga-decrets.json': data.boggaDecrets };
  assert.deepEqual(FICHIERS_LEGERS.map((f) => f.url).sort(), Object.keys(parUrl).sort());
  let echoue = true;
  const demandes = [];
  const leger = creerDonneesLegeres({
    fetch: async (url) => {
      demandes.push(url);
      if (echoue && url.endsWith('an-decrets.json')) return { ok: false, status: 503 };
      return { ok: true, json: async () => parUrl[url] };
    },
  });
  await assert.rejects(leger.charger(), (e) => e.name === 'ErreurDonnees' && e.statut === 503);
  echoue = false;
  const modele = await leger.charger();
  assert.ok(modele.decretsAn({}).length > 0);
  assert.ok(modele.couverture().an.annees.length > 0);
  assert.ok(!demandes.some((u) => /personnes|entrees/.test(u)), 'the name files are never asked for here');
});
