import streamlit as st
import pandas as pd
import numpy as np

# -------------------------------
# SYLLABUS STRUCTURE
# -------------------------------
SYLLABUS = {
    "UPSC": {
        "Polity": ["Constitution", "Parliament", "Judiciary"],
        "History": ["Ancient", "Medieval", "Modern"]
    },
    "SSC": {
        "Quantitative Aptitude": ["Percentage", "Profit & Loss", "Algebra"],
        "Reasoning": ["Analogy", "Series", "Puzzles"]
    },
    "GATE": {
        "Core Subject 1": ["Topic 1", "Topic 2"],
        "Core Subject 2": ["Advanced Topic"]
    }
}

# -------------------------------
# STUDENT DATA SIMULATION
# -------------------------------
# Number of students who completed each topic and days taken
STUDENT_DATA = {
    "Constitution": [5, 6, 7, 6, 5],        # days taken by students
    "Parliament": [3, 4, 4, 5],
    "Judiciary": [4, 5, 5, 6],
    "Ancient": [6, 7, 8],
    "Medieval": [5, 6, 5, 6],
    "Modern": [4, 5, 5],
    "Percentage": [2, 3, 2, 3, 4],
    "Profit & Loss": [3, 3, 4, 4],
    "Algebra": [4, 4, 5],
    "Analogy": [2, 2, 3, 3],
    "Series": [2, 3, 3],
    "Puzzles": [3, 3, 4],
    "Topic 1": [5, 6, 5, 7],
    "Topic 2": [4, 5, 5],
    "Advanced Topic": [6, 7, 6]
}

# -------------------------------
# STREAMLIT CONFIG
# -------------------------------
st.set_page_config(page_title="Predictive Study Planner", layout="wide")
st.title("📘 Predictive Study Planner")
st.caption("Predict time to complete a topic based on previous students' data and your free hours.")

# -------------------------------
# EXAM & SUBJECT SELECTION
# -------------------------------
exam = st.selectbox("Select Exam", list(SYLLABUS.keys()))
subjects = SYLLABUS[exam]

subject_selected = st.selectbox("Select Subject", list(subjects.keys()))
topic_selected = st.selectbox("Select Topic", subjects[subject_selected])

# -------------------------------
# USER INPUTS
# -------------------------------
st.subheader(f"Topic: {topic_selected}")

free_hours = st.number_input("Free hours per day available", min_value=1, max_value=24, value=2)

# -------------------------------
# PREDICTION LOGIC
# -------------------------------
if st.button("Predict Study Plan"):
    if topic_selected in STUDENT_DATA:
        past_days = STUDENT_DATA[topic_selected]
        avg_days = np.mean(past_days)
        min_days = np.min(past_days)
        max_days = np.max(past_days)
        num_students = len(past_days)

        # Predict daily hours
        daily_hours = 2  # Default base
        total_hours_required = avg_days * daily_hours
        predicted_daily_hours = min(free_hours, total_hours_required / avg_days)

        st.subheader("📊 Prediction")
        st.markdown(f"- **Number of students studied this topic**: {num_students}")
        st.markdown(f"- **Average days taken**: {avg_days:.1f} days")
        st.markdown(f"- **Min days taken**: {min_days} days")
        st.markdown(f"- **Max days taken**: {max_days} days")
        st.markdown(f"- **Predicted daily study hours for you**: {predicted_daily_hours:.1f} hours/day")
        st.markdown(f"- **Expected total days to complete**: {avg_days:.1f} days")
    else:
        st.warning("No student data available for this topic.")
