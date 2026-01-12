# app.py
import streamlit as st
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
import random

# -----------------------------------
# CONFIG
# -----------------------------------
st.set_page_config(page_title="AI-Powered Study Plan Generator", layout="wide")
st.title("📘 AI-Powered Personalized Study Plan Generator")
st.caption("Simulates multiple students, predicts days & hours needed per topic, adaptive based on progress")

# -----------------------------------
# SYLLABUS
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
        "Core Subject 1": ["Topic 1", "Topic 2"],
        "Core Subject 2": ["Advanced Topic"],
        "Engineering Mathematics": ["Calculus", "Linear Algebra"],
        "General Aptitude": ["Verbal", "Numerical"]
    }
}

# -----------------------------------
# RL & STUDY PARAMETERS
# -----------------------------------
ALPHA = 0.3
GAMMA = 0.9
TOTAL_HOURS_PER_DAY = 6

# -----------------------------------
# SIMULATE MULTIPLE STUDENTS
# -----------------------------------
NUM_STUDENTS = 5  # You can increase for more realistic simulation

def simulate_student_data(exam):
    subjects = SYLLABUS[exam]
    data = []
    for student_id in range(1, NUM_STUDENTS+1):
        for subject, topics in subjects.items():
            for topic in topics:
                progress = random.randint(0, 100)  # % completed
                days_taken = max(1, int(np.random.normal(loc=5, scale=2)))  # simulate days taken
                score = random.randint(50, 100)  # quiz score
                data.append({
                    "student_id": f"Student {student_id}",
                    "subject": subject,
                    "topic": topic,
                    "progress": progress,
                    "days_taken": days_taken,
                    "score": score
                })
    return pd.DataFrame(data)

# -----------------------------------
# SELECT EXAM / SUBJECT / TOPIC
# -----------------------------------
exam = st.selectbox("Select Exam", list(SYLLABUS.keys()))
subjects = SYLLABUS[exam]

# Core subject dropdown
subject = st.selectbox("Select Subject", list(subjects.keys()))
topic = st.selectbox("Select Topic", subjects[subject])

# -----------------------------------
# GENERATE SIMULATED DATA
# -----------------------------------
student_df = simulate_student_data(exam)
st.subheader(f"Simulated Data ({exam})")
st.dataframe(student_df)

# -----------------------------------
# CLUSTER STUDENTS BY PROGRESS
# -----------------------------------
kmeans = KMeans(n_clusters=3, random_state=42)
topic_df = student_df[(student_df.subject==subject) & (student_df.topic==topic)]
topic_df = topic_df.reset_index(drop=True)

topic_df["Cluster"] = kmeans.fit_predict(topic_df[["progress"]])
cluster_means = topic_df.groupby("Cluster")["progress"].mean().sort_values()
skill_map = {cluster: label for cluster, label in zip(cluster_means.index, ["Beginner", "Intermediate", "Advanced"])}
topic_df["Skill Level"] = topic_df["Cluster"].map(skill_map)

# -----------------------------------
# REINFORCEMENT LEARNING FOR PRIORITY
# -----------------------------------
Q = {idx: 0.0 for idx in topic_df.index}
for idx, row in topic_df.iterrows():
    reward = (100 - row.progress)/100
    Q[idx] = Q[idx] + ALPHA * (reward + GAMMA * max(Q.values()) - Q[idx])

topic_df["RL Priority"] = topic_df.index.map(Q)

# -----------------------------------
# PREDICT DAYS & HOURS FOR SELECTED STUDENT
# -----------------------------------
# Average over all students
avg_days = topic_df["days_taken"].mean()
predicted_daily_hours = TOTAL_HOURS_PER_DAY * (1 - topic_df["progress"].mean()/100)

st.subheader(f"📅 Predicted Study Plan for {topic}")
st.write(f"- Average days taken by students: {avg_days:.1f} days")
st.write(f"- Predicted daily study hours for you: {predicted_daily_hours:.1f} hours/day")
st.write(f"- Expected total days to complete topic: {avg_days:.1f} days")

# -----------------------------------
# SHOW STUDENT PROGRESS
# -----------------------------------
st.subheader(f"🧠 Topic Progress ({topic})")
for _, row in topic_df.iterrows():
    if row["Skill Level"] == "Beginner":
        st.error(f"🔴 {row.student_id} → {row.progress}% complete")
    elif row["Skill Level"] == "Intermediate":
        st.warning(f"🟡 {row.student_id} → {row.progress}% complete")
    else:
        st.success(f"🟢 {row.student_id} → {row.progress}% complete")
