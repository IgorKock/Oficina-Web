from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from sqlalchemy.exc import OperationalError
from flask_login import LoginManager # Importa LoginManager

# Instâncias globais para o banco de dados, migrações e login manager.
# Estas instâncias são criadas aqui e depois inicializadas com a aplicação Flask.
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager() # Inicializa LoginManager

def create_app():
    """
    Cria e configura a instância da aplicação Flask.
    Esta função é chamada uma vez em `run.py` para obter a aplicação configurada.
    """
    app = Flask(__name__)

    # --- Configurações da Aplicação ---
    # Caminho para o seu banco de dados SQLite. Ele será criado na raiz do projeto.
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clientes.db' 
    # Desabilita o rastreamento de modificações do SQLAlchemy (melhora a performance).
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
    # Chave secreta para sessões do Flask (necessário para Flask-Login e flash messages).
    # MUITO IMPORTANTE: Mude esta chave para uma string longa e aleatória em produção.
    app.config['SECRET_KEY'] = 'sua_chave_secreta_muito_segura_e_longa_aqui_para_producao' 

    # --- Inicializa as Extensões com a Aplicação ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app) # Inicializa o Flask-Login com a aplicação

    # Define a rota para onde o utilizador será redirecionado se não estiver logado
    # 'main.login' refere-se ao nome da função da rota de login dentro do Blueprint 'main'.
    login_manager.login_view = 'main.login' 

    # --- Importa os Modelos do Banco de Dados ---
    # IMPORTANTE: Importa os modelos aqui, DENTRO da função create_app,
    # e APÓS db.init_app(app). Isso é crucial para evitar problemas de importação circular
    # e garantir que os modelos tenham acesso à instância 'db' correta.
    from . import models 

    # --- Configura a Função de Carregamento de Utilizador para o Flask-Login ---
    # Esta função é usada pelo Flask-Login para recarregar o utilizador da sessão.
    @login_manager.user_loader
    def load_user(user_id):
        """
        Função de carregamento de utilizador para o Flask-Login.
        Retorna um objeto Utilizador dado um ID de utilizador.
        """
        # Tenta carregar o utilizador pelo ID. Retorna None se o utilizador não for encontrado.
        return models.Utilizador.query.get(int(user_id))

    # --- Importa e Regista o Blueprint 'main' ---
    # Isso é CRUCIAL para que as rotas definidas em 'routes.py' sejam reconhecidas pelo Flask.
    from .routes import main
    app.register_blueprint(main) 

    # --- Lógica para Criar Tabelas e Adicionar Papéis Iniciais ---
    # Executa dentro do contexto da aplicação para garantir que o banco de dados esteja acessível.
    with app.app_context():
        db.create_all() # Cria todas as tabelas definidas nos modelos se elas não existirem.
        try:
            _add_initial_roles_on_startup() # Chama a função auxiliar para adicionar papéis.
        except OperationalError as e:
            # Captura erros se as tabelas não existirem (comum antes das migrações).
            print("\n--- ERRO CRÍTICO DE BANCO DE DADOS ---")
            print("Parece que a tabela 'papeis' não existe no seu banco de dados.")
            print("Isso geralmente acontece se as migrações do Flask-Migrate não foram aplicadas.")
            print("Por favor, execute os seguintes comandos no seu terminal (uma vez):")
            print("1. `flask db init` (se ainda não tiver a pasta 'migrations')")
            print("2. `flask db migrate -m \"Adiciona tabelas de Utilizadores e Papéis\"`")
            print("3. `flask db upgrade`")
            print("Após aplicar as migrações, execute `python run.py` novamente.")
            print("---------------------------------------\n")
            raise e # Levanta a exceção para que o erro seja visível e o processo pare.

    return app

# Função auxiliar para adicionar papéis iniciais (chamada dentro de create_app).
def _add_initial_roles_on_startup():
    """
    Adiciona papéis padrão ao banco de dados se eles não existirem.
    Esta função é idempotente (pode ser chamada várias vezes sem efeitos colaterais).
    """
    print("Verificando e adicionando papéis iniciais ao banco de dados automaticamente...")
    papeis_a_adicionar = [
        {'nome': 'Administrador', 'descricao': 'Acesso total ao sistema e gestão de utilizadores'},
        {'nome': 'Mecanico', 'descricao': 'Pode ver e atualizar ordens de serviço e veículos'},
        {'nome': 'Recepcionista', 'descricao': 'Pode gerir clientes e agendamentos'},
        {'nome': 'Gerente', 'descricao': 'Pode ver relatórios e gerir funcionários'}
    ]
    
    # Itera sobre os papéis e os adiciona se não existirem.
    for papel_data in papeis_a_adicionar:
        papel_existente = db.session.query(models.Papel).filter_by(nome=papel_data['nome']).first()
        if not papel_existente:
            novo_papel = models.Papel(nome=papel_data['nome'], descricao=papel_data['descricao'],
                               created_at=datetime.utcnow(), updated_at=datetime.utcnow())
            db.session.add(novo_papel)
            print(f"Papel '{papel_data['nome']}' adicionado.")
        else:
            print(f"Papel '{papel_data['nome']}' já existe.")
    
    db.session.commit() # Salva as alterações no banco de dados.
    print("Verificação e adição de papéis iniciais concluída.")