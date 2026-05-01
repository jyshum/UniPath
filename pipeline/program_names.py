"""Program taxonomy helpers backed by canadian_programs.json."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "canadian_programs.json"
SUPPORTED_CATEGORIES = {
    "ENGINEERING",
    "SCIENCE",
    "BUSINESS",
    "COMPUTER_SCIENCE",
    "HEALTH",
    "ARTS",
    "LAW",
    "EDUCATION",
    "OTHER",
}

BROAD_PROGRAMS = {
    "engineering": ("Engineering", "ENGINEERING"),
    "applied science": ("Engineering", "ENGINEERING"),
    "apsc": ("Engineering", "ENGINEERING"),
    "science": ("Science", "SCIENCE"),
    "sciences": ("Science", "SCIENCE"),
    "arts": ("Arts", "ARTS"),
    "humanities": ("Arts", "ARTS"),
    "social science": ("Social Sciences", "ARTS"),
    "social sciences": ("Social Sciences", "ARTS"),
    "business": ("Commerce", "BUSINESS"),
    "commerce": ("Commerce", "BUSINESS"),
    "bcomm": ("Commerce", "BUSINESS"),
    "sauder": ("Commerce", "BUSINESS"),
    "rotman": ("Commerce", "BUSINESS"),
    "schulich": ("Business Administration", "BUSINESS"),
    "beedie": ("Business Administration", "BUSINESS"),
    "ivey": ("Business Administration", "BUSINESS"),
    "ivey aeo": ("Business Administration", "BUSINESS"),
}

LEGACY_ALIASES = {
    # CUDO names.
    "computer and information science": "Computer Science",
    "computer & information science": "Computer Science",
    "commerce/management/business admin": "Commerce",
    "commerce/mgmt/business admin": "Commerce",
    "biological and biomedical sciences": "Biological Sciences",
    "biological & biomedical sciences": "Biological Sciences",
    "health profession and related programs": "Health Sciences",
    "health profession & related programs": "Health Sciences",
    "kinesiology/recreation/physical education": "Kinesiology",
    "fine and applied arts": "Fine Arts",
    "fine & applied arts": "Fine Arts",
    "liberal arts and sciences/general studies": "Arts",
    "liberal arts & sciences/general studies": "Arts",
    "mathematics and statistics": "Mathematics",
    "mathematics & statistics": "Mathematics",
    "physical science": "Physical Sciences",
    # Pipeline variants not guaranteed by the taxonomy.
    "compsci": "Computer Science",
    "cs": "Computer Science",
    "computer science": "Computer Science",
    "life sci": "Life Sciences",
    "life sciences": "Life Sciences",
    "biomed": "Biomedical Sciences",
    "kin": "Kinesiology",
    "med sci": "Medical Sciences",
    "medical sciences": "Medical Sciences",
    "psych": "Psychology",
    "econ": "Economics",
}

BROAD_CATEGORY_FALLBACK = {
    "Engineering": "ENGINEERING",
    "Science": "SCIENCE",
    "Arts": "ARTS",
    "Social Sciences": "ARTS",
    "Commerce": "BUSINESS",
    "Business Administration": "BUSINESS",
    "Education": "EDUCATION",
    "Law": "LAW",
    "Architecture": "OTHER",
}

HIGH_SIGNAL_ALIASES = {
    "syde",
    "nano",
    "afm",
    "farm",
    "engsci",
    "tron",
    "mte",
    "sauder",
    "ivey",
    "aeo",
    "rotman",
    "schulich",
    "beedie",
}


@dataclass(frozen=True)
class ProgramEntry:
    canonical_name: str
    category: str
    schools: tuple[str, ...]
    aliases: tuple[str, ...]
    admission_type: dict[str, str]


@dataclass(frozen=True)
class ProgramTaxonomy:
    programs: tuple[ProgramEntry, ...]
    admission_notes: dict


@lru_cache(maxsize=1)
def _taxonomy_data() -> dict:
    with TAXONOMY_PATH.open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_program_taxonomy() -> ProgramTaxonomy:
    data = _taxonomy_data()
    programs = tuple(
        ProgramEntry(
            canonical_name=p["canonical_name"],
            category=p["category"],
            schools=tuple(p.get("schools", [])),
            aliases=tuple(p.get("aliases", [])),
            admission_type=dict(p.get("admission_type", {})),
        )
        for p in data.get("programs", [])
    )
    return ProgramTaxonomy(
        programs=programs,
        admission_notes=data.get("metadata", {}).get("admission_notes", {}),
    )


def _key(value: str) -> str:
    normalized = value.strip().lower().replace("&", " and ")
    normalized = normalized.replace("/", " ").replace("-", " ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _candidate_keys(raw: str) -> set[str]:
    raw = raw.strip()
    candidates = {
        raw,
        raw.replace("/", " "),
        raw.replace("-", " "),
        raw.replace("&", "and"),
    }
    return {_key(candidate) for candidate in candidates if candidate.strip()}


def _normalize_broad_faculty(raw: str) -> str | None:
    return BROAD_PROGRAMS.get(_key(raw), (None, None))[0]


def _school_matches(program: ProgramEntry, school: str | None) -> bool:
    if not school:
        return False
    school_key = _key(school)
    return any(_key(candidate) == school_key for candidate in program.schools)


def _token_contains(raw_key: str, candidate_key: str) -> bool:
    if not candidate_key or len(candidate_key) < 4:
        return False
    return f" {candidate_key} " in f" {raw_key} "


def _contains_fallback(raw: str, school: str | None = None) -> str | None:
    raw_key = _key(raw)
    taxonomy = load_program_taxonomy()
    candidates: list[tuple[int, ProgramEntry]] = []
    for program in taxonomy.programs:
        for name in (program.canonical_name, *program.aliases):
            name_key = _key(name)
            if _token_contains(raw_key, name_key):
                candidates.append((len(name_key), program))
    if school:
        school_candidates = [
            item for item in candidates if _school_matches(item[1], school)
        ]
        if school_candidates:
            candidates = school_candidates
    if candidates:
        return sorted(candidates, key=lambda item: item[0], reverse=True)[0][1].canonical_name

    broad_candidates = [
        (len(key), value[0])
        for key, value in BROAD_PROGRAMS.items()
        if _token_contains(raw_key, key)
    ]
    if broad_candidates:
        return sorted(broad_candidates, key=lambda item: item[0], reverse=True)[0][1]
    return None


def validate_program_taxonomy() -> list[str]:
    """Return validation errors for taxonomy shape and canonical conflicts."""
    errors: list[str] = []
    seen: dict[str, str] = {}
    for program in load_program_taxonomy().programs:
        name = program.canonical_name
        category = program.category
        if not name:
            errors.append("missing canonical_name")
            continue
        if category not in SUPPORTED_CATEGORIES:
            errors.append(f"unsupported category for {name}: {category}")
        if name in seen and seen[name] != category:
            errors.append(f"duplicate canonical name in multiple categories: {name}")
        seen[name] = category
    return errors


def normalize_program_name(raw: str | None, school: str | None = None) -> str | None:
    """Normalize a program name to its canonical form."""
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None

    broad = _normalize_broad_faculty(raw)
    if broad:
        return broad

    keys = _candidate_keys(raw)
    legacy_matches = [name for key, name in LEGACY_ALIASES.items() if _key(key) in keys]
    taxonomy = load_program_taxonomy()
    matches: list[ProgramEntry] = []
    for program in taxonomy.programs:
        program_keys = {_key(program.canonical_name), *(_key(alias) for alias in program.aliases)}
        if keys & program_keys:
            matches.append(program)

    if school:
        school_matches = [program for program in matches if _school_matches(program, school)]
        if len(school_matches) == 1:
            return school_matches[0].canonical_name

    if len(matches) == 1:
        return matches[0].canonical_name

    if legacy_matches:
        return legacy_matches[0]

    contained = _contains_fallback(raw, school=school)
    if contained:
        return contained

    return raw


def get_program_category(canonical_name: str | None) -> str:
    """Get the broad program category for a canonical program name."""
    if not canonical_name:
        return "OTHER"
    for program in load_program_taxonomy().programs:
        if program.canonical_name == canonical_name:
            return program.category
    broad = _normalize_broad_faculty(canonical_name)
    if broad and broad != canonical_name:
        return get_program_category(broad)
    return BROAD_CATEGORY_FALLBACK.get(canonical_name, "OTHER")


def get_admission_type(canonical_name: str, school: str) -> str | None:
    """Return direct/faculty/mixed admission metadata for a school/program."""
    for program in load_program_taxonomy().programs:
        if program.canonical_name == canonical_name:
            explicit = program.admission_type.get(school)
            if explicit:
                return explicit
    notes = load_program_taxonomy().admission_notes.get(school, {})
    category = get_program_category(canonical_name).lower()
    return notes.get(category) or notes.get("all")


def get_admission_note(school: str, category_or_program: str | None = None) -> str | None:
    """Return the human-readable admission note for a school."""
    notes = load_program_taxonomy().admission_notes.get(school)
    if not notes:
        return None
    return notes.get("note")


def program_aliases_for_prompt(max_items: int | None = None) -> str:
    """Format high-signal aliases for the Reddit extraction prompt."""
    rows = []
    for program in load_program_taxonomy().programs:
        aliases = [alias for alias in program.aliases if _key(alias) in HIGH_SIGNAL_ALIASES]
        if aliases:
            rows.append(f'- {", ".join(aliases)} -> {program.canonical_name}')
    rows.sort()
    if max_items is not None:
        rows = rows[:max_items]
    return "\n".join(rows)


def program_search_terms() -> list[str]:
    """Return bounded, taxonomy-backed Reddit search terms."""
    terms = {
        "Waterloo SYDE accepted",
        "Waterloo nano accepted",
        "Waterloo AFM accepted",
        "Waterloo FARM accepted",
        "Waterloo tron accepted",
        "UofT EngSci accepted",
        "UBC Sauder accepted",
        "Western Ivey AEO",
        "McMaster health sci accepted",
    }
    for program in load_program_taxonomy().programs:
        for alias in program.aliases:
            if _key(alias) in HIGH_SIGNAL_ALIASES:
                for school in program.schools[:2]:
                    short = school.replace("University of ", "")
                    short = short.replace("UBC Vancouver", "UBC")
                    short = short.replace("Toronto", "UofT")
                    terms.add(f"{short} {alias} accepted")
    return sorted(terms)[:250]
