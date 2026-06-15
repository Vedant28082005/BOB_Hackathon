FROM pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime

WORKDIR /app

# System deps for OpenCV and PaddleOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    g++ gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Increase timeout to 600s for large packages (torch, paddlepaddle)
RUN pip install --no-cache-dir --timeout=600 -r requirements.txt

COPY . .

RUN mkdir -p model_weights

ENV PYTHONUNBUFFERED=1
EXPOSE 8001

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
