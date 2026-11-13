/**
 * Synthetic data for the interface tests, in the real shapes of the files of site/data/
 * (docs/format-donnees-an.md, docs/format-donnees-bogga.md). Every person, name, file number
 * and identifier below is INVENTED: no real person from the archives appears in this directory.
 */

/** A small Archives nationales export: three decrees, two households, one lone person. */
export function fichiersAn() {
  const anDecrets = {
    format: 'decretas-an-decrets/1',
    champs: ['id', 'inv', 'notice', 'date', 'drap_date', 'titre', 'famille', 'classe', 'cote', 'drap_cote', 'cote_sug', 'doc', 'etat', 'n_pers', 'n_exp', 'annee', 'trim', 'contexte'],
    tables: {
      inv: ['FRAN_IR_000001', 'FRAN_IR_000002'],
      drap_date: ['', 'conflit-titre-retenu'],
      famille: ['admission-citoyen', 'naturalisation'],
      classe: ['A1', 'A2', 'A3', 'R', '-'],
      drap_cote: ['', 'suspecte-bb11', 'absente'],
      etat: ['indexe', 'partiel', 'image', 'retenu-filae'],
    },
    liens_particuliers: { notice: {}, images: { 2: 'http://www.siv.archives-nationales.culture.gouv.fr/siv/media/FRAN_IR_000002/ZZ9/autre', 1: null } },
    lignes: [
      [0, 0, 'DEC001', '1885-03-10', 0, 'Décret de naturalisations algériennes du 10 mars 1885.', 1, 0, 'BB/34/900', 0, null, 'document 4', 0, 3, 3, 1885, null, null],
      [1, 1, 'DEC002', '1913-07-26', 1, 'Décret d\'admission aux droits de citoyen français.', 0, 0, 'BB/11/901', 1, 'BB/34/901', null, 0, 1, 1, 1913, null, null],
      [2, 1, 'DEC003', null, 0, 'Décrets de 1933', 0, 1, null, 2, null, null, 2, 0, 0, 1933, null, null],
    ],
  };
  const anPersonnes = {
    format: 'decretas-an-personnes/1',
    champs: ['id', 'role', 'princ', 'nom', 'an', 'prec', 'naiss', 'lieu', 'res', 'prof', 'dec', 'dossier', 'cote', 'notice', 'img', 'ind', 'regle', 'nea', 'rea'],
    tables: {
      role: ['principal', 'epouse', 'enfant', 'demandeur'],
      prec: ['', 'jour', 'conventionnelle', 'position'],
      ind: ['M', 'N', 'E'],
      regle: ['ne-en-algerie(explicite)+filiation', 'ne-italie'],
      nea: ['', 'explicite', 'repertoire'],
      rea: ['', 'explicite', 'repertoire'],
    },
    liens_particuliers: { notice: {}, images: {} },
    lignes: [
      [0, 0, 0, 'Testaoui, Belkacem ben Exemplane', 1850, 2, '1 janvier 1850 (Fictiville, Algérie)', 'Fictiville, Algérie', 'Fictiville', 'cultivateur', 0, '1234 X 85', 'BB/11/1234', 'PERS001', 1, 0, 0, 1, 2],
      [1, 1, 0, 'Exemplaoui, Fatma bent Ali', 1855, 1, '3 mai 1855 (Fictiville)', 'Fictiville', 'Fictiville', null, 0, null, null, null, 0, null, null, null, null],
      [2, 2, 0, 'Ahmed', 1878, 3, '12 juin 1878', null, null, null, 0, null, null, null, 0, null, null, null, null],
      [3, 2, 0, 'Zohra', 1880, 3, '2 février 1880', null, null, null, 0, null, null, null, 0, null, null, null, null],
      [4, 0, 4, 'Fictifi, Giovanni', 1860, 1, '4 avril 1860 (Naples, Italie)', 'Naples, Italie', 'Fictiville', 'maçon', 0, '99 X 85', null, 'PERS002', 0, 2, 1, 0, 2],
      [5, 0, 5, 'Testaoui, Larbi ould Rabah', 1874, 1, '9 septembre 1874 (Fictiville, Algérie)', 'Fictiville, Algérie', null, null, 1, '777 X 13', 'BB/11/777', 'PERS003', 0, 0, 0, 1, 0],
    ],
  };
  const anMeta = {
    format: 'decretas-an-meta/1',
    genere_le: '2026-11-11T00:00:00',
    source: { telecharges_du: '2026-10-16', telecharges_au: '2026-10-16' },
    comptes: { exporte: { occurrences_de_noms: 6, principaux: 3, epouses: 1, enfants: 2 } },
    vie_privee: { apparentes_retenus_par_principal: { 5: 2 } },
    noms_inexploitables: { par_principal: { 0: 1 } },
    couverture_annees: {
      champs: ['annee', 'trim', 'etat', 'decrets', 'decrets_avec_noms', 'personnes', 'filae', 'noms_exportes', 'alg_decrets', 'alg_avec_noms', 'personnes_exportees'],
      lignes: [
        [1885, null, 'indexe', 10, 10, 100, false, true, 4, 4, 30],
        [1898, null, 'indexe', 12, 12, 120, true, false, 5, 5, 0],
        [1899, null, 'image', 20, 0, 0, true, false, 6, 0, 0],
        [1900, null, 'partiel', 20, 2, 9, true, false, 7, 1, 0],
        [1913, null, 'indexe', 15, 15, 150, false, true, 8, 8, 40],
        [1928, null, 'partiel', 40, 12, 60, true, false, 9, 3, 0],
        [1933, null, 'image', 30, 0, 0, false, false, 10, 0, 0],
        [1934, null, 'image', 30, 0, 0, false, false, 11, 0, 0],
      ],
    },
    couverture_trimestres: {
      champs: ['annee', 'trim', 'etat', 'decrets', 'decrets_avec_noms', 'personnes', 'filae', 'noms_exportes', 'alg_decrets', 'alg_avec_noms', 'personnes_exportees'],
      lignes: [
        [1928, 1, 'indexe', 10, 10, 50, true, false, 3, 3, 0],
        [1928, 2, 'partiel', 10, 2, 10, true, false, 2, 0, 0],
        [1928, 3, 'image', 10, 0, 0, true, false, 2, 0, 0],
        [1928, 4, 'image', 10, 0, 0, true, false, 2, 0, 0],
      ],
    },
    inventaires: {
      champs: ['inv', 'annee', 'trim', 'titre', 'cotes', 'etat', 'decrets', 'decrets_avec_noms', 'personnes', 'filae', 'noms_exportes'],
      lignes: [
        ['FRAN_IR_000001', 1885, null, 'Décrets de 1885', 'BB/34/900', 'indexe', 10, 10, 100, false, true],
        ['FRAN_IR_000003', 1898, null, 'Décrets de 1898', 'BB/34/910', 'indexe', 12, 12, 120, true, false],
        ['FRAN_IR_000002', 1913, null, 'Décrets de 1913', 'BB/34/901', 'indexe', 15, 15, 150, false, true],
      ],
    },
    credit: { gabarit: 'Archives nationales de France ; {cote} ; {lieu} ; {date}', lieu_de_conservation: 'Pierrefitte', date_des_informations: '2026-10-16' },
    indices: { M: 'musulman algérien probable (« indigène » de l\'époque)', N: 'né en Algérie', E: 'étranger européen probable' },
    classes: { A1: 'le titre du décret nomme l\'Algérie (hors rejets)', A2: 'admission sans territoire', '-': 'autre décret' },
    avertissements: ['Les indices sont des classements heuristiques.'],
  };
  return { anDecrets, anPersonnes, anMeta };
}

/** A small Bulletin: two volumes (one item with one volume, one with several), three decrees. */
export function fichiersBogga() {
  const boggaVolumes = {
    champs: ['annee', 'item', 'doc', 'famille', 'lien_volume', 'lien_page', 'image_page', 'lien_verifie', 'bibliotheque', 'droits', 'pagination', 'livraisons', 'controle'],
    lignes: [
      [1873, 'bulletin_fictif_1873', 'bulletin_fictif_1873', 'tesseract', 'https://archive.org/details/bulletin_fictif_1873',
        'https://archive.org/details/bulletin_fictif_1873/page/n{leaf}/mode/1up',
        'https://archive.org/download/bulletin_fictif_1873/page/n{leaf}_w{largeur}.jpg', 'non vérifié', null, 'Domaine public', {}, {}, {}],
      [1885, 'depot-fictif', 'Tome 1885 A', 'tesseract', 'https://archive.org/details/depot-fictif/Tome%201885%20A',
        'https://archive.org/details/depot-fictif/Tome%201885%20A/page/n{leaf}/mode/1up',
        'https://archive.org/download/depot-fictif/Tome%201885%20A/page/n{leaf}_w{largeur}.jpg', 'oui : contrôlé', 'Bibliothèque fictive', 'Domaine public', {}, {}, {}],
    ],
  };
  const boggaDecrets = {
    champs: ['id', 'volume', 'nature', 'dates', 'date_etat', 'date_brute', 'entete', 'article', 'livraison', 'livraison_etat', 'livraison_date', 'livraison_date_etat', 'page', 'feuille', 'derniere_feuille', 'entrees', 'total_imprime', 'doublon_de', 'drapeaux'],
    lignes: [
      [0, 0, 'admission', ['1873-11-05'], 0, '5 novembre 1873', 'Par décret du 5 novembre 1873, ont été admises…', '509', 509, 0, '1873-12-06', 0, 605, 640, 641, 2, 25, null, 0],
      [1, 1, 'admission', ['1885-03-10'], 1, '40 mars 1885', 'Par décret du 10 mars 1885…', null, 901, 1, null, 2, 120, 150, 150, 1, null, null, 2],
      [2, 1, 'admission', ['1885-03-10', null], 2, '10 mars', 'Par décret du même jour…', null, 902, 0, '1885-04-20', 0, 131, 161, 161, 0, null, 1, 4],
    ],
  };
  const boggaEntrees = {
    champs: ['id', 'volume', 'decret', 'nom', 'texte', 'marqueurs', 'nationalite', 'naissance', 'residence', 'page', 'feuille', 'drapeaux'],
    lignes: [
      [0, 0, 0, 'Ali bon Slimane Exemplaoui', '1. Ali bon Slimane Exemplaoui, indigène, Fictiville.', 1, null, null, 'Fictiville', 605, 640, 0],
      [1, 0, 0, 'Fictmann (Jean)', '2. Fictmann (Jean), né en 1840, demeurant à Fictiville.', 16, 'suedois', 1840, 'Fictiville', 605, 640, 64],
      [2, 1, 1, 'Belkacem ben Exemplane', 'Belkacem ben Exemplane, cultivateur, né en 1850, demeurant à Fictiville.', 32, null, 1850, 'Fictiville', 120, 150, 0],
      // same leaf as row 0, but not contiguous in the file
      [3, 0, 0, 'Mohamed ben Fictifi', '3. Mohamed ben Fictifi, indigène.', 1, null, null, null, 605, 640, 2],
    ],
  };
  const boggaMeta = {
    version_format: 1,
    genere_le: '2026-11-11',
    credit: 'Texte et images : Internet Archive (archive.org)',
    bibliotheques: [],
    avertissements: ['Le texte vient d\'une lecture automatique.'],
    marqueurs: { 1: 'le mot « indigène » est imprimé dans l\'entrée', 16: 'un mot de nationalité est imprimé', 32: 'l\'en-tête du décret dit « les indigènes dont les noms suivent »' },
    drapeaux_entrees: { 2: 'l\'entrée court sur deux pages', 64: 'peut contenir deux personnes' },
    drapeaux_decrets: { 2: 'l\'en-tête dit « les indigènes »', 4: 'aucune entrée découpée' },
    etats_dates: { 0: 'lue', 1: 'corrigée ou déduite par le programme', 2: 'suspecte' },
    etats_numeros_livraison: { 0: 'lu', 1: 'calculé', 2: 'incertain' },
    couverture: [
      // read by machine, holds no decree (the rank of its volume does not matter here)
      { annee: 1861, etat: 'indexé', volume: 0, decrets: 0, entrees: 0, que_faire: 'Volume antérieur à 1865.' },
      { annee: 1862, etat: 'absent d\'Internet Archive', volume: null, decrets: 0, entrees: 0, que_faire: 'Chercher sur un autre site.' },
      { annee: 1873, etat: 'indexé', volume: 0, decrets: 1, entrees: 3, que_faire: '', taux_pages_table: 1, taux_listes_numerotees: 0.92 },
      { annee: 1885, etat: 'indexé', volume: 1, decrets: 2, entrees: 1, que_faire: '' },
    ],
    pages_a_lire_a_la_main: [{ volume: 0, annee: 1873, feuille: 148, page: 113, lien: 'https://archive.org/details/bulletin_fictif_1873/page/n148/mode/1up', raison: 'liste non découpée', decret: null }],
    totaux: { volumes: 2, decrets: 3, entrees: 4, pages_a_lire_a_la_main: 1 },
  };
  return { boggaVolumes, boggaDecrets, boggaEntrees, boggaMeta };
}

export function fichiers() {
  return { ...fichiersAn(), ...fichiersBogga() };
}

/** A link table in the shape of site/contenu/liens.json, with invented hosts where it matters. */
export function tableDeLiens() {
  return {
    statuts: {
      'teste-200': 'Réponse normale.',
      'non-teste': 'Personne n\'a encore vu cette adresse répondre. Voir « observation » et « origine ».',
    },
    liens: [
      { id: 'an-inventaire', libelle: 'Inventaire d\'une année', hote: 'www.siv.archives-nationales.culture.gouv.fr', gabarit: 'https://www.siv.archives-nationales.culture.gouv.fr/siv/IR/{inventaire}', variables: ['inventaire'], statut: 'teste-200', avertissement: null, repli: null, proposer: true },
      { id: 'an-notice', libelle: 'Notice', hote: 'www.siv.archives-nationales.culture.gouv.fr', gabarit: 'https://www.siv.archives-nationales.culture.gouv.fr/siv/UD/{inventaire}/{notice}', variables: ['inventaire', 'notice'], statut: 'non-teste', avertissement: 'Jamais vu fonctionner : utilisez l\'inventaire.', repli: 'an-inventaire', proposer: true },
      { id: 'ia-page', libelle: 'Une page', hote: 'archive.org', gabarit: 'https://archive.org/details/{identifiant}/page/n{feuillet}/mode/1up', variables: ['identifiant', 'feuillet'], statut: 'teste-200', avertissement: null, repli: null, proposer: true },
      { id: 'ia-page-volume', libelle: 'Une page, dépôt à plusieurs volumes', hote: 'archive.org', gabarit: 'https://archive.org/details/{identifiant}/{volume}/page/n{feuillet}/mode/1up', variables: ['identifiant', 'volume', 'feuillet'], statut: 'teste-200', avertissement: null, repli: null, proposer: true },
      { id: 'recherche-mot', libelle: 'Chercher un mot', hote: 'archive.org', gabarit: 'https://archive.org/details/{identifiant}?q={mot}', variables: ['identifiant', 'mot'], statut: 'non-teste', avertissement: null, repli: null, proposer: false },
      { id: 'fixe', libelle: 'Page fixe', hote: 'www.exemple.test', gabarit: 'https://www.exemple.test/page', variables: [], statut: 'teste-200', avertissement: null, repli: null, proposer: true },
      { id: 'piege', libelle: 'Hôte qui ne correspond pas', hote: 'www.exemple.test', gabarit: 'https://ailleurs.test/{identifiant}', variables: ['identifiant'], statut: 'teste-200', avertissement: null, repli: null, proposer: true },
    ],
  };
}
