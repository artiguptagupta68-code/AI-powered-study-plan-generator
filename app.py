import streamlit as st
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans

# -------------------------------
# SYLLABUS STRUCTURE
# -------------------------------
SYLLABUS = {
    "UPSC": {
        "Polity": ["Constitution", "Parliament", "Judiciary"],
        "History": ["Ancient", "Medieval", "Modern"],
        "Geography": ["Physical", "Indian", "World"],
        "Economy": ["Budget", "Survey", "Planning"],
        "Environment": ["Ecology", "Climate Change"],
        "Science & Tech": ["Biotech", "Space", "IT"]
    },
    "SSC": {
        "Quantitative Aptitude": ["Percentage", "Profit & Loss", "Algebra"],
        "Reasoning": ["Analogy", "Series", "Puzzles"],
        "English": ["Grammar", "Vocabulary", "Comprehension"],
        "General Awareness": ["History", "Geography", "Current Affairs"]
    },
    "GATE": {
        "Engineering Mathematics": ["Linear Algebra", "Calculus", "Differential Equations", "Probability & Statistics"],
        "Computer Science": ["Data Structures", "Algorithms", "Operating Systems", "DBMS", "Computer Networks"],
        "Electronics": ["Digital Circuits", "Analog Circuits", "Signals & Systems", "Communication Systems"],
        "Mechanical": ["Thermodynamics", "Fluid Mechanics", "Strength of Materials", "Dynamics"],
        "General Aptitude": ["Verbal Ability", "Numerical Ability"]
    }
}

# -------------------------------
# RL PARAMETERS
# -------------------------------
ALPHA = 0.2
GAMMA = 0.9
TOTAL_HOURS = 6

# -------------------------------
# STREAMLIT CONFIG
# -------------------------------
st.set_page_config(page_title="Adaptive Study Planner", layout="wide")
st.title("📘 Adaptive Study Planner")
st.caption("Generate personalized day-wise study plan based on topic progress and skill level")

# -------------------------------
# EXAM SELECTION
# -------------------------------
exam = st.selectbox("Select Exam", list(SYLLABUS.keys()))
subjects = SYLLABUS[exam]

# -------------------------------
# RESET STATE ON EXAM CHANGE
# -------------------------------
if "current_exam" not in st.session_state or st.session_state.current_exam != exam:
    st.session_state.current_exam = exam
    st.session_state.topic_progress = {}
    st.session_state.Q = {}

    for subject, topics in subjects.items():
        for topic in topics:
            key = f"{subject}::{topic}"
            st.session_state.topic_progress[key] = 0
            st.session_state.Q[key] = 0.0

# -------------------------------
# SUBJECT & TOPIC SELECTION
# -------------------------------
st.subheader("Select Subject and Topic to update progress")

subject_selected = st.selectbox("Select Subject", list(subjects.keys()))
topic_selected = st.selectbox("Select Topic", subjects[subject_selected])
key_selected = f"{subject_selected}::{topic_selected}"

st.session_state.topic_progress[key_selected] = st.slider(
    f"Progress for {topic_selected}", 0, 100, st.session_state.topic_progress[key_selected]
)

# -------------------------------
# GENERATE STUDY PLAN
# -------------------------------
if st.button("Generate Day-wise Study Plan"):

    data = []

    # RL UPDATE
    for key, progress in st.session_state.topic_progress.items():
        reward = (100 - progress) / 100
        st.session_state.Q[key] = st.session_state.Q[key] + ALPHA * (
            reward + GAMMA * max(st.session_state.Q.values()) - st.session_state.Q[key]
        )

        subject, topic = key.split("::")
        data.append([subject, topic, progress, st.session_state.Q[key]])

    df = pd.DataFrame(
        data,
        columns=["Subject", "Topic", "Coverage (%)", "RL Priority"]
    )

    # -------------------------------
    # CLUSTERING (TOPIC SKILL LEVEL)
    # -------------------------------
    kmeans = KMeans(n_clusters=3, random_state=42)
    df["Cluster"] = kmeans.fit_predict(df[["Coverage (%)"]])

    cluster_means = df.groupby("Cluster")["Coverage (%)"].mean().sort_values()
    skill_map = {cluster: label for cluster, label in zip(
        cluster_means.index,
        ["Beginner", "Intermediate", "Advanced"]
    )}

    df["Skill Level"] = df["Cluster"].map(skill_map)

    # -------------------------------
    # DAY-WISE STUDY ALLOCATION
    # -------------------------------
    df["Daily Study Hours"] = (
        df["RL Priority"] / df["RL Priority"].sum()
    ) * TOTAL_HOURS

    df = df.sort_values("Daily Study Hours", ascending=False)

    # -------------------------------
    # OUTPUT
    # -------------------------------
    st.subheader("📅 Day-wise Personalized Study Plan")
    st.dataframe(
        df[[
            "Subject",
            "Topic",
            "Coverage (%)",
            "Skill Level",
            "Daily Study Hours"
        ]].round(2)
    )

    # -------------------------------
    # LEARNING INSIGHTS
    # -------------------------------
    st.subheader("🧠 Learning Insights")
    for _, row in df.iterrows():
        hours_needed = row["Daily Study Hours"]
        if row["Skill Level"] == "Beginner":
            st.error(f"🔴 {row['Subject']} → {row['Topic']} → Study {hours_needed:.1f} hrs today")
        elif row["Skill Level"] == "Intermediate":
            st.warning(f"🟡 {row['Subject']} → {row['Topic']} → Study {hours_needed:.1f} hrs today")
        else:
            st.success(f"🟢 {row['Subject']} → {row['Topic']} → Study {hours_needed:.1f} hrs today")
