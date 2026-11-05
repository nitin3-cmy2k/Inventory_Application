# Use an official lightweight Python runtime as a parent image
FROM python:3.11-slim

# Set system environment variables to optimize Python performance inside Docker
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies needed for building packages or pinging network resources
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first to take advantage of Docker layer caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies with an extended network timeout
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --default-timeout=100 -r requirements.txt

# Copy application source code and views
COPY app/app.py .
COPY app/templates ./templates

EXPOSE 5000

CMD ["python", "/app/app.py"]
