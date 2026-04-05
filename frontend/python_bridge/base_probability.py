"""
python_bridge/base_probability.py
Reads JSON from stdin, calls calibrated_probability(), writes JSON to stdout.
Used by /api/base-probability for the live grade preview.
"""
import sys
import json
import os

# Add project root (two levels up from frontend/python_bridge/) to path
_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.normpath(_project_root))

from core.calibrate import calibrated_probability, ADMITTED_PROFILES  # noqa: E402


def main() -> None:
    data = json.loads(sys.stdin.read())
    school  = data['school']
    program = data['program'].upper()
    grade   = float(data['grade'])

    # v1: only return data for ADMITTED_PROFILES combos
    if (school, program) not in ADMITTED_PROFILES:
        print(json.dumps({'error': 'no_data'}))
        return

    result = calibrated_probability(school, program, grade)

    if result is None:
        print(json.dumps({'error': 'no_data'}))
        return

    print(json.dumps({
        'probability':    result['probability'],
        'display_percent': f"{round(result['probability'] * 100)}%",
        'mode':           result['mode'],
        'data_limited':   result['data_limited'],
    }))


if __name__ == '__main__':
    main()
