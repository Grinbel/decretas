# `site/js/` — the interface, and where to plug the next pages

Plain ES modules, no framework, no build step, no dependency. The browser loads `js/app.js`;
Node loads the same files for the tests (`site/js/package.json` only says "these `.js` files
are ES modules").

Read this first if you are about to add a page: **the seams are the router, the view
registry, and four shared components** (guide steps, external link, card, notice).

## 1. The seams, in one screen

### Add or replace a page

A page is a **view**: an object with `titre()` and `monter()`, registered in `js/app.js`
under the first segment of its address. Every page of the site is a real view now; there is no
placeholder left.

```js
// js/vues/quel-acte.js
import { h } from '../composants/dom.js';

export const vueQuelActe = {
  // document title, without the site name
  titre: (route, { T }) => T.quelActe.titre,

  // build the page into <main>; may return a clean-up function
  monter(conteneur, route, { T, contenu, donnees, aller }) {
    conteneur.append(h('div', { class: 'vue' }, h('h1', null, T.quelActe.titre)));
    contenu.charger('aiguillage').then((arbre) => { /* … */ });
    return () => { /* stop timers, unsubscribe */ };
  },

  // optional: same page, other parameters — redraw in place and return true
  // (return false, or leave it out, to be unmounted and mounted again)
  actualiser(route, contexte) { return false; },

  // a page that draws itself after a download says so, and calls contexte.finDeRendu() once drawn
  asynchrone: true,
};
```

**Where the reader lands.** A page never moves the focus or the scroll by itself after its
download: it calls `finDeRendu(cible?, { ancre })` (from the context), and `app.js` decides —
back in the history: the scroll, the open cards and the link followed are put back
(`logique/position.js`, kept in `history.state`); after a navigation inside the site: the
focus goes to `cible` (default: the `h1`); on the first page of a visit: nothing moves, unless
`ancre: true` says the address names a place in the page (`#/actes/T7`). A page that fails
because a file did not come draws `echecDePage(zone, { T, erreur, remonter, finDeRendu })`
(`composants/echec.js`): one title, one message, one « Réessayer » that draws it again.

```js
// js/app.js
import { vueQuelActe } from './vues/quel-acte.js';
enregistrer('quel-acte', vueQuelActe);
```

Then add the new module (and the modules it imports) to the `modulepreload` list of
`site/index.html`: `tests/js/ui-coquille.test.mjs` fails until the list matches the imports.

| Address | View |
|---|---|
| `#/` | `vues/accueil.js` — home = the search |
| `#/recherche?q=…&ne=1876&tol=10&x=…&v=…` | `vues/recherche.js` — results and bilan |
| `#/notice/an/<inventaire>/<notice>[?m=<rank>]`, `#/notice/bogga/<year>/<leaf>/<rank>` | `vues/notice.js` — one notice |
| `#/quel-acte?r=<answer>,<answer>`, `#/quel-acte/<outcome>[?ne=1900]` | `vues/quel-acte.js` — the decision tree, one question per screen; the answers are the address |
| `#/guides`, `#/guides/<id>?inventaire=…&notice=…&annee=…` (or `?annee=…&feuillet=…&page=…` for the Bulletin) | `vues/guides.js` — one guide filled for one decree (`logique/parametres-guide.js`) |
| `#/decrets?ne=1876`, `?annees=1899-1912,1933`, `?de=…&a=…&g=…&annee=…`, `#/decrets/lus` | `vues/decrets.js` — the decree browser, the checklist and its printable page |
| `#/numero?t=…` | `vues/numero.js` — the citation checker (`logique/numero.js`) |
| `#/actes[/<T1…T16>][?epoque=…]` | `vues/actes.js` — the 16 cards of `types-d-actes.json` |
| `#/vocabulaire[/<term id>]` | `vues/vocabulaire.js` — the words; other pages link here (`composants/chargement-leger.js#mot`) |
| `#/methode` | `vues/methode.js` — the rules of the search, the coverage tables |
| `#/a-propos` | `vues/a-propos.js` — sources, credits, privacy, open questions |

The **route** given to a view is `{ nom, segments, params }` (`js/routeur.js`):
`#/guides/legifrance-jorf?x=1` → `{ nom: 'guides', segments: ['legifrance-jorf'], params: { x: '1' } }`.
Build addresses with `formerHash(nom, segments, params)`, never by hand. Everything is after
the `#`: a browser never sends that part to a server, so a search can be bookmarked and shared
without being transmitted to the host of these files.

The **context** (third argument, built once in `app.js`):

| Key | What |
|---|---|
| `T` | every string of the interface (`textes/index.js`) |
| `donnees` | the data client (§ 3): `charger()`, `chercher(etat)`, `fiche(ref)`, `decretsAn(filtre)`, `etat()`, `abonner(fn)`, `reessayer()` |
| `leger` | the small data files without the names (`donnees/legeres.js`): `charger()` → the model of `donnees/modele.js` (`decretsAn`, `couverture`, `publicationsDuJour`, `volumeDeLAnnee`) |
| `carnet()` | the checklist « décrets déjà lus » (`donnees/carnet.js`), created on first use |
| `contenu` | the guidance content: `charger('guides')`, `plusieurs('bilan', 'guides')`, `liens()` (the link resolver) |
| `aller(hash, { remplacer })` | navigate; `remplacer: true` does not add a history entry |
| `retourPossible()` | true when "back" stays on the site |
| `finDeRendu(cible, { ancre })` | to call once an asynchronous page is drawn (see « Where the reader lands ») |
| `memoriser(objet)`, `restauration()` | what a page keeps in its history entry for "back" (the search keeps its card windows) |
| `remonter()` | draw the current page again from scratch (the « Réessayer » of a failed page) |

What the shell does for every view: sets `document.title`, marks the current navigation link,
empties `<main>`, scrolls to the top, and — after a navigation inside the site — moves the
focus to the `<h1>` of the new page. **A view draws exactly one `<h1>`.** When a view draws its
title later (after a download), it calls `viserTitre(h1)` itself.

### Shared components (`js/composants/`)

| Component | Call | Use it for |
|---|---|---|
| **Guide steps** | `etapesGuide(guide, { liens, params, legende, ecrans, libelles, paramsParLien, remplacements, niveau })` | the numbered steps of one guide of `guides.json`: instruction, links filled from `liens.json`, « ce que vous devez voir », other outcomes, shared help screens, and the discreet « À confirmer » note of every step whose `verifie` is `false` |
| **External link** | `lienExterne(liens, id, params, { libelle, sansRepli, notesVues })`, `listeDeLiens(liens, ids, params)`, `lienParticulier(liens, url, libelle)` | every address outside the site (§ 4) |
| **Card** | `carte({ titre, niveau, classe, attributs }, ...corps)`, `champs([[label, value], …])` | one self-standing item of a list; the title is a real heading. Cards are never nested |
| **Notice** | `avis({ ton: 'info' \| 'attention' \| 'neutre', titre, role }, ...contenu)` | a boxed message; `attention` for what changes the meaning of a result |
| Search form | `formulaireRecherche({ valeurs, compact, surSoumission, surIntention })` | home (large) and results (compact) |
| Loading status | `etatChargement(donnees, { discret, sansErreur })` | sentence + real progress bar + retry on failure; put it on any page that waits for the index (`sansErreur`: the page shows the failure itself, so that there is one message and one button) |
| Page failure | `echecDePage(zone, { T, erreur, remonter, finDeRendu })` | a file of the site did not come: « Cette page n'a pas pu s'afficher » and « Réessayer » |
| Unverified statement | `aConfirmer(verification)` (in `avis.js`) | the « À confirmer : … » line of a block of the content files whose `verification.etat` is not `verifie` |
| Full notice | `detailFiche(fiche, { liens, guides, vocabulaire, bilan, couverture, niveau })` | every field of a notice, the hint, the publication, « Voir le document », the citation block |
| Result card | `carteResultat(fiche, touches, contexte)` | one notice in a list of results (household on one card) |
| Spellings | `variantes({ graphies, apparentees, etat, ouvert, surBascule })` | « Graphies rapprochées par la recherche » |
| Bilan | `dessinerBilan(composition, contexte)` | the « bilan de recherche » |
| Waiting for the small files | `attendreDonneesLegeres(zone, leger, dessiner, { vivant })` | a sentence while they come, a retry button when they fail |
| A word and its definition | `mot(id, texte)` | a link to `#/vocabulaire/<id>` |
| DOM | `h(tag, attrs, ...children)`, `remplacer`, `icone(nom)`, `nomEcrit(text)`, `texteMixte(text)`, `viserTitre(el)` | see § 5 |

`params` of a guide are the values of the link templates for the notice at hand
(`{ inventaire, notice }` for the Archives nationales, `{ identifiant, volume, feuillet }` for
Internet Archive). Without them a link that needs them is drawn as text ("adresse à composer
selon votre cas"), never as a dead link.

### Styles (`site/css/`)

`base.css` (tokens on `:root`, light and dark, reset, page frame), `composants.css` (one block
per component, same names as the files of `js/composants/`), `vues.css` (one block per page),
`impression.css` (print). Use the tokens (`--encre`, `--accent`, `--e4`, `--t-l`, `--cible`…),
**logical properties only** (`margin-inline`, `padding-block`, `inset-inline-start`,
`text-align: start`) so that a right-to-left language needs no second stylesheet, and give
every control a block size of at least `var(--cible)` (44 px). A page container is
`<div class="vue">`; `.chapeau`, `.note`, `.liens-internes`, `.retour`, `.repli`, `.tableau`,
`.bouton--principal | --secondaire | --lien` are ready.

## 2. Map of the modules

```
js/demarrage.js           classic script (ES5): says so when the modules cannot run (old browser, a file missing)
js/app.js                 entry: shell (header, footer), context, view registration, router
js/routeur.js             analyserHash, formerHash, demarrerRouteur
js/vues/                  registre.js (enregistrer, trouver) · accueil · recherche · notice
                          guides · quel-acte · decrets · numero · actes · vocabulaire · methode · a-propos
js/composants/            DOM building blocks (table above)
js/logique/               pure functions, no DOM — all tested in tests/js/ui-*.test.mjs
  requete.js                state of a search <-> address bar <-> engine query
  menage.js                 correspondences -> cards (household grouping), card windows, highlighting
  explications.js           why a notice matched, in words; engine warnings in sentences
  bilan.js                  the bilan assembled from the engine's report, the coverage, bilan.json
  fenetre-annees.js         « Que faire maintenant ? »: years possible for a birth year
  liens.js                  the ONLY place where a link template becomes an address
  formats.js                numbers, dates, ranges of years, template filling
  aiguillage.js             walking the decision tree, outcomes reachable, periods for a birth year
  decrets.js                reading groups (guide b2), order, window of years, counts
  numero.js                 the FORM of what someone was given (date, file number, call number…)
  parametres-guide.js       accepted parameters of a guide page, from a decree or a Bulletin entry
  position.js               the reader's place kept in history.state (scroll, open cards, link followed)
  verification.js           the « À confirmer » note of a statement of the content files not verified
js/donnees/               the data layer (§ 3)
js/textes/                index.js (T), fr.js (every French string), typographie.js, nombres.js
js/recherche/             the name search engine (docs/moteur-de-recherche.md) — not part of the
                          interface: change it only for a real bug, with a test
```

## 3. The data layer

```
main thread                                   Web Worker (js/donnees/worker.js)
───────────                                   ─────────────────────────────────
donnees/client.js  ── postMessage ──────────▶ donnees/service.js
  charger()                                     downloads the 7 files of site/data/ (same origin)
  chercher(etat)                                builds the name index   (recherche/index.js)
  fiche(ref)                                    answers searches        (recherche/chercher.js)
  decretsAn(filtre)                             joins rows into notices (donnees/modele.js)
donnees/contenu.js  (site/contenu/*.json, small, fetched on demand on the main thread)
donnees/legeres.js  (an-meta, an-decrets, bogga-meta, bogga-volumes, bogga-decrets: about 130 kB
                     compressed, on the main thread, for the pages that need no names)
donnees/carnet.js   (« décrets déjà lus », localStorage: the only storage of the site)
```

- The 10 MB of names are downloaded, parsed and indexed **in the worker**: the main thread
  never holds them and typing never waits for them. The index itself receives only names,
  birth years and row ranks (`occurrencesFromColumns`); the page receives the few notices it
  shows, as plain objects.
- `donnees.charger()` is idempotent. The home page calls it when the name field gets the
  focus, or when the browser is idle (not at all on idle with "data saver" on). Any other
  call (`chercher`, `fiche`…) waits for it.
- `donnees.etat()` → `{ phase: 'repos' | 'chargement' | 'pret' | 'erreur', progression, resume, erreur }`.
  `resume.couverture` is the coverage summary every page should take its years and counts
  from (`modele.js#couverture`): **no year and no count is written in the interface code**.
- `donnees.chercher(etat)` → `{ correspondances, fiches, bilan, apparentees, fidele }` where
  `etat` is `{ texte, annee, tolerance, exclusions, ajouts }` (`logique/requete.js`).
  `correspondances[i].cle` is the key of its card in `fiches` (`an:<principal row>` — one
  household, one card — or `bogga:<row>`).
- A **fiche** of the Archives nationales (`modele.js#ficheAn`): `membres` (principal first,
  then spouse and children, each with `role`, `nom`, `an`, `prec`, `naiss`, `lieu`, `res`,
  `prof`), `dossier`, `coteDossier`, `notice`, `indice` (`{ code, libelle, regle }` — always
  shown under the word « indice »), `decret` (with `couverture` of its year), `publications`
  (the decrees of the printed Bulletin that bear the same date), `ref`.
  A fiche of the Bulletin (`ficheBogga`): `nom`, `texte`, `marqueurs`, `drapeaux`, `page`,
  `feuille`, `decret`, `volume`, `ref`.
- Row ranks change at every rebuild of the data. What may go into an address is `fiche.ref`;
  `donnees.fiche(ref)` finds the notice again.
- `donnees.decretsAn({ annees, classes, etats })` is there for the decree browser.
- Errors are `ErreurDonnees` (`code`: `chargement`, `format`, `worker`, `non-charge`,
  `interne`) and `ContenuIndisponible`; the sentences are in `T.chargement.erreur` and
  `T.erreurs`.

## 4. External links: one table, one component

- An address outside the site is **never written in the code**. It is a template of
  `site/contenu/liens.json`, filled by `logique/liens.js` (`creerLiens(table).resoudre(id,
  params)`), drawn by `composants/lien-externe.js`. The data files call the inventory `inv`;
  the table calls it `{inventaire}`: both names are accepted. Nothing reads the `liens` key of
  `an-meta.json`.
- Variables are checked before they are copied (`FRAN_IR_` + six digits, etc.), free text is
  encoded, and the result must be `https` on the host the table announces; otherwise there is
  no address.
- A link whose `proposer` is `false` is never drawn. A link whose `statut` is not `teste-200`
  is drawn with « Lien non vérifié. » and the sentence of the table (`avertissement`, or the
  generic sentence of `statuts`), plus its `repli`.
- `liens_particuliers` of the data files (an address copied as it is from an inventory) go
  through `lienParticulier`: accepted only on a host the table already knows, always shown as
  never tested. `null` means "no link at all".
- The image of a printed page is the one resource loaded from another site
  (`archive.org`), and only after a click on « Afficher la page imprimée », which says where
  it goes. Its address is the `image_page` template of `bogga-volumes.json`
  (`logique/liens.js#imagePageBulletin`).

## 5. Rules that hold everywhere

- **Text, never markup.** Build the DOM with `h()`; a string reaches the page through
  `textContent` or `setAttribute` only. `innerHTML` and its cousins are refused by a test.
- **Strict CSP** (`site/index.html`): no inline script, style or handler; `connect-src 'self'`.
- **Strings** live in `textes/fr.js`, under the vocabulary of `CONTEXT.md`. A translation is a
  copy with the same keys, registered in `textes/index.js` with its direction. Sentences of
  the content files (`site/contenu/*.json`) are shown as they are.
- **What a source writes is shown as written** (`nomEcrit`, `<q class="source-brute">`);
  French no-break spaces are added to our own sentences only (`textes/typographie.js`).
  Arabic text is marked `lang="ar" dir="rtl"` (`nomEcrit`, `texteMixte`).
- The period word « indigène » only between guillemets. Never "n'a pas été admis", never
  "n'était pas français"; an empty search is never presented as the absence of a decree.
- **Almost nothing is stored**: no cookie, no analytics, no session storage. The state of a page
  is its address. One exception, on purpose and said on the page: the checklist « décrets déjà
  lus » of the decree browser, in `localStorage` under one key, written only when the visitor
  ticks a box, never sent, erased by a button. `donnees/carnet.js` is the only module allowed to
  touch the storage (`tests/js/ui-coquille.test.mjs` checks it). Guide progress boxes are kept in
  memory only.
- **What an address says is never shown as a fact.** A guide opened with `?inventaire=…&notice=…`
  shows the decree it finds in the data, or says it found none; a date or a call number read
  from the address is never displayed.
- **At most about 50 result cards** are in the page (`logique/menage.js#fenetresDeCartes`);
  the full notice of a card is built when the card is opened.
- Everything collapsed on screen is opened for printing (`app.js`, `beforeprint`).

## 6. Tests

From the root of the repository:

```bash
node --test tests/js/
python3 -m unittest discover -s tests -t .
```

- `node --test tests/js/`: `--test` starts Node's built-in test runner; given a directory,
  Node 22 runs `tests/js/index.js`, which loads every `*.test.mjs` (the engine's tests and the
  interface's `ui-*.test.mjs`).
- `python3 -m unittest discover -s tests -t .`: `-m unittest` runs the standard test module;
  `discover` finds the tests; `-s tests` is the directory searched; `-t .` is the project
  root, so that the `decretas` package can be imported.

`tests/js/ui-aide.mjs` holds the synthetic data of the interface tests: every person in it is
invented. No real name may enter `tests/`, `docs/`, `site/js/` or `site/contenu/`.

To look at the pages:

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory site
```

- `-m http.server`: Python's built-in static file server; `8765`: the port;
  `--bind 127.0.0.1`: listen on this machine only; `--directory site`: the folder served.
  Open `http://127.0.0.1:8765/`. (This server does not compress: the index weighs about
  12 MB here, about 3 MB behind a host that sends gzip or brotli.)

The browser checks (screenshots at four widths in both colour schemes, console, network,
keyboard, the journeys of stage 2) are driven by scripts kept outside the repository, under the
git-ignored `data/build/essais-navigateur/` (`ui.mjs`, `etape2.mjs`, `parcours.mjs`).
