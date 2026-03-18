import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

BC_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1x4YqRM344w_occH1OVuyci47V2ZY4Uz0NE4S6Ui70lQ"
    "/export?format=csv&gid=1140327995"
)

# TODO: Replace with URL once export permission is granted
ONTARIO_RAW_PATH = Path("data/raw/ontario_raw.csv")

BC_OUTPUT_PATH = Path("data/processed/bc_fetched.csv")
ONTARIO_OUTPUT_PATH = Path("data/processed/ontario_fetched.csv")

BC_APPLICANT_TYPE_COL = "Which of the following options best describes you?"
BC_FIRST_YEAR_VALUE = "First year applicant"

BC_2025_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1RjkjiNevP1iMNLaJim1xxTiBoMqP4xGPqHulXpBP8Xc"
    "/export?format=csv&gid=992616934"
)

BC_2025_OUTPUT_PATH = Path("data/processed/bc_2025_fetched.csv")

# Maps 2025 column names to canonical 2026 column names
BC_2025_COLUMN_MAP = {
    "School (Submit multiple responses if more than one, if UBC specify UBCV or UBCO)": "School ",
    "Major/degree?": "Major/degree",
    "Final Status": "Final status",
    "Grade 11 Average ": "Grade 11 average",
    "Grade 12 General Average ": "General grade 12 average",
    "Core Average": "Core average",
    "Extracurriculars/notable essay/interview topics": "Extracurriculars/notable essay/interview topics",
    "Special circumstances": "Special circumstances",
    "Country of citizenship": "Country of citizenship",
    "Country of residence": "Country of residence",
    "Province of residence": "Province of residence",
    "Additional comments?": "Additional comments?",
    "Scholarship $$": "Scholarship?",
}


def fetch_bc_2025() -> pd.DataFrame:
    """
    Fetches the 2025 BC sheet via public CSV export URL.
    Renames columns to match the 2026 canonical schema.
    Adds source and pulled_at columns.
    Saves to data/processed/bc_2025_fetched.csv.
    Returns DataFrame.
    """
    print("Fetching BC 2025 sheet from URL...")
    df = pd.read_csv(BC_2025_URL)

    total_rows = len(df)

    # Rename columns to canonical schema
    df = df.rename(columns=BC_2025_COLUMN_MAP)

    # Keep only columns that exist in the canonical schema
    canonical_cols = list(BC_2025_COLUMN_MAP.values())
    df = df[[c for c in canonical_cols if c in df.columns]]

    print(f"  BC 2025: {total_rows} rows")

    df["source"] = "BC_2025"
    df["pulled_at"] = datetime.now(timezone.utc).isoformat()

    BC_2025_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(BC_2025_OUTPUT_PATH, index=False)
    print(f"  Saved to {BC_2025_OUTPUT_PATH}")

    return df

def fetch_bc() -> pd.DataFrame:
    """
    Fetches BC sheet via public CSV export URL.
    Filters to first-year applicants only.
    Adds source and pulled_at columns.
    Saves to data/processed/bc_fetched.csv.
    Returns filtered DataFrame.
    """
    print("Fetching BC sheet from URL...")
    df = pd.read_csv(BC_URL)

    total_rows = len(df)
    df = df[df[BC_APPLICANT_TYPE_COL] == BC_FIRST_YEAR_VALUE].copy()
    filtered_rows = len(df)

    print(f"  BC: {total_rows} total rows -> {filtered_rows} first year applicants")

    df["source"] = "BC"
    df["pulled_at"] = datetime.now(timezone.utc).isoformat()

    BC_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(BC_OUTPUT_PATH, index=False)
    print(f"  Saved to {BC_OUTPUT_PATH}")

    return df


def fetch_ontario() -> pd.DataFrame:
    """
    Reads Ontario CSV from data/raw/ontario_raw.csv (manually placed).
    Adds source and pulled_at columns.
    Saves to data/processed/ontario_fetched.csv.
    Returns DataFrame.

    TODO: Replace file read with URL fetch once export permission is granted.
    Swap this line:
        df = pd.read_csv(ONTARIO_RAW_PATH)
    For this:
        df = pd.read_csv(ONTARIO_URL)
    """
    if not ONTARIO_RAW_PATH.exists() or ONTARIO_RAW_PATH.stat().st_size == 0:
        raise FileNotFoundError(
            f"Ontario raw file not found at {ONTARIO_RAW_PATH}. "
            "Download the sheet manually and place it there."
        )

    print("Reading Ontario sheet from local file...")
    df = pd.read_csv(ONTARIO_RAW_PATH)

    print(f"  Ontario: {len(df)} rows")

    df["source"] = "Ontario"
    df["pulled_at"] = datetime.now(timezone.utc).isoformat()

    ONTARIO_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ONTARIO_OUTPUT_PATH, index=False)
    print(f"  Saved to {ONTARIO_OUTPUT_PATH}")

    return df


def run() -> dict[str, pd.DataFrame]:
    """
    Runs all fetch functions. Returns dict with source keys.
    Ontario fetch is skipped gracefully if the raw file is not present.
    """
    results = {}

    results["bc"] = fetch_bc()
    results["bc_2025"] = fetch_bc_2025()

    try:
        results["ontario"] = fetch_ontario()
    except FileNotFoundError as e:
        print(f"  Skipping Ontario: {e}")

    print("\nFetch complete.")
    for source, df in results.items():
        print(f"  {source.upper()}: {len(df)} rows, {len(df.columns)} columns")

    return results


if __name__ == "__main__":
    run()

