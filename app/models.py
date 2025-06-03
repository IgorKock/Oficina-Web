from . import db 
from sqlalchemy.event import listens_for
import pytz
from datetime import datetime
from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin # Importa UserMixin para integração com Flask-Login

def para_utc(data_local, fuso_local='America/Sao_Paulo'):
    """
    Converte um objeto datetime local para UTC.
    Usado para garantir que os timestamps no banco de dados sejam consistentes.
    """
    fuso = pytz.timezone(fuso_local)
    
    # Verifica se o objeto `datetime` já tem `tzinfo`
    if data_local.tzinfo is None:
        # Se o objeto for naive, aplica o fuso horário local
        data_local = fuso.localize(data_local)
    
    # Converte para UTC
    return data_local.astimezone(pytz.utc)

# Tabela de associação para o relacionamento muitos-para-muitos entre Utilizadores e Papéis
# Esta tabela liga um utilizador a um ou mais papéis.
utilizador_papeis = db.Table(
    'utilizador_papeis',
    db.Column('id_utilizador', db.Integer, db.ForeignKey('utilizadores.id'), primary_key=True),
    db.Column('id_papel', db.Integer, db.ForeignKey('papeis.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
    db.Column('updated_at', db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
)

class Utilizador(db.Model, UserMixin): # Adiciona UserMixin para compatibilidade com Flask-Login
    """
    Tabela de Utilizadores/Funcionários da Oficina.
    Armazena informações sobre os utilizadores que podem aceder ao sistema.
    """
    __tablename__ = 'utilizadores'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False) # Armazena o hash da senha de forma segura
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=True)  # Novo campo: Telefone / WhatsApp
    palavras_chave = db.Column(db.String(255), nullable=True)  # Novo campo: Tags para qualificar o utilizador
    created_at = db.Column(db.DateTime, default=datetime.utcnow) # Timestamp de criação
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) # Timestamp de última atualização

    # Relacionamento muitos-para-muitos com Papel através da tabela de associação
    papeis = db.relationship('Papel', secondary=utilizador_papeis, backref=db.backref('utilizadores', lazy='dynamic'), lazy='dynamic')

    def set_senha(self, senha):
        """Define a senha do utilizador, armazenando seu hash de forma segura."""
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        """Verifica se a senha fornecida corresponde ao hash armazenado."""
        return check_password_hash(self.senha_hash, senha)

    def is_admin(self):
        """
        VERIFICA SE O UTILIZADOR POSSUI O PAPEL DE 'ADMINISTRADOR'.
        Isso é usado para controlar o acesso a certas funcionalidades ou visualizações.
        """
        # Itera sobre os papéis associados ao utilizador e verifica se algum deles
        # tem o nome 'Administrador'.
        return any(papel.nome == 'Administrador' for papel in self.papeis)

    def __repr__(self):
        return f"<Utilizador(id={self.id}, nome='{self.nome}', email='{self.email}')>"

class Papel(db.Model):
    """
    Tabela de Papéis.
    Define os diferentes níveis de acesso ou funções dentro do sistema (ex: Administrador, Mecânico).
    """
    __tablename__ = 'papeis'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False) # Nome único do papel (ex: 'Administrador')
    descricao = db.Column(db.String(255), nullable=True) # Descrição do papel
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Papel(id={self.id}, nome='{self.nome}')>"


# --- Modelos Existentes (do seu esquema original) ---

class Peca(db.Model):
    __tablename__ = 'pecas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)  # Nome da peça
    descricao = db.Column(db.String(200), nullable=True)  # Descrição da peça
    quantidade = db.Column(db.Integer, nullable=False, default=0)  # Quantidade disponível
    preco = db.Column(db.Float, nullable=False)  # Preço por unidade

class Carro(db.Model):
    __tablename__ = 'carros'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    marca = db.Column(db.String(50), nullable=False)
    modelo = db.Column(db.String(50), nullable=False)
    motor = db.Column(db.String(50), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    placa = db.Column(db.String(20), nullable=False)
    quilometro = db.Column(db.Integer, nullable=False)

class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    endereco = db.Column(db.String(200), nullable=True)  # Endereço do cliente
    estado = db.Column(db.String(50), nullable=True)  # Estado do cliente
    cidade = db.Column(db.String(100), nullable=True)  # Cidade do cliente
    cep = db.Column(db.String(10), nullable=True)  # CEP do cliente
    bairro = db.Column(db.String(200), nullable=True)  # Bairro do cliente
    cpf = db.Column(db.String(14), nullable=True) # CPF do cliente
    apelido = db.Column(db.String(500)) # Apelido/Nome Social do cliente
    cnpj = db.Column(db.String(20), nullable=True) # CNPJ do cliente
    telefones = db.relationship('Telefone', backref='cliente', lazy=True)
    historicos = db.relationship('Historico', backref='cliente', lazy=True)
    pagamentos = db.relationship('Pagamento', backref='cliente', lazy=True)

class Telefone(db.Model):
    __tablename__ = 'telefones'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(15), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)

class Historico(db.Model):
    __tablename__ = 'historicos'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    carro_id = db.Column(db.Integer, db.ForeignKey('carros.id'), nullable=False)  # 🔹 Associando ao carro
    data = db.Column(db.DateTime, nullable=False)  
    descricao = db.Column(db.String(200), nullable=False)

    carro = db.relationship('Carro', backref=db.backref('historicos', lazy='dynamic'))  # 🔹 Relacionamento com Carro

# Evento para o modelo Historico: Ajusta a data para UTC antes de inserir
@listens_for(Historico, 'before_insert')
def ajustar_data_historico_para_utc(mapper, connect, target):
    if target.data:
        target.data = para_utc(target.data)

class Pagamento(db.Model):
    __tablename__ = 'pagamentos'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    carro_id = db.Column(db.Integer, db.ForeignKey('carros.id'), nullable=False)  # 🔹 Associando ao veículo
    historico_id = db.Column(db.Integer, db.ForeignKey('historicos.id'), nullable=False)  # 🔹 Associando ao serviço
    data = db.Column(db.DateTime, default=db.func.current_timestamp())  
    valor = db.Column(db.Float, nullable=False)
    metodo = db.Column(db.String(50), nullable=False)
    tipo_pagamento = db.Column(db.String(20), nullable=True)
    parcelas = db.Column(db.Integer, nullable=True)

    carro = db.relationship('Carro', backref=db.backref('pagamentos', lazy='dynamic'))
    historico = db.relationship('Historico', backref=db.backref('pagamentos', lazy='dynamic'))

# Evento para o modelo Pagamento: Ajusta a data para UTC antes de inserir
@listens_for(Pagamento, 'before_insert')
def ajustar_data_pagamento_para_utc(mapper, connect, target):
    if target.data:
        target.data = para_utc(target.data)