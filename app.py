import streamlit as st
from datetime import datetime, timedelta

# ------------------------------
# Step 1: Define the study plan
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
# Step 2: Generate plan with dates
# ------------------------------

def generate_plan(start_date_str):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    dynamic_plan = {}

    for exam, subjects in study_plan.items():
        dynamic_plan[exam] = {}
        for subject, topics in subjects.items():
            dynamic_plan[exam][subject] = []
            current_date = start_date
            for topic in topics:
                end_date = current_date + timedelta(days=topic["days"] - 1)
                dynamic_plan[exam][subject].append({
                    "topic": topic["topic"],
                    "start_date": current_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "status": "Pending"
                })
                current_date = end_date + timedelta(days=1)  # next topic starts the next day
    return dynamic_plan

# ------------------------------
# Step 3: Update completion
# ------------------------------

def mark_complete(plan, exam, subject, topic_name, actual_days=None):
    topics = plan[exam][subject]
    for i, topic in enumerate(topics):
        if topic["topic"] == topic_name:
            topic["status"] = "Completed"
            if actual_days:
                # Adjust next topics if actual days differ
                planned_days = (datetime.strptime(topic["end_date"], "%Y-%m-%d") - 
                                datetime.strptime(topic["start_date"], "%Y-%m-%d")).days + 1
                delta_days = actual_days - planned_days
                for j in range(i+1, len(topics)):
                    start = datetime.strptime(topics[j]["start_date"], "%Y-%m-%d") + timedelta(days=delta_days)
                    end = datetime.strptime(topics[j]["end_date"], "%Y-%m-%d") + timedelta(days=delta_days)
                    topics[j]["start_date"] = start.strftime("%Y-%m-%d")
                    topics[j]["end_date"] = end.strftime("%Y-%m-%d")
            break

# ------------------------------
# Step 4: Streamlit UI
# ------------------------------

st.title("📚 AI-Powered Study Plan Manager")

# Step 1: Select start date
start_date = st.date_input("Select start date for your study plan", datetime.today())

# Initialize session state for plan
if "plan" not in st.session_state:
    st.session_state.plan = generate_plan(start_date.strftime("%Y-%m-%d"))

st.subheader("Your Study Plan")
for exam, subjects in st.session_state.plan.items():
    st.markdown(f"### {exam}")
    for subject, topics in subjects.items():
        st.markdown(f"**{subject}**")
        for topic in topics:
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            with col1:
                st.text(topic["topic"])
            with col2:
                st.text(f"{topic['start_date']} → {topic['end_date']}")
            with col3:
                st.text(topic["status"])
            with col4:
                # Unique key ensures buttons inside loops work reliably
                button_key = f"{exam}-{subject}-{topic['topic']}-complete"
                if st.button("Mark Completed", key=button_key):
                    mark_complete(st.session_state.plan, exam, subject, topic["topic"])
                    st.success(f"Marked '{topic['topic']}' as completed!")

st.subheader("Adjust Topic Duration")
exam_select = st.selectbox("Exam", list(study_plan.keys()))
subject_select = st.selectbox("Subject", list(study_plan[exam_select].keys()))
topic_select = st.selectbox("Topic", [t["topic"] for t in st.session_state.plan[exam_select][subject_select]])
new_days = st.number_input("Actual days taken", min_value=1, value=1)
if st.button("Update Duration"):
    mark_complete(st.session_state.plan, exam_select, subject_select, topic_select, actual_days=new_days)
    st.success(f"Updated '{topic_select}' duration to {new_days} days")
