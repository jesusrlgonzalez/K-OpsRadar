FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
COPY outputs/demo/ outputs/demo/
ENV PYTHONPATH=/app/src
ENV I23_DB_PATH=/app/outputs/demo/quality.sqlite
USER 65532
EXPOSE 8000
CMD ["uvicorn", "i23.api:app", "--host", "0.0.0.0", "--port", "8000"]
