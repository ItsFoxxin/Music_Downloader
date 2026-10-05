FROM python:3.12.13-slim-bookworm
ARG APP_UID=10001
ARG APP_GID=10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN test "$APP_UID" -gt 0 && test "$APP_GID" -gt 0 \
    && apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g "$APP_GID" foxden && useradd -u "$APP_UID" -g "$APP_GID" -M foxden
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
USER foxden:foxden
EXPOSE 8010
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8010", "--workers", "1", "--no-proxy-headers"]
