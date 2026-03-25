FROM python:3.11-slim

WORKDIR /app

# Install system deps for Pillow (Soul Card renderer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libjpeg62-turbo-dev zlib1g-dev libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages (order: mindos → ome → ome-server)
COPY packages/mindos packages/mindos
RUN pip install --no-cache-dir packages/mindos

COPY packages/ome packages/ome
RUN pip install --no-cache-dir "packages/ome[all]"

COPY packages/ome-server packages/ome-server
RUN pip install --no-cache-dir packages/ome-server

# Install Pillow for Soul Card
RUN pip install --no-cache-dir Pillow

# Install CJK fonts for Soul Card text rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 8765

CMD ["uvicorn", "ome_server.main:app", "--host", "0.0.0.0", "--port", "8765"]
