
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
# Warning छुपाने के लिए --no-warn-script-location का इस्तेमाल:
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --no-warn-script-location -r requirements.txt

COPY . .

CMD ["python", "Main.py"]
