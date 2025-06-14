# Usa a imagem base Ubuntu mais recente
FROM ubuntu:latest
# Define um argumento para o frontend Debian (útil para instalações não interativas)
ARG DEBIAN_FRONTEND=noninteractive

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia todo o conteúdo do diretório atual para o diretório de trabalho no container
COPY . .

# Atualiza a lista de pacotes e instala as dependências do sistema
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    # Instala bibliotecas Python via apt para garantir que as dependências de sistema sejam atendidas
    python3-flask \
    python3-flask-migrate \
    python3-flask-sqlalchemy \
    python3-flask-login \
    python3-sqlalchemy \
    python3-tz \
    python3-werkzeug \
    python3-pymysql \
    # Limpa o cache apt para reduzir o tamanho da imagem Docker
    && rm -rf /var/lib/apt/lists/*

# Expõe a porta 5000, que é a porta padrão da aplicação Flask
EXPOSE 5000

# Define o comando que será executado quando o container for iniciado
CMD ["python3", "run.py"]

