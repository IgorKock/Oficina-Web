# Sobre
Um sistema web utilizando python para gerenciamento de clientes de oficina e de gerenciamento de inventário.

# Requisitos
Precisa do Python 3.13.2 ou suprior e dos seguintes pacotes do pip: Flask, Flask-Migrate, Flask-SQLAlchemy, Flask-Login, pytz, werkzeug, PyMySQL e o SQLAlchemy.

Também precisa do MySQL/MariaDB.

# Executar localmente
Se preferir executar localmente siga esses passos abaixo.

No MySQL/MariaDB execute esses comandos:
> CREATE DATABASE oficina_web CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
> 
> CREATE USER 'seu_usuario'@'localhost' IDENTIFIED BY 'sua_senha';
> 
> GRANT ALL PRIVILEGES ON oficina_web.* TO 'flask_user'@'localhost';
> 
> FLUSH PRIVILEGES;
>
> EXIT;

Lembre-se de trocar o usuário e a senha para um próprio.

Execute o arquivo run.py e digite a URL que aparecer no seu navegador.

# Executar via docker
Se preferir executar via docker siga esses passos abaixo.

Altere o arquivo do docker-compose para trocar o usuário e a senha para um próprio seu.

Após isso pode escolher um desses:

Usar o Docker Compose com o comando "docker compose up --build -d".

Ou através de um Docker pronto no Docker Hub: https://hub.docker.com/r/igorkock/oficinaweb
