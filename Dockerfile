FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

WORKDIR /app

# 1. C++20 कम्पाइलर, मेक टूल्स और आवश्यक पैकेजेस
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    cmake \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 2. Pip अपग्रेड और डिपेंडेंसी इंस्टॉलेशन
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --default-timeout=100 --retries 10 --root-user-action=ignore -r requirements.txt

# 3. सभी प्रोजेक्ट फाइल्स कॉपी करना
COPY . .

# 4. C++ Core को Python में कंपाइल व रजिस्टर करना
RUN pip install --no-cache-dir --root-user-action=ignore -e .

# 5. बॉट स्टार्ट कमांड
CMD ["python", "bot_controller.py"]
