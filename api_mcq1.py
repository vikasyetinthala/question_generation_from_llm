# ============================================================================
# MCQ Generator API
# Generates multiple choice questions from Word documents using Groq LLM
# ============================================================================

from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.responses import JSONResponse
from docx import Document
import io
import re
import uvicorn
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

# FastAPI App Configuration
APP_CONFIG = {
    "title": "MCQ Generator API",
    "description": "Generate multiple choice questions from Word documents using AI",
    "version": "1.0.0"
}

# LLM Configuration
LLM_CONFIG = {
    "model": "llama-3.1-8b-instant",
    "temperature": 0.7,
    "max_tokens": 3000
}

# Validation Constants
ALLOWED_FILE_TYPES = [".docx"]
MIN_QUESTIONS = 1
MAX_QUESTIONS = 10
DEFAULT_QUESTIONS = 5
MAX_DOCUMENT_LENGTH = 3000

# MCQ Prompt Template
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

# Initialize FastAPI App
app = FastAPI(**APP_CONFIG)

@app.post("/generate-mcqs")
async def generate_mcqs(
    file: UploadFile = File(...),
    groq_api_key: str = Header(...),
    num_questions: int = DEFAULT_QUESTIONS
):
    """
    Generate multiple choice questions from a Word document.
    
    Parameters:
    - file: Word document (.docx)
    - groq_api_key: Your Groq API Key (pass via header)
    - num_questions: Number of questions to generate (1-10, default: 5)
    
    Returns:
    - JSON with generated MCQs in structured format
    """
    try:
        # Validate inputs
        validate_file(file.filename)
        validate_num_questions(num_questions)
        
        # Extract and process document
        content = await file.read()
        document_text = extract_text_from_docx(content)
        
        # Initialize LLM and create chain
        llm = initialize_llm(groq_api_key)
        chain = create_prompt_chain(llm)
        
        # Generate questions
        result = chain.invoke({
            "document_text": document_text[:MAX_DOCUMENT_LENGTH],
            "num_questions": num_questions
        })
        
        # Parse and structure response
        mcqs = parse_mcqs(result)
        
        return JSONResponse({
            "status": "success",
            "filename": file.filename,
            "num_questions_generated": len(mcqs),
            "questions": mcqs,
            "raw_response": result
        })
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating questions: {str(e)}"
        )


@app.get("/health")
async def health():
    """Health check endpoint - verify API is running"""
    return {
        "status": "healthy",
        "service": "MCQ Generator API",
        "version": APP_CONFIG["version"]
    }


@app.get("/info")
async def info():
    """Get API information and usage details"""
    return {
        "title": APP_CONFIG["title"],
        "description": APP_CONFIG["description"],
        "version": APP_CONFIG["version"],
        "endpoints": {
            "POST /generate-mcqs": {
                "description": "Generate multiple choice questions from a Word document",
                "request_headers": {
                    "groq_api_key": "Your Groq API Key (required)"
                },
                "request_body": {
                    "file": "Word document (.docx file)",
                    "num_questions": f"Number of questions ({MIN_QUESTIONS}-{MAX_QUESTIONS}, default: {DEFAULT_QUESTIONS})"
                },
                "response": {
                    "status": "success/error",
                    "questions": "Array of MCQ objects with question, options, and correct_answer"
                }
            },
            "GET /health": "Check if API is running",
            "GET /info": "Get API information and documentation"
        }
    }


@app.get("/")
async def root():
    """Root endpoint - welcome message"""
    return {
        "message": "Welcome to MCQ Generator API",
        "documentation": "Visit /info for API details",
        "health": "Check /health for status"
    }


# ============================================================================
# UTILITY FUNCTIONS
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
            detail=f"File must be a .docx file. Got: {file_ext}"
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


def initialize_llm(groq_api_key: str) -> ChatGroq:
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


def create_prompt_chain(llm: ChatGroq) -> object:
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



# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """Run FastAPI server"""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
