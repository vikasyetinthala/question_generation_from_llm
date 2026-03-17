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
from typing import List, Dict
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from src.api.schemas import *
from src.utils import *
from src.config import *

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

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


def _run_video_job(job_id: str, document_text: str):
    """Background thread that generates the video and stores the result."""
    temp_dir = f"temp_{job_id}"
    output_filename = f"video_{job_id}.mp4"
    os.makedirs(temp_dir, exist_ok=True)
    try:
        # 1. Generate Slide Data — use API key from environment
        llm = initialize_llm(GROQ_API_KEY)
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

        with open(output_filename, "rb") as f:
            video_bytes = f.read()

        _video_jobs[job_id]["video_bytes"] = video_bytes
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

        content = await file.read()
        document_text = extract_text_from_file(file.filename, content)

        if not GROQ_API_KEY:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured on server")
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
    Start an async video generation job from a Word document.
    Uses GROQ_API_KEY from server environment — no key needed in request.

    Returns immediately with a job_id.
    Poll GET /video-status/{job_id} to check progress.
    Download with GET /download-video/{job_id} when status is 'done'.
    """
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured on server")

    try:
        validate_file(file.filename)
        content = await file.read()
        document_text = extract_text_from_file(file.filename, content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File processing failed: {str(e)}")

    job_id = str(uuid.uuid4())
    _video_jobs[job_id] = {"status": "pending", "video_bytes": None, "error": None}

    # Run the heavy work in a background thread so the HTTP response returns immediately
    thread = threading.Thread(
        target=_run_video_job,
        args=(job_id, document_text),
        daemon=True,
    )
    thread.start()

    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "pending",
            "message": "Video generation started. Poll /video-status/{job_id} to check progress.",
            "status_url": f"/video-status/{job_id}",
            "download_url": f"/download-video/{job_id}",
        },
    )


@app.get("/video-status/{job_id}")
async def video_status(job_id: str):
    """
    Check the status of a video generation job.

    Returns:
    - status: 'pending' | 'done' | 'error'
    - error: error message if status is 'error'
    """
    job = _video_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    response: Dict = {"job_id": job_id, "status": job["status"]}
    if job["status"] == "error":
        response["error"] = job.get("error", "Unknown error")
    return JSONResponse(response)


@app.get("/download-video/{job_id}")
async def download_video(job_id: str):
    """
    Download the generated video once the job status is 'done'.
    """
    job = _video_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    if job["status"] == "pending":
        raise HTTPException(status_code=202, detail="Video is still being generated. Try again later.")

    if job["status"] == "error":
        raise HTTPException(status_code=500, detail=f"Video generation failed: {job.get('error', 'Unknown error')}")

    video_bytes = job.get("video_bytes")
    if not video_bytes:
        raise HTTPException(status_code=404, detail="Video data not found")

    _video_jobs.pop(job_id, None)

    return StreamingResponse(
        io.BytesIO(video_bytes),
        media_type="video/mp4",
        headers={"Content-Disposition": "attachment; filename=educational_video.mp4"},
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
                "description": "Generate MCQs from a document (no API key header needed)",
                "request_body": {
                    "file": "Word document (.docx or .pdf)",
                    "num_questions": f"Number of questions ({MIN_QUESTIONS}-{MAX_QUESTIONS}, default: {DEFAULT_QUESTIONS})"
                },
            },
            "POST /generate-video": "Start async video generation, returns job_id immediately",
            "GET /video-status/{job_id}": "Poll video generation status (pending/done/error)",
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
