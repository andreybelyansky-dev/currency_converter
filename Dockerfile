FROM python:3.12-slim

ENV PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./
COPY converter/ ./converter/

# ENTRYPOINT (а не CMD), чтобы docker run currency-converter USD RUB 100
# передавал аргументы скрипту, а не заменял команду.
ENTRYPOINT ["python", "main.py"]