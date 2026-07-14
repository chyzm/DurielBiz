FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000

# gthread workers: a slow/idle client ties up one thread, not the whole app,
# and --timeout becomes a worker heartbeat rather than a per-request kill switch.
CMD ["gunicorn", "pos_system.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--worker-class", "gthread", \
     "--threads", "4", \
     "--timeout", "120", \
     "--graceful-timeout", "120", \
     "--access-logfile", "-"]