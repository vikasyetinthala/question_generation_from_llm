"""
Utility functions for MCQ and question generation
"""

import re
import io
from fastapi import HTTPException
from docx import Document
from typing import List, Dict, Optional
from pypdf import PdfReader
import os 
import shutil
from src.config import *

from docx import Document
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

# ============================================================================
# DOCUMENT UTILITIES
# ============================================================================

def extract_text_from_docx(content: bytes) -> str:
    """
    Extract text from a Word document.
    
    Args:
        content: Raw bytes of the .docx file
        
    Returns:
        Extracted text as string
        
    Raises:
        HTTPException: If document cannot be read or is empty
    """
    try:
        doc = Document(io.BytesIO(content))
        text_parts = []
        
        # Extract from paragraphs
        for p in doc.paragraphs:
            if p.text.strip():
                text_parts.append(p.text.strip())
                
        # Extract from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    text_parts.append(" | ".join(row_text))
                    
        document_text = "\n\n".join(text_parts)
        
        if not document_text:
            raise ValueError("Document contains no readable text")
        
        return document_text
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read DOCX document: {str(e)}")


def extract_text_from_pdf(content: bytes) -> str:
    """
    Extract text from a PDF document using PyPDF.
    
    Args:
        content: Raw bytes of the .pdf file
        
    Returns:
        Extracted text as string
        
    Raises:
        HTTPException: If document cannot be read or is empty
    """
    try:
        text_parts = []
        
        pdf_reader = PdfReader(io.BytesIO(content))
        
        if len(pdf_reader.pages) == 0:
            raise HTTPException(status_code=400, detail="PDF document is empty")
        
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_parts.append(page_text)
        
        document_text = "\n\n".join(text_parts)
        
        if not document_text:
            raise HTTPException(status_code=400, detail="No extractable text found in PDF")
        
        return document_text
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read PDF document: {str(e)}")


def extract_text_from_file(filename: str, content: bytes) -> str:
    """
    Extract text from document based on file type.
    
    Args:
        filename: Name of the file
        content: Raw bytes of the file
        
    Returns:
        Extracted text as string
        
    Raises:
        HTTPException: If file type is not supported or cannot be read
    """
    file_ext = "." + filename.split('.')[-1].lower()
    
    if file_ext == ".docx":
        return extract_text_from_docx(content)
    elif file_ext == ".pdf":
        return extract_text_from_pdf(content)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Supported types: .docx, .pdf"
        )





# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

def validate_file(filename: str, allowed_types: List[str]) -> None:
    """
    Validate uploaded file type.
    
    Args:
        filename: Name of the uploaded file
        allowed_types: List of allowed file extensions (e.g., ['.docx'])
        
    Raises:
        HTTPException: If file type is not allowed
    """
    file_ext = "." + filename.split('.')[-1].lower()
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File must be one of {allowed_types}. Got: {file_ext}"
        )


def validate_num_questions(num_questions: int, min_val: int, max_val: int) -> None:
    """
    Validate number of questions parameter.
    
    Args:
        num_questions: Number of questions to generate
        min_val: Minimum allowed questions
        max_val: Maximum allowed questions
        
    Raises:
        HTTPException: If num_questions is out of valid range
    """
    if num_questions < min_val or num_questions > max_val:
        raise HTTPException(
            status_code=400,
            detail=f"num_questions must be between {min_val} and {max_val}"
        )


def validate_document_length(text: str, min_length: int) -> None:
    """
    Validate minimum document length.
    
    Args:
        text: Document text
        min_length: Minimum required character count
        
    Raises:
        HTTPException: If document is too short
    """
    if len(text) < min_length:
        raise HTTPException(
            status_code=400,
            detail=f"Document too short. Minimum {min_length} characters required."
        )


# ============================================================================
# PARSING UTILITIES
# ============================================================================

def parse_mcqs(text: str) -> List[Dict]:
    """
    Parse MCQ text response into structured format.
    
    Args:
        text: Raw LLM response containing MCQs
        
    Returns:
        List of dictionaries with question, options, and correct answer
    """
    mcqs = []
    
    # Split by question pattern
    questions = re.split(r'Question \d+:', text)
    
    for q in questions[1:]:  # Skip first empty split
        lines = q.strip().split('\n')
        if len(lines) < 5:
            continue
        
        question_text = lines[0].strip()
        options = {}
        correct_answer = None
        
        # Parse options and answer
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('A)'):
                options['A'] = line[2:].strip()
            elif line.startswith('B)'):
                options['B'] = line[2:].strip()
            elif line.startswith('C)'):
                options['C'] = line[2:].strip()
            elif line.startswith('D)'):
                options['D'] = line[2:].strip()
            elif line.startswith('Correct Answer:'):
                correct_answer = line.split(':')[1].strip()
        
        # Only add if all required fields are present
        if question_text and len(options) == 4 and correct_answer:
            mcqs.append({
                "question": question_text,
                "options": options,
                "correct_answer": correct_answer
            })
    
    return mcqs


def parse_questions(text: str) -> List[Dict]:
    """
    Parse general questions from LLM response.
    
    Args:
        text: Raw LLM response containing questions
        
    Returns:
        List of dictionaries with questions and answers
    """
    questions = []
    
    # Split by question pattern
    q_splits = re.split(r'Question \d+:', text)
    
    for q in q_splits[1:]:  # Skip first empty split
        lines = q.strip().split('\n')
        if len(lines) < 2:
            continue
        
        question_text = lines[0].strip()
        answer_text = None
        
        # Find answer line
        for i, line in enumerate(lines[1:], 1):
            if line.strip().lower().startswith('answer:'):
                answer_text = line.split(':', 1)[1].strip()
                break
        
        if question_text and answer_text:
            questions.append({
                "question": question_text,
                "answer": answer_text
            })
    
    return questions


def parse_fill_in_the_blanks(text: str) -> List[Dict]:
    """
    Parse fill-in-the-blanks questions from LLM response.
    
    Args:
        text: Raw LLM response containing fill-in-the-blanks questions
        
    Returns:
        List of dictionaries with questions, answers, and context
    """
    blanks = []
    
    # Split by question pattern
    q_splits = re.split(r'Question \d+:', text)
    
    for q in q_splits[1:]:  # Skip first empty split
        lines = q.strip().split('\n')
        if len(lines) < 2:
            continue
        
        question_text = None
        blank_answer = None
        context = None
        
        # Parse the lines
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
                
            if question_text is None:
                # First non-empty line is the question
                question_text = line_stripped
            elif line_stripped.lower().startswith('blank answer:'):
                blank_answer = line_stripped.split(':', 1)[1].strip()
            elif line_stripped.lower().startswith('context:'):
                context = line_stripped.split(':', 1)[1].strip()
        
        # Only add if required fields are present
        if question_text and blank_answer:
            blanks.append({
                "question": question_text,
                "blank_answer": blank_answer,
                "context": context
            })
    
    return blanks


# ============================================================================
# TEXT UTILITIES
# ============================================================================

def truncate_text(text: str, max_length: int) -> str:
    """
    Truncate text to maximum length.
    
    Args:
        text: Input text
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace.
    
    Args:
        text: Input text
        
    Returns:
        Cleaned text
    """
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def cleanup_files(filepath: str, dirpath: str):
    """Delete the generated video file and temporary directory."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
        if os.path.exists(dirpath):
            shutil.rmtree(dirpath)
    except Exception as e:
        print(f"Error during cleanup: {e}")



def extract_text_from_docx(content: bytes) -> str:
    """
    Extract text from a Word document.
    
    Args:
        content: Raw bytes of the .docx file
        
    Returns:
        Extracted text as string
        
    Raises:
        HTTPException: If document cannot be read or is empty
    """
    try:
        doc = Document(io.BytesIO(content))
        text_parts = []
        
        # Extract from paragraphs
        for p in doc.paragraphs:
            if p.text.strip():
                text_parts.append(p.text.strip())
                
        # Extract from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    text_parts.append(" | ".join(row_text))
                    
        document_text = "\n\n".join(text_parts)
        
        if not document_text:
            raise ValueError("Document contains no readable text")
        
        return document_text
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read document: {str(e)}")


def validate_file(filename: str) -> None:
    """
    Validate uploaded file type.
    
    Args:
        filename: Name of the uploaded file
        
    Raises:
        HTTPException: If file type is not allowed
    """
    file_ext = "." + filename.split('.')[-1].lower()
    if file_ext not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"File must be a .docx or .pdf file. Got: {file_ext}"
        )


def validate_num_questions(num_questions: int) -> None:
    """
    Validate number of questions parameter.
    
    Args:
        num_questions: Number of questions to generate
        
    Raises:
        HTTPException: If num_questions is out of valid range
    """
    if num_questions < MIN_QUESTIONS or num_questions > MAX_QUESTIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"num_questions must be between {MIN_QUESTIONS} and {MAX_QUESTIONS}"
        )


def initialize_llm(groq_api_key: str):
    """
    Initialize and return Groq LLM instance.
    
    Args:
        groq_api_key: API key for Groq service
        
    Returns:
        Initialized ChatGroq instance
    """
    return ChatGroq(
        model=LLM_CONFIG["model"],
        temperature=LLM_CONFIG["temperature"],
        groq_api_key=groq_api_key
    )


def create_prompt_chain(llm):
    """
    Create LangChain prompt and execution chain.
    
    Args:
        llm: Initialized ChatGroq instance
        
    Returns:
        Execution chain combining prompt template and LLM
    """
    prompt = PromptTemplate(
        input_variables=["document_text", "num_questions"],
        template=MCQ_PROMPT_TEMPLATE
    )
    return prompt | llm | StrOutputParser()


def create_slide_image(title, bullets, output_path, logo_path=None):
    """Create a slide image using Pillow with text wrapping."""
    width, height = 1280, 720
    background_color = (30, 30, 30)
    text_color = (255, 255, 255)
    accent_color = (0, 150, 255)
    
    img = Image.new('RGB', (width, height), color=background_color)
    draw = ImageDraw.Draw(img)
    
    # Use default font if custom font not found
    try:
        title_font = ImageFont.truetype("arial.ttf", 48)
        content_font = ImageFont.truetype("arial.ttf", 32)
    except:
        title_font = ImageFont.load_default()
        content_font = ImageFont.load_default()
        
    import textwrap
    import os
    
    # Check if a logo path is provided and exists
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            # Resize the logo to fit nicely (e.g. height 100)
            aspect_ratio = logo.width / logo.height
            new_height = 100
            new_width = int(new_height * aspect_ratio)
            logo = logo.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Position it at the top-right corner
            # 40px margins from the top and right
            img.paste(logo, (width - new_width - 40, 40), logo)
        except Exception as e:
            print(f"Error drawing logo: {e}")
    
    # Calculate safe text area (leave right margin for logo)
    logo_reserved_width = 220  # width reserved for logo in top-right
    text_safe_width = width - logo_reserved_width  # usable text area width
    divider_end = text_safe_width - 20
    
    # Approximate chars per line based on font size 48 and safe width (~14px/char)
    safe_title_chars = int(text_safe_width / 27)

    # Draw Title
    title_wrapped = textwrap.wrap(title, width=safe_title_chars)
    y_offset = 60
    for line in title_wrapped:
        draw.text((80, y_offset), line, font=title_font, fill=accent_color)
        y_offset += 60
        
    y_offset += 10
    draw.line((80, y_offset, divider_end, y_offset), fill=accent_color, width=3)
    
    # Draw Bullets
    y_offset += 40
    # Bullet chars: font size 32 ~9px/char, safe width to 1100px
    safe_bullet_chars = int((width - 140) / 18)
    for bullet in bullets:
        bullet_wrapped = textwrap.wrap(f"• {bullet}", width=safe_bullet_chars)
        for i, line in enumerate(bullet_wrapped):
            indent = 0 if i == 0 else 20
            draw.text((100 + indent, y_offset), line, font=content_font, fill=text_color)
            y_offset += 45
        y_offset += 20  # Add extra spacing between bullets
        
    img.save(output_path)


def parse_mcqs(text: str) -> list:
    """
    Parse MCQ text response into structured format.
    
    Args:
        text: Raw LLM response containing MCQs
        
    Returns:
        List of dictionaries with question, options, and correct answer
    """
    mcqs = []
    
    # Split by question pattern
    questions = re.split(r'Question \d+:', text)
    
    for q in questions[1:]:  # Skip first empty split
        lines = q.strip().split('\n')
        if len(lines) < 5:
            continue
        
        question_text = lines[0].strip()
        options = {}
        correct_answer = None
        
        # Parse options and answer
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('A)'):
                options['A'] = line[2:].strip()
            elif line.startswith('B)'):
                options['B'] = line[2:].strip()
            elif line.startswith('C)'):
                options['C'] = line[2:].strip()
            elif line.startswith('D)'):
                options['D'] = line[2:].strip()
            elif line.startswith('Correct Answer:'):
                correct_answer = line.split(':')[1].strip()
        
        # Only add if all required fields are present
        if question_text and len(options) == 4 and correct_answer:
            mcqs.append({
                "question": question_text,
                "options": options,
                "correct_answer": correct_answer
            })
    
    return mcqs

