import streamlit as st
import pandas as pd
import numpy as np

# -------------------------------
# SYLLABUS STRUCTURE
# -------------------------------
SYLLABUS = {
    "UPSC": {
        "Polity": ["Constitution", "Parliament", "Judiciary"],
        "History": ["Ancient", "Medieval", "Modern"],
        "Geography": ["Physical", "Indian", "World"],
        "Economy": ["Budget", "Survey", "Planning"]
    },
    "SSC": {
        "Quantitative Aptitude": ["Percentage", "Profit & Loss", "Algebra"],
        "Reasoning": ["Analogy", "Series", "Puzzles"],
        "English": ["Grammar", "Vocabulary", "Comprehension"]
    },
    "GATE": {
        "Core Subject 1": ["Topic 1", "Topic 2"],
        "Core Subject 2": ["Advanced Topic"]
    }
}

# -------------------------------
# STREAMLIT CONFIG
# -------------------------------
st.set_page_config(page_title="Smart Study Planner", layout="wide")
st.title("📘 Smart Adaptive Study Planner")
st.caption("Plan your study based on remaining days, studied days, and free hours/day.")

# -------------------------------
# EXAM & SUBJECT SELECTION
# -------------------------------
exam = st.selectbox("Select Exam", list(SYLLABUS.keys()))
subjects = SYLLABUS[exam]

subject_selected = st.selectbox("Select Subject", list(subjects.keys()))
topics = subjects[subject_selected]

# -------------------------------
# TOPIC DROPDOWN
# -------------------------------
topic_selected = st.selectbox("Select Topic", topics)

# -------------------------------
# USER INPUTS
# -------------------------------
st.subheader(f"Topic: {topic_selected}")
total_days = st.number_input(f"Total days to complete {topic_selected}", min_value=1, max_value=60, value=7)
days_studied = st.number_input(f"Days already studied for {topic_selected}", min_value=0, max_value=total_days, value=0)
free_hours = st.number_input(f"Free hours per day available", min_value=1, max_value=24, value=2)

expected_days = total_days - days_studied
expected_days = max(expected_days, 1)  # avoid zero division

# -------------------------------
# GENERATE STUDY PLAN
# -------------------------------
if st.button("Generate Study Plan"):
    daily_hours = min(free_hours, free_hours * expected_days / expected_days)  # proportionate hours

    plan_df = pd.DataFrame([{
        "Exam": exam,
        "Subject": subject_selected,
        "Topic": topic_selected,
        "Total Days": total_days,
        "Days Studied": days_studied,
        "Expected Days": expected_days,
        "Daily Study Hours": round(daily_hours, 2)
    }])

    st.subheader("📅 Study Plan")
    st.dataframe(plan_df)

    st.subheader("🧠 Insight")
    st.write(f"Topic **{topic_selected}** has **{expected_days} days remaining**. "
             f"Study **{daily_hours:.1f} hours per day** to complete on time.")
