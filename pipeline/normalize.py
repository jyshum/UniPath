# normalizes unclean data 
#       - run with python -m pipeline.normalize

import re
import pandas as pd
from pathlib import Path

BC_FETCHED_PATH = Path("data/processed/bc_fetched.csv")
BC_CLEANED_PATH = Path("data/cleaned/bc_cleaned.csv")

SCHOOL_LOOKUP = {
    # -------------------------
    # UBC Vancouver
    # -------------------------
    "ubc": "UBC Vancouver",
    "ubc ": "UBC Vancouver",
    "ubcv": "UBC Vancouver",
    "ubcv ": "UBC Vancouver",
    "ubc vancouver": "UBC Vancouver",
    "university of british columbia": "UBC Vancouver",
    "ubc v": "UBC Vancouver",
    # UBC faculty names → UBC Vancouver
    "sauder": "UBC Vancouver",
    "ubc sauder": "UBC Vancouver",
    "sauder school of business": "UBC Vancouver",

    # -------------------------
    # UBC Okanagan
    # -------------------------
    "ubco": "UBC Okanagan",
    "ubc okanagan": "UBC Okanagan",
    "ubc-o": "UBC Okanagan",

    # -------------------------
    # Simon Fraser University
    # -------------------------
    "sfu": "Simon Fraser University",
    "simon fraser": "Simon Fraser University",
    "simon fraser university": "Simon Fraser University",
    # SFU faculty names
    "beedie": "Simon Fraser University",
    "sfu beedie": "Simon Fraser University",

    # -------------------------
    # University of Victoria
    # -------------------------
    "uvic": "University of Victoria",
    "u vic": "University of Victoria",
    "university of victoria": "University of Victoria",
    "uvictoria": "University of Victoria",
    "uvic (university of victoria)": "University of Victoria",

    # -------------------------
    # University of Alberta
    # -------------------------
    "uofa": "University of Alberta",
    "u of a": "University of Alberta",
    "u of alberta": "University of Alberta",
    "university of alberta": "University of Alberta",
    "alberta": "University of Alberta",
    "ualberta": "University of Alberta",
    "uofalberta": "University of Alberta",

    # -------------------------
    # University of Toronto
    # -------------------------
    "uoft": "University of Toronto",
    "u of t": "University of Toronto",
    "university of toronto": "University of Toronto",
    "utsg": "University of Toronto",
    "uoft sg": "University of Toronto",
    "uoft - sg": "University of Toronto",
    "uoft (toronto)": "University of Toronto",
    "uoft (st. george)": "University of Toronto",
    "u of t sg": "University of Toronto",
    "u of t (st. george - university college)": "University of Toronto",
    "uoft st-george trinity college": "University of Toronto",
    "uoft st. george victoria college": "University of Toronto",
    "university of toronto (st. george)": "University of Toronto",
    "uoft st. george": "University of Toronto",
    # UofT faculty names → University of Toronto
    "rotman": "University of Toronto",
    "rotman commerce": "University of Toronto",
    "innis": "University of Toronto",
    "victoria college uoft": "University of Toronto",
    "trinity college uoft": "University of Toronto",
    "engsci": "University of Toronto",
    "uoft engsci": "University of Toronto",

    # UofT Mississauga
    "utm": "University of Toronto Mississauga",
    "ut mississauga": "University of Toronto Mississauga",
    "university of toronto mississauga": "University of Toronto Mississauga",
    "university of toronto (mississauga)": "University of Toronto Mississauga",

    # UofT Scarborough
    "utsc": "University of Toronto Scarborough",
    "uoft sc": "University of Toronto Scarborough",
    "uoft scarborough": "University of Toronto Scarborough",
    "u of t (scarborough)": "University of Toronto Scarborough",

    # -------------------------
    # Western University
    # -------------------------
    "uwo": "Western University",
    "western": "Western University",
    "western ": "Western University",
    "western university": "Western University",
    "university of western ontario": "Western University",
    # Western faculty names
    "ivey": "Western University",
    "ivey aeo": "Western University",
    "ivey business school": "Western University",
    "huron university": "Western University",
    "huron university (western)": "Western University",
    "western huron": "Western University",
    "kings university college": "Western University",

    # -------------------------
    # Queen's University
    # -------------------------
    "queens": "Queen's University",
    "queen's": "Queen's University",
    "queens university": "Queen's University",
    "queen\u2019s": "Queen's University",
    "queens smith engineering": "Queen's University",
    # Queen's faculty names
    "smith": "Queen's University",
    "smith school of business": "Queen's University",
    "queens smith": "Queen's University",

    # -------------------------
    # University of Waterloo
    # -------------------------
    "waterloo": "University of Waterloo",
    "university of waterloo": "University of Waterloo",
    "uwaterloo": "University of Waterloo",
    "uw": "University of Waterloo",
    "uw cs": "University of Waterloo",
    "waterloo university": "University of Waterloo",

    # -------------------------
    # McGill University
    # -------------------------
    "mcgill": "McGill University",
    "mcgill university": "McGill University",
    # McGill faculty names
    "desautels": "McGill University",
    "desautels faculty of management": "McGill University",
    "macdonald university": "McGill University",
    "macdonald": "McGill University",

    # -------------------------
    # McMaster University
    # -------------------------
    "mcmaster": "McMaster University",
    "mcmaster university": "McMaster University",
    "mcmaster univeristy": "McMaster University",
    # McMaster faculty names
    "degroote": "McMaster University",
    "degroote school of business": "McMaster University",

    # -------------------------
    # York University
    # -------------------------
    "york": "York University",
    "york university": "York University",
    # York faculty names
    "schulich": "York University",
    "schulich school of business": "York University",
    "lassonde": "York University",
    "lassonde school of engineering": "York University",
    "glendon": "York University",

    # -------------------------
    # Toronto Metropolitan University
    # -------------------------
    "tmu": "Toronto Metropolitan University",
    "toronto metropolitan university": "Toronto Metropolitan University",
    "ryerson": "Toronto Metropolitan University",

    # -------------------------
    # University of Ottawa
    # -------------------------
    "uottawa": "University of Ottawa",
    "university of ottawa": "University of Ottawa",
    "ottawa u": "University of Ottawa",
    "u of ottawa": "University of Ottawa",

    # -------------------------
    # Carleton University
    # -------------------------
    "carleton": "Carleton University",
    "carleton university": "Carleton University",
    # Carleton faculty names
    "sprott": "Carleton University",
    "sprott school of business": "Carleton University",

    # -------------------------
    # University of Calgary
    # -------------------------
    "ucalgary": "University of Calgary",
    "university of calgary": "University of Calgary",
    "university of calgary ": "University of Calgary",
    "uofc": "University of Calgary",
    "uofc ": "University of Calgary",
    # Calgary faculty names
    "haskayne": "University of Calgary",
    "haskayne school of business": "University of Calgary",

    # -------------------------
    # University of Saskatchewan
    # -------------------------
    "usask": "University of Saskatchewan",
    "university of saskatchewan": "University of Saskatchewan",

    # -------------------------
    # Wilfrid Laurier University
    # -------------------------
    "laurier": "Wilfrid Laurier University",
    "wilfrid laurier university": "Wilfrid Laurier University",
    "wilfred laurier university": "Wilfrid Laurier University",
    "laurier health sci": "Wilfrid Laurier University",
    # Laurier faculty names
    "lazaridis": "Wilfrid Laurier University",
    "lazaridis school of business": "Wilfrid Laurier University",

    # -------------------------
    # University of Guelph
    # -------------------------
    "guelph": "University of Guelph",
    "university of guelph": "University of Guelph",

    # -------------------------
    # Ontario Tech University
    # -------------------------
    "ontario tech": "Ontario Tech University",
    "ontario tech university": "Ontario Tech University",
    "otech": "Ontario Tech University",

    # -------------------------
    # MacEwan University
    # -------------------------
    "macewan": "MacEwan University",
    "macewan university": "MacEwan University",

    # -------------------------
    # Vancouver Island University
    # -------------------------
    "viu": "Vancouver Island University",
    "viu, nanaimo": "Vancouver Island University",

    # -------------------------
    # BCIT
    # -------------------------
    "bcit": "BCIT",
    "bcit - burnaby": "BCIT",

    # -------------------------
    # Nipissing University
    # -------------------------
    "nipissing university": "Nipissing University",
    "nipissing": "Nipissing University",

    # -------------------------
    # Bow Valley College
    # -------------------------
    "bow valley college": "Bow Valley College",
    "bow valley": "Bow Valley College",

    # -------------------------
    # Kwantlen Polytechnic University
    # -------------------------
    "kpu": "Kwantlen Polytechnic University",
    "kwantlen": "Kwantlen Polytechnic University",

    # -------------------------
    # Capilano University
    # -------------------------
    "capilano university": "Capilano University",
    "capilano": "Capilano University",

    # -------------------------
    # Dalhousie University
    # -------------------------
    "dal": "Dalhousie University",
    "dalhousie": "Dalhousie University",
    "dalhousie university": "Dalhousie University",

    # -------------------------
    # University of Manitoba
    # -------------------------
    "umanitoba": "University of Manitoba",
    "university of manitoba": "University of Manitoba",
    "manitoba": "University of Manitoba",

    # -------------------------
    # University of New Brunswick
    # -------------------------
    "unb": "University of New Brunswick",
    "university of new brunswick": "University of New Brunswick",

    # -------------------------
    # Concordia University
    # -------------------------
    "concordia": "Concordia University",
    "concordia university": "Concordia University",
    "john molson": "Concordia University",
    "john molson school of business": "Concordia University",

    # -------------------------
    # University of Regina
    # -------------------------
    "uregina": "University of Regina",
    "university of regina": "University of Regina",
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
    if pd.isna(raw) or str(raw).strip() == "":
        return None, False

    raw = str(raw).strip()

    # Detect multiple schools — commas, slashes, or 3+ uppercase words
    separators = [",", "/"]
    is_multi = any(sep in raw for sep in separators)

    # Also detect space-separated multi-school entries like "UBC SFU UVic"
    # Heuristic: if there are 2+ known school abbreviations in the string
    known_abbreviations = ["ubc", "sfu", "uvic", "uoft", "mcmaster", "queens", "western", "waterloo", "alberta"]
    text_lower = raw.lower()
    abbreviation_matches = sum(1 for abbr in known_abbreviations if abbr in text_lower)
    if abbreviation_matches >= 2:
        is_multi = True

    # Extract first school — split on comma, slash, space, or parenthesis
    import re
    first = re.split(r'[,/(]', raw)[0].strip()

    normalized = SCHOOL_LOOKUP.get(first.lower())

    # If first token didn't match, try just the first word
    if normalized is None:
        first_word = first.split()[0].strip().lower()
        normalized = SCHOOL_LOOKUP.get(first_word)

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

domestic_pr_terms = {"canadian pr", "pr", "permanent resident"}

def normalize_citizenship(raw) -> str | None:

    if pd.isna(raw) or str(raw).strip().upper() in ("N/A", "NA", ""):
        return None

    raw_stripped = str(raw).strip().lower()

    # Exact match for short abbreviations and PR terms
    canadian_terms = {"canada", "canadian", "can", "ca"}
    pr_terms = {"canadian pr", "pr", "permanent resident"}

    if raw_stripped in pr_terms:
        return "DOMESTIC"
    if "canada" in raw_stripped or "canadian" in raw_stripped:
        return "DOMESTIC"
    if raw_stripped in canadian_terms:
        return "DOMESTIC"
    # Dual citizenship with Canada — domestic
    if "canada" in raw_stripped and "/" in raw_stripped:
        return "DOMESTIC"

    return "INTERNATIONAL"

def normalize_row(row: pd.Series) -> dict:
    school_normalized, multi_school_flag = normalize_school(row.get("School "))

    grade_11 = parse_average(row.get("Grade 11 average"))
    grade_12 = parse_average(row.get("General grade 12 average"))
    core = parse_average(row.get("Core average"))

    # Impute core_avg if missing but other grades exist
    if core is None:
        available = [g for g in [grade_11, grade_12] if g is not None]
        if available:
            core = round(sum(available) / len(available), 2)

    return {
        "source": row.get("source"),
        "pulled_at": row.get("pulled_at"),
        "school_raw": row.get("School "),
        "school_normalized": school_normalized,
        "multi_school_flag": multi_school_flag,
        "program_raw": row.get("Major/degree"),
        "decision": normalize_decision(row.get("Final status")),
        "grade_11_avg": grade_11,
        "grade_12_avg": grade_12,
        "core_avg": core,
        "ec_raw": row.get("Extracurriculars/notable essay/interview topics"),
        "circumstances_raw": row.get("Special circumstances"),
        "province": normalize_province(row.get("Province of residence")),
        "citizenship": normalize_citizenship(row.get("Country of citizenship")),
        "scholarship": row.get("Scholarship?"),
        "comments_raw": row.get("Additional comments?"),
    }


BC_FETCHED_PATH = Path("data/processed/bc_fetched.csv")
BC_2025_FETCHED_PATH = Path("data/processed/bc_2025_fetched.csv")
BC_CLEANED_PATH = Path("data/cleaned/bc_cleaned.csv")


def run():
    """
    Reads all fetched CSVs, normalizes every row, saves to bc_cleaned.csv.
    """
    dfs = []

    if BC_FETCHED_PATH.exists():
        print("Reading bc_fetched.csv...")
        dfs.append(pd.read_csv(BC_FETCHED_PATH))

    if BC_2025_FETCHED_PATH.exists():
        print("Reading bc_2025_fetched.csv...")
        dfs.append(pd.read_csv(BC_2025_FETCHED_PATH))

    if not dfs:
        print("No fetched files found. Run fetch_sheets.py first.")
        return

    df = pd.concat(dfs, ignore_index=True)
    print(f"  {len(df)} total rows to normalize")

    normalized_rows = [normalize_row(row) for _, row in df.iterrows()]
    cleaned_df = pd.DataFrame(normalized_rows)

    BC_CLEANED_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_csv(BC_CLEANED_PATH, index=False)
    print(f"  Saved to {BC_CLEANED_PATH}")

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
    