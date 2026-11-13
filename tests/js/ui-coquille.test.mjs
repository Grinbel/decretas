import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE = fileURLToPath(new URL('../../site/', import.meta.url));
const lire = (rel) => readFileSync(path.join(SITE, rel), 'utf8');

function fichiersJs(dir = 'js') {
  const out = [];
  for (const name of readdirSync(path.join(SITE, dir))) {
    const rel = `${dir}/${name}`;
    if (statSync(path.join(SITE, rel)).isDirectory()) out.push(...fichiersJs(rel));
    else if (name.endsWith('.js')) out.push(rel);
  }
  return out;
}

/** Modules reached from an entry by static imports (paths relative to site/). */
function graphe(entree) {
  const seen = new Set();
  const todo = [entree];
  while (todo.length > 0) {
    const rel = todo.pop();
    if (seen.has(rel)) continue;
    seen.add(rel);
    for (const m of lire(rel).matchAll(/^\s*(?:import|export)\s[^'"]*?from\s+'([^']+)'|^\s*import\s+'([^']+)'/gm)) {
      todo.push(path.posix.normalize(path.posix.join(path.posix.dirname(rel), m[1] ?? m[2])));
    }
  }
  return seen;
}

const sansCommentaires = (source) => source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');

const html = lire('index.html');

test('shell: a strict Content-Security-Policy, and nothing inline for it to forbid', () => {
  const csp = /<meta http-equiv="Content-Security-Policy" content="([^"]+)">/.exec(html)?.[1] ?? '';
  const directives = Object.fromEntries(csp.split(';').map((d) => d.trim().split(/\s+/)).map(([name, ...values]) => [name, values]));
  assert.deepEqual(directives['default-src'], ["'none'"]);
  assert.deepEqual(directives['script-src'], ["'self'"]);
  assert.deepEqual(directives['style-src'], ["'self'"]);
  assert.deepEqual(directives['connect-src'], ["'self'"], 'data and content are only ever fetched from the site itself');
  assert.deepEqual(directives['worker-src'], ["'self'"]);
  assert.deepEqual(directives['form-action'], ["'none'"]);
  assert.deepEqual(directives['base-uri'], ["'none'"]);
  // the one exception: the image of a printed page, asked after an explicit click
  assert.deepEqual(directives['img-src'], ["'self'", 'https://archive.org', 'https://*.archive.org']);
  assert.doesNotMatch(csp, /unsafe-inline|unsafe-eval|\*\s|data:|blob:/);
  assert.doesNotMatch(html, /<script(?![^>]*\bsrc=)[^>]*>/, 'no inline script');
  assert.doesNotMatch(html, /<style|\sstyle=|\son[a-z]+=/i, 'no inline style, no inline handler');
  assert.match(html, /<meta name="referrer" content="no-referrer">/);
});

test('shell: the page asks nothing from another site', () => {
  const adresses = [...html.matchAll(/\s(?:src|href)="([^"]+)"/g)].map((m) => m[1]);
  assert.ok(adresses.length > 5);
  for (const a of adresses) assert.match(a, /^(?:#|[a-z0-9_./-]+$)/i, a);
  for (const css of readdirSync(path.join(SITE, 'css'))) {
    assert.doesNotMatch(lire(`css/${css}`), /url\(|@import|https?:\/\//, css);
  }
});

test('shell: every module of the page is preloaded, so that the first paint does not wait for a chain of discoveries', () => {
  const precharges = new Set([...html.matchAll(/<link rel="modulepreload" href="([^"]+)">/g)].map((m) => m[1]));
  const attendus = graphe('js/app.js');
  assert.deepEqual([...precharges].sort(), [...attendus].sort());
  // the worker's own graph is loaded by the worker, off the main thread
  assert.equal(precharges.has('js/donnees/service.js'), false);
});

test('shell: the document says its language, has one main landmark, a skip link, and works without the data', () => {
  assert.match(html, /<html lang="fr" dir="ltr">/);
  assert.equal((html.match(/<main\b/g) ?? []).length, 1);
  assert.match(html, /<a class="evitement" href="#contenu">/);
  assert.match(html, /<noscript>[\s\S]*JavaScript[\s\S]*<\/noscript>/);
  assert.match(html, /indépendant/);
  assert.match(html, /aucun certificat/);
});

test('code: a string never becomes markup, and no storage, cookie or beacon is used', () => {
  for (const rel of fichiersJs()) {
    const code = sansCommentaires(lire(rel));
    assert.doesNotMatch(code, /innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function\b|DOMParser/, rel);
    assert.doesNotMatch(code, /sessionStorage|document\.cookie|indexedDB|sendBeacon|XMLHttpRequest|WebSocket|EventSource/, rel);
    // One exception, on purpose: the checklist « décrets déjà lus », kept in this browser only.
    if (rel !== 'js/donnees/carnet.js') assert.doesNotMatch(code, /localStorage/, rel);
  }
  const carnet = sansCommentaires(lire('js/donnees/carnet.js'));
  assert.equal((carnet.match(/localStorage/g) ?? []).length, 1, 'the checklist reaches the storage in one place');
  // and nothing else of the site reaches the checklist's storage object
  for (const rel of fichiersJs()) {
    if (rel === 'js/donnees/carnet.js') continue;
    assert.doesNotMatch(sansCommentaires(lire(rel)), /stockageDuNavigateur|getItem\(|setItem\(/, rel);
  }
});

test('code: no external address is written by hand — they come from site/contenu/liens.json', () => {
  for (const rel of fichiersJs()) {
    if (rel.startsWith('js/recherche/')) continue;
    const literals = [...sansCommentaires(lire(rel)).matchAll(/['"`]https?:\/\/[^'"`]*/g)].map((m) => m[0].slice(1));
    assert.deepEqual(literals.filter((u) => u !== 'http://www.w3.org/2000/svg'), [], rel);
  }
});

test('code: the only fetches are same-origin files, without credentials', () => {
  const appels = [];
  for (const rel of fichiersJs()) {
    for (const m of sansCommentaires(lire(rel)).matchAll(/\bfetch\(([^)]*)\)/g)) appels.push(`${rel}: fetch(${m[1]})`);
  }
  // one in the data worker, one for the content files, one for the small data files of the
  // pages that need no names; the engine's own session is not used by the page
  const page = appels.filter((a) => !a.startsWith('js/recherche/'));
  assert.equal(page.length, 3, page.join('\n'));
  for (const a of page) assert.match(a, /credentials: 'omit'/, a);
});

test('views: every page is registered under its address, and none is a placeholder', () => {
  const noms = [...sansCommentaires(lire('js/app.js')).matchAll(/enregistrer\('([^']*)'/g)].map((m) => m[1]);
  assert.deepEqual(noms.sort(), ['', 'a-propos', 'actes', 'decrets', 'guides', 'methode', 'notice', 'numero', 'quel-acte', 'recherche', 'vocabulaire'].sort());
  assert.doesNotMatch(lire('js/app.js'), /vueEnAttente|attente\.js/);
});

test('words: the strings never pass a verdict on a person, and the period word stays between guillemets', async () => {
  const source = sansCommentaires(lire('js/textes/fr.js'));
  assert.doesNotMatch(source, /n'a pas été admis|n'était pas français|n'a jamais été|aucun résultat|Aucun résultat/i);
  for (const m of source.matchAll(/indigène/g)) {
    assert.equal(source.slice(m.index - 2, m.index), '« ', `« indigène » without guillemets near: ${source.slice(m.index - 30, m.index + 20)}`);
  }
  assert.doesNotMatch(source, /République française|Marianne/);
  const { fr } = await import('../../site/js/textes/fr.js');
  // every page has its document title
  for (const cle of ['quelActe', 'decrets', 'lus', 'numero', 'actes', 'vocabulaire', 'aPropos', 'methode', 'guides']) {
    assert.ok(typeof fr[cle]?.titreDocument === 'string' && fr[cle].titreDocument.length > 3, cle);
  }
  // the decree browser names every reading group
  const { GROUPES } = await import('../../site/js/logique/decrets.js');
  for (const g of GROUPES) assert.ok(fr.decrets.groupesNoms[g], g);
  // the citation checker explains every form it recognises
  for (const code of ['date', 'annee', 'dossier', 'cote-bb34', 'cote-bb11', 'cote-autre', 'inventaire', 'document', 'article', 'page', 'publication', 'nombre-nu']) {
    assert.ok(fr.numero.formes[code]?.nom && fr.numero.formes[code]?.texte, code);
  }
  assert.doesNotMatch(source, /faux|frauduleux|arnaque|escroc|mensonge/i, 'the checker never accuses anyone');
  // every warning code documented by the engine has its sentence
  for (const code of ['aucun-terme', 'compose-de-particules', 'initiale-ignoree', 'nombre-ignore', 'trop-de-termes', 'variante-sans-nom', 'variante-plusieurs-mots', 'annee-illisible', 'tolerance-illisible']) {
    assert.equal(typeof fr.avertissements[code], 'function', code);
    assert.ok(fr.avertissements[code]('x').length > 20, code);
  }
});

test('views: every page module loads (a syntax error in a view would otherwise surface only in a browser)', async () => {
  for (const name of readdirSync(path.join(SITE, 'js/vues'))) {
    const module = await import(new URL(`../../site/js/vues/${name}`, import.meta.url));
    assert.ok(Object.keys(module).length > 0, name);
  }
});
