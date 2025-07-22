from flask import Flask, session # 🔹 Adicionado 'session'
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from sqlalchemy.exc import OperationalError, ProgrammingError
from flask_login import LoginManager, current_user # 🔹 Adicionado 'current_user'
import os
import pytz
import time

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

    # Inicializa as extensões Flask com a aplicação.
    # ISSO DEVE ACONTECER ANTES DE IMPORTAR OS MODELOS.
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    # IMPORTANTE: Importa os modelos aqui, DENTRO da função create_app,
    # e APÓS db.init_app(app). Isso evita a importação circular e garante
    # que o 'db' esteja totalmente inicializado.
    from . import models

    @login_manager.user_loader
    def load_user(user_id):
        # 🔹 NOVO: Lógica de verificação de sessão única no user_loader
        user = models.Utilizador.query.get(int(user_id))
        
        if user:
            # Verifica se o token de sessão do navegador corresponde ao do banco de dados
            # Se não corresponder, ou se o token do banco de dados for None (sessão inválida ou não iniciada)
            if 'session_token' not in session or user.session_token != session['session_token']:
                # Se os tokens não correspondem, ou se o token do DB é None,
                # isso significa que a sessão atual não é válida ou foi sobrescrita.
                # Retorna None para desautenticar o usuário.
                return None
        return user # Retorna o usuário se os tokens corresponderem ou se não houver token na sessão

    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # Chamamos a função de adição de papéis DENTRO do contexto da aplicação.
    # A própria função _add_initial_roles_on_startup AGORA gerencia seu próprio contexto.
    with app.app_context():
        _add_initial_roles_on_startup(app) # Passa 'app' como argumento

    return app

# Função auxiliar para adicionar papéis iniciais ao banco de dados
# Esta função AGORA aceita 'app_instance' e gerencia seu próprio app_context,
# tornando-a mais robusta para qualquer chamada.
def _add_initial_roles_on_startup(app_instance): # Aceita 'app_instance' como argumento
    from . import models # Importa models aqui para garantir acesso a db e Papel

    with app_instance.app_context(): # Gerencia o contexto internamente
        papel_administrador_data = {'nome': 'Administrador', 'descricao': 'Administrador do sistema com acesso total.'}
        papel_mecanico_data = {'nome': 'Mecanico', 'descricao': 'Utilizador com permissões de Mecânico.'}
        papel_recepcionista_data = {'nome': 'Recepcionista', 'descricao': 'Pode gerir clientes e agendamentos'}
        papel_gerente_data = {'nome': 'Gerente', 'descricao': 'Pode ver relatórios e gerir funcionários'}

        papeis_iniciais = [papel_administrador_data, papel_mecanico_data, papel_recepcionista_data, papel_gerente_data]

        print("Verificando e adicionando papéis iniciais ao banco de dados...")
        try:
            for papel_data in papeis_iniciais:
                papel_existente = models.Papel.query.filter_by(nome=papel_data['nome']).first()
                if not papel_existente:
                    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
                    agora_local = datetime.now(fuso_brasilia)
                    
                    novo_papel = models.Papel(nome=papel_data['nome'], descricao=papel_data['descricao'],
                                           created_at=agora_local.astimezone(pytz.utc), updated_at=agora_local.astimezone(pytz.utc))
                    db.session.add(novo_papel)
                    print(f"Papel '{papel_data['nome']}' adicionado.")
                else:
                    print(f"Papel '{papel_data['nome']}' já existe.")
            db.session.commit()
            print("Verificação e adição de papéis iniciais concluída.")
        except ProgrammingError as e:
            db.session.rollback()
            print("\n--- ERRO: A tabela 'papeis' não existe no banco de dados. ---")
            print("Isso é normal se você está executando 'flask db init', 'migrate' ou 'upgrade'.")
            print("Por favor, certifique-se de que as migrações foram aplicadas corretamente.")
            print(f"Detalhes do erro: {e}")
            print("-------------------------------------------\n")
        except OperationalError as e:
            db.session.rollback()
            print("\n--- ERRO CRÍTICO DE BANCO DE DADOS ---")
            print("Parece que há um problema de conexão ou configuração com o MariaDB.")
            print("Verifique se o servidor MariaDB está ativo e se a base de dados, usuário e senha foram criados corretamente.")
            print(f"Detalhes do erro: {e}")
            print("---------------------------------------\n")
            raise e
        except Exception as e:
            db.session.rollback()
            print(f"Ocorreu um erro inesperado ao adicionar papéis iniciais: {e}")
            raise e