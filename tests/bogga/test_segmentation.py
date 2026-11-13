"""Segmentation of synthetic volumes: every layout met between 1866 and 1888, and every
trap found by the verification of the prototype. All names are invented."""
from __future__ import annotations

import unittest

from decretas.bogga import dates, personnes as P, segmentation as S
from tests.bogga.fabrique import closing, make_pages, one_issue, title_page

SC = "conformément aux dispositions du sénatus-consulte du 14 juillet 1865"


def names(decree: S.Decree) -> list[str]:
    return [entry.name for entry in decree.entries]


class LayoutTestCase(unittest.TestCase):
    def test_1873_numbered_list_with_departments(self) -> None:
        body = [
            "— 494 —\nN° 349. — COMPTABILITÉ PUBLIQUE.\nARRÊTÉ DU 45 ocToBrE 1873.\nFait à Alger, le 45 octobre 1873.\n"
            "N° 350. — NATURALISATION.\n"
            "Par décret présidentiel du 8 moi 1873, contresigné par le Garde des Sceaux, Ministre de la Justice, ont été admises à jouir des droits",
            "ne Ss\n— 495 —\nde citoyen français, " + SC.replace("14", "4$") + ", les 5 personnes ci-après désignées :\nœ 2\n"
            "DÉPARTEMENT D'ALGER.\n"
            "1. Fictivo (Aldo/, badois, demeurant à Val-Fictif.\n"
            "2. Testaoui bon Exemple, indigène musulman, demeurant à\nBeni-Fictif.\n"
            "DÉPARTEMENT D ORAN.\n"
            "3. Inventaux (Rodolphe-Jean), suisse, régiment étranger. 4. El Hadj El Modèle, indigène musulman, 2 tirailleurs algé-\nriens.",
            "— 496 —\nDÉPARTEMENT DE CONSTANTINE.\n5. Essaino (Ugo), italien, demeurant à Guelma.",
        ]
        pages = one_issue(1873, body, number=502, closing_date="23 octobre1873")
        seg = S.segment_volume(pages, 1873)
        self.assertEqual(len(seg.decrees), 1)
        decree = seg.decrees[0]
        self.assertEqual(decree.dates, [("1873-05-08", dates.READ)])
        self.assertEqual(decree.article, "350")
        self.assertEqual((decree.leaf, decree.page), (1, 2))
        self.assertEqual(decree.announced, 5)
        self.assertEqual(len(decree.entries), 5)
        self.assertEqual(decree.last_number, 5)
        self.assertEqual(names(decree)[1], "Testaoui bon Exemple")
        self.assertIn("Beni-Fictif", decree.entries[1].raw)
        self.assertEqual([entry.department for entry in decree.entries], ["alger", "alger", "oran", "oran", "constantine"])
        self.assertEqual([entry.leaf for entry in decree.entries], [2, 2, 2, 2, 3])
        self.assertEqual(sum(1 for entry in decree.entries if entry.markers & P.M_INDIGENE), 2)
        self.assertEqual(decree.issue.number, 502)
        self.assertEqual(decree.issue.date.isoformat(), "1873-10-23")
        self.assertEqual(seg.unsegmented, [])

    def test_1872_surname_forename_nation_place(self) -> None:
        body = [
            "N° 65. — NATURALISATION EN ALGÉRIE.\n"
            "Par décrets présidentiels des 5 et 16 décembre 1872, contresignés par le Ministre de la Justice, les personnes ci-après "
            "désignées ont été admises à jouir des droits de citoyens français, " + SC + " :\n"
            "DÉPARTEMENT D ALGER.\n"
            "* Fictif, Paul-Aldo, suisse, demeurant à Val-Fictif. * Exemplbach, Joseph, allemand, Mustapha.\n"
            "* Amar ben Inventé, indigène, Alger.\n"
            "* Testmann, Antoine, id, id.\n* Modelard, Pierre, 1d id.",
        ]
        seg = S.segment_volume(one_issue(1873, body, closing_date="28 février 1873"), 1873)
        decree = seg.decrees[0]
        self.assertEqual(decree.dates, [("1872-12-05", dates.READ), ("1872-12-16", dates.READ)])
        self.assertEqual(decree.date_raw, "5 et 16 décembre 1872")
        self.assertEqual(names(decree), ["Fictif, Paul-Aldo", "Exemplbach, Joseph", "Amar ben Inventé",
                                         "Testmann, Antoine", "Modelard, Pierre"])

    def test_1866_sieur_list_with_the_date_at_the_end(self) -> None:
        body = [
            "N° 370. — NATURALISATION. — Exécution du Sénatus-Consulte du 14 juillet 1865. — Décret impérial (contre-signé par le "
            "Garde des Sceaux, Ministre de la Justice et des Cultes), qui ad- met à jouir des droits de citoyen français, en "
            "conformité des articles 1° ($ 3), 4 et 5 du Sénatus-Consulte du 14 juillet 1865 :\n"
            "l° Le sieur EXEMPLON (Azar), né à Oran dans le courant du mois de mars 1815, interprète militaire ;\n"
            "2 Le sieur Fictou Modeloun, dit BEN ESSAI, né à Oran le l* fé- vrier 1823, interprète militaire auxiliaire. — Paris, 11 juillet 1866.\n"
            "ERRATUM.\nUne erreur s'est glissée dans la circulaire du 14 novembre 1866.",
        ]
        seg = S.segment_volume(one_issue(1866, body, closing_date="30 novembre 1866"), 1866)
        decree = seg.decrees[0]
        self.assertEqual(decree.dates, [("1866-07-11", dates.READ)])
        self.assertEqual(names(decree), ["EXEMPLON (Azar)", "Fictou Modeloun"])
        self.assertEqual(decree.entries[0].birth_year, 1815)

    def test_1866_single_person_named_inside_the_sentence(self) -> None:
        body = [
            "N° 304. — NATURALISATION. — Par décret impérial en date du 11 août 1866, le sieur FICTAOUD EXEMPLI, négociant, demeurant à "
            "Villefictive, a été admis à jouir des droits de citoyen français, par application du "
            "Sénatus-Consulte du 14 juillet 1865.\n"
            "N° 305. — CULTES. — Par décret impérial du 5 septembre 1866, est approuvée la délibération fictive.",
        ]
        seg = S.segment_volume(one_issue(1866, body, closing_date="30 septembre 1866"), 1866)
        self.assertEqual(len(seg.decrees), 1)
        entry = seg.decrees[0].entries[0]
        self.assertEqual(entry.name, "FICTAOUD EXEMPLI")
        self.assertTrue(entry.flags & P.F_DANS_ENTETE)

    def test_1868_dated_titles_without_any_formula(self) -> None:
        body = [
            "DÉCRETS DE NATURALISATION EN ALGÉRIE.\n"
            "N°14. — Décrer pu 5 Juin 1867.\n"
            "1. Le sieur Aldo FICTO, né le 3 mars 1843 à Villefictive (Maroc), instituteur, domicilié à Oran.\n"
            "2. Le sieur EXEMPLA (Azar), israélite indigène, colporteur, né à Constantine en 1838, demeurant à Val-Fictif.\n"
            "N°15. — DÉCRET DU 22 JUIN 1867.\n"
            "1. Le sieur Testet (Azar), indigène israélite, né à Alger en 1834, demeurant à Val-Fictif.\n"
            "N° 16. — DÉCRET Du 6 Juizcert 1867.\n"
            "1: Le sieur Modora (Azar), colporteur, indigène israélite, né à Alger en 1827, demeurant à Val-Fictif.\n"
            "N° 23. — MILICES. — Nominations.",
        ]
        seg = S.segment_volume(one_issue(1868, body, closing_date="29 février 1868"), 1868)
        self.assertEqual([decree.kind for decree in seg.decrees], ["titre", "titre", "titre"])
        self.assertEqual([len(decree.entries) for decree in seg.decrees], [2, 1, 1])
        self.assertEqual(seg.decrees[0].dates[0][0], "1867-06-05")
        self.assertEqual(seg.decrees[1].article, "15")
        self.assertEqual(seg.decrees[2].dates, [])                      # unreadable month: no date invented
        self.assertEqual(seg.decrees[2].date_state, dates.SUSPECT)
        self.assertIn("Juizcert", seg.decrees[2].date_raw)

    def test_1869_one_sentence_for_many_dated_decrees(self) -> None:
        body = [
            "NATURALISATION EX ALGÉRIE. — EXÉCUTION du sénatus-consulte du 1% juillet 4865.\n"
            "Par décrets impériaux, ci-après mentionnés et contresienés par le garde des sceaux, Ministre de la justice et des "
            "cultes, ont été admis à jouir des droits de citoyen français, en conformité des articles 4°, 4 et 5 du "
            "sénatus-consulte du 14 juillet 1865, les individus ci-dessous nommés et désignés :\n"
            "N° 72. — Décret du 30 novembre 1867.\n"
            "FICTONN (Azar), étranger israélite, né en 1838, à Villefictive (Maroc),\ndemeurant à Oran.\n"
            "2. EXEMPLOZ (Azar), étranger isreélite, né à Villefictive (Maroc), en 1831, colporteur à Oran.\n"
            "No 78, — Déc@t du 15 mars 1868.\n"
            "4. TESTOIS (Aldo-Ulric), étranger européen, né à Villefictive (Suisse), le 3 mars 1834, fusilier au régiment étranger à Mascara.\n"
            "36. MODELZA (Ugo), étranger européen, né en 1843 à Villafictiva (Italie), patron de barque, domicilié à Alger, "
            "N9 89 — Décret du 26 Décembre 1867.\n"
            ". ESSAIRSO (Ugo), né à Villafictiva (Italie), le 3 mars 4815 marin à Val-Fictif (province d'Oran).\n"
            "N° 99. — PÊCHE. — Arrêté fictif.",
        ]
        seg = S.segment_volume(one_issue(1869, body, closing_date="20 juillet 1869"), 1869)
        self.assertEqual([decree.dates[0][0] for decree in seg.decrees], ["1867-11-30", "1868-03-15", "1867-12-26"])
        self.assertEqual([len(decree.entries) for decree in seg.decrees], [2, 2, 1])
        self.assertEqual([decree.article for decree in seg.decrees], ["72", "78", "78"])
        self.assertTrue(seg.decrees[0].entries[0].markers & P.M_ETRANGER)
        self.assertEqual(seg.decrees[0].entries[0].residence, "Oran")
        # the volume publishes decrees up to two years old: they are not suspect for that
        self.assertTrue(all(state != dates.SUSPECT for decree in seg.decrees for _iso, state in decree.dates))

    def test_1874_sentence_under_the_title_and_dated_sub_lists(self) -> None:
        body = [
            "N° 322. — NATURALISATION.\n"
            "Ont été admis à jouir des droits de Français, conformé- ment aux dispositions du sénatus-consulte du 44 juillet 1865 "
            "et du décret du 21 avril 4866, les étrangers et in- digènes musulmans dont les noms suivent :\n"
            "Décret du 5 mars 1874\n"
            "DÉPARTEMENT D'ALGER 4. Fictujo (Ramiro), sujet espagnol, demeurant à Alger. DÉPARTEMENT DE- CONSTANTINE\n"
            ". Exempliner (Ulric), aïlemand, demeurant à Val-Fictif.\n"
            "Décret du 96 mars 1874\n"
            "DÉPARTEMENT D'ALGER\n"
            "Testel ben Modèle, indigène musulman, demourant à Alger.\n"
            "N° 323. — Ont été admis à jouir des droits de Fran- çais, " + SC + ", les étrangers dont les noms suivent :\n"
            "Décret du 17 avril 1874\n"
            "Inventar ben Essai, indigène musulman, demeurant à Douéra.",
        ]
        seg = S.segment_volume(one_issue(1874, body, closing_date="28 août 1874"), 1874)
        self.assertEqual([len(decree.entries) for decree in seg.decrees], [2, 1, 1])
        self.assertEqual(seg.decrees[0].dates, [("1874-03-05", dates.READ)])
        self.assertEqual(seg.decrees[1].dates, [(None, dates.SUSPECT)])          # « 96 mars »: unreadable day
        self.assertEqual(seg.decrees[2].article, "323")
        self.assertEqual([entry.department for entry in seg.decrees[0].entries], ["alger", "constantine"])

    def test_1875_one_heading_two_decrees_told_apart_by_parenthesised_dates(self) -> None:
        body = [
            "N° 358. — NATURALISATION.\n"
            "Par décrets prési‘entiels, rendus en Conseil d'Etat, les\n"
            "22 juin et 6 juillet 4875, et contresignés par le Minis- tre de la Justice, sont admis à jouir des droits de citoyen "
            "français, " + SC + ", les étrangers ou indigènes dont les noms suivent :\n"
            "DÉPARTEMENT D'ALGER (Décret du 22 juin)\n"
            ". Fictus (Antoine-Paul), anglais, demeurant à Alger. . Exemplonzo (Antonio), espagnol, Alger.\n"
            "(Décret du 6 juillet)\n"
            ". Testaras (Ramiro), espagnol, demeurant à Val-Fictif.\n"
            "DÉPARTEMENT D'ORAN\n(Décret du 22 juin)\n"
            "Modelaguer (Ramiro), espagnol, demeurant à Oran.",
        ]
        seg = S.segment_volume(one_issue(1875, body, closing_date="20 juillet 1875"), 1875)
        self.assertEqual(len(seg.decrees), 2)
        self.assertEqual([decree.dates for decree in seg.decrees],
                         [[("1875-06-22", dates.REPAIRED)], [("1875-07-06", dates.REPAIRED)]])
        self.assertEqual([names(decree) for decree in seg.decrees],
                         [["Fictus (Antoine-Paul)", "Exemplonzo (Antonio)", "Modelaguer (Ramiro)"], ["Testaras (Ramiro)"]])

    def test_1877_sentence_cut_by_a_page_break_with_the_person_inside(self) -> None:
        body = [
            "— 197 —\nNATURALISATIONS\n"
            "N° 472. — Par décret présidentiel, en date du 45 no- vembre 4877, rendu en Conseil d'Etat et contresigné par le",
            "— 198 —\nMinistre de la justice, le sieur Fictetti (Ugo), commis aux écritures, né à Villafictiva (ltalie), le 3 "
            "mars 4854, demeurant à Val-Fictif (Oran), est admis à jouir des droits de citoyen français.\n"
            "CONCESSIONS AUX DÉPARTEMENTS\nN° 473. — Par Décret du Président de la République, en date du 18 octobre 1877,",
        ]
        seg = S.segment_volume(one_issue(1877, body, closing_date="5 décembre 1877"), 1877)
        self.assertEqual(len(seg.decrees), 1)
        self.assertEqual(seg.decrees[0].dates, [("1877-11-15", dates.REPAIRED)])
        self.assertEqual(names(seg.decrees[0]), ["Fictetti (Ugo)"])
        self.assertEqual(seg.decrees[0].entries[0].birth_year, 1854)

    def test_1879_appeles_a_jouir_de_la_qualite(self) -> None:
        body = [
            "N° 76. — NATURALISATIONS,\n"
            "Par décret présidentiel, en date du 24 décembre 1878, contresigné par M. le Garde des Sceaux, Ministre de la justice, "
            "a été appelé à jouir des droits de citoyen français le nommé :\n"
            "Fictirgian (Aldo-Ulric), sergent à la légion étrangère, né à Villefictive (Egypte), le 3 mars 1852.\n"
            "Par décret présidentiel, en date du 45 janvier 1879, contresigné par le Garde des Sceaux, Ministre de la justice, "
            "ont été appelés à jouir de la qualité de citoyen français les étrangers dont les noms suivent :\n"
            "DÉPARTEMENT D'ALGER\n"
            "Exemplet (Aldo-Marcel), ajusteur, né le 3 mars 1849 à Villefictive (Belgique), demeurant à Val-Fictif (Alger).\n"
            "Ali ben Testi, cultivateur, né à Talla-Fictive (Alger), le 3 mars 1852, demeurant à Val-Fictif.",
        ]
        seg = S.segment_volume(one_issue(1879, body, closing_date="15 février 1879"), 1879)
        self.assertEqual([len(decree.entries) for decree in seg.decrees], [1, 2])
        self.assertEqual(seg.decrees[1].dates, [("1879-01-15", dates.REPAIRED)])
        self.assertFalse(seg.decrees[0].entries[0].markers & P.M_ETRANGER)       # « légion étrangère »

    def test_1884_dated_title_above_an_undated_sentence(self) -> None:
        body = [
            "N° 64. — NATURALISATIONS.\nDÉCRET DU 28 NOVEMBRE 1883\n"
            "Par décret présidentiel contresignè par M. le Garde des Sceaux, Ministre de la Justice, et rendu en conformité du "
            "Sénatus-Consulte du 14 juillet 1865, ont été admis à jouir des droits de citoyen français les étrangers dont les noms suivent :\n"
            "(Légion Étrangère)\n"
            "Fictmann (Aldo-Ulric), soldat de 4° classe, né le 3 mars 1858 à Villefictive (Suisse).\n"
            "N° 82. — NATURALISATIONS.\n"
            "Par décrets présidentiels contresignés par M. le Garde des Sceaux, Ministre de la Justice, ont été admis à jouir des "
            "droits de citoyen français les étrangers dont les noms suivent :\n"
            "DÉCRET DU 5 DÉCEMBRE 1883\n"
            "Exemplo (Ugo), marin, né à Villafictiva (Italie), le 3 mars 1850, demeurant à Bône.\n"
            "DÉCRET DU 47 DÉCEMBRE 4883\n"
            "Testini (Marc), maçon, né à Gênes (Italie), le 9 mai 1851, demeurant à Alger.",
        ]
        seg = S.segment_volume(one_issue(1884, body, closing_date="10 mars 1884"), 1884)
        self.assertEqual([decree.dates[0][0] for decree in seg.decrees], ["1883-11-28", "1883-12-05", "1883-12-17"])
        self.assertEqual([len(decree.entries) for decree in seg.decrees], [1, 1, 1])
        self.assertTrue(all(decree.kind == "formule" for decree in seg.decrees))

    def test_1885_naturalisation_and_reintegration_sentences(self) -> None:
        body = [
            "N° 500. — NATURALISATION.\n"
            "Par décret présidentiel du 19 août 1885, contresigné par M. le Garde des Sceaux, Ministre de la Justice, et rendu en "
            "conformité du sénatus-consulte du 14 juillet 1865, ont été naturalisés Français, les étrangers dont les noms suivent, "
            "résidant en Algérie :\n"
            "Fictner (Laurent), soldat de 1re classe à la Légion étrangère, né le 5 décembre 1856 à Siegen (Prusse).\n"
            "Par décret Présidentiel du 24 juin 1885, contresigné par M. le Garde des Sceaux, Ministre de la Justice, ont été "
            "ré- intégrées dans la qualité de Françaises, en exécution de l'article 18 du Code civil :\n"
            "Exemplier (Marie), veuve Testo, née à Oran, le 2 mars 1840, y demeurant.",
        ]
        seg = S.segment_volume(one_issue(1885, body, closing_date="25 novembre 1885"), 1885)
        self.assertEqual([decree.nature for decree in seg.decrees], [S.NATURE_NATURALISATION, S.NATURE_REINTEGRATION])
        self.assertTrue(seg.decrees[0].entries[0].markers & P.M_NATURALISEE)
        self.assertTrue(seg.decrees[1].entries[0].markers & P.M_REINTEGREE)

    def test_1888_sub_lists_and_heading_that_names_the_indigene(self) -> None:
        body = [
            "N° 39. — NATURALISATION.\n"
            "Par décret présidentiel du 21 novembre 1887, contresigné par M. le Garde des Sceaux, Ministre de la Justice, et rendu "
            "en conformité du Sénatus-Consulte du 14 juillet 1865, ont été admis à jouir des droits de citoyen français les "
            "étrangers dont les noms suivent :\nDÉPARTEMENT D'ALGER\n"
            "Fictling (Ulric), mitron, né à Blida (Alger), le 3 mars 1861, de parents bavarois, demeurant à Alger.\n"
            "Exempliri Amar ben Fictif ben Modèle, indigène algérien, monogame, propriétaire, né à Bir Fictif, près Val-Fictif "
            "le 44 mai 4843, demeurant à Val-Fictif.\n"
            "Est naturalisée Française :\n"
            "Testban (Esther), femme Fictati, née le 21 avril 1859, à Oran, de parents israélites algériens, demeurant à Oran.\n"
            "Sont réintégrées dans la qualité de Française, par application de l'article 18 du Code civil :\n"
            "Modelène (Marie-Louise), femme Essaiké, née de parents français, le 3 mars 1863 à Val-Fictif (Constantine), y demeurant.\n"
            "Par décret présidentiel du 45 décembre 1887, contresigné par M. le Garde des Sceaux, Ministre de la Justice, a été "
            "admis à jouir des droits de citoyen français l'indigène dont le nom suit :\n"
            "Inventaoui (Bel Fictif ben Exemple), monogame, garde champêtre, né en 1838 à Aïn-Fictive (Alger), demeurant à Bourg-Essai.",
        ]
        seg = S.segment_volume(one_issue(1888, body, number=1104, closing_date="9 février 1888"), 1888)
        first, second = seg.decrees
        self.assertEqual([entry.markers & (P.M_NATURALISEE | P.M_REINTEGREE) for entry in first.entries],
                         [0, 0, P.M_NATURALISEE, P.M_REINTEGREE])
        self.assertEqual(first.entries[1].birth_year, 1843)
        self.assertEqual(first.entries[1].name, "Exempliri Amar ben Fictif ben Modèle")
        self.assertEqual(first.entries[0].nationality, "bavarois")
        self.assertEqual(second.dates, [("1887-12-15", dates.REPAIRED)])
        self.assertTrue(second.heading_indigene)
        self.assertTrue(second.entries[0].markers & P.M_INDIGENE_ENTETE)
        self.assertFalse(second.entries[0].markers & P.M_INDIGENE)       # the word is not in the entry itself
        self.assertEqual((first.issue.number, first.issue.date.isoformat()), (1104, "1888-02-09"))

    def test_harvard_ocr_with_double_spaces_and_damaged_formula(self) -> None:
        body = [
            "N*  347.  —  Naturalisation.  —  Décret  présidentiel  du  46  août 4872,  contresigné  par  le  Ministre  de  la  "
            "Justice,  qui  admet  à^ouir des  droits  de  citoyens  français^  conformément  aux  dispositionrdu SénaluS'Consulte  "
            "du  U  juillet  4865,  les  sieurs:\n"
            "1 .  Fictitz  (Aldo- Ulric),  allemand,  demeurant\n-à  Alger.\n"
            "2.  Exemplba  (Ugo),  italien,  demeurant  à\nAlger.\n"
            "33.  Testjemah  Azar.  israélite,  Val-Fictif.\n"
            "Digitized  by\nGoogle",
            "N-  348.  —  Douanes.\nPar  arrêté  du  Ministre  des  Finances,  en  date  du  1 1 octobre  1872,  M.  Fictoy  "
            "(Arnaud),  receveur principal  des  douanes  à  Bône,  a  été  appelé  à  la  recette principale  d'Alger.",
        ]
        texts = [title_page(1872, 428).replace("ANNÉE", "AMMÉK")] + body
        texts[-1] += "\nCertifié  conforme  : Alger,  le  31  octobre  1872.  * Le  Chef  de  la  section"
        seg = S.segment_volume(make_pages(texts), 1872)
        self.assertEqual(len(seg.decrees), 1)
        self.assertEqual(seg.decrees[0].dates, [("1872-08-16", dates.REPAIRED)])
        self.assertEqual(len(seg.decrees[0].entries), 3)
        self.assertEqual(seg.issues[0].date.isoformat(), "1872-10-31")


class TrapTestCase(unittest.TestCase):
    def heading(self, date: str = "8 mai 1873") -> str:
        return (f"Par décret présidentiel du {date}, contresigné par le Ministre de la Justice, ont été admises à jouir des "
                f"droits de citoyen français, {SC}, les personnes ci-après désignées :")

    def test_title_alone_is_not_a_decree(self) -> None:
        body = ["N° 12. — NATURALISATION. — Instructions.\nMonsieur le Préfet, la circulaire ci-jointe résume les règles.\n"
                "Fictan (Ulric), badois, demeurant à Alger."]
        self.assertEqual(S.segment_volume(one_issue(1873, body), 1873).decrees, [])

    def test_table_and_law_wordings_are_not_decrees(self) -> None:
        body = [
            "22 Décret qui admet divers indigènes à jouir des droits de citoyen français ......... 205 | 271 | 580\n"
            "ART. 11. — L'indigène musulman ou israélite qui veut être admis à jouir des droits de citoyen français, conformément "
            "au paragraphe 3 du décret du 21 avril 1866, doit se présenter en personne.\n"
            "Il peut, sur sa demande, être admis à jouir des droits de citoyen français ; vu le décret du 14 juillet 1865."
        ]
        self.assertEqual(S.segment_volume(one_issue(1866, body), 1866).decrees, [])

    def test_unreadable_article_number_still_closes_the_decree(self) -> None:
        body = [
            "N° 410. — " + self.heading("15 octobre 1873") + "\n"
            "1. Fictietti (Amédée), italien, demeurant à Alger. 2. Exemplino (Nicolas), italien, demeurant à Alger.\n"
            "N° $12. — NOTAIRES.\n"
            "Par décret du 3 novembre 1873, ont été nommés :\n"
            "Testerd (Aldo-Marcel), principal clerc de notaire, en remplacement de M. Modelin, démissionnaire.\n"
            "Inventard (Paul), demeurant à Blida, notaire à Médéa.",
        ]
        seg = S.segment_volume(one_issue(1873, body, closing_date="6 décembre 1873"), 1873)
        self.assertEqual(len(seg.decrees), 1)
        self.assertEqual(names(seg.decrees[0]), ["Fictietti (Amédée)", "Exemplino (Nicolas)"])

    def test_prose_after_a_list_closes_it_even_without_an_article_number(self) -> None:
        body = [
            "N° 410. — " + self.heading() + "\n1. Fictietti (Amédée), italien, demeurant à Alger.\n"
            "Par arrêté du 4 novembre 1873, M. Exemplard (Jules), demeurant à Oran, a été nommé interprète.\n"
            "Testin (Paul), né à Blida, demeurant à Médéa.",
        ]
        seg = S.segment_volume(one_issue(1873, body, closing_date="6 décembre 1873"), 1873)
        self.assertEqual(names(seg.decrees[0]), ["Fictietti (Amédée)"])

    def test_scrambled_columns_are_reported_not_dropped(self) -> None:
        scrambled = (
            "165° 166: 167: 168. 169 170 171: 172 173\n— 113 —\n"
            "Fictschel, Jarques. Exemplaim, Tilus, Testuch, Rodolphe, Modelé, Sebastien, Inventber, Joseph, Essaier Francois,\n"
            "Fictagiano, Aldo Ugo, italien, Oran.\n"
            "Fictin, Pierre, Exemplger Joseph, Modelklé Joseph, Schefict, Jacch, Yorfict, Léopold. Zuefict, Constant, frusfict, Félix,\n"
            "Amar ben Exemplacein, Schaelfict, Jean, Beckfict, Franco, Batafict, Luidut, Mevfict, Frederir, Mevfict, Jacob,\n"
            "id. id. il. il. il. id. id. id. Id. italien, * indirène, allemand, allemand, italien, allemind, allemiud."
        )
        body = ["N° 65. — " + self.heading("5 décembre 1872") + "\n* Fictif, Paul-Aldo, suisse, demeurant à Val-Fictif.", scrambled,
                "209' Exemplin, Ulric, allemand, Val-Fictif. 210° Testery, Aldo, allemand, Bourg-Essai."]
        seg = S.segment_volume(one_issue(1873, body, closing_date="28 février 1873"), 1873)
        decree = seg.decrees[0]
        self.assertEqual(len(decree.entries), 3)                      # one before, two after the scrambled page
        self.assertEqual([page.leaf for page in seg.manual_pages], [2])
        self.assertTrue(all(block.leaf == 2 for block in seg.unsegmented))
        kept = " ".join(block.text for block in seg.unsegmented)
        self.assertIn("Amar ben Exemplacein", kept)                  # still searchable as raw text
        self.assertIn("Fictagiano", kept)
        self.assertIn("indirène", kept)

    def test_republished_decree_is_marked_and_both_citations_stay(self) -> None:
        people = ("1 Amar ou Fictiman, indigène musulman, demeurant à Val-Fictif.\n2 Exemplio (Ugo), sujet italien, demeurant à Alger.\n"
                  "3 Testting (Ulric), bavarois, demeurant à Bourg-Essai.\n4 Modelmann (Aldo), badois, demeurant à Val-Modèle.")
        again = people.replace("Fictiman", "Fictirnan").replace("Testting", "Tesiting").replace("Exemplio", "Exemplto")
        body = ["N° 359. — " + self.heading("24 mai 1873") + "\n" + people + "\nN° 360. — MILICES.\nArrêté fictif.",
                "N° 411. — " + self.heading("25 mai 1873") + "\n" + again]
        seg = S.segment_volume(one_issue(1873, body, closing_date="6 décembre 1873"), 1873)
        self.assertEqual([decree.duplicate_of for decree in seg.decrees], [None, 0])
        self.assertEqual([len(decree.entries) for decree in seg.decrees], [4, 4])
        self.assertTrue(all(entry.flags & P.F_DECRET_REPUBLIE for entry in seg.decrees[1].entries))
        self.assertFalse(any(entry.flags & P.F_DECRET_REPUBLIE for entry in seg.decrees[0].entries))

    def test_sentence_cut_by_entries_read_out_of_order(self) -> None:
        body = [
            "N° 358. — " + self.heading() + "\n1. Fictizei (Aldo), anglo-maltais, demeurant à Val-Fictif.\n"
            "N° 359, — Par décret présidentiel, en date du 24 mai 1573, ntresigaé par le C:rde des Sceaux, Ministre de la Justice, ont\n"
            "Exemploux (Ugo), italien, à Val-Fictif.",
            "été admises à jouir des droite de citoyen français, couformément aux dispositions du sénatus-consulte du 14 juillet 4865, "
            "les per- sonnes ci-après désignées :\nDÉPARTEMENT D'ALGER.\n4 Amar ou Testiman, indigène musulman, demeurant à Val-Fictif.",
        ]
        seg = S.segment_volume(one_issue(1873, body, closing_date="31 octobre 1873"), 1873)
        self.assertEqual(len(seg.decrees), 2)
        self.assertEqual(names(seg.decrees[0]), ["Fictizei (Aldo)", "Exemploux (Ugo)"])
        self.assertEqual(seg.decrees[1].dates, [("1873-05-24", dates.REPAIRED)])
        self.assertEqual(names(seg.decrees[1]), ["Amar ou Testiman"])

    def test_decree_date_after_its_issue_is_never_exported_as_read(self) -> None:
        body = ["N° 410. — " + self.heading("15 octobre 1874") + "\n1. Fictietti (Amédée), italien, demeurant à Alger."]
        seg = S.segment_volume(one_issue(1873, body, closing_date="6 décembre 1873"), 1873)
        self.assertEqual(seg.decrees[0].dates, [("1873-10-15", dates.REPAIRED)])
        self.assertEqual(seg.decrees[0].date_raw, "15 octobre 1874")

    def test_issue_dates_are_validated_before_use(self) -> None:
        def issue(number: int, date: str, extra: str = "") -> list[str]:
            return [title_page(1888, number), "Arrêté fictif du 2 janvier 1888." + extra + "\n" + closing(date)]

        decree = ("\nN° 77. — NATURALISATION.\nPar décret présidentiel du 27 décembre 1887, contresigné par M. le Garde des Sceaux, "
                  "ont été admis à jouir des droits de citoyen français les étrangers dont les noms suivent :\n"
                  "Fictan (Jean), journalier, né en 1850 à Oran, demeurant à Alger.")
        texts = issue(1105, "18 février 1888") + issue(1106, "?6 février 1888", decree) + issue(1107, "28 février 1888")
        seg = S.segment_volume(make_pages(texts), 1888)
        self.assertEqual([i.number for i in seg.issues], [1105, 1106, 1107])
        self.assertEqual(seg.issues[1].date.isoformat(), "1888-02-26")
        self.assertEqual(seg.issues[1].date_state, dates.REPAIRED)
        self.assertEqual(seg.decrees[0].issue.number, 1106)
        self.assertEqual(seg.decrees[0].dates, [("1887-12-27", dates.READ)])

    def test_issue_number_hidden_by_a_stamp_is_computed_and_said_so(self) -> None:
        texts = ([title_page(1888, 1103), "Arrêté fictif.\n" + closing("16 janvier 1888")]
                 + [title_page(1888, 1104).replace("N° 1104.", "N° %1"), "Arrêté fictif.\n" + closing("9 février 1888")]
                 + [title_page(1888, 1105), "Arrêté fictif.\n" + closing("18 février 1888")])
        issues = S.livraisons.find_issues(make_pages(texts), 1888)
        self.assertEqual([(i.number, i.number_state) for i in issues],
                         [(1103, S.livraisons.NUMBER_READ), (1104, S.livraisons.NUMBER_COMPUTED), (1105, S.livraisons.NUMBER_READ)])

    def test_decree_without_any_entry_is_kept_and_visible(self) -> None:
        body = ["N° 410. — " + self.heading() + "\n(liste illisible)\nN° 411. — MILICES."]
        seg = S.segment_volume(one_issue(1873, body, closing_date="6 décembre 1873"), 1873)
        self.assertEqual(len(seg.decrees), 1)
        self.assertEqual(seg.decrees[0].entries, [])

    def test_entry_running_over_a_page_break_is_flagged(self) -> None:
        body = ["N° 410. — " + self.heading() + "\n1. Fictietti (Amédée), italien, demeurant à",
                "— 607 —\nAlger.\n2. Exemplino (Nicolas), italien, demeurant à Oran."]
        seg = S.segment_volume(one_issue(1873, body, closing_date="6 décembre 1873"), 1873)
        first, second = seg.decrees[0].entries
        self.assertTrue(first.flags & P.F_SUR_DEUX_PAGES)
        self.assertEqual((first.leaf, second.leaf), (1, 2))
        self.assertEqual(first.residence, "Alger")


    def test_decree_sentence_printed_right_after_an_entry_opens_a_new_decree(self) -> None:
        body = ["N° 19. — NATURALISATION.\n" + self.heading("26 octobre 1887").replace("admises", "admis")
                + "\nFictène (Marie-Louise), femme Exemplké, née de parents français, le 3 mars 1863 à Val-Fictif (Constantine), y demeu- rant. "
                "Par déc et présidentiel en date du 14 novembre 1887 et contresigné par M. lc Garde des Sceaux, Ministre de Ja Jus- tice, "
                "ont été admis à jouir des droits de citoyen français les individus dont les noms suivent :\n"
                "Testano (Ugo), pêcheur, né à Fictida (Italie), le 3 mars 1849, demeurant à Val-Fictif."]
        seg = S.segment_volume(one_issue(1888, body, closing_date="16 janvier 1888"), 1888)
        self.assertEqual([names(decree) for decree in seg.decrees], [["Fictène (Marie-Louise)"], ["Testano (Ugo)"]])
        self.assertEqual(seg.decrees[1].dates, [("1887-11-14", dates.READ)])

    def test_person_introduced_by_m_inside_the_sentence_and_minister_is_no_person(self) -> None:
        body = ["N° 500. — Par décret du 44 avril 1874, M. Fictmann (Aldo- Ulric), lieutenant au régiment étranger, à été admis à "
                "jouir des droits de citoyen français, par application du sénatus-consulte du 14 juillet 1865.\n"
                "N° 501. — Par décret présidentiel, en date du 17 février 1874, contresigné par M. le Garde des Sceaux, Ministre de "
                "la Justice, est admis à jouir des droits de citoyen français, " + SC + ",\n"
                "M. Exemplulo (Ugo), commis de négoce, né de parents italiens, le 3 mars 1849, à Bône (Constantine), y demeurant.\n"
                "Par décret Présidentiel en date du 8 mars 1874, contresigné par M. le Garde des Sceaux, ministre de la justice, a été "
                "appelé à jouir des droits de citoyen français, le sieur : | Testinger (Aldo-Ulric), soldat à la Légion étrangère, "
                "né le 3 mars 1855 à Villefictive (Moselle)."]
        seg = S.segment_volume(one_issue(1874, body, closing_date="28 août 1874"), 1874)
        self.assertEqual([names(decree) for decree in seg.decrees],
                         [["Fictmann (Aldo- Ulric)"], ["Exemplulo (Ugo)"], ["Testinger (Aldo-Ulric)"]])
        self.assertTrue(seg.decrees[0].entries[0].flags & P.F_DANS_ENTETE)

    def test_title_of_another_act_in_capitals_closes_the_list_but_a_damaged_list_header_does_not(self) -> None:
        body = ["N° 447. — " + self.heading("14 août 1877") + "\n"
                "DÉPYRTEMENT D'ALFER\n"
                "1 Le sieur Fictora (Ramiro), curé de la paroisse fictive, né le 3 mars 1825, à Villafictiva (Espagne) ;\n"
                "PENSIONS CIVILES. — DÉCRET DU 27 JUIN 1877.\n"
                "Exemplet (Paul), ex-commis, né à Blida, demeurant à Alger."]
        seg = S.segment_volume(one_issue(1877, body, closing_date="5 septembre 1877"), 1877)
        self.assertEqual(len(seg.decrees), 1)
        self.assertEqual(names(seg.decrees[0]), ["Fictora (Ramiro)"])


class ReviewRegressionTestCase(unittest.TestCase):
    """Defects found by the adversarial review of the first build, each on a synthetic page."""

    GARDE = "contresigné par M. le Garde des Sceaux, Ministre de la Justice"

    def heading(self, date: str = "8 mai 1873") -> str:
        return (f"Par décret présidentiel du {date}, contresigné par le Ministre de la Justice, ont été admises à jouir des "
                f"droits de citoyen français, {SC}, les personnes ci-après désignées :")

    def test_decree_sentence_with_a_destroyed_verb_still_opens_its_own_decree(self) -> None:
        # the persons of the second decree were given to the first one, with the first one's date
        for damaged in ("ont été admis à jonir des droits de citoyen français",
                        "ont été a9- mis à jouir des droits de citoyen français",
                        "ont été ad- mis à joir des droits de citoyen français",
                        ",.-ont été adwis à jouir des droits de citoyen français",
                        "ont été a mis à jouir des droits de citoyen francais",
                        "ont été admis a jouir des dtoits de citoyen français",
                        "ont xxx yyyyy zz qqqqq des droits de citoyen français"):
            with self.subTest(damaged=damaged):
                body = ["N° 410. — " + self.heading("25 mars 1880") + "\n1. Fictietti (Aldo), italien, demeurant à Alger.\n"
                        f"Par décret présidentiel, en date du 4 mai 1880, {self.GARDE}, {damaged}, {SC}, les étrangers dont "
                        "les noms suivent :\nExemplino (Ugo), italien, demeurant à Oran.\nTestaoui ben Exemple, indigène "
                        "musulman, demeurant à Blida."]
                seg = S.segment_volume(one_issue(1880, body, closing_date="20 juin 1880"), 1880)
                self.assertEqual([names(decree) for decree in seg.decrees],
                                 [["Fictietti (Aldo)"], ["Exemplino (Ugo)", "Testaoui ben Exemple"]])
                self.assertEqual(seg.decrees[1].dates, [("1880-05-04", dates.READ)])
                self.assertEqual(seg.unsegmented, [])

    def test_reintegration_and_naturalisation_sentences_with_other_auxiliaries(self) -> None:
        body = ["N° 410. — " + self.heading("8 mars 1886") + "\n1. Fictietti (Aldo), italien, demeurant à Alger.\n"
                f"Per décret présidentiel du 6 avril 1886, {self.GARDE}, et rendu en vertu de l'article 18 du code civil, sont "
                "réintégrés dans la qualité de Français :\nExemplier (Aldo), né le 3 mars 1850 à Val-Fictif, demeurant à Oran.\n"
                f"Par décret présidentiel en date du 18 juin 1886, {self.GARDE}, à été réintégré dans la qualité de Français, le "
                "sieur Testouty (Ulric), caporal à la Légion étrangère, né le 3 mars 1859 à Val-Fictif.\n"
                f"Par décret Présidentiel, en date du 3 mai 1886, {self.GARDE}, est naturalisée française, {SC},\n"
                "La dame Modelignon (Alda-Marcella), religieuse, née le 3 mars 1836 à Villefictive (Luxembourg)."]
        seg = S.segment_volume(one_issue(1886, body, closing_date="20 juillet 1886"), 1886)
        self.assertEqual([decree.nature for decree in seg.decrees],
                         [S.NATURE_ADMISSION, S.NATURE_REINTEGRATION, S.NATURE_REINTEGRATION, S.NATURE_NATURALISATION])
        self.assertEqual([decree.dates[0][0] for decree in seg.decrees], ["1886-03-08", "1886-04-06", "1886-06-18", "1886-05-03"])
        self.assertEqual([len(decree.entries) for decree in seg.decrees], [1, 1, 1, 1])
        self.assertEqual(names(seg.decrees[3]), ["Modelignon (Alda-Marcella)"])

    def test_sub_list_header_alone_is_never_a_decree(self) -> None:
        body = ["N° 126. — NATURALISATION.\nPar décrets présidentiels, " + self.GARDE + ", ont été admis à jouir des droits de "
                "citoyen français :\nDécret du 15 octobre 1884\nDÉPARTEMENT D'ORAN\n"
                "Est naturalisée Française la nommée Fictivia (Alda-Marcella), née le 3 mars 1855 à Villafictiva (Espagne), "
                "demeurant à Val-Fictif.\nExemplino (Ugo), italien, demeurant à Oran."]
        seg = S.segment_volume(one_issue(1885, body, closing_date="20 mars 1885"), 1885)
        self.assertEqual(len(seg.decrees), 1)
        self.assertEqual(seg.decrees[0].nature, S.NATURE_ADMISSION)
        self.assertEqual(seg.decrees[0].dates, [("1884-10-15", dates.READ)])
        self.assertEqual(names(seg.decrees[0]), ["Fictivia (Alda-Marcella)", "Exemplino (Ugo)"])
        self.assertTrue(seg.decrees[0].entries[0].markers & P.M_NATURALISEE)

    def test_minister_named_in_the_sentence_is_never_a_person(self) -> None:
        # « M. Le Garde des Sceaux » (capital L) had become an entry of the decree
        body = ["N° 410. — Par décrets présidentiels du 8 mai 1876, contresignés par M. Le Ministre de la justice, ont été admis à "
                "jouir des droits de citoyen français les étrangers dont les noms suivent :\nFictietti (Aldo), italien, demeurant à Alger.\n"
                "Par décret présidentiel du 9 mai 1876, contresigné par M. Le Garde des Sceaux, Ministre de la Justice, a été admis "
                "à jouir des droits de citoyen français :\nExemplino (Ugo), italien, demeurant à Oran."]
        seg = S.segment_volume(one_issue(1876, body, closing_date="20 juillet 1876"), 1876)
        self.assertEqual([names(decree) for decree in seg.decrees], [["Fictietti (Aldo)"], ["Exemplino (Ugo)"]])

    def test_heading_dates_the_ocr_made_hard_to_read(self) -> None:
        cases = (
            ("en date du 27 février 41879", "20 mai 1879", [("1879-02-27", dates.REPAIRED)]),          # doubled first digit
            ("en date du 13 février", "20 mai 1879", [("1879-02-13", dates.REPAIRED)]),                # no year printed
            ("en date du 5 août 18792", "20 octobre 1879", [("1879-08-05", dates.REPAIRED)]),          # year beyond repair
            ("en date du 2t octobre 1878", "20 janvier 1879", [(None, dates.SUSPECT)]),               # day beyond repair
            ("en date du 44 mai 1879", "20 juillet 1879", [("1879-05-14", dates.SUSPECT)]),           # 14 or 11
        )
        for printed, issue_date, expected in cases:
            with self.subTest(printed=printed):
                body = [f"N° 410. — Par décret présidentiel, {printed}, {self.GARDE}, et rendu en conformité du Sénatus-Consulte "
                        "du 44 juillet 1855, ont été admis à jouir des droits de citoyen français les étrangers dont les noms "
                        "suivent :\nFictietti (Aldo), italien, demeurant à Alger."]
                seg = S.segment_volume(one_issue(1879, body, closing_date=issue_date), 1879)
                self.assertEqual(seg.decrees[0].dates, expected)
                self.assertTrue(seg.decrees[0].date_raw)

    def test_senatus_consulte_with_a_damaged_year_is_never_the_decree_date(self) -> None:
        # « Sénatus-Consulte du 44 juillet 1855 » had been exported as a decree of 14 July
        body = [f"N° 410. — Par décret présidentiel {self.GARDE}, et rendu en conformité du Sénatus-Consulte du 44 juillet 1855, "
                "ont été admis à jouir des droits de citoyen français :\nFictietti (Aldo), italien, demeurant à Alger."]
        seg = S.segment_volume(one_issue(1882, body, closing_date="15 septembre 1882"), 1882)
        self.assertEqual(seg.decrees[0].dates, [])
        self.assertEqual(seg.decrees[0].date_state, dates.SUSPECT)

    def test_date_of_another_act_printed_before_the_word_decret_is_ignored(self) -> None:
        body = [f"N° 202. — NATURALISATION.\nARRÊTÉS DES 6 ET 14 Mars 1888 ne décret présidentiel dn 6 mars 4888, {self.GARDE}, "
                "ont été admis à jouir des droits de citoyen français les étrangers dont les noms suivent :\n"
                "Fictietti (Aldo), italien, demeurant à Alger."]
        seg = S.segment_volume(one_issue(1888, body, closing_date="23 avril 1888"), 1888)
        self.assertEqual(seg.decrees[0].dates, [("1888-03-06", dates.REPAIRED)])

    def test_decree_of_the_same_day_takes_the_date_of_the_decree_before(self) -> None:
        body = ["N° 410. — " + self.heading("24 décembre 1874") + "\n1. Fictietti (Aldo), italien, demeurant à Alger.\n"
                "Par décret du même jour, ont été admises à jouir des droits de citoyen français, les personnes dont les noms "
                "suivent :\nExemplino (Ugo), italien, demeurant à Oran."]
        seg = S.segment_volume(one_issue(1875, body, closing_date="15 février 1875"), 1875)
        self.assertEqual(seg.decrees[1].dates, [("1874-12-24", dates.REPAIRED)])
        self.assertIn("même jour", seg.decrees[1].date_raw)

    def test_dated_title_above_the_sentence_with_a_header_in_between(self) -> None:
        body = ["N° 64. — NATURALISATION.\nDÉCRET DU 28 NOVEMBRE 1883\nll\nDIVISION D'ORAN (Légion Étrangère)\n"
                f"Par décret présidentiel {self.GARDE}, et rendu en conformité du Sénatus-Consulte du 44 juillet 1865, ont été "
                "admis à jouir des droits de citoyen français :\n"
                "Fictmidt (Aldo-Ulric), soldat de 1° cl., né le 3 mars 1858 à Villefictive (ci-devant Bas-Rhin)."]
        seg = S.segment_volume(one_issue(1884, body, closing_date="10 mars 1884"), 1884)
        self.assertEqual(len(seg.decrees), 1)
        self.assertEqual(seg.decrees[0].dates, [("1883-11-28", dates.READ)])

    def test_dated_title_of_the_article_before_is_not_borrowed(self) -> None:
        body = ["N° 63. — PENSIONS CIVILES.\nDÉCRET DU 9 FÉVRIER 1884\nUn décret a concédé une pension civile au sieur Fictera.\n"
                f"N° 64. — Par décret présidentiel {self.GARDE}, ont été admis à jouir des droits de citoyen français :\n"
                "Fictmidt (Aldo-Ulric), soldat de 1° cl., né le 3 mars 1858 à Villefictive (ci-devant Bas-Rhin)."]
        seg = S.segment_volume(one_issue(1884, body, closing_date="10 mars 1884"), 1884)
        self.assertEqual(seg.decrees[0].dates, [])

    def test_dated_title_glued_to_the_end_of_an_entry(self) -> None:
        # the entry was rejected (it held the word « décret ») and the next persons kept the earlier date
        body = [f"N° 362. — Par décrets Présidentiels, {self.GARDE}, ont été admis à jouir des droits de citoyen français, "
                "conformément aux dispositions\ndu Sénatus-Consulte du 14 juillet 4865, les étrangefs dont les noms suivent : "
                "Décret du 4 août 1883 à DIVISION D'ORAN ; Légion étrangère. Ficting (Aldo), soldat de 4° classe, né le 3 mars "
                "1860 à Villefictive (ci-devant Moselle).\n"
                "Exemplatéu (Ramiro-Ugo), propriétaire, né le 3 mars 1854 à Villafictiva (Espagne), demeurant à Val-Fictif. "
                "Décret du 20 août 1883 ù\nTestini (Marc), maçon, né à Villafictiva (Italie), le 3 mars 1851, demeurant à Alger."]
        seg = S.segment_volume(one_issue(1883, body, closing_date="30 octobre 1883"), 1883)
        self.assertEqual([decree.dates[0][0] for decree in seg.decrees], ["1883-08-04", "1883-08-20"])
        self.assertEqual([names(decree) for decree in seg.decrees],
                         [["Ficting (Aldo)", "Exemplatéu (Ramiro-Ugo)"], ["Testini (Marc)"]])
        self.assertEqual(seg.unsegmented, [])

    def test_two_dated_titles_on_one_line_keep_their_own_persons(self) -> None:
        # the person printed between the two titles went to the decree before, the next ones to the wrong date
        body = [f"N° 300. — Par décrets Présidentiels, {self.GARDE}, ont été admis à jouir des droits de citoyen français, {SC}, "
                "les étrangers dont les noms suivent :\nDécret du 23 juin 1883. DIVISION D'ORAN\n"
                "Fictayer (Aldo), soldat de 4° classe à la légion étrangère, né le 3 mars 1859 à Villefictive (ci-devant Bas-Rhin).\n"
                "Décret du 7 juillet 1883. DÉPARTEMENT DE CONSTANTINE Exemplois (Ugo), employé de chemin de fer, né le 3 mars 1850 "
                "à Val-Fictif (île de Malte), demeurant à Bône. Décret du 11 juillet 1883. DIVISION D'ORAN\n"
                "Testourt (Ulric). soldat de 1re classe à la légion étrangère, né le 3 mars 1858 à Val-Modèle (ci-devant Moselle)."]
        seg = S.segment_volume(one_issue(1883, body, closing_date="26 septembre 1883"), 1883)
        self.assertEqual([(decree.dates[0][0], names(decree)) for decree in seg.decrees],
                         [("1883-06-23", ["Fictayer (Aldo)"]), ("1883-07-07", ["Exemplois (Ugo)"]),
                          ("1883-07-11", ["Testourt (Ulric)"])])

    def test_end_of_a_sub_list_header_on_its_own_line_is_not_kept_as_text(self) -> None:
        body = ["N° 410. — " + self.heading("8 mai 1885") + "\n1. Fictietti (Aldo), italien, demeurant à Alger.\n"
                "A été réintégrée dans la qualité de Française,\npar applica- tion de l'article 48 du Coce civil, la nemmée :\n"
                "Exemplivord (Alda-Marcella), femme Testiera, née le 3 mars 1849 à Villefictive (Ardèche), demeurant à Val-Fictif.\n"
                "Est réintégrée dans la qualité de Française,\npar application de l'article 18 du Code civil, la nommée "
                "Modelancey (Alda-Ugolina), femme Fictenech, née le 3 mars 1856 à Val-Fictif, de parents français, demeurant à Blida."]
        seg = S.segment_volume(one_issue(1885, body, closing_date="20 juillet 1885"), 1885)
        self.assertEqual(names(seg.decrees[0]), ["Fictietti (Aldo)", "Exemplivord (Alda-Marcella)", "Modelancey (Alda-Ugolina)"])
        self.assertEqual([entry.markers & P.M_REINTEGREE for entry in seg.decrees[0].entries], [0, P.M_REINTEGREE, P.M_REINTEGREE])
        self.assertEqual(seg.unsegmented, [])

    def test_damaged_list_headers_are_neither_persons_nor_unsegmented_text(self) -> None:
        body = ["N° 410. — " + self.heading("8 mai 1875") + "\nDÉRTEMENT D'ALGER\n1. Fictietti (Aldo), italien, demeurant à Alger.\n"
                "(Territoire civil)\nDIVSION D'ORAN\n2. Exemplino (Ugo), italien, demeurant à Oran.\nLÉPARTEMENT DE CONSTANTINE\n"
                "3. Testini (Marc), italien, demeurant à Bône."]
        seg = S.segment_volume(one_issue(1875, body, closing_date="20 juillet 1875"), 1875)
        self.assertEqual(len(seg.decrees[0].entries), 3)
        self.assertEqual(seg.unsegmented, [])

    def test_department_header_on_the_line_of_the_entry(self) -> None:
        body = ["N° 410. — " + self.heading("8 mai 1878") + "\n"
                "Département d'Alger Fictelie (Aldo-Ulric), cultivateur, né à Villefictive (Prusse), le 45 août 1835, demeurant à Val-Fictif.\n"
                "Département (TOran, Exemplayan (Azar), monogame, marchand ambulant, né à Villefictive (Maroc), le 3 mars 1839, "
                "demeurant à Val-Modèle.\n"
                "Déparlement d'Oran, Testalès (Ramiro), cultivateur, né à Villafictiva (Espagne), en 1836, demeurant à Val-Fictif."]
        seg = S.segment_volume(one_issue(1878, body, closing_date="20 juillet 1878"), 1878)
        self.assertEqual(names(seg.decrees[0]), ["Fictelie (Aldo-Ulric)", "Exemplayan (Azar)", "Testalès (Ramiro)"])
        self.assertEqual(seg.decrees[0].entries[0].department, "alger")
        self.assertEqual(seg.unsegmented, [])

    def test_damaged_department_header_on_its_own_line_never_enters_the_name(self) -> None:
        # the names were 'DÉPARTEMEriT D'ORAN Nom (…)', 'Départemenê d'Oran. De Nom (…)', 'Légion étrangére. Nom (…)'
        body = ["N° 410. — " + self.heading("8 mai 1876") + "\nDÉPARTEMEriT D'ORAN\n"
                "Fictlman (Ulric), courtier maritime, né à Villefictive (Suéde) le 3 mars 4835, domicilié à Oran.\n"
                "Départemenê d'Oran.\nDe Exempluna (Ramiro-Aldo), jardinier, né à Villafictiva (Espagne), le 3 mars 1831, demeurant à Val-Fictif.\n"
                "DIVISION D'ORAN Légion étrangére. Testrey (Aldo-Ulric), soldat de 2° classe, nè le 3 mars 4861 à Val-Modèle (ci-devant Bas-Rhin)."]
        seg = S.segment_volume(one_issue(1876, body, closing_date="20 juillet 1876"), 1876)
        self.assertEqual(names(seg.decrees[0]), ["Fictlman (Ulric)", "De Exempluna (Ramiro-Aldo)", "Testrey (Aldo-Ulric)"])
        self.assertEqual([entry.department for entry in seg.decrees[0].entries], ["oran", "oran", "oran"])
        self.assertEqual(seg.unsegmented, [])

    def test_year_after_the_volume_is_never_exported_as_read(self) -> None:
        body = ["N° 410. — " + self.heading("31 août 1884") + "\n1. Fictietti (Aldo), italien, demeurant à Alger.\n"
                "CxxxxxÉ CxxxxxxE : Axxxx, le 20 décembre 1881."]
        seg = S.segment_volume(make_pages([title_page(1881, 858)] + body), 1881)
        self.assertEqual(seg.decrees[0].dates, [("1881-08-31", dates.SUSPECT)])


class HelpersTestCase(unittest.TestCase):
    def test_formula_variants(self) -> None:
        for text in ("ont été admises à jouir des droits de citoyen français",
                     "ont été ad- mis à jouir des droits de citoyen français",
                     "qui admet à^ouir des droits de citoyens français",
                     "sont admis ù. jouir des droits de citoyen français",
                     "ont été admis à jouir” des droits de citoyen francais",
                     "ont élé admis à jouir dés droits de citoyen français",
                     "sont admis à jouir des dr its de citoyen français",
                     "a été admise à jouir des droits de française",
                     "ont été appelés à jouir de la qualité de citoyen français",
                     "les droits de citoyen français ont été conférés, conformément au sénatus-consulte, au sieur Fictet"):
            with self.subTest(text=text):
                self.assertTrue(S.has_formula(text))

    def test_not_the_formula(self) -> None:
        for text in ("qui veut être admis à jouir des droits de citoyen français",
                     "Décret qui admet divers étrangers à jouir des droits de citoyen français",
                     "Admission de trois indigènes à jouir des droits de citoyen français, D., p. 680",
                     "sont admis à concourir pour les emplois"):
            with self.subTest(text=text):
                self.assertFalse(S.has_formula(text))

    def test_decree_word_within_two_ocr_errors(self) -> None:
        for text in ("Par décret présidentiel", "Par déeret présidentiel", "Par Jécret présidentiel", "Far décret impérial",
                     "Par décrot présidentiel", "Un décret impérial en date du 22 mai 1867", "Décret impérial du 5 décembre 1866"):
            with self.subTest(text=text):
                self.assertTrue(S.decree_intro(text))
        self.assertFalse(S.decree_intro("Par arrêté du 4 novembre 1873"))
        self.assertFalse(S.decree_intro("du décret du 21 avril 1866, les étrangers", at_start=True))

    def test_dated_sub_heading(self) -> None:
        self.assertEqual(S.match_sub_decree("N° 72. — Décret du 30 novembre 1867."), ("30 novembre 1867", ""))
        self.assertEqual(S.match_sub_decree("No 78, — Déc@t du 15 mars 1868.")[0], "15 mars 1868")
        self.assertEqual(S.match_sub_decree("(Décret du 6 juillet)")[0], "6 juillet")
        self.assertEqual(S.match_sub_decree("DÉCRET DU 28 Mat 1873 Département d'Alger"), ("28 Mat 1873", "Département d'Alger"))
        self.assertIsNone(S.match_sub_decree("Décret du 5 septembre 1866, sur le rapport du Garde des Sceaux, est approuvée"))
        self.assertIsNone(S.match_sub_decree("Départ du 5 mars 1874"))

    def test_last_number_of_a_numbered_list(self) -> None:
        self.assertEqual(S._last_list_number([1, 2, 3, None, 5, 6, 7], [], 7), 7)
        self.assertEqual(S._last_list_number([None, None, 3, 4, 442, 6, 7, 8, 9, 10, 11, 12], [], 12), 12)   # 442 misread
        self.assertEqual(S._last_list_number([1, 2, 3, 4, 5, 6, 1, 2, 3], [], 9), 9)                          # restarts per department
        self.assertEqual(S._last_list_number([None] * 20, [20, 21, 22, 23, 24], 20), 24)                      # numbers in the margin
        self.assertIsNone(S._last_list_number([None] * 6, [], 6))


if __name__ == "__main__":
    unittest.main()
