# syntax=docker/dockerfile:1
FROM debian:stable-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      bash ca-certificates curl iproute2 net-tools \
      nmap netcat-openbsd snmp \
      openssh-client telnet \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/toolkit

# Copy script
COPY switch_toolkit.sh /usr/local/bin/switch_toolkit.sh
RUN chmod +x /usr/local/bin/switch_toolkit.sh

# Default interactive entry
ENTRYPOINT ["/usr/local/bin/switch_toolkit.sh"]
CMD ["interactive"]
