#!/usr/bin/env node
/**
 * Command-line search over the site data files, with the same engine as the browser
 * (site/js/recherche/). No network. Used for the pilot ancestor and for regression checks.
 *
 *   node tools/chercher.mjs --annee 1876 "Testaoui Belkacem ben Chabane"
 *   node tools/chercher.mjs --aide
 */

import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

import { buildIndex, occurrencesFromColumns, DataFormatError } from '../site/js/recherche/index.js';
import { search, CLASSES, DEFAULT_TOLERANCE } from '../site/js/recherche/chercher.js';
import { suggestVariants } from '../site/js/recherche/suggestions.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEFAULT_DIR = path.join(ROOT, 'site', 'data');
/** Default data files: name, source group, and whether the text comes from OCR of a printed page. */
const DEFAULT_FILES = [
  { nom: 'an-personnes.json', groupe: 'an', ocr: false },
  { nom: 'bogga-entrees.json', groupe: 'bogga', ocr: true },
];

const HELP = `Recherche d'un nom dans les données du site (aucun accès réseau).

Usage : node tools/chercher.mjs [options] <nom recherché>

Le nom s'écrit comme dans la case de recherche du site :
  Belkacem ben Chabane Testaoui    trois termes ; « ben » est une particule, jamais exigée
  "Belkacem|Belgacem" Chabane      variantes d'un même terme, séparées par |
  "Belkacem|-Belkassem"            le signe - écarte une graphie trouvée dans l'index
  '"Hadj" Ali'                     les guillemets exigent un mot, même une particule
  بلقاسم بن شعبان                    saisie en arabe (toujours approchante)

Options :
  --annee <AAAA>          année de naissance approximative de l'ancêtre
  --tolerance <n>         écart admis autour de cette année, en années (défaut : ${DEFAULT_TOLERANCE})
  --limite <n>            nombre de lignes affichées par classe (défaut : 20)
  --sans-partielles       ne pas chercher les correspondances partielles
  --suggestions           afficher, pour chaque terme, les graphies présentes dans l'index
  --json                  écrire en JSON les correspondances et le bilan de recherche
  --donnees <dossier>     dossier des fichiers de données (défaut : site/data)
  --fichier <chemin>      fichier à charger à la place des fichiers habituels ; répétable ;
                          forme « chemin », « chemin:groupe » ou « chemin:groupe:ocr »
  --champ-nom <colonne>   colonne du nom (défaut : « nom » ; plusieurs colonnes : a,b)
  --champ-id <colonne>    colonne de l'identifiant (défaut : « id », sinon le numéro de ligne)
  --champ-annee <colonne> colonne de l'année de naissance (défaut : détectée, p. ex. « an »)
  --exiger-tous           échouer si l'un des fichiers habituels manque (défaut : l'ignorer)
  --aide                  afficher cette aide

Codes de sortie : 0 recherche faite ; 2 données absentes ou illisibles ; 64 mauvaise commande.
`;

class UsageError extends Error {}
class DataError extends Error {}

const fmt = (n) => new Intl.NumberFormat('fr-FR').format(n);
const rel = (p) => {
  const r = path.relative(process.cwd(), p);
  return r === '' || r.startsWith('..') ? p : r;
};

function parseCommandLine(argv) {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      allowPositionals: true,
      options: {
        annee: { type: 'string' },
        tolerance: { type: 'string' },
        limite: { type: 'string' },
        'sans-partielles': { type: 'boolean', default: false },
        suggestions: { type: 'boolean', default: false },
        json: { type: 'boolean', default: false },
        donnees: { type: 'string' },
        fichier: { type: 'string', multiple: true },
        'champ-nom': { type: 'string' },
        'champ-id': { type: 'string' },
        'champ-annee': { type: 'string' },
        'exiger-tous': { type: 'boolean', default: false },
        aide: { type: 'boolean', default: false },
      },
    });
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    // Node words its own message in English: only the option name is taken from it.
    const option = /'(-{1,2}[^'\s=]+)/.exec(error.message)?.[1];
    const named = option ? ` : ${option}` : '';
    if (error.code === 'ERR_PARSE_ARGS_UNKNOWN_OPTION') {
      throw new UsageError(`Option inconnue${named}. Un nom qui commence par un tiret s'écrit après « -- ».`);
    }
    if (error.code === 'ERR_PARSE_ARGS_INVALID_OPTION_VALUE') {
      throw new UsageError(`Option mal employée${named} : il lui manque une valeur, ou elle n'en prend pas.`);
    }
    throw new UsageError('Ligne de commande incorrecte.');
  }
  const { values, positionals } = parsed;
  const number = (name, min, max) => {
    if (values[name] === undefined) return undefined;
    const v = Number(values[name]);
    if (!Number.isInteger(v) || v < min || v > max) {
      throw new UsageError(`--${name} attend un nombre entier entre ${min} et ${max} (reçu : « ${values[name]} »).`);
    }
    return v;
  };
  return {
    aide: values.aide,
    texte: positionals.join(' ').trim(),
    annee: number('annee', 1000, 2100),
    tolerance: number('tolerance', 0, 100),
    limite: number('limite', 0, 100000) ?? 20,
    partielles: !values['sans-partielles'],
    suggestions: values.suggestions,
    json: values.json,
    donnees: values.donnees ? path.resolve(values.donnees) : DEFAULT_DIR,
    fichiers: values.fichier ?? [],
    champNom: values['champ-nom'],
    champId: values['champ-id'],
    champAnnee: values['champ-annee'],
    exigerTous: values['exiger-tous'],
  };
}

function fileList(opts) {
  if (opts.fichiers.length > 0) {
    return opts.fichiers.map((spec) => {
      const [chemin, groupe, ocr] = spec.split(':');
      const full = path.resolve(chemin);
      return { chemin: full, groupe: groupe || path.basename(full).replace(/[-.].*$/, ''), ocr: ocr === 'ocr', requis: true };
    });
  }
  return DEFAULT_FILES.map((f) => ({ chemin: path.join(opts.donnees, f.nom), groupe: f.groupe, ocr: f.ocr, requis: opts.exigerTous }));
}

async function loadFiles(opts, log) {
  const all = [];
  const groupesOcr = [];
  let loaded = 0;
  for (const f of fileList(opts)) {
    if (!existsSync(f.chemin)) {
      const message = `Fichier de données absent : ${rel(f.chemin)}`;
      if (f.requis) throw new DataError(`${message}.`);
      log(`${message} — ignoré.`);
      continue;
    }
    let data;
    try {
      data = JSON.parse(await readFile(f.chemin, 'utf8'));
    } catch (error) {
      if (error instanceof SyntaxError) throw new DataError(`${rel(f.chemin)} n'est pas du JSON lisible.`);
      if (error.code === 'EACCES' || error.code === 'EISDIR') throw new DataError(`${rel(f.chemin)} ne peut pas être lu (${error.code}).`);
      throw error;
    }
    let adapted;
    try {
      adapted = occurrencesFromColumns(data, { groupe: f.groupe, champNom: opts.champNom, champId: opts.champId, champAnnee: opts.champAnnee });
    } catch (error) {
      if (error instanceof DataFormatError) throw new DataError(`${rel(f.chemin)} : ${error.message}`);
      throw error;
    }
    for (const o of adapted.occurrences) all.push(o);
    if (f.ocr) groupesOcr.push(f.groupe);
    loaded++;
    const c = adapted.colonnes;
    log(`Données : ${rel(f.chemin)} — groupe « ${f.groupe} »${f.ocr ? ' (texte imprimé lu par OCR)' : ''}, ${fmt(adapted.lignes)} lignes, `
      + `${fmt(adapted.occurrences.length)} noms (colonne du nom : ${c.nom.join(', ')} ; identifiant : ${c.id ?? 'numéro de ligne'} ; `
      + `année de naissance : ${c.annee ?? 'aucune colonne'}).`);
  }
  if (loaded === 0) {
    throw new DataError('Aucun fichier de données trouvé. Ils sont produits par les constructeurs de données '
      + `(attendus dans ${rel(opts.donnees)}) ; un autre fichier peut être indiqué avec --fichier.`);
  }
  return { occurrences: all, groupesOcr };
}

const LEVEL_TEXT = { k0: 'même graphie', k1: "équivalence d'écriture", k2: 'squelette de consonnes' };

function termText(t) {
  if (t.absent) return `    ${t.terme} : ABSENT`;
  let how = t.arabe
    ? `saisie en arabe : correspondance approchante${t.voyellesLongues === true ? ', voyelles longues concordantes' : t.voyellesLongues === false ? ', voyelles longues non retrouvées' : ''}`
    : LEVEL_TEXT[t.niveau];
  if (t.soudure === 'colle') how += ', écrit en plusieurs mots ou collé';
  if (t.soudure === 'article-fondu') how += `, article « ${t.prefixe} » fondu dans le nom (El Arbi = Larbi)`;
  if (t.soudure === 'prefixe-source') how += `, préfixe « ${t.prefixe} » détaché du mot écrit`;
  if (t.soudure === 'prefixe-saisie') how += `, préfixe « ${t.prefixe} » détaché de la saisie`;
  const via = t.variante !== t.terme ? ` (variante « ${t.variante} »)` : '';
  return `    ${t.terme}${via} = « ${t.ecrit} » — ${how}`;
}

function resultText(r) {
  const birth = r.anneeNaissance === null ? 'année de naissance inconnue' : `né(e) en ${r.anneeNaissance}`;
  const gap = r.annee && r.annee.ecart !== null ? `, écart ${r.annee.ecart > 0 ? '+' : ''}${r.annee.ecart}` : '';
  const role = r.occurrence.champ ? ` {${r.occurrence.champ}}` : '';
  return [`  [${r.groupe}] ${r.id}${role} — ${r.nom} (${birth}${gap})`, ...r.termes.map(termText)].join('\n');
}

const CLASS_TITLES = {
  correspondance: 'Correspondances',
  'graphie-approchante': 'Correspondances à graphie approchante',
  partielle: 'Correspondances partielles (un terme manque)',
};

const WARNINGS = {
  'aucun-terme': () => 'Aucun terme distinctif dans la saisie (les particules seules ne se cherchent pas).',
  'compose-de-particules': (d) => `Deux particules se suivent ; si c'est un nom de famille, écrivez-le collé : « ${d} ».`,
  'initiale-ignoree': (d) => `Initiale ignorée : « ${d} ».`,
  'nombre-ignore': (d) => `Nombre ignoré dans la saisie : « ${d} » (l'année se donne avec --annee).`,
  'trop-de-termes': (d) => `Trop de termes ; « ${d} » n'est pas pris en compte.`,
  'variante-sans-nom': (d) => `Variante sans nom (particules seules) ignorée : « ${d} ».`,
  'variante-plusieurs-mots': (d) => `Variante en plusieurs mots : « ${d} » est cherchée d'un seul tenant.`,
  'annee-illisible': (d) => `Année illisible : « ${d} ».`,
  'tolerance-illisible': (d) => `Tolérance illisible : « ${d} ».`,
};

function printReport(out, opts, index, correspondances, bilan) {
  const w = (line = '') => out.write(`${line}\n`);
  w(`Index : ${fmt(index.size)} noms (${Object.entries(bilan.index.parGroupe).map(([g, c]) => `${g} ${fmt(c)}`).join(', ')}), `
    + `${fmt(bilan.index.formes)} formes, construit en ${bilan.index.dureeConstructionMs} ms.`);
  w();
  w(`Recherche : ${bilan.saisie}`);
  for (const t of bilan.termes) {
    const parts = t.variantes.map((v) => (v.ecriture === 'arabe'
      ? `${v.saisie} [arabe ; squelettes ${v.squelettes.map((s) => s.cle).join(', ')}]`
      : `${v.saisie} [k1 ${v.formes[0].k1}${v.formes[0].k2 ? ` ; k2 ${v.formes[0].k2}` : ' ; pas de niveau approchant (mot trop court)'}]`));
    w(`  terme : ${parts.join(' | ')}${t.exige ? ' (exigé tel quel)' : ''}${t.graphiesExclues.length ? ` ; graphies écartées : ${t.graphiesExclues.join(', ')}` : ''}`);
  }
  if (bilan.particulesIgnorees.length > 0) w(`  particules non exigées : ${bilan.particulesIgnorees.map((p) => p.saisie).join(', ')}`);
  if (bilan.annee) w(`  année de naissance : ${bilan.annee.valeur} ± ${bilan.annee.tolerance} ans (de ${bilan.annee.de} à ${bilan.annee.a}) ; les noms sans année sont gardés`);
  for (const a of bilan.avertissements) w(`  attention : ${(WARNINGS[a.code] ?? (() => a.code))(a.detail)}`);
  w();

  for (const cls of CLASSES) {
    const total = bilan.comptes.parClasse[cls];
    w(`== ${CLASS_TITLES[cls]} : ${fmt(total)} ==`);
    const lines = correspondances.filter((r) => r.classe === cls);
    for (const r of lines) w(resultText(r));
    if (total > lines.length) w(`  … ${fmt(total - lines.length)} de plus (voir --limite).`);
    w();
  }

  w('Bilan de recherche');
  w(`  par source : ${Object.entries(bilan.comptes.parGroupe).map(([g, c]) => `${g} ${CLASSES.map((k) => c[k]).join('/')}`).join(' ; ')} (correspondances / approchantes / partielles)`);
  if (bilan.annee) {
    const e = bilan.comptes.ecarteesParAnnee;
    w(`  écartées par l'année de naissance : ${e.correspondance} / ${e['graphie-approchante']} / ${e.partielle} ; gardées sans année connue : ${bilan.comptes.sansAnneeDeNaissance}`);
  }
  for (const g of bilan.graphiesTrouvees) {
    const list = g.graphies.map((x) => `${x.graphie} (${x.occurrences}${x.niveau === 'k2' ? ', approchante' : ''}${x.soudure && x.soudure.startsWith('prefixe') ? ', avec préfixe' : ''})`);
    w(`  graphies trouvées pour « ${g.terme} » : ${list.length ? list.join(', ') : 'aucune'}${g.tronque ? ', …' : ''}`);
  }
  w(`  ordre : classe, puis écart à l'année de naissance, puis nombre de termes écrits comme saisis, puis ordre des sources`);
  w(`  durée de la recherche : ${bilan.dureeMs} ms`);

  if (opts.suggestions) {
    w();
    w('Graphies présentes dans l\'index, par terme');
    for (const t of bilan.termes) {
      const s = suggestVariants(index, t.variantes[0].saisie);
      const line = (label, list) => (list.length ? w(`    ${label} : ${list.map((x) => `${x.graphie} (${x.occurrences})`).join(', ')}`) : undefined);
      w(`  ${s.terme}`);
      line('même graphie', s.exactes);
      line('même écriture (k1)', s.memeEcriture);
      line('squelette de consonnes (k2)', s.squelette);
      line('avec ou sans préfixe', s.avecPrefixe);
      line('noms apparentés, à ajouter soi-même comme variantes', s.apparentees);
    }
  }
}

async function main(argv) {
  const opts = parseCommandLine(argv);
  if (opts.aide) {
    process.stdout.write(HELP);
    return 0;
  }
  if (opts.texte === '') throw new UsageError('Il manque le nom à chercher.');
  const log = (line) => process.stderr.write(`${line}\n`);
  const { occurrences, groupesOcr } = await loadFiles(opts, opts.json ? () => {} : log);
  const index = buildIndex(occurrences, { groupesOcr });
  const { correspondances, bilan } = search(
    index,
    { texte: opts.texte, annee: opts.annee, tolerance: opts.tolerance },
    { limite: opts.limite, partielles: opts.partielles },
  );
  if (opts.json) {
    process.stdout.write(`${JSON.stringify({ correspondances, bilan }, null, 1)}\n`);
  } else {
    printReport(process.stdout, opts, index, correspondances, bilan);
  }
  return 0;
}

main(process.argv.slice(2)).then(
  (code) => { process.exitCode = code; },
  (error) => {
    if (error instanceof UsageError) {
      process.stderr.write(`${error.message}\nAide : node tools/chercher.mjs --aide\n`);
      process.exitCode = 64;
    } else if (error instanceof DataError) {
      process.stderr.write(`${error.message}\n`);
      process.exitCode = 2;
    } else {
      throw error;
    }
  },
);
