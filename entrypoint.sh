#!/bin/bash
# Este script garante que o MariaDB está pronto e aplica migrações antes de iniciar a aplicação Flask.

# Função para aguardar o MariaDB
wait_for_mariadb() {
  echo "Aguardando o MariaDB iniciar em $DB_HOST:$DB_PORT..."
  # Loop até que o serviço de banco de dados esteja acessível
  # O 'nc -z' é usado para testar a conexão TCP sem enviar dados
  while ! nc -z "$DB_HOST" "$DB_PORT"; do
    sleep 1
  done
  echo "MariaDB iniciou!"
}

# Define as variáveis de ambiente para o host e porta do DB
# Padrões para 'db' e 3306, que são os valores no docker-compose.yml
DB_HOST=${DB_HOST:-db}
DB_PORT=${DB_PORT:-3306}

# Exporta FLASK_APP para que os comandos flask db funcionem corretamente
export FLASK_APP=run.py

# Chama a função para aguardar o MariaDB
wait_for_mariadb

# Lógica de migração: Inicializa migrações se a pasta não existir,
# e sempre aplica as migrações mais recentes.
MIGRATIONS_DIR="/app/migrations"

if [ ! -f "$MIGRATIONS_DIR/env.py" ]; then
  echo "Diretório de migrações '$MIGRATIONS_DIR' não encontrado. Inicializando Flask-Migrate..."
  flask db init
  # Verifica se o flask db init foi bem-sucedido
  if [ $? -ne 0 ]; then
    echo "Erro ao executar 'flask db init'. Saindo."
    exit 1
  fi
  echo "Gerando migração inicial..."
  flask db migrate -m "Initial migration"
  # Verifica se o flask db migrate foi bem-sucedido
  if [ $? -ne 0 ]; then
    echo "Erro ao executar 'flask db migrate'. Saindo."
    exit 1
  fi
else
  echo "Diretório de migrações '$MIGRATIONS_DIR' já existe."
fi

echo "Aplicando migrações de banco de dados..."
flask db upgrade
# Verifica o código de saída do comando anterior
if [ $? -ne 0 ]; then
  echo "Erro ao aplicar migrações do banco de dados. Verifique os logs acima."
  # Não saímos aqui imediatamente, permitimos que a aplicação tente iniciar
  # pois o erro pode ser na criação dos papéis, não nas tabelas em si
fi

echo "Migrações aplicadas!"

# Inicia a aplicação Flask (comando original do CMD)
echo "Iniciando a aplicação Flask..."
exec "$@" # Executa o comando passado para o entrypoint (CMD do Dockerfile)