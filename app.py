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
        "Quantitative Aptitude", "Reasoning",
        "English", "General Awareness"
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

# -----------------------------------
# STREAMLIT UI
# -----------------------------------
st.set_page_config(page_title="Adaptive AI Study Planner")
st.title("🎯 Adaptive AI Study Planner")
st.write("Study plan updates automatically as you progress")

exam = st.selectbox("Select Exam", list(SYLLABUS.keys()))

subjects = SYLLABUS[exam]

# -----------------------------------
# SESSION STATE INIT
# -----------------------------------
if "accuracy" not in st.session_state:
    st.session_state.accuracy = {s: 50 for s in subjects}

if "Q" not in st.session_state:
    st.session_state.Q = np.zeros(len(subjects))

# -----------------------------------
# CURRENT PERFORMANCE INPUT
# -----------------------------------
st.subheader("📊 Current Accuracy (%)")

for s in subjects:
    st.session_state.accuracy[s] = st.slider(
        s, 0, 100, st.session_state.accuracy[s]
    )

# -----------------------------------
# UPDATE AFTER MOCK TEST
# -----------------------------------
st.subheader("🧪 Update After Mock Test")
st.caption("Enter new accuracy after studying / mock test")

new_accuracy = {}

for s in subjects:
    new_accuracy[s] = st.number_input(
        f"{s} (New Accuracy)",
        min_value=0,
        max_value=100,
        value=st.session_state.accuracy[s],
        step=1
    )

# -----------------------------------
# GENERATE / UPDATE STUDY PLAN
# -----------------------------------
if st.button("Update Study Plan"):

    rewards = []

    for i, subject in enumerate(subjects):
        reward = new_accuracy[subject] - st.session_state.accuracy[subject]
        rewards.append(reward)

        # Q-learning update
        st.session_state.Q[i] = st.session_state.Q[i] + ALPHA * (
            reward + GAMMA * np.max(st.session_state.Q) - st.session_state.Q[i]
        )

        # Update stored accuracy
        st.session_state.accuracy[subject] = new_accuracy[subject]

    # -----------------------------------
    # DATAFRAME
    # -----------------------------------
    df = pd.DataFrame({
        "Subject": subjects,
        "Accuracy": list(st.session_state.accuracy.values()),
        "RL Score": st.session_state.Q
    })

    # -----------------------------------
    # CLUSTERING (Skill Groups)
    # -----------------------------------
    kmeans = KMeans(n_clusters=3, random_state=42)
    df["Cluster"] = kmeans.fit_predict(df[["Accuracy"]])

    cluster_means = df.groupby("Cluster")["Accuracy"].mean().sort_values()
    skill_labels = ["Beginner", "Intermediate", "Advanced"]

    cluster_map = {
        cluster: skill_labels[i]
        for i, cluster in enumerate(cluster_means.index)
    }

    df["Skill Level"] = df["Cluster"].map(cluster_map)

    # -----------------------------------
    # STUDY TIME ALLOCATION
    # -----------------------------------
    total_hours = 6
    df["Daily Study Hours"] = (
        df["RL Score"] / df["RL Score"].sum()
    ) * total_hours

    df = df.sort_values("Daily Study Hours", ascending=False)

    # -----------------------------------
    # OUTPUT
    # -----------------------------------
    st.subheader("📅 Updated Personalized Study Plan")
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
    st.subheader("🧠 Learning Insights")

    for _, row in df.iterrows():
        if row["Skill Level"] == "Beginner":
            st.error(f"🔴 {row['Subject']} needs more focus")
        elif row["Skill Level"] == "Intermediate":
            st.warning(f"🟡 {row['Subject']} improving steadily")
        else:
            st.success(f"🟢 {row['Subject']} performing well")

    st.success("✅ Study plan updated using real performance improvement")
