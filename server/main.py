"""
server/main.py
FastAPI server — production replacement for the subprocess bridge.
Deployed on Railway. Called via HTTP from the Next.js API route on Vercel.
"""
import sys
from pathlib import Path

# Ensure project root is on the path regardless of where uvicorn is invoked from
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.calibrate import final_probability, ADMITTED_PROFILES
from core.recommend import find_similar, program_stats, list_programs

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
def get_programs():
    return list_programs(min_records=10)


@app.get("/programs/{school}/{program}")
def get_program_stats(school: str, program: str):
    result = program_stats(school, program.upper())
    if result["total_records"] == 0:
        return {"error": "no_data"}
    return result
