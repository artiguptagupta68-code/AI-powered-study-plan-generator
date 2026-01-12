import streamlit as st
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
import random
import pickle

# -------------------
# Simulated past student data
# -------------------
# Each topic stores: [score%, hours_taken, day]
STUDENT_HISTORY = {
    "Constitution": [[40, 2, 1], [50, 2.5, 1], [60, 3, 1]],
    "Parliament": [[70, 2, 1], [65, 1.5, 1], [60, 2, 1]]
}

TOPICS = list(STUDENT_HISTORY.keys())

# -------------------
# Streamlit Inputs
# -------------------
st.title("📘 Adaptive RL Study Planner")
topic = st.selectbox("Select Topic", TOPICS)
free_hours = st.slider("Available Free Hours per Day", 1, 8, 2)

# -------------------
# Clustering to find mastery
# -------------------
topic_data = np.array(STUDENT_HISTORY[topic])
scores = topic_data[:, 0].reshape(-1, 1)

kmeans = KMeans(n_clusters=3, random_state=42)
clusters = kmeans.fit_predict(scores)
cluster_means = [scores[clusters==i].mean() for i in range(3)]
sorted_clusters = np.argsort(cluster_means)
skill_map = {sorted_clusters[0]:"Beginner", sorted_clusters[1]:"Intermediate", sorted_clusters[2]:"Advanced"}
latest_score = scores[-1][0]
skill_level = skill_map[clusters[-1]]

st.write(f"Current Skill Level: {skill_level} ({latest_score}%)")

# -------------------
# Reinforcement Learning Q-table (simplified)
# -------------------
# Actions = hours/day allocation: [1,2,3,4,5]
ACTIONS = [1,2,3,4,5]
# Q-values per topic per action (initialized random)
try:
    with open("q_table.pkl","rb") as f:
        Q = pickle.load(f)
except:
    Q = {t:{a:0 for a in ACTIONS} for t in TOPICS}

# Recommend action (hours/day) with highest Q
best_action = max(Q[topic], key=Q[topic].get)
predicted_days = 10 * (2 / best_action)  # simplified heuristic
predicted_daily_hours = best_action

st.subheader("📊 Predicted Plan")
st.write(f"- Recommended hours/day: {predicted_daily_hours}h")
st.write(f"- Expected total days to complete topic: {predicted_days:.1f} days")

# -------------------
# Simulate study session
# -------------------
new_score = st.slider("Mock Test Score after study (%)", 0, 100, latest_score)
if st.button("Update Progress"):
    # reward = improvement in score
    reward = new_score - latest_score
    alpha = 0.2
    gamma = 0.9
    # Q-learning update
    Q[topic][predicted_daily_hours] = Q[topic][predicted_daily_hours] + alpha * (
        reward + gamma * max(Q[topic].values()) - Q[topic][predicted_daily_hours]
    )
    # Save Q-table
    with open("q_table.pkl","wb") as f:
        pickle.dump(Q,f)
    st.success(f"Q-values updated for topic {topic}. Keep studying!")

# -------------------
# Show suggested daily plan table
# -------------------
days = int(np.ceil(predicted_days))
plan = pd.DataFrame({
    "Day": range(1, days+1),
    "Topic": [topic]*days,
    "Hours": [predicted_daily_hours]*days
})
st.dataframe(plan)
