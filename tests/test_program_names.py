from pipeline.program_names import normalize_program_name, get_program_category


def test_normalize_cudo_name():
    """CUDO-style names map to canonical names."""
    assert normalize_program_name("Computer & Information Science") == "Computer Science"
    assert normalize_program_name("Commerce/Management/Business Admin") == "Commerce"
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
