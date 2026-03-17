# normalizes unclean data 
#       - run with python -m pipeline.normalize

import re
import pandas as pd
from pathlib import Path

BC_FETCHED_PATH = Path("data/processed/bc_fetched.csv")
BC_CLEANED_PATH = Path("data/cleaned/bc_cleaned.csv")

SCHOOL_LOOKUP = {
    # UBC Vancouver
    "ubcv": "UBC Vancouver",
    "ubc vancouver": "UBC Vancouver",
    "ubc": "UBC Vancouver",
    "ubc ": "UBC Vancouver",
    "ubcv ": "UBC Vancouver",

    # UBC Okanagan
    "ubco": "UBC Okanagan",
    "ubc okanagan": "UBC Okanagan",

    # Simon Fraser University
    "sfu": "Simon Fraser University",
    "simon fraser": "Simon Fraser University",
    "simon fraser university": "Simon Fraser University",

    # University of Victoria
    "uvic": "University of Victoria",
    "u vic": "University of Victoria",
    "university of victoria": "University of Victoria",

    # University of Alberta
    "uofa": "University of Alberta",
    "u of a": "University of Alberta",
    "university of alberta": "University of Alberta",

    # University of Toronto
    "uoft": "University of Toronto",
    "u of t": "University of Toronto",
    "university of toronto": "University of Toronto",
    "university of toronto (st. george)": "University of Toronto",
    "uoft st. george": "University of Toronto",
    "u of t sg": "University of Toronto",
    "ut mississauga": "University of Toronto Mississauga",

    # Western University
    "uwo": "Western University",
    "western": "Western University",
    "western ": "Western University",
    "western university": "Western University",
    "huron university (western)": "Western University",

    # Queen's University
    "queens": "Queen's University",
    "queen's": "Queen's University",
    "queens university": "Queen's University",

    # University of Waterloo
    "waterloo": "University of Waterloo",
    "university of waterloo": "University of Waterloo",

    # McGill University
    "mcgill": "McGill University",
    "mcgill university": "McGill University",

    # McMaster University
    "mcmaster": "McMaster University",
    "mcmaster university": "McMaster University",
    "mcmaster univeristy": "McMaster University",

    # University of Saskatchewan
    "usask": "University of Saskatchewan",
    "university of saskatchewan": "University of Saskatchewan",

    # University of Calgary
    "university of calgary": "University of Calgary",
    "university of calgary ": "University of Calgary",

    # Vancouver Island University
    "viu": "Vancouver Island University",
    "viu, nanaimo": "Vancouver Island University",

    # Other
    "bcit": "BCIT",
    "bcit - burnaby": "BCIT",
    "carleton university": "Carleton University",
    "uottawa": "University of Ottawa",
    "nipissing university": "Nipissing University",
    "wilfred laurier university": "Wilfrid Laurier University",
    "bow valley college": "Bow Valley College",
}

PROVINCE_LOOKUP = {
    # British Columbia
    "bc": "BC",
    "b.c.": "BC",
    "british columbia": "BC",
    "british colombia": "BC",  # typo seen in data

    # Ontario
    "on": "ON",
    "ontario": "ON",

    # Alberta
    "ab": "AB",
    "alberta": "AB",

    # Saskatchewan
    "sk": "SK",
    "saskatchewan": "SK",

    # Manitoba
    "mb": "MB",
    "manitoba": "MB",

    # Quebec
    "qc": "QC",
    "quebec": "QC",
    "québec": "QC",

    # Nova Scotia
    "ns": "NS",
    "nova scotia": "NS",

    # New Brunswick
    "nb": "NB",
    "new brunswick": "NB",
    "new brusnwick": "NB",  # typo seen in data

    # Newfoundland
    "nl": "NL",
    "newfoundland": "NL",
    "newfoundland and labrador": "NL",

    # Prince Edward Island
    "pe": "PE",
    "pei": "PE",
    "prince edward island": "PE",
}


def normalize_province(raw) -> str | None:
    """
    Normalizes a raw province string to a two-letter code.
    Returns None for unrecognized or non-Canadian values.
    """
    if pd.isna(raw) or str(raw).strip().upper() in ("N/A", "NA", ""):
        return None

    raw = str(raw).strip().lower()

    return PROVINCE_LOOKUP.get(raw, None)


def normalize_school(raw) -> tuple[str | None, bool]:
    """
    Normalizes a raw school name string.

    Returns:
        (normalized_name, multi_school_flag)
        - normalized_name: canonical school name, or None if unparseable
        - multi_school_flag: True if multiple schools were listed in one cell
    """
    if pd.isna(raw) or str(raw).strip() == "":
        return None, False

    raw = str(raw).strip()

    # Detect multiple schools — commas or slashes separating names
    separators = [",", "/"]
    is_multi = any(sep in raw for sep in separators)

    # Always work with the first school mentioned
    first = raw.split(",")[0].split("/")[0].strip()

    normalized = SCHOOL_LOOKUP.get(first.lower())

    return normalized, is_multi

# normalize grades
def parse_average(raw) -> float | None:
    """
    Parses a raw grade string into a float percentage.

    Handles:
    - '' | NaN | 'N/A' | 'na' | 'n/a' -> none
    - IB scores 'IB 38/45...'         -> score/45 * 100
    - Percentage strings '74%'        -> 74.0
    - Clean numbers '96.6'            -> 96.6
    - anything unpareseable           -> none
    """

    # handles empty
    if pd.isna(raw) or str(raw).strip().upper() in ("N/A", "NA", ""):
        return None
    
    raw = str(raw).strip()

    # handles ib score
    if "IB" in raw.upper():
        match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*45", raw)
        if match:
            score = float(match.group(1))
            return round(score / 45 * 100, 2)
        return None

    # percentage string
    if "%" in raw:
        try:
            return float(raw.replace("%", "").strip())
        except ValueError:
            return None

    # plain number
    try:
        return float(raw)
    except ValueError:
        return None

def normalize_decision(raw) -> str | None: 

    if pd.isna(raw) or str(raw).strip().upper() in ("N/A", "NA", ""):
        return None
    
    raw = str(raw).strip().lower()

    if "accepted" in raw:
        return "ACCEPTED"
    
    if "waitlisted" in raw:
        return "WAITLISTED"
    
    if "deferred" in raw:
        return "DEFERRED"
    
    if "rejected" in raw:
        return "REJECTED"
    
    return None

def normalize_citizenship(raw) -> str | None:

    if pd.isna(raw) or str(raw).strip().upper() in ("N/A", "NA", ""):
        return None

    raw = str(raw).strip().lower()

    canadian_terms = {"canada", "canadian", "can", "ca"}

    if "canada" in raw or "canadian" in raw or raw in canadian_terms:
        return "DOMESTIC"
    
    return "INTERNATIONAL"

def normalize_row(row: pd.Series) -> dict:
    """
    Applies all normalization functions to a single row.
    Returns a dict of normalized values ready for the cleaned DataFrame.
    """
    school_normalized, multi_school_flag = normalize_school(row.get("School "))

    return {
        # Provenance
        "source": row.get("source"),
        "pulled_at": row.get("pulled_at"),

        # School
        "school_raw": row.get("School "),
        "school_normalized": school_normalized,
        "multi_school_flag": multi_school_flag,

        # Program
        "program_raw": row.get("Major/degree"),

        # Decision
        "decision": normalize_decision(row.get("Final status")),

        # Grades
        "grade_11_avg": parse_average(row.get("Grade 11 average")),
        "grade_12_avg": parse_average(row.get("General grade 12 average")),
        "core_avg": parse_average(row.get("Core average")),

        # Extracurriculars and circumstances (raw for now — Session 4 handles tagging)
        "ec_raw": row.get("Extracurriculars/notable essay/interview topics"),
        "circumstances_raw": row.get("Special circumstances"),

        # Location and citizenship
        "province": normalize_province(row.get("Province of residence")),
        "citizenship": normalize_citizenship(row.get("Country of citizenship")),

        # Metadata
        "scholarship": row.get("Scholarship?"),
        "comments_raw": row.get("Additional comments?"),
    }


def run():
    """
    Reads bc_fetched.csv, normalizes every row, saves to bc_cleaned.csv.
    Prints a summary of null counts per key field.
    """
    print("Reading bc_fetched.csv...")
    df = pd.read_csv(BC_FETCHED_PATH)

    print(f"  {len(df)} rows to normalize")

    normalized_rows = [normalize_row(row) for _, row in df.iterrows()]
    cleaned_df = pd.DataFrame(normalized_rows)

    BC_CLEANED_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_csv(BC_CLEANED_PATH, index=False)
    print(f"  Saved to {BC_CLEANED_PATH}")

    # Summary — how many nulls per key field
    key_fields = [
        "school_normalized", "decision", "grade_11_avg",
        "grade_12_avg", "core_avg", "province", "citizenship"
    ]
    print("\nNull counts per key field:")
    for field in key_fields:
        null_count = cleaned_df[field].isna().sum()
        total = len(cleaned_df)
        print(f"  {field}: {null_count}/{total} null")


if __name__ == "__main__":
    run()
    