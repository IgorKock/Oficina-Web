#!/bin/bash
# Este script garante que o MariaDB está pronto e aplica migrações antes de iniciar a aplicação Flask.

# Função para aguardar o MariaDB
wait_for_mariadb() {
  echo "Aguardando o MariaDB iniciar em $DB_HOST:$DB_PORT..."
  # Loop até que o serviço de banco de dados esteja acessível
  while ! nc -z $DB_HOST $DB_PORT; do
    sleep 1
  done
  echo "MariaDB iniciou!"
}

# Define as variáveis de ambiente para o host e porta do DB
# Use as variáveis do docker-compose.yml
DB_HOST=${DB_HOST:-db} # Padrão para 'db' se não estiver definido
DB_PORT=${DB_PORT:-3306} # Padrão para 3306 se não estiver definido

# Chama a função para aguardar o MariaDB
wait_for_mariadb

# Aplica as migrações do banco de dados
echo "Aplicando migrações de banco de dados..."
# É crucial garantir que o FLASK_APP esteja definido para o 'flask db' funcionar
export FLASK_APP=run.py
flask db upgrade

# Verifica o código de saída do comando anterior
if [ $? -ne 0 ]; then
  echo "Erro ao aplicar migrações do banco de dados. Verifique os logs acima."
  # Opcional: Você pode querer sair aqui se as migrações forem críticas para o início da aplicação
  # exit 1
fi

echo "Migrações aplicadas!"

# Inicia a aplicação Flask (comando original do CMD)
echo "Iniciando a aplicação Flask..."
exec "$@" # Executa o comando passado para o entrypoint (CMD do Dockerfile)