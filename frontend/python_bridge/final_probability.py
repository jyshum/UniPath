"""
python_bridge/final_probability.py
Reads JSON from stdin, calls final_probability(), writes JSON to stdout.
Used by /api/final-probability on form submit.
"""
import sys
import json
import os

_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.normpath(_project_root))

from calibrate import final_probability, ADMITTED_PROFILES  # noqa: E402


def main() -> None:
    data = json.loads(sys.stdin.read())
    school     = data['school']
    program    = data['program'].upper()
    grade      = float(data['grade'])
    supp_types = data.get('supplemental_types', [])
    supp_texts = data.get('supplemental_texts', {})
    supp_done  = data.get('supplemental_completed', {})
    activities = data.get('activities', [])

    # v1: only return data for ADMITTED_PROFILES combos
    if (school, program) not in ADMITTED_PROFILES:
        print(json.dumps({'error': 'no_data'}))
        return

    # Format activity list inputs into a single scored block
    if activities:
        formatted = '\n'.join(
            f"Activity {i + 1}: {act.strip()}"
            for i, act in enumerate(activities)
            if act.strip()
        )
        if formatted:
            supp_texts['activity_list'] = formatted

    result = final_probability(
        school=school,
        program_category=program,
        grade=grade,
        supplemental_types=supp_types,
        supplemental_texts=supp_texts,
        supplemental_completed=supp_done,
    )

    if result is None:
        print(json.dumps({'error': 'no_data'}))
        return

    print(json.dumps(result))


if __name__ == '__main__':
    main()
