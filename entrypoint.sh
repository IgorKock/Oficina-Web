#!/bin/bash
set -e # Sai imediatamente se um comando falhar

# Função para aguardar o MariaDB
wait_for_mariadb() {
  echo "Aguardando o MariaDB iniciar em $DB_HOST:$DB_PORT..."
  # O 'nc -z' é usado para testar a conexão TCP sem enviar dados
  # Usamos um loop com timeout para robustez
  local timeout=30
  local start_time=$(date +%s)
  while ! nc -z "$DB_HOST" "$DB_PORT"; do
    current_time=$(date +%s)
    elapsed_time=$((current_time - start_time))
    if [ $elapsed_time -ge $timeout ]; then
      echo "Tempo limite excedido ao aguardar o MariaDB."
      exit 1
    fi
    echo "Ainda aguardando o MariaDB..."
    sleep 1
  done
  echo "MariaDB iniciou!"
}

# Define as variáveis de ambiente para o host e porta do DB
DB_HOST=${DB_HOST:-db}
DB_PORT=${DB_PORT:-3306}

# Exporta FLASK_APP para que os comandos flask db funcionem corretamente
export FLASK_APP=run.py # Confirme se o seu ficheiro principal é 'run.py'

# Chama a função para aguardar o MariaDB
wait_for_mariadb

# Lógica de migração: Inicializa migrações se a pasta não existir,
# e sempre aplica as migrações mais recentes.
MIGRATIONS_DIR="/app/migrations"

if [ ! -f "$MIGRATIONS_DIR/env.py" ]; then
  echo "Diretório de migrações '$MIGRATIONS_DIR' não encontrado. Inicializando Flask-Migrate..."
  flask db init || { echo "Erro: 'flask db init' falhou. Saindo."; exit 1; }
  echo "Gerando migração inicial..."
  flask db migrate -m "Initial migration" || { echo "Erro: 'flask db migrate' falhou. Saindo."; exit 1; }
else
  echo "Diretório de migrações '$MIGRATIONS_DIR' já existe."
fi

echo "Aplicando migrações de banco de dados..."
# É CRUCIAL que este comando seja bem-sucedido para que as tabelas sejam criadas.
flask db upgrade || { echo "--- ERRO CRÍTICO: FALHA NA APLICAÇÃO DE MIGRAÇÕES ---"; exit 1; }

echo "Migrações aplicadas com sucesso!"

# 💤 Delay mínimo para garantir que o banco finalize as alterações
sleep 2

# Inicia a aplicação Flask (comando original do CMD)
echo "Iniciando a aplicação Flask..."
exec "$@" # Executa o comando passado para o entrypoint (CMD do Dockerfile)