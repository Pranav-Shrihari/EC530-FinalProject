from setuptools import setup, find_packages
import io, os

# long_description from your README
here = os.path.abspath(os.path.dirname(__file__))
with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_desc = f.read()

setup(
    name='pdf-quiz-generator',
    version='0.1.0',
    author='Your Name',
    author_email='you@example.com',
    description='Streamlit app: summarize PDFs & generate quizzes',
    long_description=long_desc,
    long_description_content_type='text/markdown',
    url='https://github.com/youruser/pdf-quiz-generator',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'streamlit>=1.0',
        'pymupdf',         # fitz binding
        'reportlab',
        'openai',
    ],
    entry_points={
        'console_scripts': [
            'pdf-quiz=pdf_quiz_generator.cli:main',
        ],
    },
    python_requires='>=3.7',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Framework :: Streamlit',
    ],
)
