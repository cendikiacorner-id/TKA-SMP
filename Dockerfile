# TKA Cerdas — image produksi minimal, tanpa dependensi eksternal.
FROM python:3.12-slim

# Zona waktu Indonesia (opsional, agar log mudah dibaca)
ENV TZ=Asia/Jakarta \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Aplikasi hanya memakai pustaka standar Python, tidak perlu pip install.
COPY server.py gsheets.py office.py pdf.py reports.py seed_soal.py ./
COPY public ./public

# Folder data agar basis data SQLite dapat dipasang sebagai volume persisten.
RUN mkdir -p /data && useradd -m -u 10001 app \
    && chown -R app:app /app /data
ENV TKA_DB_DIR=/data
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:%s/api/health'%os.environ.get('PORT','8000'),timeout=4)"

CMD ["python", "server.py"]
