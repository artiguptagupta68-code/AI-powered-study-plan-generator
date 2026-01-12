import streamlit as st
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans

# -----------------------------------
# SYLLABUS DATA
# -----------------------------------
SYLLABUS = {
    "UPSC": [
        "Polity", "History", "Geography",
        "Economy", "Environment", "Science & Tech"
    ],
    "SSC": [
        "Quantitative Aptitude",
        "Reasoning",
        "English",
        "General Awareness"
    ],
    "GATE": [
        "Engineering Mathematics",
        "Core Subject 1",
        "Core Subject 2",
        "General Aptitude"
    ]
}

# -----------------------------------
# RL PARAMETERS
# -----------------------------------
ALPHA = 0.2
GAMMA = 0.9
TOTAL_HOURS = 6

# -----------------------------------
# STREAMLIT CONFIG
# -----------------------------------
st.set_page_config(page_title="Adaptive AI Study Planner")
st.title("🎯 Adaptive AI Study Planner")
st.caption(
    "Tailors learning based on performance for UPSC, SSC & GATE aspirants"
)

# -----------------------------------
# EXAM SELECTION
# -----------------------------------
exam = st.selectbox("Select Exam", list(SYLLABUS.keys()))

subjects = SYLLABUS[exam]

# -----------------------------------
# RESET STATE ON EXAM CHANGE
# -----------------------------------
if "current_exam" not in st.session_state or st.session_state.current_exam != exam:
    st.session_state.current_exam = exam
    st.session_state.accuracy = {s: 50 for s in subjects}
    st.session_state.Q = np.zeros(len(subjects))

# -----------------------------------
# PERFORMANCE INPUT
# -----------------------------------
st.subheader("📊 Current Performance (%)")

for s in subjects:
    st.session_state.accuracy[s] = st.slider(
        s,
        0,
        100,
        st.session_state.accuracy[s]
    )

# -----------------------------------
# MOCK TEST UPDATE
# -----------------------------------
st.subheader("🧪 Update After Mock Test")

new_accuracy = {}
for s in subjects:
    new_accuracy[s] = st.number_input(
        f"{s} (Post-Test Accuracy)",
        0,
        100,
        st.session_state.accuracy[s],
        step=1
    )

# -----------------------------------
# UPDATE STUDY PLAN
# -----------------------------------
if st.button("Update Personalized Study Plan"):

    # RL UPDATE
    for i, subject in enumerate(subjects):
        reward = new_accuracy[subject] - st.session_state.accuracy[subject]

        st.session_state.Q[i] = st.session_state.Q[i] + ALPHA * (
            reward + GAMMA * np.max(st.session_state.Q) - st.session_state.Q[i]
        )

        st.session_state.accuracy[subject] = new_accuracy[subject]

    # DATAFRAME
    df = pd.DataFrame({
        "Subject": subjects,
        "Accuracy": list(st.session_state.accuracy.values()),
        "RL Score": st.session_state.Q
    })

    # -----------------------------------
    # CLUSTERING
    # -----------------------------------
    kmeans = KMeans(n_clusters=3, random_state=42)
    df["Cluster"] = kmeans.fit_predict(df[["Accuracy"]])

    cluster_means = df.groupby("Cluster")["Accuracy"].mean().sort_values()
    skill_labels = ["Beginner", "Intermediate", "Advanced"]

    df["Skill Level"] = df["Cluster"].map({
        cluster: skill_labels[i]
        for i, cluster in enumerate(cluster_means.index)
    })

    # -----------------------------------
    # STUDY HOURS ALLOCATION
    # -----------------------------------
    df["Daily Study Hours"] = (
        df["RL Score"] / df["RL Score"].sum()
    ) * TOTAL_HOURS

    df = df.sort_values("Daily Study Hours", ascending=False)

    # -----------------------------------
    # OUTPUT
    # -----------------------------------
    st.subheader("📅 Updated Adaptive Study Plan")
    st.dataframe(
        df[[
            "Subject",
            "Accuracy",
            "Skill Level",
            "Daily Study Hours"
        ]].round(2)
    )

    # -----------------------------------
    # INSIGHTS
    # -----------------------------------
    st.subheader("🧠 AI Insights")

    for _, row in df.iterrows():
        if row["Skill Level"] == "Beginner":
            st.error(f"🔴 {row['Subject']} needs intensive focus")
        elif row["Skill Level"] == "Intermediate":
            st.warning(f"🟡 {row['Subject']} improving steadily")
        else:
            st.success(f"🟢 {row['Subject']} well prepared")

# -----------------------------------
# MONETIZATION SECTION
# -----------------------------------
st.markdown("---")
st.subheader("💳 Monetization Strategy")

st.write("""
This platform can be monetized through a **subscription-based model**:

• **Free Tier**
  - Manual study plan
  - Limited updates

• **Premium Tier**
  - Reinforcement learning based adaptation
  - Performance tracking over time
  - Skill clustering & insights
  - Personalized alerts & reminders

This makes the solution scalable for UPSC, SSC & GATE aspirants.
""")
