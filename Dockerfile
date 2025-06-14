# Usa a imagem base Ubuntu mais recente
FROM ubuntu:latest
# Define um argumento para o frontend Debian (útil para instalações não interativas)
ARG DEBIAN_FRONTEND=noninteractive

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia todo o conteúdo do diretório atual para o container
COPY . .

# Instala python3 e python3-pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    # Limpa o cache apt para reduzir o tamanho da imagem Docker
    && rm -rf /var/lib/apt/lists/*

# Instala as dependências Python via pip
# É crucial instalar pymysql via pip para garantir a versão correta e que funcione com SQLAlchemy
RUN pip install Flask Flask-SQLAlchemy Flask-Migrate Flask-Login PyMySQL python-dotenv pytz

# Expõe a porta 5000, que é a porta padrão da aplicação Flask
EXPOSE 5000

# O comando CMD para iniciar sua aplicação Flask
CMD ["python3", "run.py"]
