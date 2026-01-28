"""
Utility functions for MCQ and question generation
"""

import re
import io
from fastapi import HTTPException
from docx import Document
from typing import List, Dict, Optional
from pypdf import PdfReader


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
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        document_text = "\n\n".join(paragraphs)
        
        if not document_text:
            raise HTTPException(status_code=400, detail="Document contains no text")
        
        return document_text
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
