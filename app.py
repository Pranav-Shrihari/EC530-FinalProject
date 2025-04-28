import streamlit as st
import fitz
from PDF_extractor import extract_text_from_pdf, clean_text, summarize_text, generate_questions_from_summary, grade_answer, create_polished_pdf, is_copied_from_summary, highlight_copied_parts
import tempfile
import openai
import re

st.set_page_config(page_title="PDF Summarizer & Quizzer", layout="centered")
st.title("📄 PDF Summarizer & Quiz Generator")

# 🔐 Prompt for API Key
if "api_key_validated" not in st.session_state or not st.session_state.api_key_validated:
    api_key = st.text_input("Enter your OpenAI API Key:", placeholder="sk-...", type="password")

    if not api_key:
        st.warning("Please enter your API key to proceed.")
        st.stop()

    # Set key for OpenAI
    client = openai.OpenAI(api_key=api_key)

    # Validate API key by listing models (minimal test)
    try:
        client.models.list()  # this will raise if the key is invalid
        st.session_state.api_key_validated = True
        st.session_state.api_key = api_key  # store it if needed elsewhere
        st.rerun()  # refresh to hide the key field
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
    # Key has already been validated in session
    api_key = st.session_state.api_key
    client = openai.OpenAI(api_key=api_key)

# If needed, set the key in environment (optional)
import os
os.environ["OPENAI_API_KEY"] = api_key

# Show success message only if file has not yet been uploaded
api_success = st.success("✅ API Key validated successfully! You can now upload your PDF.")

uploaded_file = st.file_uploader("Upload your PDF file (max 5 pages)", type="pdf")

if uploaded_file:
    api_success.empty()  # Clear the success message
    # Save to a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    # Check if the file is a PDF and less than 5 pages
    try:
        pdf_doc = fitz.open(tmp_path)
        if pdf_doc.page_count > 5:
            st.error("The PDF file exceeds 5 pages. Please provide a PDF with 5 or fewer pages.")
            st.stop()
    except Exception as e:
        st.error(f"Error: The file could not be opened. Please check the path and try again.")
        st.stop()

    pdf_success = st.success("✅ PDF uploaded successfully!")

    if "summary" not in st.session_state:
        with st.spinner("Generating summary..."):
            pdf_text = extract_text_from_pdf(tmp_path)
            cleaned_text = clean_text(pdf_text)
            summary = summarize_text(cleaned_text)
            st.session_state.summary = summary
    else:
        summary = st.session_state.summary

    pdf_success.empty()  # Clear the success message

    show_questions = st.checkbox("Would you like to generate questions based on this summary?")

    if not show_questions:
        st.subheader("📝 Summary")
        st.write(summary)

        # --- Download Summary as PDF Button ---
        pdf_buffer = create_polished_pdf(summary, title="Generated Summary")
        st.download_button(
            label="Download Summary as Formatted PDF",
            data=pdf_buffer,
            file_name="summary.pdf",
            mime="application/pdf"
        )

    else:
        # Initialize lock state if not set
        if "quiz_settings_locked" not in st.session_state:
            st.session_state.quiz_settings_locked = False

        st.subheader("🛠 Customize Your Quiz")

        # Show text inputs
        num_questions_input = st.text_input(
            "How many questions would you like to generate?", 
            disabled=st.session_state.quiz_settings_locked,
            key="num_questions_input"
        )

        points_per_question_input = st.text_input(
            "How many points is each question worth?", 
            disabled=st.session_state.quiz_settings_locked,
            key="points_per_question_input"
        )

        if not st.session_state.quiz_settings_locked:
            if st.button("✅ Confirm Settings", key="confirm_settings_button"):
                try:
                    num_questions = int(num_questions_input)
                    points_per_question = int(points_per_question_input)

                    if num_questions <= 0 or points_per_question <= 0:
                        st.error("Please enter positive numbers for both fields.")
                        st.stop()
                    
                    # Lock settings
                    st.session_state.num_questions = num_questions
                    st.session_state.points_per_question = points_per_question
                    st.session_state.quiz_settings_locked = True
                    st.rerun()  # Refresh to show the quiz section
                except ValueError:
                    st.error("Please enter valid integers for number of questions and points per question.")
                    st.stop()
        else:
            if "questions_text" not in st.session_state:
                with st.spinner("Generating questions..."):
                    questions_text = generate_questions_from_summary(summary, num_questions=num_questions_input, points_per_question=points_per_question_input)
                    st.session_state.questions_text = questions_text
            else:
                questions_text = st.session_state.questions_text

            st.subheader("🧠 Questions")
            questions = questions_text.split("\n")

            for i, question in enumerate(questions):
                question_container = st.container()

                with question_container:
                    st.markdown(f"**Q{question.strip()}**")

                    # Ensure keys exist
                    if f"feedback_{i}" not in st.session_state:
                        st.session_state[f"feedback_{i}"] = ""
                    if f"answer_{i}" not in st.session_state:
                        st.session_state[f"answer_{i}"] = ""

                    user_answer = st.text_area("Your Answer:", key=f"answer_{i}")

                    feedback_placeholder = st.empty()

                    # Only show Grade button if feedback not yet provided
                    if not st.session_state[f"feedback_{i}"]:
                        if st.button(f"Grade Answer {i+1}", key=f"grade_button_{i}"):
                            if user_answer.strip():
                                if is_copied_from_summary(user_answer, summary):
                                    st.warning("⚠️ Your answer appears to be directly copied from the summary.")
                                    highlighted = highlight_copied_parts(user_answer, summary)
                                    st.markdown("Here’s where copying was detected:")
                                    st.markdown(highlighted, unsafe_allow_html=True)
                                    st.session_state[f"feedback_{i}"] = f"**Score: 0/{points_per_question_input}**"
                                else:
                                    with st.spinner("Grading..."):
                                        feedback = grade_answer(question, user_answer, points_per_question_input)
                                    st.session_state[f"feedback_{i}"] = feedback
                                st.rerun()  # rerun immediately after grading
                            else:
                                st.warning("Please enter an answer before grading.")

                    # Always show feedback if available
                    if st.session_state[f"feedback_{i}"]:
                        feedback_placeholder.markdown(f"**Feedback for Q{i+1}:**\n\n{st.session_state[f'feedback_{i}']}")

                
            # Reset Quiz Settings Button
            if st.button("🔄 Reset Quiz Settings", key="reset_quiz_settings_button"):
                for key in ["quiz_settings_locked", "num_questions_input", "points_per_question_input", "questions_text", "answers", "feedbacks"]:
                    st.session_state.pop(key, None)
                st.success("Quiz settings have been reset. Please set them again.")
                st.rerun()