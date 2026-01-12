import requests, zipfile, os, fitz
from collections import defaultdict

# -----------------------
# 1) Download from Drive
# -----------------------

file_id = "1IRP5upBPCua57WmoEfjn9t6YJQq0_yGB"
download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

local_zip = "plan.zip"
extract_dir = "syllabus_data"
os.makedirs(extract_dir, exist_ok=True)

print("📥 Downloading syllabus ZIP from Drive...")

response = requests.get(download_url)
with open(local_zip, "wb") as f:
    f.write(response.content)

print("✅ Download complete!")

# -----------------------
# 2) Extract ZIP
# -----------------------

with zipfile.ZipFile(local_zip, 'r') as zip_ref:
    zip_ref.extractall(extract_dir)

print("📂 ZIP extracted to:", extract_dir)

# -----------------------
# 3) Read PDF text
# -----------------------

def read_pdf_text(path):
    doc = fitz.open(path)
    lines = []
    for page in doc:
        text = page.get_text("text")
        for line in text.split("\n"):
            if line.strip():
                lines.append(line.strip())
    return lines

# -----------------------
# 4) Build syllabus tree
# -----------------------

def build_syllabus(root_path):
    syllabus = defaultdict(dict)

    for root, dirs, files in os.walk(root_path):
        exam = os.path.basename(root)

        for file in files:
            if file.lower().endswith(".pdf"):
                subject = os.path.splitext(file)[0]
                pdf_path = os.path.join(root, file)

                pdf_lines = read_pdf_text(pdf_path)

                # simple heuristic: lines with ':' or short lines as topic
                topics = defaultdict(list)
                current_topic = None

                for line in pdf_lines:
                    # treat lines with colon OR <=6 words as topic
                    if ':' in line or len(line.split()) <= 6:
                        if current_topic:
                            topics[current_topic] = topics[current_topic]
                        current_topic = line
                    else:
                        if current_topic:
                            topics[current_topic].append(line)

                if current_topic:
                    topics[current_topic] = topics[current_topic]

                syllabus[exam][subject] = topics

    return syllabus

syllabus = build_syllabus(extract_dir)
print("📚 Syllabus tree built.")

# -----------------------
# 5) Estimate time per topic
# -----------------------

def calc_estimated_time(syllabus):
    keyword_multiplier = {"advanced":1.5, "complex":1.3, "important":1.2}
    topic_status = {}

    for exam, subjects in syllabus.items():
        for subject, topics in subjects.items():
            for topic, subtopics in topics.items():
                num_lines = 1 + sum(len(s.split()) for s in subtopics)
                base_time = num_lines * 0.1  # ~0.1 hr per line

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
print("🕒 Estimated times calculated for topics.")

# Example output
for k,v in list(topic_status.items())[:5]:
    print(k, "→", v)
