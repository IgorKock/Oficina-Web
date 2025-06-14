from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from sqlalchemy.exc import OperationalError, ProgrammingError
from flask_login import LoginManager
import os
import pytz # Importar pytz para manipulação de fuso horário

# A instância 'db' é criada aqui, fora da função create_app
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager() # Inicializa LoginManager

def create_app():
    app = Flask(__name__)

    # Obter variáveis de ambiente, com valores padrão de fallback
    # Estes valores padrão só serão usados se as variáveis de ambiente não forem definidas
    # Pelo Docker Compose, elas *serão* definidas, então os padrões são apenas para segurança
    DB_USER = os.environ.get('DB_USER', 'flask_user')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '123')
    DB_HOST = os.environ.get('DB_HOST', 'localhost') # No Docker Compose, será 'db'
    DB_NAME = os.environ.get('DB_NAME', 'oficina_web')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sua_chave_secreta_muito_segura_padrao')

    # Configura a URI de conexão com o banco de dados usando as variáveis de ambiente
    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = SECRET_KEY # Necessário para sessões do Flask-Login

    # Inicializa as extensões Flask com a aplicação
    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = 'main.login' # Define a rota de login para o Flask-Login

    # Importa os modelos aqui para evitar problemas de importação circular
    from .models import Utilizador, Papel 

    # Configura o user_loader para o Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return Utilizador.query.get(int(user_id))

    # Regista o Blueprint das rotas na aplicação
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # Contexto da aplicação para operações de inicialização
    with app.app_context():
        try:
            # Chama a função para adicionar papéis iniciais ao banco de dados
            _add_initial_roles_on_startup(app)
            print("Aplicação iniciada com sucesso e papéis iniciais verificados.")

        except ProgrammingError as e:
            db.session.rollback() # Reverte a transação em caso de erro
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
            # Não levanta o erro novamente para que o comando Flask-Migrate possa continuar
        except OperationalError as e:
            db.session.rollback() # Reverte a transação em caso de erro
            print("\n--- ERRO CRÍTICO DE BANCO DE DADOS ---\n")
            print("Parece que há um problema de conexão ou configuração com o MariaDB.")
            print("Verifique se o servidor MariaDB está ativo e se a base de dados, usuário e senha foram criados corretamente.")
            print(f"Detalhes do erro: {e}")
            print("---------------------------------------\n")
            raise e # Levanta o erro para que o processo seja interrompido
        except Exception as e:
            db.session.rollback() # Reverte a transação em caso de erro
            print(f"Ocorreu um erro inesperado ao adicionar papéis iniciais: {e}")
            raise e

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

    with app.app_context():
        print("Verificando e adicionando papéis iniciais ao banco de dados...")
        for papel_data in initial_roles:
            papel_existente = Papel.query.filter_by(nome=papel_data['nome']).first()
            if not papel_existente:
                novo_papel = Papel(nome=papel_data['nome'], descricao=papel_data['descricao'])
                db.session.add(novo_papel)
                print(f"Adicionado papel: {papel_data['nome']}")
        db.session.commit() # Confirma as alterações no banco de dados
        print("Verificação e adição de papéis concluída.")