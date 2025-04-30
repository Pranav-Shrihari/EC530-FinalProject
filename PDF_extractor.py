import fitz  # PyMuPDF
import re
import openai
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import difflib
import io

# Step 1: PDF Text Extraction
def extract_text_from_pdf(pdf_path):
    # Open the provided PDF file
    doc = fitz.open(pdf_path)
    text = ""
    
    # Loop through each page and extract text
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        text += page.get_text("text")  # Extract text
    
    return text

# Step 2: Text Preprocessing and Organization

# Clean text: remove unwanted content like page numbers, headers, and footers
def clean_text(text):
    # Remove page numbers (for example: "Page 1", "Page 2", etc.)
    text = re.sub(r'Page \d+', '', text)

    # Remove any unwanted extra whitespaces (between words, paragraphs, etc.)
    text = re.sub(r'\s+', ' ', text).strip()

    return text

# Step 3: Summary Generation using AI

# Summarize the entire content using OpenAI's GPT (or another summarizer)
def summarize_text(text):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    
    # Correct API call for v1/chat/completions endpoint
    response = openai.chat.completions.create(
        model="gpt-4",  # Ensure the correct model name is used, you can use gpt-3.5-turbo or gpt-4
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Please summarize the following content: {text}"}
        ],
        max_tokens=500,  # Optionally, you can limit the number of tokens in the response
        temperature=0.7  # Controls the randomness of the response
    )
    
    # Extract and return the summary content
    content = response.choices[0].message.content.strip()
    return content

# Step 4: Question Generation using AI

# Generate questions based on the summary of the entire text
def generate_questions_from_summary(summary, num_questions=5, points_per_question=10, question_type="Short Answer"):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    
    # Request questions based on the summary
    response = openai.chat.completions.create(
        model="gpt-4",  # You can also use gpt-3.5-turbo
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Based on the following summary, generate {num_questions} {question_type.lower()} questions for review: {summary}, with each question worth {points_per_question} points."}
        ],
        max_tokens=300,  # You can adjust this number for longer or shorter responses
        temperature=0.7
    )
    
    # Extract and return the generated questions
    questions = response.choices[0].message.content.strip()
    return questions

# Step 5: Grading User's Response using AI

# Function to grade the user's response using AI
def grade_answer(question, user_answer, summary, max_points = 10):
    # 1) Copy check
    if is_copied_from_summary(user_answer, summary):
        return (
            f"Grade: 0/{max_points}\n\n"
            "Your answer appears to be copied from the summary. "
            "Therefore, you have been awarded a 0 for this question.\n\n"
        )
    
    # 2) Otherwise, do the normal AI grading
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    
    # Request grading feedback based on the user's answer
    response = openai.chat.completions.create(
        model="gpt-4",  # You can also use gpt-3.5-turbo
        messages=[
            {"role": "system", "content": "You are a grading assistant."},
            {"role": "user", "content": f"Question: {question}\nUser Answer: {user_answer}\nGrade the answer out of {max_points} points and provide feedback with an example answer."}
        ],
        max_tokens=200,  # You can adjust this number for longer or shorter responses
        temperature=0.7
    )
    
    # Extract and return the feedback
    feedback = response.choices[0].message.content.strip()
    return feedback

# Step 6: PDF Generation using ReportLab
def create_polished_pdf(summary_text, title="Summary"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Define custom styles
    title_style = ParagraphStyle(
        name='TitleStyle',
        parent=styles['Title'],
        fontSize=20,
        spaceAfter=20
    )
    body_style = ParagraphStyle(
        name='BodyStyle',
        parent=styles['BodyText'],
        fontSize=12,
        spaceAfter=12
    )
    
    story = []

    # Add the Title
    story.append(Paragraph(f"<b>{title}</b>", title_style))
    story.append(Spacer(1, 20))

    # Preprocess summary text
    paragraphs = summary_text.strip().split('\n')
    bullet_items = []
    inside_bullet_list = False

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue  # skip empty lines

        # Detect bullets (lines starting with "-" or "•")
        if para.startswith(("-", "•")):
            bullet_text = para.lstrip("-• ").strip()
            # Convert **bold** markers inside bullet
            bullet_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', bullet_text)
            bullet_items.append(Paragraph(bullet_text, body_style))
            inside_bullet_list = True
        else:
            if inside_bullet_list:
                # Close the previous bullet list
                story.append(ListFlowable(
                    [ListItem(item) for item in bullet_items],
                    bulletType='bullet'
                ))
                bullet_items = []
                inside_bullet_list = False

            # Process normal paragraph with bold conversion
            para = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', para)
            story.append(Paragraph(para, body_style))
            story.append(Spacer(1, 12))

    # If the summary ends with a bullet list, add it
    if bullet_items:
        story.append(ListFlowable(
            [ListItem(item) for item in bullet_items],
            bulletType='bullet'
        ))

    doc.build(story)
    buffer.seek(0)
    return buffer

# Step 7 - Quiz + Feedback PDF Generation
def create_quiz_feedback_pdf(questions, answers, feedbacks, title="Quiz and Feedback"):
    """
    Generates a PDF containing the quiz questions, user answers, and structured feedback.
    Breaks each feedback string into Grade, Feedback, and Example Answer sections.
    :param questions: List of question strings
    :param answers:   List of user answer strings
    :param feedbacks: List of raw feedback strings from grade_answer
    :param title:     Title on the PDF cover page
    :return:          BytesIO buffer with PDF data
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='TitleStyle', parent=styles['Title'], fontSize=20, spaceAfter=20)
    grade_style = ParagraphStyle(name='GradeStyle', parent=styles['Heading3'], fontSize=14, spaceAfter=6)
    question_style = ParagraphStyle(name='QuestionStyle', parent=styles['Heading2'], fontSize=14, spaceAfter=6)
    answer_style = ParagraphStyle(name='AnswerStyle', parent=styles['BodyText'], fontSize=12, spaceAfter=4)
    feedback_style = ParagraphStyle(name='FeedbackStyle', parent=styles['BodyText'], fontSize=12, textColor='red', spaceAfter=12)

    story = []
    story.append(Paragraph(f"<b>{title}</b>", title_style))
    story.append(Spacer(1, 20))

    for idx, (q, a, f_raw) in enumerate(zip(questions, answers, feedbacks), start=1):
        # Question
        story.append(Paragraph(f"Q{q}", question_style))
        story.append(Spacer(1, 4))

        # Extract Grade
        grade_match = re.search(r"\*?Grade:?\s*(\d+/\d+)\*?", f_raw)
        grade = grade_match.group(1) if grade_match else ""
        # Clean raw feedback text
        f_clean = re.sub(r"\*?Grade:?\s*\d+/\d+\*?", "", f_raw).strip()

        # Split Feedback vs Example Answer
        example_answer = ""
        if "Example Answer:" in f_clean:
            parts = f_clean.split("Example Answer:", 1)
            feedback_text = parts[0].strip().lstrip(":").strip()
            example_answer = parts[1].strip()
        else:
            feedback_text = f_clean

        # User Answer Section
        story.append(Paragraph(f"<b>Your Answer:</b> {a}", answer_style))
        story.append(Spacer(1, 4))

        # Grade Section
        story.append(Paragraph(f"<b>Grade:</b> {grade}", grade_style))
        story.append(Spacer(1, 4))

        # Feedback Section
        story.append(Paragraph(f"{feedback_text}", feedback_style))
        story.append(Spacer(1, 4))

        # Example Answer Section
        if example_answer:
            story.append(Paragraph(f"<b>Example Answer:</b> {example_answer}", feedback_style))
            story.append(Spacer(1, 12))
        else:
            story.append(Spacer(1, 12))

    doc.build(story)
    buffer.seek(0)
    return buffer




# Helper functions to detect copied content
def is_copied_from_summary(answer, summary, threshold=0.8):
    """
    Check if a significant portion of the answer overlaps with the summary.
    Flags True if:
      1) The entire answer is in the summary.
      2) Word-overlap ratio ≥ threshold.
      3) SequenceMatcher quick_ratio ≥ threshold.
      4) ≥ threshold fraction of answer characters come from summary sentences verbatim.
    """
    answer = answer.strip()
    summary = summary.strip()
    if not answer or not summary:
        return False

    # 1) Direct substring
    if answer in summary:
        return True

    # 2) Word-level overlap
    import re, difflib
    ans_words = set(re.findall(r'\w+', answer.lower()))
    summ_words = set(re.findall(r'\w+', summary.lower()))
    if ans_words:
        overlap = len(ans_words & summ_words) / len(ans_words)
        if overlap >= threshold:
            return True

    # 3) Fuzzy
    if difflib.SequenceMatcher(None, answer.lower(), summary.lower()).quick_ratio() >= threshold:
        return True

    # 4) Sentence‐level verbatim match
    #   Split the answer into sentences, count how many chars of those sentences appear verbatim in summary
    answer_sentences = re.split(r'(?<=[.!?])\s+', answer)
    total_chars = len(answer)
    if total_chars > 0:
        matched_chars = 0
        for sent in answer_sentences:
            sent = sent.strip()
            # ignore very short fragments
            if len(sent) < 10:
                continue
            if sent in summary:
                matched_chars += len(sent)
        if matched_chars / total_chars >= threshold:
            return True

    return False