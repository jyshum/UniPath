import re
import pandas as pd
from pathlib import Path

BC_CLEANED_PATH = Path("data/cleaned/bc_cleaned.csv")
BC_EXTRACTED_PATH = Path("data/cleaned/bc_extracted.csv")

EMPTY_RESPONSES = {
    "na", "n/a", "none", "none required", "not needed", "not applicable",
    "no", "nope", "nil", "grades only", "grades", "/", "-", ".",
    "sfu doesnt care bout ecs", "wasn't asked", "not taken into consideration",
    "nothing",
}

def is_empty_response(text) -> bool:
    # Returns True if the text is noise.
    if pd.isna(text):
        return True
    cleaned = str(text).strip().lower()
    if cleaned == "":
        return True
    if cleaned in EMPTY_RESPONSES:
        return True
    # Catch "NA for X", "not needed for Y" patterns
    if re.match(r"^(na|n/a|none|not needed|not requxired)\s+for\s+", cleaned):
        return True
    return False

def tag_ec(raw) -> list[str]:
    """
    Tags extracurricular activities from raw text.
    Returns a list of tags from:
    SPORTS, ARTS, LEADERSHIP, COMMUNITY_SERVICE, WORK_EXPERIENCE,
    ACADEMIC_COMPETITION, RESEARCH, ENTREPRENEURSHIP, OTHER
    Returns ["NONE"] if empty response.
    """
    if is_empty_response(raw):
        return ["NONE"]

    text = str(raw).lower()
    tags = []

    # SPORTS — specific enough to fire on single keywords
    sport_keywords = [
        "basketball", "volleyball", "soccer", "hockey", "tennis", "swimming",
        "track", "rugby", "baseball", "badminton", "golf", "skiing", "rowing",
        "football", "lacrosse", "athlete", "varsity", "sport", "sailing",
        "gymnastics", "taekwondo", "kickboxing", "waterpolo", "cross country",
        "dance", "ballet", "dragon boat",
    ]
    if any(kw in text for kw in sport_keywords):
        tags.append("SPORTS")

    # ARTS — specific enough to fire on single keywords
    arts_keywords = [
        "piano", "violin", "guitar", "music", "band", "orchestra", "choir",
        "theatre", "theater", "drama", "art", "drawing", "painting",
        "rcm", "instrument", "musical", "oboe", "percussion", "bagpip",
        "jazz", "ensemble", "wind ensemble", "crochet", "pottery",
    ]
    if any(kw in text for kw in arts_keywords):
        tags.append("ARTS")

    # LEADERSHIP — president/founder fire alone; head/exec need more context
    leadership_strong = [
        "president", "founder", "co-founder", "vice president", "vp",
        "captain", "director", "chair", "student council", "school council",
    ]
    leadership_weak = ["executive", "leader", "head", "manager"]
    if any(kw in text for kw in leadership_strong):
        tags.append("LEADERSHIP")
    elif any(kw in text for kw in leadership_weak):
        # Only tag if there's a second weak signal too
        if sum(1 for kw in leadership_weak if kw in text) >= 2:
            tags.append("LEADERSHIP")

    # COMMUNITY_SERVICE — "volunteer" alone is enough; "community" needs support
    if "volunteer" in text or "volunteering" in text:
        tags.append("COMMUNITY_SERVICE")
    elif "community" in text and any(kw in text for kw in ["service", "outreach", "hospital", "food bank", "charity", "nonprofit", "tutoring"]):
        tags.append("COMMUNITY_SERVICE")

    # WORK_EXPERIENCE
    work_keywords = [
    "part-time", "part time", "cashier", "intern", "internship",
    "employed", "wages", "salary", "dishwash", "detailer", "waitress",
    "working at", "full-time", "full time",
    ]
    # "job" and "work" checked separately to avoid matching "volunteer work"
    if any(kw in text for kw in work_keywords):
        tags.append("WORK_EXPERIENCE")
    elif "job" in text and "volunteer" not in text:
        tags.append("WORK_EXPERIENCE")
    elif re.search(r'\bwork\b', text) and "volunteer" not in text and "coursework" not in text:
        tags.append("WORK_EXPERIENCE")

    # ACADEMIC_COMPETITION — specific enough
    comp_keywords = [
        "competition", "olympiad", "contest", "deca", "debate", "model un",
        "hackathon", "case comp", "math competition", "science fair", "award",
        "mun", "skills canada", "skillscanada",
    ]
    if any(kw in text for kw in comp_keywords):
        tags.append("ACADEMIC_COMPETITION")

    # RESEARCH — specific enough
    research_keywords = [
        "research", "lab", "professor", "experiment", "publication",
        "thesis", "laboratory",
    ]
    if any(kw in text for kw in research_keywords):
        tags.append("RESEARCH")

    # ENTREPRENEURSHIP — specific enough
    entrepreneurship_keywords = [
        "startup", "entrepreneur", "founded", "app", "company",
        "venture", "nonprofit", "non-profit", "npo", "business",
    ]
    if any(kw in text for kw in entrepreneurship_keywords):
        tags.append("ENTREPRENEURSHIP")

    if not tags:
        tags.append("OTHER")

    return tags

def tag_circumstances(raw) -> list[str]:
    """
    Tags special circumstances from raw text.
    Returns a list of tags from:
    INTERNATIONAL, INDIGENOUS, IB_STUDENT, FINANCIAL_HARDSHIP,
    FAMILY_CIRCUMSTANCE, NONE
    Returns ["NONE"] if empty response.
    """
    if is_empty_response(raw):
        return ["NONE"]

    text = str(raw).lower()
    tags = []

    # INDIGENOUS — all specific enough to fire alone
    indigenous_keywords = [
        "indigenous", "first nations", "metis", "métis", "inuit", "aboriginal",
    ]
    if any(kw in text for kw in indigenous_keywords):
        tags.append("INDIGENOUS")

    # IB_STUDENT — "ib" alone is risky, require "international baccalaureate" or "ib" + grade context
    if "international baccalaureate" in text:
        tags.append("IB_STUDENT")
    elif re.search(r"\bib\b", text) and any(kw in text for kw in ["grades", "score", "predicted", "45", "42", "diploma"]):
        tags.append("IB_STUDENT")

    # INTERNATIONAL — specific enough
    international_keywords = [
        "international applicant", "international student", "visa",
        "immigrant", "newcomer", "cuaet", "war refugee", "refugee",
        "ukrainian citizenship", "foreign",
    ]
    if any(kw in text for kw in international_keywords):
        tags.append("INTERNATIONAL")

    # FINANCIAL_HARDSHIP — multi-keyword required for vague ones
    if "financial hardship" in text or "low income" in text:
        tags.append("FINANCIAL_HARDSHIP")
    elif any(kw in text for kw in ["financial", "bursary", "scholarship needed"]):
        if any(kw in text for kw in ["hardship", "need", "support", "afford"]):
            tags.append("FINANCIAL_HARDSHIP")

    # FAMILY_CIRCUMSTANCE — multi-keyword required
    family_anchors = ["mother", "father", "parent", "grandmother", "grandfather", "sibling", "brother", "sister"]
    family_events = ["lost", "passed away", "death", "illness", "medical", "caregiver", "passing"]
    if "passed away" in text:
        tags.append("FAMILY_CIRCUMSTANCE")
    elif any(anchor in text for anchor in family_anchors) and any(event in text for event in family_events):
        tags.append("FAMILY_CIRCUMSTANCE")

    if not tags:
        tags.append("NONE")

    return tags

def tag_program(raw) -> str:
    """
    Maps raw program name to a single category.
    Returns one of: COMPUTER_SCIENCE, ENGINEERING, BUSINESS, SCIENCE,
    ARTS, HEALTH, LAW, EDUCATION, OTHER
    """
    if is_empty_response(raw):
        return "OTHER"

    text = str(raw).lower().strip()

    # HEALTH — check before SCIENCE to avoid biomed/life sci going to SCIENCE
    if any(kw in text for kw in [
        "nursing", "pharmacy", "kinesiology", "kinetics", "physiotherapy",
        "dentistry", "medicine", "medical", "health sci", "health science",
        "health information", "biomed", "biomedical", "ibiomed", "i-biomed",
        "medical radiation", "med rad", "midwifery", "nutrition", "food",
        "pre-med", "radiation science", "biomedical physiology",
    ]):
        return "HEALTH"

    # ENGINEERING — check before SCIENCE to avoid applied science going to SCIENCE
    if any(kw in text for kw in [
        "engineering", "applied science", "apsc", "mechanical", "electrical",
        "civil", "chemical", "bioengineering", "mechatronics", "aerospace",
        "software eng", "soft eng", "comp eng", "mech eng", "engsci",
        "eng sci", "nuclear", "environmental engineering", "architecture",
        "computer engineering", "systems design",
    ]):
        return "ENGINEERING"

    # COMPUTER_SCIENCE — check before SCIENCE
    if any(kw in text for kw in [
        "computer science", "computing", "software", "comp sci", "cs",
        "cyber security", "cybersecurity", "data science", "artificial intelligence",
        "machine learning", "information technology", "computer engineering",
    ]):
        # Exclude false positives
        if "political science" in text or "social science" in text:
            pass
        else:
            return "COMPUTER_SCIENCE"

    # BUSINESS — check before ARTS to avoid economics going to ARTS
    if any(kw in text for kw in [
        "business", "commerce", "bcom", "bba", "accounting", "finance",
        "marketing", "management", "sauder", "suader", "rotman", "ivey",
        "schulich", "beedie", "lazaridis", "economics", "econ",
        "actuarial", "bmos", "bmobs", "afm", "hba",
        "sprott", "desautels", "haskayne", "degroote",
    ]):
        return "BUSINESS"

    # ARTS
    if any(kw in text for kw in [
        "arts", "humanities", "english", "history", "philosophy",
        "political science", "sociology", "geography", "gender",
        "film", "social science", "communication", "journalism",
        "media", "design", "interaction design", "planning",
        "criminology", "anthropology", "linguistics", "psychology",
        "diaspora", "semiotics", "broadcasting",
    ]):
        return "ARTS"

    # SCIENCE — broad catch after all above
    if any(kw in text for kw in [
        "science", "biology", "chemistry", "physics", "math",
        "statistics", "biochemistry", "neuroscience", "life science",
        "bioscience", "molecular", "ecology", "forensic", "anatomy",
        "environmental science", "cell biology", "animal",
        "pharmaceutical science", "bsc", "isci", "general sci",
    ]):
        return "SCIENCE"

    # LAW
    if any(kw in text for kw in ["law", "legal", "jd", "llb"]):
        return "LAW"

    # EDUCATION
    if any(kw in text for kw in ["education", "teaching", "teacher", "bed"]):
        return "EDUCATION"

    return "OTHER"

def extract_row(row: pd.Series) -> dict:
    """Applies all taggers to a single row. Returns dict of extracted fields."""
    return {
        **row.to_dict(),
        "ec_tags": tag_ec(row.get("ec_raw")),
        "circumstance_tags": tag_circumstances(row.get("circumstances_raw")),
        "program_category": tag_program(row.get("program_raw")),
    }


def run():
    """
    Reads bc_cleaned.csv, applies extract_row to every row,
    saves to bc_extracted.csv, prints tag distribution summary.
    """
    print("Reading bc_cleaned.csv...")
    df = pd.read_csv(BC_CLEANED_PATH)
    print(f"  {len(df)} rows to process")

    extracted = [extract_row(row) for _, row in df.iterrows()]
    out_df = pd.DataFrame(extracted)

    # Convert tag lists to pipe-separated strings for CSV storage
    out_df["ec_tags"] = out_df["ec_tags"].apply(lambda x: "|".join(x) if isinstance(x, list) else x)
    out_df["circumstance_tags"] = out_df["circumstance_tags"].apply(lambda x: "|".join(x) if isinstance(x, list) else x)

    BC_EXTRACTED_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(BC_EXTRACTED_PATH, index=False)
    print(f"  Saved to {BC_EXTRACTED_PATH}")

    # Summary
    from collections import Counter
    all_ec_tags = [tag for tags in out_df["ec_tags"].str.split("|") for tag in tags]
    all_circ_tags = [tag for tags in out_df["circumstance_tags"].str.split("|") for tag in tags]

    print("\nEC tag distribution:")
    for tag, count in Counter(all_ec_tags).most_common():
        print(f"  {tag}: {count}")

    print("\nCircumstance tag distribution:")
    for tag, count in Counter(all_circ_tags).most_common():
        print(f"  {tag}: {count}")

    print("\nProgram category distribution:")
    for tag, count in Counter(out_df["program_category"]).most_common():
        print(f"  {tag}: {count}")


if __name__ == "__main__":
    run()
