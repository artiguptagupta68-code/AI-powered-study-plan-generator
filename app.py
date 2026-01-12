import streamlit as st
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
import pickle

# -----------------------
# Simulated Student Data
# -----------------------
STUDENT_HISTORY = {
    "UPSC": {
        "Polity": {
            "Constitution": [[40, 2, 1], [50, 2.5, 1], [60, 3, 1]],
            "Parliament": [[70, 2, 1], [65, 1.5, 1], [60, 2, 1]],
            "Judiciary": [[50, 2, 1], [55, 2.5, 1], [65, 3, 1]]
        },
        "History": {
            "Ancient": [[60, 2, 1], [70, 2, 1], [75, 2.5, 1]],
            "Medieval": [[50, 1.5, 1], [55, 2, 1], [60, 2, 1]],
            "Modern": [[45, 1.5, 1], [55, 2, 1], [65, 2.5, 1]]
        }
    },
    "SSC": {
        "Quantitative Aptitude": {
            "Percentage": [[60, 2, 1], [70, 2, 1], [80, 3, 1]],
            "Profit & Loss": [[50, 1.5, 1], [55, 2, 1], [65, 2, 1]],
            "Algebra": [[40, 2, 1], [45, 2, 1], [55, 2.5, 1]]
        },
        "Reasoning": {
            "Analogy": [[55, 1.5, 1], [60, 2, 1], [65, 2, 1]],
            "Series": [[50, 1.5, 1], [55, 2, 1], [60, 2, 1]],
            "Puzzles": [[45, 1, 1], [50, 1.5, 1], [55, 2, 1]]
        }
    },
    "GATE": {
        "Engineering Mathematics": {
            "Calculus": [[40, 2, 1], [50, 2.5, 1], [55, 3, 1]],
            "Linear Algebra": [[45, 2, 1], [50, 2, 1], [60, 2.5, 1]]
        },
        "Core Subject 1": {
            "Topic 1": [[30, 1.5, 1], [40, 2, 1], [50, 2.5, 1]],
            "Topic 2": [[35, 1.5, 1], [45, 2, 1], [55, 2.5, 1]]
        },
        "Core Subject 2": {
            "Advanced Topic": [[50, 2, 1], [55, 2.5, 1], [60, 3, 1]]
        },
        "General Aptitude": {
            "Verbal": [[60, 1.5, 1], [65, 2, 1], [70, 2, 1]],
            "Numerical": [[50, 1.5, 1], [55, 2, 1], [60, 2, 1]]
        }
    }
}

# -----------------------
# Streamlit Page
# -----------------------
st.set_page_config(page_title="Adaptive Study Dashboard")
st.title("📘 Adaptive Study Dashboard")
st.caption("Analyze your progress and get a personalized GATE/UPSC/SSC study plan")

# -----------------------
# Sidebar Selection
# -----------------------
exam = st.selectbox("Select Exam", list(STUDENT_HISTORY.keys()))
subject = st.selectbox("Select Subject", list(STUDENT_HISTORY[exam].keys()))
topic = st.selectbox("Select Topic", list(STUDENT_HISTORY[exam][subject].keys()))

# -----------------------
# Extract Topic Data
# -----------------------
topic_data = np.array(STUDENT_HISTORY[exam][subject][topic])
scores = topic_data[:, 0]
hours = topic_data[:, 1]

# -----------------------
# Clustering Skill Level
# -----------------------
kmeans = KMeans(n_clusters=3, random_state=42)
clusters = kmeans.fit_predict(scores.reshape(-1,1))
cluster_means = [scores[clusters==i].mean() for i in range(3)]
sorted_clusters = np.argsort(cluster_means)
skill_map = {sorted_clusters[0]:"Beginner", sorted_clusters[1]:"Intermediate", sorted_clusters[2]:"Advanced"}
latest_score = scores[-1]
skill_level = skill_map[clusters[-1]]

# -----------------------
# Topic-wise Stats
# -----------------------
num_students = len(scores)
avg_days = np.mean(topic_data[:,2])
min_days = np.min(topic_data[:,2])
max_days = np.max(topic_data[:,2])
predicted_daily_hours = np.mean(hours)
expected_total_days = avg_days

st.subheader("📊 Topic-wise Analysis")
st.write(f"- Current Skill Level: **{skill_level}** ({latest_score}%)")
st.write(f"- Number of students studied this topic: {num_students}")
st.write(f"- Average days taken: {avg_days:.1f} days")
st.write(f"- Min days taken: {min_days} days")
st.write(f"- Max days taken: {max_days} days")
st.write(f"- Predicted daily study hours for you: {predicted_daily_hours:.1f} hours/day")
st.write(f"- Expected total days to complete: {expected_total_days:.1f} days")

# -----------------------
# Topic Progress Chart
# -----------------------
st.subheader("📈 Progress Over Time")
progress_df = pd.DataFrame({
    "Student": [f"Student {i+1}" for i in range(num_students)],
    "Score (%)": scores,
    "Hours": hours,
    "Days Taken": topic_data[:,2]
})
st.bar_chart(progress_df[["Score (%)"]])

# -----------------------
# Personalized Study Plan
# -----------------------
st.subheader("📅 Suggested Study Plan")
total_days = int(np.ceil(expected_total_days))
plan_df = pd.DataFrame({
    "Day": range(1, total_days+1),
    "Topic": [topic]*total_days,
    "Hours": [predicted_daily_hours]*total_days
})
st.dataframe(plan_df)

# -----------------------
# Update Mock Session
# -----------------------
new_score = st.slider("Update your score after study (%)", 0, 100, int(latest_score))
if st.button("Update Progress"):
    reward = new_score - latest_score
    alpha = 0.2
    gamma = 0.9

    # Load or init Q-table
    try:
        with open("q_table.pkl","rb") as f:
            Q = pickle.load(f)
    except:
        Q = {}
    if topic not in Q:
        Q[topic] = {predicted_daily_hours:0}

    Q[topic][predicted_daily_hours] = Q[topic][predicted_daily_hours] + alpha*(reward + gamma*max(Q[topic].values()) - Q[topic][predicted_daily_hours])

    with open("q_table.pkl","wb") as f:
        pickle.dump(Q,f)
    st.success(f"✅ Progress updated! Q-values updated for {topic}.")
