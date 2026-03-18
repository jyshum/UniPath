# app.py

import streamlit as st
import sqlite3
import pandas as pd
import recommend

# --- Page config ---
st.set_page_config(
    page_title="UniPath AI",
    page_icon="🎓",
    layout="centered"
)


# --- Helpers ---
@st.cache_data
def get_schools():
    """Returns sorted list of schools in the database."""
    conn = sqlite3.connect("database/unipath.db")
    df = pd.read_sql(
        "SELECT DISTINCT school_normalized FROM students "
        "WHERE school_normalized IS NOT NULL "
        "ORDER BY school_normalized",
        conn
    )
    conn.close()
    return df["school_normalized"].tolist()


PROGRAM_OPTIONS = [
    "ENGINEERING",
    "SCIENCE",
    "BUSINESS",
    "ARTS",
    "COMPUTER_SCIENCE",
    "HEALTH",
    "LAW",
    "EDUCATION",
    "OTHER",
]


# --- UI ---
st.title("🎓 UniPath AI")
st.caption("Data-backed university outcomes for Canadian high school students.")

st.divider()

st.subheader("School Lookup")
st.write("Enter your profile to see how similar students performed at a specific school.")

schools = get_schools()

col1, col2 = st.columns(2)

with col1:
    school = st.selectbox("School", options=schools)
    grade = st.number_input(
        "Your core average",
        min_value=50.0,
        max_value=100.0,
        value=90.0,
        step=0.5,
    )

with col2:
    program = st.selectbox("Program category", options=PROGRAM_OPTIONS)
    tolerance = st.slider(
        "Grade tolerance (±)",
        min_value=1.0,
        max_value=5.0,
        value=2.0,
        step=0.5,
        help="How close in grades should similar students be?"
    )

search = st.button("Search", type="primary", use_container_width=True)

if search:
    result = recommend.lookup_school(school, grade, program, tolerance=tolerance)

    st.divider()

    if result["total_similar"] == 0:
        st.warning(
            f"No students found within ±{tolerance} of a {grade} average "
            f"applying to {program} at {school}. "
            f"Try widening the grade tolerance or selecting a different program."
        )
    else:
        st.subheader(f"Results — {school}")
        st.caption(
            f"Based on **{result['total_similar']} students** with a core average "
            f"within ±{tolerance} of {grade} applying to {program}."
        )

        # Build results table
        rows = []
        for b in result["breakdown"]:
            if b["count"] == 1:
                rows.append({
                    "Outcome": b["decision"],
                    "Students": b["count"],
                    "Avg Grade": b["avg_grade"],
                    "Min Grade": b["min_grade"],
                    "Max Grade": b["max_grade"],
                })
            else:
                rows.append({
                    "Outcome": b["decision"],
                    "Students": b["count"],
                    "Avg Grade": b["avg_grade"],
                    "Min Grade": b["min_grade"],
                    "Max Grade": b["max_grade"],
                })

        results_df = pd.DataFrame(rows)
        st.dataframe(
            results_df,
            use_container_width=True,
            hide_index=True,
        )

        # Honest data caveat
        st.caption(
            "⚠️ This data comes from self-reported Reddit submissions and reflects "
            "a non-random sample. Treat results as directional, not definitive."
        )