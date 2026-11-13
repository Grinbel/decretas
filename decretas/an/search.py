"""A simple debugging search over the database (the site has its own search, in the browser).

Vocabulary of CONTEXT.md: a *terme* is one element of the ancestor's name, typed with one or
more *variantes*; a notice is a *correspondance* when at least one variant of every term is
found among the words of the notice (principal, spouse, children), in any order; a
*correspondance partielle* lacks exactly one term, which is named. Particles (ben, ould, el…)
are never required and never used as keys.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from . import names

LEVEL_EXACT = "exacte"
LEVEL_CLOSE = "graphie voisine"
LEVEL_LOOSE = "graphie approchante"
LEVELS: tuple[str, ...] = (LEVEL_EXACT, LEVEL_CLOSE, LEVEL_LOOSE)

ROLE_PRINCIPAL = "principal"


@dataclass(slots=True)
class Term:
    variants: list[str]
    keys: tuple[frozenset[str], frozenset[str], frozenset[str]]   # per level: k0, k1, k2

    @property
    def label(self) -> str:
        return self.variants[0]


@dataclass(slots=True)
class TermHit:
    role: str
    level: int      # index in LEVELS
    word: str       # the notice word that matched


@dataclass(slots=True)
class Correspondence:
    person_id: int
    hits: dict[int, TermHit]              # term index -> best hit
    missing: list[str] = field(default_factory=list)   # labels of absent terms (partial only)

    @property
    def level(self) -> int:
        return max(hit.level for hit in self.hits.values())


@dataclass(slots=True)
class SearchResult:
    terms: list[Term]
    searched_notices: int
    correspondences: list[Correspondence]
    partial: list[Correspondence]
    notices_per_term: list[int]


def make_term(text: str) -> Term:
    """'Belkacem,Belgacem/Bel Kacem' -> a term with three variants.

    A form obtained by detaching a prefix from what the user typed ('Belhadi' -> 'hadi') is
    only ever a loose key: such a hit is reported as an approximate spelling, never as exact.
    """
    variants = [v.strip() for v in text.replace("/", ",").replace("|", ",").split(",") if v.strip()]
    typed: set[str] = set()
    detached: set[str] = set()
    for variant in variants:
        words = names.tokens(variant)
        significant = [w for w in words if w not in names.PARTICLES and len(w) > 1] or words
        whole = {"".join(words)} if len(words) > 1 else set()
        if len(significant) == 1:
            whole.add(significant[0])
        for form in whole - names.PARTICLES:
            typed.add(form)
            detached.update(f for f in names.split_forms(form) if f not in names.PARTICLES)
    return Term(variants or [text], (frozenset(typed), frozenset(names.k1(f) for f in typed),
                                     frozenset(names.k2(f) for f in typed | detached)))


def _best_hit(term: Term, role: str, forms: set[str]) -> TermHit | None:
    best: TermHit | None = None
    for form in forms:
        if form in term.keys[0]:
            return TermHit(role, 0, form)
        if names.k1(form) in term.keys[1]:
            level = 1
        elif names.k2(form) in term.keys[2]:
            level = 2
        else:
            continue
        if best is None or level < best.level:
            best = TermHit(role, level, form)
    return best


def search(connection: sqlite3.Connection, term_texts: list[str], *, born_around: int | None = None,
           tolerance: int = 5, tier_only: bool = False) -> SearchResult:
    """Search every person notice of the database (or of the Algeria tier only)."""
    terms = [make_term(text) for text in term_texts]
    tier_clause = "WHERE p.palier_algerie = 1" if tier_only else ""
    occurrences: dict[int, list[tuple[str, str, int | None]]] = {}
    for person_id, name, year in connection.execute(
            f"SELECT p.personne_id, p.nom_brut, p.naissance_annee FROM personne p {tier_clause}"):
        occurrences[person_id] = [(ROLE_PRINCIPAL, name, year)]
    for person_id, role, name, year in connection.execute(
            f"SELECT a.personne_id, a.role, a.nom_brut, a.naissance_annee FROM apparente a "
            f"JOIN personne p USING(personne_id) {tier_clause} ORDER BY a.personne_id, a.rang"):
        occurrences[person_id].append((role, name, year))

    full: list[Correspondence] = []
    partial: list[Correspondence] = []
    per_term = [0] * len(terms)
    for person_id in sorted(occurrences):
        hits: dict[int, TermHit] = {}
        years: dict[str, list[int | None]] = {}
        for role, name, year in occurrences[person_id]:
            years.setdefault(role, []).append(year)
            forms = names.expand(names.tokens(name))
            for index, term in enumerate(terms):
                hit = _best_hit(term, role, forms)
                if hit is not None and (index not in hits or hit.level < hits[index].level):
                    hits[index] = hit
        if not hits:
            continue
        for index in hits:
            per_term[index] += 1
        if born_around is not None and not _born_near(hits, years, born_around, tolerance):
            continue
        if len(hits) == len(terms):
            full.append(Correspondence(person_id, hits))
        elif len(terms) > 1 and len(hits) == len(terms) - 1:
            missing = [term.label for index, term in enumerate(terms) if index not in hits]
            partial.append(Correspondence(person_id, hits, missing))
    full.sort(key=lambda c: (c.level, c.person_id))
    partial.sort(key=lambda c: (c.level, c.person_id))
    return SearchResult(terms, len(occurrences), full, partial, per_term)


def _born_near(hits: dict[int, TermHit], years: dict[str, list[int | None]], target: int, tolerance: int) -> bool:
    """True when a person whose name matched may be born around ``target`` (unknown years pass)."""
    candidates = [year for role in {hit.role for hit in hits.values()} for year in years.get(role, [])]
    known = [year for year in candidates if year is not None]
    if not known:
        return True
    return any(abs(year - target) <= tolerance for year in known)


def describe(connection: sqlite3.Connection, person_id: int) -> dict[str, object]:
    """Everything worth printing about one person notice."""
    row = connection.execute(
        "SELECT p.inv, p.notice_id, p.titre_brut, p.nom_non_saisi, p.naissance_brut, p.naissance_annee, "
        "p.naissance_conventionnelle, p.naissance_suspecte, p.residence, p.profession, p.dossier, p.dossier_brut, "
        "p.cote_dossier, p.lien_notice, p.lien_images, p.indice, p.regle, p.palier_algerie, d.date, d.date_drapeau, "
        "d.titre, d.classe_algerie, d.cote, d.cote_drapeau, d.cote_suggeree, d.document, d.lien_notice, d.lien_images, "
        "d.notice_id FROM personne p JOIN decret d USING(decret_id) WHERE p.personne_id = ?", (person_id,)).fetchone()
    keys = ("inv", "notice", "nom", "nom_non_saisi", "naissance", "annee", "conventionnelle", "suspecte", "residence",
            "profession", "dossier", "dossier_brut", "cote_dossier", "lien_notice", "lien_images", "indice", "regle",
            "palier", "decret_date", "decret_drapeau_date", "decret_titre", "decret_classe", "decret_cote",
            "decret_drapeau_cote", "decret_cote_suggeree", "decret_document", "decret_lien_notice",
            "decret_lien_images", "decret_notice")
    record: dict[str, object] = dict(zip(keys, row))
    record["apparentes"] = connection.execute(
        "SELECT role, texte_brut, appariement FROM apparente WHERE personne_id = ? ORDER BY rang",
        (person_id,)).fetchall()
    return record
