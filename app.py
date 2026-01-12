import streamlit as st
import numpy as np

# -------------------------------
# SAMPLE SYLLABUS STRUCTURE
# -------------------------------
SYLLABUS = {
    "UPSC": {
        "Polity": ["Constitution", "Parliament", "Judiciary"],
        "History": ["Ancient", "Medieval", "Modern"],
        "Geography": ["Physical", "Indian", "World"],
    },
    "SSC": {
        "Quantitative Aptitude": ["Percentage", "Profit & Loss", "Algebra"],
        "Reasoning": ["Analogy", "Series", "Puzzles"],
        "English": ["Grammar", "Vocabulary", "Comprehension"],
    }
}

# -------------------------------
# SIMULATED STUDENT DATA (DAYS TAKEN)
# -------------------------------
STUDENT_DATA = {
    "Constitution": [5, 6, 6, 5, 7],
    "Parliament": [4, 5, 5, 4, 6],
    "Judiciary": [6, 7, 6, 5, 6],
    "Ancient": [3, 4, 4, 3, 5],
    "Medieval": [4, 4, 5, 5, 6],
    "Modern": [5, 6, 6, 7, 6],
    "Physical": [2, 3, 3, 2, 3],
    "Indian": [3, 4, 4, 3, 4],
    "World": [4, 5, 5, 4, 5],
    "Percentage": [1, 1, 2, 1, 2],
    "Profit & Loss": [2, 2, 3, 2, 3],
    "Algebra": [2, 3, 3, 2, 4],
    "Analogy": [1, 1, 2, 1, 2],
    "Series": [2, 2, 2, 2, 3],
    "Puzzles": [2, 3, 3, 2, 3],
    "Grammar": [1, 2, 2, 1, 2],
    "Vocabulary": [1, 1, 1, 1, 2],
    "Comprehension": [2, 2, 3, 2, 3]
}

# -------------------------------
# STREAMLIT CONFIG
# -------------------------------
st.set_page_config(page_title="Adaptive Study Planner")
st.title("📘 Adaptive Study Planner")
st.caption("Select your exam, subject, and topic to get a personalized study plan.")

# -------------------------------
# USER INPUTS
# -------------------------------
exam_selected = st.selectbox("Select Exam", list(SYLLABUS.keys()))
subject_selected = st.selectbox("Select Subject", list(SYLLABUS[exam_selected].keys()))
topic_selected = st.selectbox("Select Topic", SYLLABUS[exam_selected][subject_selected])

free_hours = st.slider("Available Free Hours per Day", 1, 8, 2)

# -------------------------------
# PREDICTION LOGIC
# -------------------------------
if st.button("Predict Study Plan"):
    if topic_selected in STUDENT_DATA:
        past_days = STUDENT_DATA[topic_selected]
        num_students = len(past_days)
        avg_days = np.mean(past_days)
        min_days = np.min(past_days)
        max_days = np.max(past_days)

        # Assume students studied 2 hours/day
        avg_hours_per_day_by_students = 2
        total_hours_needed = avg_days * avg_hours_per_day_by_students

        # Calculate expected total days based on user's free hours
        expected_total_days = total_hours_needed / free_hours
        predicted_daily_hours = min(free_hours, total_hours_needed / expected_total_days)

        st.subheader("📊 Topic-wise Prediction")
        st.markdown(f"- **Number of students studied this topic**: {num_students}")
        st.markdown(f"- **Average days taken**: {avg_days:.1f} days")
        st.markdown(f"- **Min days taken**: {min_days} days")
        st.markdown(f"- **Max days taken**: {max_days} days")
        st.markdown(f"- **Predicted daily study hours for you**: {predicted_daily_hours:.1f} hours/day")
        st.markdown(f"- **Expected total days to complete**: {expected_total_days:.1f} days")
    else:
        st.warning("No student data available for this topic.")

# -------------------------------
# OPTIONAL: DAY-WISE SCHEDULE
# -------------------------------
st.subheader("📅 Suggested Day-wise Schedule")
if topic_selected in STUDENT_DATA:
    expected_total_days = np.ceil(total_hours_needed / free_hours)
    daily_hours = min(free_hours, total_hours_needed / expected_total_days)
    schedule = pd.DataFrame({
        "Day": list(range(1, int(expected_total_days) + 1)),
        "Topic": [topic_selected] * int(expected_total_days),
        "Study Hours": [daily_hours] * int(expected_total_days)
    })
    st.dataframe(schedule.round(2))
