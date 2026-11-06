FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Static files for the Django admin only (collected at build time; needs no real secret).
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

RUN useradd --system --no-create-home app && chown -R app /app
USER app
EXPOSE 8000

# One ASGI process serves both REST and the WebSocket feed.
CMD ["sh", "-c", "python manage.py migrate --noinput && daphne -b 0.0.0.0 -p 8000 config.asgi:application"]
