# Folosim o imagine de Python cu suport pentru browsere
FROM python:3.10-slim

# Instalăm dependențele de sistem pentru Chrome/Selenium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libxrender1 \
    libxtst6 \
    libxi6 \
    libdbus-1-3 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Instalăm Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Setăm directorul de lucru
WORKDIR /app

# Copiem fișierele cu dependențe
COPY requirements.txt .

# Instalăm dependențele Python
RUN pip install --no-cache-dir -r requirements.txt

# Instalăm driverele necesare pentru SeleniumBase
RUN sbase install chromedriver

# Copiem restul codului
COPY . .

# Expunem portul (Render va folosi variabila PORT)
EXPOSE 8080

# Comanda de start
CMD ["python", "app.py"]
