import streamlit as st
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans

# -----------------------------------
# SYLLABUS STRUCTURE
# -----------------------------------
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
        "Engineering Mathematics": ["Calculus", "Linear Algebra"],
        "Core Subject 1": ["Topic 1", "Topic 2"],
        "Core Subject 2": ["Advanced Topic"],
        "General Aptitude": ["Verbal", "Numerical"]
    }
}

# -----------------------------------
# RL PARAMETERS
# -----------------------------------
ALPHA = 0.2
GAMMA = 0.9
TOTAL_HOURS = 6  # hours per day

# -----------------------------------
# STREAMLIT CONFIG
# -----------------------------------
st.set_page_config(page_title="Adaptive Study Planner")
st.title("📘 Adaptive Study Planner")
st.caption("Exam → Subject → Topic → Day-wise personalized plan")

# -----------------------------------
# EXAM SELECTION
# -----------------------------------
exam = st.selectbox("Select Exam", list(SYLLABUS.keys()))
subjects = SYLLABUS[exam]

# -----------------------------------
# INITIALIZE SESSION STATE
# -----------------------------------
if "current_exam" not in st.session_state or st.session_state.current_exam != exam:
    st.session_state.current_exam = exam
    st.session_state.topic_progress = {}
    st.session_state.Q = {}
    for subject, topics in subjects.items():
        for topic in topics:
            key = f"{subject}::{topic}"
            st.session_state.topic_progress[key] = 0
            st.session_state.Q[key] = 0.0

# -----------------------------------
# TOPIC PROGRESS INPUT
# -----------------------------------
st.subheader("📊 Topic Coverage (%)")

for subject, topics in subjects.items():
    st.markdown(f"### {subject}")
    for topic in topics:
        key = f"{subject}::{topic}"
        st.session_state.topic_progress[key] = st.slider(
            topic, 0, 100, st.session_state.topic_progress.get(key, 0)
        )

# -----------------------------------
# GENERATE STUDY PLAN
# -----------------------------------
if st.button("Generate Day-wise Study Plan"):

    data = []
    # RL UPDATE & Data collection
    for key, progress in st.session_state.topic_progress.items():
        reward = (100 - progress) / 100
        st.session_state.Q[key] += ALPHA * (
            reward + GAMMA * max(st.session_state.Q.values()) - st.session_state.Q[key]
        )
        subject, topic = key.split("::")
        data.append([subject, topic, progress, st.session_state.Q[key]])

    df = pd.DataFrame(data, columns=["Subject", "Topic", "Coverage (%)", "RL Priority"])

    # -----------------------------------
    # CLUSTERING (SKILL LEVEL)
    # -----------------------------------
    if len(df) >= 3:  # KMeans needs at least 3 samples for 3 clusters
        kmeans = KMeans(n_clusters=3, random_state=42)
        df["Cluster"] = kmeans.fit_predict(df[["Coverage (%)"]])
        cluster_means = df.groupby("Cluster")["Coverage (%)"].mean().sort_values()
        skill_map = {cluster: label for cluster, label in zip(
            cluster_means.index, ["Beginner", "Intermediate", "Advanced"]
        )}
        df["Skill Level"] = df["Cluster"].map(skill_map)
    else:
        # fallback for small number of topics
        df["Skill Level"] = ["Beginner" if x < 50 else "Intermediate" if x < 80 else "Advanced" for x in df["Coverage (%)"]]

    # -----------------------------------
    # CALCULATE DAILY HOURS & DAYS NEEDED
    # -----------------------------------
    df["Daily Study Hours"] = (df["RL Priority"] / df["RL Priority"].sum()) * TOTAL_HOURS
    # Assume each topic requires 10 study hours as base
    df["Hours Needed"] = 10  # you can make this dynamic
    df["Days Needed"] = (df["Hours Needed"] / df["Daily Study Hours"]).apply(np.ceil).replace(np.inf, 1)

    df = df.sort_values("Days Needed", ascending=False)

    # -----------------------------------
    # DISPLAY DATAFRAME
    # -----------------------------------
    st.subheader("📅 Day-wise Personalized Study Plan")
    st.dataframe(
        df[["Subject", "Topic", "Coverage (%)", "Skill Level", "Daily Study Hours", "Days Needed"]].round(2)
    )

    # -----------------------------------
    # FLASHCARD STYLE INSIGHTS
    # -----------------------------------
    st.subheader("🧠 Learning Insights")
    for _, row in df.iterrows():
        msg = f"{row['Subject']} → {row['Topic']} (Complete in {int(row['Days Needed'])} days)"
        if row["Skill Level"] == "Beginner":
            st.error(f"🔴 {msg}")
        elif row["Skill Level"] == "Intermediate":
            st.warning(f"🟡 {msg}")
        else:
            st.success(f"🟢 {msg}")
