# Question Generator API

FastAPI-based service to generate multiple choice questions and insightful questions from Word documents using Groq LLM.

## Features

✅ **MCQ Generation** - Generate multiple choice questions from documents
✅ **General Questions** - Generate thoughtful questions with answers
✅ **Multiple Formats** - Support for .docx and .pdf files
✅ **FastAPI Backend** - Production-ready REST API with auto-documentation
✅ **Groq LLM Integration** - Fast and efficient AI-powered generation
✅ **Type Safety** - Pydantic models for request/response validation

## Project Structure

```
project/
├── src/
│   ├── __init__.py
│   ├── config.py              # Configuration & constants
│   ├── utils.py               # Utility functions
│   ├── services/
│   │   ├── document_processor.py    # Document handling
│   │   └── llm_service.py           # LLM operations
│   └── api/
│       ├── main.py            # FastAPI app & routes
│       └── schemas.py         # Pydantic models
├── tests/                     # Test files
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore rules
└── README.md                 # This file
```

## Prerequisites

- Python 3.8+
- Groq API Key ([Get one here](https://console.groq.com))

## Installation

1. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and add your GROQ_API_KEY
   ```

## Configuration

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_api_key_here
API_HOST=0.0.0.0
API_PORT=8000
LLM_MODEL=llama-3.1-8b-instant
LLM_TEMPERATURE=0.7
```

## Running the API

**Start the FastAPI server:**
```bash
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Access the API:**
- API: `http://localhost:8000`
- Interactive Docs (Swagger UI): `http://localhost:8000/docs`
- Alternative Docs (ReDoc): `http://localhost:8000/redoc`

## API Endpoints

### Health Check
```
GET /health
```
Returns: `{"status": "healthy", "service": "Question Generator API", "version": "1.0.0"}`

### API Info
```
GET /info
```
Returns API documentation and available endpoints.

### Generate MCQs
```
POST /generate-mcqs
```

**Headers:**
- `groq_api_key`: Your Groq API key (required)

**Query Parameters:**
- `num_questions`: Number of questions (1-10, default: 5)

**Request Body:**
- `file`: Document file (.docx or .pdf)

**Response:**
```json
{
  "status": "success",
  "filename": "document.pdf",
  "num_questions_generated": 5,
  "questions": [
    {
      "question": "What is...",
      "options": {
        "A": "Option A",
        "B": "Option B",
        "C": "Option C",
        "D": "Option D"
      },
      "correct_answer": "B"
    }
  ],
  "raw_response": "..."
}
```

### Generate Questions
```
POST /generate-questions
```

**Headers:**
- `groq_api_key`: Your Groq API key (required)

**Query Parameters:**
- `num_questions`: Number of questions (1-10, default: 5)

**Request Body:**
- `file`: Document file (.docx or .pdf)

**Response:**
```json
{
  "status": "success",
  "filename": "document.docx",
  "num_questions_generated": 3,
  "questions": [
    {
      "question": "What is...?",
      "answer": "The answer is..."
    }
  ],
  "raw_response": "..."
}
```

## API Examples

### Using cURL

**Generate MCQs from PDF:**
```bash
curl -X POST http://localhost:8000/generate-mcqs \
  -H "groq_api_key: your_api_key" \
  -F "file=@document.pdf" \
  -F "num_questions=5"
```

**Generate MCQs from DOCX:**
```bash
curl -X POST http://localhost:8000/generate-mcqs \
  -H "groq_api_key: your_api_key" \
  -F "file=@document.docx" \
  -F "num_questions=5"
```

**Generate Questions:**
```bash
curl -X POST http://localhost:8000/generate-questions \
  -H "groq_api_key: your_api_key" \
  -F "file=@document.pdf" \
  -F "num_questions=3"
```

**Health Check:**
```bash
curl http://localhost:8000/health
```

### Using Python

```python
import requests

api_key = "your_groq_api_key"
with open("document.docx", "rb") as f:
    files = {"file": f}
    headers = {"groq_api_key": api_key}
    response = requests.post(
        "http://localhost:8000/generate-mcqs",
        files=files,
        headers=headers,
        params={"num_questions": 5}
    )
    print(response.json())
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | Required | Your Groq API key |
| `API_HOST` | 0.0.0.0 | API server host |
| `API_PORT` | 8000 | API server port |
| `LLM_MODEL` | llama-3.1-8b-instant | LLM model to use |
| `LLM_TEMPERATURE` | 0.7 | LLM temperature (0-1) |
| `DEBUG` | False | Debug mode |

## Deployment

### Render (Recommended - Free Tier)

**Step 1: Push to GitHub**
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/your-username/your-repo.git
git push -u origin main
```

**Step 2: Deploy on Render**

1. Go to [render.com](https://render.com) and sign up
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Fill in the details:
   - **Name:** `question-generator-api`
   - **Runtime:** `Docker`
   - **Build Command:** Leave blank (auto-detected)
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port 8000`
5. Under **"Advanced"**, add Environment Variable:
   - **Key:** `GROQ_API_KEY`
   - **Value:** Your Groq API key
6. Click **"Create Web Service"**

**Step 3: Done!**
Your API will be live at: `https://your-app-name.onrender.com`

Access:
- API: `https://your-app-name.onrender.com`
- Docs: `https://your-app-name.onrender.com/docs`

### Using Gunicorn (Production)

```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
```

### Docker

**Build:**
```bash
docker build -t question-generator .
```

**Run locally:**
```bash
docker run -p 8000:8000 -e GROQ_API_KEY=your_key question-generator
```

### Cloud Platforms

**Render (Free - Recommended)**
- [render.com](https://render.com)
- 750 free hours/month
- Auto-deploy from GitHub

**Railway**
- [railway.app](https://railway.app)
- $5/month free credit

**Fly.io**
- [fly.io](https://fly.io)
- Free tier available
- Global deployment

**Google Cloud Run**
- [cloud.google.com/run](https://cloud.google.com/run)
- Pay-per-use (very cheap)
- Auto-scales to zero

## Troubleshooting

**Issue:** "GROQ_API_KEY not found"
- Solution: Make sure `.env` file exists in project root with your API key

**Issue:** "File must be a .docx file"
- Solution: Only Word documents (.docx) and PDF (.pdf) files are supported

**Issue:** "Failed to read PDF document"
- Solution: Ensure the PDF file is not corrupted and contains readable text

**Issue:** "Document contains no text"
- Solution: The document must have readable text content

**Issue:** "num_questions must be between 1 and 10"
- Solution: Send a number between 1-10 for num_questions parameter

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Formatting

```bash
black src/
flake8 src/
```

## License

This project is provided as-is for educational and development purposes.

## Version

v1.0.0 - Initial release

---

**Made with ❤️ for AI-powered education**
