# Usa a imagem oficial do Ubuntu como base
FROM ubuntu:latest

# Define uma variável de ambiente para evitar prompts interativos durante a instalação de pacotes
ARG DEBIAN_FRONTEND=noninteractive

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia todo o conteúdo do diretório atual (local) para o diretório de trabalho (/app) no container
COPY . .

# Atualiza a lista de pacotes e instala as dependências necessárias
# Inclui dos2unix para corrigir quebras de linha de scripts
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
    netcat-openbsd \
    wget \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Baixa o script wait-for-it.sh e o torna executável
# Este script é usado no entrypoint.sh para esperar pelo DB
RUN wget https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh -O /usr/bin/wait-for-it.sh \
    && chmod +x /usr/bin/wait-for-it.sh

# Copia o script entrypoint.sh para o container
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
# Converte as quebras de linha do entrypoint.sh para o formato Unix E torna-o executável
RUN dos2unix /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

# Expõe a porta 5000, que é a porta padrão onde o Flask roda
EXPOSE 5000

# Define o entrypoint do container. O Docker executará este script na inicialização.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# CMD é o comando padrão que é passado como argumento para o ENTRYPOINT.
# Neste caso, o ENTRYPOINT irá chamar 'python3 run.py' no final.
CMD ["python3", "run.py"]