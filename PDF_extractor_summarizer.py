import fitz  # PyMuPDF
import re
import openai
import os

# Step 1: PDF Text Extraction (from Step 1)
def extract_text_from_pdf(pdf_path):
    # Open the provided PDF file
    doc = fitz.open(pdf_path)
    text = ""
    
    # Loop through each page and extract text
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        text += page.get_text("text")  # Extract text
    
    return text

# Step 2: Text Preprocessing and Organization (from Step 2)

# Clean text: remove unwanted content like page numbers, headers, and footers
def clean_text(text):
    # Remove page numbers (for example: "Page 1", "Page 2", etc.)
    text = re.sub(r'Page \d+', '', text)

    # Remove any unwanted extra whitespaces (between words, paragraphs, etc.)
    text = re.sub(r'\s+', ' ', text).strip()

    return text

# Segment the text into sections based on detected headings or subheadings
def segment_text_by_headings(text):
    sections = []
    
    # Regular expression for detecting "Chapter" or "Section" or any heading-like patterns
    # Adjust the regex to match patterns like Chapter X, Section Y, etc.
    split_sections = re.split(r'(?=\n(?:Chapter \d+|Section \d+))', text)  # Look ahead for "Chapter X" or "Section X"
    
    for section in split_sections:
        section = section.strip()
        if section:
            sections.append(section)
    
    return sections

# Summarize each section using OpenAI's GPT (or another summarizer)
def summarize_section(text):
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
    
    # Correct way to extract summary content from the response
    content = response.choices[0].message.content.strip()  # Corrected access pattern
    return content

def summarize_sections(sections):
    summaries = []
    for section in sections:
        summary = summarize_section(section)
        summaries.append(summary)
    return summaries

# Step 3: Combine Extraction, Preprocessing, Summarization, and Keyword Extraction
def preprocess_pdf_text(pdf_path):
    # Step 1: Extract text from the PDF
    pdf_text = extract_text_from_pdf(pdf_path)
    
    # Step 2: Clean and preprocess the text
    cleaned_text = clean_text(pdf_text)
    
    # Step 3: Segment the text into sections
    sections = segment_text_by_headings(cleaned_text)
    
    # Step 4: Summarize each section
    summaries = summarize_sections(sections)
    
    return summaries

# Main function to prompt the user for a file path and execute the steps
def main():
    # Ask the user to input the file path for the PDF
    pdf_path = input("Please enter the file path of the PDF: ")
    
    # Check if the file exists and process it
    try:
        with open(pdf_path, 'rb'):  # Open the file in binary mode to check its existence
            print(f"Extracting and processing text from: {pdf_path}")
            summaries = preprocess_pdf_text(pdf_path)
            for idx, summary in enumerate(summaries):
                print(f"\nSection {idx+1} Summary: \n{summary}")
            
    except FileNotFoundError:
        print(f"Error: The file at {pdf_path} was not found. Please check the path and try again.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
