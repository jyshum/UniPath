import json
import time
import requests
import ollama
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session

from database.models import Student, init_db, get_engine
from pipeline.normalize import normalize_row


HEADERS = {"User-Agent": "unipath-ai/1.0 (research project)"}

SUBREDDITS = ["OntarioGrade12s", "BCGrade12s"]

SEARCH_QUERIES = [

    # Engineering
    "accepted engineering",
    "rejected engineering",
    "engineering admission",
    "applied science accepted",
    "got into engineering",
    "engineering offer",
    "ECE accepted",
    "software engineering accepted",
    "mechanical engineering accepted",
    "chemical engineering accepted",

    # Computer Science
    "accepted computer science",
    "rejected computer science",
    "CS accepted",
    "CompSci accepted",
    "got into CS",
    "computer science offer",
    "CS rejection",
    "math CS accepted",

    # Business / Commerce
    "accepted commerce",
    "Sauder accepted",
    "Ivey accepted",
    "Schulich accepted",
    "Beedie accepted",
    "Rotman accepted",
    "HBA accepted",
    "BBA accepted",
    "got into business",
    "commerce rejection",
    "Ivey AEO",

    # Science
    "accepted science",
    "life sciences accepted",
    "health sciences accepted",
    "rejected science",
    "got into science",
    "biomed accepted",
    "biochemistry accepted",
    "kinesiology accepted",

    # Health
    "nursing accepted",
    "pharmacy accepted",
    "health sci accepted",
    "McMaster health sci",
    "rejected health sciences",
    "physiotherapy accepted",

    # Arts / Humanities
    "accepted arts",
    "social sciences accepted",
    "got into arts",
    "rejected arts",
    "psychology accepted",

    # School-specific program combos
    "UBC science accepted",
    "UBC engineering accepted",
    "UBC Sauder accepted",
    "Waterloo CS accepted",
    "Waterloo math accepted",
    "Waterloo engineering accepted",
    "McMaster life sci accepted",
    "McMaster health sci accepted",
    "UofT engineering accepted",
    "UofT life sci accepted",
    "Queens engineering accepted",
    "Western Ivey accepted",
]

VALID_DECISIONS = {"Accepted", "Rejected", "Waitlisted", "Deferred"}

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
        return []

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
- school: university name as a string (e.g. "UBC", "University of Toronto") or null.
  If a faculty name implies a school (e.g. "Ivey" → "Western University", "Sauder" → "UBC"), extract both.
- program: program or major name as a string or null.
  You may infer program ONLY from faculty or program names explicitly present in the post:
  "Sauder" or "UBC Sauder" → "Commerce",
  "Ivey" or "Ivey AEO" → "Business Administration",
  "Schulich" → "Business",
  "Beedie" → "Business",
  "Rotman" → "Commerce",
  "Engineering" or "Applied Science" or "APSC" → "Engineering",
  "Health Sci" or "Health Sciences" → "Health Sciences",
  "Life Sci" or "Life Sciences" → "Life Sciences",
  "CompSci" or "CS" or "Computer Science" → "Computer Science",
  "Nursing" → "Nursing",
  "Pharmacy" → "Pharmacy",
  "Kinesiology" or "Kin" → "Kinesiology",
  "Biomed" or "Biomedical" → "Biomedical Sciences",
  "Biochemistry" → "Biochemistry",
  "Psychology" or "Psych" → "Psychology",
  "Math" or "Mathematics" → "Mathematics",
  "Physics" → "Physics",
  "Economics" or "Econ" → "Economics",
  "Architecture" → "Architecture",
  "Education" → "Education",
  "Law" → "Law",
  "Arts" or "Humanities" → "Arts",
  "Science" → "Science",
  "Social Science" → "Social Sciences"
  IMPORTANT: Only extract program if a program or faculty name is explicitly present in the post text.
  Do NOT guess program from school name alone (e.g. "UBC" alone is not enough to extract a program).
  Do NOT infer program from the search query or surrounding context.
  If no program is mentioned, return null.
- decision: one of exactly "Accepted", "Rejected", "Waitlisted", "Deferred" or null.
  Do NOT extract decisions like "Expired", "Pending", "Conditional" — return null for these.
- core_avg: the student's overall grade average as a float (e.g. 94.5) or null.
  Do NOT extract IB total scores (e.g. 38/45) as a percentage — convert them: score/45*100.
  If multiple averages are mentioned, extract the core or overall average, not subject-specific grades.
  If the average is a percentage string like "94%", extract 94.0.
- ec_raw: extracurriculars, clubs, sports, volunteering, or notable achievements as a string or null.
  Only extract if explicitly mentioned. Do not fabricate.
- province: Canadian province of the student as a string or null.
  Only extract if explicitly stated. Do not infer from school location.
- citizenship: country of citizenship as a string or null.
  Only extract if explicitly stated.

Rules:
- Return ONLY a valid JSON object, no explanation, no markdown, no code fences
- Return null for any field not clearly stated in the post
- If the post contains no admissions data at all, return {{"relevant": false}}
- If it does contain admissions data, include {{"relevant": true}}
- A post is only relevant if it contains at minimum: a school, a decision, and a grade average
- Do NOT extract data from hypothetical or question-based posts (e.g. "what are my chances?")
- Do NOT extract data from posts asking for advice, only from posts reporting actual outcomes

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
    if not data.get("relevant"):
        return False
    if isinstance(data.get("school"), list):
        return False
    if isinstance(data.get("decision"), list):
        return False
    if isinstance(data.get("core_avg"), list):
        return False
    if not data.get("school"):
        return False
    if data.get("decision") not in VALID_DECISIONS:
        return False
    if data.get("core_avg") is None:
        return False
    if not data.get("program"):
        return False
    return True

def extraction_to_normalize_input(data: dict, subreddit: str) -> pd.Series:
    def safe_str(val):
        if val is None:
            return None
        if isinstance(val, list):
            return val[0] if val else None
        return str(val)

    def safe_float(val):
        try:
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    return pd.Series({
        "School ": safe_str(data.get("school")),
        "Major/degree": safe_str(data.get("program")),
        "Final status": safe_str(data.get("decision")),
        "Grade 11 average": None,
        "General grade 12 average": None,
        "Core average": safe_float(data.get("core_avg")),
        "Extracurriculars/notable essay/interview topics": safe_str(data.get("ec_raw")),
        "Special circumstances": None,
        "Province of residence": safe_str(data.get("province")),
        "Country of citizenship": safe_str(data.get("citizenship")),
        "Scholarship?": None,
        "Additional comments?": None,
        "source": "REDDIT_SCRAPED",
        "pulled_at": datetime.now(timezone.utc).isoformat(),
    })

def load_student(normalized: dict, engine) -> bool:
    from pipeline.load_to_db import row_to_student
    row = pd.Series(normalized)
    student = row_to_student(row)

    with Session(engine) as session:
        # Check for duplicate before inserting
        existing = session.query(Student).filter(
            Student.source == "REDDIT_SCRAPED",
            Student.school_normalized == student.school_normalized,
            Student.decision == student.decision,
            Student.core_avg == student.core_avg,
        ).first()

        if existing:
            return False

        session.add(student)
        session.commit()
    return True

PROGRESS_FILE = Path(__file__).parent.parent / "data" / "reddit_agent_progress.txt"

def load_progress() -> set:
    if not PROGRESS_FILE.exists():
        return set()
    return set(PROGRESS_FILE.read_text().strip().splitlines())


def save_progress(key: str):
    try:
        PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PROGRESS_FILE, "a") as f:
            f.write(key + "\n")
        print(f"    [progress saved: {key}]")
    except Exception as e:
        print(f"    [progress save failed: {e}]")

def run():
    """
    Fetches posts from target subreddits, extracts admissions data
    using Ollama, validates, normalizes, and loads to database.
    Resumes from last completed query if interrupted.
    """
    print("=" * 50)
    print("Reddit Agent — Data Collection")
    print("=" * 50)

    engine = init_db()
    seen_ids = set()
    completed = load_progress()

    total_fetched = 0
    total_extracted = 0
    total_loaded = 0

    for subreddit in SUBREDDITS:
        print(f"\nScraping r/{subreddit}...")

        for query in SEARCH_QUERIES:
            key = f"{subreddit}::{query}"

            if key in completed:
                print(f"  Skipping '{query}' (already done)")
                continue

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
                    print(f"    ✓ {data.get('school')} | {data.get('program')} | {data.get('decision')} | {data.get('core_avg')}")
                except Exception as e:
                    print(f"    ✗ Load failed: {e}")

            # Mark query as complete after all posts processed
            save_progress(key)

    print(f"\n{'=' * 50}")
    print(f"Agent complete.")
    print(f"  Posts processed: {total_fetched}")
    print(f"  Valid extractions: {total_extracted}")
    print(f"  Rows loaded: {total_loaded}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    run()

