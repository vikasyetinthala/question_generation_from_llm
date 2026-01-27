"""
Document processing service
"""

import io
from docx import Document
from typing import Optional
from ..utils import extract_text_from_file, validate_document_length
from .. import config


class DocumentProcessor:
    """Handle document extraction and processing"""
    
    @staticmethod
    def extract_text(filename: str, content: bytes) -> str:
        """
        Extract text from document content.
        
        Args:
            filename: Name of the file (to determine file type)
            content: Raw bytes of document
            
        Returns:
            Extracted text
        """
        text = extract_text_from_file(filename, content)
        validate_document_length(text, config.MIN_DOCUMENT_LENGTH)
        return text
    
    @staticmethod
    def truncate_for_llm(text: str, max_length: Optional[int] = None) -> str:
        """
        Truncate text for LLM processing.
        
        Args:
            text: Input text
            max_length: Maximum length (uses config default if None)
            
        Returns:
            Truncated text
        """
        if max_length is None:
            max_length = config.MAX_DOCUMENT_LENGTH
        
        return text[:max_length]
    
    @staticmethod
    def get_document_preview(text: str, preview_length: int = 1000) -> str:
        """
        Get a preview of document text.
        
        Args:
            text: Document text
            preview_length: Length of preview
            
        Returns:
            Preview text with ellipsis if truncated
        """
        if len(text) > preview_length:
            return text[:preview_length] + "..."
        return text
