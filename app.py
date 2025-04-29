import streamlit as st
import fitz
from PDF_extractor import (
    extract_text_from_pdf,
    clean_text,
    summarize_text,
    generate_questions_from_summary,
    grade_answer,
    create_polished_pdf,
    is_copied_from_summary,
    highlight_copied_parts,
)
import tempfile
import openai
import os
import re

# --- Page Config ---
st.set_page_config(page_title="PDF Summarizer & Quiz Generator", layout="centered")
st.title("📄 PDF Summarizer & Quiz Generator")

# --- API Key Prompt ---
if "api_key_validated" not in st.session_state or not st.session_state.api_key_validated:
    api_key = st.text_input(
        "Enter your OpenAI API Key:", placeholder="sk-...", type="password"
    )
    if not api_key:
        st.warning("Please enter your API key to proceed.")
        st.stop()
    client = openai.OpenAI(api_key=api_key)
    try:
        client.models.list()
        st.session_state.api_key_validated = True
        st.session_state.api_key = api_key
        st.rerun()
    except openai.AuthenticationError:
        st.error("Invalid API key. Please enter a valid OpenAI API key.")
        st.stop()
    except openai.OpenAIError as e:
        st.error(f"OpenAI Error: {str(e)}")
        st.stop()
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        st.stop()
else:
    api_key = st.session_state.api_key
    client = openai.OpenAI(api_key=api_key)

# Ensure downstream OpenAI calls pick up the key
os.environ["OPENAI_API_KEY"] = api_key

# --- PDF Upload ---
api_success = st.success("✅ API Key validated successfully! You can now upload your PDF.")
uploaded_file = st.file_uploader("Upload your PDF file (max 5 pages)", type="pdf")

if uploaded_file:
    api_success.empty()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    try:
        pdf_doc = fitz.open(tmp_path)
        if pdf_doc.page_count > 5:
            st.error("The PDF exceeds 5 pages. Please upload up to 5 pages.")
            st.stop()
    except Exception:
        st.error("Error opening PDF. Please check the file and try again.")
        st.stop()

    # --- Summarize ---
    if "summary" not in st.session_state:
        with st.spinner("PDF Uploaded Successfully! Generating summary..."):
            raw = extract_text_from_pdf(tmp_path)
            cleaned = clean_text(raw)
            summary = summarize_text(cleaned)
            st.session_state.summary = summary
    summary = st.session_state.summary

    # --- Summary vs Quiz Toggle ---
    quiz_active = st.session_state.get("questions_generated", False) and not st.session_state.get("graded_all", False)
    show_questions = st.session_state.get("questions_generated", False)

    # Display checkbox only before quiz generation or after grading reset
    if not quiz_active and not show_questions:
        if st.checkbox("Would you like to generate questions based on this summary?", key="show_questions_checkbox"):
            st.session_state.questions_generated = True
            # clear any prior grading flag
            st.session_state.pop("graded_all", None)
            st.rerun()

    # --- Render Content ---
    if not show_questions:
        st.subheader("📝 Summary")
        st.write(summary)
        buffer = create_polished_pdf(summary, title="Generated Summary")
        st.download_button(
            label="Download Summary as PDF",
            data=buffer,
            file_name="summary.pdf",
            mime="application/pdf",
        )
    else:
        # --- Quiz Settings ---
        if "quiz_settings_locked" not in st.session_state:
            st.session_state.quiz_settings_locked = False
        if not st.session_state.quiz_settings_locked:
            st.subheader("🛠 Customize Your Quiz")
            num_q = st.text_input("How many questions?", key="num_q_input")
            pts_q = st.text_input("Points per question?", key="pts_q_input")
            if st.button("✅ Confirm Settings", key="confirm_settings_button"):
                try:
                    n = int(num_q)
                    p = int(pts_q)
                    if n <= 0 or p <= 0:
                        st.error("Enter positive integers.")
                        st.stop()
                    st.session_state.num_questions = n
                    st.session_state.points_per_question = p
                    st.session_state.quiz_settings_locked = True
                    st.rerun()
                except ValueError:
                    st.error("Please enter valid integers.")
                    st.stop()
        else:
            # --- Generate Questions ---
            if "questions_text" not in st.session_state:
                with st.spinner("Generating questions..."):
                    qt = generate_questions_from_summary(
                        st.session_state.summary,
                        num_questions=st.session_state.num_questions,
                        points_per_question=st.session_state.points_per_question,
                    )
                    st.session_state.questions_text = qt
            questions = st.session_state.questions_text.split("\n")

            st.subheader("🧠 Questions")
            for i, ques in enumerate(questions):
                st.markdown(f"**Q{ques.strip()}**")
                st.session_state.setdefault(f"answer_{i}", "")
                st.session_state.setdefault(f"feedback_{i}", "")

                readonly = st.session_state.get("graded_all", False)
                _ = st.text_area(
                    "Your Answer:", key=f"answer_{i}", height=150,
                    disabled=readonly
                )

                if st.session_state[f"feedback_{i}"]:
                    st.markdown(
                        f"**Feedback for Q{i+1}:**\n\n{st.session_state[f'feedback_{i}']}"
                    )

            # --- Grade All Questions (stepwise) ---
            # initialize our grading flags
            st.session_state.setdefault("grading_all", False)
            st.session_state.setdefault("grading_index", 0)

            # when the user first clicks Grade All, start the stepwise loop
            if not st.session_state.get("graded_all", False) \
               and not st.session_state.get("grading_all", False):
                if st.button("📖 Grade All Questions", key="grade_all_button"):
                    # ensure every question has an answer
                    missing = [
                        i for i in range(len(questions))
                        if not st.session_state.get(f"answer_{i}", "").strip()
                    ]
                    if missing:
                        st.warning("Please answer all questions before grading.")
                    else:
                        # clear any old feedback
                        for i in range(len(questions)):
                            st.session_state.pop(f"feedback_{i}", None)
                        # kick off the stepwise grader
                        st.session_state.grading_all = True
                        st.session_state.grading_index = 0
                        st.rerun()

            # if we are in the middle of grading_all, grade one question then rerun
            if st.session_state.get("grading_all", False):
                idx = st.session_state.grading_index
                ques = questions[idx]
                ans = st.session_state.get(f"answer_{idx}", "").strip()

                # perform the same grading logic, but only for question idx
                if is_copied_from_summary(ans, st.session_state.summary):
                    st.warning(f"⚠️ Q{idx+1} appears copied from the summary.")
                    hl = highlight_copied_parts(ans, st.session_state.summary)
                    st.markdown("Here’s where copying was detected:")
                    st.markdown(hl, unsafe_allow_html=True)
                    score_text = f"0/{st.session_state.points_per_question}"
                    st.session_state[f"feedback_{idx}"] = f"**Score: {score_text}**"
                else:
                    with st.spinner(f"Grading Q{idx+1}..."):
                        fb = grade_answer(
                            ques,
                            ans,
                            st.session_state.points_per_question,
                        )
                    fb_norm = re.sub(r"(?i)(\d+)\s*out of\s*(\d+)", r"\1/\2", fb)
                    st.session_state[f"feedback_{idx}"] = fb_norm

                # advance to the next question (or finish)
                st.session_state.grading_index += 1
                if st.session_state.grading_index >= len(questions):
                    st.session_state.grading_all = False
                    st.session_state.graded_all = True
                st.rerun()


            # --- Quiz Summary ---
        if st.session_state.get("graded_all", False):
            total_score = 0
            total_possible = st.session_state.num_questions * st.session_state.points_per_question
            for i in range(st.session_state.num_questions):
                fb = st.session_state.get(f"feedback_{i}", "")
                match = re.search(r"(\d+)/(\d+)", fb)
                if match:
                    total_score += int(match.group(1))
            percentage = (total_score / total_possible) * 100 if total_possible > 0 else 0
            if percentage >= 90:
                letter = "A"
            elif percentage >= 80:
                letter = "B"
            elif percentage >= 70:
                letter = "C"
            elif percentage >= 60:
                letter = "D"
            else:
                letter = "F"
            st.subheader("🎉 Quiz Summary")
            st.markdown(f"**Total Score:** {total_score}/{total_possible}")
            st.markdown(f"**Percentage:** {percentage:.1f}%")
            st.markdown(f"**Grade:** {letter}")
                
            # --- Back to Summary Button ---
            if st.session_state.get("graded_all", False):
                if st.button("🔙 Back to Summary", key="back_to_summary"):
                    # Clear quiz-related and feedback state
                    clear_keys = [
                        "questions_generated",
                        "questions_text",
                        "graded_all",
                        "quiz_settings_locked",
                        "num_q_input",
                        "pts_q_input",
                    ]
                    for key in clear_keys:
                        st.session_state.pop(key, None)
                    # Clear dynamic answers and feedback
                    for key in list(st.session_state.keys()):
                        if key.startswith("answer_") or key.startswith("feedback_"):
                            st.session_state.pop(key, None)
                    st.rerun()
