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
    """Generates plan for a single subject starting from start_date"""
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

def recalc_plan(plan):
    """Recalculates all topic dates based on planned_days or actual_days"""
    current_date = plan[0]["start_date"]
    for topic in plan:
        # Always use actual_days if entered, else planned_days
        days = topic["actual_days"] if topic["actual_days"] is not None else topic["planned_days"]
        topic["start_date"] = current_date
        topic["end_date"] = current_date + timedelta(days=days-1)
        current_date = topic["end_date"] + timedelta(days=1)

def mark_topic(plan, topic_name, actual_days):
    """Marks topic completed and updates future dates"""
    for topic in plan:
        if topic["topic"] == topic_name:
            topic["status"] = "Completed"
            topic["actual_days"] = actual_days
            break
    recalc_plan(plan)

def calculate_subject_end(plan):
    """Returns current end date of subject"""
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

# Initialize session state for subject plan
if "subject_plan" not in st.session_state:
    st.session_state.subject_plan = {}
if subject_select not in st.session_state.subject_plan:
    st.session_state.subject_plan[subject_select] = generate_subject_plan(
        study_plan[exam_select][subject_select],
        subject_start_date
    )
else:
    # Update start date if changed
    st.session_state.subject_plan[subject_select][0]["start_date"] = subject_start_date
    recalc_plan(st.session_state.subject_plan[subject_select])

plan = st.session_state.subject_plan[subject_select]

# Step 3: Display plan table with proper columns
st.subheader(f"{subject_select} Plan")
st.markdown(
    "| Topic | Start Date | End Date | Status | Planned Days | Actual Days | Action |\n"
    "|-------|------------|----------|--------|--------------|------------|--------|"
)

for i, topic in enumerate(plan):
    col1, col2, col3, col4, col5, col6, col7 = st.columns([3, 2, 2, 2, 2, 2, 2])
    with col1:
        st.text(topic["topic"])
    with col2:
        st.text(topic["start_date"].strftime("%Y-%m-%d"))
    with col3:
        st.text(topic["end_date"].strftime("%Y-%m-%d"))
    with col4:
        st.text(topic["status"])
    with col5:
        # Planned Days input
        planned_key = f"planned_{subject_select}_{i}"
        planned = st.number_input(f"", min_value=1, value=topic["planned_days"], key=planned_key)
        topic["planned_days"] = planned
    with col6:
        # Actual Days input (affects dynamic recalculation immediately)
        actual_key = f"actual_{subject_select}_{i}"
        actual_val = topic["actual_days"] if topic["actual_days"] is not None else topic["planned_days"]
        actual = st.number_input(f"", min_value=1, value=actual_val, key=actual_key)
        # Update actual_days even if topic is not completed yet
        topic["actual_days"] = actual
    with col7:
        # Mark Completed button
        btn_key = f"{subject_select}_{topic['topic']}_complete"
        if st.button("Mark Completed", key=btn_key):
            mark_topic(plan, topic["topic"], topic["actual_days"])
            st.success(f"Marked '{topic['topic']}' completed.")

# Step 4: Recalculate subject end dynamically
recalc_plan(plan)
subject_end = calculate_subject_end(plan)
st.subheader(f"Estimated Completion Date for {subject_select}: {subject_end.strftime('%Y-%m-%d') if subject_end else 'N/A'}")
