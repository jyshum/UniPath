"""Program name normalization. Maps variant names to canonical program names."""

# Keys are lowercase for case-insensitive lookup.
# Values are the canonical program name.
_PROGRAM_NAME_MAP = {
    # CUDO names → canonical
    "computer & information science": "Computer Science",
    "commerce/management/business admin": "Commerce",
    "biological & biomedical sciences": "Biological Sciences",
    "health profession & related programs": "Health Sciences",
    "kinesiology/recreation/physical education": "Kinesiology",
    "fine & applied arts": "Fine Arts",
    "liberal arts & sciences/general studies": "Arts",
    "mathematics & statistics": "Mathematics",
    "physical science": "Physical Sciences",
    "social sciences": "Social Sciences",

    # Pipeline program_raw variants → canonical
    "compsci": "Computer Science",
    "cs": "Computer Science",
    "computer science": "Computer Science",
    "life sci": "Life Sciences",
    "life sciences": "Life Sciences",
    "sauder": "Commerce",
    "bcomm": "Commerce",
    "commerce": "Commerce",
    "ivey aeo": "Business Administration",
    "ivey": "Business Administration",
    "business administration": "Business Administration",
    "health sci": "Health Sciences",
    "health sciences": "Health Sciences",
    "biomed": "Biomedical Sciences",
    "biomedical sciences": "Biomedical Sciences",
    "kin": "Kinesiology",
    "kinesiology": "Kinesiology",
    "med sci": "Medical Sciences",
    "medical sciences": "Medical Sciences",
    "nursing": "Nursing",
    "pharmacy": "Pharmacy",
    "psychology": "Psychology",
    "engineering": "Engineering",
    "science": "Science",
    "arts": "Arts",
    "mathematics": "Mathematics",
    "economics": "Economics",
    "education": "Education",
    "law": "Law",
    "architecture": "Architecture",
    "biochemistry": "Biochemistry",
    "physics": "Physics",
}

# Canonical program name → broad category
_PROGRAM_CATEGORY_MAP = {
    "Computer Science": "COMPUTER_SCIENCE",
    "Commerce": "BUSINESS",
    "Business Administration": "BUSINESS",
    "Engineering": "ENGINEERING",
    "Life Sciences": "SCIENCE",
    "Biological Sciences": "SCIENCE",
    "Biomedical Sciences": "SCIENCE",
    "Science": "SCIENCE",
    "Physical Sciences": "SCIENCE",
    "Mathematics": "SCIENCE",
    "Biochemistry": "SCIENCE",
    "Physics": "SCIENCE",
    "Health Sciences": "HEALTH",
    "Medical Sciences": "HEALTH",
    "Nursing": "HEALTH",
    "Kinesiology": "HEALTH",
    "Pharmacy": "HEALTH",
    "Arts": "ARTS",
    "Fine Arts": "ARTS",
    "Social Sciences": "ARTS",
    "Psychology": "ARTS",
    "Economics": "ARTS",
    "Education": "EDUCATION",
    "Law": "LAW",
    "Architecture": "OTHER",
}


def normalize_program_name(raw: str | None) -> str | None:
    """Normalize a program name to its canonical form.

    Returns the canonical name if found in the map, otherwise returns
    the input unchanged (stripped). Returns None for None input.
    """
    if raw is None:
        return None
    key = raw.strip().lower()
    if key in _PROGRAM_NAME_MAP:
        return _PROGRAM_NAME_MAP[key]
    return raw.strip()


def get_program_category(canonical_name: str) -> str:
    """Get the broad program category for a canonical program name.

    Returns 'OTHER' if the name is not in the category map.
    """
    return _PROGRAM_CATEGORY_MAP.get(canonical_name, "OTHER")
