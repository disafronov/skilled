FROM ghcr.io/astral-sh/uv:0.11.19 AS uv

FROM ubuntu:noble-20260410 AS base

# ENVs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC

# Base dependencies
RUN apt-get update && \
    apt-get install -y \
        tzdata && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

USER ubuntu:ubuntu
WORKDIR /home/ubuntu/app

# Create venv (uses .python-version from the build context).
RUN --mount=from=uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/home/ubuntu/.cache/uv,uid=1000,gid=1000 \
    --mount=type=bind,source=.python-version,target=.python-version \
    uv venv

ENV PATH="/home/ubuntu/app/.venv/bin:$PATH"

##########################

FROM base AS builder

# Install dependencies first (without installing the project itself).
RUN --mount=from=uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/home/ubuntu/.cache/uv,uid=1000,gid=1000 \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=.python-version,target=.python-version \
    uv sync --frozen --no-install-project --link-mode=copy --no-editable --no-group dev

# Copy the project into the image — no src/, files are at root.
COPY --chown=ubuntu:ubuntu \
    ./apps/ /home/ubuntu/app/apps/ \
    ./config/ /home/ubuntu/app/config/ \
    ./workers/ /home/ubuntu/app/workers/ \
    ./manage.py /home/ubuntu/app/manage.py \
    ./README.md /home/ubuntu/app/README.md

# Sync the project now that sources exist.
RUN --mount=from=uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/home/ubuntu/.cache/uv,uid=1000,gid=1000 \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --link-mode=copy --no-editable --no-group dev

##########################

FROM base AS runtime

# Copy venv and app files from builder stage.
COPY --from=builder /home/ubuntu/app/.venv/ /home/ubuntu/app/.venv/
COPY --from=builder /home/ubuntu/app/ /home/ubuntu/app/

WORKDIR /home/ubuntu/app

ENV GUNICORN_CMD_ARGS="--control-socket /tmp/gunicorn.ctl --bind 0.0.0.0:8000 --worker-tmp-dir /tmp --access-logfile - --error-logfile -"

ENTRYPOINT ["python3", "manage.py"]
CMD ["start"]

EXPOSE 8000
