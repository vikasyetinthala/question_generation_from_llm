"""
LLM (Language Model) service for question generation
"""

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from typing import Dict, Any
from .. import config


class LLMService:
    """Handle LLM initialization and question generation"""
    
    def __init__(self, api_key: str):
        """
        Initialize LLM service.
        
        Args:
            api_key: Groq API key
        """
        self.api_key = api_key
        self.llm = None
    
    def initialize(self) -> None:
        """Initialize Groq LLM instance"""
        self.llm = ChatGroq(
            model=config.LLM_MODEL,
            temperature=config.LLM_TEMPERATURE,
            groq_api_key=self.api_key
        )
    
    def _create_chain(self, prompt_template: str) -> object:
        """
        Create LangChain execution chain.
        
        Args:
            prompt_template: Template string for the prompt
            
        Returns:
            Execution chain
        """
        if self.llm is None:
            self.initialize()
        
        prompt = PromptTemplate(
            input_variables=["document_text", "num_questions"],
            template=prompt_template
        )
        return prompt | self.llm | StrOutputParser()
    
    def _create_chain_with_topic(self, prompt_template: str) -> object:
        """
        Create LangChain execution chain with topic variable.
        
        Args:
            prompt_template: Template string for the prompt
            
        Returns:
            Execution chain
        """
        if self.llm is None:
            self.initialize()
        
        prompt = PromptTemplate(
            input_variables=["document_text", "num_questions", "topic"],
            template=prompt_template
        )
        return prompt | self.llm | StrOutputParser()
    
    def generate_mcqs(self, document_text: str, num_questions: int) -> str:
        """
        Generate multiple choice questions.
        
        Args:
            document_text: Text from document
            num_questions: Number of questions to generate
            
        Returns:
            Raw LLM response with generated MCQs
        """
        chain = self._create_chain(config.MCQ_PROMPT_TEMPLATE)
        
        result = chain.invoke({
            "document_text": document_text,
            "num_questions": num_questions
        })
        
        return result
    
    def generate_questions(self, document_text: str, num_questions: int) -> str:
        """
        Generate general questions.
        
        Args:
            document_text: Text from document
            num_questions: Number of questions to generate
            
        Returns:
            Raw LLM response with generated questions
        """
        chain = self._create_chain(config.QUESTION_PROMPT_TEMPLATE)
        
        result = chain.invoke({
            "document_text": document_text,
            "num_questions": num_questions
        })
        
        return result
    
    def generate_feedback_questions(self, document_text: str, num_questions: int, topic: str) -> str:
        """
        Generate questions focused on a specific topic.
        
        Args:
            document_text: Text from document
            num_questions: Number of questions to generate
            topic: Topic to focus on
            
        Returns:
            Raw LLM response with generated questions
        """
        chain = self._create_chain_with_topic(config.FEEDBACK_PROMPT_TEMPLATE)
        
        result = chain.invoke({
            "document_text": document_text,
            "num_questions": num_questions,
            "topic": topic
        })
        
        return result
