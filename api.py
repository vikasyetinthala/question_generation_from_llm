# ============================================================================
# MCQ Generator API
# Generates multiple choice questions from Word documents using Groq LLM
# ============================================================================

import io
import re
import os
import uvicorn
import uuid
import shutil
import threading
import zipfile
from typing import List, Dict
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from gtts import gTTS
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from src.api.schemas import *
from src.utils import *
from src.config import *

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

# FastAPI App Configuration
APP_CONFIG = {
    "title": "MCQ Generator API",
    "description": "Generate multiple choice questions from Word documents using AI",
    "version": "1.0.0"
}

# Initialize FastAPI App
app = FastAPI(**APP_CONFIG)

# ============================================================================
# ASYNC VIDEO JOB STORE
# In-memory store: job_id -> { status, video_bytes, error }
# status values: "pending" | "done" | "error"
# ============================================================================

_video_jobs: Dict[str, Dict] = {}


def _run_video_job(job_id: str, document_text: str, groq_api_key: str):
    """Background thread that generates the video and stores the result."""
    temp_dir = f"temp_{job_id}"
    output_filename = f"video_{job_id}.mp4"
    os.makedirs(temp_dir, exist_ok=True)
    try:
        # 1. Generate Slide Data
        llm = initialize_llm(groq_api_key)
        parser = JsonOutputParser(pydantic_object=VideoData)
        prompt = PromptTemplate(
            template=VIDEO_PROMPT_TEMPLATE + "\n{format_instructions}",
            input_variables=["document_text"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )
        chain = prompt | llm | parser

        video_data_raw = None
        slides = []
        max_retries = 3
        for attempt in range(max_retries):
            try:
                video_data_raw = chain.invoke({"document_text": document_text[:MAX_DOCUMENT_LENGTH]})
                if isinstance(video_data_raw, dict) and "slides" in video_data_raw:
                    slides = video_data_raw["slides"]
                elif isinstance(video_data_raw, list):
                    slides = video_data_raw
                if slides:
                    break
            except Exception as e:
                print(f"[job {job_id}] Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        f"Failed to generate valid slide content after {max_retries} attempts"
                    )

        if not slides:
            raise RuntimeError("Failed to generate slide content from document")

        # Normalize slides for dictionary access
        normalized_slides = []
        for s in slides:
            if hasattr(s, "model_dump"):
                normalized_slides.append(s.model_dump())
            elif isinstance(s, dict):
                normalized_slides.append(s)
            else:
                normalized_slides.append(dict(s))
        slides = normalized_slides

        # 2. Process Slides (Audio + Images)
        video_clips = []
        for i, slide in enumerate(slides):
            audio_path = os.path.join(temp_dir, f"audio_{i}.mp3")
            tts = gTTS(text=slide["script"], lang="en")
            tts.save(audio_path)

            img_path = os.path.join(temp_dir, f"slide_{i}.png")
            logo_path = None
            if os.path.exists("logo.png"):
                logo_path = "logo.png"
            elif os.path.exists("logo.jpg"):
                logo_path = "logo.jpg"
            create_slide_image(slide["title"], slide["bullets"], img_path, logo_path=logo_path)

            audio_clip = AudioFileClip(audio_path)
            img_clip = ImageClip(img_path).with_duration(audio_clip.duration)
            clip = img_clip.with_audio(audio_clip)
            video_clips.append(clip)

        # 3. Assemble Video
        final_video = concatenate_videoclips(video_clips, method="compose")
        final_video.write_videofile(output_filename, fps=24, codec="libx264")
        
        # Close all clips to release file locks (important for Windows)
        for clip in video_clips:
            clip.close()
        final_video.close()

        # 4. Generate Transcription
        full_transcription = ""
        for i in range(len(slides)):
            audio_path = os.path.join(temp_dir, f"audio_{i}.mp3")
            if os.path.exists(audio_path):
                transcript = transcribe_audio(audio_path, groq_api_key)
                full_transcription += f"Slide {i+1}:\n{transcript}\n\n"
        
        transcription_path = os.path.join(temp_dir, "transcription.txt")
        with open(transcription_path, "w", encoding="utf-8") as f:
            f.write(full_transcription)

        # 5. Create ZIP Archive for async job (if needed, but here it just stores video_bytes)
        # However, _video_jobs only stores video_bytes currently. 
        # The user's request implies the ZIP download should have it.
        # Wait, the current _run_video_job only stores video_bytes. 
        # Let's see if there's a download-video endpoint that uses this.
        
        with open(output_filename, "rb") as f:
            video_bytes = f.read()

        _video_jobs[job_id]["video_bytes"] = video_bytes
        _video_jobs[job_id]["transcription"] = full_transcription
        _video_jobs[job_id]["status"] = "done"

    except Exception as e:
        _video_jobs[job_id]["status"] = "error"
        _video_jobs[job_id]["error"] = str(e)
        print(f"[job {job_id}] Failed: {e}")
    finally:
        cleanup_files(output_filename, temp_dir)


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.post("/generate-mcqs")
async def generate_mcqs(
    file: UploadFile = File(...),
    num_questions: int = DEFAULT_QUESTIONS
):
    """
    Generate multiple choice questions from a Word document.

    Parameters:
    - file: Word document (.docx or .pdf)
    - num_questions: Number of questions to generate (1-10, default: 5)

    Returns:
    - JSON with generated MCQs in structured format
    """
    try:
        validate_file(file.filename)
        validate_num_questions(num_questions)
        
        # Extract and process document
        content = await file.read()
        document_text = extract_text_from_file(file.filename, content)
        
        # Initialize LLM and create chain
        llm = initialize_llm(GROQ_API_KEY)
        chain = create_prompt_chain(llm)

        result = chain.invoke({
            "document_text": document_text[:MAX_DOCUMENT_LENGTH],
            "num_questions": num_questions
        })

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


@app.post("/generate-video")
async def generate_video(
    file: UploadFile = File(...),
):
    """
    Generate an educational video from a Word document.
    """
    temp_dir = f"temp_{uuid.uuid4()}"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        validate_file(file.filename)
        content = await file.read()
        document_text = extract_text_from_file(file.filename, content)
        
        # 1. Generate Slide Data
        llm = initialize_llm(GROQ_API_KEY)
        # Use a simpler prompt for the 8b model to avoid confusion
        prompt = PromptTemplate(
            template=VIDEO_PROMPT_TEMPLATE + "\n\nCRITICAL: Output ONLY a valid JSON object. No preamble or explanation. Start with an opening brace and end with a closing brace.\nFormat:\n{{\"slides\": [{{\"title\": \"Slide Title\", \"bullets\": [\"Point 1\", \"Point 2\"], \"script\": \"Narrator script\"}}]}}",
            input_variables=["document_text"]
        )
        chain = prompt | llm | StrOutputParser()
        
        video_data_raw = None
        slides = []
        
        # Add retry logic since LLMs sometimes fail strict JSON formatting
        max_retries = 3
        for attempt in range(max_retries):
            try:
                raw_response = chain.invoke({"document_text": document_text[:MAX_DOCUMENT_LENGTH]})
                
                # Clean up response if LLM added markdown backticks
                json_str = raw_response.strip()
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].strip()
                
                import json
                video_data_raw = json.loads(json_str)
                
                # Handle dict with 'slides' key or just a straight list of slides
                if isinstance(video_data_raw, dict) and "slides" in video_data_raw:
                    slides = video_data_raw["slides"]
                elif isinstance(video_data_raw, list):
                    slides = video_data_raw
                    
                if slides:
                    break # Success!
                    
            except Exception as e:
                print(f"Attempt {attempt + 1} failed to parse JSON: {e}")
                if attempt == max_retries - 1:
                    raise HTTPException(status_code=500, detail=f"Failed to generate valid slide content after {max_retries} attempts")

        if not slides:
            print(f"Failed to parse slides. Raw response: {video_data_raw}")
            raise HTTPException(status_code=500, detail="Failed to generate slide content from document")

        # Normalize slides to list of dicts if they are Pydantic objects
        normalized_slides = []
        for s in slides:
            if hasattr(s, "model_dump"):
                normalized_slides.append(s.model_dump())
            elif isinstance(s, dict):
                normalized_slides.append(s)
            else:
                # Fallback for unexpected types
                normalized_slides.append(dict(s))
        slides = normalized_slides

        # 2. Process Slides (Audio + Images)
        video_clips = []
        for i, slide in enumerate(slides):
            # Create Audio
            audio_path = os.path.join(temp_dir, f"audio_{i}.mp3")
            tts = gTTS(text=slide['script'], lang='en')
            tts.save(audio_path)
            
            # Create Image
            img_path = os.path.join(temp_dir, f"slide_{i}.png")
            
            # Check for logo
            logo_path = None
            if os.path.exists("logo.png"):
                logo_path = "logo.png"
            elif os.path.exists("logo.jpg"):
                logo_path = "logo.jpg"
                
            create_slide_image(slide['title'], slide['bullets'], img_path, logo_path=logo_path)
            
            # Create Clip
            audio_clip = AudioFileClip(audio_path)
            img_clip = ImageClip(img_path).with_duration(audio_clip.duration)
            clip = img_clip.with_audio(audio_clip)
            video_clips.append(clip)
            
            # Do NOT close audio_clip or img_clip here as they are used in 'clip'
            
        # 3. Assemble Video and Script
        final_video = concatenate_videoclips(video_clips, method="compose")
        base_name = f"video_{uuid.uuid4()}"
        video_output = f"{base_name}.mp4"
        txt_output = os.path.join(temp_dir, "script.txt")
        zip_output = f"{base_name}.zip"

        # Generate Video
        final_video.write_videofile(video_output, fps=24, codec="libx264")
        
        # Close all clips and release file locks
        for clip in video_clips:
            clip.close()
        final_video.close()
        
        # Generate TXT
        create_script_txt(slides, txt_output)

        # 4. Generate Transcription
        full_transcription = ""
        for i in range(len(slides)):
            audio_path = os.path.join(temp_dir, f"audio_{i}.mp3")
            if os.path.exists(audio_path):
                transcript = transcribe_audio(audio_path, GROQ_API_KEY)
                full_transcription += f"Slide {i+1}:\n{transcript}\n\n"
        
        transcription_output = os.path.join(temp_dir, "transcription.txt")
        with open(transcription_output, "w", encoding="utf-8") as f:
            f.write(full_transcription)

        # Create ZIP Archive
        with zipfile.ZipFile(zip_output, 'w') as zipf:
            zipf.write(video_output, "educational_video.mp4")
            zipf.write(txt_output, "slides_content.txt")
            zipf.write(transcription_output, "transcription.txt")

        # Read the ZIP file into memory
        with open(zip_output, "rb") as f:
            zip_bytes = f.read()
        
        # Clean up all temp files and the zip file itself
        if os.path.exists(video_output):
            os.remove(video_output)
        if os.path.exists(zip_output):
            os.remove(zip_output)
        cleanup_files("", temp_dir) 
        
        import io as _io
        return StreamingResponse(
            _io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=video_package_{uuid.uuid4().hex[:8]}.zip"}
        )

    except HTTPException:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise
    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(e)}")




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
                "request_headers": {"groq_api_key": "Your Groq API Key (required)"},
                "request_body": {
                    "file": "Word document (.docx file)",
                    "num_questions": f"Number of questions ({MIN_QUESTIONS}-{MAX_QUESTIONS}, default: {DEFAULT_QUESTIONS})"
                },
                "response": {
                    "status": "success/error",
                    "questions": "Array of MCQ objects with question, options, and correct_answer"
                }
            },
            "POST /generate-video": "Start async video generation, returns job_id",
            "GET /video-status/{job_id}": "Poll video generation status",
            "GET /download-video/{job_id}": "Download completed video",
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
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
