# Use Python 3.11 slim as base image
FROM python:3.11-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.6.1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy only requirements first to leverage Docker cache
COPY pyproject.toml poetry.lock* ./
COPY requirements*.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set up cron for daily analytics
COPY ci/cron_daily.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/cron_daily.sh

# Copy the rest of the application
COPY . .

# Set up cron job
RUN (crontab -l 2>/dev/null; echo "0 9 * * * /usr/local/bin/cron_daily.sh") | crontab -

# Create a non-root user and switch to it
RUN useradd -m scraper && \
    chown -R scraper:scraper /app
USER scraper

# Set environment variables for production
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/scraper/.local/bin:${PATH}" \
    PYTHONFAULTHANDLER=1

# Create necessary directories
RUN mkdir -p /app/data

# Set the working directory
WORKDIR /app

# Expose any necessary ports (if your application requires it)
# EXPOSE 8000

# Set the default command to run the scraper
CMD ["python", "-m", "src.cli", "--help"]
