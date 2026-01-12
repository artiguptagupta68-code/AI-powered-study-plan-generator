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
st.caption("Plan your study based on remaining days, studied days, and available free hours per day.")

# -------------------------------
# EXAM & SUBJECT SELECTION
# -------------------------------
exam = st.selectbox("Select Exam", list(SYLLABUS.keys()))
subjects = SYLLABUS[exam]

subject_selected = st.selectbox("Select Subject", list(subjects.keys()))
topics = subjects[subject_selected]

# -------------------------------
# USER INPUTS: Topic, Days, Hours
# -------------------------------
st.subheader("Enter Topic Details")
data = []
for topic in topics:
    st.markdown(f"**{topic}**")
    total_days = st.number_input(f"Total days to complete {topic}", min_value=1, max_value=60, value=7, key=f"{topic}_total")
    days_studied = st.number_input(f"Days already studied for {topic}", min_value=0, max_value=total_days, value=0, key=f"{topic}_studied")
    free_hours = st.number_input(f"Free hours per day for {topic}", min_value=1, max_value=24, value=2, key=f"{topic}_free")
    expected_days = total_days - days_studied
    expected_days = max(expected_days, 1)  # avoid zero division
    data.append({
        "Subject": subject_selected,
        "Topic": topic,
        "Total Days": total_days,
        "Days Studied": days_studied,
        "Free Hours/Day": free_hours,
        "Expected Days": expected_days
    })

df = pd.DataFrame(data)

# -------------------------------
# GENERATE STUDY PLAN
# -------------------------------
if st.button("Generate Study Plan"):

    # Allocate daily hours proportionally
    df["Daily Study Hours"] = df.apply(lambda row: min(row["Free Hours/Day"], row["Free Hours/Day"] * row["Expected Days"] / row["Expected Days"]), axis=1)
    
    # Sort topics with fewer expected days first
    df = df.sort_values("Expected Days")

    # Display table
    st.subheader("📅 Day-wise Study Plan")
    st.dataframe(df[["Subject", "Topic", "Days Studied", "Expected Days", "Daily Study Hours"]].round(2))

    # Insights
    st.subheader("🧠 Learning Insights")
    for _, row in df.iterrows():
        st.write(
            f"Topic **{row['Topic']}**: "
            f"{row['Expected Days']} days left, "
            f"study **{row['Daily Study Hours']:.1f} hours/day**"
        )
