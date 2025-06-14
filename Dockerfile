# Usa a imagem base Ubuntu mais recente, conforme solicitado.
FROM ubuntu:latest

# Define uma variável de ambiente para que a instalação não faça perguntas interativas.
ARG DEBIAN_FRONTEND=noninteractive

# Define o diretório de trabalho dentro do container.
# Todos os comandos subsequentes serão executados neste diretório.
WORKDIR /app

# Copia todo o conteúdo do diretório atual da sua máquina (onde o Dockerfile está)
# para o diretório /app dentro do container. Isso inclui o seu código Flask.
COPY . .

# Atualiza a lista de pacotes do sistema e instala todas as dependências necessárias para a sua aplicação.
# Inclui python3, pip (para gerenciar pacotes python), e as bibliotecas Flask e suas extensões,
# além do PyMySQL para a conexão com o banco de dados.
# O 'rm -rf /var/lib/apt/lists/*' é para limpar o cache do apt e reduzir o tamanho final da imagem.
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
    python3-pymysql \
    && rm -rf /var/lib/apt/lists/*

# Expõe a porta 5000 do container.
# Esta é a porta padrão que a sua aplicação Flask deve escutar.
EXPOSE 5000

# Define a variável de ambiente FLASK_APP.
# Isto informa ao Flask qual é o ficheiro principal da sua aplicação (ex: run.py).
ENV FLASK_APP=run.py

# Comando para executar a sua aplicação quando o container é iniciado.
# Certifique-se de que o seu ficheiro 'run.py' contém a lógica para iniciar a aplicação Flask.
CMD ["python3", "run.py"]