# TakeMySkins Automator - Render.com Deployment
# Optimized for 512MB RAM free tier

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for SeleniumBase + health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libu2f-udev \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
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
