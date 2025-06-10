from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from sqlalchemy.exc import OperationalError, ProgrammingError
from flask_login import LoginManager
import os
import pytz # Importar pytz para o ajuste de fuso horário


# A instância 'db' é criada aqui, fora da função create_app
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager() # Inicializa LoginManager

def create_app():
    app = Flask(__name__)

    # Obter a string de conexão completa do banco de dados da variável de ambiente
    # Se não estiver definida (ex: em desenvolvimento local sem Docker Compose),
    # usa os valores padrão para construir a string.
    # Note que o 'db' no host é o nome do serviço MariaDB no docker-compose.yml
    # DB_USER = os.environ.get('DB_USER', 'seu_usuario')
    # DB_PASSWORD = os.environ.get('DB_PASSWORD', 'sua_senha') # CERTIFIQUE-SE QUE ESTA SENHA ESTÁ CORRETA E É A MESMA DO MARIADB
    # DB_HOST = os.environ.get('DB_HOST', 'localhost')
    # DB_NAME = os.environ.get('DB_NAME', 'oficina_web')
    
    db_uri = os.environ.get('SQLALCHEMY_DATABASE_URI') or \
             f"mysql+pymysql://{os.environ.get('DB_USER', 'user_app')}:" \
             f"{os.environ.get('DB_PASSWORD', 'password_app')}@" \
             f"{os.environ.get('DB_HOST', 'localhost')}:3306/" \
             f"{os.environ.get('DB_NAME', 'oficina_web')}"


    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'sua_chave_secreta_muito_segura' # Necessário para sessões do Flask-Login

    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app) # Inicializa o Flask-Login com a aplicação
    login_manager.login_view = 'main.login' # Define a rota para onde o utilizador será redirecionado se não estiver logado

    # IMPORTANTE: Importa os modelos aqui, DENTRO da função create_app,
    # e APÓS db.init_app(app). Isso evita a importação circular.
    from . import models

    # Configura o user_loader para o Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        """
        Função de carregamento de utilizador para o Flask-Login.
        """
        return models.Utilizador.query.get(int(user_id))

    # Importa e registra os Blueprints
    from .routes import main
    app.register_blueprint(main)

    # Chamamos a função de adição de papéis DENTRO do contexto da aplicação.
    # Ela mesma terá tratamento de erro para quando a tabela não existir.
    with app.app_context():
        # REMOVIDO: db.create_all() - O Flask-Migrate se encarrega disso
        _add_initial_roles_on_startup()


    return app

def _add_initial_roles_on_startup():
    from . import models # Importa models aqui para evitar circularidade
    papel_administrador_data = {'nome': 'Administrador', 'descricao': 'Administrador do sistema com acesso total.'}
    papel_mecanico_data = {'nome': 'Mecanico', 'descricao': 'Utilizador com permissões de Mecânico.'}
    papel_recepcionista_data = {'nome': 'Recepcionista', 'descricao': 'Pode gerir clientes e agendamentos'}
    papel_gerente_data = {'nome': 'Gerente', 'descricao': 'Pode ver relatórios e gerir funcionários'}

    papeis_iniciais = [papel_administrador_data, papel_mecanico_data, papel_recepcionista_data, papel_gerente_data]

    print("Verificando e adicionando papéis iniciais ao banco de dados...")
    try:
        for papel_data in papeis_iniciais:
            # Tenta consultar a tabela. Se ela não existir, ProgrammingError será levantado.
            papel_existente = models.Papel.query.filter_by(nome=papel_data['nome']).first()
            if not papel_existente:
                novo_papel = models.Papel(nome=papel_data['nome'], descricao=papel_data['descricao'],
                                       created_at=datetime.utcnow(), updated_at=datetime.utcnow())
                db.session.add(novo_papel)
                print(f"Papel '{papel_data['nome']}' adicionado.")
            else:
                print(f"Papel '{papel_data['nome']}' já existe.")
        db.session.commit()
        print("Verificação e adição de papéis iniciais concluída.")
    except ProgrammingError as e:
        # Erro específico quando a tabela não existe
        db.session.rollback() # Garante que a sessão seja limpa
        print("\n--- ERRO: A tabela 'papeis' não existe no banco de dados. ---")
        print("Isso é normal se você está executando 'flask db init', 'migrate' ou 'upgrade'.")
        print("Por favor, certifique-se de que as migrações foram aplicadas corretamente:")
        print("1. No Prompt de Comando, defina a variável de ambiente: set FLASK_APP=run.py")
        print("2. flask db init (APENAS na primeira vez que usar Flask-Migrate neste projeto)")
        print("3. flask db migrate -m 'Cria tabelas iniciais para MariaDB'")
        print("4. flask db upgrade")
        print("Após aplicar as migrações, execute 'python run.py' novamente para adicionar os papéis.")
        print("-------------------------------------------\n")
        # Não levanta o erro novamente para que o comando Flask-Migrate possa continuar
    except OperationalError as e:
        # Para outros erros de conexão ou operação do BD (ex: credenciais erradas)
        db.session.rollback()
        print("\n--- ERRO CRÍTICO DE BANCO DE DADOS ---")
        print("Parece que há um problema de conexão ou configuração com o MariaDB.")
        print("Verifique se o servidor MariaDB está ativo e se a base de dados, usuário e senha foram criados corretamente.")
        print(f"Detalhes do erro: {e}")
        print("---------------------------------------\n")
        raise e # Levanta o erro para que o processo seja interrompido
    except Exception as e:
        # Para qualquer outro erro inesperado
        db.session.rollback()
        print(f"Ocorreu um erro inesperado ao adicionar papéis iniciais: {e}")
        raise e