FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN groupadd --gid 10001 gmfms && useradd --uid 10001 --gid gmfms --create-home gmfms
COPY requirements/ requirements/
RUN pip install -r requirements/production.txt -c requirements/lock.txt
COPY --chown=10001:10001 . .
RUN mkdir -p /data/private_media /app/staticfiles && chown -R 10001:10001 /data /app/staticfiles
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "--config", "deploy/gunicorn.conf.py", "config.wsgi:application"]
