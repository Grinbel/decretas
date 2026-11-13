# Décrets en images seules — stratégie, outils et marche à suivre

Ce document traite le cas difficile du projet : les décrets que les Archives nationales (AN) publient
**en images, sans que les noms soient saisis**. Il dit ce que l'on sait, ce que l'on ignore, ce que font
les outils de `decretas/an_images/`, et la suite exacte de commandes à lancer le jour où le site des AN
répond de nouveau.

Vocabulaire : celui de [CONTEXT.md](../CONTEXT.md). Sigles : **AN** = Archives nationales ; **SLV** =
Salle de lecture virtuelle, le site `www.siv.archives-nationales.culture.gouv.fr` ; **vue** = une image,
c'est-à-dire une page photographiée d'un décret ; **OCR** = lecture automatique d'un texte imprimé ou
dactylographié à partir de son image ; **HTR** = lecture automatique d'une écriture manuscrite.

Tous les chemins sont donnés depuis la racine du dépôt. Aucun exemple ne reprend une personne réelle :
les noms cités (« Testaoui », « Fictivo »…) sont inventés. Les décrets, documents publics, sont désignés
par leur inventaire et leur notice.

**État au 2026-11-11.** La SLV a répondu `503` toute la journée (jour férié ; une panne, pas un refus).
Trois vérifications ont été faites par cet outil, à 18 h 05, 19 h 16 et 23 h 42 (heure de Paris) : trois
fois `503`. **Aucune page de décret, aucune visionneuse, aucune image de décret de la SLV n'a donc été
vue.** Tout ce qui suit sépare ce qui est constaté de ce qui est supposé.

---

## 1. L'essentiel

1. **1 518 décrets** intéressant l'Algérie n'existent qu'en images : 781 pour 1899-1912, 63 pour
   avril-décembre 1928, 674 pour 1933-1948 (compte fait sur `site/data/an-decrets.json`, état `image`).
2. Pour chacun, les AN donnent déjà la **date, le titre, la cote, parfois le numéro de document** et un
   **lien d'images propre au décret**. On sait donc *quel décret ouvrir* ; on ne sait pas *qui est dedans*.
3. Les métadonnées des fichiers d'images sont, d'ordinaire, techniques (dimensions, appareil, date de
   numérisation). **Il n'y a aucune raison d'y attendre un nom de personne**, et l'outil est prêt à le
   constater sur la première image reçue. Elles servent à autre chose : ordonner les vues, vérifier qu'il
   n'en manque pas, citer « vue 3 sur 7 ».
4. **Le nom ne peut venir que de la lecture de l'image.** Quatre voies, à mener ensemble : lecture humaine
   guidée ; recoupement avec le même décret *imprimé* au Bulletin ou au Journal officiel ; lecture par
   machine suivie d'une vérification humaine ; demande des données aux AN.
5. Rien n'est laissé au hasard dans les outils : chaque requête est journalisée, chaque corps reçu est
   gardé, chaque lecture porte la mention « à vérifier sur l'image », chaque ligne non comprise est
   conservée et reste cherchable, et un résultat vide n'est jamais présenté comme une absence de décret.

---

## 2. Ce que l'on sait sans ouvrir une image

### 2.1 Les métadonnées du décret (constaté, dans les exports XML des AN)

| Donnée | Exemple (décret public) | Présence |
|---|---|---|
| Date du décret | 5 février 1905 | toujours |
| Titre | « Décret de naturalisations algériennes du 5 février 1905. » | toujours ; il dit si l'Algérie est concernée |
| Classe (calculée par ce projet) | A1, A2, A3, R | toujours — voir ci-dessous |
| Cote de la liasse | `BB/34/424` | presque toujours |
| Numéro de document dans la liasse | « document 21 » | 1899-1930 ; absent de 1931 à 1948 |
| Lien d'images du décret | `/siv/media/FRAN_IR_057220/AP001236/` | toujours |

Classes : **A1** le titre nomme l'Algérie ; **A2** « admission aux droits de citoyen français » sans
territoire ; **A3** décret composite qui inclut l'admission ; **R** rejet, révocation ou retrait.

Répartition des 1 518 décrets en images seules (`data/build/an-images/plan-collecte.md`) :

| Période | A1 | A2 | A3 | R | Total |
|---|---:|---:|---:|---:|---:|
| 1899-1912 | 636 | 0 | 0 | 145 | 781 |
| avril-décembre 1928 | 53 | 0 | 0 | 10 | 63 |
| 1933-1948 | 434 | 148 | 80 | 12 | 674 |

Plus d'un décret sur trois de 1933-1948 (toutes natures confondues) partage sa date et son titre avec un
autre, et n'a pas de numéro de document : seule sa notice (`D4`, `D5`…) les distingue. Il faut donc toujours garder l'identifiant de
la notice, jamais « le décret du tant ».

### 2.2 Le numéro de média qui croît avec la date (constaté dans le XML ; interprétation supposée)

Sur 253 467 liens d'images des exports, **quatre** portent en plus un identifiant de média :

| Décret du | Inventaire / notice | Identifiant |
|---|---|---|
| 26 décembre 1889 | `FRAN_IR_056731` / `idd_1889_12_22` | `DAFANCH94_NUMJ011088_D` |
| 26 janvier 1891 | `FRAN_IR_056871` / `idd_1891_01_20` | `DAFANCH94_NUMJ014520_D` |
| 23 mai 1896 | `FRAN_IR_056877` / `idd_1896_05-25` | `DAFANCH94_NUMJ023847_D` |
| 30 mars 1927 | `FRAN_IR_057667` / `idd_1927_03_08` | `DAFANCH94_NUMJ064396_D` |

Constaté : le numéro croît avec la date du décret. **Supposé, non vérifié** : ce serait un compteur
continu de vues sur toute la sous-série BB/34. Sous cette hypothèse, `plan-collecte` calcule :

| Entre | et | Écart des numéros | Décrets datés dans l'intervalle | Numéros par décret |
|---|---|---:|---:|---:|
| 26 décembre 1889 | 26 janvier 1891 | 3 432 | 358 | 9,6 |
| 26 janvier 1891 | 23 mai 1896 | 9 327 | 1 569 | 5,9 |
| 23 mai 1896 | 30 mars 1927 | 40 549 | 9 389 | 4,3 |

Soit 4,7 numéros par décret en moyenne, tous décrets confondus ; et 1 805 décrets sont datés avant le
premier repère, qui porte le numéro 11 088 (6,1 par décret si le compteur part de zéro en 1883). Les
ordres de grandeur concordent : c'est un indice sérieux que le numéro compte des vues, **pas une preuve**.
Si la reprise le confirme, ce numéro devient un instrument : deux décrets voisins encadrent les numéros
des vues d'un troisième, un trou dans la suite signale une vue manquante, et le nombre de vues d'un
décret se déduit sans l'ouvrir. Si elle l'infirme (compteur par lot, par liasse…), ces moyennes ne valent
rien et le rapport de reprise le dira (§ 3 du rapport : « Que désigne l'identifiant… »).

### 2.3 Les métadonnées contenues dans les fichiers d'images (attendu ; à confirmer)

Une image peut porter : la densité (points par pouce), des champs EXIF (appareil, logiciel, date,
`ImageDescription`, `Copyright`), un paquet XMP, des champs IPTC, des commentaires, un profil de couleur ;
un PNG, des blocs de texte ; un TIFF, ses balises ; un JPEG 2000, des boîtes XML.

Attente raisonnable pour des images de diffusion issues d'une chaîne de numérisation d'archives : **des
données techniques, rien de nominatif**. Au mieux une cote ou un numéro de lot dans un champ descriptif.
Ce n'est qu'une attente : la commande `metadonnees` liste à part tout champ de **texte libre**, justement
parce que c'est le seul endroit où une cote ou une légende pourrait se trouver.

Ce que l'outil a réellement lu le 2026-11-11, sur les seules images présentes dans le dépôt :

| Fichiers | Résultat |
|---|---|
| 49 captures du tutoriel officiel « Devenir français » (`data/samples/an-remote/verify/tutoimg/`), PNG extraits d'un PDF | densité 72 ppp, aucun texte, aucun EXIF : 0 champ de texte libre |
| 2 pages du Bulletin officiel venues d'Internet Archive (`data/samples/internet-archive/raw/tests/`) | JPEG en niveaux de gris, JFIF seul, qualité ≈ 75 : 0 champ de texte libre. Le nom du fichier annonce une largeur de 1 000 px, l'image en fait 1 870 : l'outil le signale |
| 6 pages du Journal officiel venues de Wikimedia (`data/samples/other-sources/wikimedia/`) | JPEG sans JFIF ni EXIF : 0 champ de texte libre |
| `data/samples/gallica/07c-iiif-image.jpg` | **ce n'est pas une image** mais une page HTML (refus de Gallica) : l'outil le dit au lieu d'échouer |

Sorties gardées : `data/build/an-images/metadonnees-tutoriel-girophares.txt` et `.json`,
`data/build/an-images/metadonnees-echantillons-jpeg.txt` et `.json`. Aucune de ces images n'est une image
de décret de la SLV : la question reste ouverte pour celles-ci jusqu'à la reprise.

---

## 3. Le nom ne vient que de la lecture : quatre voies

### 3.1 Lecture humaine guidée (disponible tout de suite)

Le site guide déjà l'utilisateur (guide « Années en images seules : lire les décrets vous-même » de
`site/contenu/guides.json`). Le principe : réduire la liste des décrets à lire, puis lire chaque décret en
entier.

- **Par l'année de naissance.** Il fallait 21 ans pour demander l'admission par décret : un ancêtre né en
  1885 ne peut figurer que dans un décret de 1906 ou après.
- **Par la classe.** De 1933 à 1948, les décrets « d'admission aux droits de citoyen français » (A2) et
  les décrets composites (A3) sont distincts des naturalisations d'étrangers (A1). De 1899 à 1912 et en
  1928, les titres ne distinguent pas : tout est « naturalisations algériennes » (A1).
- **Pas par l'alphabet.** Dans un décret, les personnes ne se suivent ni par ordre alphabétique ni par
  numéro de dossier (constaté sur l'ordre des notices des années saisies et sur les captures de 1932).
  **Il faut lire le décret en entier.**

Taille de la lecture, hors rejets (commande `plan-collecte --ne-en ANNEE --classes A1,A2,A3`) :

| Ancêtre né en | Décrets à lire, 1899-1912 | 1928 | 1933-1948 (A1) | 1933-1948 (A2 et A3) | Total |
|---|---:|---:|---:|---:|---:|
| 1870 ou avant | 636 | 53 | 434 | 228 | 1 351 |
| 1880 | 554 | 53 | 434 | 228 | 1 269 |
| 1890 | 91 | 53 | 434 | 228 | 806 |
| 1900 | 0 | 53 | 434 | 228 | 715 |
| 1910 | 0 | 0 | 434 | 228 | 662 |
| 1920 | 0 | 0 | 4 | 102 | 106 |

Ces nombres sont grands. C'est la raison d'être des trois autres voies. Ils disent aussi ce qu'un
bénévole peut faire : lire une année, pas une vie.

Ce que la lecture humaine doit rapporter, pour devenir une **citation** : la date du décret, sa notice
(inventaire et identifiant), la cote, le numéro de la vue (« vue 3 sur 7 »), le nom tel qu'il est écrit, et
le numéro de dossier en marge (« 1234 X 45 ») qui ouvre le dossier individuel.

### 3.2 Le même décret, imprimé (recoupement)

Les décrets étaient publiés. Un texte imprimé est lisible par recherche plein texte, là où une image de
dactylographie ne l'est pas.

| Période du décret | Où il a pu être imprimé | Accès |
|---|---|---|
| 1899-1926 | *Bulletin officiel du Gouvernement général de l'Algérie* | Gallica, pour un humain (1907 manque, 1890 est incomplet, une autre année manque sans être identifiée) |
| à partir de 1927 | *Journal officiel de l'Algérie* | Gallica, pour un humain (une année manque, non identifiée) |
| toute la période | *Journal officiel de la République française*, lois et décrets | Gallica (1880-1946 au moins) ; Légifrance à partir de 1924 |

Les liens viennent de `site/contenu/liens.json` (gabarits `gallica-*`, `legifrance-*`) ; Gallica refuse les
programmes, ces liens sont donc pour une personne, dans son navigateur.

**Règle de recoupement.** Une occurrence trouvée dans l'imprimé désigne un décret en images quand :

1. la **date du décret** écrite dans l'imprimé est celle de la notice des AN ;
2. la **nature** concorde (admission, naturalisation) ;
3. le **nom** et, s'ils sont imprimés, l'année et le lieu de naissance concordent avec ce que l'on cherche.

On ouvre alors ce décret-là, et lui seul, pour lire la page.

**Incertitudes, à dire à l'utilisateur.**

- Le délai entre un décret et sa publication n'a été mesuré que sur le Bulletin officiel de 1873 (28 à
  195 jours, médiane 74) et de 1888 (35 à 116 jours, médiane 64,5). **Après 1888 : non mesuré.** Chercher
  dans les six mois qui suivent la date du décret ; un décret de fin d'année paraît l'année suivante.
- Que *tous* les décrets d'admission de 1899-1912 et de 1933-1948 aient été imprimés, et où : **non
  vérifié**. Un seul extrait de 1927, de seconde main, montre une admission au Journal officiel sous la
  forme « NOM (Prénom ben Père), qualité, né le … à … ».
- Plusieurs décrets portent la même date : la date seule ne suffit pas, il faut la nature et le nom.
- L'OCR de Gallica déforme les noms (« Belkaccm » pour « Belkacem » dans l'extrait cité) : essayer les
  variantes. Ne pas trouver un nom dans l'imprimé **ne prouve rien**.

### 3.3 Lecture par machine, vérifiée par des personnes

| Période | Écriture | Lecture par machine |
|---|---|---|
| 1932 | dactylographiée — **constaté** sur les captures du tutoriel officiel | OCR ordinaire plausible ; aucun essai fait (Tesseract n'est pas installé, aucune image en pleine définition) |
| 1933-1948 | dactylographiée, **vraisemblablement** (continuité avec 1932) ; non vu | idem, à essayer sur les exemplaires de la reprise |
| 1928 | **non vu** | inconnu |
| 1899-1912 | **non vu** : manuscrite ou dactylographiée | si manuscrite, un OCR ne lit rien d'utile ; il faut un modèle d'écriture manuscrite (HTR) ou une lecture humaine |

C'est la première chose que la reprise doit établir (étapes B2, E1, C1, F1) : elle décide de tout le reste.

Ce que les captures de 1932 montrent de la page, et que l'analyseur sait lire : un paragraphe par
personne ; en marge gauche le numéro de dossier (« 1234 X 32 »), souvent suivi d'une coche au crayon ;
`NOM (Prénoms), profession, né le … à … (pays), demeurant à … (département).` ; l'épouse introduite par
« et NOM (Prénom), sa femme, née le … » ; les enfants numérotés « 1°) … 2°) … », un par ligne, avec
« d° » pour un lieu répété ; une femme mariée écrite « NOM (Prénoms) femme NOM-DU-MARI » ; sous chaque
personne la ligne des droits de sceau (« Remise totale. ») ; la machine à écrire tape `I` pour `1` et `O`
pour `0` (« né le 7 mars I88I ») ; la date du décret est un tampon en haut à droite (« 2 FEV 1932 »).
**La forme des noms dans un décret d'admission d'« indigènes » algériens n'a pas été vue.**

Règles de la lecture par machine dans ce projet :

- toute occurrence porte `confiance = "lecture automatique — à vérifier sur l'image"` ; c'est un
  **indice**, jamais une citation ;
- le résultat va dans `data/build/an-images/lectures.json`, **pas** dans `site/data/` : publier des
  lectures de machine est une décision séparée, à prendre après avoir mesuré leur taux d'erreur sur des
  pages relues par une personne ;
- un nom mal lu est introuvable par une recherche exacte : le moteur de recherche du site tolère déjà les
  graphies approchantes, mais une lecture fausse reste fausse — d'où la relecture ;
- un décret dont une vue n'a pas été lue est marqué « lu partiellement » : une absence dans ses lignes ne
  dit rien.

**Faire relire par des volontaires.** Les AN ont leur propre programme d'indexation collaborative,
Girophares, dont le projet « Devenir français » porte sur les décrets de 1932 à 1948 (progression
annoncée de 99 %, 218 contributeurs ; « interruption provisoire » annoncée le 23 septembre 2026). Lien :
entrée `an-girophares-devenir-francais` de `site/contenu/liens.json`. Deux conséquences : les noms de
1933-1948 sont peut-être déjà saisis et simplement pas encore versés dans la SLV — **le demander avant de
refaire le travail** (§ 3.4) ; et un volontaire du projet peut être orienté vers ce programme plutôt que
vers une saisie parallèle. Pour 1899-1912, rien de tel n'est annoncé.

### 3.4 Demander les données aux Archives nationales

À écrire à la direction des publics des AN, en une seule lettre, avec des questions fermées :

1. Les saisies du projet « Devenir français » pour 1933-1948 seront-elles versées dans les inventaires de
   la SLV, et quand ? Peuvent-elles être communiquées avant ?
2. Les décrets de 1899-1912 et de 1928 font-ils l'objet d'une indexation en cours (l'inventaire racine dit
   qu'elle a été « engagée en partenariat avec Filae » en 2021) ? Sous quelles conditions de réutilisation ?
3. Un projet gratuit et sans publicité peut-il publier un index de noms **lu par lui-même sur les images**
   de ces décrets ? Deux textes des inventaires sont en cause : la mention « usage privé », et la clause
   qui soumet à l'accord de Filae toute publication nominative de plus de 1 000 individus « pour les
   années indexées par Filae ». Ce document ne tranche pas ce point de droit.
4. Existe-t-il un moyen prévu pour obtenir les images d'une série (lot, manifeste, autre) plutôt que de
   les demander une par une ?

Tant que la réponse à la question 3 n'est pas écrite, les lectures restent sur le poste de travail.

---

## 4. Les outils

Module `decretas/an_images/`, bibliothèque standard de Python seulement (Pillow, s'il est installé, sert
uniquement à recouper les dimensions lues). À lancer depuis la racine du dépôt.

| Commande | Ce qu'elle fait | Réseau |
|---|---|---|
| `python3 -m decretas.an_images disponibilite` | une requête : le site répond-il ? | 1 requête à la SLV |
| `python3 -m decretas.an_images reprise` | le plan d'observation : un exemplaire de chaque cas, rapport | 40 requêtes au plus par passage |
| `python3 -m decretas.an_images metadonnees <fichiers…>` | ce que disent un fichier d'image, son nom, son adresse | aucun |
| `python3 -m decretas.an_images lire <dossier>` | images → transcriptions → occurrences de noms à vérifier | aucun (sauf le programme externe que vous brancheriez) |
| `python3 -m decretas.an_images plan-collecte` | combien de décrets, de requêtes, d'heures | aucun |

### 4.1 `reprise` : le plan et ses règles

Le plan reprend les 30 requêtes du rapport de recherche du 2026-11-11, amendé comme sa vérification le
demandait : il **commence par les quatre liens à identifiant de média** (L1 à L4), puis demande un
exemplaire de chaque cas.

| Cas | Étapes | Exemplaire | Question |
|---|---|---|---|
| `lots` | L1-L4 | les quatre liens du § 2.2 | que désigne « _D » ; noms et ordre des médias |
| `personne-avec-images` | P1, P2, P3 (+ A1) | première personne du décret `FRAN_IR_057268` / `AP002722` (11 janvier 1913) | **le lien d'une personne ouvre-t-il sa page ou tout le décret ?** |
| `personne-sans-images` | S1 (+ S2) | première personne du décret `FRAN_IR_056878` / `idd_1897_01-01` | sa page propose-t-elle les images du décret parent ? |
| `image-1899-1912` | B1, B2 | `FRAN_IR_057220` / `AP001236` (5 février 1905) | manuscrit ou dactylographié ? |
| `image-1928` | E1 (+ E2) | `FRAN_IR_057672` / `YI004589` (1er mai 1928) | mêmes noms de fichiers ? aspect |
| `image-1933-1948` | C1 (+ C2) | `FRAN_IR_058672` / `D4` (2 janvier 1935) | vues, noms, taille, lisibilité |
| `admission-1946-1947` | F1 (+ F2) | `FRAN_IR_058664` / `D32` (17 juillet 1946) | forme des noms d'un décret d'admission |
| `site` | J1, T1, T2, G1, G2, H1-H3, U1, X1, X2, O1 | onglets, recherche, aide, conditions, exports, OAI | compléments |

Les étapes entre parenthèses et le cas `site` forment le **palier 2** ; le reste, le **palier 1**. Les deux
personnes exemplaires ne sont pas écrites dans le code : elles sont prises dans `site/data/` au moment du
lancement (« la première personne de ce décret »).

Règles appliquées par le programme, sans option pour les lever sur l'hôte réel :

- le client poli du projet (`decretas/net.py`) : agent utilisateur honnête, une requête à la fois ;
- **6 s au moins** entre deux requêtes ; **40 requêtes au plus** par passage, 80 par jour ;
- le témoin de session anonyme posé par le site est renvoyé, comme le ferait un navigateur ; sa valeur
  est gardée dans `data/raw/an-images/reprise/etat.json` (droits 600), jamais affichée, jamais écrite au
  manifeste ni au rapport. Les corps de pages sont enregistrés bruts : si le site écrit lui-même
  l'identifiant de session dans ses liens, il s'y trouve — ils restent sous `data/raw/`, ignoré par git ;
- chaque redirection est une requête journalisée ; une redirection vers un autre hôte est notée, pas suivie ;
- **premier `502`, `503` ou délai dépassé : arrêt de 30 minutes** (code de sortie 3) ; **troisième de la
  journée : arrêt jusqu'au lendemain** (code 4) ; rien n'est réessayé entre-temps ;
- `403`, `429` ou page anti-robot : **arrêt complet** (code 5) jusqu'à une décision humaine ;
- ces arrêts valent **pour l'hôte, quelle que soit la commande** qui les a rencontrés : `disponibilite` et
  `reprise` lisent et écrivent le même fichier d'arrêt, `data/raw/an-images/arret.json` (droits 600 ; option
  `--arret` pour un essai), avant d'envoyer quoi que ce soit. Un refus reçu par `disponibilite` arrête donc
  `reprise`, et une pause de `reprise` arrête `disponibilite`. Seul `reprise --lever-blocage` lève un refus ;
- tout hôte est traité comme l'hôte réel (délai minimal et plafonds), sauf un serveur d'essai local
  (`127.0.0.1`, `localhost`, `::1`) : une variante du nom (point final, majuscules, adresse IP) ne fait pas
  sortir des limites ;
- chaque corps reçu, erreurs comprises, est gardé sous `data/raw/an-images/reprise/` avec un manifeste
  (`manifest.jsonl`, une ligne par requête) ; un second lancement ne redemande que ce qui manque ;
- **deux images au plus par cas**, la première vue et une vue intérieure, à la plus grande taille que la
  page propose.

Les adresses d'images sont cherchées dans les pages par plusieurs stratégies indépendantes, parce que la
structure réelle est inconnue : attributs des balises (`img`, `a`, `source`, `iframe`…), attributs `data-*`,
gestionnaires `onclick`, blocs JSON, chaînes des scripts, motif `/mm/media/download/…`, noms finissant
comme un fichier d'image, indices IIIF (`info.json`, `manifest`). Le rapport dit ce que chaque stratégie a
trouvé. **Limite** : l'outil lit le HTML reçu, il n'exécute pas le JavaScript ; si la visionneuse construit
ses adresses dans le navigateur, il faudra lire le corps enregistré et donner l'adresse à la main
(`--suivre`).

Le rapport `data/build/an-images/reprise-rapport.md` répond point par point : 1 chaînes de redirection ;
2 structure des pages d'arrivée ; 3 noms et ordre des images, et ce que désigne l'identifiant « _D » ;
4 lien d'une personne : sa page ou tout le décret ; 5 tailles offertes ; 6 métadonnées des images ;
7 compléments ; 8 ce qui reste inconnu ; 9 journal des requêtes. Un point sans réponse est écrit
« Non observé ».

### 4.2 `metadonnees`

Lit sans outil tiers : JPEG (JFIF et densité, EXIF avec `DateTime`, `Software`, `Make`, `Model`,
`ImageDescription`, `Copyright`, sous-répertoires EXIF et GPS, paquet XMP, IPTC et ressources Photoshop,
commentaires, profil ICC, qualité estimée d'après la table de quantification, octets après la fin de
l'image) ; PNG (blocs de texte, densité, date, EXIF) ; TIFF (balises) ; JPEG 2000 (boîtes, XML, XMP) ; GIF
et WebP (dimensions, commentaires). Elle décode aussi le **nom du fichier** (lot, numéro, suffixe de
taille) et l'**adresse** d'où il vient, en séparant ce qui est constaté de ce qui est une hypothèse, et
compare les noms d'une suite de fichiers (« le nombre croît de 1 en 1 : le nom donne l'ordre des vues »).
Un fichier abîmé, ou qui n'est pas une image, est décrit comme tel ; rien ne fait échouer la commande.

### 4.3 `lire` : les lecteurs et leur contrat

Un lecteur transforme une image en texte. Trois lecteurs, une seule interface :

| Lecteur | Ce qu'il lit | Mention portée par ses lignes |
|---|---|---|
| `manuel` | le fichier texte posé à côté de l'image par une personne : `page.jpg` → `page.txt` ou `page.jpg.txt` | « transcription manuelle — à vérifier sur l'image » |
| `tesseract` | l'image, par le programme Tesseract **s'il est installé** | « lecture automatique — à vérifier sur l'image » |
| `commande` | l'image, par un programme externe décrit dans un fichier de configuration | « lecture automatique — à vérifier sur l'image » |

Le mode `auto` (par défaut) prend la transcription manuelle quand elle existe, sinon Tesseract s'il est
là. **Tesseract n'est pas installé sur le poste le 2026-11-11** : la commande le dit, donne la commande
d'installation et liste chaque image non lue ; elle n'échoue jamais en silence. Installation (Debian,
Ubuntu) : `sudo apt install tesseract-ocr tesseract-ocr-fra` — `sudo` exécute avec les droits
d'administration, `apt install` installe des paquets, `tesseract-ocr` est le programme,
`tesseract-ocr-fra` son modèle du français.

**Contrat du lecteur `commande`** (pour brancher plus tard un modèle de vision ou tout autre outil) :

```json
{"commande": ["mon-lecteur", "--image", "{image}"], "delai_s": 300, "nom": "essai"}
```

- `commande` est une **liste** d'arguments, lancée **sans interpréteur de commandes** ; `{image}` est
  remplacé par le chemin absolu de l'image (ajouté en dernier argument si aucun élément ne le contient) ;
- le programme écrit la transcription sur sa **sortie standard**, en UTF-8, une ligne de la page par
  ligne, dans l'ordre de lecture, le numéro de marge au début de la ligne qu'il regarde ;
- code de sortie 0 en cas de succès ; tout autre code, un délai dépassé (`delai_s`, 1 à 3 600 secondes) ou
  une sortie vide est rapporté comme un échec **pour cette image** ;
- `nom` (facultatif) étiquette le lecteur dans les lignes produites (`commande:essai`).

Ce dépôt ne fournit **aucun identifiant ni aucune clé**, n'appelle rien par défaut et ne configure aucun
programme : ce dont un programme externe a besoin est son affaire, lu dans son propre environnement.
Envoyer des images à un service extérieur est une décision à prendre en connaissance de cause (les pages
portent des noms de personnes).

**Ce que produit l'analyse.** Pour chaque personne, épouse et enfant, une ligne au format d'entrée du
moteur de recherche du site (extrait des champs ; s'y ajoutent profession, lieu, résidence, sceau et le
texte lu) :

```json
{"id": 0, "nom": "TESTAOUI (Ahmed ben Mohamed)", "anneeNaissance": 1885, "groupe": "an-images",
 "ocr": false, "role": "principal", "decret": "FRAN_IR_000001/D1", "image": "LOT_000101_L.jpg", "vue": 1,
 "lecteur": "manuel", "confiance": "transcription manuelle — à vérifier sur l'image",
 "dossier": "20001 X 31", "dossier_lu": "20001 X 3I", "drapeaux": ["numero-de-dossier-corrige"]}
```

Un essai (`tests/an_images/test_lire.py`) donne ces lignes au vrai moteur (`site/js/recherche/`) et
vérifie qu'il les trouve.

**Rien n'est jeté.** Trois cas produisent des lignes de rôle `bloc` — un morceau de texte de 200 mots au
plus, cherchable, marqué `texte-non-decoupe` : des lignes de la liste rattachées à personne ; un décret
où **aucune** personne n'a été reconnue (mise en page inconnue : chaque page lue est alors donnée
entière) ; un paragraphe anormalement long. Un nom écrit dans une disposition que personne n'a encore vue
reste ainsi trouvable.

Signalements (`drapeaux`) portés par les lignes :

| Drapeau | Sens |
|---|---|
| `numero-de-dossier-corrige`, `chiffres-corriges` | `I` ou `O` lus à la place de `1` ou `0` et corrigés ; le texte lu est gardé (`dossier_lu`, `naissance`) |
| `sans-numero-de-dossier` | aucun numéro en regard de la personne |
| `numero-apparie-par-rang` | les numéros de marge ont été lus à part (en colonne) et rendus aux personnes dans l'ordre : à contrôler |
| `forme-de-nom-non-reconnue` | pas de « NOM (Prénoms) » : le début du paragraphe est gardé comme nom |
| `a-cheval-sur-deux-images` | la personne commence sur une vue et finit sur la suivante |
| `debut-apres-paragraphe-inacheve` | la personne précédente n'avait pas de fin nette |
| `naissance-non-lue`, `annee-invraisemblable` | pas d'année lue ; ou année impossible (après le décret, avant 1750), alors non utilisée |
| `enfants-annonces-non-lus`, `enfants-partiellement-lus`, `enfants-sans-annonce`, `nombre-d-enfants-different-de-l-annonce` | contrôles sur la liste des enfants (« ayant six enfants mineurs » mais trois lus : la liste continue sur la vue suivante, ou des lignes manquent) |
| `lieu-repris-de-la-ligne-precedente` | « d° » remplacé par le lieu de la ligne du dessus |
| `paragraphe-anormalement-long` | bien plus de texte qu'une personne n'en prend : d'autres personnes y sont peut-être |
| `decret-lu-partiellement` | une vue au moins du décret n'a pas été lue |
| `texte-non-decoupe` | ligne de rôle `bloc` |

Le décret auquel une image appartient vient du fichier `decret.json` que la reprise écrit à côté des
images qu'elle télécharge, ou des options `--inventaire` et `--notice`.

### 4.4 `plan-collecte`

Compte, dans `site/data/an-decrets.json`, les décrets en images seules par année et par classe, et les
convertit en requêtes et en heures à une requête toutes les 10 s. Deux grandeurs **ne sont pas mesurées**
et restent des paramètres : le nombre d'images par décret (`--pages-par-decret`, 6 par défaut) et le nombre
de requêtes hors images par décret (`--requetes-fixes`, 2 par défaut). Avec ces valeurs provisoires :
12 144 requêtes, 33,7 heures, soit 5,6 jours à 6 heures par jour ; de 4 554 requêtes (1 image par décret)
à 63 756 (40 images).

**Le collecteur n'est pas écrit, et ne doit pas l'être avant la reprise.** Ses requêtes dépendent de la
structure réelle des pages (y a-t-il une page de visionneuse ? les images sont-elles sur le même hôte ?
une taille « pleine » existe-t-elle ?), que personne n'a vue. L'écrire maintenant serait deviner.

---

## 5. Marche à suivre quand le site répond

Où : `[poste]`, votre PC, dans un terminal (zsh), à la racine du dépôt `decretas`. Rien ne s'exécute sur
une autre machine ; la seule machine distante touchée est le serveur de la SLV des Archives nationales.

**Chaque étape suppose que la précédente a réussi.** Donnez-vous une étape, lisez son tableau, et ne
passez à la suivante qu'avec le résultat attendu. **L'étape la plus susceptible d'échouer est la 3** : le
site peut retomber en panne en cours de route (c'est prévu : arrêt, puis reprise où l'on s'est arrêté), ou
les pages peuvent ne livrer aucune adresse d'image aux stratégies génériques (c'est prévu aussi : étape 4).
Consignez chaque bloc exécuté dans `day-action.md`, à la racine de l'espace de travail (règle de
l'espace).

De préférence un jour ouvré, en journée.

### Étape 0 — vérifier que l'outil est intact (aucun réseau)

```bash
python3 -m unittest discover -s tests/an_images -t .
```

`-m unittest` lance le module d'essais de Python ; `discover` lui fait chercher les essais ; `-s
tests/an_images` : dossier où chercher ; `-t .` : racine du projet (le point = le dossier courant).

| Résultat | Sens | Suite |
|---|---|---|
| `OK` en dernière ligne | les essais passent | étape 1 |
| `FAILED (failures=…)` ou `errors=…` | l'outil a été modifié et ne fait plus ce qu'il annonce | ne rien lancer vers le site ; corriger d'abord |
| `ModuleNotFoundError: No module named 'tests'` ou `'decretas'` | vous n'êtes pas à la racine du dépôt | s'y placer, recommencer |
| `command not found: python3` | Python absent du poste | l'installer ; rien d'autre n'est requis |

### Étape 1 — le site répond-il ? (une requête)

```bash
python3 -m decretas.an_images disponibilite
```

Sans option. Options existantes : `--simulation` dit ce qui serait envoyé sans rien envoyer ;
`--max-par-jour N` plafond de vérifications par jour (6 par défaut) ; `--delai-reponse S` secondes
d'attente d'une réponse (60 par défaut) ; `--racine DOSSIER` dossier du journal ; `--base ADRESSE` autre
site (pour un essai sur un serveur local seulement).

| Affichage | Code | Sens | Suite |
|---|---:|---|---|
| `HTTP 302 → … : le site RÉPOND` (ou `HTTP 200`) | 0 | le site est revenu | étape 2 |
| `HTTP 503 : le site est toujours en panne` (ou `502`) | 3 | panne | attendre 30 minutes au moins ; refaire l'étape 1 |
| `aucune réponse (…)` | 3 | site injoignable ou très lent (délai dépassé, réseau, DNS) | vérifier votre connexion ; sinon attendre 30 minutes |
| `REFUS : …` | 5 | `403`, `429` ou page anti-robot : le site refuse ce programme | **ne rien relancer** ; lire le corps gardé sous `data/raw/an-images/disponibilite/` ; écrire aux AN (§ 3.4) |
| `HTTP 404` ou autre : `réponse inattendue` | 1 | l'adresse connue a changé | lire le corps gardé ; ne pas lancer la reprise à l'aveugle |
| `Déjà N vérification(s) aujourd'hui` | 2 | plafond du jour atteint, rien n'a été envoyé | demain |

### Étape 2 — relire le plan sans rien envoyer

```bash
python3 -m decretas.an_images reprise --simulation --palier 1
```

`--simulation` : afficher le plan et l'état, ne rien envoyer, ne rien écrire. `--palier 1` : l'essentiel
seulement (13 adresses de départ).

| Affichage | Sens | Suite |
|---|---|---|
| les étapes L1 à L4 en tête, puis P1, P2, P3, S1, B1, B2, E1, C1, F1 ; `État actuel : aucune pause ni arrêt en cours.` | le plan est complet | étape 3 |
| une ligne `NON PLANIFIÉ : Cas « personne avec images »…` | `site/data/` est absent ou incomplet : les deux personnes exemplaires ne peuvent pas être choisies | lancer `python3 -m decretas.an construire` (reconstruit `site/data/` à partir des exports ; aucun réseau), puis refaire l'étape 2 |
| `État actuel : Pause en cours…` | un échec récent impose encore d'attendre | attendre l'heure indiquée |
| `État actuel : Arrêt pour la journée…` | trois échecs aujourd'hui | demain |
| `État actuel : Arrêt maintenu : le site a refusé…` | un refus est enregistré | ne pas relancer ; décision humaine (option `--lever-blocage`, à n'employer qu'après une réponse des AN ou la certitude que le refus ne visait pas le programme) |

### Étape 3 — le palier 1 (36 requêtes si chaque lien redirige une fois ; 4 à 15 minutes)

```bash
python3 -m decretas.an_images reprise --palier 1
```

`--palier 1` : l'essentiel. Valeurs par défaut, déjà au plus prudent permis : `--delai 6` (secondes entre
deux requêtes ; minimum 6), `--plafond 40` (requêtes pour ce passage ; maximum 40), `--plafond-jour 80`
(maximum 80), `--delai-reponse 90` (secondes d'attente d'une réponse). Autres options : `--cas a,b` ne
traiter que ces cas ; `--suivre CAS=ADRESSE` ajouter une adresse lue à la main (étape 4) ; `--racine
DOSSIER` et `--rapport FICHIER` autres emplacements ; `--donnees DOSSIER` autre dossier de données du
site ; `--rapport-seul` réécrire le rapport sans rien envoyer ; `--lever-blocage` voir l'étape 2 ; `--base
ADRESSE` autre site (pour un essai sur un serveur local seulement).

Si les pages obligent à suivre une visionneuse, le compte monte jusqu'à 58 : le passage s'arrête alors à 40
(deuxième ligne du tableau) et la même commande, relancée, finit le travail.

Pendant le passage, une ligne par étape : son identifiant, son état, le nombre de requêtes envoyées et
d'images reçues.

| Dernière ligne avant « Rapport écrit » | Code | Sens | Suite |
|---|---:|---|---|
| `Plan parcouru : N requête(s) envoyée(s)` | 0 | toutes les étapes ont reçu une réponse (un `404` est une réponse) | étape 4 |
| `Plafond de 40 requêtes atteint pour ce passage : plan inachevé` | 2 | le site redirige plus que prévu, ou des pages de visionneuse ont été suivies | relancer **la même commande** : seul ce qui manque est demandé (plafond du jour : 80 requêtes) |
| `Étape X : HTTP 503. Échec n° 1 du jour : arrêt de 30 minutes` (ou `502`, ou `aucune réponse`) | 3 | le site a flanché | relancer la même commande après l'heure indiquée ; l'acquis est gardé |
| `… C'est le 3ᵉ échec du jour : arrêt jusqu'à demain` | 4 | trois échecs | demain, même commande |
| `REFUS du site : …` | 5 | `403`, `429` ou page anti-robot | **tout arrêter** ; lire le corps `.refus` sous `data/raw/an-images/reprise/pages/` ; écrire aux AN |
| `Délai refusé : … Le minimum sur cet hôte est 6 s` | 2 | option `--delai` trop basse | relancer sans cette option |
| `Arrêt sur une erreur inattendue du client : …` | 1 | cas non prévu (cache abîmé, disque plein…) | lire le message ; ne pas insister |

Dans tous les cas le rapport est réécrit avec ce qui est acquis.

### Étape 4 — lire le rapport

Fichier : `data/build/an-images/reprise-rapport.md`. Lire dans l'ordre les § 4, 3, 5, 6.

| Ce que dit le rapport | Sens | Suite |
|---|---|---|
| § 5 : un tableau d'images téléchargées pour B2, E1, C1, F1 | les exemplaires sont là | étape 5 |
| § 2, note « aucune adresse d'image trouvée par les stratégies génériques » | la page construit ses adresses autrement (JavaScript, formulaire) | ouvrir le corps indiqué (`data/raw/an-images/reprise/pages/<étape>.corps`), y chercher l'adresse de la visionneuse ou d'une image, puis `python3 -m decretas.an_images reprise --palier 1 --suivre image-1899-1912=/siv/…` (`--suivre` : le cas, le signe égal, l'adresse relevée ; répétable) |
| § 2 : « Images ou descriptions sur un AUTRE hôte (non demandées) » | les images sont servies par une autre machine que la SLV | **s'arrêter** : interroger un nouvel hôte est une décision à part (son `robots.txt`, ses conditions) ; le noter et décider |
| § 2 : « page d'erreur du site » ou « formulaire de connexion présent » | la page reçue n'est pas la notice | relire le corps ; si un compte est exigé pour voir les images, le dire dans le guidage du site |
| § 4 : **« Tout le décret. »** | le lien d'une personne n'isole pas sa page | le guidage du site dit « parcourez le décret » |
| § 4 : **« Page(s) précise(s). »** | le lien d'une personne ouvre sa vue | le guidage peut dire « vue n° … » ; et, pour les années saisies, chaque personne donne le numéro de vue de sa page : un jeu d'apprentissage gratuit pour la lecture par machine |
| § 4 : « Indéterminé » ou « Indécidable sur cet exemplaire » | une des deux pages n'a pas livré ses vues, ou le décret n'a qu'une vue | étape 4, deuxième ligne ; ou refaire P2 et P3 sur un autre décret |
| § 3 : « Que désigne l'identifiant… » : quatre verdicts concordants | l'hypothèse du § 2.2 est confirmée ou écartée | mettre à jour le § 2.2 de ce document |

### Étape 5 — les métadonnées des images reçues (aucun réseau)

```bash
python3 -m decretas.an_images metadonnees data/raw/an-images/reprise/images --json data/build/an-images/metadonnees-reprise.json
```

Le dossier est parcouru en entier. `--json FICHIER` : écrire aussi le résultat complet en JSON. Autres
options : `--format json` affiche le JSON au lieu du tableau ; `--url ADRESSE` décode aussi l'adresse d'où
vient un fichier (un seul fichier) ; `--sans-pil` n'emploie pas Pillow pour recouper les dimensions.

| Affichage | Sens | Suite |
|---|---|---|
| `TEXTE LIBRE  aucun champ descriptif` pour chaque fichier, et le bilan « Aucune métadonnée descriptive » | l'attente du § 2.3 est confirmée : rien de nominatif | étape 6 ; l'écrire au § 2.3 |
| `TEXTE LIBRE  N champ(s) descriptif(s)` | un champ porte du texte | **le lire** : cote, légende, numéro de lot ? Si c'est une cote ou un rang de vue, l'exploiter ; si c'est un nom, revoir toute la stratégie |
| `Anomalie  ce fichier est une page HTML ou XML, pas une image` | le serveur a répondu autre chose qu'une image | retour à l'étape 4 |
| `Anomalie  structure … endommagée` | le fichier reçu est abîmé (rare : un téléchargement coupé est normalement compté comme un échec, pas comme une réponse) | garder le fichier tel quel, c'est une observation ; ne pas toucher à `manifest.jsonl`. L'outil ne redemande pas une adresse déjà obtenue : le noter pour le collecteur, qui devra prévoir ce cas |
| `Aucun fichier d'image à inspecter.` (code 2) | aucune image n'a été téléchargée | retour à l'étape 4 |

Relever aussi : dimensions et densité (lisible par une machine ? il faut à peu près 20 pixels de haut par
lettre), et « Suite des noms de fichiers » (le nom donne-t-il l'ordre des vues ?).

### Étape 6 — regarder les images, puis essayer la lecture

Ouvrir à l'œil les deux images de chaque cas, sous `data/raw/an-images/reprise/images/<cas>/`, et noter
pour chacun : **manuscrit ou dactylographié** ; où est le numéro de dossier ; comment un nom est écrit.
Aucun programme ne remplace ce regard.

```bash
python3 -m decretas.an_images lire data/raw/an-images/reprise/images/image-1933-1948 --date 1935-01-02
```

Le dossier est celui d'un cas. `--date AAAA-MM-JJ` : date du décret, pour signaler une année de naissance
impossible. Autres options : `--lecteur auto|manuel|tesseract|commande` (auto par défaut) ; `--config
FICHIER` configuration du lecteur `commande` (§ 4.3) ; `--inventaire` et `--notice` identifient le décret
quand le dossier n'a pas de `decret.json` ; `--psm N` mode de découpage de page de Tesseract (4 par
défaut : une colonne) ; `--langue` modèle de langue de Tesseract (`fra`) ; `--sortie FICHIER` (par défaut
`data/build/an-images/lectures.json`).

| Affichage | Code | Sens | Suite |
|---|---:|---|---|
| `NON LUE : … pas de transcription … ` et `Tesseract n'est pas installé` | 3 | aucun lecteur n'a pu lire | installer Tesseract (§ 4.3), ou écrire la transcription d'une page dans un `.txt` voisin, ou brancher un lecteur `commande` ; relancer |
| `… lecture complète ; N personne(s) …` avec N > 0 | 0 | la disposition de 1932 est reconnue | **comparer chaque ligne à l'image** ; compter les erreurs : c'est la mesure qui décidera d'une publication |
| `AUCUNE personne reconnue : mise en page inconnue de l'analyseur` | 0 | le texte est lu mais sa forme n'est pas celle de 1932 | le texte reste cherchable (blocs) ; adapter `decretas/an_images/transcription.py` à la forme observée, avec un essai |
| beaucoup de `forme-de-nom-non-reconnue` ou `paragraphe-anormalement-long` dans « Signalements » | 0 | lecture trop bruitée, ou forme des noms différente (décret d'admission) | regarder l'image ; même suite que la ligne précédente |
| `Tesseract est présent … mais son modèle « fra » manque` | 1 avec `--lecteur tesseract`, 3 en mode `auto` | modèle de langue absent | `sudo apt install tesseract-ocr-fra` (`sudo` : droits d'administration ; `apt install` : installer un paquet) |
| `Le lecteur « commande » demande un fichier de configuration` ou `… introuvable` | 1 | configuration absente ou fausse | corriger le fichier (§ 4.3) |
| `Dossier introuvable` ou `Aucune image dans ce dossier` | 2 | mauvais chemin, ou cas sans image | vérifier le chemin ; retour à l'étape 4 |

Pour une page manuscrite (si 1899-1912 l'est), Tesseract ne donnera rien d'utilisable : ne pas conclure
« illisible », conclure « il faut un autre lecteur » (§ 3.3).

### Étape 7 — le palier 2 (les compléments)

Par égard pour le service, une heure au moins après l'étape 3, ou le lendemain (le plafond du jour, 80
requêtes, arrête de toute façon le programme) :

```bash
python3 -m decretas.an_images reprise --palier 2
```

`--palier 2` : l'essentiel puis les compléments ; ce qui est déjà acquis n'est pas redemandé. Mêmes issues
qu'à l'étape 3. S'y ajoutent, dans le rapport (§ 7) : `HTTP 404` pour O1 (pas d'entrepôt OAI à cette
adresse : la question est close) ; « DIFFÈRE de la copie locale » pour X1 ou X2 (un export a changé depuis
le 2026-10-16 : des noms sont peut-être arrivés — relancer alors `scripts/telecharger-inventaires.sh`
puis `python3 -m decretas.an construire`).

### Étape 8 — recalculer le plan de collecte avec les mesures (aucun réseau)

```bash
python3 -m decretas.an_images plan-collecte --pages-par-decret 6 --requetes-fixes 2
```

Remplacer `6` par le nombre de vues par décret observé (§ 3 du rapport) et `2` par le nombre de requêtes
qu'il a fallu avant la première image (§ 1 du rapport). Autres options : `--annees A-B` ; `--classes
A1,A2…` ; `--ne-en ANNEE` (décrets datés de ANNEE + 21 ou après) ; `--delai S` secondes entre deux requêtes
(10 par défaut) ; `--heures-par-jour H` (6) ; `--donnees FICHIER` ; `--tous-les-decrets CSV` (liste à plat
de tous les décrets, pour l'indice du § 2.2) ; `--sortie DOSSIER`.

| Affichage | Code | Sens | Suite |
|---|---:|---|---|
| `1518 décrets en images seules (…)` puis les trois périodes | 0 | calcul fait ; fichiers `plan-collecte.md`, `.json` et `-decrets.csv` sous `data/build/an-images/` | décider (§ 6) |
| `Fichier illisible : …an-decrets.json` | 1 | `site/data/` absent | `python3 -m decretas.an construire` |
| `Classe(s) inconnue(s)` ou `Intervalle d'années incompris` | 1 | option mal écrite | corriger |
| `Indice des identifiants de média : non calculé` | 0 | `data/build/an-decrets.csv` absent | facultatif : `python3 -m decretas.an decrets --csv data/build/an-decrets.csv` (`--csv` : fichier à écrire) |

**On s'arrête là.** Le collecteur s'écrit ensuite, à partir de ce que le rapport a montré.

---

## 6. Après la reprise : ce qu'il faudra décider

| Si la reprise montre… | Alors |
|---|---|
| des pages dactylographiées nettes pour 1933-1948 | essayer l'OCR sur les exemplaires ; mesurer l'erreur ; écrire le collecteur pour cette période d'abord (674 décrets) |
| des pages manuscrites pour 1899-1912 | pas d'OCR ; lecture humaine guidée et recoupement avec le Bulletin officiel imprimé (§ 3.2) ; un lecteur d'écriture manuscrite seulement s'il est branché et mesuré |
| que le lien d'une personne ouvre sa vue exacte | chaque année saisie fournit des couples « nom saisi par les AN — image de sa page » : de quoi mesurer n'importe quel lecteur sans rien saisir |
| que les images demandent un compte, ou sont sur un autre hôte | ne rien collecter avant d'avoir lu les conditions de cet accès et, au besoin, écrit aux AN |
| un refus (`403`, `429`, anti-robot) | arrêt ; la voie est la lettre du § 3.4 |
| un nom de fichier qui donne l'ordre des vues | le collecteur peut vérifier qu'aucune vue ne manque, et le site citer « vue n sur N » |

Une collecte entière représente de l'ordre de 12 000 requêtes vers un service public fragile. Elle ne se
lance qu'après la lettre du § 3.4 : si les AN versent bientôt les noms de 1933-1948, la moitié du travail
disparaît.

---

## 7. Ce qui a été exécuté pour de bon, et ce qui ne l'a été que sur des maquettes

**Exécuté pour de bon le 2026-11-11 :**

- `disponibilite` : trois requêtes à la SLV (18 h 05, 19 h 16, 23 h 42), trois `503`. Journal :
  `data/raw/an-images/disponibilite/manifest.jsonl`. **Aucune autre requête n'a été envoyée à la SLV, ni
  à aucun autre hôte.**
- `reprise --simulation` : le plan s'affiche, les deux personnes exemplaires sont trouvées dans
  `site/data/`. `reprise --rapport-seul` : le rapport `data/build/an-images/reprise-rapport.md` existe et
  dit, pour chaque point, « Non observé ».
- `metadonnees` sur 58 fichiers réels du dépôt (§ 2.3).
- `plan-collecte` sur les vraies données (`site/data/an-decrets.json`, `data/build/an-decrets.csv`).
- `lire` sur une capture réelle du tutoriel officiel (une page d'un décret du 2 février 1932, 451 × 693
  pixels), avec une transcription manuelle faite à l'œil sur cette capture : 2 personnes et 7 enfants
  reconnus, tampon et numéros de dossier lus, et un signalement juste (six enfants annoncés, trois lus : la
  page s'arrête là). Fichiers sous `data/build/an-images/demonstration/` (ignoré par git : la page nomme
  des personnes réelles).

**Essayé seulement sur des maquettes** (`tests/an_images/`, 147 essais, serveur local `http.server`, images
et transcriptions fabriquées) :

- tout le déroulement de la reprise : redirections, témoin de session, pages suivies, choix de la plus
  grande image, plafonds, pause de 30 minutes, arrêt du jour, refus, reprise après arrêt, rapport ;
- les stratégies d'extraction, sur du HTML **inventé** : elles sont génériques à dessein, mais rien ne
  garantit qu'elles trouvent les images dans les vraies pages ;
- les lecteurs `tesseract` (un faux programme joue son rôle) et `commande` ;
- l'analyseur de pages, sur des transcriptions inventées qui reproduisent ce que montrent les captures
  de 1932.

**Jamais exécuté** : la reprise contre la SLV ; un OCR réel ; quoi que ce soit sur une image de décret en
pleine définition.

---

## 8. Limites connues

- L'analyseur ne connaît que la disposition de 1932. Pour toute autre, il garde le texte en blocs ; il ne
  devine pas.
- L'ordre des vues est celui où la page les cite. S'il n'est pas l'ordre des pages du décret, une personne
  « à cheval sur deux images » sera mal recollée : le rapport demande de le vérifier à l'œil.
- Le rang de taille d'une image est une heuristique sur son nom (`-min`, `-medium`, sans suffixe, IIIF
  `full`). Si une taille supérieure existe sous une adresse que la page ne cite pas, l'outil ne la trouve
  pas.
- Aucune requête `POST` n'est faite : si la visionneuse n'est atteinte que par un formulaire, la reprise
  le constatera sans le franchir.
- Les nombres du § 3.1 comptent des décrets, pas des pages : le nombre de pages par décret reste inconnu.
- La question de droit du § 3.4 (publier un index lu sur les images) n'a pas de réponse dans ce dépôt.
