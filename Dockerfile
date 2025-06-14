# Usa a imagem base Ubuntu mais recente
FROM ubuntu:latest
# Define um argumento para o frontend Debian (útil para instalações não interativas)
ARG DEBIAN_FRONTEND=noninteractive

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia todos os arquivos do contexto (incluindo entrypoint.sh e sua aplicação) para o container
COPY . .

# Atualiza a lista de pacotes e instala as dependências do sistema via apt
# Inclui 'netcat-traditional' para o comando 'nc' no entrypoint.sh
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-sqlalchemy \
    netcat-traditional \
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

# Torna o script de entrada executável
RUN chmod +x ./entrypoint.sh

# Expõe a porta 5000, que é a porta padrão da aplicação Flask
EXPOSE 5000

# Define o script entrypoint que será executado quando o container iniciar
# Ele aguardará o DB, executará migrações e, em seguida, iniciará a aplicação Flask
ENTRYPOINT ["./entrypoint.sh"]