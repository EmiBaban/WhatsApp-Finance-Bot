FROM python:3.12-slim

# Instalare doar dependențele sistem necesare pentru Tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-ron \
    libtesseract-dev \
    libglib2.0-0 \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libopenblas-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiază requirements.txt și instalează dependențele Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copiază codul aplicației
COPY . .

# Variabile de mediu
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

# Comanda de start
CMD ["sh", "-c", "gunicorn -w 2 -b 0.0.0.0:$PORT --access-logfile - --error-logfile - --capture-output --log-level info reply_whatsapp:app"]
