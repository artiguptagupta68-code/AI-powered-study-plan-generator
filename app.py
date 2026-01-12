from datetime import datetime, timedelta

# ----------------------
# 1) Already have topic_status from syllabus PDF parsing
# ----------------------

# topic_status = { (exam, subject, topic): {...} }

# ----------------------
# 2) Planner functions
# ----------------------
def get_pending_topics(selected_subjects):
    return [k for k,v in topic_status.items() if v['status']=='pending' and k[1] in selected_subjects]

def assign_daily_topics(capacity, selected_subjects):
    assigned = []
    used = 0
    pending = get_pending_topics(selected_subjects)
    for k in pending:
        est_time = topic_status[k]['estimated_time'] + topic_status[k]['practice_time']
        if used + est_time <= capacity:
            assigned.append(k)
            used += est_time
        else:
            break
    return assigned

def mark_completed(k):
    topic_status[k]['status'] = 'completed'
    topic_status[k]['last_studied'] = datetime.now()
    topic_status[k]['next_revision'] = [
        datetime.now() + timedelta(days=1),
        datetime.now() + timedelta(days=3),
        datetime.now() + timedelta(days=7)
    ]
    print(f"✅ Completed: {k[0]} > {k[1]} > {k[2]}")

def add_delay(k):
    topic_status[k]['status'] = 'delayed'
    print(f"⏱ Delayed: {k}")

def get_due_revisions():
    now = datetime.now()
    due = []
    for k, info in topic_status.items():
        if info['status']=='completed':
            for rev in info['next_revision']:
                if now >= rev:
                    due.append(k)
                    break
    return due

def adjust_time_adaptively(k, actual_hours):
    old = topic_status[k]['estimated_time']
    topic_status[k]['estimated_time'] = round((old + actual_hours)/2,2)
    print(f"🛠 Adaptive update: {k} new est. time = {topic_status[k]['estimated_time']} hr")

def show_progress():
    total = len(topic_status)
    completed = len([v for v in topic_status.values() if v['status']=='completed'])
    pending = len([v for v in topic_status.values() if v['status']=='pending'])
    delayed = len([v for v in topic_status.values() if v['status']=='delayed'])
    print(f"\n📊 Progress → Total:{total} | Completed:{completed} | Pending:{pending} | Delayed:{delayed}")

# ----------------------
# 3) Daily planner loop
# ----------------------
def daily_planner():
    while True:
        print("\n=== Adaptive Study Planner ===")
        show_progress()

        # Daily capacity
        try:
            capacity = float(input("Enter study capacity today (hrs): "))
        except:
            print("❌ Invalid input!")
            continue

        # Select subjects
        subjects_list = list({sub for _,sub,_ in topic_status})
        print("\nAvailable subjects:")
        for i,s in enumerate(subjects_list):
            print(f"{i+1}. {s}")
        choices = input("Select subjects to study (comma-separated numbers): ")
        try:
            selected_subjects = [subjects_list[int(c)-1] for c in choices.split(",")]
        except:
            print("❌ Invalid selection!")
            continue

        # Assign topics
        assigned = assign_daily_topics(capacity, selected_subjects)
        if not assigned:
            print("No topics fit in your capacity today or all topics done!")
        else:
            print("\n📌 Topics assigned today:")
            for i,k in enumerate(assigned,1):
                print(f"{i}. {k[0]} > {k[1]} > {k[2]}")

            # Complete/delay input
            for i,k in enumerate(assigned,1):
                action = input(f"Did you complete topic {i}? (y = yes / n = delay): ").strip().lower()
                if action=='y':
                    mark_completed(k)
                    try:
                        actual_hours = float(input("Enter actual hours spent: "))
                        adjust_time_adaptively(k, actual_hours)
                    except:
                        pass
                else:
                    add_delay(k)

        # Revisions
        due = get_due_revisions()
        if due:
            print("\n🕑 Topics due for revision today:")
            for k in due:
                print(f"- {k[0]} > {k[1]} > {k[2]}")

        cont = input("\nPlan next day? (y/n): ").strip().lower()
        if cont != 'y':
            break

# ----------------------
# 4) Run
# ----------------------
if __name__=="__main__":
    daily_planner()
