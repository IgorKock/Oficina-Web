#!/bin/bash
# entrypoint.sh

# Espera até que o serviço 'db' esteja disponível na porta 3306
# O 'db' é o nome do serviço MariaDB no docker-compose.yml
echo "Aguardando o MariaDB iniciar em db:3306..."
# Loop até que o netcat consiga conectar à porta 3306 do host 'db'
while ! nc -z db 3306; do
  sleep 1 # Espera 1 segundo antes de tentar novamente
done
echo "MariaDB iniciou!"

# Executa as migrações do Flask-Migrate
# Garante que o banco de dados está atualizado antes da aplicação iniciar
echo "Aplicando migrações de banco de dados..."
flask db upgrade
echo "Migrações aplicadas!"

# Inicia a aplicação Flask
echo "Iniciando a aplicação Flask..."
exec python3 run.py