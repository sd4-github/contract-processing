FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi 'uvicorn[standard]' alembic sqlalchemy 'psycopg[binary]' 'celery[redis]' pymongo azure-storage-blob azure-identity sentry-sdk ddtrace 'PyJWT[crypto]' python-multipart
COPY . .
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
