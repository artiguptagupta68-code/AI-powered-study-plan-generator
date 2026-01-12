import streamlit as st
import pandas as pd

# -------------------------------
# COMPLETE SYLLABUS DATA
# -------------------------------
SYLLABUS = {

    "UPSC CSE": {
        "Polity": [
            "Constitution", "Fundamental Rights", "Parliament",
            "Judiciary", "Federalism", "Governance"
        ],
        "History": [
            "Ancient History", "Medieval History",
            "Modern History", "World History"
        ],
        "Geography": [
            "Physical Geography", "Indian Geography",
            "World Geography", "Environment Geography"
        ],
        "Economy": [
            "Indian Economy", "Budget",
            "Economic Survey", "Planning"
        ],
        "Environment": [
            "Ecology", "Biodiversity",
            "Climate Change", "Environmental Policies"
        ],
        "Science & Technology": [
            "Biotechnology", "Space Technology",
            "Defence Technology", "IT & AI"
        ]
    },

    "SSC": {
        "Quantitative Aptitude": [
            "Number System", "Percentage", "Profit & Loss",
            "Time & Work", "Algebra", "Geometry"
        ],
        "Reasoning": [
            "Analogy", "Series", "Coding-Decoding",
            "Blood Relations", "Puzzles"
        ],
        "English": [
            "Grammar", "Vocabulary", "Reading Comprehension",
            "Sentence Improvement"
        ],
        "General Awareness": [
            "History", "Geography", "Polity",
            "Economy", "Current Affairs"
        ]
    },

    "GATE": {
        "Engineering Mathematics": [
            "Linear Algebra", "Calculus",
            "Probability", "Differential Equations"
        ],
        "Core Subject 1": [
            "Subject Topic 1", "Subject Topic 2",
            "Subject Topic 3"
        ],
        "Core Subject 2": [
            "Advanced Topic 1", "Advanced Topic 2"
        ],
        "General Aptitude": [
            "Verbal Ability", "Numerical Ability"
        ]
    }
}

# -------------------------------
# STREAMLIT UI
# -------------------------------
st.set_page_config(page_title="AI Study Plan Generator")
st.title("📘 AI-Powered Personalized Study Plan")
st.write("Syllabus-based adaptive study planning")

exam = st.selectbox("Select Exam", list(SYLLABUS.keys()))

st.subheader("📊 Enter Your Accuracy (%) Per Subject")

performance = {}

for subject in SYLLABUS[exam]:
    performance[subject] = st.slider(
        subject, 0, 100, 50
    )

# -------------------------------
# STUDY PLAN LOGIC
# -------------------------------
if st.button("Generate Study Plan"):

    df = pd.DataFrame({
        "Subject": performance.keys(),
        "Accuracy (%)": performance.values()
    })

    df["Weakness Score"] = 100 - df["Accuracy (%)"]
    df = df.sort_values("Weakness Score", ascending=False)

    total_study_hours = 6
    df["Daily Hours"] = (
        df["Weakness Score"] / df["Weakness Score"].sum()
    ) * total_study_hours

    st.subheader("📅 Personalized Daily Study Plan")
    st.dataframe(df)

    # ---------------------------
    # SUBJECT-WISE BREAKDOWN
    # ---------------------------
    st.subheader("📚 Topic-Level Focus")

    for subject in df["Subject"]:
        if performance[subject] < 60:
            st.warning(f"🔴 {subject}")
            st.write(", ".join(SYLLABUS[exam][subject]))
        else:
            st.success(f"🟢 {subject} – Maintain & Revise")

    st.info(
        "🔁 Study plan auto-adjusts after each mock test or quiz."
    )

print ("Study plan auto-adjusts after each mock test or quiz")
