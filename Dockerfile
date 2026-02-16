FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
COPY pyproject.toml ./
COPY README.md ./
COPY src ./src
COPY scripts ./scripts
COPY config ./config
COPY .env.example ./.env.example

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt \
    && python -m pip install --no-deps -e . \
    && python -m compileall src scripts

EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "src/invest/webapp/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
