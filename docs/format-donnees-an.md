# Données des Archives nationales : format des fichiers du site

Ce document décrit ce que produit `python3 -m decretas.an construire` à partir des inventaires XML-EAD des
Archives nationales (décrets de naturalisation, sous-série BB/34, 1883-1948) :

| Fichier | Contenu | Versionné |
|---|---|---|
| `site/data/an-decrets.json` | les décrets du « palier Algérie » | non (données personnelles voisines) |
| `site/data/an-personnes.json` | les occurrences de noms cherchables du palier Algérie | non (données personnelles) |
| `site/data/an-meta.json` | génération, effectifs, couverture, noms retenus (clause Filae, vie privée), identifiants de liens, crédit | non |
| `data/build/an.sqlite` | **tout** le corpus (21 557 décrets, 371 860 notices de personnes), pour la mise au point | non |
| `data/build/an-decrets.csv` | tous les décrets à plat (`python3 -m decretas.an decrets --csv …`) | non |

Sigles : **AN** Archives nationales ; **EAD** *Encoded Archival Description* (norme XML des inventaires) ; **IR**
instrument de recherche (un inventaire, identifiant `FRAN_IR_xxxxxx`) ; **BB/34** sous-série des décrets ;
**BB/11** sous-série des dossiers de demande ; **RGPD** règlement général sur la protection des données.

Le vocabulaire est celui de `CONTEXT.md` : une notice trouvée ici est un **indice** de recherche solide (elle vient
d'un inventaire officiel) mais ce n'est pas encore une **citation** : il manque la date et la page de la publication
officielle du décret.

## 1. Principes

1. **Le texte brut d'abord.** Chaque champ analysé est accompagné du texte tel qu'il est écrit dans l'inventaire
   (`titre`, `nom`, `naiss`). Rien n'est corrigé en silence : une valeur douteuse est gardée et signalée par un drapeau.
2. **Clé d'une notice = (inventaire, identifiant de notice).** 838 identifiants (`D1`, `D2`…) existent dans
   plusieurs inventaires.
3. **Les liens ne sont jamais inventés, et il n'y a qu'une table de gabarits.** Le lien de la notice et le lien des
   images sont copiés du XML dans la base. Les fichiers du site ne portent que des identifiants ; le lien se
   reconstruit avec la table unique du site, `site/contenu/liens.json`, dont `an-meta.json` ne donne que les
   identifiants d'entrée (§ 5). Tout lien du XML qui ne suit pas la forme habituelle est publié tel quel dans
   `liens_particuliers`. À la construction, chaque lien copié est comparé à cette forme.
4. **Sortie déterministe.** Deux constructions des mêmes entrées donnent des fichiers identiques octet pour octet
   (base SQLite comprise). L'horodatage est isolé dans `an-meta.json` et peut être imposé (`--horodatage`). Seule
   son **année** agit sur les deux autres fichiers : elle fixe le seuil de la règle « vie privée » (§ 6 bis). La base
   SQLite n'en dépend pas.
5. **Un indice n'est pas un fait.** Les colonnes `ind`, `regle`, `nea`, `rea` sont des classements heuristiques,
   avec la règle qui les a produits. Elles ordonnent et expliquent ; elles ne filtrent ni ne prouvent.

## 2. Forme commune des fichiers colonnes

`an-decrets.json` et `an-personnes.json` ont la même forme, compacte :

```json
{"format": "decretas-an-…/1",
 "champs": ["id", "…"],
 "tables": {"nom_de_champ": ["valeur 0", "valeur 1", "…"]},
 "liens_particuliers": {"notice": {}, "images": {}},
 "lignes": [[0, "…"], [1, "…"]]}
```

- `lignes[i][j]` est la valeur du champ `champs[j]` pour la ligne `i`. Une ligne par ligne de texte dans le fichier.
- **`id` vaut toujours le rang de la ligne** (`lignes[i][0] == i`) : `princ` et `dec` sont donc des index directs.
  Ce rang n'est pas stable d'une construction à l'autre quand le contenu change (par exemple avec
  `--inclure-filae`) ; l'identité stable d'une notice est le couple (inventaire, `notice`).
- Quand un champ porte le nom d'une entrée de `tables`, sa valeur est un **index** dans cette table.
- Une valeur absente est `null` (jamais une chaîne vide).
- `liens_particuliers.notice` et `.images` : `{"<id de ligne>": "<adresse copiée du XML>"}` pour les seules lignes
  dont le lien ne suit pas la forme habituelle (valeur `null` : pas de lien du tout). L'adresse est donnée telle
  que les Archives nationales l'écrivent, donc en `http://` (§ 5).

## 3. `an-decrets.json` — un décret par ligne

Contient **tous** les décrets de classe A1, A2, A3 ou R — y compris ceux dont aucun nom n'est saisi (« image
seule »), qui servent à la recherche guidée — plus tout autre décret (classe `-`) auquel appartient une personne
exportée.

| Champ | Type | Sens |
|---|---|---|
| `id` | entier | rang de la ligne |
| `inv` | index → `tables.inv` | inventaire (`FRAN_IR_055161`) |
| `notice` | texte | identifiant de la notice du décret dans cet inventaire (`SB000001`) |
| `date` | texte ISO ou `null` | date du décret, **réconciliée** (voir `drap_date`) ; `null` si l'inventaire ne donne qu'un intervalle ou rien |
| `drap_date` | index → `tables.drap_date` | drapeau de la date (ci-dessous) |
| `titre` | texte | titre d'époque, tel qu'écrit (fautes comprises) |
| `famille` | index → `tables.famille` | famille de la taxonomie (ci-dessous) |
| `classe` | index → `tables.classe` | classe Algérie : `A1`, `A2`, `A3`, `R` ou `-` |
| `cote` | texte ou `null` | cote du décret telle qu'écrite (`BB/34/387`, `19780549/461`) |
| `drap_cote` | index → `tables.drap_cote` | `""`, `suspecte-bb11` ou `absente` |
| `cote_sug` | texte ou `null` | cote probable quand `cote` est suspecte (`BB/11/477` → `BB/34/477`) ; la valeur d'origine n'est jamais remplacée |
| `doc` | texte ou `null` | numéro de document dans le registre (`document 1`) ; absent de 1933 à 1948 |
| `etat` | index → `tables.etat` | état de l'index des noms pour ce décret (ci-dessous) |
| `n_pers` | entier | nombre de notices de personnes rattachées au décret dans l'inventaire |
| `n_exp` | entier | nombre de ces personnes présentes dans `an-personnes.json` |
| `annee` | entier | année du registre (celle de l'inventaire) |
| `trim` | 1-4 ou `null` | trimestre de l'inventaire ; renseigné seulement pour 1925-1930, années découpées en quatre inventaires |
| `contexte` | texte ou `null` | titre du registre englobant, en 1944 : `… (Alger)` distingue le registre d'Alger |

**`drap_date`** (plusieurs drapeaux se joignent par `+`) :

| Valeur | Sens |
|---|---|
| `""` | l'attribut `unitdate/@normal`, le texte de `<unitdate>` et le titre concordent |
| `conflit-titre-retenu` | `@normal` contredit le titre ; la date du titre est retenue parce qu'elle seule tombe dans l'année de l'inventaire (août 1933 est codé 1938 dans le XML) ou parce que le texte de `<unitdate>` la répète |
| `conflit-normal-retenu` | `@normal` et le titre se contredisent sans que rien ne les départage : `@normal` est gardé, la date est à vérifier sur l'image |
| `titre-seul` | pas de `<unitdate>` : date lue dans le titre |
| `intervalle` | l'inventaire donne un intervalle (« Décrets, arrêtés et rapports divers de 1931 ») : `date` vaut `null` |
| `sans-date` | aucune date |
| `hors-inventaire` | l'année retenue n'est pas celle de l'inventaire (aucun cas dans les exports du 2026-10-16) |

**`famille`** (première règle satisfaite) : `rejet`, `revocation-retrait`, `admission-citoyen`,
`composite-avec-citoyen`, `autorisation-etranger`, `liberation-allegeance`, `admission-domicile`, `naturalisation`,
`naturalisation+reintegration`, `reintegration`, `titre-nom-dispense`, `divers`. Le titre n'est jamais testé par son
premier mot (28 décrets commencent par une faute ou ont perdu leur titre).

**`classe`** — pertinence pour un ancêtre algérien, jamais une qualification juridique :

| Classe | Définition | À savoir |
|---|---|---|
| `A1` | le titre nomme l'Algérie et n'est pas un rejet | avant 1931, « naturalisations algériennes » mêle les « indigènes » admis et les étrangers naturalisés en Algérie ; avec `famille = admission-citoyen`, c'est le décret d'admission au sens strict |
| `A2` | « admission aux droits de citoyen français » sans aucun territoire (à partir de 1931) | mêle des Algériens à des personnes d'autres territoires |
| `A3` | décret composite incluant l'admission aux droits de citoyen (1941-1948) | l'admission est noyée dans un décret général ; aucun nom saisi |
| `R` | rejet, révocation ou retrait dont le titre nomme l'Algérie ; ou rejet de demandes d'« admission aux droits de citoyen français » écrit sans territoire (4 décrets de 1933-1934, pendant de `A2` pour les demandes refusées) | une demande rejetée explique une absence ; ne pas afficher « nomme l'Algérie » pour toute la classe |
| `-` | autre | présent seulement parce qu'une personne exportée en relève |

Un libellé français de chaque classe est fourni dans `an-meta.json` (`classes`). Un territoire est reconnu dans le
titre par une liste de mots (Algérie et sa faute « Aglérie », Tunisie, Maroc, Madagascar, Indochine, colonies,
Afrique équatoriale ou occidentale…) : un territoire absent de cette liste, écrit entre parenthèses après « citoyen
français », ferait classer le décret en `A2` à tort (aucun cas connu dans les exports du 2026-10-16).

**`etat`** :

| Valeur | Sens |
|---|---|
| `indexe` | des noms sont saisis pour ce décret, dans un inventaire indexé (au moins 90 % de ses décrets portent des noms) |
| `partiel` | des noms sont saisis pour ce décret, mais dans un inventaire où la saisie est fragmentaire : la liste n'est pas réputée complète |
| `image` | aucun nom saisi : seules les images du décret sont consultables |
| `retenu-filae` | des noms existent dans l'inventaire des AN mais ne sont **pas publiés ici** (clause Filae, § 6) : chercher le nom sur le site des Archives nationales |

## 4. `an-personnes.json` — une occurrence de nom par ligne

Une ligne par **personne principale** d'une notice, suivie immédiatement de son **épouse**, de ses **enfants** et,
dans deux notices de 1898, de son **second demandeur**, cités dans la même notice. Ce sont des noms cherchables
rattachés au principal par `princ`.

Sélection (« palier Algérie ») : la notice est exportée si son décret est de classe A1, A2, A3 ou R, **ou** si la
personne est née ou réside en Algérie, **ou** si elle porte l'indice `M`, **ou** si la notice dit ses parents
algériens (« Tunis, Tunisie, de père algérien » : règle `parents-algeriens+…`), **ou** si son épouse, l'un de ses
enfants ou son second demandeur est né ou réside en Algérie (105 notices, toutes par l'épouse : on cherche une
famille par n'importe lequel de ses membres). Dans ce dernier cas l'indice du principal ne change pas : ses champs
`nea` et `rea` restent vides, et c'est le champ `lieu` ou `res` de la ligne de l'épouse qui montre l'Algérie.

Trois choses ne sont **pas** dans ce fichier, et `an-meta.json` les compte :

- les noms des années couvertes par la clause Filae, retenus par défaut (§ 6) ;
- les noms des personnes qui pourraient être encore en vie (§ 6 bis) — une ligne retenue n'existe pas : si c'est le
  principal, toute sa notice est absente ; si c'est une épouse ou un enfant, la fiche du principal reste, et
  `vie_privee.apparentes_retenus_par_principal` dit **combien** de ses proches manquent, jamais lesquels ;
- les mentions d'épouses et d'enfants qui ne sont pas des noms (une date, un numéro de dossier… § 6 ter).

| Champ | Type | Sens |
|---|---|---|
| `id` | entier | rang de la ligne |
| `role` | index → `tables.role` | `principal`, `epouse`, `enfant` ou `demandeur` (second demandeur ; valeur ajoutée le 2026-11-11 en **fin** de table : les index 0, 1 et 2 n'ont pas changé, et aucune ligne de l'export par défaut ne la porte, § 4 bis) |
| `princ` | entier | `id` de la ligne du principal (lui-même pour un principal) |
| `nom` | texte ou `null` | nom **exactement comme écrit** (blancs réduits). Enfant : prénoms seuls, le nom de famille est celui du principal. `null` : nom non saisi dans l'inventaire (la notice garde son dossier) |
| `an` | entier ou `null` | année de naissance |
| `prec` | index → `tables.prec` | précision de la naissance (ci-dessous) |
| `naiss` | texte ou `null` | texte brut de la naissance : la ligne « Naissance » du principal ; pour l'épouse, la fin de sa ligne ou sa propre ligne de naissance ; pour l'enfant, le contenu de sa parenthèse ou la date qui lui est associée |
| `lieu` | texte ou `null` | lieu de naissance extrait de `naiss` |
| `res` | texte ou `null` | résidence, telle qu'écrite. Quand la notice ne porte qu'**une** ligne de résidence, placée après l'épouse (472 notices, surtout 1917, 1918 et 1932), elle est donnée au principal **et** à l'épouse : c'est la résidence du ménage. Quand le principal a deux lignes de résidence (148 notices, presque toutes de 1890), `res` donne la première ; `rea` tient compte des deux |
| `prof` | texte ou `null` | profession (principal seulement) |
| `dec` | entier | `id` du décret dans `an-decrets.json` |
| `dossier` | texte ou `null` | numéro du dossier de demande, normalisé (`90010 X 92`, `149 BX 30`, `109 bis X 12` ; plusieurs numéros joints par ` ; `) ; principal seulement. Quand aucun numéro n'est reconnu, le texte de l'inventaire est donné tel quel (« Numéro de dossier manquant », `1397 X 9`) |
| `cote` | texte ou `null` | cote du dossier telle qu'écrite (`BB/11/90010`, `BB/11/6575,BB/11/6576`, `BB/11/10349/4`, `19770874/9002`) ; `null` pour environ 5 % des personnes exportées : il faut alors partir du numéro de dossier |
| `notice` | texte ou `null` | identifiant de la notice de la personne (pour le lien) ; `null` pour épouse et enfant (utiliser celui du principal) |
| `img` | 0 ou 1 | 1 si la notice a son propre lien d'images ; sinon utiliser les images du décret |
| `ind` | index → `tables.ind` ou `null` | indice (ci-dessous) ; principal seulement |
| `regle` | index → `tables.regle` ou `null` | règle qui a produit l'indice |
| `nea` | index → `tables.nea` ou `null` | né(e) en Algérie : `""`, `explicite` ou `repertoire` |
| `rea` | index → `tables.rea` ou `null` | réside en Algérie : mêmes valeurs |

Le champ `naiss` d'une épouse saisie sous la forme de 1895 « NOM, née NOM, 3 mai 1855, née le Gênes. » (84 épouses
du corpus, 22 exportées) commence par la date : le nom est coupé à la date, comme pour toute épouse dont la ligne
n'a pas de « née le … » suivi d'une date ; `lieu` donne ce qui suit « née le ». Rien n'est réécrit. Limite : quand
des enfants sont cités à la suite sur la même ligne (« …, née le Gênes, Lucie (5 mai 1880). »), ils restent
dans `lieu` et ne sont pas des noms cherchables (3 épouses exportées).

**`prec`** (une seule valeur, la plus prudente l'emporte) :

| Valeur | Sens |
|---|---|
| `jour`, `mois`, `annee` | précision de la date écrite |
| `conventionnelle` | « 1 janvier », « présumé », « vers » : date d'état civil reconstitué — **comparer l'année, jamais le jour** |
| `position` | enfant de la forme « A ; B né(e)(s) le d1 ; d2 » : prénom et date associés par leur rang, **non vérifié** |
| `liste-non-appariee` | même forme, mais les deux listes n'ont pas la même longueur : `an` vaut `null` et `naiss` donne toute la liste des dates |
| `suspecte` | année impossible (postérieure au décret, ou antérieure de plus de cent ans) : gardée telle quelle. Vaut pour le principal, l'épouse et les enfants |
| `""` | pas de date |

**`ind`** — un indice par personne principale :

| Code | Sens | Règles (`regle`) |
|---|---|---|
| `M` | musulman algérien probable (« indigène » de l'époque) | `ne-en-algerie(explicite\|repertoire)+…` suivi des marqueurs `prenom-musulman`, `filiation` (ben, bent, ould…), `mention-indigene`, `parents-algeriens` ; `parents-algeriens+ne-tunisie\|ne-maroc\|ne-ailleurs+…` (né hors d'Algérie de parents dits algériens, avec un marqueur de nom) ; ou, plus faible, `lieu-de-naissance-non-reconnu+…+reside-en-algerie\|decret-algerie` |
| `N` | né en Algérie, sans autre indice | `ne-en-algerie(…)`, `ne-en-algerie(…)+parents-francais` |
| `E` | étranger européen probable (né en Europe, ou de parents étrangers) | `ne-italie`, `ne-espagne`, `ne-france`… ; `ne-en-algerie(…)+parents-etrangers` ; `ne-france+parents-etrangers`, `parents-etrangers` (parents déclarés étrangers, né ailleurs qu'en Algérie) |
| `T` | Marocain ou Tunisien probable | `ne-maroc`, `ne-tunisie` ; `…+parents-etrangers` quand les parents sont dits marocains ou tunisiens |
| `L` | légionnaire | `profession-legion` |
| `I` | indéterminé | `aucune-regle` ; `parents-algeriens+ne-…` (né hors d'Algérie de parents dits algériens, sans marqueur de nom : la notice est dans le palier, rien de plus n'est affirmé) |

Le pays de naissance d'une règle `ne-…` est lu dans le lieu de naissance **sans** sa clause sur les parents :
« Lyon, Rhône, France, de parents italiens » donne `ne-france+parents-etrangers`, et « Tunis, Tunisie, de père
algérien » ou « Tunis, Algérie ( père ) [Tunisie] » ne sont pas des naissances en Algérie (`nea` vide). La table
`tables.regle` compte 52 règles distinctes dans les exports du 2026-10-16 ; elle peut en gagner : lire la règle, ne pas
supposer une liste fermée.

« Né en Algérie » ne repose pas sur le seul mot « Algérie » (qui oublie au moins 12 % des naissances) :
`explicite` = le pays, un département ou une région est nommé, ou `Alger`, `Oran`, `Constantine` figure seul en
deuxième position (« Bône ( Constantine ) ») — l'adjectif « algérien », qui ne qualifie que les parents, n'est pas
un marqueur de lieu ; `repertoire` = aucun autre pays n'est nommé et la première
composante du lieu est une localité du répertoire `decretas/an/reference/gazetteer_algerie.tsv` (420 localités vues
au moins trois fois avec un marqueur explicite, au moins neuf fois sur dix en Algérie).

Limites connues : l'effectif de `M` est la taille d'une classe heuristique, pas un nombre d'admissions ; des
familles juives d'Algérie et du M'zab sont parfois prises pour musulmanes ; les lieux de naissance rares ou mal
orthographiés ne sont pas reconnus ; le marqueur `prenom-musulman` peut venir d'un nom de famille décollé
(« Ben… ») ; la règle faible `lieu-de-naissance-non-reconnu` (52 notices) peut se tromper quand le pays de naissance
est mal orthographié. Les marqueurs de nom juif ne servent qu'à **retenir** l'indice `M` : aucune classe
correspondante n'est produite ni publiée.

### 4 bis. Le second demandeur (1898)

Deux notices de 1898 portent une ligne « Deuxième demandeur : NOM, Prénoms », suivie de la naissance et de la
résidence de cette seconde personne. Elle est lue comme une occurrence de nom de rôle `demandeur`, rattachée au
principal comme une épouse (`an`, `naiss`, `lieu`, `res` sont les siens ; `notice`, `dossier`, `cote` sont ceux du
principal). Elle suit son principal en tout : elle n'est dans `an-personnes.json` **que si** les noms de son année
y sont. 1898 est une année de la clause Filae : par défaut elle n'y est donc pas. Avec les inventaires du
2026-10-16, elle n'y serait pas davantage avec `--inclure-filae`, parce qu'aucune des deux notices n'est dans le
palier Algérie (aucun lieu algérien n'y figure). Dans la base de travail, les deux noms sont cherchables par
`python3 -m decretas.an chercher`.

## 5. `an-meta.json`

Objet JSON indenté (lisible), dont les clés sont :

| Clé | Contenu |
|---|---|
| `format` | `decretas-an-meta/1` |
| `genere_le` | horodatage de la génération (option `--horodatage`) ; son année fixe le seuil de la règle « vie privée » |
| `source` | producteur, fonds, nombre d'inventaires, dates de téléchargement, inventaire racine ignoré |
| `fichiers` | pour `an-decrets.json` et `an-personnes.json` : `octets` et `sha256` (contrôle d'intégrité) |
| `comptes` | `corpus` (tout l'inventaire ; dont `seconds_demandeurs`, `personnes_du_palier_par_un_apparente`, `apparentes_au_nom_inexploitable`), `exporte` (ce que contiennent les fichiers ; dont `seconds_demandeurs`), `indices_du_palier` (tout le palier Algérie du corpus, noms retenus compris) |
| `filae` | années couvertes, `noms_inclus`, texte de la clause, nombre d'individus concernés |
| `vie_privee` | règle « personnes pouvant être en vie » et ce qu'elle retient (§ 6 bis) |
| `noms_inexploitables` | mentions d'épouses et d'enfants qui ne sont pas des noms, non exportées (§ 6 ter) |
| `seuil_indexe` | part des décrets portant des noms à partir de laquelle une période est dite indexée (0,9) |
| `couverture_annees` | table colonnes, une ligne par année de 1883 à 1948 |
| `couverture_trimestres` | même table, une ligne par trimestre pour 1925-1930 |
| `inventaires` | table colonnes des 84 inventaires : `inv`, `annee`, `trim`, `titre`, `cotes`, `etat`, `decrets`, `decrets_avec_noms`, `personnes`, `filae`, `noms_exportes` |
| `non_couvert` | liste `{code, periode, texte}` de ce qu'une recherche dans ces fichiers **ne couvre pas**, prête pour le bilan de recherche. Codes : `image-seule`, `partiel`, `retenu-filae` (un par année, ou par trimestre pour 1925-1930 : `periode` vaut `1900` ou `1928, 1er trimestre`), puis `avant-1883`, `apres-1948`, `jugements-1919`, `pas-une-citation`, `homonymes-et-graphies`, `enfants`, `clause-filae` (absent avec `--inclure-filae`), `vie-privee` (absent avec `--inclure-vivants-possibles`), `noms-inexploitables` (présent quand il y en a). Afficher la liste telle quelle : d'autres codes peuvent venir |
| `table_des_liens` | `contenu/liens.json` : chemin, depuis la racine du site, de la table unique des gabarits de liens |
| `liens` | pour chaque sorte de lien, l'**identifiant** de son entrée dans cette table et la correspondance des variables (ci-dessous). Aucune adresse |
| `liens_particuliers_inventaires` | inventaires dont le lien écrit dans le XML ne suit pas la forme habituelle (aucun aujourd'hui) |
| `credit` | gabarit de la mention obligatoire, lieu de conservation, date des informations, rappel de la licence |
| `indices` | libellé français de chaque code d'indice |
| `classes` | libellé français de chaque classe Algérie (`A1`, `A2`, `A3`, `R`, `-`) |
| `avertissements` | rappels à afficher près des résultats |

**Couverture** — champs de `couverture_annees` et `couverture_trimestres` :
`annee`, `trim` (`null` dans la table annuelle), `etat` (`indexe`, `partiel`, `image`), `decrets`,
`decrets_avec_noms`, `personnes` (notices), `filae` (année couverte par la clause), `noms_exportes` (des noms de
cette période sont dans `an-personnes.json`), `alg_decrets` et `alg_avec_noms` (décrets A1 + A2 + A3 + R, total et
avec noms), puis `a1`, `a1_avec_noms`, `a2`, `a2_avec_noms`, `a3`, `a3_avec_noms`, `r`, `r_avec_noms`, et
`personnes_exportees`. Pour une période `partiel`, `decrets_avec_noms` / `decrets` donne la part indexée.

Mesuré sur les exports du 2026-10-16 : 35 années indexées (1883-1898, 1913-1927, 1929-1932),
14 partielles (1900-1912 : de 2 à 82 décrets avec noms par an ; 1928 : 248 sur 739, dont janvier-mars 192 sur 196,
avril-juin 47 sur 168, juillet-septembre 5 sur 152, octobre-décembre 4 sur 223), 17 en image seule (1899 et
1933-1948).

**Liens** (`liens`) — des identifiants, pas des adresses. Le site n'a qu'**une** table de gabarits de liens
externes, `site/contenu/liens.json` ; `an-meta.json` ne la répète pas. Il dit quelle entrée de cette table sert pour
chaque sorte de lien, et quel champ des fichiers de données remplit chaque variable de son gabarit :

```json
"table_des_liens": "contenu/liens.json",
"liens": [
 {"nom": "inventaire", "id": "an-inventaire",    "variables": {"inventaire": "inv"}},
 {"nom": "notice",     "id": "an-notice",        "variables": {"inventaire": "inv", "notice": "notice"}},
 {"nom": "images",     "id": "an-images-notice", "variables": {"inventaire": "inv", "notice": "notice"}}
]
```

| `nom` | Entrée de `site/contenu/liens.json` | Sert à | Variables du gabarit ← champ des données |
|---|---|---|---|
| `inventaire` | `an-inventaire` | la page de l'inventaire d'une année | `{inventaire}` ← `inv` |
| `notice` | `an-notice` | la page d'une notice (décret ou personne) | `{inventaire}` ← `inv`, `{notice}` ← `notice` |
| `images` | `an-images-notice` | les images rattachées à une notice | `{inventaire}` ← `inv`, `{notice}` ← `notice` |

Pour construire un lien :

1. chercher d'abord la ligne dans `liens_particuliers` (du fichier de données, ou `liens_particuliers_inventaires`
   pour un inventaire) : si elle y est, utiliser l'adresse donnée, ou ne proposer aucun lien si la valeur est `null` ;
2. sinon prendre dans `site/contenu/liens.json` l'entrée dont l'`id` est celui de `liens`, et remplacer chaque
   variable de son `gabarit` par la valeur du champ indiqué : `inv` est l'identifiant de l'inventaire
   (`tables.inv[…]` de `an-decrets.json`, soit `FRAN_IR_055161` ; pour une personne, celui de son décret `dec`),
   `notice` est le champ `notice` de la ligne (pour une épouse, un enfant ou un second demandeur : celui de son
   principal). Les identifiants se recopient tels quels, sans encodage ;
3. le statut du lien (`teste-200`, `non-teste`…), sa date d'essai, son `avertissement` et son `repli` se lisent
   dans cette même entrée : `an-meta.json` ne les porte plus. Le 2026-11-11, seul `an-inventaire` est `teste-200` ;
   `an-notice` et `an-images-notice` sont `non-teste` (le site des Archives nationales répondait 503).

Les gabarits de `site/contenu/liens.json` sont en `https://` ; les exports XML écrivent ces mêmes adresses en
`http://` (le site des Archives nationales redirige). C'est la seule différence, et elle est **vérifiée** :
`python3 -m decretas.an verifier` échoue si une des trois entrées manque, si ses variables ne sont plus celles
ci-dessus, ou si son gabarit n'est plus la forme écrite dans le XML au schéma près. Une adresse de
`liens_particuliers` est au contraire donnée telle qu'elle est écrite dans le XML, donc en `http://`. Pour une
personne sans lien d'images propre (`img = 0`), utiliser les images de son décret.

**Crédit** : toute réutilisation doit mentionner
`Archives nationales de France ; cote ; lieu de conservation ; date des informations`
(`credit.gabarit`, avec `credit.lieu_de_conservation` et `credit.date_des_informations`, date de téléchargement
des inventaires).

## 6. La clause Filae

L'inventaire racine `FRAN_IR_057397` et l'inventaire de 1899 `FRAN_IR_057213` portent cette restriction : « Pour
les années indexées par Filae, toute publication sur internet à des fins de recherche nominative, patronymique, ou
généalogique, d'un corpus concernant plus de 1000 individus devra faire l'objet d'une autorisation préalable de la
société Filae. » La racine dit que l'indexation de 1898 à 1912 et de 1928 a été « engagée en partenariat avec
Filae » ; qui a saisi 1898 et janvier-mars 1928 n'est pas établi.

Tant que les Archives nationales n'ont pas précisé la portée de la clause, **1898, 1899-1912 et 1928 sont traitées
comme couvertes** (`FILAE_YEARS` dans `decretas/an/build.py`) :

- par défaut, les noms de ces années ne sont **pas** exportés ; leurs décrets le sont, avec l'état `retenu-filae`
  quand des noms existent, et `non_couvert` le dit année par année ;
- `--inclure-filae` les exporte (usage privé et local, ou une fois l'autorisation obtenue) ;
- dans les deux cas la commande affiche le nombre d'individus concernés. Mesuré : 13 852 notices de personnes dans
  tout le corpus pour ces années ; dans le palier Algérie, 2 218 personnes principales et 383 épouses et enfants.

## 6 bis. Vie privée : les personnes qui pourraient être encore en vie

Les inventaires nomment des enfants, et quelques personnes principales, nés dans les années 1920 et 1930. Un index
public de noms ne doit pas publier le nom d'une personne vivante. Règle appliquée **par défaut** à chaque occurrence
de nom, au moment de l'export :

1. **Année retenue** pour la personne : l'année de naissance écrite dans la notice ; si elle manque, ou si elle est
   impossible (postérieure au décret, ou antérieure de plus de cent ans : précision `suspecte`), **l'année du
   décret**, puisque nul ne naît après le décret qui le nomme. Pour les enfants cités en deux listes (« A ; B né(e)(s)
   le d1 ; d2 »), dont l'association du prénom et de la date n'est pas vérifiée, c'est l'année la plus récente de
   la liste qui vaut pour chacun.
2. L'occurrence est **retenue** quand cette année est égale ou postérieure à l'**année seuil** = année de la
   génération − 100. Générés en 2026, les fichiers retiennent donc toute personne née en 1926 ou après, et toute
   personne d'année inconnue ou impossible nommée sous un décret de 1926 ou d'une année postérieure. Une personne
   née en 1926 peut avoir 99 ans le jour de la génération : elle est retenue.
3. Quand la **personne principale** est retenue, toute la notice l'est, épouse et enfants compris : ils ne se lisent
   que sous son nom.

Conséquences voulues : une faute de saisie sous un décret ancien (« 1961 » dans un décret de 1890) ne retient
rien, la personne est née en 1890 au plus tard, et sa ligne garde la précision `suspecte` ; une faute de saisie
sous un décret récent (« 1826 » pour « 1926 ») retient la ligne. La règle ne lit que des années, jamais des jours :
elle retient un peu trop, jamais trop peu.

L'année de la génération est celle de `--horodatage` (par défaut : aujourd'hui). Chaque 1er janvier, une
reconstruction publie donc une année de naissance de plus ; rien ne se publie sans reconstruction.

`an-meta.json` → `vie_privee` :

| Clé | Contenu |
|---|---|
| `active` | `true` par défaut ; `false` si les fichiers ont été produits avec `--inclure-vivants-possibles` : **ils ne doivent alors pas être publiés** |
| `annee_de_generation`, `age`, `annee_seuil` | 2026, 100, 1926 |
| `regle` | la règle en français, prête à afficher |
| `motifs` | libellé de chaque motif : `naissance-recente`, `naissance-inconnue`, `naissance-impossible`, `notice-du-principal-retenue` |
| `concernes`, `concernes_par_motif` | occurrences désignées par la règle, au total et par rôle (`principaux`, `epouses`, `enfants`, `seconds_demandeurs`), parmi les notices que cet export pouvait publier (les années Filae n'y sont pas quand elles sont retenues) |
| `retenus` | ce qui manque réellement dans `an-personnes.json` : égal à `concernes` quand `active`, zéro sinon |
| `apparentes_retenus_par_principal` | `{"<id de ligne du principal>": nombre}` : combien d'épouses et d'enfants de cette notice sont retenus. Le nombre seul, pour que la fiche puisse dire « 2 proches cités dans cette notice ne sont pas affichés » ; aucun nom, aucune date |

Un décret dont des personnes sont retenues reste listé ; son `n_exp` ne compte que les personnes présentes.
`--inclure-vivants-possibles` désactive la règle pour un usage privé et local ; la commande affiche alors un
avertissement sur la sortie d'erreur. Elle **refuse** (code 2) d'écrire un tel export dans `site/` : il faut un
`--sortie` hors du site (par exemple `--sortie data/build/export-prive`, où `--sortie` désigne le dossier des
fichiers produits). Il en va de même pour `--inclure-filae`. Et `python3 -m decretas verifier` échoue si les
fichiers servis (`site/data/`) contiennent un nom d'une année Filae, un nom d'une personne qui pourrait être en
vie, ou si `an-meta.json` dit l'une des deux règles inactive.

Mesuré le 2026-11-11 (seuil 1926, noms Filae retenus) : **296 occurrences retenues** — 61 personnes principales,
11 épouses, 224 enfants. Par motif : `naissance-recente` 192 (1 principal, 191 enfants), `naissance-inconnue` 74
(53 principaux, 8 épouses, 13 enfants), `naissance-impossible` 9 (7 principaux, 2 épouses),
`notice-du-principal-retenue` 21 (1 épouse, 20 enfants). 115 fiches de principaux exportés ont au moins un proche
retenu (208 proches en tout). Vérifié sur le fichier produit : aucune ligne dont l'année retenue (calcul simple,
sans la règle des listes) est 1926 ou plus.

## 6 ter. Les mentions qui ne sont pas des noms

À la place du nom d'une épouse ou du prénom d'un enfant, l'inventaire porte parfois autre chose. Ces mentions sont
gardées telles quelles dans la base de travail (`apparente.texte_brut`, `nom_brut`, avec le drapeau `nom_drapeau`),
mais elles ne sont **pas exportées** comme noms cherchables. Règles strictes, sans vocabulaire à deviner :

| `nom_drapeau` | Règle | Exemple (inventé) |
|---|---|---|
| `numero-de-dossier` | le « nom » est un numéro de dossier et rien d'autre | `90100 X 20` |
| `date` | le « nom » contient une date | `3 mai 1891 ; Paul` |
| `chiffre` | le « nom » contient un autre chiffre (un nom n'en contient jamais) | `Lucie 28`, `5 enfants` |
| `vide` | rien, ou aucun mot de deux lettres | `?` |
| `libelle-de-champ` | le « nom » commence par le libellé d'une autre rubrique | `Lieu de résidence : Marie` |

`an-meta.json` → `noms_inexploitables` donne la règle, le libellé des motifs, `non_exportes` (total et par rôle),
`non_exportes_par_motif`, et `par_principal` (`{"<id de ligne du principal>": nombre}`, comme pour la vie privée).
Ne sont comptées que les mentions des notices exportées.

Mesuré : 130 mentions dans tout le corpus (69 numéros de dossier, 31 dates, 15 chiffres, 9 vides, 6 libellés) ;
**9 dans les notices exportées** (5 numéros de dossier, 2 dates, 2 chiffres ; 5 épouses, 4 enfants). Limites
connues : un prénom réel collé à la mention est perdu avec elle (« 3 mai 1891 ; Paul », un prénom tapé en
majuscules verrouillées où « é » est devenu « 2 ») ; un nom d'épouse qui contient la date d'un jugement ou d'un
décès (« veuve de … décédé le 3 mars 1890 », 4 épouses du corpus, aucune dans le palier) est écarté lui aussi ;
une remarque écrite sans chiffre à la place d'un prénom (« attente d'autorisation ») n'est **pas** détectée. Les
noms des personnes principales ne sont jamais écartés : 96 d'entre eux, dans le palier, contiennent un chiffre,
presque tous (93) dans une mention entre parenthèses (« ( rejet en date du … ) ») ; ils restent cherchables par
leurs autres mots.

## 7. Ce que ces fichiers ne couvrent pas

`an-meta.json` → `non_couvert` en donne la liste à jour. En résumé :

- les années sans nom saisi : 1899 et 1933-1948 ; les années fragmentaires : 1900-1912 et avril-décembre 1928 ;
- les noms retenus au titre de la clause Filae (par défaut) ;
- les noms des personnes qui pourraient être encore en vie (par défaut, § 6 bis) et les mentions qui ne sont pas des
  noms (§ 6 ter) ;
- les décrets antérieurs à 1883 et postérieurs à 1948 ;
- les admissions par **jugement** (loi du 4 février 1919), qui ne sont dans aucun décret ;
- les personnes hors palier Algérie (elles sont dans `data/build/an.sqlite`, pas dans les fichiers du site) ;
- la publication officielle du décret (date et page) : une notice n'est pas une citation ;
- les décrets de rejet, de révocation ou de retrait dont le titre ne nomme ni l'Algérie ni des demandes
  d'admission aux droits de citoyen sans territoire (leurs personnes nées ou résidant en Algérie sont exportées
  quand des noms sont saisis ; les décrets en image seule ne sont pas listés).

## 8. La base `data/build/an.sqlite`

Noms de tables et de colonnes en français (c'est un format de données, comme les fichiers du site). Elle contient
tout le corpus et ne porte aucun horodatage.

| Table | Une ligne par | Colonnes notables |
|---|---|---|
| `inventaire` | inventaire (84) | `annee`, `trimestre`, `etat`, `n_decrets`, `n_decrets_avec_noms`, `n_personnes`, `annee_filae`, `reutilisation`, `lien`, `sha256`, `telecharge_le` |
| `decret` | décret (21 557) | `date`, `date_drapeau`, `date_normal`, `date_texte`, `date_titre`, `famille`, `territoires`, `classe_algerie`, `cote`, `cote_source`, `cote_drapeau`, `cote_suggeree`, `document`, `n_personnes`, `etat`, `decret_parent`, `contexte`, `lien_notice`, `lien_images` |
| `personne` | notice de personne (371 860) | `titre_brut`, `nom_brut`, `nom_non_saisi`, découpage indicatif du nom, `naissance_brut` et champs analysés, `naissance_conventionnelle`, `naissance_suspecte`, `residence`, `profession`, `profession_dans_naissance`, `dossier_brut`, `dossier`, `cote_dossier`, `lien_notice`, `lien_images`, `ne_en_algerie`, `reside_en_algerie`, `indice`, `regle`, `palier_algerie`, `palier_par_apparente` (1 quand la notice n'est dans le palier que par son épouse, un enfant ou son second demandeur), `residence_ligne_epouse` (1 quand la résidence vient de l'unique ligne placée après l'épouse), `mentions` (lignes « Remarques », « Mention de retrait », seconde ligne de résidence…) |
| `apparente` | épouse, enfant ou second demandeur (100 694) | `role` (`epouse`, `enfant`, `demandeur`), `texte_brut`, `nom_brut`, `naissance_brut`, `naissance_annee`, `naissance_suspecte`, `appariement`, `nom_drapeau` (§ 6 ter ; vide pour un nom), `ne_en_algerie`, `reside_en_algerie` (mêmes valeurs que pour le principal) |
| `ligne_incomprise` | ligne de contenu que l'analyseur n'a pas comprise (8) | `inv`, `notice_id`, `texte` |
| `notice_ecartee` | notice écartée de l'index des noms (7) | `motif`, `titre` |
| `meta` | clé | format (`decretas-an-sqlite/3`), inventaire racine, compteurs de lignes |

Notices écartées : sept notices rangées parmi les personnes qui sont des décrets réglementaires ou des règlements
d'armoiries. Elles sont reconnues **par leur structure** (un titre, mais ni `<persname>`, ni ligne de contenu, ni
image), jamais par le premier mot du titre. Une personne dont le titre est vide, ou dont le nom a été écrasé par un
titre de décret, est gardée avec `nom_non_saisi = 1`.

La base contient **toutes** les personnes, y compris celles que la règle « vie privée » retient : elle reste sur le
poste de travail (`data/` est ignoré par git) et ne se publie pas. Une base au format `decretas-an-sqlite/2` est
refusée par `construire --export-seul` et par `verifier` : relancer `construire`.

## 9. Commandes

À lancer depuis la racine du dépôt. Aucune n'utilise le réseau.

```bash
python3 -m decretas.an construire
python3 -m decretas.an verifier
python3 -m decretas.an chercher testaoui,testaouy amar --ne-vers 1876
python3 -m decretas.an decrets --csv data/build/an-decrets.csv
```

- `construire` : lit `data/raw/an/FRAN_IR_*.xml`, écrit la base et les trois fichiers du site.
  `--source DOSSIER` autre dossier d'exports (par exemple un rafraîchissement daté) ; `--base FICHIER` autre base ;
  `--sortie DOSSIER` autre dossier pour les fichiers du site ; `--inclure-filae` exporte aussi les noms des années
  couvertes par la clause ; `--inclure-vivants-possibles` exporte aussi les noms des personnes qui pourraient être
  encore en vie (§ 6 bis) — usage privé et local seulement, la commande l'écrit en toutes lettres sur la sortie
  d'erreur et `an-meta.json` le signale (`vie_privee.active = false`) ; `--horodatage ISO` impose la date de
  génération, qui doit commencer par `AAAA-MM-JJ` (son année fixe le seuil de la règle « vie privée ») ;
  `--export-seul` refait les fichiers du site sans relire les XML ; `--silencieux` supprime la ligne par inventaire.
- `verifier` : compare chaque XML au manifeste (taille, SHA-256, fin de fichier), les effectifs par inventaire à
  `decretas/an/reference/inventaires_attendus.tsv`, les trois entrées de liens à `site/contenu/liens.json` (§ 5),
  puis donne la couverture de l'analyseur et les signalements.
  `--detail` liste les lignes non comprises (elles contiennent des données personnelles). Code de sortie 1 en cas
  d'anomalie.
- `chercher` : chaque argument est un **terme** ; ses **variantes** sont séparées par des virgules. Affiche les
  correspondances, les correspondances partielles (un terme absent, nommé) et un bilan de recherche.
  `--ne-vers AAAA` ne garde que les personnes nées vers cette année ; `--tolerance N` écart admis (5 ans par
  défaut) ; `--algerie` restreint au palier Algérie ; `--limite N` nombre de notices affichées.
- `decrets` : `--csv FICHIER` (obligatoire) fichier à écrire ; `--algerie` seulement les classes A1, A2, A3, R ;
  `--source DOSSIER` autre dossier d'exports. Colonnes du CSV (UTF-8 avec BOM, pour les tableurs) : `annee`,
  `trimestre`, `date`, `drapeau_date`, `date_normal`, `date_titre`, `titre`, `famille`, `territoires`,
  `classe_algerie`, `cote`, `drapeau_cote`, `cote_suggeree`, `document`, `etat`, `personnes_indexees`, `contexte`,
  `decret_parent`, `inventaire`, `notice_id`, `lien_notice`, `lien_images` (les deux liens sont copiés du XML).
  `scripts/lister-decrets-algeriens.py` reste utilisable : il appelle ce même module et écrit, sans option,
  `data/derived/decrets-algeriens.csv` (les 3 345 décrets des classes A1, A2, A3 et R, mêmes colonnes ; fichier
  refait le 2026-11-11, l'ancien datait d'avant la taxonomie). Ses options : `-o FICHIER` (ou `--sortie FICHIER`)
  autre fichier à écrire ; `--tous` garder tous les décrets ; des chemins de XML en arguments pour ne lire que
  ceux-là.
- `repertoire` et `attendus` (maintenance) : recalculent le répertoire des localités et la table des effectifs
  attendus à partir de la base, après un changement des règles ou un rafraîchissement des inventaires.

Le téléchargement des inventaires n'appartient pas à ce module : `scripts/telecharger-inventaires.sh` (seul
programme qui parle au site des Archives nationales) ne redemande jamais un fichier présent, attend 5 secondes au
moins entre deux requêtes, s'arrête au premier refus et quand le site est en panne. Options : `--simulation`
n'envoie rien ; `--delai N` fixe l'attente (5 au minimum) ; `--rafraichir` télécharge un jeu complet dans un nouveau
dossier daté `data/raw/an/rafraichi-AAAA-MM-JJ/` sans toucher aux fichiers de référence ; `--aide` affiche l'usage.
Codes de sortie : 0 terminé, 1 refus, 2 mauvais usage, 3 site en panne, 4 fichier tronqué. Ses branches HTTP sont
essayées dans `tests/an/test_cli.py` avec un faux `curl` ; il n'a pas été relancé contre le site depuis le
2026-10-16.

## 10. Mesures de la construction du 2026-11-11

Sur les 85 exports du 2026-10-16 (84 inventaires, la racine `FRAN_IR_057397` étant ignorée), génération du
2026-11-11 (année seuil de la vie privée : 1926) :

- corpus : 21 557 décrets, 371 860 notices de personnes, 30 999 épouses, 69 693 enfants, 2 seconds demandeurs ;
  7 notices écartées ; 8 lignes de contenu non comprises sur 897 517 ;
- classes : A1 2 640 (1 517 avec des noms), A2 278 (130), A3 80 (0), R 347 (180), autres 18 212 ;
- palier Algérie : 45 594 personnes principales (41 551 sous un décret A1, A2 ou R ; 105 entrées par leur épouse
  seulement, dont 1 dans une année Filae) ; nées en Algérie 7 732 (7 582 `explicite`, 150 `repertoire`), y résidant
  17 344 ;
- export par défaut (noms Filae et personnes pouvant être en vie retenus) : 4 847 décrets (`indexe` 3 200, `image`
  1 518, `retenu-filae` 129 ; classes A1 2 640, A2 278, A3 80, R 347, `-` 1 502) et **52 427 occurrences de noms**
  (43 315 principaux, 6 607 épouses, 2 505 enfants, aucun second demandeur) ;
- retenu au titre de la vie privée : 296 occurrences (61 principaux, 11 épouses, 224 enfants ; détail par motif au
  § 6 bis) ; mentions qui ne sont pas des noms, non exportées : 9 (§ 6 ter) ;
- retenu au titre de la clause Filae : 2 218 personnes principales du palier et leurs 383 épouses et enfants ;
- tailles : `an-decrets.json` 818 843 octets (83 650 en gzip), `an-personnes.json` 10 750 938 (2 714 677),
  `an-meta.json` 60 295 (9 591) ;
- deux constructions complètes de suite donnent une base et deux fichiers de données identiques octet pour octet,
  et le même `an-meta.json` quand `--horodatage` est le même.

Par rapport à la construction précédente du même jour (52 373 occurrences) : + 104 notices entrées par leur
épouse, avec leurs épouses et enfants ; − 296 occurrences retenues au titre de la vie privée (dont une partie
dans ces nouvelles notices) ; − 9 mentions qui ne sont pas des noms ; 22 épouses de 1895 exportées sous leur nom
sans la date (§ 4).

## 11. Jeux d'essai

Les fichiers de `tests/an/fixtures/` et les exemples de ce document sont **synthétiques** : personnes, noms et numéros de dossier inventés, seule
la forme des exports est reproduite. Aucune donnée personnelle des archives ne doit entrer dans `tests/` ni dans
`docs/`.
