import streamlit as st
import zipfile, os, fitz, requests
from collections import defaultdict
from datetime import datetime, timedelta

# -------------------------------
# 1) Streamlit: Google Drive ZIP link input
# -------------------------------
st.title("📚 Adaptive Study Planner for UPSC / GATE / SSC")
drive_link = st.text_input("Enter Google Drive file link for syllabus ZIP:")

syllabus = {}
topic_status = {}

if drive_link:
    try:
        # Extract file_id from Google Drive link
        file_id = drive_link.split("/d/")[1].split("/")[0]
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        
        # Download ZIP
        local_zip = "syllabus.zip"
        extract_dir = "syllabus_data"
        os.makedirs(extract_dir, exist_ok=True)

        response = requests.get(download_url)
        with open(local_zip, "wb") as f:
            f.write(response.content)
        st.success("✅ Syllabus ZIP downloaded successfully!")

        # Extract ZIP
        with zipfile.ZipFile(local_zip, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        st.success(f"📂 ZIP extracted to {extract_dir}")

    except Exception as e:
        st.error(f"❌ Error downloading or extracting ZIP: {e}")

    # -------------------------------
    # 2) Read PDFs and parse syllabus
    # -------------------------------
    def read_pdf_text(path):
        doc = fitz.open(path)
        lines = []
        for page in doc:
            for line in page.get_text("text").split("\n"):
                if line.strip():
                    lines.append(line.strip())
        return lines

    def build_syllabus(root_path):
        syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        for root, dirs, files in os.walk(root_path):
            exam = os.path.basename(root)
            if exam == "" or exam.startswith("."):
                continue

            for file in files:
                if file.lower().endswith(".pdf"):
                    subject = os.path.splitext(file)[0]
                    pdf_path = os.path.join(root, file)
                    pdf_lines = read_pdf_text(pdf_path)

                    current_topic = None
                    for line in pdf_lines:
                        line = line.strip()
                        if not line:
                            continue
                        # Heuristic: short lines or lines with ":" are topics
                        if ':' in line or len(line.split()) <= 6:
                            current_topic = line
                            syllabus[exam][subject][current_topic] = []
                        else:
                            if current_topic:
                                syllabus[exam][subject][current_topic].append(line)

        return syllabus

    syllabus = build_syllabus(extract_dir)
    st.success("📚 Syllabus parsed successfully!")

    # -------------------------------
    # 3) Calculate estimated time
    # -------------------------------
    def calc_estimated_time(syllabus):
        keyword_multiplier = {"advanced":1.5, "complex":1.3, "important":1.2}
        topic_status = {}
        for exam, subjects in syllabus.items():
            for subject, topics in subjects.items():
                for topic, subtopics in topics.items():
                    num_lines = 1 + sum(len(s.split()) for s in subtopics)
                    base_time = num_lines * 0.1
                    mult = 1.0
                    for kw, m in keyword_multiplier.items():
                        if kw in topic.lower():
                            mult *= m
                    est = round(base_time * mult, 2)
                    practice = round(est * 0.3, 2)
                    topic_status[(exam, subject, topic)] = {
                        "estimated_time": est,
                        "practice_time": practice,
                        "revision_time": 1,
                        "status": "pending",
                        "last_studied": None,
                        "next_revision": []
                    }
        return topic_status

    topic_status = calc_estimated_time(syllabus)
    st.success("🕒 Estimated times calculated for topics!")

    # -------------------------------
    # 4) Streamlit UI for daily planner
    # -------------------------------
    st.subheader("📌 Daily Planner")

    # Select daily study capacity
    capacity = st.number_input("Enter study capacity today (hours):", min_value=1.0, value=6.0, step=0.5)

    # Select subjects
    all_subjects = list({sub for _, sub, _ in topic_status})
    selected_subjects = st.multiselect("Select subjects to study today:", all_subjects)

    if st.button("Assign Topics"):
        # Assign topics based on capacity
        def assign_daily_topics(capacity, selected_subjects):
            assigned = []
            used = 0
            pending = [k for k,v in topic_status.items() if v['status']=='pending' and k[1] in selected_subjects]
            for k in pending:
                est_time = topic_status[k]['estimated_time'] + topic_status[k]['practice_time']
                if used + est_time <= capacity:
                    assigned.append(k)
                    used += est_time
                else:
                    break
            return assigned

        assigned_topics = assign_daily_topics(capacity, selected_subjects)

        if assigned_topics:
            st.write("📌 **Topics assigned today:**")
            for k in assigned_topics:
                st.write(f"- {k[0]} > {k[1]} > {k[2]} | Est: {topic_status[k]['estimated_time']}h, Practice: {topic_status[k]['practice_time']}h")

            # Complete / Delay checkboxes
            for k in assigned_topics:
                completed = st.checkbox(f"Completed: {k[0]} > {k[1]} > {k[2]}", key=str(k))
                if completed:
                    topic_status[k]['status'] = 'completed'
                    topic_status[k]['last_studied'] = datetime.now()
                    topic_status[k]['next_revision'] = [
                        datetime.now() + timedelta(days=1),
                        datetime.now() + timedelta(days=3),
                        datetime.now() + timedelta(days=7)
                    ]
        else:
            st.info("No topics fit your capacity today or all topics are done!")

        # Show progress
        total = len(topic_status)
        completed = len([v for v in topic_status.values() if v['status']=='completed'])
        pending = len([v for v in topic_status.values() if v['status']=='pending'])
        delayed = len([v for v in topic_status.values() if v['status']=='delayed'])
        st.subheader("📊 Progress")
        st.write(f"Total: {total} | Completed: {completed} | Pending: {pending} | Delayed: {delayed}")

        # Show revisions due
        now = datetime.now()
        due = []
        for k, info in topic_status.items():
            if info['status']=='completed':
                for rev in info['next_revision']:
                    if now >= rev:
                        due.append(k)
                        break
        if due:
            st.subheader("🕑 Topics due for revision today:")
            for k in due:
                st.write(f"- {k[0]} > {k[1]} > {k[2]}")
