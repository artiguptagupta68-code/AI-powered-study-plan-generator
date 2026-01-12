from datetime import datetime, timedelta
import pprint

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
                end_date = current_date + timedelta(days=topic["days"]-1)
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
    """
    Marks a topic complete and optionally adjusts next topics if it took different days.
    """
    topics = plan[exam][subject]
    for i, topic in enumerate(topics):
        if topic["topic"] == topic_name:
            topic["status"] = "Completed"
            if actual_days:
                # Calculate difference in days
                planned_days = (datetime.strptime(topic["end_date"], "%Y-%m-%d") - 
                                datetime.strptime(topic["start_date"], "%Y-%m-%d")).days + 1
                delta_days = actual_days - planned_days
                # Adjust next topics
                for j in range(i+1, len(topics)):
                    start = datetime.strptime(topics[j]["start_date"], "%Y-%m-%d") + timedelta(days=delta_days)
                    end = datetime.strptime(topics[j]["end_date"], "%Y-%m-%d") + timedelta(days=delta_days)
                    topics[j]["start_date"] = start.strftime("%Y-%m-%d")
                    topics[j]["end_date"] = end.strftime("%Y-%m-%d")
            break

# ------------------------------
# Step 4: Example usage
# ------------------------------

plan = generate_plan("2026-01-12")  # start date of plan
pprint.pprint(plan)  # print full plan

# Mark a topic completed early
mark_complete(plan, "GATE", "Control Systems", "Signals & Systems", actual_days=2)

print("\nUpdated plan after completing 'Signals & Systems' early:\n")
pprint.pprint(plan)
