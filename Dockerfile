# TakeMySkins Automator - Render.com Deployment
# Optimized for 512MB RAM free tier

FROM python:3.10-slim

WORKDIR /app

# Install minimal system dependencies
# SeleniumBase va descărca Chrome, deci nu-l instalez manual
RUN apt-get update && apt-get install -y \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py engine.py gui.py db_manager.py .

# Create session directory
RUN mkdir -p user_session downloaded_files

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

# Expose ports
EXPOSE 8080 8081

# Health check for Render (detects spin-up)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8081/healthz || exit 1

# Run application
CMD ["python", "app.py"]
