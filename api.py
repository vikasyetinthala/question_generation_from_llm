# ============================================================================
# Video & MCQ Generator API
# ============================================================================

import io
import re
import os
import uvicorn
import uuid
import shutil
import threading
import zipfile
import json
from typing import List, Dict, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Header, Form
from gtts import gTTS
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

from src.api.schemas import VideoData, Slide
from src.utils import (
    initialize_llm, 
    parse_mcqs, 
    extract_text_from_docx, 
    extract_text_from_pdf,
    extract_text_from_file,
    validate_file, 
    create_slide_image, 
    create_script_txt, 
    transcribe_audio, 
    cleanup_files, 
    parse_script_txt,
    modify_script_with_llm
)
from src.config import (
    DEFAULT_QUESTIONS, 
    MIN_QUESTIONS, 
    MAX_QUESTIONS, 
    GROQ_API_KEY, 
    MAX_DOCUMENT_LENGTH, 
    ALLOWED_FILE_TYPES,
    LLM_CONFIG,
    VIDEO_PROMPT_TEMPLATE,
    MCQ_PROMPT_TEMPLATE
)

# ============================================================================
# INITIALIZATION
# ============================================================================

app = FastAPI(
    title="MCQ & Video Generator API",
    description="Generate MCQs and educational videos from documents using AI",
    version="1.2.0"
)

# ============================================================================
# VIDEO GENERATION CORE
# ============================================================================

def _process_video_generation(
    content: Optional[bytes] = None, 
    filename: Optional[str] = None, 
    prompt: Optional[str] = None, 
    is_script: bool = False,
    source_document: str = "",
    preparsed_slides: Optional[List[Dict]] = None
) -> io.BytesIO:
    """Core logic to generate video and return ZIP buffer."""
    job_id = str(uuid.uuid4())
    temp_dir = f"temp_{job_id}"
    output_filename = f"video_{job_id}.mp4"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        slides = []
        
        # 1. Get Initial Slides
        if preparsed_slides:
            slides = preparsed_slides
        elif not is_script:
            document_text = extract_text_from_file(filename, content)
            llm = initialize_llm(GROQ_API_KEY)
            video_prompt = PromptTemplate(
                template=VIDEO_PROMPT_TEMPLATE + "\n\nCRITICAL: Output ONLY a valid JSON object. No preamble. Format:\n{{\"slides\": [{{\"title\": \"Slide Title\", \"bullets\": [\"Point 1\", \"Point 2\"], \"script\": \"Narrator script\"}}]}}",
                input_variables=["document_text"]
            )
            chain = video_prompt | llm | StrOutputParser()
            
            # Generate Slide Data
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    raw_response = chain.invoke({"document_text": document_text[:MAX_DOCUMENT_LENGTH]})
                    json_str = raw_response.strip()
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0].strip()
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].strip()
                    
                    video_data = json.loads(json_str)
                    if isinstance(video_data, dict) and "slides" in video_data:
                        slides = video_data["slides"]
                    elif isinstance(video_data, list):
                        slides = video_data
                    if slides: break
                except Exception as e:
                    print(f"LLM Attempt {attempt + 1} failed: {e}")
        else:
            script_text = content.decode("utf-8")
            slides = parse_script_txt(script_text)

        if not slides:
            raise RuntimeError("Failed to obtain slide content")

        # 2. Apply Prompt Modification if provided
        if prompt:
            # Convert slides to script text for modification
            script_path = os.path.join(temp_dir, "temp_script.txt")
            create_script_txt(slides, script_path)
            with open(script_path, "r", encoding="utf-8") as f:
                current_script = f.read()
            
            modified_script, modification_summary = modify_script_with_llm(current_script, prompt, GROQ_API_KEY, source_document)
            
            # Save modification summary
            summary_path = os.path.join(temp_dir, "modification_summary.txt")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write("MODIFICATION SUMMARY\n")
                f.write("=" * 20 + "\n\n")
                f.write(modification_summary)
            
            slides = parse_script_txt(modified_script)
            if not slides:
                raise RuntimeError("Failed to parse modified script")

        # 3. Generate Video
        video_clips = []
        for i, slide in enumerate(slides):
            audio_path = os.path.join(temp_dir, f"audio_{i}.mp3")
            img_path = os.path.join(temp_dir, f"slide_{i}.png")
            
            # Audio
            tts = gTTS(text=slide['script'], lang='en')
            tts.save(audio_path)
            
            # Image
            logo_path = None
            for ext in ["png", "jpg"]:
                if os.path.exists(f"logo.{ext}"):
                    logo_path = f"logo.{ext}"
                    break
            create_slide_image(slide['title'], slide['bullets'], img_path, logo_path=logo_path)
            
            # Clip
            audio_clip = AudioFileClip(audio_path)
            img_clip = ImageClip(img_path).with_duration(audio_clip.duration)
            clip = img_clip.with_audio(audio_clip)
            video_clips.append(clip)

        final_video = concatenate_videoclips(video_clips, method="compose")
        final_video.write_videofile(
            output_filename, fps=24, codec="libx264", audio_codec="aac",
            temp_audiofile=os.path.join(temp_dir, "temp-audio.m4a"), remove_temp=True
        )
        
        for clip in video_clips: clip.close()
        final_video.close()

        # 4. Transcription
        full_transcription: str = ""
        for i in range(len(slides)):
            audio_path = os.path.join(temp_dir, f"audio_{i}.mp3")
            if os.path.exists(audio_path):
                transcript = transcribe_audio(audio_path, GROQ_API_KEY)
                full_transcription = full_transcription + f"Slide {i+1}:\n{transcript}\n\n"
        
        # 5. Pack into ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            with open(output_filename, "rb") as f:
                zipf.writestr("educational_video.mp4", f.read())
            
            # Create script TXT for the ZIP
            final_script_path = os.path.join(temp_dir, "slides_content.txt")
            create_script_txt(slides, final_script_path)
            with open(final_script_path, "r", encoding="utf-8") as f:
                zipf.writestr("slides_content.txt", f.read())
            
            zipf.writestr("transcription.txt", full_transcription)
            
            # Include modification summary if it exists
            summary_path = os.path.join(temp_dir, "modification_summary.txt")
            if os.path.exists(summary_path):
                with open(summary_path, "rb") as f:
                    zipf.writestr("modification_summary.txt", f.read())
        
        zip_buffer.seek(0)
        return zip_buffer

    except Exception as e:
        print(f"Error in _process_video_generation: {e}")
        raise e
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
    """Generate multiple choice questions from a document."""
    try:
        if not GROQ_API_KEY: raise HTTPException(status_code=500, detail="Groq API key required")
        
        validate_file(file.filename)
        content = await file.read()
        document_text = extract_text_from_file(file.filename, content)
        
        llm = initialize_llm(GROQ_API_KEY)
        prompt = PromptTemplate(
            template=MCQ_PROMPT_TEMPLATE,
            input_variables=["document_text", "num_questions"]
        )
        chain = prompt | llm | StrOutputParser()

        result = chain.invoke({
            "document_text": document_text[:MAX_DOCUMENT_LENGTH],
            "num_questions": num_questions
        })
        mcqs = parse_mcqs(result)

        return {"status": "success", "questions": mcqs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-video")
async def generate_video(
    file: UploadFile = File(...),
):
    """Generate video from a document (PDF/DOCX) and return ZIP directly."""
    if not GROQ_API_KEY: 
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured in environment")
    
    validate_file(file.filename)
    content = await file.read()
    try:
        zip_buffer = _process_video_generation(content, file.filename, prompt=None, is_script=False)
        return StreamingResponse(
            zip_buffer, 
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=video_package.zip"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/regenerate-video")
async def regenerate_video(
    file: UploadFile = File(...),
    source_file: Optional[UploadFile] = File(None),
    prompt: Optional[str] = Form(None)
):
    """Regenerate video from a script (.txt) with an optional modification prompt and optional source document context."""
    if not GROQ_API_KEY: 
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured in environment")
    
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Regeneration requires a .txt script file")
        
    content = await file.read()
    
    source_document_text = ""
    if source_file:
        source_content = await source_file.read()
        source_document_text = extract_text_from_file(source_file.filename, source_content)

    try:
        zip_buffer = _process_video_generation(
            content, file.filename, prompt=prompt, is_script=True, source_document=source_document_text
        )
        return StreamingResponse(
            zip_buffer, 
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=regenerated_video_package.zip"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/regenerate-from-transcription")
async def regenerate_from_transcription(
    transcription_file: UploadFile = File(...),
    slides_file: UploadFile = File(...),
    source_file: Optional[UploadFile] = File(None),
    prompt: Optional[str] = Form(None)
):
    """Regenerate video from a transcription (.txt) and slides content (.txt) with an optional modification prompt."""
    if not GROQ_API_KEY: 
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured in environment")
    
    # 1. Read files
    transcription_content = (await transcription_file.read()).decode("utf-8")
    slides_content = (await slides_file.read()).decode("utf-8")
    
    # 2. Extract source document context if provided
    source_document_text = ""
    if source_file:
        source_bytes = await source_file.read()
        source_document_text = extract_text_from_file(source_file.filename, source_bytes)
    
    # 3. Parse and Merge
    from src.utils import parse_transcription_txt, merge_transcription_with_slides
    
    raw_slides = parse_script_txt(slides_content)
    transcription_map = parse_transcription_txt(transcription_content)
    merged_slides = merge_transcription_with_slides(raw_slides, transcription_map)
    
    if not merged_slides:
        raise HTTPException(status_code=400, detail="Failed to parse slides or transcription content")

    # 4. Process Video Generation
    try:
        zip_buffer = _process_video_generation(
            prompt=prompt, 
            is_script=False, 
            source_document=source_document_text,
            preparsed_slides=merged_slides
        )
        return StreamingResponse(
            zip_buffer, 
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=transcription_regenerated_video.zip"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.2.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
