# main.py

import sys
from pipeline import fetch_sheets, normalize, extract_fields, load_to_db


def run_pipeline():
    print("=" * 50)
    print("UniPath AI — Data Pipeline")
    print("=" * 50)

    print("\n[1/4] Fetching sheets...")
    fetch_sheets.run()

    print("\n[2/4] Normalizing data...")
    normalize.run()

    print("\n[3/4] Extracting fields...")
    extract_fields.run()

    print("\n[4/4] Loading to database...")
    load_to_db.run()

    print("\n" + "=" * 50)
    print("Pipeline complete.")
    print("=" * 50)


if __name__ == "__main__":
    run_pipeline()