# Le moteur de recherche de noms

Ce document décrit, en langage courant puis pour les développeurs, comment le site retrouve un nom
écrit par un commis français entre 1865 et 1962 à partir du nom tel qu'une famille l'écrit
aujourd'hui. Il sert aussi de matière à la page « Comment marche la recherche ».

Le vocabulaire est celui de [CONTEXT.md](../CONTEXT.md) : *terme*, *variante*, *correspondance*,
*correspondance partielle*, *particule*, *bilan de recherche*.

Tous les noms cités en exemple sont des prénoms très courants ou des noms de famille inventés
(« Testaoui », « Exemplaoui ») ; aucun ne désigne une personne des archives.

## 1. L'essentiel

- La recherche se fait **dans votre navigateur**. Le nom que vous tapez n'est envoyé nulle part.
- Vous écrivez le nom comme vous le connaissez ; le moteur le rapproche des graphies des sources
  par des **règles écrites**, que vous pouvez lire ci-dessous. Il n'y a **aucun score de
  ressemblance** : chaque correspondance dit quel terme a été reconnu dans quel mot, et pourquoi.
- Trois classes de correspondances, jamais rien de plus lâche :
  1. **correspondance** — tous les termes sont là, à l'orthographe près ;
  2. **correspondance à graphie approchante** — tous les termes sont là, mais l'un au moins n'est
     reconnu qu'approximativement ; les deux graphies sont montrées ;
  3. **correspondance partielle** — il manque exactement un terme, et il est nommé.
- Une correspondance n'est **pas une preuve** : elle désigne une notice à aller lire dans la
  source. Deux personnes différentes peuvent porter le même nom.

## 2. Ce que vous saisissez

| Vous tapez | Le moteur comprend |
|---|---|
| `Belkacem ben Chabane Testaoui` | trois **termes** : Belkacem, Chabane, Testaoui. « ben » est une particule : elle n'est jamais exigée. L'ordre ne compte pas. |
| `Belkacem\|Belgacem Chabane` | le premier terme a deux **variantes** : l'une ou l'autre suffit. |
| `Belkacem\|-Belkassem` | le signe `-` **écarte** une graphie que le moteur aurait acceptée. |
| `"Hadj" Ali` | les guillemets **exigent** un mot tel quel, même une particule. |
| `Bel Hadi` ou `Belhadi` | la même chose : collé ou en deux mots. |
| `El Arbi` ou `Larbi` | la même chose : l'article « el » s'écrit aussi fondu dans le nom (§ 4). |
| `بلقاسم بن شعبان` | saisie en arabe : voir § 6. Toujours approchante. |
| une année de naissance, à part | filtre « né vers » : ± 5 ans par défaut, réglable (§ 8). |

Chaque terme doit être retrouvé dans **un mot différent** de la notice : pour « Mohamed ben
Mohamed », il faut deux « Mohamed » écrits.

Ce qui n'est pas pris en compte est dit dans le bilan : les particules laissées de côté, une
initiale seule (« B. »), un nombre tapé dans la case du nom.

## 3. Comment deux graphies sont comparées : trois niveaux

Chaque mot est comparé à trois niveaux, du plus strict au plus large.

### Niveau k0 — la même graphie

Majuscules, accents et apostrophes intérieures ne comptent pas.

| Écrit | Lu |
|---|---|
| `Châbane`, `CHABANE` | chabane |
| `M'Hamed`, `M’hamed` | mhamed |
| `Naït` | nait |
| `Kaçem` | kacem |

Espaces, virgules, tirets, parenthèses, crochets, chiffres et points séparent les mots :
`Abd-el-Kader` se lit `abd`, `el`, `kader`.

### Niveau k1 — les équivalences d'écriture

Des habitudes de transcription qui ne changent pas le nom. Une correspondance au niveau k1 est une
correspondance pleine.

| Règle | Exemples rapprochés |
|---|---|
| lettre doublée = lettre simple | Mohammed = Mohamed ; Chaabane = Chabane ; Kaddour = Kadour |
| `c` devant e, i = `s` = `ss` = `ç` | Kacem = Kassem = Kaçem ; Hocine = Hossine ; Youcef = Youssef |
| `c` dur, `ck`, `q`, `qu` = `k` | Cadi = Kadi ; Qasim = Kasim |
| `ou`, `oo`, `w` = `u` | Ouahab = Wahab |
| `y` = `i` | Yahya = Yahia ; Tayeb = Taïeb |
| `ph` = `f` | Mustapha = Mustafa |
| `sch`, `tch`, `sh` = `ch` | Schérif = Chérif |
| `e` muet final après `n` | Chabane = Chaban ; Slimane = Sliman ; Eddine = Eddin |
| `h` final après une voyelle | Fatmah = Fatma ; Abdallah = Abdalla |

Restent **distincts** à ce niveau, exprès : Belhadi et Belhadj ; Mohamed, Mahmoud, Mohand et
M'hamed ; Amar et Omar ; Saïd et Saad ; Slimane et Salomon ; Hocine et Hassen ; Kacem et Kaci ;
Belkacem et Belgacem ; Brahim et Ibrahim ; Fatma et Fatima ; Louis et Louise.

Confusions connues et acceptées au niveau k1 : les prénoms français en `-ne` (Jean = Jeanne,
Simon = Simone).

### Niveau k2 — le squelette de consonnes (approchant)

On ne garde que la charpente du mot. Ce niveau rapproche beaucoup, donc il est **toujours
présenté à part**, comme « graphie approchante », avec les deux graphies côte à côte.

| Règle | Exemples rapprochés |
|---|---|
| les voyelles intérieures tombent | Mustapha = Mostefa (`mstfa`) ; Mohamed = M'hamed = Mehamed (`mhmd`) ; Hocine = Hussein (`hsn`) |
| `k`, `q`, `kh`, `g` dur, `gu` = `k` | Belkacem = Belgacem = Belkassem (`blksm`) ; Guesmi = Kesmi ; Lakhdar = Lakdar |
| `gh` reste à part (noté `g`) | Seghir = Sghir, mais Ghali ≠ Kali |
| `dj` = `j` = `g` doux | Hadj = Haj ; Djilali = Jilali |
| `th` = `t` ; `dh` = `d` ; `z` = `s` | Fathma = Fatma ; Arezki = Areski |
| la première voyelle, quelle qu'elle soit | Omar = Aomar = Amor ; Othmane = Athmane ; Aïssa = Issa |
| `y`, `ou`/`w` devant voyelle en tête = consonne | Youcef (`ysf`) ; Ouali = Wali (`wli`) |
| la voyelle finale compte (a, i, ou) | Mahmoud ≠ Mahmoudi ; Fatma ≠ Fatmi ; Belhadi ≠ Belhadj |
| `-ah` = `-eh` = `-a` | Salah = Saleh |
| finale `-aoui`, `-oui` gardée | Mostefaoui (`mstfwi`) ≠ Mostefa (`mstfa`) |

**Garde-fous du niveau approchant** :

1. il ne s'applique qu'aux mots d'au moins **4 lettres** dont le squelette a au moins **3 signes** :
   Ali, Saïd, Saad, Hadj, Laïd ne sont jamais rapprochés « à peu près » ;
2. il n'est **jamais combiné** avec un préfixe détaché (§ 4) — sauf en saisie arabe, qui est
   toujours approchante (§ 6) ;
3. il n'est **jamais accepté dans une correspondance partielle** ;
4. un mot que nous avons collé (« ben Ali » → « benali ») n'y a droit que si le mot lui-même y a
   droit : « ben Ali » n'est pas un « Bonelli » approchant ;
5. chaque graphie rapprochée est listée avec son nombre de notices, et peut être **décochée**.

**Confusions connues du niveau k2** — des noms différents qui ont le même squelette. Elles
apparaissent en « graphie approchante » et c'est à vous de les écarter :

| Squelette | Noms confondus |
|---|---|
| `mhmd` | Mohamed, M'hamed **et Mahmoud** |
| `hsn` | Hocine, Hussein **et Hassan, Hassen** |
| `slmn` | Slimane **et Salomon** |
| `ksm` | Kacem **et Cosme** |
| `kdr` | Kader **et Kaddour, Kouider** |
| `amr` | Omar, Aomar, Amor **et Amar, Ameur** |
| `asa` | Aïssa, Issa **et Assia** |
| `smri` | Zemri **et Zemmouri** |
| `bnli` | Benali **et Bonelli** |

Mohand (forme kabyle de Mohamed) n'est rapproché de Mohamed à **aucun** niveau : aucune règle
d'écriture ne les relie. Il est proposé comme « nom apparenté » (§ 9), à cocher soi-même.

## 4. Particules et noms collés

Une **particule** est un mot de filiation, un article, un titre ou une mention d'état civil. Elle
n'est **jamais exigée** et ne se cherche jamais seule (sauf entre guillemets) :

- filiation : ben, bent, bint, bin, ibn, b., ould, oulad, ouled, oult, ou, aït, ath, naït, n', fils, fille ;
- articles et préfixes écrits à part : el, al, ed, es, en, er, ez, et, ech, bel, bou, abou, abd, abdel ;
- titres : si, sid, sidi, hadj, hadja, lalla, moulay ;
- état civil : dit, dite, alias, né, née, veuve, vve, femme, épouse ;
- particules européennes : de, du, des, d', di, da, del, della, van, von, le, la.

Les commis collaient ou décollaient ces mots à leur gré. Le moteur réconcilie les deux écritures,
**dans les deux sens** :

| Vous tapez | La source écrit | Classe | Explication donnée |
|---|---|---|---|
| Belkacem | Bel Kaçem | correspondance | « écrit en plusieurs mots » |
| Bel Hadi | Belhadi | correspondance | « écrit collé » |
| ben Chabane | Benchabane | correspondance | « écrit collé » |
| Abdelkader | Abd el Kader | correspondance | « écrit en plusieurs mots » |
| Sidahmed | Sid Ahmed | correspondance | « écrit en plusieurs mots » |
| Larbi | El Arbi | correspondance | article « el » fondu dans le nom |
| El Akhdar | Lakhdar | correspondance | article « el » fondu dans le nom |
| Chabane | Benchabane | graphie approchante | préfixe « ben » détaché du mot écrit |
| Benchabane | Chabane (sans « ben » devant) | graphie approchante | préfixe « ben » détaché de la saisie |
| Zemri | Ezzemri | graphie approchante | article « ez » détaché du mot écrit |
| Kader | Abdelkader | graphie approchante | préfixe « abdel » détaché du mot écrit |

Règles de détachement :

- préfixes détachables : ben, bent, bel, bou, abou, abd (+ article), ould, aït, naït, el, si, ou,
  et l'article assimilé (ez-z…, en-n…, ed-d…, er-r…, es-s…, et-t…) ;
- il doit rester **au moins 4 lettres** : Benali ne devient pas « ali », Bouzid ne devient pas « zid » ;
- le reste ne doit **jamais être une particule** : **« Belhadj » ne devient pas « hadj »**, et ne
  ramène donc pas toutes les notices « El Hadj » ;
- un seul détachement à la fois : « Benchabane » ne rejoint pas « Bouchabane » ;
- un détachement donne toujours une correspondance **à graphie approchante**, jamais pleine.

**L'article fondu.** Devant une voyelle ou un h, l'article « el » (ou « al ») s'écrit aussi fondu
dans le nom : El Arbi = Larbi, El Akhdar = Lakhdar, El Aïd = Laïd, El Amine = Lamine,
El Houcine = Lhoucine. Le moteur rapproche les deux écritures dans les deux sens ; c'est une
correspondance pleine, mais l'explication le dit (« article fondu ») et le terme n'est pas compté
parmi ceux « écrits exactement comme saisis ». Ce que cette règle ne fait pas :

- devant une autre consonne, rien : « El Kader » n'est pas « Lkader » ;
- un titre reste une particule : « El Hadj » n'est pas lu « Lhadj » ;
- un mot écrit collé dans la source n'est pas touché (« Elisabeth » ne devient pas « Lisabeth ») :
  la graphie collée « Elarbi » ne rejoint donc pas « Larbi » ;
- « Larbi » ne rejoint pas « Arbi » écrit sans article : c'est un nom apparenté (§ 9).

Mesuré le 2026-11-11 sur tous les noms à notre disposition (482 267, base de mise au point des
Archives nationales et entrées du bulletin) : la règle crée 99 formes pour 153 noms écrits ; 38
rejoignent une graphie fondue réellement présente ailleurs (El Arbi, 21 fois, rejoint les 57
« Larbi » ; El Aïd, El Ayachi, El Aroussi, El Amouri, El Achemi, El Abidi, El Hassen…).

Si vous tapez « Bel Hadj » en deux mots, le moteur y voit deux particules et vous le dit ; pour
chercher le nom de famille, écrivez-le collé : « Belhadj ». Il ne l'exige pas d'office, parce que
« bel Hadj Ahmed » veut aussi dire « fils d'El Hadj Ahmed », où « Hadj » est un titre.

## 5. Les sources imprimées (texte lu par reconnaissance optique)

Le texte des bulletins imprimés vient d'une lecture automatique (OCR, reconnaissance optique de
caractères), qui abîme les mots. Pour ces sources seulement :

- « bon », « ban », « ten », « bea », « hen », « beu » (lectures observées de « ben ») et, par
  analogie seulement, « bcn », sont lus comme la particule « ben » ; « on » est lu « ou » —
  uniquement en minuscules et **entre deux mots** ; « Bon, Jean » reste un nom ;
- un signe parasite au milieu d'un mot est ignoré : « Moh:mmed » se lit « mohmmed », ce qui
  rejoint Mohamed au niveau approchant ;
- « ben » collé à la fin du mot précédent est détaché : « Aliben Fictifi » se lit aussi
  « Ali » + « ben Fictifi » (cette règle vaut pour toutes les sources).

Contrôle fait le 2026-11-11 sur les 9 616 entrées nommées du fichier
`site/data/bogga-entrees.json` de ce jour : la règle s'y applique 13 fois — 10 fois pour « ben »
(« bon » 4, « ten » 2, « bea » 2, « hen » 1, « beu » 1) et 3 fois pour « ou » (« on ») — et, à la
lecture des 13 entrées, c'est chaque fois une vraie particule abîmée. « ban » (signalé par le
rapport de recherche) et « bcn » n'y apparaissent pas. Non traités, vus une ou deux fois :
« beau » et « nou ».

Ce que le moteur **ne répare pas** : une lettre remplacée par une autre dans le nom lui-même
(« Belkasserm », « Ah » pour « Ali »). Une telle notice ne ressort au mieux qu'en correspondance
partielle, par ses autres termes. Les années lues « 4873 » pour « 1873 » sont l'affaire du
programme qui prépare les données, pas du moteur.

## 6. La saisie en arabe

On peut taper le nom en arabe : `بلقاسم بن شعبان`. Le moteur traduit chaque lettre vers le
squelette de consonnes du niveau k2, d'après la façon dont les commis la rendaient en français.

| Arabe | Signe du squelette | Arabe | Signe |
|---|---|---|---|
| ق ك خ | k (Kacem, Belgacem, Khaled) | ش | ch |
| غ | g (gh) | ج | j (dj, j) |
| ز س ص | s | ت ث ط | t |
| د ذ ض ظ | d | ح ه | h |
| ع ء au milieu | rien (Messaoud) | ا أ إ ع en tête | « a », pour toute voyelle initiale |
| و ي au milieu | rien (ce sont « ou », « i ») | و / ي en tête | w / y |
| ة ا ى à la fin | -a | ي à la fin | -i |
| ح ه à la fin | -a (Salah, Abdallah) | وي à la fin | -wi (Hamraoui) |

- Particules reconnues : بن، ابن (ben) ; بنت (bent) ; ولد (ould) ; بو، أبو (bou, abou) ; عبد (abd) ;
  ال (el) ; سي، سيدي ; الحاج ; آيت.
- L'article est essayé de plusieurs façons : détaché (الهادي → Hadi), collé (Elhadi), assimilé
  devant les lettres qui l'assimilent (الزمري → Ezzemri), et fondu **seulement devant une voyelle
  ou un h** (العربي → Larbi, الأخضر → Lakhdar, الحسين → Lhocine). Devant une autre consonne il
  n'est pas fondu : lire القادر « Lkader » ramènerait tous les Lakhdar.
- Les particules tapées sont aussi essayées collées : بن علي → Benali ; عبد القادر → Abdelkader.
- عبد suivi de l'article, tapé en un mot ou en deux, est lu des deux façons que le français
  connaît : avec le l (عبدالقادر → Abdelkader, عبدالله → Abdallah) et sans lui devant r, s, n, d, t, z…
  (عبدالرحمن → Abderrahmane, عبدالسلام → Abdesselam, عبدالنور → Abdennour).
- Les noms composés en « -eddine », tapés en un mot ou en deux, sont lus comme **un seul nom** :
  نور الدين → Noureddine, عز الدين → Azzedine, خير الدين → Kheireddine, محي الدين → Mahieddine,
  صلاح الدين → Salaheddine.

**Ce que cela peut et ne peut pas faire** :

- l'arabe n'écrit pas les voyelles brèves et le squelette ignore les autres : une saisie en arabe
  ne donne **jamais** une correspondance pleine. Elle est toujours rangée en « graphie
  approchante », avec la mention **« saisie en arabe : correspondance approchante »** ;
- un nom court donne un squelette court et ramène des noms sans rapport : سعيد (`sd`) ramène Saïd,
  mais aussi Saad. Les voyelles longues tapées (ا و ي) servent seulement à **classer** : les graphies
  qui les contiennent passent devant (محمود → Mahmoud avant Mohamed) ; rien n'est caché ;
- pas de correspondance partielle en saisie arabe (ce serait empiler deux approximations) ;
- lecture fixe des lettres ambiguës : ي en tête = « y » (يمينة est Yamina, jamais Amina) ; ي final
  = « -i », ى final = « -a ». Deux courtes listes font exception, parce que ces graphies sont
  très courantes : يحي، موسي، عيسي، مصطفي، ليلي، سلمي sont aussi lus en « -a » (Yahia, Moussa,
  Aïssa, Mustapha…), et يدير est aussi lu Idir. Tout autre nom en « -a » tapé avec ي n'est pas
  retrouvé ;
- un nom en « -eddine » que la source écrit en deux mots (« Nour Eddine ») n'est pas retrouvé par
  نور الدين ; cherchez-le alors en lettres latines, terme par terme ;
- non couverts : غ rendu « r' », ث rendu « ts », ذ et ظ rendus « z » ; les noms berbères, qui
  n'ont pas de graphie arabe stable — tapez-les en lettres latines ;
- un préfixe détaché du mot écrit est accepté en saisie arabe (حميد retrouve Abdelhamid, شعبان
  retrouve Benchabane), ce que la saisie latine ne permet jamais au niveau approchant ;
- le bon usage : taper le nom en arabe, lire la liste des graphies françaises trouvées, puis
  **relancer la recherche avec celles que vous retenez**, en lettres latines.

La table d'essai du dépôt couvre 50 graphies arabes de noms courants (prénoms et formes de noms
de famille), plus une vingtaine d'essais ajoutés à la relecture (composés de عبد tapés en un
mot, noms en « -eddine », يحي, يدير). Les deux côtés de ces tables ont été écrits par nous :
elles montrent que les règles sont cohérentes, pas qu'elles retrouvent ce que tapent de vrais
utilisateurs. Aucun arabisant ne les a relues.

## 7. Les trois classes, et l'ordre

| Classe | Condition | Ce qui est montré |
|---|---|---|
| **correspondance** | chaque terme retrouvé au niveau k0 ou k1 (collage et article fondu compris) | pour chaque terme, le mot écrit et le niveau |
| **correspondance à graphie approchante** | chaque terme retrouvé, l'un au moins par le squelette (k2), par un préfixe détaché, ou saisi en arabe | les deux graphies, la règle appliquée |
| **correspondance partielle** | il manque **exactement un** terme ; les autres sont retrouvés au niveau k0 ou k1 | le terme absent, nommé |

- Pas de correspondance partielle pour une recherche d'un seul terme.
- Deux termes absents, ou un terme absent et un terme approchant : la notice **n'est pas montrée**.
- Une notice n'apparaît que dans une classe, la meilleure.

**Ordre d'affichage**, toujours le même pour la même recherche :

1. la classe (dans l'ordre du tableau) ;
2. l'écart à l'année de naissance demandée, du plus petit au plus grand ; les notices sans année
   viennent après ;
3. le nombre de termes écrits **exactement** comme vous les avez saisis ;
4. en saisie arabe : le nombre de termes dont les voyelles longues concordent ;
5. l'ordre des sources (l'ordre des fichiers de données).

Aucun nombre n'est calculé ni affiché pour « noter » une correspondance.

## 8. L'année de naissance

- Facultative. Avec une année, on garde les notices dont l'année de naissance est à **± 5 ans**
  (valeur par défaut, affichée, modifiable de 0 à 100).
- Les notices **sans année de naissance connue sont gardées** et étiquetées comme telles : les
  bulletins de 1872-1873 ne donnent jamais l'année.
- Le bilan dit combien de correspondances de chaque classe ont été écartées par l'année.
- Beaucoup d'années sont conventionnelles (« né en 1876 » pour « présumé né vers ») : élargissez
  la tolérance avant de conclure qu'une personne est absente.

## 9. Les graphies proposées

Plutôt que de vous demander de deviner les variantes, le site montre, pour chaque terme, les
graphies **réellement présentes** dans les sources, avec leur nombre de notices :

- *même graphie* et *même écriture (k1)* — déjà prises en compte comme correspondances ;
- *squelette (k2)* — déjà prises en compte comme graphies approchantes ; **décochez** celles qui
  sont un autre nom (Mahmoud pour Mohamed) ;
- *avec ou sans préfixe* — Ezzemri pour Zemri, Chabane pour Benchabane ;
- *noms apparentés* — une courte liste écrite à la main (Mohamed / Mohand, Brahim / Ibrahim,
  Smaïl / Ismaïl, Larbi / Arbi, Embarek / M'barek, Belkacem / Aboulkacem…). Ils ne sont **jamais
  appliqués d'office** : à vous de les ajouter comme variantes.

Chaque ligne se décoche **séparément** : décocher « Kacem » (proposé « avec préfixe » pour
Belkacem) n'enlève pas les notices qui écrivent « Bel Kacem » en deux mots, et décocher
« Benchabane » n'enlève pas « Chabane ».

## 10. Le bilan de recherche

Toute recherche rend, avec ou sans correspondance, un bilan lisible par une machine :

- les termes tels qu'ils ont été compris, leurs variantes, leurs clés k0, k1, k2 (ou les
  squelettes essayés, en arabe) ;
- les particules laissées de côté, les avertissements (initiale ignorée, « Bel Hadj » en deux
  mots, variante en plusieurs mots…) ;
- l'année et la tolérance appliquées ;
- pour chaque terme, les graphies trouvées dans l'index, leur niveau, leur nombre de notices et
  ce qu'il faut exclure pour décocher la ligne ;
- le nombre de correspondances par classe, par source, celles écartées par l'année, celles
  gardées sans année ;
- la taille de l'index fouillé, par source ; les règles en vigueur (niveaux, garde-fous, ordre,
  liste des particules) ; la durée.

Ce bilan ne dit pas quelles **années** ni quels **volumes** sont couverts : cela relève des
données de chaque source, que la page de résultats doit y ajouter.

## 11. Limites connues

- Les règles sont celles de la transcription **française** des noms arabes et berbères. Elles
  rapprochent parfois des noms européens sans rapport (Benali / Bonelli, Amiel / Émile au niveau
  approchant).
- Formes non rapprochées, à saisir comme variantes : Mohand / Mohamed ; Brahim / Ibrahim ;
  Larbi / Arbi (sans article) ; Elarbi / Larbi (article collé) ; Embarek / M'barek ;
  Ahmed / Ahmet (d / t final) ; Abderrahmane / Abdelrahman (l assimilé ou non).
- Un nom court caché dans un nom collé n'est pas retrouvé : « Ali » ne ramène pas « Benali »
  (il faut 4 lettres après le préfixe). Tapez « ben Ali » ou « Benali ».
- Deux noms sans particule écrits tantôt collés, tantôt séparés ne sont pas rapprochés :
  « Nour Eddine » et « Noureddine », « Baba Ameur » et « Babaameur ». Essayez les deux.
- « Bel Hadj » tapé en deux mots n'est pas cherché (deux particules, § 4).
- Une notice qui répète le nom entre crochets (« … [autre graphie] ») contient deux fois chaque
  mot : elle peut satisfaire à tort une recherche qui demande deux fois le même prénom.
- Une faute de lecture OCR dans le nom lui-même n'est pas réparée (§ 5).
- Le niveau approchant est large sur les mots de 4 ou 5 lettres (Omar, Amar, Amor, Ameur
  ensemble). Il est borné par ses garde-fous, pas par un calcul de vraisemblance.
- Les termes doivent tous se trouver dans **une même notice** (un nom tel qu'il est écrit, avec sa
  filiation). Le père cherché dans une notice et le fils dans une autre ne sont pas réunis.
- Avec deux termes très courants, les correspondances partielles se comptent par milliers : elles
  sont dénombrées, mais seules les premières sont listées.
- Une personne peut avoir été inscrite sans nom de famille (avant l'état civil de 1882, « Belkacem
  ben Chabane » sans patronyme) : essayez aussi sans le nom de famille.

## 12. Mesures

### Calibrage sur des noms réels

Mesuré le 2026-11-11 sur la base prototype des Archives nationales (`data/samples/an-local/an.sqlite`,
lue en lecture seule ; seuls des nombres en sont tirés).

| Population | Notices | Mots (hors particules) | Graphies k0 | Clés k1 | Classes k2 |
|---|---:|---:|---:|---:|---:|
| Notices classées « musulman probable » (Algérie, Maroc, Tunisie) | 1 904 | 5 648 | 2 250 | 2 121 | 1 674 |
| Palier Algérie (décret algérien, ou né ou résidant en Algérie) | 45 199 | 125 224 | 30 097 | 28 270 | 17 768 |

Nombres recalculés à la relecture du 2026-11-11 (le premier relevé donnait 2 251 et 1 672, 30 102
et 17 762 : écarts de quelques unités, dus à la façon de compter les mots trop courts pour le
niveau k2 ; ici un tel mot compte pour une classe à lui seul).

- Niveau k1, population « musulman probable » : 111 clés réunissent plusieurs graphies
  (Mohamed / Mohammed, 387 et 271 mots ; Belkacem / Belkassem / Belcacem ; Slimane / Sliman…).
  À la relecture des 70 plus fréquentes, aucune confusion entre deux noms arabes différents n'a
  été relevée (relecture faite par nous, non contrôlée par un arabisant).
- Niveau k2 : 88,6 % des mots de cette population y ont droit (4 lettres, 3 signes ; recalculé).
  Relevé du constructeur, **non refait à la relecture** : pour un de ces mots, le niveau k2
  n'ajoute aucune notice dans 19,6 % des cas ; il ajoute en médiane 20 % de notices en plus du
  niveau k1, le double au 75e centile, sept fois plus au 90e centile ; les plus gros apports sont
  voulus (une graphie rare de Mohamed rejoint les 700 autres) ou sont des confusions avec des
  prénoms européens (Amiel / Émile).

### Contrôles sur les fichiers du site

Faits le 2026-11-11 sur `site/data/an-personnes.json` (52 367 puis 52 372 noms : personnes,
épouses, enfants) et `site/data/bogga-entrees.json` (9 616 entrées nommées). Les deux fichiers
étaient encore en cours de production et ont été régénérés pendant la relecture : chaque nombre
ci-dessous vaut pour l'état du fichier au moment de la mesure.

État actuel des fichiers (régénération du 2026-11-11 au soir, `python3 -m decretas.an construire`) :
`site/data/an-personnes.json` compte **52 427 noms** (43 315 personnes principales, 6 607 épouses,
2 505 enfants) et l'index des deux fichiers 62 123 noms (52 427 + 9 696 du bulletin). Depuis les
mesures ci-dessous, ce fichier a gagné 104 notices (celles dont seule l'épouse est née en
Algérie) et perdu 296 noms de personnes qui pourraient être encore en vie ainsi que 9 mentions
qui n'étaient pas des noms (numéro de dossier, date) : voir `docs/format-donnees-an.md` § 6 bis.
Les contrôles ci-dessous n'ont **pas** été refaits sur cet état ; seuls ont été revérifiés, par
`tools/chercher.mjs`, le chargement des deux fichiers et la taille de l'index.

- **Chaque nom se retrouve lui-même** : les 52 372 noms des Archives nationales, cherchés par
  leurs propres mots, reviennent tous en « correspondance » (0 échec ; 4 noms sans aucun mot
  cherchable, qui sont des numéros de dossier). Ces numéros de dossier ne sont plus exportés
  comme noms : dans le fichier actuel, aucun des 52 427 noms n'est dépourvu de lettre (compté
  par un script à part, pas par le moteur).
- **Chaque explication est vraie** : 3 901 recherches fabriquées à partir de noms réels déformés
  (lettre doublée, c / ss, k / g, préfixe ajouté) ont rendu 89 767 correspondances ; pour chacune,
  un programme à part (il réutilise le calcul des clés du moteur, pas son code de recherche) a
  revérifié le mot écrit à la position annoncée, le niveau annoncé, la classe, le terme absent,
  le filtre d'année et l'ordre : aucune contradiction. Ce contrôle et les deux suivants lisent
  des noms réels : ils ont été faits à la main et ne sont pas dans le dépôt.
- **Quarante-six notices tirées au sort** (34 des Archives nationales classées « musulman
  probable », 12 du bulletin marquées « indigène »), cherchées à la main sous une graphie
  d'aujourd'hui, avec leur année : 60 recherches. Avant les corrections de la relecture, la
  notice visée revenait en « correspondance » 35 fois, en « graphie approchante » 16 fois
  (au premier ou au deuxième rang), en « correspondance partielle » 7 fois, et n'était pas
  retrouvée 2 fois. Ces neuf échecs ou demi-échecs viennent de ce que le moteur refuse exprès :
  un nom de famille de quatre ou cinq lettres, trop court pour le niveau approchant (deux cas),
  deux approximations dans la même notice, un nom apparenté (Brahim / Ibrahim), un article
  fondu, une lettre abîmée par l'OCR, deux noms collés en un. La règle de l'article fondu,
  ajoutée depuis, a réparé le sien (passé en « graphie approchante »).
- **Ancêtre pilote** du projet (prénom, nom du père, nom de famille et année de naissance
  approximative ; son identité reste dans les notes de recherche locales, non versées), cherché à
  cinq ans près sur les deux fichiers : aucune correspondance, dans aucune classe. Sans le nom de
  famille : aucune correspondance ni graphie approchante, 21 correspondances partielles (12 aux
  Archives nationales, 9 au bulletin), dont aucune ne réunit le prénom et le nom du père.
- **Les dix autres noms de la feuille** : quatre reviennent en une « correspondance » chacun — les
  trois que le rapport `docs/research/sources-2026-11/an-local.md` § 6.2 dit « trouvés » et celui
  qu'il dit « probable ». Un cinquième aussi, que le rapport dit « non trouvé » : la seule notice
  qui porte ce nom de famille, née deux ans avant l'année de la feuille, porte le prénom cherché
  comme nom d'un aïeul, pas comme prénom. Les deux termes y sont, la règle est respectée, et **ce
  n'est très probablement pas la même personne**. C'est un bon exemple de ce qu'une
  correspondance n'est pas : une identification. Les cinq autres noms ne donnent aucune
  correspondance ni graphie approchante.

### Vitesse

Mesuré le 2026-11-11 sur un poste de bureau, Node 22.20 ; un téléphone sera plusieurs fois plus
lent, et aucun téléphone n'a été essayé.

| Index | Construction | Recherche habituelle (2 ou 3 termes) | Recherche la plus lourde mesurée |
|---|---:|---:|---:|
| 45 199 noms réels (palier Algérie de la base prototype) | 0,23 s | 0,04 à 0,5 ms | 2,8 ms (« Jean Marie », 5 534 correspondances) |
| 61 983 noms réels (les deux fichiers du site au moment de la mesure, par `tools/chercher.mjs` ; 62 123 aujourd'hui, vitesse non remesurée) | 0,26 à 0,33 s | 1,5 à 2,7 ms (première recherche d'un processus neuf) | 6,5 ms (un nom de famille rare et « Mohamed ») |
| 150 000 noms réels | 0,58 s | 0,07 à 0,3 ms | 15 ms (« Jean Marie », 31 195 correspondances, presque toutes partielles) |
| 371 867 noms réels (base entière) | 1,4 s | 0,04 à 0,5 ms | 43 ms (« Jean Marie », 70 966 correspondances) |
| 150 000 noms inventés (essai du dépôt) | 1,05 s à froid, 0,72 s à chaud | 0,8 à 3 ms | 15 ms (27 135 correspondances) |

Dans un vrai navigateur (essai du 2026-11-11, sans interface : Chromium 131 et Firefox 132, les
deux fichiers du site servis par la machine elle-même) : le module de recherche se charge comme
Web Worker, les deux fichiers sont lus et l'index de 61 983 noms est prêt 0,33 s (Chromium) ou
0,57 s (Firefox) après l'ouverture de la page, dont 0,21 s de construction ; une recherche y
prend 1 à 4 ms. Sur un vrai réseau, le temps de téléchargement (12,5 Mo avant compression)
s'y ajoute. Safari n'a pas été essayé.

## 13. Pour les développeurs

### Modules (`site/js/recherche/`)

Modules ES sans dépendance ni étape de construction, utilisables dans un Web Worker et dans
Node ≥ 22. Aucun accès réseau, sauf le téléchargement des fichiers de données par `session.js`.
Le fichier `site/js/recherche/package.json` (`{"type": "module"}`) dit à Node que ces fichiers
`.js` sont des modules ES ; le navigateur ne le lit pas. Sans lui, Node ne les charge que grâce à
sa détection de syntaxe, activée d'office à partir de la version 22.7 seulement (constaté en la
désactivant sur Node 22.20 : tout import échoue sans ce fichier, tout passe avec).

| Fichier | Rôle | Exports principaux |
|---|---|---|
| `normaliser.js` | découpage, clés k0 / k1 / k2, particules, formes collées et décollées | `tokenize`, `keysOf`, `keysOfWord`, `k1`, `k2`, `skeleton`, `detachedStems`, `fusedArticleForm`, `nameForms`, `isParticle` |
| `arabe.js` | saisie en arabe → squelettes candidats | `hasArabic`, `analyzeArabic`, `arabicCandidates`, `longVowelsAgree` |
| `index.js` | index en mémoire, adaptateur des fichiers en colonnes | `buildIndex`, `occurrencesFromColumns`, `indexSummary`, `DataFormatError` |
| `chercher.js` | modèle de requête, classes, ordre, bilan | `parseQuery`, `search`, `CLASSES` |
| `suggestions.js` | graphies présentes dans l'index pour un terme | `suggestVariants`, `RELATED_NAMES` |
| `session.js` | protocole de messages, sans objet global | `createSession`, `resolveUrl` |
| `worker.js` | enveloppe Web Worker de `session.js` | — |

### Entrées

Une **occurrence** est un nom écrit et sa provenance :

```js
{ id, nom, anneeNaissance /* nombre ou null */, groupe /* 'an', 'bogga'… */, ocr /* facultatif */ }
```

Les propriétés supplémentaires sont conservées et reviennent avec la correspondance
(`correspondance.occurrence`). C'est l'appelant qui décide ce qu'est une occurrence : la personne
d'une notice, son épouse, un enfant, une entrée imprimée.

Les fichiers du site ont une forme en colonnes, `{"champs": […], "lignes": [[…], …]}`, lue par
`occurrencesFromColumns(data, { groupe, champNom, champId, champAnnee, ocr })`. Sans indication,
les colonnes sont cherchées sous leurs noms usuels, dans cet ordre :

- nom : `nom`, `nom_brut`, `nomBrut`, `nom_complet`, `nomComplet`, `name`, `texte` ;
- identifiant : `id`, `identifiant`, `notice_id`, `noticeId`, `cle` ; à défaut, le numéro de ligne ;
- année de naissance : `anneeNaissance`, `annee_naissance`, `naissance_annee`, `naissanceAnnee`,
  `an_naissance`, `an`, `naissance`, `ne_en`.

Les deux fichiers du site sont donc lus sans option : `an-personnes.json` par `nom`, `id`, `an` ;
`bogga-entrees.json` par `nom`, `id`, `naissance`. La colonne `annee` seule n'est **pas** prise
pour une année de naissance (ce peut être l'année du décret). Une année est un entier de 1000 à
2100, ou un texte qui **commence** par quatre chiffres ; tout autre contenu (« 1 janvier 1882 »)
donne « année inconnue ». `champNom` accepte plusieurs colonnes (`"nom,conjoint"`) : chacune donne
une occurrence. Les autres clés du fichier (`format`, `tables`, `liens_particuliers`) sont
ignorées ; chaque occurrence garde `ligne`, le rang de sa ligne, pour que la page y relise les
autres colonnes.

Dans les deux fichiers, `id` est le **rang de la ligne** : il change d'une construction des
données à l'autre. Ne pas le garder d'une session à la suivante.

```js
import { buildIndex, occurrencesFromColumns } from './index.js';
import { search } from './chercher.js';

const { occurrences } = occurrencesFromColumns(donnees, { groupe: 'an' });
const index = buildIndex(occurrences, { groupesOcr: ['bogga'] });
const { correspondances, bilan } = search(index, { texte: 'Belkacem ben Chabane Testaoui', annee: 1876 });
```

### Requête

Texte libre, ou objet :

```js
{ texte: 'Belkacem ben Chabane',
  termes: ['Testaoui|Testaouy', { variantes: ['Bel Hadi', 'Belhadi'], exclues: ['belhadj'], exige: false }],
  annee: 1876, tolerance: 5, limite: 100 }
```

Une chaîne dans `termes` est lue comme du texte libre ; un objet est **un** terme, dont les
variantes peuvent tenir en plusieurs mots.

### Correspondance rendue

```js
{ id, nom, groupe, anneeNaissance, occurrence,
  classe: 'correspondance' | 'graphie-approchante' | 'partielle',
  termes: [
    { terme: 'Belkacem', variante: 'Belkacem', niveau: 'k2', soudure: null, prefixe: null,
      ecrit: 'Belgacem', position: 1, exact: false, arabe: false, lecture: null, voyellesLongues: null },
    { terme: 'Chabane', absent: true } ],
  termeAbsent: 'Chabane' /* ou null */, termesExacts: 1,
  annee: { ecart: 3, inconnue: false } /* null sans année demandée */ }
```

`soudure` vaut `null`, `'colle'` (différence d'espacement seulement), `'article-fondu'` (El Arbi
= Larbi, d'un côté ou de l'autre), `'prefixe-source'` (préfixe détaché du mot écrit) ou
`'prefixe-saisie'` (préfixe détaché de la saisie) ; `prefixe` nomme la particule ou le préfixe
(`'-ben'` pour un « ben » collé à la fin du mot écrit). Les deux premières valeurs et `null`
laissent la correspondance pleine ; les deux dernières la rangent en « graphie approchante ».
`ecrit` reprend les mots de la notice tels qu'ils sont écrits (plusieurs mots pour une forme
collée par nous : « Bel Kaçem ») et `position` est le rang du dernier de ces mots dans le nom.
`exact` est vrai quand le mot écrit est celui qui a été saisi, à la casse, aux accents et à
l'espacement près (niveau k0, sans préfixe détaché ni article fondu).
En saisie arabe, `arabe` est vrai, `niveau` vaut `'k2'`, `lecture` dit comment le mot a été lu
(`mot`, `article-detache`, `article-fondu`, `article-assimile`, `voyelle-initiale-omise`,
`compose-eddine`, `colle:ben`, `colle:abd+el`…) et `voyellesLongues` vaut `true`, `false` ou `null`.

`limite` borne le nombre de correspondances rendues **par classe** (100 par défaut) ; les comptes
du bilan restent complets et `bilan.tronque` signale les classes coupées.

`nom`, `ecrit`, `graphie` et `occurrence` reprennent le texte des fichiers de données tel quel :
la page doit les afficher comme du **texte** (`textContent`), jamais comme du HTML.

### Bilan rendu

`saisie`, `termes`, `particulesIgnorees`, `avertissements` (`{code, detail}` ; codes : `aucun-terme`,
`compose-de-particules`, `initiale-ignoree`, `nombre-ignore`, `trop-de-termes`,
`variante-sans-nom`, `variante-plusieurs-mots`, `annee-illisible`, `tolerance-illisible`), `annee`
(`{valeur, tolerance, de, a}`), `regles`, `graphiesTrouvees`, `comptes` (`parClasse`, `parGroupe`,
`ecarteesParAnnee`, `sansAnneeDeNaissance`, `total`), `tronque`, `limiteParClasse`, `index`,
`dureeMs`. Les libellés français de ces codes sont à écrire par la page ; `tools/chercher.mjs`
en donne une version.

`graphiesTrouvees` a une entrée par terme : `{terme, nombre, tronque, graphies}` ; chaque graphie
est `{graphie, forme, exclure, niveau, soudure, arabe, voyellesLongues, occurrences}`. Pour
**décocher** une ligne, la page relance la recherche en ajoutant le contenu de `exclure` (un
tableau) aux `exclues` du terme — pas `forme`, qui pour un préfixe détaché désigne le mot nu et
enlèverait une autre ligne. Dans `suggestVariants`, c'est `forme` qui se passe dans `exclues`.

### Protocole du Web Worker

```js
const worker = new Worker('js/recherche/worker.js', { type: 'module' });
worker.postMessage({ type: 'charger', fichiers: [
  { url: 'data/an-personnes.json', groupe: 'an' },
  { url: 'data/bogga-entrees.json', groupe: 'bogga', ocr: true } ] });
```

**Adresses des fichiers.** Dans un worker, le navigateur résout une adresse relative par rapport
au **script du worker**, pas par rapport à la page : `data/an-personnes.json` y serait demandé
sous `js/recherche/` et répondrait 404 (constaté dans Chromium et Firefox). `worker.js` résout
donc les adresses relatives par rapport à la **racine du site**, deux niveaux au-dessus de lui :
l'appel ci-dessus marche tel quel. Une page qui n'est pas à la racine, ou des données ailleurs,
donnent leur base : `{type: 'charger', base: document.baseURI, fichiers: […]}`.

| Message envoyé | Réponses |
|---|---|
| `{type: 'charger', base?, fichiers: [{url, groupe, champNom?, champId?, champAnnee?, ocr?}], groupesOcr?}` | plusieurs `{type: 'progression', fichier, numero, sur, etape, recus, total}`, puis `{type: 'pret', index, fichiers}`. `fichier` répète l'`url` reçue (`null` à l'étape `index`). `etape` : `telechargement` (`recus` et `total` en octets ; `total` vaut `null` tant qu'il est inconnu, et le reste si le serveur n'annonce pas la taille ou compresse l'envoi), `lecture` (en caractères), `index` (en noms). Un événement par bloc reçu — près de 200 pour le gros fichier dans Firefox : ne pas redessiner la page à chacun |
| `{type: 'chercher', id, requete, options?}` | `{type: 'correspondances', id, correspondances, bilan}` |
| `{type: 'suggerer', id, terme, limite?}` | `{type: 'suggestions', id, suggestions}` |
| `{type: 'etat'}` | `{type: 'etat', charge, enCours, index, fichiers}` |
| toute erreur | `{type: 'erreur', id?, code, message}` — codes `chargement`, `format`, `non-charge`, `message-inconnu`, `interne` ; `message` est une phrase française affichable, sans détail technique |

Les messages sont traités dans l'ordre d'arrivée. Un chargement raté ne laisse pas d'index à
moitié construit.

### Ligne de commande

```bash
node tools/chercher.mjs --annee 1876 --suggestions "Belkacem ben Chabane Testaoui"
```

- `--annee 1876` : année de naissance approximative ;
- `--suggestions` : ajoute, pour chaque terme, les graphies présentes dans l'index ;
- le dernier argument, entre guillemets, est le nom cherché.

Autres options : `--tolerance <n>` (écart admis, 5 par défaut) ; `--limite <n>` (lignes par classe,
20 par défaut) ; `--sans-partielles` ; `--json` (correspondances et bilan en JSON) ;
`--donnees <dossier>` (`site/data` par défaut) ; `--fichier <chemin[:groupe[:ocr]]>` (un autre
fichier, répétable) ; `--champ-nom`, `--champ-id`, `--champ-annee` (noms de colonnes, appliqués à
**tous** les fichiers chargés : à n'employer qu'avec `--fichier`) ; `--exiger-tous` (échouer si
l'un des deux fichiers habituels manque) ; `--aide`.

Codes de sortie : 0 recherche faite (même sans correspondance) ; 2 données absentes ou illisibles ;
64 ligne de commande incorrecte. Les messages vont sur la sortie d'erreur, le résultat sur la
sortie standard.

Par défaut la commande charge `site/data/an-personnes.json` (groupe `an`) et
`site/data/bogga-entrees.json` (groupe `bogga`, texte imprimé). Un fichier absent est signalé et
ignoré ; si aucun n'est là, elle s'arrête avec le code 2 et un message clair.

### Essais

```bash
node --test tests/js/
```

- `--test` : lance le lanceur d'essais intégré à Node ; avec un dossier en argument, Node 22
  exécute `tests/js/index.js`, qui charge tous les fichiers `*.test.mjs`.

Pour un compte rendu fichier par fichier : `node --test "tests/js/*.test.mjs"` (le motif entre
guillemets est développé par Node, pas par le shell).

Les essais couvrent : classes d'équivalence k1 et k2, paires qui ne doivent pas se rejoindre,
confusions k2 documentées (si l'une disparaît, ce document doit changer), particules, formes
collées et décollées, formes abîmées par l'OCR, saisie en arabe, correspondances partielles,
tolérance sur l'année, stabilité de l'ordre, protocole du worker, ligne de commande, et un budget
de vitesse sur 150 000 noms inventés. `tests/js/regressions.test.mjs` garde un essai par défaut
corrigé à la relecture du 2026-11-11.

Ce que ces essais ne font pas : ils tournent dans Node, avec des remplaçants de `self` et de
`fetch` ; l'essai dans un vrai navigateur (§ 12) a été fait à la main et n'est pas dans le dépôt.
