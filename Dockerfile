FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Warning हटाने के लिए --root-user-action=ignore जोड़ा गया है
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

COPY . .

CMD ["python", "main.py"]
