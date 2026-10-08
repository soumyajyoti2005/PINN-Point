FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml constraints.txt ./
RUN python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb'))['project']; print('\n'.join(d['dependencies'] + d['optional-dependencies']['dev']))" > /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt -c constraints.txt
COPY . .

# Start uvicorn on 0.0.0.0:$API_PORT. 
# We use exec form with sh -c to expand the $API_PORT variable at runtime.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${API_PORT}"]
