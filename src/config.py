"""
Configuration and environment settings
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# APPLICATION SETTINGS
# ============================================================================

APP_NAME = "Question Generator API"
APP_VERSION = "1.0.0"
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# ============================================================================
# API CONFIGURATION
# ============================================================================

API_TITLE = "MCQ Generator API"
API_DESCRIPTION = "Generate multiple choice questions from Word documents using AI"
API_VERSION = "1.0.0"
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))

# ============================================================================
# LLM CONFIGURATION
# ============================================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "3000"))


# LLM Configuration
LLM_CONFIG = {
    "model": LLM_MODEL,
    "temperature": LLM_TEMPERATURE,
    "max_tokens": LLM_MAX_TOKENS
}

# ============================================================================
# VALIDATION CONSTANTS
# ============================================================================

ALLOWED_FILE_TYPES = [".docx", ".pdf"]
MIN_QUESTIONS = 1
MAX_QUESTIONS = 10
DEFAULT_QUESTIONS = 5
MAX_DOCUMENT_LENGTH = 10000
MIN_DOCUMENT_LENGTH = 10



# ============================================================================
# STREAMLIT CONFIGURATION
# ============================================================================

STREAMLIT_PAGE_TITLE = "Question Generator from Documents"
STREAMLIT_LAYOUT = "wide"
STREAMLIT_INITIAL_SIDEBAR_STATE = "expanded"

# ============================================================================
# MCQ PROMPT TEMPLATES
# ============================================================================


MCQ_PROMPT_TEMPLATE = """Based on the following document content, generate {num_questions} multiple choice questions that test understanding of the key concepts.

Document:
{document_text}

For each question, generate in this exact format:

Question 1: [Question text here?]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
Correct Answer: [A/B/C/D]

Repeat this format for all {num_questions} questions. Make them clear, specific, and relevant to the document content. Ensure options are plausible but the correct answer is unambiguous."""

QUESTION_PROMPT_TEMPLATE = """Based on the following document content, generate {num_questions} thoughtful and insightful questions that promote deeper understanding.

Document:
{document_text}

Generate {num_questions} questions in this format:

Question 1: [Your question here?]
Answer: [Concise answer]

Make questions clear, specific, and directly related to the document content."""

FILL_IN_THE_BLANKS_PROMPT_TEMPLATE = """Based on the following document content, generate {num_questions} fill-in-the-blanks questions.

Document:
{document_text}

For each question, create a sentence with a blank (represented by ___) and provide the answer. Generate in this exact format:

Question 1: [Sentence with a blank represented by ___]
Blank Answer: [The word or phrase that fills the blank]
Context: [Brief explanation or context]

Repeat this format for all {num_questions} questions. Make sure the blanks are meaningful and test understanding of key concepts. The blank should be significant enough that removing it requires comprehension of the material."""

FEEDBACK_PROMPT_TEMPLATE = """Based on the following document and topic, generate {num_questions} questions.

Document:
{document_text}

Topic Focus: {topic}

Generate questions in this format:

Question 1: [Question about {topic}?]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
Correct Answer: [A/B/C/D]

Ensure all questions are relevant to '{topic}'."""


# Video Prompt Template
VIDEO_PROMPT_TEMPLATE = """You are an expert educator. Based on the following document content, create a structured script for a COMPREHENSIVE educational video.
The video should consist of at least 15 to 20 slides to ensure every single detail and section of the material is covered thoroughly. For each slide, provide:
1. A concise Title.
2. 3-4 key Bullet Points. Make sure each bullet point is SHORT and CONCISE (maximum 12 words per bullet point).
3. A spoken Script (what the narrator says).

CRITICAL: Do not summarize or skip any major sections. The video must cover all details from the input text to ensure a complete learning experience.

Document:
{document_text}

Output the response in JSON format as a list of slide objects.
Example:
[
  {{
    "title": "Introduction to AI",
    "bullets": ["Definition of AI", "History", "Why it matters"],
    "script": "Welcome! Today we're exploring Artificial Intelligence, its roots, and its transformative impact."
  }}
]
"""
