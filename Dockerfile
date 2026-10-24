FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    sudo \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash go \
    && echo 'go:go' | chpasswd \
    && usermod -aG sudo go \
    && echo 'go ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/go \
    && chmod 0440 /etc/sudoers.d/go

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN chown -R go:go /app

USER go
EXPOSE 10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
