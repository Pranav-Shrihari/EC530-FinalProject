# PDF-Quiz-Generator

A Streamlit-based tool to summarize PDF documents, generate quiz questions from that summary, and grade answers entered by the user—all packaged for easy installation via pip.

## Features

- PDF Summarization: Extracts text from PDFs and generates concise summaries using OpenAI.

- Quiz Generation: Produces multiple-choice, true/false, or short-answer questions based on the summary.

- Automated Grading: Grades user responses immediately, highlights copied content, and provides feedback.

- Polished Outputs: Exports both summaries and quizzes as polished PDF files.

- CLI Launcher: Instantly spin up the Streamlit web interface with a single command.

### Requirements:

- Python 3.7+

- Streamlit

- PyMuPDF

- reportlab

- openai

## How to run the app
Once you have cloned/downloaded the repository, you can run the following command in the command line to install all of the required libraries (ensure that you are in the right directory):
<pre lang="markdown"> pip install -r requirements.txt </pre>
After that, you can run the following command to initialize the app:
<pre lang="markdown"> pdf_quiz_generator </pre>

## Contributing
Contributions are welcome! Please follow the standard GitHub flow:

- Fork this repo

- Create a feature branch (git checkout -b feat/YourFeature)

- Commit your changes (git commit -m "Add feature")

- Push to branch (git push origin feat/YourFeature)

- Open a Pull Request

Please ensure tests pass and update documentation where necessary.
