# Données du Bulletin officiel (BOGGA) — format des fichiers du site

Ce document décrit les quatre fichiers que produit `python3 -m decretas.bogga construire` dans
`site/data/` à partir du *Bulletin officiel du Gouvernement général de l'Algérie* (BOGGA) tel
qu'il est lisible sur Internet Archive pour les années 1861 et 1863 à 1886, et 1888.

Vocabulaire : celui de [CONTEXT.md](../CONTEXT.md). Sigles : **BOGGA** = Bulletin officiel du
Gouvernement général de l'Algérie ; **OCR** = lecture automatique du texte d'une page à partir
de son image ; **feuille** (*leaf*) = numéro d'ordre d'une image dans un volume numérisé
(0, 1, 2…), différent du numéro de **page** imprimé sur le papier ; **livraison** = un numéro du
Bulletin (une vingtaine à une soixantaine par an), qui se termine par « CERTIFIÉ CONFORME :
Alger, le … » — cette date est la date de publication à citer.

Les fichiers contiennent des noms de personnes : ils restent sous `site/data/`, répertoire
ignoré par git. Aucun exemple de ce document ne reprend une personne réelle : les noms cités
(« Testaoui », « Fictmann »…) sont inventés.

## 1. Vue d'ensemble

| Fichier | Une ligne par | Taille mesurée le 2026-11-11 |
|---|---|---|
| `site/data/bogga-volumes.json` | volume annuel (26) | 37 Ko, 4 Ko en gzip |
| `site/data/bogga-decrets.json` | décret tel que publié (527) | 198 Ko, 22 Ko en gzip |
| `site/data/bogga-entrees.json` | entrée de personne (9 696) ou bloc non segmenté (34) | 1,74 Mo, 0,40 Mo en gzip |
| `site/data/bogga-meta.json` | — (objet unique) | 17 Ko, 3 Ko en gzip |

Les trois premiers ont la même forme, dite « en colonnes » :

```json
{"champs": ["id", "volume", "…"], "lignes": [[0, 11, "…"], [1, 11, "…"]]}
```

`champs` donne le nom de chaque colonne ; chaque élément de `lignes` est un tableau de même
longueur. Les identifiants (`id`) sont les rangs des lignes : `lignes[i][0] == i`. Les renvois
(`volume`, `decret`, `doublon_de`) sont des rangs dans le fichier visé. Ils changent à chaque
reconstruction : ne pas les conserver ailleurs.

Une date est une chaîne `AAAA-MM-JJ` ou `null`. Un **état** accompagne chaque date :

| État | Sens | Que montrer |
|---|---|---|
| 0 | lue telle quelle par l'OCR | la date |
| 1 | corrigée ou déduite par le programme : chiffre 1 lu 4 (« 45 décembre 4873 », « 41879 »), année rétablie d'après la livraison qui publie le décret (« du 13 février », « 18892 »), ou « même jour » que le décret imprimé juste avant | la date, en disant qu'elle a été rétablie |
| 2 | suspecte : illisible, ambiguë ou contredite par un contrôle. La valeur est `null`, **ou une lecture seulement possible** (« 44 mai » donné comme 14 mai, qui peut être le 11 ; date très antérieure à sa publication ; année ramenée dans le volume) | le texte brut, et la valeur comme simple hypothèse |

Le texte brut de la date (`date_brute`) est conservé chaque fois que l'OCR en donne un.

## 2. `bogga-volumes.json`

| Champ | Type | Sens |
|---|---|---|
| `annee` | entier | année du volume |
| `item` | chaîne | identifiant Internet Archive, copié de la notice |
| `doc` | chaîne | préfixe exact des fichiers du volume dans l'item, lu dans la notice (jamais reconstruit) |
| `famille` | `"tesseract"` ou `"harvard"` | exemplaire océrisé par Internet Archive (Tesseract), ou numérisation Google de la bibliothèque de Harvard (1864, 1872, 1876) |
| `lien_volume` | chaîne | page du volume sur archive.org |
| `lien_page` | chaîne | modèle de lien vers une feuille : remplacer `{leaf}` par le champ `feuille` |
| `image_page` | chaîne | modèle d'adresse de l'image d'une feuille : remplacer `{leaf}` et `{largeur}` (largeur demandée en pixels, non respectée au pixel près) |
| `lien_verifie` | chaîne | exactement `"non vérifié"` (18 volumes), ou une phrase de résultat qui commence par `oui :`, `partiel :` ou `non :` — contrôle de `verifier --liens`, ou contrôle sur l'image pour 1873 et 1888. Tester d'abord l'égalité avec `"non vérifié"` |
| `bibliotheque` | chaîne ou `null` | bibliothèque qui a numérisé, quand elle est connue |
| `droits` | chaîne | mention de droits à afficher |
| `pagination` | objet | `feuilles`, `pages_numerotees`, `decalage_dominant` (feuille − page le plus fréquent), `pages_au_decalage_dominant`, `pages_calculees` |
| `livraisons` | objet | `nombre`, `premier_numero`, `dernier_numero`, `numeros_lus`, `numeros_calcules`, `numeros_incertains`, `dates_lues`, `dates_corrigees`, `dates_suspectes`, `clotures_non_lues` (livraisons dont la ligne « CERTIFIÉ CONFORME » n'a pas pu être lue : elles sont comptées, sans date) |
| `controle` | objet | fiche de contrôle, § 6 |

Les deux formes de lien viennent d'une seule table (`decretas/bogga/catalogue.py`) :

- item à un seul volume : `https://archive.org/details/<item>/page/n{leaf}/mode/1up` ;
- item à plusieurs volumes : `https://archive.org/details/<item>/<doc encodé>/page/n{leaf}/mode/1up`.

Ces deux formes ont été contrôlées sur l'image le 2026-11-11 pour 1873 et 1888 (rapport de
recherche), et la numérotation `n{leaf}` de la liseuse a été comparée à notre index pour 1866,
1868, 1872, 1876, 1880 et 1885 (`verifier --liens`) : identique, feuille pour feuille. Les
dix-huit autres volumes utilisent le même modèle sans contrôle propre (`"non vérifié"`). Aucun
lien n'a été ouvert dans un vrai navigateur. Le modèle `image_page` est copié du rapport de
recherche et n'a pas été retesté.

## 3. `bogga-decrets.json`

Une ligne par décret **tel que publié** : un décret republié a deux lignes, la seconde renvoyant
à la première par `doublon_de` ; les deux citations sont gardées.

| Champ | Type | Sens |
|---|---|---|
| `id` | entier | rang de la ligne |
| `volume` | entier | rang dans `bogga-volumes.json` |
| `nature` | chaîne | `"admission"` (formule « admis à jouir des droits de citoyen français » et ses variantes), `"naturalisation"` (« ont été naturalisés Français », « est naturalisée française »), `"reintegration"` (« réintégré(e)s dans la qualité de Français »), `"titre"` (volume de 1868 : décret annoncé par une ligne « N° 14. — Décret du … » sans formule) |
| `dates` | tableau de dates | date(s) du décret ; plusieurs quand l'en-tête dit « des 5 et 16 décembre 1872 » ; vide quand aucune n'a pu être trouvée ; peut contenir `null` (date imprimée mais illisible) |
| `date_etat` | 0, 1 ou 2 | le pire état des dates du décret (2 aussi quand `dates` est vide) |
| `date_brute` | chaîne | la date comme l'OCR la donne ; commence par « même jour que le décret précédent » quand l'en-tête dit « Par décret du même jour » |
| `entete` | chaîne | la phrase du décret, brute, 400 caractères au plus |
| `article` | chaîne ou `null` | numéro d'article lu avant le décret (« 350 »). **Peu fiable** (« 204% », « 461 » pour 161) : la page est la clé sûre |
| `livraison` | entier ou `null` | numéro de la livraison. Une livraison « bis » porte le numéro de la précédente |
| `livraison_etat` | 0, 1 ou 2 | 0 lu sur la page de titre de la livraison ; 1 calculé depuis une livraison voisine (peut être décalé d'une unité quand une livraison « bis » n'a pas été reconnue) ; 2 incertain |
| `livraison_date` | date ou `null` | date du « CERTIFIÉ CONFORME » de la livraison = **date de publication**. `null` quand cette ligne n'a pas pu être lue : la date de la livraison suivante n'est jamais prêtée |
| `livraison_date_etat` | 0, 1 ou 2 | état de cette date |
| `page` | entier ou `null` | page imprimée où commence la phrase du décret |
| `feuille` | entier | feuille correspondante |
| `derniere_feuille` | entier | dernière feuille où une entrée du décret a été trouvée |
| `entrees` | entier | nombre d'entrées de personnes découpées |
| `total_imprime` | entier ou `null` | nombre de personnes que la page annonce elle-même : « les 37 personnes ci-après désignées », ou dernier numéro d'une liste numérotée |
| `doublon_de` | entier ou `null` | `id` du décret dont celui-ci est la republication |
| `drapeaux` | entier (bits) | 1 = première page calculée ; 2 = l'en-tête dit « l'indigène / les indigènes dont … » ; 4 = aucune entrée découpée ; 8 = l'en-tête mentionne des « indigènes » parmi d'autres, sans dire lesquels |

Règles de contrôle appliquées aux dates : une date de décret n'est jamais postérieure à la
livraison qui le publie (sinon l'année est rétablie, état 1, ou la date est marquée 2) ; elle
n'est jamais prise dans le titre d'un autre acte, ni dans « Sénatus-Consulte du 14 juillet
1865 » ; les dates de livraison ne reculent jamais à l'intérieur d'un volume (une date illisible
n'est complétée que si une seule lecture tient entre ses voisines ; sinon elle reste `null`,
état 2).

Mesuré sur les 527 décrets : date du décret lue 284, rétablie 200, suspecte 43 (dont 6 sans
aucune date) ; date de publication lue 386, rétablie 96, suspecte ou absente 45 ; numéro de
livraison lu 340, calculé 177, incertain 10.

## 4. `bogga-entrees.json`

Une ligne par entrée de personne. Les blocs **non segmentés** (drapeau 8) sont dans le même
fichier : c'est le texte brut d'une page que le programme n'a pas su découper (colonnes
mélangées par l'OCR). Ils permettent de retrouver un nom sur une telle page, mais ce ne sont pas
des personnes identifiées : `nom` y est vide et il ne faut pas les compter.

| Champ | Type | Sens |
|---|---|---|
| `id` | entier | rang de la ligne |
| `volume` | entier | rang dans `bogga-volumes.json` |
| `decret` | entier | rang dans `bogga-decrets.json` |
| `nom` | chaîne | la partie « nom » **comme elle est écrite**, parenthèses comprises : `Nom (Prénom ben Père)`, `Nom (Prénom, Prénom)`, `Nom, Prénom` (mise en page 1870-1873), `Prénom ben Père ben Grand-père`. Jamais vide pour une personne ; les fautes de l'OCR y sont laissées |
| `texte` | chaîne | l'entrée entière comme l'OCR la donne (lignes jointes par une espace, rien de corrigé, numéro de liste compris) |
| `marqueurs` | entier (bits) | voir ci-dessous |
| `nationalite` | chaîne ou `null` | mot de nationalité imprimé, ramené au masculin singulier sans accent (`italien`, `marocain`, `suedois`) ; un nom de pays entre parenthèses n'en est pas un |
| `naissance` | entier ou `null` | année de naissance imprimée après « né(e) » ; `null` si absente ou impossible |
| `residence` | chaîne ou `null` | lieu après « demeurant à », ou lieu de naissance pour « y demeurant », ou dernier champ de « Nom, Prénom, nation, lieu » |
| `page` | entier ou `null` | page imprimée de l'entrée (celle où elle commence) |
| `feuille` | entier | feuille correspondante : c'est elle qu'on met dans `lien_page` |
| `drapeaux` | entier (bits) | voir ci-dessous |

`marqueurs` :

| Bit | Sens |
|---|---|
| 1 | le mot « indigène » est imprimé dans l'entrée (lu avec deux fautes d'OCR au plus : « indisène », « indirène ») |
| 2 | « musulman(e) » |
| 4 | « israélite » |
| 8 | « étranger / étrangère » comme statut (pas « régiment étranger » ni « légion étrangère ») |
| 16 | un mot de nationalité est imprimé (champ `nationalite`) |
| 32 | l'en-tête du décret dit lui-même « l'indigène / les indigènes dont le(s) nom(s) sui(ven)t » |
| 64 | personne « naturalisée Française » (sous-liste d'un décret, ou décret de naturalisation) |
| 128 | personne « réintégrée dans la qualité de Française » |

**Attention** : un marqueur dit ce qui est *imprimé*, pas ce qu'était la personne. De 1877 à
1888, beaucoup d'entrées d'« indigènes » ne portent pas le mot (« Prénom ben Père, cultivateur,
né à …, demeurant à … » sous un en-tête « les indigènes et étrangers dont les noms suivent ») :
l'absence du bit 1 ne permet de rien conclure. Avant le 24 octobre 1870, « indigène israélite »
désigne les Juifs d'Algérie (bits 1 et 4 ensemble). Quand deux personnes sont restées collées
dans une entrée (drapeau 64), les marqueurs et la nationalité peuvent être ceux de la seconde.

`drapeaux` :

| Bit | Sens |
|---|---|
| 1 | page imprimée calculée d'après les pages voisines (le numéro lu était absent ou incohérent) |
| 2 | l'entrée court sur deux pages (`page` et `feuille` sont celles du début) |
| 4 | nom incertain : fin du nom non reconnue, ou initiale abîmée par l'OCR (« waFictler (Prénom) ») |
| 8 | bloc non segmenté : texte brut, pas une personne identifiée |
| 16 | appartient à un décret republié (`doublon_de` du décret) |
| 32 | une année de naissance est imprimée mais sa lecture est impossible (« né en 1897 » dans le volume de 1888) |
| 64 | peut contenir **deux personnes** : entrée très longue, deux naissances, deux domiciles, ou un second « Nom (Prénom), » après une virgule. Le champ `nom` ne donne que la première : chercher aussi dans `texte` |
| 128 | personne nommée dans la phrase même du décret (« le sieur …, a été admis à jouir … ») |

Mesuré sur les 9 696 entrées : 546 portent le mot « indigène » (dont 117 aussi « israélite » et
161 « musulman ») ; 7 553 ont une année de naissance, 6 152 une résidence, 2 484 un mot de
nationalité ; 104 portent le drapeau 64, 10 le drapeau 4, 58 le drapeau 32.

## 5. `bogga-meta.json`

| Clé | Sens |
|---|---|
| `version_format` | 1 |
| `genere_le` | date de construction |
| `source`, `credit`, `bibliotheques` | à afficher : « Texte et images : Internet Archive (archive.org) », et « Harvard University (numérisation Google) » pour 1864, 1872, 1876 |
| `avertissements` | quatre phrases à montrer dans le bilan de recherche |
| `marqueurs`, `drapeaux_entrees`, `drapeaux_decrets`, `etats_dates`, `etats_numeros_livraison` | libellés français des codes ci-dessus |
| `couverture` | une ligne par année de 1861 à 1888, **y compris 1862 et 1887 qui manquent** : `annee`, `etat` (`"indexé"`, `"absent d'Internet Archive"`, `"non téléchargé"`), `volume`, `decrets`, `entrees`, `que_faire` (texte à afficher quand l'année n'apporte rien) ; pour les années indexées s'ajoutent `decrets_republies`, `entrees_hors_republication`, `entrees_marquees_indigene`, `blocs_non_segmentes`, `taux_pages_table`, `taux_listes_numerotees` ; pour les années absentes, `lien` (peut être vide) et `lien_verifie` |
| `pages_a_lire_a_la_main` | liste : `volume`, `annee`, `feuille` (ou `null`), `page`, `lien`, `raison`, `decret` (ou `null`) |
| `totaux` | `volumes`, `decrets`, `entrees`, `entrees_marquees_indigene`, `blocs_non_segmentes`, `pages_a_lire_a_la_main` |
| `fichiers` | taille brute et en gzip des trois fichiers en colonnes |

Quatre raisons mettent une page dans `pages_a_lire_a_la_main` (20 pages aujourd'hui) : liste non
découpée (colonnes mélangées) ; décret reconnu à sa formule mais sans aucune entrée ; page
indiquée par la table alphabétique du volume sans qu'aucun décret y ait été reconnu ; phrase de
décret lue hors de tout décret découpé. Quand la feuille n'a pas pu être déterminée (numéro de
page de la table sans feuille correspondante), `feuille` vaut `null` et `lien` mène au volume.

## 6. La fiche de contrôle d'un volume (`controle`)

Le programme se contrôle contre le volume lui-même, sans aucune source extérieure. Exemple
(volume de 1873) :

```json
{
  "table_alphabetique": {
    "trouvee": true, "feuille": 738, "nominative": false,
    "pages_listees_lisibles": 11, "pages_retrouvees": 11,
    "dont_a_la_page_suivante": 0, "dont_avec_confusion_1_4": 0,
    "pages_non_retrouvees": [], "numeros_douteux": [5], "numeros_illisibles": 1,
    "taux_pages": 1.0, "decrets_trouves_hors_table": []
  },
  "listes_numerotees": {
    "decrets_avec_total_imprime": 15, "personnes_annoncees": 926, "entrees_trouvees": 852,
    "taux_entrees": 0.9201, "decrets_avec_plus_d_entrees_que_le_total": 4
  },
  "formule_hors_decret": [], "decrets": 15, "decrets_sans_entree": 0,
  "decrets_republies": 1, "entrees": 877, "pages_a_lire_a_la_main": 1
}
```

- **Table alphabétique.** La plupart des volumes ont, en fin de volume, une table qui donne à
  « NATURALISATION » les pages des articles d'admission. `taux_pages` = part de ces pages qui
  tombent dans un décret trouvé. La table est elle-même du texte OCR : un numéro hors de l'ordre
  croissant va dans `numeros_douteux` (il ne compte ni pour ni contre), un jeton illisible dans
  `numeros_illisibles`. Une page est aussi comptée retrouvée quand le décret commence à la page
  suivante (titre de l'article en bas de page) ou quand elle ne diffère que par des 1 lus 4.
  `nominative: true` (1880) : la table liste les personnes, pas les pages ; elle n'est pas
  exploitée. `trouvee: false` (1867, et les volumes sans décret) : `taux_pages` vaut `null`.
  Sur l'ensemble : 279 pages retrouvées sur 289 pages listées lisibles (96,5 %).
- **Listes numérotées.** Quand la page annonce un total (« les 37 personnes ») ou numérote la
  liste, `taux_entrees` = entrées trouvées / personnes annoncées, chaque décret étant plafonné à
  son total (un décret avec trop d'entrées ne compense pas un autre). C'est une **borne
  supérieure** du rappel : une entrée parasite peut masquer un oubli. Sur l'ensemble des décrets
  qui s'y prêtent : 2 479 sur 2 699 (91,9 %), de 78 % (1874) à 100 %. Les volumes de 1870, 1879,
  1880, 1882, 1884, 1886 et 1888 n'ont pas de liste numérotée : le taux vaut `null`, ce qui ne
  veut pas dire 100 %.
- Ces deux taux mesurent le découpage du **texte OCR**. Ils ne disent rien des fautes de lecture
  à l'intérieur d'un nom (un « tt » lu « lt ») : un nom mal lu est une entrée trouvée.

## 7. Ce que le fichier ne contient pas, et ses limites connues

- Les années **1862** et **1887** (absentes d'Internet Archive) et tout ce qui suit 1888.
- Dans les volumes de 1861, 1863, 1864, 1865 et 1871, le programme n'a reconnu aucun décret
  d'admission. Pour 1861, 1863 et 1864 c'est attendu (années antérieures au sénatus-consulte du
  14 juillet 1865) ; pour 1865 et 1871, une recherche des mots « citoyen français » et
  « naturalisation » dans le texte OCR n'a trouvé que des textes réglementaires, mais ce n'est
  pas une lecture des pages.
- Les décrets « qui accordent la naturalisation à … » de 1866-1867 rédigés sans la formule
  d'admission ne sont pas repris.
- Aucune correction du texte : ni les noms, ni les lieux. Le rapprochement des graphies est
  l'affaire de la recherche (variantes saisies par l'utilisateur), pas de ce fichier.
- Environ une entrée sur cent contient encore deux personnes collées (drapeau 64 quand le
  programme s'en aperçoit : 104 entrées) ; quelques dizaines de noms gardent un signe parasite
  en tête (« ES Nom (Prénom) ») ou une parenthèse que l'OCR n'a pas fermée.
- Quand un en-tête annonce plusieurs décrets sans sous-titres datés, les personnes sont
  rattachées au décret qui porte toutes les dates.
- Un numéro de livraison calculé peut être décalé d'une unité : la numérotation se recouvre
  d'un numéro entre les volumes 1867 et 1868, 1869 et 1870, 1870 et 1871, 1877 et 1878. Les
  numéros du volume de 1864 (un seul numéro lu, manifestement faux) sont tous incertains.
- Les contrôles portent sur le texte OCR, jamais sur l'image : la page ouverte par le lien
  reste la seule preuve.

## 8. Reconstruire

Depuis la racine du dépôt :

```bash
python3 -m decretas.bogga telecharger --simulation
python3 -m decretas.bogga telecharger
python3 -m decretas.bogga construire
python3 -m decretas.bogga verifier
```

- `-m decretas.bogga` : lance le module `decretas/bogga/__main__.py` (Python 3.12, bibliothèque
  standard seule).
- `telecharger` : demande à Internet Archive, par volume, trois petits fichiers de texte
  (`_hocr_searchtext.txt.gz`, `_hocr_pageindex.json.gz`, `_page_numbers.json`) et les range sous
  `data/raw/ia/<item>/`, avec un journal `data/raw/ia/manifest.jsonl` (une ligne par requête :
  `url`, `status`, `bytes`, `sha256`, `at`). Ni image ni PDF. Une adresse déjà obtenue n'est
  jamais redemandée.
  - `--simulation` : n'envoie rien et n'écrit rien, affiche ce qui serait demandé.
  - `--annees 1873,1888` : seulement ces années.
  - `--delai 5.5` : secondes entre deux requêtes (5 au minimum, quoi qu'on demande).
  - `--plafond 150` : nombre maximal de requêtes vers archive.org, tous passages confondus.
  - `--reprendre-apres-refus` : décision humaine — un refus antérieur (403 ou 429) est levé.
  - `--reessayer-echecs` : redemander les adresses restées en erreur 5xx ou sans réponse.
- `construire` : découpe les volumes et écrit les quatre fichiers (une quarantaine de
  secondes) ; `--annees` limite aux années données (les fichiers ne contiennent alors que
  celles-là).
- `verifier` : relit les fichiers, contrôle leur cohérence et retrouve deux notices témoins par
  leur structure (page, feuille, date, livraison, nombre d'entrées). `--liens 1868,1872,1876`
  (trois années au plus, une requête chacune) demande à Internet Archive la table des pages de
  sa liseuse et la compare à notre index ; le résultat est écrit dans
  `data/build/bogga/liens-verifies.json` et repris par `construire` dans `lien_verifie`.
  `--simulation` (avec `--liens`) affiche l'adresse sans rien envoyer ni écrire ; `--plafond`
  comme ci-dessus.

Tests : `python3 -m unittest discover -s tests -t .` (`-s tests` : répertoire où chercher ;
`-t .` : racine du projet, pour que `decretas` s'importe). Les jeux d'essai sont synthétiques :
noms, prénoms, lieux et dates y sont inventés.
