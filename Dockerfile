# TakeMySkins Automator - Render.com Deployment
# Optimized for 512MB RAM free tier

FROM python:3.10-slim

WORKDIR /app

# Install Chromium + system dependencies for SeleniumBase
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    chromium-common \
    chromium-sandbox \
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
    xvfb \
    xauth \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Symlink: SeleniumBase looks for 'google-chrome' or 'chrome' binary
# chromedriver is already installed by the package, no need to symlink it
RUN ln -sf /usr/bin/chromium /usr/bin/google-chrome \
    && ln -sf /usr/bin/chromium /usr/bin/chrome

# Environment - tell SeleniumBase to use system Chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMIUM_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Copy requirements first (for layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy application code
COPY app.py engine.py webui.py db_manager.py .

# Create session directory
RUN mkdir -p user_session downloaded_files

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV SE_HEADLESS=0

# Expose ports
EXPOSE 8080 8081

# Start Xvfb (virtual display for the Steam login browser), then the app
CMD ["sh", "-c", "Xvfb :99 -screen 0 1280x800x24 -nolisten tcp & sleep 2 && python app.py"]
