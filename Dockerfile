FROM ubuntu:latest
ARG DEBIAN_FRONTEND=noninteractive
WORKDIR /app
COPY . .
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-flask \
    python3-flask-migrate \
    python3-flask-sqlalchemy \
	python3-flask-login \
    python3-sqlalchemy \
    python3-tz \
	python3-werkzeug \
    && rm -rf /var/lib/apt/lists/*
EXPOSE 5000
CMD ["python3", "run.py"]
