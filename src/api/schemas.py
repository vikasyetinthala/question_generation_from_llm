"""
Pydantic schemas for API request/response validation
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class MCQOption(BaseModel):
    """MCQ Option"""
    A: str = Field(..., description="Option A")
    B: str = Field(..., description="Option B")
    C: str = Field(..., description="Option C")
    D: str = Field(..., description="Option D")


class MCQ(BaseModel):
    """Multiple Choice Question"""
    question: str = Field(..., description="Question text")
    options: Dict[str, str] = Field(..., description="Answer options A, B, C, D")
    correct_answer: str = Field(..., description="Correct answer letter (A/B/C/D)")


class MCQResponse(BaseModel):
    """API Response for MCQ Generation"""
    status: str = Field(..., description="Status of the request")
    filename: str = Field(..., description="Name of uploaded file")
    num_questions_generated: int = Field(..., description="Number of questions generated")
    questions: List[MCQ] = Field(..., description="List of generated MCQs")
    raw_response: Optional[str] = Field(None, description="Raw response from LLM")


class Question(BaseModel):
    """General Question"""
    question: str = Field(..., description="Question text")
    answer: str = Field(..., description="Answer to the question")


class QuestionsResponse(BaseModel):
    """API Response for Question Generation"""
    status: str = Field(..., description="Status of the request")
    filename: str = Field(..., description="Name of uploaded file")
    num_questions_generated: int = Field(..., description="Number of questions generated")
    questions: List[Question] = Field(..., description="List of generated questions")
    raw_response: Optional[str] = Field(None, description="Raw response from LLM")


class HealthResponse(BaseModel):
    """Health Check Response"""
    status: str = Field(..., description="Health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")


class APIInfo(BaseModel):
    """API Information"""
    title: str = Field(..., description="API title")
    description: str = Field(..., description="API description")
    version: str = Field(..., description="API version")
    endpoints: Dict = Field(..., description="Available endpoints")


class ErrorResponse(BaseModel):
    """Error Response"""
    status: str = Field(default="error", description="Error status")
    detail: str = Field(..., description="Error details")
    code: int = Field(..., description="Error code")
