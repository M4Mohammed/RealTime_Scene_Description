# Use an official Python runtime as a parent image, optimized for PyTorch
FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed for OpenCV, PIL, etc.
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Create directories required by the application
RUN mkdir -p /app/src/backend /app/src/frontend

# Copy the application code into the container
COPY ./src/backend /app/src/backend
COPY ./src/frontend /app/src/frontend

# Expose the API port
EXPOSE 8000

# Optional: Pre-download the Hugging Face model so the container starts faster
# This requires running a tiny script during build
RUN python -c "from transformers import BlipProcessor, BlipForConditionalGeneration; \
    BlipProcessor.from_pretrained('Salesforce/blip-image-captioning-base'); \
    BlipForConditionalGeneration.from_pretrained('Salesforce/blip-image-captioning-base')"

# Set the current working directory to backend so Uvicorn runs correctly
WORKDIR /app/src/backend

# Command to run the FastAPI application using Uvicorn
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
