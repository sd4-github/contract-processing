FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY . .
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser
CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:8000", "--workers", "2"]
