import streamlit as st
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans

# -------------------------------
# SYLLABUS DATA
# -------------------------------
SYLLABUS = {

    "UPSC CSE": {
        "Polity": ["Constitution", "Parliament", "Judiciary"],
        "History": ["Ancient", "Medieval", "Modern"],
        "Geography": ["Physical", "Indian", "World"],
        "Economy": ["Budget", "Survey", "Planning"],
        "Environment": ["Ecology", "Climate Change"],
        "Science & Tech": ["Biotech", "Space", "IT"]
    },

    "SSC": {
        "Quantitative Aptitude": ["Algebra", "Geometry", "Arithmetic"],
        "Reasoning": ["Analogy", "Series", "Puzzles"],
        "English": ["Grammar", "Vocabulary", "RC"],
        "General Awareness": ["History", "Geography", "Current Affairs"]
    },

    "GATE": {
        "Engineering Mathematics": ["Calculus", "Linear Algebra"],
        "Core Subject 1": ["Topic 1", "Topic 2"],
        "Core Subject 2": ["Advanced Topic 1"],
        "General Aptitude": ["Verbal", "Numerical"]
    }
}

# -------------------------------
# STREAMLIT UI
# -------------------------------
st.set_page_config(page_title="AI Study Plan Generator")
st.title("📘 AI-Powered Personalized Study Plan")

exam = st.selectbox("Select Exam", list(SYLLABUS.keys()))

st.subheader("📊 Enter Your Accuracy (%)")

performance = {}
for subject in SYLLABUS[exam]:
    performance[subject] = st.slider(subject, 0, 100, 50)

# -------------------------------
# CLUSTERING + STUDY PLAN
# -------------------------------
if st.button("Generate Study Plan"):

    df = pd.DataFrame({
        "Subject": performance.keys(),
        "Accuracy": performance.values()
    })

    # ---------------------------
    # KMEANS CLUSTERING
    # ---------------------------
    X = df[["Accuracy"]].values

    kmeans = KMeans(n_clusters=3, random_state=42)
    df["Cluster"] = kmeans.fit_predict(X)

    # Map clusters to skill levels
    cluster_means = df.groupby("Cluster")["Accuracy"].mean().sort_values()

    skill_map = {}
    labels = ["Beginner", "Intermediate", "Advanced"]

    for i, cluster in enumerate(cluster_means.index):
        skill_map[cluster] = labels[i]

    df["Skill Level"] = df["Cluster"].map(skill_map)

    # ---------------------------
    # STUDY HOURS ALLOCATION
    # ---------------------------
    df["Priority Score"] = 100 - df["Accuracy"]
    total_hours = 6

    df["Daily Study Hours"] = (
        df["Priority Score"] / df["Priority Score"].sum()
    ) * total_hours

    st.subheader("📊 Student Skill Segmentation")
    st.dataframe(df[["Subject", "Accuracy", "Skill Level", "Daily Study Hours"]])

    # ---------------------------
    # RECOMMENDATIONS
    # ---------------------------
    st.subheader("🧠 AI Recommendations")

    for _, row in df.iterrows():
        if row["Skill Level"] == "Beginner":
            st.error(f"🔴 Focus strongly on {row['Subject']}")
            st.write(", ".join(SYLLABUS[exam][row["Subject"]]))

        elif row["Skill Level"] == "Intermediate":
            st.warning(f"🟡 Improve consistency in {row['Subject']}")

        else:
            st.success(f"🟢 Maintain performance in {row['Subject']}")

    st.info("📈 Clusters update automatically after each performance update.")
