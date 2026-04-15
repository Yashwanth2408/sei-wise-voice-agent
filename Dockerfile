FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/
COPY data/ ./data/
COPY bot.py ./

RUN pip install --upgrade pip
RUN pip install -e .

ENV PYTHONPATH=src
ENV PYTHONUNBUFFERED=1

EXPOSE 7861

CMD ["python", "bot.py", "-t", "webrtc", "--host", "0.0.0.0", "--port", "7861"]
