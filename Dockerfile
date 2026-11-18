FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EVENTS_DB=/data/events.db

WORKDIR /app
COPY app.py ./app.py
COPY static ./static

RUN mkdir -p /data \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && chown -R app:app /app /data

USER app
EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/api/health', timeout=2)"

CMD ["python", "app.py"]
