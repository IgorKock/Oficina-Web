from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from sqlalchemy.exc import OperationalError # Importar OperationalError para tratamento de erro
from flask_login import LoginManager # Importa LoginManager

# A instância 'db' é criada aqui, fora da função create_app
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager() # Inicializa LoginManager

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clientes.db' # Mantendo SQLite
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
        Função de carregamento de utilizador para Flask-Login.
        Retorna uma instância de Utilizador dado um user_id.
        """
        return models.Utilizador.query.get(int(user_id))

    # Adiciona a lógica de setup de papéis aqui, dentro do contexto da aplicação
    with app.app_context():
        db.create_all() # Garante que as tabelas são criadas se não existirem
        try:
            _add_initial_roles_on_startup()
        except OperationalError as e:
            print("\n--- ERRO CRÍTICO DE BANCO DE DADOS ---")
            print("Parece que a tabela 'papeis' não existe no seu banco de dados.")
            print("Isso geralmente acontece se as migrações do Flask-Migrate não foram aplicadas.")
            print("Por favor, execute os seguintes comandos no seu terminal (uma vez):")
            print("1. flask db init (se ainda não tiver a pasta 'migrations')")
            print("2. flask db migrate -m \"Adiciona tabelas de Utilizadores e Papéis\"")
            print("3. flask db upgrade")
            print("Após aplicar as migrações, execute 'python run.py' novamente.")
            print("---------------------------------------\n")
            raise e

    from .routes import main
    app.register_blueprint(main)

    return app

# Função auxiliar para adicionar papéis iniciais
# Esta função é chamada dentro de create_app()
def _add_initial_roles_on_startup():
    """
    Adiciona papéis padrão ao banco de dados se eles não existirem.
    Esta função é idempotente.
    """
    print("Verificando e adicionando papéis iniciais ao banco de dados automaticamente...")
    papeis_a_adicionar = [
        {'nome': 'Administrador', 'descricao': 'Acesso total ao sistema e gestão de utilizadores'},
        {'nome': 'Mecanico', 'descricao': 'Pode ver e atualizar ordens de serviço e veículos'},
        {'nome': 'Rececionista', 'descricao': 'Pode gerir clientes e agendamentos'},
        {'nome': 'Gerente', 'descricao': 'Pode ver relatórios e gerir funcionários'}
    ]
    
    for papel_data in papeis_a_adicionar:
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