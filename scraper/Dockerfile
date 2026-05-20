FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Chromium + chromedriver para o Selenium
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-liberation \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Copiar o codigo ANTES de instalar para o setuptools find encontrar o pacote.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# Default: roda uma vez e sai. Use `docker compose --profile scraper run --rm scraper`
ENTRYPOINT ["cge-scraper"]
CMD ["run", "--once"]
