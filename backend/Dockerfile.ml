FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml constraints-ml.txt ./
RUN python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb'))['project']; print('\n'.join(d['dependencies'] + d['optional-dependencies']['dev'] + d['optional-dependencies']['ml']))" > /tmp/requirements.txt \
    && pip install --default-timeout=100 --no-cache-dir -r /tmp/requirements.txt -c constraints-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

COPY . .

