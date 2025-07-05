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
# Se o 'flask db upgrade' falhar, o script vai sair devido ao 'set -e'.
flask db upgrade

echo "Migrações aplicadas com sucesso!"

# Tenta conectar ao banco de dados e verificar/adicionar papéis iniciais
# ESTA PARTE AGORA RODA DEPOIS DO flask db upgrade, SEM UM LOOP 'UNTIL' QUE CAUSE ERROS PREMATUROS.
# Usando 'python3 -c' com uma string de comando Python mais robusta.
echo "Verificando e adicionando papéis iniciais ao banco de dados..."

# Python command to execute. Using triple quotes for multi-line string.
# CONFIRMADO: Seus modelos e rotas estão dentro de um pacote 'app' dentro de /app
PYTHON_COMMAND='''
import sys
import os
# Adiciona /app ao Python path para garantir que as importações funcionem corretamente
sys.path.insert(0, '/app')
from run import app # Assumindo que 'app' é importado de 'run.py'
from app.models import db, Papel # CONFIRMADO: Importa de app.models
from app.routes import verify_initial_roles # CONFIRMADO: Importa de app.routes

try:
    with app.app_context():
        print('Conexão com o banco de dados estabelecida com sucesso para papéis!')
        verify_initial_roles()
    sys.exit(0) # Sucesso
except Exception as e:
    print(f"Erro ao verificar/adicionar papéis: {e}", file=sys.stderr)
    sys.exit(1) # Falha
'''

# Executa o comando Python. O 'set -e' no início do script bash
# garantirá que se este comando Python falhar (sys.exit(1)),
# o script bash também sairá.
python3 -c "$PYTHON_COMMAND"

echo "Verificação e adição de papéis concluída."

# Inicia a aplicação Flask (comando original do CMD)
echo "Iniciando a aplicação Flask..."
exec "$@" # Executa o comando passado para o entrypoint (CMD do Dockerfile)