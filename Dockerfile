FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY OCR_app.py .
COPY parser.py .
COPY gsheet.py .

RUN mkdir -p secrets

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080


CMD ["sh", "-c", "uvicorn OCR_app:app --host 0.0.0.0 --port $PORT"]