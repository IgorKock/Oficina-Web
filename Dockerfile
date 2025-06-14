# Usa a imagem base Ubuntu mais recente
FROM ubuntu:latest
# Define um argumento para o frontend Debian (útil para instalações não interativas)
ARG DEBIAN_FRONTEND=noninteractive

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia todo o conteúdo do diretório atual para o container
COPY . .

# Atualiza a lista de pacotes e instala as dependências do sistema via apt
# Adiciona python3-full para garantir todas as dependências Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-sqlalchemy \
    # Bibliotecas Flask e suas extensões
    python3-flask \
    python3-flask-sqlalchemy \
    python3-flask-migrate \
    python3-flask-login \
    # Drivers de banco de dados e utilitários
    python3-pymysql \
    # Outras bibliotecas
    python3-tz \
    python3-werkzeug \
    # Limpa o cache apt para reduzir o tamanho da imagem Docker
    && rm -rf /var/lib/apt/lists/*

# Expõe a porta 5000, que é a porta padrão da aplicação Flask
EXPOSE 5000

# Adiciona um pequeno atraso antes de iniciar a aplicação
# Isso pode ajudar a garantir que a rede Docker esteja totalmente estabelecida
CMD ["bash", "-c", "sleep 10 && python3 run.py"]