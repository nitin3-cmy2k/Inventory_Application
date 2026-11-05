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

# Install Python application dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the network port Flask runs on
EXPOSE 5000

# Command to launch the application
CMD ["python", "app.py"]

