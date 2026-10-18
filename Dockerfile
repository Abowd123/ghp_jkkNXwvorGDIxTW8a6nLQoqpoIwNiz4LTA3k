FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b fonts-noto-core fonts-dejavu-core libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# one BLAS thread per worker process (big latency win, see README › الأداء)
ENV MPLBACKEND=Agg CIVILBOT_DB=/data/civilbot.sqlite3 BACKUP_DIR=/backups \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
RUN useradd -m bot && mkdir -p /data /backups && chown bot /data /backups
USER bot
VOLUME ["/data", "/backups"]
HEALTHCHECK --interval=60s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os,time,sys; f='/tmp/civilbot.alive'; sys.exit(0 if os.path.exists(f) and time.time()-os.path.getmtime(f)<180 else 1)"
CMD ["python", "-m", "civilbot.bot.main"]
