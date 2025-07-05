#!/bin/bash
set -e # Sai imediatamente se um comando falhar

# Função para aguardar o MariaDB
wait_for_mariadb() {
  echo "Aguardando o MariaDB iniciar em $DB_HOST:$DB_PORT..."
  local timeout=30
  local start_time=$(date +%s)
  while ! nc -z "$DB_HOST" "$DB_PORT"; do
    current_time=$(date +%s)
    elapsed_time=$((current_time - start_time))
    if [ $elapsed_time -ge $timeout ]; then
      echo "Ainda aguardando o MariaDB..."
      exit 1
    fi
    echo "Tempo limite excedido ao aguardar o MariaDB."
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
# Se o 'flask db upgrade' falhar, o script vai sair devido ao 'set -e'.
flask db upgrade

echo "Migrações aplicadas com sucesso!"

# Tenta conectar ao banco de dados e verificar/adicionar papéis iniciais
# ESTA PARTE AGORA RODA DEPOIS do flask db upgrade.
# Usando 'python3 -c' com uma string de comando Python mais robusta e em UMA ÚNICA LINHA.
echo "Verificando e adicionando papéis iniciais ao banco de dados..."
MAX_RETRIES=10
RETRY_COUNT=0

# Python command to execute. Now in a single line with escaped single quotes.
# IMPORTANT: Adjust 'from app.models' and 'from app.routes' based on your actual project structure.
# If models.py and routes.py are directly in /app, use 'from models import ...' and 'from routes import ...'
PYTHON_COMMAND='import sys; import os; sys.path.insert(0, "/app"); from run import app; from app.models import db, Papel; from app.routes import verify_initial_roles; try: with app.app_context(): print("Conexão com o banco de dados estabelecida com sucesso para papéis!"); verify_initial_roles(); sys.exit(0) except Exception as e: print(f"Erro ao verificar/adicionar papéis: {e}", file=sys.stderr); sys.exit(1)'

until python3 -c "$PYTHON_COMMAND" || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
    RETRY_COUNT=$((RETRY_COUNT+1))
    echo "Conexão com o banco de dados ou verificação de papéis falhou. Tentativa $RETRY_COUNT/$MAX_RETRIES. Aguardando 5 segundos..."
    sleep 5
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "Falha ao conectar ao banco de dados ou verificar papéis após $MAX_RETRIES tentativas. Saindo."
    exit 1
fi
echo "Verificação e adição de papéis concluída."

# Inicia a aplicação Flask (comando original do CMD)
echo "Iniciando a aplicação Flask..."
exec "$@" # Executa o comando passado para o entrypoint (CMD do Dockerfile)