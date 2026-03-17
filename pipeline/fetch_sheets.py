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
    Runs both fetch functions. Returns dict with 'bc' and 'ontario' keys.
    Ontario fetch is skipped gracefully if the raw file is not present.
    """
    results = {}

    results["bc"] = fetch_bc()

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

