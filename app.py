import streamlit as st
from dataclasses import dataclass, field
from typing import List
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="Dynamic Study Planner", layout="wide")

# ---------------- DATA MODELS ---------------- #

@dataclass
class SubTopic:
    name: str
    study: int
    free: int
    practice: int
    status: str = "Pending"

    @property
    def total_time(self):
        return self.study + self.free + self.practice


@dataclass
class Topic:
    name: str
    subtopics: List[SubTopic] = field(default_factory=list)

    def next_subtopic(self):
        for s in self.subtopics:
            if s.status != "Completed":
                return s
        return None


@dataclass
class Subject:
    name: str
    topics: List[Topic]
    revision: int

    @property
    def total_time(self):
        return sum(
            s.total_time
            for t in self.topics
            for s in t.subtopics
        ) + self.revision


@dataclass
class Exam:
    name: str
    subjects: List[Subject]


# ---------------- UTILS ---------------- #

def load_syllabus_from_url(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        return [li.text.strip() for li in soup.find_all("li")[:20]]
    except:
        return []


def assign_tasks(subjects, capacity):
    assigned = []
    remaining = capacity

    for subject in subjects:
        for topic in subject.topics:
            sub = topic.next_subtopic()
            if sub and sub.total_time <= remaining:
                assigned.append((subject, topic, sub))
                sub.status = "In Progress"
                remaining -= sub.total_time

    return assigned


# ---------------- SESSION STATE ---------------- #

if "exam" not in st.session_state:
    st.session_state.exam = None

# ---------------- UI ---------------- #

st.title("📚 Dynamic UPSC / GATE / SSC Study Planner")

# ----------- EXAM CREATION ----------- #

with st.sidebar:
    st.header("⚙️ Setup")

    exam_name = st.text_input("Exam Name", "UPSC")

    if st.button("Create Exam"):
        st.session_state.exam = Exam(exam_name, [])
        st.success("Exam created")

# ----------- SUBJECT CREATION ----------- #

if st.session_state.exam:
    st.subheader(f"🎯 Exam: {st.session_state.exam.name}")

    with st.expander("➕ Add Subject"):
        sub_name = st.text_input("Subject Name")
        revision = st.number_input("Revision Time (hrs)", 0, 50, 3)

        if st.button("Add Subject"):
            st.session_state.exam.subjects.append(
                Subject(sub_name, [], revision)
            )
            st.success("Subject added")

# ----------- TOPIC & SUBTOPIC ----------- #

for subject in st.session_state.exam.subjects if st.session_state.exam else []:
    with st.expander(f"📘 {subject.name} (Total: {subject.total_time} hrs)"):

        topic_name = st.text_input(f"Topic name for {subject.name}", key=subject.name)
        if st.button("Add Topic", key=f"add_{subject.name}"):
            subject.topics.append(Topic(topic_name))
            st.success("Topic added")

        for topic in subject.topics:
            st.markdown(f"### 🔹 {topic.name}")

            c1, c2, c3 = st.columns(3)
            sub_name = c1.text_input("Subtopic", key=f"{topic.name}_name")
            study = c2.number_input("Study hrs", 0, 20, 2, key=f"{topic.name}_study")
            practice = c3.number_input("Practice hrs", 0, 20, 1, key=f"{topic.name}_prac")
            free = st.number_input("Free days", 0, 10, 1, key=f"{topic.name}_free")

            if st.button("Add Subtopic", key=f"{topic.name}_add"):
                topic.subtopics.append(SubTopic(sub_name, study, free, practice))
                st.success("Subtopic added")

            for s in topic.subtopics:
                st.write(
                    f"➡️ {s.name} | ⏱ {s.total_time} hrs | 📌 {s.status}"
                )

# ----------- DAILY STUDY ALLOCATION ----------- #

st.subheader("🗓️ Daily Study Allocation")

daily_capacity = st.number_input("Daily Study Capacity (hrs)", 1, 24, 6)

if st.button("Assign Today's Study"):
    tasks = assign_tasks(st.session_state.exam.subjects, daily_capacity)
    if tasks:
        st.success("Tasks assigned")
        for subj, top, sub in tasks:
            st.write(f"✅ {subj.name} → {top.name} → {sub.name}")
    else:
        st.warning("No tasks available")

# ----------- UPDATE PROGRESS ----------- #

st.subheader("🔄 Update Progress")

for subject in st.session_state.exam.subjects if st.session_state.exam else []:
    for topic in subject.topics:
        for sub in topic.subtopics:
            if sub.status == "In Progress":
                col1, col2 = st.columns(2)
                if col1.button(f"✔ Complete {sub.name}"):
                    sub.status = "Completed"
                    st.success("Marked Completed")
                if col2.button(f"⏳ Delay {sub.name}"):
                    sub.free += 1
                    sub.status = "Pending"
                    st.warning("Extended by 1 day")

# ----------- SYLLABUS FETCH ----------- #

st.subheader("🌐 Load Syllabus from Website")

url = st.text_input("Syllabus URL")
if st.button("Fetch Syllabus"):
    syllabus = load_syllabus_from_url(url)
    if syllabus:
        st.success("Syllabus loaded")
        for item in syllabus:
            st.write("•", item)
    else:
        st.error("Could not fetch syllabus")
