from sqlalchemy.orm import Session

from core.profile_enrichment import is_profile_eligible, upsert_profile_for_student
from database.models import Student, init_db


def backfill_applicant_profiles(db_path: str = "database/unipath.db") -> dict:
    engine = init_db(db_path)
    checked = 0
    created_or_updated = 0
    skipped = 0

    with Session(engine) as session:
        students = session.query(Student).all()
        for student in students:
            checked += 1
            if not is_profile_eligible(student):
                skipped += 1
                continue
            upsert_profile_for_student(session, student)
            created_or_updated += 1
        session.commit()

    summary = {
        "checked": checked,
        "created_or_updated": created_or_updated,
        "skipped": skipped,
    }
    print(summary)
    return summary


if __name__ == "__main__":
    backfill_applicant_profiles()
