FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

WORKDIR /app

# 1. C++20 कम्पाइलर, मेक टूल्स और पैकेजेस
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    cmake \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 2. Pip अपग्रेड और pybind11, setuptools, wheel इंस्टॉल करना
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir pybind11 setuptools wheel

# 3. सभी प्रोजेक्ट फाइल्स कॉपी करना
COPY . .

# 4. C++ Core को बिना बिल्ड आइसोलेशन के इंस्टॉल करना (यह एरर को ठीक करेगा)
RUN pip install --no-cache-dir --no-build-isolation --root-user-action=ignore -e .

# 5. बॉट स्टार्ट कमांड
CMD ["python", "bot_controller.py"]
