FROM python:3.12-slim

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 1000 crew \
    && mkdir -p /srv/workspaces \
    && chown -R crew:crew /srv
USER crew

EXPOSE 8000

# Render (and similar PaaS hosts) inject PORT and require the app to bind to
# it; default to 8000 for docker-compose / plain `docker run` where PORT isn't set.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
