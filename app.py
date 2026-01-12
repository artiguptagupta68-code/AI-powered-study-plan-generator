import zipfile, os
import fitz  # PyMuPDF
from collections import defaultdict

ZIP_PATH = r"C:\Users\ASUS\Downloads\plan.zip"
EXTRACT_PATH = "syllabus_data"
os.makedirs(EXTRACT_PATH, exist_ok=True)

# Extract ZIP
with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
    zip_ref.extractall(EXTRACT_PATH)
print("✅ ZIP extracted successfully!")
def read_pdf_text(path):
    doc = fitz.open(path)
    lines = []
    for page in doc:
        for line in page.get_text("text").split("\n"):
            if line.strip():
                lines.append(line.strip())
    return lines

def build_syllabus_from_folder(root_path):
    syllabus = defaultdict(dict)
    for root, dirs, files in os.walk(root_path):
        exam_name = os.path.basename(root)
        for file in files:
            if file.endswith(".pdf"):
                subject_name = os.path.splitext(file)[0]
                pdf_path = os.path.join(root, file)
                lines = read_pdf_text(pdf_path)

                # Simple parsing: lines with colon are topics
                topics = defaultdict(list)
                current_topic = None
                for line in lines:
                    if ':' in line or len(line.split()) <= 6:
                        if current_topic:
                            topics[current_topic] = topics[current_topic]
                        current_topic = line
                    else:
                        if current_topic:
                            topics[current_topic].append(line)
                if current_topic:
                    topics[current_topic] = topics[current_topic]
                syllabus[exam_name][subject_name] = topics
    return syllabus

syllabus = build_syllabus_from_folder(EXTRACT_PATH)
print("✅ Syllabus tree built successfully!")
def calculate_estimated_time(syllabus):
    keyword_multiplier = {"advanced":1.5, "complex":1.3, "important":1.2}
    topic_times = {}

    for exam, subjects in syllabus.items():
        for subject, topics in subjects.items():
            for topic, subtopics in topics.items():
                # Base time = 0.1 hr per line in topic + subtopics
                num_lines = 1  # counting topic line itself
                num_lines += sum(len(st.split()) for st in subtopics)
                base_time = num_lines * 0.1  # hours

                # Adjust with keywords
                multiplier = 1.0
                for kw, m in keyword_multiplier.items():
                    if kw.lower() in topic.lower():
                        multiplier *= m
                est_time = round(base_time * multiplier, 2)
                
                # Practice time = 30% of estimated time
                practice_time = round(est_time * 0.3, 2)

                topic_times[(exam, subject, topic)] = {
                    "estimated_time": est_time,
                    "practice_time": practice_time,
                    "revision_time": 1,
                    "subtopics": subtopics,
                    "status": "pending",
                    "last_studied": None,
                    "next_revision": []
                }
    return topic_times

topic_status = calculate_estimated_time(syllabus)
print("✅ Estimated time calculated for all topics!")
def adjust_time_adaptively(topic_key, actual_hours_spent):
    old_est = topic_status[topic_key]["estimated_time"]
    # Update estimated time as weighted average
    topic_status[topic_key]["estimated_time"] = round((old_est + actual_hours_spent) / 2, 2)
    print(f"Adaptive update: {topic_key} new estimated time = {topic_status[topic_key]['estimated_time']} hr")
