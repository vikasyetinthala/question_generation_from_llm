"""
FastAPI application and routes for MCQ/Question generation
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Optional
from src.config import (
    API_TITLE, API_DESCRIPTION, API_VERSION,
    ALLOWED_FILE_TYPES, MIN_QUESTIONS, MAX_QUESTIONS, DEFAULT_QUESTIONS,
    MAX_DOCUMENT_LENGTH, MIN_DOCUMENT_LENGTH
)
from src.utils import (
    validate_file, validate_num_questions, parse_mcqs, parse_questions
)
from src.services import DocumentProcessor, LLMService
from src.api.schemas import MCQResponse, QuestionsResponse, HealthResponse, APIInfo

# Initialize FastAPI app
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION
)

# Service instances
doc_processor = DocumentProcessor()


# ============================================================================
# HEALTH & INFO ENDPOINTS
# ============================================================================

@app.get("/", tags=["info"])
async def root():
    """Root endpoint - welcome message"""
    return {
        "message": "Welcome to Question Generator API",
        "documentation": "Visit /info for API details",
        "health": "Check /health for status"
    }


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health():
    """Health check endpoint - verify API is running"""
    return {
        "status": "healthy",
        "service": "Question Generator API",
        "version": API_VERSION
    }


@app.get("/info", response_model=APIInfo, tags=["info"])
async def info():
    """Get API information and usage details"""
    return {
        "title": API_TITLE,
        "description": API_DESCRIPTION,
        "version": API_VERSION,
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
                    "questions": "Array of MCQ objects"
                }
            },
            "POST /generate-questions": {
                "description": "Generate general questions from a Word document",
                "request_headers": {
                    "groq_api_key": "Your Groq API Key (required)"
                },
                "request_body": {
                    "file": "Word document (.docx file)",
                    "num_questions": f"Number of questions ({MIN_QUESTIONS}-{MAX_QUESTIONS}, default: {DEFAULT_QUESTIONS})"
                },
                "response": {
                    "status": "success/error",
                    "questions": "Array of question objects"
                }
            },
            "GET /health": "Check if API is running",
            "GET /info": "Get API information and documentation"
        }
    }


# ============================================================================
# MCQS ENDPOINT
# ============================================================================

@app.post("/generate-mcqs", response_model=MCQResponse, tags=["generation"])
async def generate_mcqs(
    file: UploadFile = File(...),
    groq_api_key: str = Header(...),
    num_questions: int = DEFAULT_QUESTIONS
):
    """
    Generate multiple choice questions from a document.
    
    **Parameters:**
    - **file**: Document file (.docx or .pdf) - required
    - **groq_api_key**: Your Groq API Key passed in header - required
    - **num_questions**: Number of questions to generate (1-10, default: 5)
    
    **Returns:**
    - JSON with generated MCQs in structured format
    
    **Example:**
    ```bash
    curl -X POST \\
      -H "groq_api_key: your_key_here" \\
      -F "file=@document.pdf" \\
      -F "num_questions=5" \\
      http://localhost:8000/generate-mcqs
    ```
    """
    try:
        # Validate inputs
        validate_file(file.filename, ALLOWED_FILE_TYPES)
        validate_num_questions(num_questions, MIN_QUESTIONS, MAX_QUESTIONS)
        
        # Extract and process document
        content = await file.read()
        document_text = doc_processor.extract_text(file.filename, content)
        
        # Initialize LLM and generate
        llm_service = LLMService(groq_api_key)
        llm_service.initialize()
        
        # Truncate document for token limits
        document_text = doc_processor.truncate_for_llm(document_text, MAX_DOCUMENT_LENGTH)
        
        # Generate questions
        result = llm_service.generate_mcqs(document_text, num_questions)
        
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


# ============================================================================
# QUESTIONS ENDPOINT
# ============================================================================

@app.post("/generate-questions", response_model=QuestionsResponse, tags=["generation"])
async def generate_questions(
    file: UploadFile = File(...),
    groq_api_key: str = Header(...),
    num_questions: int = DEFAULT_QUESTIONS
):
    """
    Generate general questions from a document.
    
    **Parameters:**
    - **file**: Document file (.docx or .pdf) - required
    - **groq_api_key**: Your Groq API Key passed in header - required
    - **num_questions**: Number of questions to generate (1-10, default: 5)
    
    **Returns:**
    - JSON with generated questions and answers
    """
    try:
        # Validate inputs
        validate_file(file.filename, ALLOWED_FILE_TYPES)
        validate_num_questions(num_questions, MIN_QUESTIONS, MAX_QUESTIONS)
        
        # Extract and process document
        content = await file.read()
        document_text = doc_processor.extract_text(file.filename, content)
        
        # Initialize LLM and generate
        llm_service = LLMService(groq_api_key)
        llm_service.initialize()
        
        # Truncate document for token limits
        document_text = doc_processor.truncate_for_llm(document_text, MAX_DOCUMENT_LENGTH)
        
        # Generate questions
        result = llm_service.generate_questions(document_text, num_questions)
        
        # Parse and structure response
        questions = parse_questions(result)
        
        return JSONResponse({
            "status": "success",
            "filename": file.filename,
            "num_questions_generated": len(questions),
            "questions": questions,
            "raw_response": result
        })
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating questions: {str(e)}"
        )
