FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends sudo procps \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash go \
    && echo 'go:go' | chpasswd \
    && usermod -aG sudo go \
    && printf '%s\n' 'go ALL=(ALL:ALL) ALL' > /etc/sudoers.d/go \
    && chmod 440 /etc/sudoers.d/go \
    && printf '%s\n' '#!/bin/bash' 'echo "RST command accepted."' > /usr/local/bin/rst \
    && chmod 755 /usr/local/bin/rst

WORKDIR /app
COPY . /app
RUN chown -R go:go /app

USER go

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 10000

CMD ["python", "/app/app.py"]
