FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts ./scripts
COPY web ./web
COPY data ./data
RUN useradd --create-home appuser
USER appuser
ENV PORT=8080
ENV AI_SETTINGS_BACKEND=environment
EXPOSE 8080
CMD ["sh", "-c", "python -m scripts.migrate && python -m scripts.seed && python -m app.server"]
