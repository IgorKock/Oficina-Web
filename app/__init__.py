from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from sqlalchemy.exc import OperationalError, ProgrammingError
from flask_login import LoginManager
import os
import pytz # Importar pytz para manipulação de fuso horário
import time # Importar time para adicionar pausas

# A instância 'db' é criada aqui, fora da função create_app
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager() # Inicializa LoginManager

def create_app():
    app = Flask(__name__)

    # Obter variáveis de ambiente, com valores padrão de fallback
    DB_USER = os.environ.get('DB_USER', 'flask_user')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '123')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_NAME = os.environ.get('DB_NAME', 'oficina_web')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sua_chave_secreta_muito_segura_padrao')

    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = SECRET_KEY

    # Inicializa as extensões Flask com a aplicação (AQUI É A ÚNICA VEZ!)
    db.init_app(app)
    migrate.init_app(app, db) # Migração também inicializa uma vez

    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    from .models import Utilizador, Papel # Importa os modelos aqui

    @login_manager.user_loader
    def load_user(user_id):
        return Utilizador.query.get(int(user_id))

    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # Contexto da aplicação para operações de inicialização
    with app.app_context():
        # Lógica de retry para a conexão ao banco de dados e inicialização de papéis
        max_retries = 10
        retry_delay = 5 # segundos
        
        for i in range(max_retries):
            try:
                print(f"Tentando conectar ao banco de dados e verificar papéis... Tentativa {i+1}/{max_retries}")
                # Tenta uma operação simples para verificar a conexão
                # Se não houver tabelas, ainda pode lançar ProgrammingError
                db.session.execute(db.text("SELECT 1")).scalar()
                print("Conexão com o banco de dados estabelecida com sucesso!")
                
                # Se a conexão for bem-sucedida, tentar adicionar papéis
                _add_initial_roles_on_startup(app)
                print("Aplicação iniciada com sucesso e papéis iniciais verificados.")
                break # Sai do loop se tudo deu certo
                
            except ProgrammingError as e:
                db.session.rollback()
                print("\n--- ERRO DE MIGRAÇÃO DE BANCO DE DADOS ---")
                print(f"Detalhes do erro: {e}")
                print("Parece que as tabelas do banco de dados não foram criadas.")
                print("Por favor, certifique-se de que as migrações foram aplicadas corretamente:")
                print("1. No Prompt de Comando, defina a variável de ambiente: set FLASK_APP=run.py")
                print("2. flask db init (APENAS na primeira vez que usar Flask-Migrate neste projeto)")
                print("3. flask db migrate -m 'Cria tabelas iniciais para MariaDB'")
                print("4. flask db upgrade")
                print("Após aplicar as migrações, execute 'python run.py' novamente para adicionar os papéis.")
                print("-------------------------------------------\n")
                break # Sai do loop, pois este erro indica que as tabelas não existem.
                      # O usuário precisa rodar as migrações manualmente.
            except OperationalError as e:
                db.session.rollback()
                print(f"Erro operacional ao conectar ao DB: {e}")
                if i < max_retries - 1:
                    print(f"Tentando novamente em {retry_delay} segundos...")
                    time.sleep(retry_delay)
                else:
                    print("\n--- ERRO CRÍTICO DE BANCO DE DADOS ---\n")
                    print("Não foi possível conectar ao MariaDB após várias tentativas.")
                    print("Verifique se o servidor MariaDB está ativo e acessível na rede Docker.")
                    print(f"Detalhes do último erro: {e}")
                    print("---------------------------------------\n")
                    raise # Levanta o erro após todas as tentativas falharem
            except Exception as e:
                db.session.rollback()
                print(f"Ocorreu um erro inesperado: {e}")
                if i < max_retries - 1:
                    print(f"Tentando novamente em {retry_delay} segundos...")
                    time.sleep(retry_delay)
                else:
                    print("\n--- ERRO INESPERADO CRÍTICO ---\n")
                    print("Não foi possível iniciar a aplicação devido a um erro inesperado após várias tentativas.")
                    print(f"Detalhes do último erro: {e}")
                    print("---------------------------------------\n")
                    raise

    return app

# Função auxiliar para adicionar papéis iniciais ao banco de dados
def _add_initial_roles_on_startup(app):
    from .models import Papel # Importa o modelo Papel aqui para evitar importações circulares
    initial_roles = [
        {'nome': 'admin', 'descricao': 'Acesso total ao sistema e gestão de utilizadores'},
        {'nome': 'mecanico', 'descricao': 'Gerencia ordens de serviço, peças e históricos de carros'},
        {'nome': 'rececionista', 'descricao': 'Gerencia clientes, carros e agendamentos'},
        {'nome': 'gerente', 'descricao': 'Supervisão geral, relatórios e gestão de pagamentos'}
    ]

    # No app_context, db.session e Papel já estão disponíveis.
    print("Verificando e adicionando papéis iniciais ao banco de dados...")
    for papel_data in initial_roles:
        papel_existente = Papel.query.filter_by(nome=papel_data['nome']).first()
        if not papel_existente:
            novo_papel = Papel(nome=papel_data['nome'], descricao=papel_data['descricao'])
            db.session.add(novo_papel)
            print(f"Adicionado papel: {papel_data['nome']}")
    db.session.commit() # Confirma as alterações no banco de dados
    print("Verificação e adição de papéis concluída.")