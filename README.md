# Decretas

Un site gratuit, indépendant et d'intérêt public : une personne tape le nom d'un ancêtre algérien,
et le site cherche, dans les sources officielles publiques, le décret par lequel cet ancêtre a été
admis à la qualité de citoyen français entre 1865 et 1962. Quand le document ne peut pas être
affiché ici, le site guide pas à pas jusqu'à lui, sans erreur et sans intermédiaire.

Le site ne délivre aucun certificat ni aucune attestation. Il n'a aucun lien avec l'administration
française ni avec l'administration algérienne, et ne doit jamais en avoir l'air. Le vocabulaire du
projet (correspondance, citation, décret d'admission, indice…) est défini dans
[CONTEXT.md](CONTEXT.md).

## Ce que contient le site

| Adresse | Page |
|---|---|
| `#/` | La recherche par nom. Elle se fait dans le navigateur : le nom tapé n'est envoyé nulle part. |
| `#/recherche?q=…&ne=…` | Les correspondances, groupées par classe, puis le **bilan de recherche** : ce qui a été fouillé, comment, ce qui ne l'a pas été et pourquoi, et que faire maintenant. |
| `#/notice/…` | Une notice entière, avec le guide jusqu'au document et le bloc « citation ». |
| `#/quel-acte` | « Quel acte chercher ? » : trois questions au plus (`site/contenu/aiguillage.json`). |
| `#/guides`, `#/guides/<id>?inventaire=…&notice=…` | Les douze guides pas à pas, remplis pour un décret précis quand on y arrive depuis une notice ou depuis la liste des décrets. |
| `#/decrets?ne=1876` | Les décrets à lire sur les images, année par année, dans l'ordre où les lire, avec une liste « décrets déjà lus » gardée sur l'appareil. `#/decrets/lus` l'imprime. |
| `#/numero` | « On m'a donné un numéro de décret » : ce qu'est une citation vérifiable, et la forme de ce que l'on vous a donné. |
| `#/actes`, `#/vocabulaire`, `#/methode`, `#/a-propos` | Les seize sortes d'actes, les mots du site, le fonctionnement de la recherche et la couverture des sources, les sources et les crédits. |

Tout ce qui suit le `#` reste dans le navigateur : une adresse de recherche peut être gardée ou
envoyée sans que l'hébergeur voie le nom cherché.

## État de la couverture

Ces chiffres ont été lus le 12 novembre 2026 dans les fichiers de données générés
(`site/data/an-meta.json`, généré le 11 novembre 2026 ; `site/data/bogga-meta.json`, généré le
11 novembre 2026). **Ils sont générés, pas écrits à la main** : ils changent à chaque reconstruction,
et le site les relit lui-même dans ces fichiers (page « Comment marche la recherche »).

- **Archives nationales, index des décrets (sous-série BB/34, 1883-1948).** 84 inventaires
  téléchargés le 16 octobre 2026 ; 21 557 décrets au total, dont 4 847 repris ici (ceux qui peuvent
  concerner l'Algérie, et ceux dont une personne reprise relève). 52 427 noms cherchables :
  43 315 personnes principales, 6 607 épouses, 2 505 enfants.
  - Cherchés par nom : 1883 à 1897, 1913 à 1927 et 1929 à 1932.
  - En images seulement, sans aucun nom saisi : 1899 à 1912, avril à décembre 1928 et 1933 à 1948,
    soit 1 518 décrets à lire un par un (la page `#/decrets` les liste).
  - Noms saisis aux Archives nationales mais non repris ici (clause Filae, voir plus bas) :
    129 décrets, surtout 1898 et le début de 1928.
  - Les personnes qui pourraient être encore en vie (moins de 100 ans l'année de génération) ne
    sont pas publiées.
- **Bulletin officiel du Gouvernement général de l'Algérie, 1861-1888**, exemplaires numérisés
  consultés sur Internet Archive et lus par une machine : 26 volumes (1862 et 1887 manquent),
  527 décrets reconnus, 9 696 entrées de personnes, et 20 pages que la machine n'a pas su découper,
  à lire à la main (elles sont listées dans le bilan et sur la page « Comment marche la recherche »).

## Construire, vérifier, servir

Toutes les commandes se lancent depuis la racine du dépôt (le dossier de ce fichier). Python 3
récent (essayé avec Python 3.12), bibliothèque standard seulement ; Node 22 pour les tests de
l'interface (essayé avec Node 22.20).

```bash
python3 -m decretas construire
```

- `python3` : l'interpréteur Python ; `-m decretas` : lance le paquet `decretas` comme un programme ;
  `construire` : la sous-commande.
- Lance dans l'ordre la construction des deux sources (`python3 -m decretas.an construire`, puis
  `python3 -m decretas.bogga construire`), puis vérifie que tous les fichiers dont les pages ont
  besoin sont présents dans `site/`. S'arrête à la première étape en échec.
- Il faut avoir téléchargé auparavant les sources brutes dans `data/raw/` (voir
  [docs/format-donnees-an.md](docs/format-donnees-an.md) et
  [docs/format-donnees-bogga.md](docs/format-donnees-bogga.md)).
- Option `--export-seul` : pour les Archives nationales, refait seulement les fichiers du site à
  partir de la base déjà construite (`data/build/an.sqlite`), sans relire les inventaires XML.

```bash
python3 -m decretas verifier
```

- `verifier` : lance les deux vérificateurs (`python3 -m decretas.an verifier` et
  `python3 -m decretas.bogga verifier`), les tests du contenu de guidage (`tests/contenu/`) et le
  contrôle des fichiers du site. Toutes les parties sont lancées même si l'une échoue ; le message
  final nomme celles qui sont en échec.

```bash
python3 -m decretas servir --port 8765
```

- `servir` : sert le dossier `site/` pour l'essayer sur cette machine ;
  `--port 8765` : le port d'écoute (8765 par défaut ; `0` choisit un port libre).
- Le serveur n'écoute que sur `127.0.0.1` : aucune autre machine ne peut s'y connecter. Il ne
  compresse pas les fichiers : il sert à essayer le site, pas à le publier. Ouvrir ensuite
  `http://127.0.0.1:8765/`. Arrêt : Ctrl+C.

Les tests :

```bash
python3 -m unittest discover -s tests -t .
node --test tests/js/
```

- `python3 -m unittest` : le lanceur de tests de Python ; `discover` : trouve les tests tout seul ;
  `-s tests` : le dossier où les chercher ; `-t .` : la racine du projet, pour que le paquet
  `decretas` puisse être importé.
- `node --test` : le lanceur de tests intégré à Node ; `tests/js/` : le dossier des tests du moteur
  de recherche et de l'interface (`ui-*.test.mjs`).

## Publier le site

Le site est **statique** : n'importe quel hébergeur de fichiers statiques convient. Il n'y a ni
serveur d'application, ni base de données, ni étape de compilation : on copie le dossier `site/`
tel quel (y compris `site/data/`, que git ignore et qu'il faut donc construire avant).

Trois exigences :

1. **Les fichiers de données doivent être servis compressés** (gzip ou brotli).
   `site/data/an-personnes.json` pèse environ 10,7 Mo brut et 2,7 Mo compressé ; l'ensemble de
   l'index environ 13 Mo brut et 3,3 Mo compressé. Beaucoup d'hébergeurs statiques compressent
   d'eux-mêmes les fichiers JSON ; sinon, configurer la compression du serveur. Pour le vérifier
   une fois le site en ligne :

   ```bash
   curl -sI -H 'Accept-Encoding: gzip, br' https://<votre-site>/data/an-personnes.json
   ```

   - `curl` : client HTTP en ligne de commande ; `-s` : sans barre de progression ;
     `-I` : ne demande que les en-têtes de la réponse ; `-H 'Accept-Encoding: gzip, br'` : annonce
     que le client accepte gzip et brotli. La réponse doit contenir `content-encoding: gzip` ou
     `content-encoding: br`.
2. **En-têtes HTTP** à régler chez l'hébergeur, parce qu'une balise `<meta>` ne peut pas les
   porter : `Content-Security-Policy: frame-ancestors 'none'` (le site ne doit pas être encadré
   par un autre), `X-Content-Type-Options: nosniff`, et les fichiers `.js` servis en
   `text/javascript`. La politique de sécurité du contenu elle-même est déjà dans
   `site/index.html`.
3. **HTTPS**, et rien d'autre à configurer : pas de cookie, pas de mesure d'audience, pas de
   compte.

## Éthique du réseau

- **Une recherche ne quitte jamais l'appareil.** Le navigateur télécharge l'index une fois, depuis
  le site lui-même, puis cherche dedans. Ni les noms tapés ni les correspondances ne sont envoyés.
- **Aucune requête vers un autre site au chargement d'une page.** Pas de police externe, pas de
  bibliothèque sur un CDN, pas de mesure d'audience. La seule ressource venue d'ailleurs est
  l'image d'une page du Bulletin officiel, demandée à archive.org **après** un clic sur
  « Afficher la page imprimée », qui dit où va la demande.
- **Une seule chose reste dans le navigateur**, et seulement si la personne coche des cases : la
  liste des « décrets déjà lus » (`localStorage`, clé `decretas.decrets-lus.v1`). Elle n'est
  envoyée nulle part, et la page l'efface d'un bouton.
- **Les liens externes viennent tous d'une seule table**, `site/contenu/liens.json`, avec leur
  statut de test ; un lien qui n'a jamais été vu fonctionner est marqué « Lien non vérifié », avec
  une phrase honnête. Aucune adresse externe n'est écrite dans le code de l'interface (un test le
  vérifie).
- **Les sites qui refusent les programmes ne sont pas contournés** : c'est la personne qui ouvre
  la page.
- **Le dépôt ne contient aucune donnée personnelle réelle** : les fichiers de données
  (`site/data/`, `data/`) sont ignorés par git ; les tests de l'interface emploient des personnes
  inventées.

## Décisions qui reviennent au responsable du site

1. **La clause Filae et la mention « usage privé ».** L'inventaire général des Archives nationales
   soumet toute publication nominative en ligne des années indexées par Filae (1898 à 1912 et 1928)
   à une autorisation préalable ; presque tous les inventaires portent une mention « usage
   privé ». Par précaution, les noms de ces années ne sont pas publiés ici. Il faut **écrire aux
   Archives nationales** pour obtenir une réponse écrite sur les conditions de réutilisation ;
   l'option `--inclure-filae` de `python3 -m decretas.an construire` (`--inclure-filae` : exporte
   aussi ces noms) ne doit servir qu'avec cette autorisation. Les textes exacts sont dans
   `site/contenu/a-propos.json`, rubrique « points ouverts ».
2. **La validation des liens non testés par un humain.** Sur les 55 liens de
   `site/contenu/liens.json`, 32 ont été vus répondre ; 12 sont proposés au public sans avoir
   jamais été vus fonctionner (la Salle de lecture virtuelle des Archives nationales était en
   panne le jour des essais), 3 sont bloqués pour les programmes mais devraient s'ouvrir dans un
   navigateur, et 8 ne sont pas montrés tant qu'un humain ne les a pas ouverts. De même, 32 des
   58 étapes des guides portent la mention « à confirmer ». La liste de ce qu'un humain doit
   ouvrir, et comment le noter, est dans [docs/contenu-sources.md](docs/contenu-sources.md),
   § 4 « À faire vérifier par un humain ».
3. **La traduction en arabe** (et, plus tard, en tamazight). Toutes les phrases de l'interface sont
   dans un seul module, `site/js/textes/fr.js` ; une traduction est une copie de ce fichier avec
   les mêmes clés, déclarée dans `site/js/textes/index.js` avec son sens d'écriture. La mise en
   page n'emploie que des propriétés logiques (début et fin de ligne plutôt que gauche et
   droite) : un sens de droite à gauche ne demande pas de seconde feuille de style. Les textes
   de `site/contenu/` sont à traduire aussi.
4. **Un moyen de signaler une erreur.** Il n'en existe pas encore, et le site le dit ; le choix du
   moyen (adresse, formulaire hébergé ailleurs…) et la façon d'y répondre restent à décider.
5. **La licence** du code et des textes du site, qui n'est pas encore choisie.

## Où lire la suite

- [site/js/README.md](site/js/README.md) : l'architecture de l'interface et les règles qu'elle suit.
- [docs/moteur-de-recherche.md](docs/moteur-de-recherche.md) : le moteur de recherche de noms.
- [docs/contenu-sources.md](docs/contenu-sources.md) : les textes de guidage, leurs sources, et ce
  qu'un humain doit encore vérifier.
- [docs/decrets-en-images.md](docs/decrets-en-images.md) : les décrets en images seules.
- [docs/format-donnees-an.md](docs/format-donnees-an.md),
  [docs/format-donnees-bogga.md](docs/format-donnees-bogga.md) : les fichiers de données.
