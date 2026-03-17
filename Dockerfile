FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including ffmpeg for moviepy
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set up a new user named "user" with user ID 1000 (Hugging Face requirement)
RUN useradd -m -u 1000 user
USER user

# Set home to the user's home directory
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Change working directory to user home
WORKDIR $HOME/app

# Copy application files and change ownership to user
COPY --chown=user . $HOME/app

# Expose port (Rent/Hugging Face)
EXPOSE 7860

# Use dynamic port from environment, defaulting to 7860 for Hugging Face
ENV PORT=7860
CMD uvicorn api:app --host 0.0.0.0 --port $PORT
