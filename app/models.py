from . import db
from sqlalchemy.event import listens_for
import pytz
from datetime import datetime
from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

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
utilizador_papeis = db.Table(
    'utilizador_papeis',
    db.Column('id_utilizador', db.Integer, db.ForeignKey('utilizadores.id'), primary_key=True),
    db.Column('id_papel', db.Integer, db.ForeignKey('papeis.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=db.func.current_timestamp()),
    db.Column('updated_at', db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
)

# Definição do modelo Papel (Role)
class Papel(db.Model):
    __tablename__ = 'papeis'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def __repr__(self):
        return f'<Papel {self.nome}>'

# Definição do modelo Utilizador (User) - Integrado com Flask-Login
class Utilizador(UserMixin, db.Model):
    __tablename__ = 'utilizadores' # Nome da tabela ajustado para português
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False) # Campo para armazenar o hash da senha
    telefone = db.Column(db.String(20), nullable=True)
    palavras_chave = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    # 🔹 NOVO: Campo para armazenar observações do utilizador
    observacoes = db.Column(db.Text, nullable=True)
    # 🔹 NOVO: Campo para armazenar o token de sessão para controle de login único
    session_token = db.Column(db.String(255), nullable=True)

    # Relacionamento muitos-para-muitos com Papel através da tabela de associação
    papeis = db.relationship('Papel', secondary=utilizador_papeis, backref=db.backref('utilizadores', lazy='dynamic'))

    def set_senha(self, senha):
        """Gera o hash da senha."""
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        """Verifica se a senha fornecida corresponde ao hash."""
        return check_password_hash(self.senha_hash, senha)
    
    def is_admin(self):
        """Verifica se o utilizador tem o papel 'admin'."""
        # Se 'papeis' for None ou não tiver um 'id' atribuído
        if not self.papeis:
            return False
        return any(papel.nome == 'Administrador' for papel in self.papeis) # 🔹 Corrigido para 'Administrador'

    def is_mecanico(self):
        return any(papel.nome == 'Mecânico' for papel in self.papeis)

    def is_recepcionista(self):
        return any(papel.nome == 'Recepcionista' for papel in self.papeis)

    def is_gerente(self):
        return any(papel.nome == 'Gerente' for papel in self.papeis)

    def __repr__(self):
        return f'<Utilizador {self.nome}>'


# Evento para o modelo Utilizador
@listens_for(Utilizador, 'before_insert')
@listens_for(Utilizador, 'before_update')
def update_utilizador_timestamps(mapper, connection, target):
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(fuso_brasilia)
    if not hasattr(target, 'created_at') or target.created_at is None:
        target.created_at = agora.astimezone(pytz.utc)
    target.updated_at = agora.astimezone(pytz.utc)


class Cliente(db.Model):
    __tablename__ = 'clientes' # Nome da tabela ajustado
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(20), nullable=True)
    cnpj = db.Column(db.String(20), nullable=True)
    apelido = db.Column(db.String(100), nullable=True)
    endereco = db.Column(db.String(255), nullable=True)
    numero = db.Column(db.String(20), nullable=True)
    complemento = db.Column(db.String(100), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    cidade = db.Column(db.String(100), nullable=True)
    estado = db.Column(db.String(2), nullable=True)
    cep = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    telefones = db.relationship('Telefone', backref='cliente', lazy='dynamic', cascade="all, delete-orphan") # 🔹 Cascade para telefones
    carros = db.relationship('Carro', backref='cliente', lazy='dynamic', cascade="all, delete-orphan") # 🔹 Cascade para carros
    historicos = db.relationship('Historico', backref='cliente', lazy='dynamic', cascade="all, delete-orphan") # 🔹 Cascade para históricos
    pagamentos = db.relationship('Pagamento', backref='cliente', lazy='dynamic', cascade="all, delete-orphan") # 🔹 Cascade para pagamentos

    def __repr__(self):
        return f'<Cliente {self.nome}>'

# Evento para o modelo Cliente
@listens_for(Cliente, 'before_insert')
@listens_for(Cliente, 'before_update')
def update_cliente_timestamps(mapper, connection, target):
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(fuso_brasilia)
    if not hasattr(target, 'created_at') or target.created_at is None:
        target.created_at = agora.astimezone(pytz.utc)
    target.updated_at = agora.astimezone(pytz.utc)


class Telefone(db.Model):
    __tablename__ = 'telefones'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    numero = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def __repr__(self):
        return f'<Telefone {self.numero}>'

# Evento para o modelo Telefone
@listens_for(Telefone, 'before_insert')
@listens_for(Telefone, 'before_update')
def update_telefone_timestamps(mapper, connection, target):
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(fuso_brasilia)
    if not hasattr(target, 'created_at') or target.created_at is None:
        target.created_at = agora.astimezone(pytz.utc)
    target.updated_at = agora.astimezone(pytz.utc)


class Carro(db.Model):
    __tablename__ = 'carros'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    marca = db.Column(db.String(50), nullable=False)
    modelo = db.Column(db.String(50), nullable=False)
    motor = db.Column(db.String(50), nullable=True)
    ano = db.Column(db.Integer, nullable=True)
    placa = db.Column(db.String(10), unique=True, nullable=False)
    quilometragem = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    historicos = db.relationship('Historico', backref='carro', lazy='dynamic', cascade="all, delete-orphan") # 🔹 Relacionamento com Historico (mantido)
    pagamentos = db.relationship('Pagamento', backref='carro', lazy='dynamic', cascade="all, delete-orphan") # 🔹 Relacionamento com Pagamento

    def __repr__(self):
        return f'<Carro {self.marca} {self.modelo}>'

# Evento para o modelo Carro
@listens_for(Carro, 'before_insert')
@listens_for(Carro, 'before_update')
def update_carro_timestamps(mapper, connection, target):
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(fuso_brasilia)
    if not hasattr(target, 'created_at') or target.created_at is None:
        target.created_at = agora.astimezone(pytz.utc)
    target.updated_at = agora.astimezone(pytz.utc)


class Peca(db.Model):
    __tablename__ = 'pecas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(200), nullable=True)
    quantidade = db.Column(db.Integer, nullable=False)
    preco = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def __repr__(self):
        return f'<Peca {self.nome}>'

# Evento para o modelo Peca
@listens_for(Peca, 'before_insert')
@listens_for(Peca, 'before_update')
def update_peca_timestamps(mapper, connection, target):
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(fuso_brasilia)
    if not hasattr(target, 'created_at') or target.created_at is None:
        target.created_at = agora.astimezone(pytz.utc)
    target.updated_at = agora.astimezone(pytz.utc)


class Historico(db.Model): # 🔹 MANTIDO COMO 'Historico'
    __tablename__ = 'historicos'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    carro_id = db.Column(db.Integer, db.ForeignKey('carros.id'), nullable=False)
    data = db.Column(db.DateTime, nullable=False) # Removido o default para controle manual
    descricao = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    pagamentos = db.relationship('Pagamento', backref='historico', lazy='dynamic', cascade="all, delete-orphan") # 🔹 Relacionamento com Pagamento (mantido)

    def __repr__(self):
        return f'<Historico {self.id}>'

# Evento para o modelo Historico
@listens_for(Historico, 'before_insert')
@listens_for(Historico, 'before_update')
def ajustar_data_historico_para_utc(mapper, connection, target):
    if target.data and target.data.tzinfo is None:
        fuso_brasilia = pytz.timezone('America/Sao_Paulo')
        local_dt = fuso_brasilia.localize(target.data)
        target.data = local_dt.astimezone(pytz.utc)
    
    # Atualiza created_at e updated_at se necessário
    agora = datetime.now(pytz.timezone('America/Sao_Paulo')) # Horário de Brasília
    if not hasattr(target, 'created_at') or target.created_at is None:
        target.created_at = agora.astimezone(pytz.utc)
    target.updated_at = agora.astimezone(pytz.utc)


class Pagamento(db.Model):
    __tablename__ = 'pagamentos'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    carro_id = db.Column(db.Integer, db.ForeignKey('carros.id'), nullable=False)  # 🔹 Associando ao veículo
    historico_id = db.Column(db.Integer, db.ForeignKey('historicos.id'), nullable=False)  # 🔹 Associando ao serviço (referencia 'historicos')
    data = db.Column(db.DateTime, nullable=False) # Removido o default para controle manual no routes.py
    valor = db.Column(db.Float, nullable=False)
    metodo = db.Column(db.String(50), nullable=False)
    tipo_pagamento = db.Column(db.String(20), nullable=True)
    parcelas = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp()) # Adicionado
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp()) # Adicionado

    def __repr__(self):
        return f'<Pagamento {self.id}>'

# Evento para o modelo Pagamento
@listens_for(Pagamento, 'before_insert')
@listens_for(Pagamento, 'before_update')
def ajustar_data_pagamento_para_utc(mapper, connection, target):
    # Se a data já tiver fuso horário (ex: vindo de datetime.now(pytz.utc)), não localize novamente
    if target.data and target.data.tzinfo is None:
        fuso_brasilia = pytz.timezone('America/Sao_Paulo')
        local_dt = fuso_brasilia.localize(target.data)
        target.data = local_dt.astimezone(pytz.utc)
    
    # Atualiza created_at e updated_at se necessário
    agora = datetime.now(pytz.timezone('America/Sao_Paulo')) # Horário de Brasília
    if not hasattr(target, 'created_at') or target.created_at is None:
        target.created_at = agora.astimezone(pytz.utc)
    target.updated_at = agora.astimezone(pytz.utc)