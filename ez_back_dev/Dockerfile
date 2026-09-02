FROM python:3.11.15-slim@sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff AS dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHON_DOTENV_DISABLED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY ez_back_dev/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes \
    --target=/opt/venv/lib/python3.11/site-packages \
    -r /tmp/requirements.txt

FROM python:3.11.15-slim@sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHON_DOTENV_DISABLED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/opt/venv/lib/python3.11/site-packages

WORKDIR /app
COPY --from=dependencies /opt/venv /opt/venv
COPY ez_back_dev /app
RUN mkdir -p /app/static/projects \
    && chown 10001:10001 /app/static/projects

USER 10001:10001

EXPOSE 8130 8131
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8130"]
