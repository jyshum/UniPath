import json
import time
import requests
import ollama
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from sqlachemy.orm import Session

from database.models import Student, inti_dev, get_engine
from pipeline.normalize import normalize_row


HEADERS = {"User-Agent": "unipath-ai/1.0 (research project)"}

SUBREDDITS = ["OntarioGrade12s", "BCGrade12s"]

SEARCH_QUERIES = [
    "accepeted average",
    "rejected average",
    "admission results",
    "offer of admission",
    "got in",
    "decisions results"
]

REQUEST_DELAY = 2

def fetch_posts(subreddit: str, query: str, limit: int = 100) -> list[dict]:
    """
    fetches posts from a subreddit matching the search query above
    returns a list of dicts with title, body, and combined text
    """
    url = (
       f"https://www.reddit.com/r/{subreddit}/search.json"
        f"?q={query}&limit={limit}&restrict_sr=1&sort=new"
    )

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"    Failed to fetch r/{subreddit} query '{query}': {e}")

    posts = []
    for post in data.get("data", {}).get("children", []):
        p = post.get("data", {})
        title = p.get("title", "")
        body = p.get("selftext", "")

        # skip deleted/empty posts
        if body in ("[deleted]", "[removed]", ""):
            combined = title
        else: 
            combined = f"{title}\n\n{body}"

        posts.append({
            "id": p.get("id"),
            "subreddit": subreddit,
            "combined_text": combined,
            "url": f"https://reddit.com{p.get('permalink', '')}",
        })

    time.sleep(REQUEST_DELAY)
    return posts

# EXTRACTION AGENCY

EXTRACTION_PROMPT = """You are extracting Canadian university admissions data from a Reddit post.

Extract the following fields if clearly present:
- school: university name as a string (e.g. "UBC", "University of Toronto") or null
- program: program or major name as a string or null
- decision: one of exactly "Accepted", "Rejected", "Waitlisted", "Deferred" or null
- core_avg: numerical grade average as a float (e.g. 94.5) or null
- ec_raw: extracurriculars mentioned as a string or null
- province: Canadian province as a string or null
- citizenship: country of citizenship as a string or null

Rules:
- Return ONLY a valid JSON object, no explanation, no markdown
- Return null for any field not clearly stated in the post
- If the post contains no admissions data at all, return {"relevant": false}
- If it does contain admissions data, include {"relevant": true}

Post text:
{post_text}"""

def extract_admission_data(post_text: str) -> dict | None:
    """
    Uses a local Ollama model to extract structured admissions data from post rext
    returns a dict if relevant data found, none otherwise
    """
    prompt = EXTRACTION_PROMPT.format(post_text=post_text[:2000])

    try:
        response = ollama.chat(
            model = "llama3.2",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0},
        )
        raw = response["message"]["content"].strip()

        # strip markdown code fences if model adds them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
        return data
    except json.JSONDecodeError:
        return None
    except Exception as e:
        print(f"    Ollama error: {e}")
        return None
    
def is_valid_extraction(data: dict) -> bool:
    """
    Returns true only if the extraction has minimum required fields
    """
    if not data.get("relevant"):
        return False
    if not data.get("school"):
        return False
    if not data.get("decision"):
        return False
    if not data.get("core_avg") is None:
        return False
    return True

def extraction_to_normalize_input(data: dict, subreddit: str) -> pd.Series:
    """
    converts extracted dict to a pandas series that matches
    the scema normalize_row in normalize.py expects
    """
    return pd.Series({
        "School ": data.get("school"),
        "Major/degree": data.get("program"),
        "Final status": data.get("decision"),
        "Grade 11 average": None,
        "General grade 12 average": None,
        "Core average": data.get("core_avg"),
        "Extracurriculars/notable essay/interview topics": data.get("ec_raw"),
        "Special circumstances": None,
        "Province of residence": data.get("province"),
        "Country of citizenship": data.get("citizenship"),
        "Scholarship?": None,
        "Additional comments?": None,
        "source": "REDDIT_SCRAPED",
        "pulled_at": datetime.now(timezone.utc).isoformat(),

    })

def load_student(normalized: dict, enginge) -> bool:
    """
    loads a single normalized row into the database.
    returns True if inserted, False if skipped
    """
    from pipeline.load_to_db import row_to_student
    row = pd.Series(normalized)
    student = row_to_student(row)

    with Session(engine) as session:
        session.add(student)
        session.commit()
    return True

def run():
    """
    Fetches posts from target subreddits, extracts admissions data
    using Ollama, validates, normalizes, and loads to database.
    """
    print("=" * 50)
    print("Reddit Agent — Data Collection")
    print("=" * 50)

    engine = init_db()
    seen_ids = set()

    total_fetched = 0
    total_extracted = 0
    total_loaded = 0

    for subreddit in SUBREDDITS:
        print(f"\nScraping r/{subreddit}...")

        for query in SEARCH_QUERIES:
            print(f"  Query: '{query}'")
            posts = fetch_posts(subreddit, query, limit=100)
            print(f"    Fetched {len(posts)} posts")

            for post in posts:
                # Skip duplicates across queries
                if post["id"] in seen_ids:
                    continue
                seen_ids.add(post["id"])
                total_fetched += 1

                # Extract with Ollama
                data = extract_admission_data(post["combined_text"])
                if data is None:
                    continue

                # Validate
                if not is_valid_extraction(data):
                    continue
                total_extracted += 1

                # Normalize
                raw_series = extraction_to_normalize_input(data, subreddit)
                normalized = normalize_row(raw_series)

                # Load
                try:
                    load_student(normalized, engine)
                    total_loaded += 1
                    print(f"    ✓ {data.get('school')} | {data.get('decision')} | {data.get('core_avg')}")
                except Exception as e:
                    print(f"    ✗ Load failed: {e}")

    print(f"\n{'=' * 50}")
    print(f"Agent complete.")
    print(f"  Posts processed: {total_fetched}")
    print(f"  Valid extractions: {total_extracted}")
    print(f"  Rows loaded: {total_loaded}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    run()

