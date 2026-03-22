FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y \
    python3 \
    python3-pip \
    bpfcc-tools \
    python3-bpfcc \
    linux-headers-generic \
    libpython3.10-dev \
    iproute2 \
    net-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir psutil prometheus_client

WORKDIR /app

CMD ["/bin/bash"]