from pipeline.program_names import normalize_program_name, get_program_category


def test_normalize_cudo_name():
    """CUDO-style names map to canonical names."""
    assert normalize_program_name("Computer & Information Science") == "Computer Science"
    assert normalize_program_name("Commerce/Management/Business Admin") == "Commerce"
    assert normalize_program_name("Commerce/Mgmt/Business Admin") == "Commerce"
    assert normalize_program_name("Biological & Biomedical Sciences") == "Biological Sciences"


def test_normalize_pipeline_variant():
    """Pipeline program_raw variants map to canonical names."""
    assert normalize_program_name("CompSci") == "Computer Science"
    assert normalize_program_name("CS") == "Computer Science"
    assert normalize_program_name("Life Sci") == "Life Sciences"
    assert normalize_program_name("Sauder") == "Commerce"
    assert normalize_program_name("Ivey AEO") == "Business Administration"


def test_normalize_passthrough():
    """Names not in the map pass through unchanged."""
    assert normalize_program_name("Engineering") == "Engineering"
    assert normalize_program_name("Nursing") == "Nursing"


def test_normalize_case_insensitive():
    """Lookup is case-insensitive."""
    assert normalize_program_name("compsci") == "Computer Science"
    assert normalize_program_name("COMPSCI") == "Computer Science"


def test_normalize_none_returns_none():
    """None input returns None."""
    assert normalize_program_name(None) is None


def test_get_program_category():
    """Canonical names map to broad categories."""
    assert get_program_category("Computer Science") == "COMPUTER_SCIENCE"
    assert get_program_category("Commerce") == "BUSINESS"
    assert get_program_category("Engineering") == "ENGINEERING"
    assert get_program_category("Life Sciences") == "SCIENCE"
    assert get_program_category("Nursing") == "HEALTH"


def test_get_program_category_unknown():
    """Unknown program names return OTHER."""
    assert get_program_category("Underwater Basket Weaving") == "OTHER"


def test_taxonomy_has_no_duplicate_canonical_name_categories():
    from pipeline.program_names import validate_program_taxonomy

    errors = validate_program_taxonomy()

    assert not [e for e in errors if "duplicate canonical" in e.lower()]


def test_biomedical_sciences_is_science():
    assert normalize_program_name("biomed sci", school="University of Waterloo") == "Biomedical Sciences"
    assert get_program_category("Biomedical Sciences") == "SCIENCE"


def test_school_aware_engineering_aliases():
    assert normalize_program_name("SYDE", school="University of Waterloo") == "Systems Design Engineering"
    assert normalize_program_name("tron", school="University of Waterloo") == "Mechatronics Engineering"
    assert normalize_program_name("EngSci", school="University of Toronto") == "Engineering Science"


def test_broad_faculty_names_stay_broad():
    assert normalize_program_name("Engineering", school="UBC Vancouver") == "Engineering"
    assert normalize_program_name("Applied Science", school="UBC Vancouver") == "Engineering"
    assert normalize_program_name("Science", school="UBC Vancouver") == "Science"


def test_admission_metadata_helpers():
    from pipeline.program_names import get_admission_type, get_admission_note

    assert get_admission_type("Systems Design Engineering", "University of Waterloo") == "direct"
    assert get_admission_type("Engineering", "UBC Vancouver") == "faculty"
    assert "Engineering" in get_admission_note("UBC Vancouver")


def test_program_aliases_for_prompt_includes_high_signal_aliases():
    from pipeline.program_names import program_aliases_for_prompt

    prompt = program_aliases_for_prompt(max_items=80)

    assert "SYDE" in prompt or "syde" in prompt
    assert "EngSci" in prompt or "engsci" in prompt
    assert "AFM" in prompt or "afm" in prompt
    assert "Sauder" in prompt or "sauder" in prompt


def test_program_search_terms_are_bounded_and_targeted():
    from pipeline.program_names import program_search_terms

    terms = program_search_terms()

    assert "Waterloo SYDE accepted" in terms
    assert "UofT EngSci accepted" in terms
    assert "Western Ivey AEO" in terms
    assert len(terms) <= 250
