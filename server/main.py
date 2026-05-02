"""
server/main.py
FastAPI server — production replacement for the subprocess bridge.
Deployed on Railway. Called via HTTP from the Next.js API route on Vercel.
"""
import sys
from pathlib import Path

# Ensure project root is on the path regardless of where uvicorn is invoked from
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Literal, Optional
import json as _json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.calibrate import final_probability, ADMITTED_PROFILES
from core.profile_matcher import get_program_archetypes, match_profiles
from core.profile_taxonomy import extract_activity_signals
from core.recommend import find_similar, program_stats, list_programs
from pipeline.normalize import normalize_school, normalize_decision, normalize_province
from pipeline.program_names import get_program_category, normalize_program_name
from pipeline.extract_fields import tag_program, tag_ec
from database.models import Student, init_db
from sqlalchemy.orm import Session

DB_PATH = str(Path(__file__).parent.parent / "database" / "unipath.db")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class ProbabilityRequest(BaseModel):
    school: str
    program: str
    grade: float
    supplemental_types: list[str] = []
    supplemental_texts: dict[str, str] = {}
    supplemental_completed: dict[str, bool] = {}
    activities: list[str] = []


class ActivityInput(BaseModel):
    category: Optional[str] = None
    activity_type: Optional[str] = None
    role_level: Optional[str] = None


class ProfileMatchRequest(BaseModel):
    school: str
    program: str
    grade_average: Optional[float] = None
    curriculum_type: str = "UNKNOWN"
    activities: list[ActivityInput] = []


class CreateProfileRequest(BaseModel):
    school: str
    program: str
    grade_average: Optional[float] = None
    decision: Optional[Literal["ACCEPTED", "REJECTED", "WAITLISTED", "DEFERRED"]] = None
    province: Optional[str] = None
    curriculum_type: str = "UNKNOWN"
    activities_text: Optional[str] = None


def _profile_db_path() -> str:
    return DB_PATH


def _grade_out_of_range(grade: Optional[float]) -> bool:
    return grade is not None and not (50 <= grade <= 100)


def _public_activity(activity: dict) -> dict:
    return {
        key: value
        for key, value in activity.items()
        if key != "raw_text"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/final-probability")
def get_final_probability(req: ProbabilityRequest):
    program = req.program.upper()

    if (req.school, program) not in ADMITTED_PROFILES:
        return {"error": "no_data"}

    # Format activity list into a single scored block
    supp_texts = dict(req.supplemental_texts)
    if req.activities:
        formatted = "\n".join(
            f"Activity {i + 1}: {act.strip()}"
            for i, act in enumerate(req.activities)
            if act.strip()
        )
        if formatted:
            supp_texts["activity_list"] = formatted

    result = final_probability(
        school=req.school,
        program_category=program,
        grade=req.grade,
        supplemental_types=req.supplemental_types,
        supplemental_texts=supp_texts,
        supplemental_completed=req.supplemental_completed,
    )

    if result is None:
        return {"error": "no_data"}

    # Similar students: ACCEPTED only, fixed ±5 window
    df, _ = find_similar(
        req.grade, program, school=req.school,
        tolerance=5.0, min_results=10, max_tolerance=5.0,
    )
    accepted = df[df["decision"] == "ACCEPTED"]
    if len(accepted) >= 1:
        result["similar_students"] = {
            "count":     int(len(accepted)),
            "avg_grade": round(float(accepted["core_avg"].mean()), 1),
            "min_grade": round(float(accepted["core_avg"].min()), 1),
            "max_grade": round(float(accepted["core_avg"].max()), 1),
        }
    else:
        result["similar_students"] = None

    return result


@app.get("/programs")
def get_programs(category: str = None):
    return list_programs(min_records=10, category=category)


@app.get("/programs/{school}/{program_name:path}/archetypes")
def get_archetypes(school: str, program_name: str):
    return get_program_archetypes(_profile_db_path(), school, program_name)


@app.get("/programs/{school}/{program_name:path}")
def get_program_stats(school: str, program_name: str):
    result = program_stats(school, program_name)
    if isinstance(result, dict) and result.get("error"):
        return result
    return result


@app.post("/profile-match")
def post_profile_match(req: ProfileMatchRequest):
    if _grade_out_of_range(req.grade_average):
        return {"error": "grade_out_of_range"}
    school_normalized, _ = normalize_school(req.school)
    if school_normalized is None:
        return {"error": "unknown_school"}
    program_normalized = normalize_program_name(req.program, school=school_normalized)
    if get_program_category(program_normalized) == "OTHER":
        return {"error": "unknown_program"}
    return match_profiles(_profile_db_path(), {
        "school": school_normalized,
        "program": program_normalized,
        "grade_average": req.grade_average,
        "curriculum_type": req.curriculum_type,
        "activities": [activity.model_dump() for activity in req.activities],
    })


@app.post("/profiles")
def create_profile(req: CreateProfileRequest):
    if _grade_out_of_range(req.grade_average):
        return {"error": "grade_out_of_range"}
    school_normalized, _ = normalize_school(req.school)
    if school_normalized is None:
        return {"error": "unknown_school"}
    program_normalized = normalize_program_name(req.program, school=school_normalized)
    if get_program_category(program_normalized) == "OTHER":
        return {"error": "unknown_program"}
    activities = extract_activity_signals(req.activities_text)
    return {
        "status": "ok",
        "normalized_school": school_normalized,
        "normalized_program": program_normalized,
        "activity_count": len(activities),
        "activities": [_public_activity(activity) for activity in activities],
    }


class SubmitOutcomeRequest(BaseModel):
    school: str
    program: str
    grade: float
    decision: Literal["Accepted", "Rejected", "Waitlisted", "Deferred"]
    ecs: Optional[str] = None
    province: Optional[str] = None


_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = init_db(DB_PATH)
    return _engine


@app.post("/submit-outcome")
def submit_outcome(req: SubmitOutcomeRequest):
    # Validate grade range
    if not (50 <= req.grade <= 100):
        return {"error": "grade_out_of_range"}

    # Normalize school
    school_normalized, multi = normalize_school(req.school)
    if school_normalized is None:
        return {"error": "unknown_school"}

    # Normalize fields
    decision = normalize_decision(req.decision)
    province = normalize_province(req.province) if req.province else None
    program_category = tag_program(req.program)
    program_normalized = normalize_program_name(req.program, school=school_normalized)
    ec_tags = _json.dumps(tag_ec(req.ecs)) if req.ecs else _json.dumps(["NONE"])
    circumstance_tags = _json.dumps(["NONE"])

    student = Student(
        source="USER_SUBMITTED",
        school_raw=req.school,
        school_normalized=school_normalized,
        multi_school_flag=multi,
        program_raw=req.program,
        program_category=program_category,
        program_normalized=program_normalized,
        decision=decision,
        core_avg=req.grade,
        ec_raw=req.ecs,
        ec_tags=ec_tags,
        circumstance_tags=circumstance_tags,
        province=province,
    )

    engine = _get_engine()
    with Session(engine) as session:
        session.add(student)
        session.commit()

    return {"status": "ok", "school_normalized": school_normalized, "program_category": program_category}
