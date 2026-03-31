FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y \
    python3 \
    python3-pip \
    bpfcc-tools \
    python3-bpfcc \
    libpython3.12-dev \
    iproute2 \
    net-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages psutil prometheus_client

WORKDIR /app

CMD ["/bin/bash"]