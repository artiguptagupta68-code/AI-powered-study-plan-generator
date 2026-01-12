from datetime import datetime, timedelta

# ----------------- SAMPLE SYLLABUS -----------------
# Structure: Exam -> Subject -> Topic -> Details
syllabus = {
    "UPSC": {
        "Polity": {
            "Indian Constitution": {"estimated_time": 3, "practice_time": 1, "revision_time":1},
            "Parliament & Govt": {"estimated_time": 2, "practice_time": 1, "revision_time":1},
        },
        "Economy": {
            "Budget & Fiscal Policy": {"estimated_time": 2, "practice_time": 1, "revision_time":1},
            "Economic Survey": {"estimated_time": 3, "practice_time": 1, "revision_time":1},
        },
    },
    "GATE": {
        "Engineering Mathematics": {
            "Linear Algebra": {"estimated_time": 3, "practice_time": 1, "revision_time":1},
            "Calculus": {"estimated_time": 4, "practice_time": 1, "revision_time":1},
        },
        "Digital Logic": {
            "Boolean Algebra": {"estimated_time": 2, "practice_time": 1, "revision_time":1},
        }
    },
    "SSC": {
        "Quantitative Aptitude": {
            "Algebra": {"estimated_time": 2, "practice_time": 1, "revision_time":1},
            "Geometry": {"estimated_time": 3, "practice_time": 1, "revision_time":1},
        },
        "Reasoning": {
            "Puzzles": {"estimated_time": 2, "practice_time": 1, "revision_time":1},
        }
    }
}

# ----------------- STATUS TRACKER -----------------
# key: (exam, subject, topic)
topic_status = {}

for exam, subjects in syllabus.items():
    for subject, topics in subjects.items():
        for topic in topics:
            topic_status[(exam, subject, topic)] = {
                "status": "pending",
                "last_studied": None,
                "next_revision": []
            }

# ----------------- FUNCTIONS -----------------

def get_pending_topics(selected_subjects):
    pending = []
    for (exam, subject, topic), info in topic_status.items():
        if subject in selected_subjects and info["status"] == "pending":
            pending.append((exam, subject, topic))
    return pending

def assign_daily_topics(capacity, selected_subjects):
    assigned = []
    used = 0
    pending = get_pending_topics(selected_subjects)
    for k in pending:
        exam, subject, topic = k
        est_time = syllabus[exam][subject][topic]["estimated_time"] + syllabus[exam][subject][topic]["practice_time"]
        if used + est_time <= capacity:
            assigned.append(k)
            used += est_time
        else:
            break
    return assigned

def mark_completed(k):
    exam, subject, topic = k
    topic_status[k]["status"] = "completed"
    topic_status[k]["last_studied"] = datetime.now()
    topic_status[k]["next_revision"] = [
        datetime.now() + timedelta(days=1),
        datetime.now() + timedelta(days=3),
        datetime.now() + timedelta(days=7)
    ]
    print(f"✅ Completed: {exam} > {subject} > {topic}")

def add_delay(k):
    topic_status[k]["status"] = "delayed"
    print(f"⏱ Delayed: {k}")

def get_due_revisions():
    now = datetime.now()
    due = []
    for k, info in topic_status.items():
        if info["status"] == "completed":
            for rev in info["next_revision"]:
                if now >= rev:
                    due.append(k)
                    break
    return due

def show_progress():
    total = len(topic_status)
    completed = len([v for v in topic_status.values() if v["status"] == "completed"])
    pending = len([v for v in topic_status.values() if v["status"] == "pending"])
    delayed = len([v for v in topic_status.values() if v["status"] == "delayed"])
    print(f"\n📊 Progress: Total={total}, Completed={completed}, Pending={pending}, Delayed={delayed}\n")

# ----------------- MAIN LOOP -----------------
def daily_planner():
    while True:
        print("\n=== Adaptive Study Planner ===")
        show_progress()

        # Input daily capacity and subjects
        try:
            capacity = float(input("Enter your study capacity today (hours, e.g., 6): "))
        except:
            print("Invalid input!")
            continue

        print("\nAvailable subjects:")
        subjects_list = list({sub for _, sub, _ in topic_status})
        for i, s in enumerate(subjects_list):
            print(f"{i+1}. {s}")
        choices = input("Select subjects to study today (comma-separated numbers): ")
        try:
            selected_subjects = [subjects_list[int(c)-1] for c in choices.split(",")]
        except:
            print("Invalid selection!")
            continue

        # Assign topics
        assigned = assign_daily_topics(capacity, selected_subjects)
        if not assigned:
            print("No topics can fit in your capacity today or all topics are done!")
        else:
            print("\n📌 Topics assigned today:")
            for i, k in enumerate(assigned, 1):
                print(f"{i}. {k[0]} > {k[1]} > {k[2]}")

            # Mark completed / delayed
            for i, k in enumerate(assigned, 1):
                action = input(f"Did you complete topic {i}? (y = yes / n = delay): ").strip().lower()
                if action == "y":
                    mark_completed(k)
                else:
                    add_delay(k)

        # Show due revisions
        due = get_due_revisions()
        if due:
            print("\n🕑 Topics due for revision today:")
            for k in due:
                print(f"- {k[0]} > {k[1]} > {k[2]}")

        cont = input("\nDo you want to plan next day? (y/n): ").strip().lower()
        if cont != "y":
            break

# ----------------- RUN -----------------
if __name__ == "__main__":
    daily_planner()
