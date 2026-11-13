# Contenu de guidage : formes des fichiers, sources, et ce qu'un humain doit encore vérifier

Établi le 2026-11-11. Ce document accompagne les sept fichiers de `site/contenu/` :
`site/contenu/types-d-actes.json`, `site/contenu/aiguillage.json`, `site/contenu/guides.json`,
`site/contenu/bilan.json`, `site/contenu/vocabulaire.json`, `site/contenu/liens.json`,
`site/contenu/a-propos.json`. Il sert à trois lecteurs : le constructeur de l'interface (§ 1 et § 2), toute
personne qui veut savoir d'où vient une phrase (§ 3), et l'humain qui doit confirmer ce que les programmes
n'ont pas pu voir (§ 4).

Vocabulaire : celui de `CONTEXT.md`. Sigles : **AN** = Archives nationales ; **ANOM** = Archives nationales
d'outre-mer ; **BnF** = Bibliothèque nationale de France ; **SDANF** = Sous-direction de l'accès à la
nationalité française ; **BOGGA** = *Bulletin officiel du Gouvernement général de l'Algérie* ; **JORF** =
*Journal officiel de la République française* ; **OCR** = texte lu par une machine sur une image.

## 0. En bref

- 12 guides, 58 étapes : 26 vues ou établies sur pièce, **32 à
  confirmer** (champ `verifie: false`, note `a_confirmer`).
- 55 gabarits de liens : 32 testés avec une réponse normale, 3 bloqués pour les
  programmes mais attendus corrects pour un humain, **20 jamais vus fonctionner** ; 8
  d'entre eux ne doivent pas être montrés au public (`proposer: false`).
- 10 écrans communs décrits, dont 7 à confirmer.
- Aucun fichier de `site/contenu/` ne contient le nom d'une personne réelle : les exemples de noms sont
  inventés et signalés comme tels.
- Les fichiers JSON sont la source : on les modifie directement. Après toute modification, relancer les tests
  (§ 7) et mettre à jour le § 4 de ce document — un test vérifie que chaque étape, lien et écran non confirmé
  y figure.

Pourquoi tant d'étapes « à confirmer » : le 2026-11-11, le site des inventaires des AN répondait « Erreur
503 » (panne), et Gallica comme Légifrance refusent les programmes. Les guides sont donc écrits à partir des
pages réellement reçues, du code de ces pages, et des pages officielles lues ; tout le reste est marqué.

## 1. Formes des fichiers JSON

Conventions communes aux sept fichiers :

- En tête : `schema` (`"decretas.contenu.<nom>/1"`), `langue` (`"fr"`), `maj` (date `AAAA-MM-JJ`).
- **Bloc de vérification** `verification` : `{ "etat": "verifie" | "partiel" | "non-verifie", "preuves": [chemin, …],
  "note": texte }`. `partiel` = une partie de l'affirmation repose sur une source secondaire ou n'a pas été
  contrôlée ; la note dit laquelle.
- **Preuve** : chemin depuis la racine du dépôt. Soit un fichier (`data/samples/…`, `data/raw/…`, `CONTEXT.md`,
  `.scratch/…`), soit un renvoi à un rapport, de la forme `docs/research/sources-2026-11/<rapport>.md § <section>`
  (ou `…/verification.md § <rapport>`). Les fichiers sous `data/` ne sont pas dans git : ils existent sur le
  poste où la recherche a été faite.
- **Énoncé sourcé** : `{ "texte", "source" (auteur, publication, date, en clair), "preuves": […], "etat" }`.
- **Variables** dans les textes : `{nom}`, toujours déclarées dans le même fichier.
- **Liens** : jamais d'adresse dans un texte. Un champ `liens` (liste) ou `lien` (un seul, ou `null`) contient
  des identifiants de `site/contenu/liens.json`.
- Les citations d'époque et les citations officielles sont entre guillemets français « » ; à l'intérieur d'une
  citation, les guillemets intérieurs sont des guillemets anglais “ ”.

### 1.1 `site/contenu/liens.json` — la seule table d'adresses externes

| Clé | Type | Sens |
|---|---|---|
| `regle` | texte | règle d'usage, à respecter par l'interface |
| `statuts` | objet | les trois statuts et leur explication affichable |
| `origines` | objet | d'où vient la forme de l'adresse, explication affichable |
| `variables` | objet | nom de variable → ce qu'elle contient et comment la remplir |
| `periodiques` | liste | `{cb, titre, sigle, parution, etat_gallica, granularite, preuves, etat}` : valeurs de `{cb}` pour Gallica |
| `volumes_hathitrust` | objet | `{note, preuves, volumes: {année: htid}}` : valeurs de `{htid}` |
| `liens` | liste | les gabarits, voir ci-dessous |

Un élément de `liens` :

| Champ | Type | Sens |
|---|---|---|
| `id` | texte | identifiant stable, cité par les autres fichiers |
| `libelle` | texte | texte du lien pour l'utilisateur |
| `hote` | texte | nom d'hôte, à afficher à côté du lien |
| `gabarit` | texte | adresse avec variables `{inventaire}`, `{notice}`, `{cb}`, `{ark}`, `{vue}`, `{annee}`, `{mois}`, `{jour}`, `{date}`, `{mot}`, `{identifiant}`, `{volume}`, `{feuillet}`, `{htid}`, `{seq}` |
| `variables` | liste | les variables du gabarit (vide si l'adresse est fixe) |
| `exemple` | texte | le gabarit rempli, pour les tests manuels |
| `statut` | texte | `teste-200` \| `bloque-pour-les-robots-attendu-ok-pour-un-humain` \| `non-teste` |
| `date_test` | date ou `null` | date du test ; `null` si `non-teste` |
| `origine` | texte | `teste-par-nous` \| `recopie-d-une-page-officielle` \| `forme-ecrite-par-la-source` \| `deduction` |
| `preuves` | liste | fichiers et sections de rapport |
| `observation` | texte | ce qui a été observé (panne, refus, nombre d'essais) |
| `proposer` | booléen | `false` : ne pas montrer ce lien au public tant qu'un humain ne l'a pas validé |
| `avertissement` | texte ou `null` | phrase à afficher sous le lien quand il n'a jamais été vu fonctionner |
| `repli` | id ou `null` | lien à proposer à côté, en secours |

Remplissage des variables : `{inventaire}` et `{notice}` se recopient tels quels depuis les données (ne pas les
encoder, ne pas les « nettoyer ») ; `{mot}` passe par `encodeURIComponent` ; `{volume}` est le nom exact du
volume dans le dépôt d'Internet Archive, encodé (espace → `%20`) ; `{feuillet}` vient de l'index, jamais d'un
calcul sur le numéro de page.

### 1.2 `site/contenu/types-d-actes.json` — les cartes

Clés : `titre`, `chapeau`, `note_vocabulaire` (l'explication unique du mot « indigène », à afficher en tête de
page), `natures`, `valeurs_publie`, `couvertures` (trois dictionnaires valeur → libellé), `types` (16 cartes,
`T1` à `T16`, dans l'ordre).

Une carte :

| Champ | Type | Sens |
|---|---|---|
| `id`, `cle` | texte | `T1`…`T16` ; clé lisible (`admission-par-decret`…) |
| `titre_court` | texte | titre de la carte |
| `periode` | objet | `{debut: année, fin: année ou null, texte}` |
| `qui` | texte | les personnes concernées |
| `natures` | liste | parmi `decret`, `arrete`, `jugement`, `declaration`, `effet-collectif` |
| `nature_texte` | texte | la même chose en une phrase |
| `fondement` | texte | le texte de droit, avec citation |
| `nominatif` | booléen | l'acte nomme-t-il la personne ? |
| `publie` | texte | `oui` \| `non` \| `partiel` \| `inconnu` \| `sans-objet` |
| `ou_publie`, `ou_conserve` | texte | où |
| `sur_ce_site` | objet | `{couvertures: […], texte, voies: [id de voie], guides: [id de guide]}` ; `couvertures` parmi `recherche-par-nom`, `recherche-guidee`, `hors-site`, `aucun-acte-nominatif` |
| `etablit`, `n_etablit_pas` | listes | énoncés sourcés |
| `a_savoir` | liste de textes | remarques |
| `verification` | bloc | état de la carte |

### 1.3 `site/contenu/aiguillage.json` — l'arbre « Quel acte chercher ? »

Clés : `titre`, `chapeau`, `regle`, `depart` (id de la première question), `questions`, `issues`, `voies`,
`age_minimal` (`{decret: 21, jugement: 25, texte, preuves}`), `epoques_intro`, `epoques`.

- Une **question** : `{id, question, aide, reponses: [{id, libelle, precision?, vers: {type: "question" | "issue", id}}]}`.
  Trois questions au plus sur tout chemin (testé).
- Une **issue** : `{id, titre, message, points: [texte], types: [id de carte], voie: id, voies_secondaires: [id],
  guides: [id], liens: [id], montrer_epoques, montrer_echelle, rappel_jugement (trois booléens), verification,
  vocabulaire?: [id de terme]}`. `vocabulaire` (facultatif) : termes de `vocabulaire.json` que l'issue emploie et
  que la page relie à leur définition (« statut personnel »…).
  `montrer_epoques` : afficher le tableau `epoques` (filtré, si l'on connaît l'année de naissance, sur les années
  ≥ naissance + 21) ; `montrer_echelle` : afficher `echelle` de `bilan.json` ; `rappel_jugement` : afficher
  `rappel_jugement.court` de `bilan.json`. Une issue ou une époque dont `verification.etat` n'est pas
  `verifie` s'affiche avec sa note (« À confirmer : … », ou une phrase générique si la note est vide) : aucun
  énoncé non vérifié n'est montré comme établi.
- Une **voie** : `{id, libelle, sur_ce_site (booléen), description, guides: [id]}`. Douze voies :
  `recherche-par-nom`, `recherche-guidee-images`, `recherche-sur-le-site-des-an`, `bulletin-imprime`, `legifrance`,
  `demande-au-ministere`, `etat-civil-en-algerie`, `declaration-recognitive`, `dossier-aux-archives-nationales`,
  `certificat-de-nationalite`, `verification-d-une-citation`, `hors-perimetre`.
- Une **époque** : `{id, annees: {debut, fin}, libelle, texte, actes_possibles: [id de carte], voie, guides,
  verification}`. Les époques couvrent 1865-1962 sans trou ; `e-jugements` (1919-1962) court en parallèle.

### 1.4 `site/contenu/guides.json` — les guides pas à pas

Clés : `titre`, `chapeau`, `franchise` (phrase à afficher en tête de tout guide), `legende`, `ecrans_communs`,
`guides`.

- Un **guide** : `{id, cas, titre, pour_qui, voie, duree, ce_qu_il_vous_faut: [texte], etapes: […], resultat,
  limites: [texte], suite: [id de guide]}`.
- Une **étape** (tous les champs sont toujours présents, dans cet ordre) :

| Champ | Type | Sens |
|---|---|---|
| `id` | texte | unique dans le guide (`a1`, `a2`…) ; l'étape se désigne `<guide>/<étape>` |
| `titre` | texte | |
| `instruction` | texte | ce qu'il faut faire |
| `ce_que_l_ecran_montre` | texte | ce que l'on doit voir si tout va bien |
| `issues_possibles` | liste | `{si, signifie, faire, ecran?}` : chaque résultat plausible ; `ecran` renvoie à un écran commun |
| `ecrans_communs` | liste d'id | écrans communs à proposer en aide |
| `liens` | liste d'id | liens de l'étape (toujours `proposer: true`) |
| `verifie` | booléen | `true` seulement si l'écran ou le document a été vu |
| `appui` | texte | `ecran-vu` \| `page-officielle-lue` \| `donnees-locales` \| `non-vu` : la meilleure pièce disponible |
| `preuves` | liste | |
| `a_confirmer` | texte ou `null` | présent si et seulement si `verifie` vaut `false` ; à afficher discrètement |

- Un **écran commun** : `{id, titre, ce_que_vous_voyez, ce_que_cela_veut_dire, que_faire, verifie, preuves,
  a_confirmer}`.

Les douze guides : `an-annee-indexee` (cas a), `an-annee-en-images` (b), `an-noms-sur-le-site-des-an` (b-bis),
`bogga-internet-archive` (c), `gallica-a-la-main` (d), `legifrance-jorf` (e), `dossier-pierrefitte` (f),
`attestation-ministere` (g), `jugement-etat-civil-algerie` (h), `declaration-recognitive` (i),
`certificat-nationalite` (j), `numero-a-verifier` (k).

### 1.5 `site/contenu/bilan.json` — les textes du bilan de recherche

| Clé | Forme | Sens |
|---|---|---|
| `principe` | texte | |
| `variables` | objet | nom → sens, pour toutes les variables `{…}` du fichier |
| `resume` | objet | cinq gabarits : `une_correspondance`, `plusieurs_correspondances`, `partielles_seulement`, `partielle`, `aucune` (le message digne quand rien n'est trouvé) |
| `ce_qui_a_ete_fouille` | `{titre, lignes, note}` | `lignes` : `{id, source_id (id d'une source de a-propos.json, ou null), gabarit, variables}` |
| `ce_qui_n_est_pas_couvert` | `{titre, lignes}` | `lignes` : `{id, titre, texte, pourquoi, que_faire, voie, guides, verification}` ; une ligne non `verifie` s'affiche avec sa note « À confirmer » |
| `rappel_jugement` | `{titre, texte, court, guides, verification}` | à afficher dans **tout** bilan |
| `echelle` | `{titre, texte, chiffres}` | `chiffres` : `{id, valeur, libelle, detail, reserve, source, preuves, etat}` ; `detail` et `reserve` s'affichent toujours avec le chiffre, `etat` ≠ `verifie` est signalé |
| `citations_officielles` | `{titre, note, principales, autres}` | citations : `{id, texte, auteur, source, date, a_quoi_sert, precaution, lien, preuves}` ; `texte` s'affiche entre guillemets, mot pour mot ; sur la fiche d'un décret d'avant 1927 (publié au Bulletin officiel), la `precaution` de `an-valeur-de-preuve` s'affiche sous la citation |
| `mises_en_garde` | `{titre, texte, points}` | `points` : `{id, texte, preuves}` |
| `demarches_restantes` | `{titre, lignes}` | `lignes` : `{id, texte, guides}` |
| `ce_que_ce_bilan_n_est_pas` | texte | à afficher en pied de bilan |

Variables : `termes`, `nb_variantes`, `annees_an`, `date_donnees_an`, `annees_bulletin`, `annees_images_seules`,
`annees_noms_non_repris`, `nb_correspondances`, `nb_partielles`, `partielles` (le nombre avec son nom, accordé),
`terme_absent`, `an_notices_reprises`, `an_notices_index`, `annee_naissance`, `tolerance_naissance`, `annee_min`
(année de naissance moins la tolérance, plus 21 : la fenêtre part de la plus ancienne année que la recherche garde).
Si l'année de naissance n'est pas saisie, ne pas afficher la ligne `fenetre-naissance`.

### 1.6 `site/contenu/vocabulaire.json`

Clés : `titre`, `chapeau`, `familles` (id → libellé), `termes`, `sigles`, `formulations`.

- Un **terme** : `{id, terme, definition, a_eviter: [texte], voir: [id de terme], famille, origine}`. `origine`
  vaut `CONTEXT.md` pour les treize termes du glossaire du projet, sinon un renvoi de rapport.
- Un **sigle** : `{sigle, developpe, explication}`.
- Une **formulation** : `{dire, ne_pas_dire, pourquoi}` — pour une page « Les mots de ce site ».

`a_eviter` et `ne_pas_dire` contiennent, par définition, des mots proscrits : ne pas les afficher comme du
texte courant.

### 1.7 `site/contenu/a-propos.json`

Clés : `titre`, `objet`, `promesse`, `sources`, `ce_que_le_site_ne_fait_pas` (`[{id, texte}]`), `vie_privee`
(`{texte, verification}`), `points_ouverts` (`[{id, titre, texte, etat: "ouvert" | "assume", preuves}]`),
`methode` (`{texte, preuves}`).

Une **source** : `{id, nom, ce_que_nous_utilisons, date_des_donnees, licence: [{texte, source, lien, preuves}],
credit, credit_exemple, credit_regle, liens, verification}`. `credit` est la mention exigée, à afficher sur
toute fiche tirée de cette source :

- `archives-nationales` : « Archives nationales de France ; cote ; lieu de conservation ; date » ;
- `gallica` : « Source gallica.bnf.fr / BnF » ;
- `internet-archive` : la publication d'abord, puis Internet Archive et l'identifiant du dépôt.

## 2. Règles pour l'interface

1. N'afficher une adresse externe qu'à partir de `site/contenu/liens.json`, avec son statut. Ne jamais montrer
   un lien `proposer: false`.
2. Sous un lien qui porte un `avertissement`, afficher l'avertissement et le lien de `repli`.
3. Sous une étape `verifie: false`, afficher discrètement « À confirmer : » suivi de `a_confirmer`.
4. Tout bilan de recherche affiche `rappel_jugement`, même quand il y a des correspondances.
5. Quand rien n'est trouvé, afficher `resume.aucune` tel quel : ne pas le raccourcir en « aucun résultat ».
6. Le mot « indigène » n'apparaît que dans des citations ; `note_vocabulaire` l'explique une fois.
7. Pour une correspondance tirée de l'index des AN, le lien principal est `an-notice` rempli avec l'identifiant de
   la notice **du décret** (c'est elle qui porte toujours le lien d'images), et le lien `an-inventaire` à côté.
8. Ouvrir les liens externes dans un nouvel onglet. Gallica dans un cadre intégré : possibilité non établie, ne
   pas la supposer.
9. Les textes ne promettent aucun moyen de signaler une erreur : il n'en existe pas encore.

## 3. Sources, par famille de phrases

Statut : **vérifié** = lu dans un fichier enregistré ou recompté sur les données locales ; **partiel** =
source secondaire, ou une partie non contrôlée ; **non vérifié** = à tenir pour une hypothèse. Quand
`docs/research/sources-2026-11/verification.md` corrige un rapport, c'est la correction qui est suivie
(colonne « Correction appliquée »).

### 3.1 Droit et types d'actes (`types-d-actes.json`, `aiguillage.json`, `vocabulaire.json`)

| Famille de phrases | Source | Fichier témoin | Statut | Correction appliquée |
|---|---|---|---|---|
| Tous les Algériens sont français depuis 1865 ; l'acte donne la qualité de citoyen (sénatus-consulte, art. 1er à 3) | `legal-types.md` § 1, § 3 (T1-T3) | `data/samples/legal-types/wikisource-sc-1865.txt` | vérifié | — |
| Âge de 21 ans pour le décret | décret n° 137 du 24 octobre 1870, art. 1er | `data/samples/legal-types/mjp-decrets-1870-10-24.txt` | vérifié | — |
| Décret Crémieux, décision du juge de paix de 1871 | `legal-types.md` § 3 (T4, T5) | même fichier | vérifié | — |
| « près de 35 000 personnes » | commentaire de la décision n° 2012-259 QPC | `data/samples/legal-types/cc-2012-259-qpc-commentaire.txt` | vérifié | — |
| Loi du 26 juin 1889 | Patrick Weil, 2003 | `data/samples/legal-types/weil-2003-HEC03-03.txt` | non vérifié sur le texte de la loi | la règle « né après 1868 » du rapport n'est pas reprise |
| Loi du 4 février 1919 : 25 ans, conditions, jugement, mention en marge, Territoires du Sud | `legal-types.md` § 3 (T7) | `data/samples/legal-types/mjp-loi-1919-02-04.txt` | vérifié | — |
| Loi du 18 août 1929 (femmes) | commentaire QPC ; Cass. 8 juin 2004 | `data/samples/legal-types/cc-2012-259-qpc-commentaire.txt` | partiel (existence et objet seulement) | — |
| Femmes admises par décret avant 1929 | comptage local | `data/samples/legal-types/local-an-title-families.json` | vérifié | « une cinquantaine » (51) ; les détails par année du rapport ne sont pas repris |
| Titres des AN : « naturalisations algériennes » jusqu'en 1930, « admission aux droits de citoyen français » à partir de 1931 ; décrets de 1944 | `legal-types.md` § 4 ; `an-local.md` § 3 | `data/samples/legal-types/local-an-title-families.json`, `data/raw/an/FRAN_IR_058662.xml` | vérifié | 8 titres contiennent le mot du droit colonial, non 5 |
| Ordonnance du 7 mars 1944 : citoyens « à titre personnel », statut inchangé | texte ; Cass. 8 juin 2004, n° 02-10250 | `data/samples/legal-types/mjp-ordonnances-cfln-1944.txt`, `data/samples/legal-types/cc-2012-259-qpc-dossier-documentaire.txt` | vérifié | « aucune liste publiée » est présenté comme non trouvé, pas comme établi |
| Loi du 7 mai 1946, statut de 1947 | textes | `data/samples/legal-types/mjp-loi-1946-05-07.txt`, `data/samples/legal-types/wikisource-statut-1947.txt` | vérifié | — |
| Jugement de renonciation après 1946 | réponse ministérielle de 1991 | `data/samples/legal-types/senat-qe-16358-1991.txt` | partiel (forme, mention, conservation inconnues) | — |
| Loi du 28 juillet 1961 (M'zab) | texte ; source secondaire pour le nombre | `data/samples/legal-types/mjp-loi-1961-805.txt` | partiel | — |
| Déclaration de 1962-1967 : qui, quand, où elle est conservée | ordonnance n° 62-825 (dossier QPC) ; page des AN ; page des ANOM ; réponse de 2018 | `data/samples/legal-types/cc-2012-259-qpc-dossier-documentaire.txt`, `data/samples/an-remote/an-dossiers-naturalisation.body`, `data/samples/other-sources/anom/site-ce-que-vous-ne-trouverez-pas.html`, `data/samples/other-sources/an-questions/QANR5L15QE6380.html` | partiel | début au 21 juillet 1962 (non au 1er janvier 1963) ; deux rédactions officielles de la date limite, d'où « mars 1967 » |
| Réintégration après 1962 | réponse ministérielle de 2018 | `data/samples/other-sources/an-questions/QANR5L15QE6380.html` | non vérifié au-delà de cette réponse | — |
| 1940-1943 (Vichy) | Florence Renucci | `data/samples/legal-types/hal-00599296-decret-cremieux.txt` | non vérifié (source secondaire) | « voie administrative » non repris |
| Les enfants mineurs suivent le père ; pas l'épouse d'office | Weil, note 77 ; loi de 1919, art. 2 | `data/samples/legal-types/weil-2003-HEC03-03.txt`, `data/samples/legal-types/mjp-loi-1919-02-04.txt` | partiel (arrêt de 1907 non lu) | — |
| Le service militaire ne change rien ; registres matricules des ANOM | loi de 1919, art. 2 ; fiche des ANOM | `data/samples/other-sources/anom/site-algerie-francaise.html` | vérifié | — |
| Rôle du Conseil d'État après 1870 | — | — | **non écrit** : question ouverte | la « correction » du rapport n'est pas reprise |

### 3.2 Ce qui fait preuve (`bilan.json`, cartes, guides g, h, j, k)

| Famille de phrases | Source, date | Fichier témoin | Statut |
|---|---|---|---|
| « Les décrets publiés au Journal officiel sont les seuls à avoir valeur de preuve. » ; tableau « Si vous recherchez… » | AN, page « Dossiers de demande de naturalisation », lue le 2026-11-11 | `data/samples/an-remote/an-dossiers-naturalisation.body` | vérifié |
| « …les décrets ont été régulièrement publiés… doit être présumée. » | ministère de la Justice, JO Sénat du 24 octobre 1991, p. 2352, question n° 16358 | `data/samples/other-sources/senat/qSEQ910716358.html` | vérifié |
| « …la mention en marge… ne saurait s'y substituer. » ; « une attestation peut être délivrée… » | ministère de la Justice, JO Sénat du 9 mars 2006, p. 723, question n° 17313 | `data/samples/other-sources/senat/qSEQ050417313.html` | vérifié (réponse de 2006, question de 2005) |
| « …ne conservent pas d'archives probantes… » | ANOM, fiche « Algérie française » | `data/samples/other-sources/anom/site-algerie-francaise.html` | vérifié (la phrase est sur cette fiche, non sur l'autre page) |
| « …dossiers d'instruction… pas des preuves de nationalité. » ; « Archives conservées en Algérie. » | AN, même page | `data/samples/an-remote/an-dossiers-naturalisation.body` | vérifié |
| Une recherche négative du ministère ne produit aucun document | CADA, avis n° 20183182 | `data/samples/other-sources/divers/cada-20183182.html` | vérifié |
| Pièces demandées pour un certificat : originaux, copies intégrales (« Les extraits d'acte ne sont pas admis ») | notice n° 52373*02 | `data/samples/other-sources/servicepublic/notice-16237-02.pdf` | vérifié |
| « les actes de naissance de tous les ascendants », « en remontant jusqu'au 1er ascendant français inclus » | fiche F1051 « Vérifié le 20 juin 2025 » — **et non la notice**, qui parle seulement d'une « chaîne de filiation » jusqu'au premier ascendant français | `data/samples/other-sources/servicepublic/F1051-cnf.html` | vérifié (attribution corrigée à la revue) |
| Cass. 8 juin 2004 : « ne pouvant résulter que d'un décret ou d'un jugement… » | dossier documentaire de la décision n° 2012-259 QPC | `data/samples/legal-types/cc-2012-259-qpc-dossier-documentaire.txt` | vérifié |

### 3.3 Chiffres d'échelle (`bilan.json`, clé `echelle`)

| Chiffre | Source | Fichier témoin | Statut | Correction appliquée |
|---|---|---|---|---|
| « un peu plus de 6 000 » ; 3 572 par décret ; 2 395 par jugement | Weil, 2003, note 77 | `data/samples/legal-types/weil-2003-HEC03-03.txt` | vérifié | formulation de l'auteur, non « environ 6 000 » |
| 1 453 de 1870 à 1919 ; 31 496 ; 512 ; 203 | Blévis, citée par Renucci (note 10) | `data/samples/legal-types/renucci-2004-accession-indigenes.txt` | partiel (seconde main) | — |
| 1 204 jugements pour 1 547 demandes, 760 décrets (1919-1930) | Weil, p. 12 | même fichier que la première ligne | vérifié | — |
| 250 admis au total en 1875 pour 2 500 000 | Roussel, 1875 | `data/samples/legal-types/wikisource-condition-naturalisation-indigenes.txt` | vérifié | chiffre **cumulé**, non « en 1875 » |
| 1 039 = 634 + 405 (116 + 289), « plus d'un tiers » | Roussel, 1875 | même fichier | vérifié | le tiers porte sur les 405, non sur les 289 |
| 1 210 000 et 60 000 (1944) ; « quelques dix mille » (1962) | Weil, p. 13-14 | `data/samples/legal-types/weil-2003-HEC03-03.txt` | vérifié | — |
| 35 sur 846 (1873), 30 sur 1 561 (1888) | prototype de lecture du bulletin | `data/samples/internet-archive/derived/bogga-1873-decrees.json`, `data/samples/internet-archive/derived/bogga-1888-decrees.json` | vérifié | rappel d'environ 90 % en 1873, 75 % sur la pire page |
| Le compte de 1 486 notices du rapport `an-local.md` | — | — | **non repris** : classe heuristique | — |

### 3.4 Couverture des inventaires des AN (`aiguillage.json` époques, `bilan.json`, guides a, b, b-bis)

| Famille de phrases | Source | Statut | Correction appliquée |
|---|---|---|---|
| Années dont les noms sont saisis : 1883-1898, 1913-1927, janvier-mars 1928, 1929-1932 | `verification.md` § an-local, § legal-types | vérifié | 1928 n'est saisie que pour le premier trimestre |
| Années en images seules : 1899-1912, avril-décembre 1928, 1933-1948 ; fragments 1900, 1905, 1909, avril-juin 1928 | idem ; `an-local.md` § 5 | vérifié | — |
| 85 inventaires, 21 557 décrets, 371 867 notices de personnes ; 9 596 décrets sans noms dans les années en images | `verification.md` § an-local | vérifié | 9 596 (non 9 606) ; 85 fichiers (non 86) |
| 636 / 53 / 103 / 150 / 80 décrets à lire ; 12 personnes en général, 299 au plus | `an-local.md` § 5.2 ; `verification.md` § an-local | vérifié | — |
| Plus d'un décret sur trois partage date et titre avec un autre (1933-1948) | `verification.md` § an-local (1 757 sur 4 698) | vérifié | l'exemple D4 du rapport `an-remote.md` n'est pas repris |
| Cote « BB/11 » portée par erreur sur 260 décrets (fin 1927, 1931) | `verification.md` § an-local | vérifié | — |
| Numéro de document : donné pour 1883-1891 (pas toujours) et 1899-1930 ; absent pour 1892-1897, presque toujours pour 1898, et de 1931 à 1948 | recompté à la revue sur `data/samples/an-local/decrets_tous.csv` (colonne `document`, par année) | vérifié | les guides a et b ne demandent plus de comparer un numéro qui n'existe pas |
| Taille d'un décret : médiane 12, moyenne 18, maximum 299 | `an-local.md` § 5.2 | vérifié | « une douzaine en moyenne » corrigé |
| Numéro de dossier connu, cote inconnue : environ une personne sur vingt | `verification.md` § an-remote (21 082 notices) | vérifié | branche ajoutée au guide f |
| Ordre de lecture des décrets de 1933-1948 | `an-local.md` § 5.3 | partiel : fondé sur les titres ; aucun décret de ces années n'a été ouvert | les décrets « (indigènes algériens) » de 1934 et 1937 sont cités |
| Projet « Devenir français » : 99 %, interrompu le 23 septembre 2026 | `an-remote.md` § 10 | vérifié (`data/samples/an-remote/giro-devenir-francais.body`) | — |

### 3.5 Site des AN : écrans (`guides.json`, guides a, b, b-bis, f)

| Famille de phrases | Source | Fichier témoin | Statut |
|---|---|---|---|
| Page d'inventaire : titre, trois onglets, champ « Rechercher dans l'inventaire » et ses trois options, bloc de connexion | `an-remote.md` § 3.2 | `data/samples/an-remote/IR-057268-consultation.body` | vérifié (HTML reçu ; rendu dans un navigateur non regardé) |
| Écran « SIA - Erreur 503 » ; attente sans réponse ; 502 | `an-remote.md` § 2 | `data/samples/an-remote/A-ud-https.body`, `data/samples/an-remote/requests.jsonl` | vérifié |
| Page d'une notice, emplacement des images, visionneuse, résultat d'une recherche, onglets 2 et 3 | `an-remote.md` § 8, § 13 | — | **non vérifié** (panne) |
| Disposition d'un décret : en-tête, tampon, paragraphes, numéro en marge, mentions manuscrites | `an-remote.md` § 5 | `data/samples/an-remote/giro-tutoriel-654.pdf` | vérifié pour janvier-février 1932 seulement |
| Disposition des décrets de 1899-1912 (manuscrits ?) et d'un décret d'admission d'Algériens | — | — | **non vérifié** |
| Dossier : nature, réservation « par extrait », délais, 5 par semaine, reproduction à distance | `an-remote.md` § 7 | `data/samples/an-remote/an-dossiers-naturalisation.body`, `data/samples/an-remote/an-extraits-de-cote.body`, `data/samples/an-remote/an-reutilisation.body` | vérifié pour les textes ; écrans non vus ; tarif non lu |
| Les dossiers ne sont pas numérisés | `verification.md` § an-remote | — | présenté comme « rien ne dit qu'ils le soient » |

### 3.6 Réutilisation et licences (`a-propos.json`, guide b-bis, `bilan.json`)

| Famille de phrases | Source | Fichier témoin | Statut |
|---|---|---|---|
| Réutilisation libre et gratuite, mention d'origine, crédit en quatre éléments, RGPD | portail des AN | `data/samples/an-remote/an-reutilisation.body`, `data/samples/an-remote/an-mentions-legales.body` | vérifié |
| « Les inventaires… sont librement réutilisables (hors introduction) » | portail des AN, « Ouverture des données » | `data/samples/an-remote/an-ouverture-donnees.body` | vérifié |
| Mention « usage privé » des inventaires | inventaires | `data/samples/an-remote/IR-057268-consultation.body` (82 exports sur 85) | texte vérifié ; **portée : interprétation, à faire confirmer par écrit** |
| Clause Filae ; indexation 1898-1912 et 1928 engagée avec Filae | inventaire racine et inventaire de 1899 | `data/raw/an/FRAN_IR_057397.xml`, `data/raw/an/FRAN_IR_057213.xml` | texte vérifié ; **qui a saisi chaque année : non établi** |
| Métadonnées de la BnF sous Licence Ouverte ; mention « Source gallica.bnf.fr / BnF » | BnF | `data/samples/gallica/bnf-www-conditions-reutilisations.html` | vérifié pour les métadonnées ; conditions des contenus de Gallica **non relues ce jour** |
| Droits déclarés des dépôts d'Internet Archive | notices des dépôts | `data/samples/internet-archive/raw/metadata/1922-t.-62.json`, `data/samples/internet-archive/raw/metadata/algeria_bogga_13_1873.json` | vérifié |
| La recherche ne quitte pas le navigateur | architecture décidée | — | **engagement de conception, à contrôler sur le site construit** |

### 3.7 Bulletin imprimé sur Internet Archive (guide c)

| Famille de phrases | Source | Statut | Correction appliquée |
|---|---|---|---|
| Années présentes : 1861, 1863-1886, 1888 ; 1862 et 1887 non trouvées | `internet-archive.md` § 2 | vérifié pour la recherche par titre | « non trouvées » plutôt que « absentes » |
| Forme des notices en 1869, 1873, 1888 ; formule d'en-tête ; rubrique ; classement par département | `internet-archive.md` § 4 | vérifié (texte OCR, deux pages regardées) | — |
| Erreurs d'OCR (1 lu 4, « ben » lu « bon ») | `internet-archive.md` § 4.4 | vérifié | — |
| Table alphabétique en fin de volume, entrée « NATURALISATION » | `internet-archive.md` § 4.1 | vérifié sur le texte OCR de 1873 et 1888 | la page de la table de 1888 n'a pas été regardée en image |
| Ligne « CERTIFIÉ CONFORME » en fin de livraison | idem | vérifié | des dates lues par la machine sont fausses : l'image fait foi |
| Délai décret → livraison | `verification.md` § internet-archive | partiel | 1888 : environ 40 à 116 jours (le « 35 » était un artefact) |
| Liens de page | `internet-archive.md` § 6 | vérifié (200, image contrôlée) ; liseuse non regardée dans un navigateur | — |
| HathiTrust : 17 volumes 1861-1877 | `internet-archive.md` § 3.1 | liste vérifiée ; liseuse non vue | — |

### 3.8 Gallica (guide d) et Légifrance (guide e)

| Famille de phrases | Source | Statut |
|---|---|---|
| Gallica refuse tous les programmes ; la BnF l'annonce | `gallica.md` § 1-3 | vérifié |
| CAPTCHA depuis le 18 décembre 2025 | `data/samples/gallica/bnf-www-captcha-gallica.html` | vérifié (annonce) ; écran non vu |
| Titres, années de parution, lacunes (1907, 1890) | catalogue de la BnF, `gallica.md` § 6 | vérifié pour le catalogue ; état réel en ligne non vu |
| Découpage en numéros | `verification.md` § gallica | vérifié sur échantillon ; corrigé (numéro simple ou paire, volume semestriel rare) |
| Formes des adresses (`/date`, `/date<année>`, `/f<n>.item`…) | `gallica.md` § 5 ; `verification.md` § gallica | **aucune n'a répondu 200** ; seule `/date` a été demandée (403) et figure sur une page officielle des ANOM |
| Forme d'une notice au JORF en 1927 | `gallica.md` § 7 | seconde main, non vue ; présentée comme telle |
| *Liste alphabétique* : numérisée, sur place seulement ; PDF 1900-1969 à Pierrefitte | catalogue de la BnF ; *La Revue française de Généalogie*, 20 novembre 2023 | vérifié ; contenu pour les Algériens inconnu |
| Les cinq étapes Légifrance ; « depuis 1924 » ; pas de signature avant le 2 juin 2004 | fiche F33626, « Vérifié le 23 octobre 2026 » (`data/samples/other-sources/servicepublic/F33626-trouver-decret.html`) | texte vérifié ; écrans non vus |
| Présence des admissions d'Algériens au JORF | — | **non constatée** : dit tel quel dans le guide |
| Délai de 10 à 11 jours (1927, 1936) | `verification.md` § gallica | deux cas, rapprochés des inventaires locaux |

### 3.9 Démarches (guides g, h, i, j, k)

| Famille de phrases | Source | Statut |
|---|---|---|
| Coordonnées de la SDANF | annuaire officiel, modifié le 28 septembre 2026 (`data/samples/other-sources/servicepublic/annuaire-sdanf-167318.html`) | vérifié ; deux variantes officielles signalées |
| Modèle de demande d'attestation | proposition du rapport `other-sources.md` § 5.1 | **non vérifié** : aucune page officielle ne décrit la démarche |
| Démarche en Algérie (copie intégrale, tribunal) | renvois des AN et des ANOM ; loi de 1919 | renvois vérifiés ; **démarche non vérifiée** ; aucune adresse en `.dz` n'est publiée |
| Déclarations de 1962-1967 : SDANF, archives départementales, exemple du Rhône | `other-sources.md` § 6.1 | renvois vérifiés ; procédure inconnue |
| Certificat de nationalité : formulaire, gratuité, tribunal | fiche F1051, notice n° 52373*02 | vérifié |
| Un numéro du type « 262-1412 » | consigne du projet ; `other-sources.md` § 7 | aucune source publique ne décrit la vente de tels numéros : le texte dit seulement qu'un numéro seul ne se vérifie pas |
| « Officines », vidéos trompeuses | *La Revue française de Généalogie*, 20 novembre 2023 | vérifié ; donné en lien, sans accusation |

## 4. À FAIRE VÉRIFIER PAR UN HUMAIN

Par ordre d'importance. Pour chaque ligne : ouvrir le lien ou suivre l'étape dans un navigateur, noter ce
que l'on voit, puis corriger le fichier JSON (`verifie`, `a_confirmer`, `statut`, `date_test`, `proposer`) et
cette liste.

### 1. Site des Archives nationales : ouvrir une notice et ses images

C'est le cœur de la promesse : sans cela, une correspondance ne mène pas au décret. À rejouer un jour ouvré, dans un navigateur, sur les exemples du plan de reprise (`docs/research/sources-2026-11/an-remote.md` § 9).

| Étape | Titre | Ce qu'il faut confirmer |
|---|---|---|
| `an-annee-indexee/a2` | Ouvrir la notice du décret sur le site des Archives nationales | Le site des Archives nationales était en panne le jour de nos essais (2026-11-11) : cet écran n'a pas pu être vu. Le lien a la forme écrite par les Archives nationales dans leurs propres inventaires. |
| `an-annee-indexee/a4` | Retrouver le décret dans l'inventaire | Le formulaire de recherche a été vu ; la page de réponses, non. Le site des Archives nationales était en panne le jour de nos essais (2026-11-11) : cet écran n'a pas pu être vu. |
| `an-annee-indexee/a5` | Ouvrir les images du décret | Le site des Archives nationales était en panne le jour de nos essais (2026-11-11) : cet écran n'a pas pu être vu. L'emplacement des images sur la notice n'est connu que par une note de travail, pas par un écran. |
| `an-annee-indexee/a6` | Lire le décret et retrouver la ligne | Disposition vue uniquement sur des captures de décrets de janvier-février 1932 (tutoriel officiel des Archives nationales). Aucune page d'une autre année, ni d'un décret d'admission d'Algériens, n'a encore été vue. |
| `an-annee-en-images/b3` | Ouvrir un décret de la liste | Le site des Archives nationales était en panne le jour de nos essais (2026-11-11) : cet écran n'a pas pu être vu. Le lien a la forme écrite par les Archives nationales dans leurs propres inventaires. |
| `an-annee-en-images/b4` | Si vous êtes sur l'inventaire de l'année : retrouver le décret par sa date | Le champ et ses options ont été vus ; la page de réponses et l'onglet « Détail du contenu », non. Le site des Archives nationales était en panne le jour de nos essais (2026-11-11) : cet écran n'a pas pu être vu. |
| `an-annee-en-images/b5` | Ouvrir les images du décret | Le site des Archives nationales était en panne le jour de nos essais (2026-11-11) : cet écran n'a pas pu être vu. |
| `an-annee-en-images/b6` | Lire toutes les pages du décret | Disposition vue uniquement sur des captures de janvier-février 1932. Aucune page de 1899-1912, de 1928 ni de 1933-1948 n'a encore été vue ; l'ordre des noms sur la page est une déduction de l'ordre des notices. |
| `an-noms-sur-le-site-des-an/n3` | Chercher le nom dans l'inventaire | Le formulaire de recherche a été vu ; la page de réponses, non. Nous ne savons pas si la recherche ignore les accents et les majuscules. |

| Lien | Statut | Proposé au public | Exemple à ouvrir | Observation |
|---|---|---|---|---|
| `an-notice` | non-teste | oui | `https://www.siv.archives-nationales.culture.gouv.fr/siv/UD/FRAN_IR_057220/AP001236` | Forme recopiée des exports XML des Archives nationales (attribut xlink:href de chaque notice). Demandée 8 fois le 2026-11-11 : toujours « Erreur 503 » (panne du site). Jamais vue fonctionner. Les identifiants {inventaire} et {notice} se recopient tels quels, sans les modifier ni les encoder. |
| `an-images-notice` | non-teste | oui | `https://www.siv.archives-nationales.culture.gouv.fr/siv/media/FRAN_IR_057220/AP001236/` | Forme recopiée des exports XML (élément daoloc, barre finale comprise). Demandée 1 fois le 2026-11-11 : « Erreur 503 ». On ne sait pas ce qu'elle ouvre : la notice, une visionneuse, ou autre chose. |
| `an-inventaire-detail` | non-teste | non | `https://www.siv.archives-nationales.culture.gouv.fr/siv/rechercheconsultation/consultation/ir/consultationIR.action?irId=FRAN_IR_057220&details=true&gotoArchivesNums=false&udId=root&auSeinIR=true` | Adresse construite par le script de la page d'inventaire elle-même (bouton de l'onglet). Sa réponse n'a pas été vue. |
| `an-inventaire-archives-numerisees` | non-teste | non | `https://www.siv.archives-nationales.culture.gouv.fr/siv/rechercheconsultation/recherche/ir/rechercheConsultationGlobal.action?irId=FRAN_IR_058673&details=false&gotoArchivesNums=true&searchUdOnly=true` | Adresse construite par le script de la page d'inventaire. Demandée 9 fois le 2026-11-11 pour l'année 1936 : 503 ou 502 (panne). Réponse jamais vue. |

### 2. Gallica : tous les liens et tous les écrans

Gallica refuse les programmes : aucun lien n'a pu être essayé. Un humain doit cliquer une fois les dix liens de `docs/research/sources-2026-11/gallica.md` § 5.4 et noter ce qu'il voit.

| Étape | Titre | Ce qu'il faut confirmer |
|---|---|---|
| `gallica-a-la-main/d1` | Choisir le bon périodique | Les titres et leurs dates de parution sont vérifiés dans le catalogue de la BnF. Que les admissions y paraissent année par année vient des recherches antérieures et d'indices (un numéro de 1927, un de 1936), pas d'un contrôle sur les pages. |
| `gallica-a-la-main/d2` | Ouvrir la page du périodique | Gallica refuse les programmes : aucun de ses écrans n'a pu être vu par nous. À faire contrôler par un humain. Un lien de cette forme est donné par le site officiel des Archives nationales d'outre-mer. |
| `gallica-a-la-main/d3` | Choisir l'année, puis le numéro | Gallica refuse les programmes : aucun de ses écrans n'a pu être vu par nous. À faire contrôler par un humain. La façon dont les numéros sont découpés est vérifiée par les notices de la BnF, sur un échantillon. |
| `gallica-a-la-main/d4` | Trouver la page dans le numéro | Gallica refuse les programmes : aucun de ses écrans n'a pu être vu par nous. À faire contrôler par un humain. |
| `gallica-a-la-main/d5` | Lire la liste et retrouver le nom | Aucun décret n'a été vu sur Gallica : forme des listes, ordre des noms et qualité du texte restent à constater. |
| `gallica-a-la-main/d6` | Relever la citation et l'adresse de la page | Forme des adresses de page non contrôlée ; la mention de source est celle que la BnF demandait d'après une copie de ses conditions datée du 2026-01-10, non relue ce jour. |

| Lien | Statut | Proposé au public | Exemple à ouvrir | Observation |
|---|---|---|---|---|
| `gallica-titre` | bloque-pour-les-robots-attendu-ok-pour-un-humain | oui | `https://gallica.bnf.fr/ark:/12148/cb32732402r/date` | Demandé par notre programme pour le Bulletin officiel (cb32732402r) : refus 403 de Cloudflare, comme tout Gallica. Le site officiel des ANOM donne un lien de cette forme vers ce bulletin (écrit « …/cb32732402r/date.item ») et vers le Journal officiel de l'Algérie (cb328020266). |
| `gallica-annee` | non-teste | oui | `https://gallica.bnf.fr/ark:/12148/cb32732402r/date1903` | Forme connue seulement par des adresses vues dans un moteur de recherche, non enregistrées. Aucune réponse 200 obtenue. |
| `gallica-jour` | non-teste | non | `https://gallica.bnf.fr/ark:/12148/cb34378481r/date19270207` | {date} s'écrit AAAAMMJJ. Jamais testé. Sans objet pour le Bulletin officiel de l'Algérie, dont les numéros ne sont datés que de l'année. |
| `gallica-vue` | non-teste | oui | `https://gallica.bnf.fr/ark:/12148/bd6t543303701/f1.item` | {vue} est le rang de l'image dans le numéro, pas le numéro de page imprimé. Forme connue par l'usage, jamais ouverte par nous. |
| `gallica-recherche-dans-numero` | non-teste | non | `https://gallica.bnf.fr/ark:/12148/bd6t543303701/f1.item.r=naturalisation` | Jamais testé sous cette forme. |
| `gallica-recherche-dans-titre-a` | non-teste | non | `https://gallica.bnf.fr/services/engine/search/sru?operation=searchRetrieve&version=1.2&collapsing=false&query=%28gallica%20all%20%22naturalisation%22%29%20and%20arkPress%20all%20%22cb32732402r_date%22` | Le critère « arkPress » ne figure pas dans la documentation de la BnF. Jamais testé. |
| `gallica-recherche-dans-titre-b` | non-teste | non | `https://gallica.bnf.fr/services/engine/search/sru?operation=searchRetrieve&version=1.2&collapsing=false&query=%28gallica%20all%20%22naturalisation%22%29%20and%20%28dc.relation%20all%20%22cb32732402r%22%29` | Fondée sur le champ « dc:relation » des notices de numéros (vérifié) ; la recherche elle-même n'a jamais été testée. |
| `gallica-conditions` | non-teste | oui | `https://gallica.bnf.fr/edit/und/conditions-dutilisation-des-contenus-de-gallica` | Adresse donnée par les pages de la BnF comme licence des contenus de Gallica. Non ouverte par nous (Gallica refuse les programmes). |

| Écran | Titre | Ce qu'il faut confirmer |
|---|---|---|
| `gallica-case-a-cocher` | Gallica : une case à cocher « je ne suis pas un robot » | Annoncée par la BnF ; l'écran lui-même n'a pas été vu, et nous ne savons pas s'il apparaît aussi quand on ouvre directement une page de document. |
| `gallica-acces-refuse` | Gallica : « Sorry, you have been blocked » | Page reçue par notre programme. Nous ne savons pas dans quels cas un humain la rencontre. |
| `page-introuvable` | « Page introuvable », erreur 404 | Cas prévu par prudence : plusieurs gabarits de liens n'ont jamais été ouverts avec succès. |

### 3. De la date du décret à la publication

Le périodique où paraît un décret d'admission après 1888, et le délai de parution, ne reposent que sur deux volumes lus et deux numéros connus de seconde main.

| Étape | Titre | Ce qu'il faut confirmer |
|---|---|---|
| `an-annee-indexee/a8` | Trouver la publication du décret | Délais mesurés sur deux volumes seulement (1873 : 28 à 195 jours ; 1888 : environ 40 à 116 jours) et sur deux numéros du Journal officiel (1927 : 11 jours ; 1936 : 10 jours). Le périodique de publication après 1888 vient des recherches antérieures et n'a pas été contrôlé sur les pages. |

### 4. Légifrance : les cinq étapes de la fiche F33626

Étapes recopiées d'une fiche officielle ; aucun écran vu. À vérifier aussi : qu'un Journal officiel antérieur à 1962 contenant des admissions d'Algériens s'ouvre bien ainsi.

| Étape | Titre | Ce qu'il faut confirmer |
|---|---|---|
| `legifrance-jorf/e1` | Ouvrir Légifrance | Étape recopiée de la fiche officielle F33626 de Service-Public (vérifiée par l'administration le 23 octobre 2026). Légifrance refuse les programmes : nous n'avons pas vu cet écran. |
| `legifrance-jorf/e2` | Indiquer la date de publication | Étape recopiée de la fiche officielle F33626 de Service-Public (vérifiée par l'administration le 23 octobre 2026). Légifrance refuse les programmes : nous n'avons pas vu cet écran. |
| `legifrance-jorf/e3` | Choisir la version papier numérisée | Étape recopiée de la fiche officielle F33626 de Service-Public (vérifiée par l'administration le 23 octobre 2026). Légifrance refuse les programmes : nous n'avons pas vu cet écran. |
| `legifrance-jorf/e4` | Résoudre le petit calcul | Étape recopiée de la fiche officielle F33626 de Service-Public (vérifiée par l'administration le 23 octobre 2026). Légifrance refuse les programmes : nous n'avons pas vu cet écran. |
| `legifrance-jorf/e5` | Consulter le document et aller à la page | Étape recopiée de la fiche officielle F33626 de Service-Public (vérifiée par l'administration le 23 octobre 2026). Légifrance refuse les programmes : nous n'avons pas vu cet écran. |

| Lien | Statut | Proposé au public | Exemple à ouvrir | Observation |
|---|---|---|---|---|
| `legifrance-accueil` | bloque-pour-les-robots-attendu-ok-pour-un-humain | oui | `https://www.legifrance.gouv.fr/` | Adresse donnée par la fiche officielle F33626. Notre programme a demandé une autre page de ce site : refus 403 avec un contrôle anti-robot (« Just a moment... »). L'accueil lui-même n'a pas été demandé. |
| `legifrance-jorf-par-date` | non-teste | non | `https://www.legifrance.gouv.fr/search/jorf?tab_selection=jorf&searchField=ALL&query=&page=1&init=true&datePublication=07%2F02%2F1927` | Les noms de paramètres sont attestés dans quatre liens de Wikimedia Commons ; le chemin « /search/jorf » est une déduction. Ne doit pas être proposé avant d'avoir été ouvert par un humain. |

| Écran | Titre | Ce qu'il faut confirmer |
|---|---|---|
| `legifrance-verification` | Légifrance : « Just a moment... » | Page reçue par notre programme, qui a été refusé. Le déroulement dans un navigateur n'a pas été vu. |
| `legifrance-petit-calcul` | Légifrance : un petit calcul à résoudre | Décrit par la fiche officielle F33626 (« un petit calcul simple ») ; écran non vu. |

### 5. Internet Archive et HathiTrust dans un navigateur

Les liens de page ont répondu et l'image est la bonne ; il reste à regarder la liseuse, sa recherche, et l'exemplaire de 1862 sur HathiTrust.

| Étape | Titre | Ce qu'il faut confirmer |
|---|---|---|
| `bogga-internet-archive/c5` | Chercher vous-même dans un volume : la table en fin de volume | La table alphabétique a été lue dans le texte tiré par la machine des volumes de 1873 et de 1888 ; elle n'a pas été regardée en image, et les autres années n'ont pas été contrôlées. Le lien qui ouvre un volume à sa première page n'a pas été essayé tel quel. |
| `bogga-internet-archive/c1` | Ouvrir la page scannée | Les deux formes de lien ont répondu normalement à notre programme et l'image servie est bien la page attendue (regardée pour 1873 et 1888). La liseuse elle-même n'a pas été regardée dans un navigateur. |
| `bogga-internet-archive/c6` | Chercher un mot dans la liseuse | La recherche dans un volume est vérifiée pour un programme, pas pour un humain dans la liseuse. |
| `bogga-internet-archive/c7` | Années absentes d'Internet Archive | La liste des volumes est vérifiée ; la liseuse de HathiTrust a refusé notre programme et n'a pas été vue. |

| Lien | Statut | Proposé au public | Exemple à ouvrir | Observation |
|---|---|---|---|---|
| `ia-volume` | non-teste | oui | `https://archive.org/details/algeria_bulletinofficieldugouvernementgeneraldelalgerie_13_1873` | Début des adresses testées (« ia-page »), sans la partie qui désigne la page. Non demandé tel quel. |
| `ia-recherche-dans-volume` | non-teste | non | `https://archive.org/details/algeria_bulletinofficieldugouvernementgeneraldelalgerie_13_1873?q=naturalisation` | Forme connue par l'usage ; page animée par JavaScript, jamais testée. Pour un programme, la recherche dans un volume passe par une autre adresse, elle vérifiée. |
| `hathitrust-page` | bloque-pour-les-robots-attendu-ok-pour-un-humain | oui | `https://babel.hathitrust.org/cgi/pt?id=hvd.hl11eu&seq=530` | Notre programme a reçu un contrôle anti-robot (403, « Just a moment... ») ; un navigateur le passe en principe tout seul. Le rapport entre {seq} et la page imprimée n'est pas connu : commencez à seq=1 et feuilletez. L'affichage intégral depuis la France n'a pas été constaté à l'écran. |

| Écran | Titre | Ce qu'il faut confirmer |
|---|---|---|
| `verification-automatique` | Une page « Just a moment... » ou « Vérification en cours » | Page reçue par notre programme sur HathiTrust ; déroulement dans un navigateur non vu. |

### 6. Commander un dossier aux Archives nationales

Procédures recopiées des pages officielles ; aucun écran de compte ni de commande n'a été vu, et le tarif de reproduction n'a pas été lu.

| Étape | Titre | Ce qu'il faut confirmer |
|---|---|---|
| `dossier-pierrefitte/f3` | Créer un espace personnel sur le site des Archives nationales | Lien et conditions lus sur le portail des Archives nationales ; écran d'inscription non vu. |
| `dossier-pierrefitte/f4` | Sur place : réserver le dossier « par extrait » | Procédure recopiée de la page officielle ; aucun écran de commande n'a été vu. |
| `dossier-pierrefitte/f5` | À distance : demander une reproduction | Procédure recopiée de la page officielle ; écrans et tarifs non vus. |

| Lien | Statut | Proposé au public | Exemple à ouvrir | Observation |
|---|---|---|---|---|
| `an-espace-personnel` | non-teste | oui | `https://www.siv.archives-nationales.culture.gouv.fr/siv/compte/espaceperso/creerEspacePerso.action` | Lien donné par le portail des Archives nationales (page sur la reproduction). Écran non vu. |
| `an-fiche-dossier` | non-teste | oui | `https://www.siv.archives-nationales.culture.gouv.fr/siv/cms/content/helpGuide.action?uuid=804c95a9-6550-4b00-b97b-78b0d52816cd&version=6&preview=false&typeSearch=&searchString=` | Adresse recopiée du site des ANOM (le portail des Archives nationales donne la même fiche sous une adresse contenant un identifiant de session, que nous ne reprenons pas). Contenu non lu par nous. |
| `an-fiche-algerie` | non-teste | oui | `https://www.siv.archives-nationales.culture.gouv.fr/siv/cms/content/helpGuide.action?uuid=8dc87e75-c0f2-4b5b-be8e-a6999f19bb6a&version=1&preview=false&typeSearch=&searchString=` | Adresse recopiée du portail des Archives nationales et du site des ANOM. Demandée 2 fois le 2026-11-11 : « Erreur 503 » (panne). Contenu non lu par nous. |

| Écran | Titre | Ce qu'il faut confirmer |
|---|---|---|
| `document-non-numerise` | « Consultable sur place », « non numérisé », « intra muros » | Mention lue dans le catalogue de la BnF pour la « Liste alphabétique » ; nous n'avons pas vu l'écran correspondant sur le site des Archives nationales. |

### 7. Démarches par courrier ou sur place

Aucune page officielle ne décrit ces démarches pour un descendant ; côté algérien, rien n'a pu être lu.

| Étape | Titre | Ce qu'il faut confirmer |
|---|---|---|
| `attestation-ministere/g3` | Écrire la demande | Aucune page officielle lue ne décrit la procédure ni les pièces pour l'attestation d'un décret ancien demandée par un descendant. Ce modèle de demande est une proposition, fondée sur une phrase d'une réponse ministérielle de 2006. |
| `jugement-etat-civil-algerie/h1` | Demander la copie intégrale de l'acte, avec ses mentions en marge | Aucun site officiel algérien n'a pu être lu : nous ne donnons donc aucune adresse en ligne, et nous ne savons pas comment la demande se fait aujourd'hui. Seul ce que prévoyait la loi de 1919 est vérifié. |
| `jugement-etat-civil-algerie/h2` | Lire la marge | Texte de la loi vérifié ; aucune mention réelle n'a été vue. |
| `jugement-etat-civil-algerie/h3` | Demander le jugement au tribunal | Les renvois des administrations françaises sont vérifiés ; la démarche auprès des tribunaux algériens ne l'est pas. La page officielle française donne, pour leurs coordonnées, une adresse web qui n'existe plus. |

| Lien | Statut | Proposé au public | Exemple à ouvrir | Observation |
|---|---|---|---|---|
| `interieur-saisine` | non-teste | oui | `https://contacts-demarches.interieur.gouv.fr` | Adresse donnée par l'annuaire officiel à la ligne « Saisine par voie électronique ». Non ouverte par nous. |

### 8. Liens recopiés de pages officielles, jamais ouverts

Risque faible : l'adresse vient d'une page officielle lue. Un clic suffit.

| Lien | Statut | Proposé au public | Exemple à ouvrir | Observation |
|---|---|---|---|---|
| `bnf-trouver-decret` | non-teste | oui | `https://www.bnf.fr/fr/trouver-un-decret-de-naturalisation` | Adresse donnée par les Archives nationales à qui cherche un décret publié. Non ouverte par nous. |
| `bnf-guide-avant-1924` | non-teste | oui | `https://bnf.libguides.com/c.php?g=659907&p=4659608` | Adresse donnée par la fiche officielle F33626 pour les décrets d'avant 1924. Non ouverte par nous. |

### 9. À faire par le responsable du site, hors écran

1. **Écrire à la direction des publics des Archives nationales** (formulaire de contact du portail) pour obtenir
   une réponse écrite sur deux points : la mention « usage privé » des inventaires, et la clause Filae (qui a
   saisi 1898, janvier-mars 1928 et les fragments de 1900, 1905, 1909 ; la clause s'applique-t-elle à un index
   dérivé des inventaires). Les textes du site disent que ces noms ne sont pas publiés « sans réponse écrite » :
   c'est vrai tant que l'index publié les exclut.
2. **Contrôler la promesse de vie privée** sur le site construit : aucune requête réseau pendant une recherche.
   Tant que ce n'est pas fait, `vie_privee.verification.etat` reste `non-verifie`.
3. **Relire les coordonnées de la SDANF** le jour de la mise en ligne (elles ont changé d'une page officielle à
   l'autre).
4. **Décider d'un moyen de signalement** des liens fautifs : les textes n'en promettent aucun.

## 5. Hypothèses et dépendances envers les autres parties du site

- **Années publiées.** Aucune liste des années lues n'est écrite à la main dans les textes : le bilan, la liste
  des décrets et la page « Comment marche la recherche » les lisent dans les fichiers de couverture générés avec
  les données (`site/data/an-meta.json`, `site/data/bogga-meta.json`). Les textes renvoient au bilan pour le
  détail (« le bilan de recherche dit lesquelles »). Seules les époques `e-1898` et `e-1928` de
  `site/contenu/aiguillage.json` et le guide `an-noms-sur-le-site-des-an` nomment encore une année ; si l'index
  fait autrement, les corriger. (`couverture_de_reference`, une copie des années tenue à la main, a été
  supprimée le 2026-11-12 : elle disait encore « 1873 et 1888 » pour le Bulletin.)
- **Partie de l'index reprise.** Seule la partie de l'index des Archives nationales qui peut concerner
  l'Algérie est exportée (`docs/format-donnees-an.md` § 4) ; le bilan le dit, avec les deux comptes de
  `an-meta.json` (`comptes.exporte.principaux` sur `comptes.corpus.notices_de_personnes`).
- **Liste des décrets des années en images.** Le guide b suppose que le site affiche, par année, la liste des
  décrets (date, titre, cote, numéro de document, identifiants `{inventaire}` et `{notice}`), triée dans
  l'ordre décrit à l'étape `an-annee-en-images/b2`, rejets à part.
- **Cotes « BB/11 » sur un décret.** À signaler dans les données (voir § 3.4).
- **Épouses et enfants.** Les textes disent qu'ils « peuvent n'être cités que dans la notice du mari ou du
  père » ; ils ne disent pas que la recherche les lit. À préciser dans le bilan si l'index les contient.
- **Fiche d'une correspondance.** Les guides a et f supposent que la fiche affiche : le nom tel qu'il est saisi,
  les lignes de la notice (naissance, profession, résidence, épouse, enfants), le titre et la date du décret, sa
  cote, son numéro de document, le numéro du dossier et sa cote, et la mention de crédit.
- **Texte lu par la machine.** Le guide c suppose que, pour le bulletin imprimé, le site montre le texte OCR en
  le signalant comme tel, à côté du lien vers l'image.
- **Périodiques par année.** Le guide d suppose que le site propose, selon l'année du décret, les périodiques de
  `periodiques` (`site/contenu/liens.json`).
- **Vérificateur de date** (guide k, étape `numero-a-verifier/k2`) : le texte renvoie à « la liste de ce site ou
  l'inventaire de l'année » ; il ne suppose pas d'outil particulier.

### Constats de la revue du 2026-11-11 sur les données déjà produites (`site/data/an-meta.json`)

Lus sans les modifier ; ils engagent le constructeur de l'interface.

- **Années.** L'index classe 1883-1898 et 1913-1927, 1929-1932 `indexe`, 1899 `image`, 1900-1912 et 1928
  `partiel`, 1933-1948 `image` ; `filae.annees` = 1898 à 1912 et 1928, `filae.noms_inclus` = `false`. C'est
  l'hypothèse des textes : aucun nom de 1898-1912 ni de 1928 n'est publié. Attention : l'état `indexe` de 1898
  et du premier trimestre de 1928 décrit l'inventaire des AN, pas ce qui est exporté (`noms_exportes`).
- **Liens.** `an-meta.json` porte ses propres gabarits (`liens`, variable `{inv}`, forme `http://`). L'interface
  ne doit afficher que ceux de `site/contenu/liens.json` (`{inventaire}`, `https://`) : `{inv}` → `{inventaire}`,
  `{notice}` → `{notice}`. Les deux tables disent la même chose du statut (notice et images jamais vues).
- **Crédit.** `an-meta.json` lit « date » comme la date de relevé des inventaires (2026-10-16) ; les textes
  donnaient la date du décret. La page des AN écrit « la date des informations » sans préciser : la règle de
  `a-propos.json` (`credit_regle`) demande désormais d'afficher les deux. Lieu : l'index écrit « Pierrefitte »,
  les textes « Pierrefitte-sur-Seine » (les deux formes figurent dans les inventaires).
- **Épouses et enfants.** L'index exporte les noms des épouses (6 519) et des enfants (2 582) : la recherche
  les lit. La mise en garde `epouse-enfants` reste vraie ; l'interface peut dire que ces lignes sont lues.
- **Règles de la recherche.** La ligne `maniere` du bilan (majuscules, accents, traits d'union ignorés ;
  particules non exigées) est un texte par défaut : le moteur (`site/js/recherche/normaliser.js`) fait
  davantage (rapprochement de graphies voisines, saisie en arabe). Le bilan affiché doit décrire les règles
  réellement appliquées ; ce point n'a pas été contrôlé ligne à ligne.

## 6. Ce qui n'est pas fait

- Aucune étape n'a été rejouée dans un navigateur : ce travail s'est fait sans accès aux sites sources.
- Pas de traduction (ni arabe, ni tamazight) : les textes sont en français seulement.
- Pas de guide pour les bases des ANOM (état civil européen, registres matricules) : leurs liens ont échoué
  pour un programme et sont peut-être morts ; les textes renvoient aux deux pages des ANOM qui les présentent.
- Pas de guide pour les portails associatifs ou commerciaux (GAMT, Cercle de généalogie juive, Filae) : deux
  liens d'association seulement, présentés comme des indices.
- Les fiches d'aide des AN sur l'Algérie et sur les dossiers n'ont pas été lues (panne) : elles sont données en
  lien, pas résumées.
- Les textes de plusieurs lois (1889, 1929, 1940, décret n° 62-1475) n'ont pas été lus : les cartes le disent.

## 6 bis. Revue contradictoire du 2026-11-11 : ce qui a été corrigé

1. **Citation mal attribuée.** La phrase sur « les actes de naissance de tous les ascendants » était attribuée,
   dans huit cartes, à la notice n° 52373*02 ; elle est sur la fiche F1051. Source et preuves corrigées.
2. **Deux vrais numéros de dossier** (chacun désigne une personne réelle des inventaires) servaient d'exemples
   dans `guides.json` et `vocabulaire.json`, et l'exemple « inventé » coïncidait avec un numéro réel. Remplacés
   par « 0000 X 12 », « 0000 X 19 », « 0000 X 31 », absents des inventaires et déclarés inventés.
3. **Étape `bogga-internet-archive/c5`** marquée vérifiée alors que la table n'a été lue que dans le texte de la
   machine et que son lien n'a jamais été ouvert : passée à `verifie: false`. Appui de `c3` et `c4` ramené à
   `donnees-locales` (aucune page ni image enregistrée ne les fonde).
4. **« Un peu plus de 6 000 »** : chiffre d'un historien, qui ne compte pas les décrets de 1915-1919 ni de
   1943-1962 ; désormais attribué à Patrick Weil dans les trois textes qui le donnent.
5. **Lacune de 1907** rappelée partout où il est écrit que le bulletin de 1889-1926 est sur Gallica.
6. **Numéro de document** : voir § 3.4 ; les guides a et b, et le glossaire, sont corrigés, avec le cas « même
   date, même titre, pas de numéro » (1933-1948) : lire les deux décrets.
7. **Généralisations** ramenées à ce qui a été lu : découpage du Bulletin officiel sur Gallica (deux notices),
   table alphabétique (1873 et 1888), désignation sans nom de famille (1869-1873).
8. **Glossaire** : « Sans effet sur le passé » (réintégration) retiré, faute de source lue.
9. **Crédit des AN** : voir § 5. **Projet « Devenir français »** : « interruption provisoire annoncée le
   23 septembre 2026 », et non « interrompu ». **Taille d'un décret** : médiane 12, moyenne 18.

Chaque correction a son test dans la classe `ReviewRegressionTest` de `tests/contenu/test_contenu.py`. Le
test `test_quotations_are_found_in_their_own_evidence` relit, quand `data/samples` est présent, chaque citation
d'au moins 30 caractères dans les fichiers donnés pour preuve (les PDF demandent l'outil `pdftotext` ; sans lui,
l'énoncé concerné est sauté).

## 7. Tester

Depuis la racine du dépôt :

```bash
python3 -m unittest discover -s tests -t .
```

- `-m unittest` : lance le module de tests de la bibliothèque standard ;
- `discover` : cherche les fichiers de tests ;
- `-s tests` : dossier où chercher ;
- `-t .` : racine du projet, pour que les imports fonctionnent.

Pour ce seul contenu : `python3 -m unittest tests.contenu.test_contenu` (le nom du module à la place de
`discover`). Les tests de `tests/contenu/test_contenu.py` vérifient les formes décrites au § 1, tous les
renvois entre fichiers, la table de liens, les règles de vocabulaire (pas de « référence » hors citation, le
mot du droit colonial toujours entre guillemets, aucune conclusion du type « n'a pas été admis »), l'absence
d'adresse en `.dz`, les seules coordonnées officielles admises, l'existence des fichiers de preuve, et la
présence dans ce document de tout ce qui reste à confirmer. Ils ne vérifient pas que les phrases sont vraies :
c'est l'objet des § 3 et § 4.
