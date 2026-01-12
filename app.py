import streamlit as st
from datetime import datetime, timedelta

# ------------------------------
# Study plan
# ------------------------------
study_plan = {
    "GATE": {
        "Control Systems": [
            {"topic": "Signals & Systems", "days": 3},
            {"topic": "Time Response Analysis", "days": 4},
            {"topic": "Frequency Response", "days": 5},
            {"topic": "Control Design & Compensation", "days": 5}
        ],
        "Engineering Mathematics": [
            {"topic": "Linear Algebra", "days": 3},
            {"topic": "Calculus", "days": 3},
            {"topic": "Differential Equations", "days": 3},
            {"topic": "Probability & Statistics", "days": 3},
            {"topic": "Numerical Methods", "days": 3}
        ]
    },
    "UPSC": {
        "History": [
            {"topic": "Ancient", "days": 3},
            {"topic": "Medieval", "days": 3},
            {"topic": "Modern", "days": 4}
        ],
        "Geography": [
            {"topic": "Physical", "days": 3},
            {"topic": "Human", "days": 3}
        ]
    },
    "SSC": {
        "Quantitative Aptitude": [
            {"topic": "Arithmetic", "days": 5},
            {"topic": "Algebra", "days": 4},
            {"topic": "Geometry", "days": 4},
            {"topic": "Data Interpretation", "days": 3}
        ],
        "Reasoning": [
            {"topic": "Verbal Reasoning", "days": 3},
            {"topic": "Non-Verbal Reasoning", "days": 3}
        ]
    }
}

# ------------------------------
# Functions
# ------------------------------

def generate_subject_plan(subject_topics, start_date):
    """Generates a plan for a single subject starting from start_date"""
    plan = []
    current_date = start_date
    for topic in subject_topics:
        end_date = current_date + timedelta(days=topic["days"]-1)
        plan.append({
            "topic": topic["topic"],
            "planned_days": topic["days"],
            "start_date": current_date,
            "end_date": end_date,
            "status": "Pending",
            "actual_days": None
        })
        current_date = end_date + timedelta(days=1)
    return plan

def update_topic(plan, topic_name, actual_days):
    """Updates a topic's completion and adjusts subsequent topic dates"""
    for i, topic in enumerate(plan):
        if topic["topic"] == topic_name:
            topic["status"] = "Completed"
            topic["actual_days"] = actual_days
            delta = actual_days - topic["planned_days"]
            # Shift subsequent topics
            for j in range(i+1, len(plan)):
                plan[j]["start_date"] += timedelta(days=delta)
                plan[j]["end_date"] += timedelta(days=delta)
            break

def calculate_subject_end(plan):
    """Returns current end date of subject (last topic's end_date)"""
    if not plan:
        return None
    return plan[-1]["end_date"]

# ------------------------------
# Streamlit UI
# ------------------------------

st.title("📚 Dynamic Study Plan Tracker")

# Step 1: Select exam and subject
exam_select = st.selectbox("Select Exam", list(study_plan.keys()))
subject_select = st.selectbox("Select Subject", list(study_plan[exam_select].keys()))

# Step 2: Pick start date for the subject individually
subject_start_date = st.date_input(f"Select start date for {subject_select}")

# Initialize subject plan in session state
if "subject_plan" not in st.session_state:
    st.session_state.subject_plan = {}
if subject_select not in st.session_state.subject_plan:
    st.session_state.subject_plan[subject_select] = generate_subject_plan(
        study_plan[exam_select][subject_select],
        subject_start_date
    )

plan = st.session_state.subject_plan[subject_select]

# Step 3: Display subject plan and mark progress
st.subheader(f"{subject_select} Plan")
for topic in plan:
    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
    with col1:
        st.text(topic["topic"])
    with col2:
        st.text(f"{topic['start_date'].strftime('%Y-%m-%d')} → {topic['end_date'].strftime('%Y-%m-%d')}")
    with col3:
        st.text(topic["status"])
    with col4:
        st.text(topic["actual_days"] if topic["actual_days"] else "-")
    with col5:
        btn_key = f"{topic['topic']}_complete"
        actual_days_input = st.number_input(f"Days taken for {topic['topic']}", min_value=1, value=topic["planned_days"], key=f"{topic['topic']}_days")
        if st.button("Mark Completed", key=btn_key):
            update_topic(plan, topic["topic"], actual_days_input)
            st.success(f"Updated {topic['topic']}")

# Step 4: Show dynamic subject completion date
subject_end = calculate_subject_end(plan)
st.subheader(f"Estimated Completion Date for {subject_select}: {subject_end.strftime('%Y-%m-%d') if subject_end else 'N/A'}")
