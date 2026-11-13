import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const TOOL = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'tools', 'chercher.mjs');
const run = (args) => spawnSync(process.execPath, [TOOL, ...args], { encoding: 'utf8' });

function withData(fn) {
  const dir = mkdtempSync(path.join(tmpdir(), 'decretas-cli-'));
  try {
    writeFileSync(path.join(dir, 'an-personnes.json'), JSON.stringify({
      champs: ['id', 'role', 'nom', 'an'],
      lignes: [
        ['a1', 'principal', 'Testaoui, Belkacem ben Chabane', 1876],
        ['a2', 'principal', 'TESTAOUI, Belgacem ben Chaabane', 1879],
        ['a3', 'principal', 'Testaoui, Mohamed ben Chabane', 1877],
        ['a4', 'principal', 'Testaoui, Belkacem ben Chabane', 1850],
      ],
    }));
    writeFileSync(path.join(dir, 'bogga-entrees.json'), JSON.stringify({
      champs: ['id', 'texte', 'page'],
      lignes: [['b1', 'Belkacem bon Chabane Testaoui', 495]],
    }));
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test('CLI: prints the three classes and the bilan, in French', () => withData((dir) => {
  const r = run(['--donnees', dir, '--champ-nom', 'nom', '--annee', '1876', 'Testaoui Belkacem ben Chabane']);
  assert.equal(r.status, 2, 'the bogga file has no column "nom": the error names the columns');
  assert.match(r.stderr, /bogga-entrees\.json : Colonne « nom » absente.*id, texte, page/);

  const an = run(['--fichier', `${path.join(dir, 'an-personnes.json')}:an`, '--annee', '1876', '--suggestions', 'Testaoui Belkacem ben Chabane']);
  assert.equal(an.status, 0, an.stderr);
  assert.match(an.stderr, /4 lignes, 4 noms \(colonne du nom : nom ; identifiant : id ; année de naissance : an\)/);
  assert.match(an.stdout, /== Correspondances : 1 ==\n {2}\[an\] a1 — Testaoui, Belkacem ben Chabane \(né\(e\) en 1876, écart 0\)/);
  assert.match(an.stdout, /== Correspondances à graphie approchante : 1 ==\n {2}\[an\] a2/);
  assert.match(an.stdout, /Belkacem = « Belgacem » — squelette de consonnes/);
  assert.match(an.stdout, /== Correspondances partielles \(un terme manque\) : 1 ==\n {2}\[an\] a3/);
  assert.match(an.stdout, /Belkacem : ABSENT/);
  assert.match(an.stdout, /particules non exigées : ben/);
  assert.match(an.stdout, /écartées par l'année de naissance : 1 \/ 0 \/ 0/);
  assert.match(an.stdout, /squelette de consonnes \(k2\) : Belgacem \(1\)/);
}));

test('CLI: default files, per-file name column given explicitly, JSON output', () => withData((dir) => {
  const out = execFileSync(process.execPath, [TOOL,
    '--fichier', `${path.join(dir, 'an-personnes.json')}:an`, '--json', 'Testaoui Belkacem Chabane'], { encoding: 'utf8' });
  const parsed = JSON.parse(out);
  assert.deepEqual(parsed.bilan.comptes.parClasse, { correspondance: 2, 'graphie-approchante': 1, partielle: 1 });
  assert.equal(parsed.correspondances[0].id, 'a1');

  const printed = run(['--fichier', `${path.join(dir, 'bogga-entrees.json')}:bogga:ocr`, '--champ-nom', 'texte', 'Benchabane Belkacem']);
  assert.equal(printed.status, 0, printed.stderr);
  assert.match(printed.stderr, /texte imprimé lu par OCR/);
  assert.match(printed.stdout, /== Correspondances : 1 ==/);
  assert.match(printed.stdout, /Benchabane = « bon Chabane »/);
}));

test('CLI: absent data files give a clear message and exit code 2', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'decretas-vide-'));
  try {
    const r = run(['--donnees', dir, 'Testaoui']);
    assert.equal(r.status, 2);
    assert.match(r.stderr, /Fichier de données absent : .*an-personnes\.json — ignoré\./);
    assert.match(r.stderr, /Fichier de données absent : .*bogga-entrees\.json — ignoré\./);
    assert.match(r.stderr, /Aucun fichier de données trouvé/);
    assert.equal(r.stdout, '');
    const strict = run(['--donnees', dir, '--exiger-tous', 'Testaoui']);
    assert.equal(strict.status, 2);
    assert.match(strict.stderr, /^Fichier de données absent : .*an-personnes\.json\.\n$/);
    const explicit = run(['--fichier', path.join(dir, 'absent.json'), 'Testaoui']);
    assert.equal(explicit.status, 2);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('CLI: one default file present is enough; the other is reported as ignored', () => withData((dir) => {
  rmSync(path.join(dir, 'bogga-entrees.json'));
  const r = run(['--donnees', dir, 'Testaoui Mohamed']);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stderr, /bogga-entrees\.json — ignoré/);
  assert.match(r.stdout, /== Correspondances : 1 ==/);
}));

test('CLI: usage errors and help', () => {
  const none = run([]);
  assert.equal(none.status, 64);
  assert.match(none.stderr, /Il manque le nom à chercher/);
  const bad = run(['--annee', 'vers1876', 'Testaoui']);
  assert.equal(bad.status, 64);
  assert.match(bad.stderr, /--annee attend un nombre entier/);
  const unknown = run(['--inconnue', 'Testaoui']);
  assert.equal(unknown.status, 64);
  assert.match(unknown.stderr, /^Option inconnue : --inconnue\./);
  assert.ok(!/Unknown option|To specify/.test(unknown.stderr), 'no English text from Node');
  const missing = run(['Testaoui', '--annee']);
  assert.equal(missing.status, 64);
  assert.match(missing.stderr, /^Option mal employée : --annee/);
  assert.ok(!/argument missing/.test(missing.stderr));
  const help = run(['--aide']);
  assert.equal(help.status, 0);
  for (const option of ['--annee', '--tolerance', '--limite', '--sans-partielles', '--suggestions', '--json', '--donnees', '--fichier',
    '--champ-nom', '--champ-id', '--champ-annee', '--exiger-tous', '--aide']) {
    assert.ok(help.stdout.includes(option), `help explains ${option}`);
  }
});

test('CLI: an unreadable JSON file is reported, not dumped as a stack trace', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'decretas-casse-'));
  try {
    writeFileSync(path.join(dir, 'an-personnes.json'), '{"champs": [');
    const r = run(['--donnees', dir, 'Testaoui']);
    assert.equal(r.status, 2);
    assert.match(r.stderr, /n'est pas du JSON lisible/);
    assert.ok(!/SyntaxError|at /.test(r.stderr));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// The real printed-bulletin file names its columns id, nom, texte, naissance… : the birth year
// must be found without any option, so that the year filter applies to printed entries too.
test('CLI: the columns of the real bogga-entrees.json are read without options', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'decretas-bogga-'));
  try {
    writeFileSync(path.join(dir, 'bogga-entrees.json'), JSON.stringify({
      champs: ['id', 'volume', 'decret', 'nom', 'texte', 'marqueurs', 'nationalite', 'naissance', 'residence', 'page', 'feuille', 'drapeaux'],
      lignes: [
        [0, 1, 4, 'Testaoui (Belkacem bon Chabane)', 'Testaoui (Belkacem bon Chabane), né en 1846 à Exempleville.', 1, null, 1846, null, 61, 116, 0],
        [1, 1, 4, 'Testaoui (Belkacem ben Chabane)', 'Testaoui (Belkacem ben Chabane), né en 1820.', 1, null, 1820, null, 62, 117, 0],
        [2, 1, 4, 'El Arbi ben Chabane', 'El Arbi ben Chabane, demeurant à Exempleville.', 1, null, null, 'Exempleville', 62, 117, 0],
      ],
    }));
    const r = run(['--donnees', dir, '--annee', '1846', 'Testaoui Belkacem ben Chabane']);
    assert.equal(r.status, 0, r.stderr);
    assert.match(r.stderr, /colonne du nom : nom ; identifiant : id ; année de naissance : naissance/);
    assert.match(r.stdout, /== Correspondances : 1 ==\n {2}\[bogga\] 0 — Testaoui \(Belkacem bon Chabane\) \(né\(e\) en 1846, écart 0\)/);
    assert.match(r.stdout, /écartées par l'année de naissance : 1 \/ 0 \/ 0/);
    const fused = run(['--donnees', dir, 'Larbi Chabane']);
    assert.match(fused.stdout, /Larbi = « El Arbi » — même graphie, article « el » fondu dans le nom/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
