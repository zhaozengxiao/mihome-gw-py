# Xiaomi Gateway (mihome) listener for Home Assistant - Python rewrite
FROM python:3.12-alpine

# Debug tools for network diagnostics
RUN apk add --no-cache net-tools iproute2

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY mihome_gw/ ./mihome_gw/
COPY options2config.py run.sh ./
# 无 /data/options.json 时的兜底配置 (用户可挂载 config.json 覆盖)
COPY config.example.json ./config.json

EXPOSE 9898/udp
EXPOSE 8080/tcp

RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]