from . import db
from sqlalchemy.event import listens_for
import pytz
from datetime import datetime
from sqlalchemy.sql import func

def para_utc(data_local, fuso_local='America/Sao_Paulo'):
    fuso = pytz.timezone(fuso_local)
    
    # Verifica se o objeto `datetime` já tem `tzinfo`
    if data_local.tzinfo is None:
        # Se o objeto for naive, aplica o fuso horário local
        data_local = fuso.localize(data_local)
    
    # Converte para UTC
    return data_local.astimezone(pytz.utc)

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
    data = db.Column(db.DateTime, nullable=False)  # Garante que o campo data é obrigatório
    descricao = db.Column(db.String(200), nullable=False)

# Evento para o modelo Historico
@listens_for(Historico, 'before_insert')
def ajustar_data_para_utc(mapper, connect, target):
    if target.data:
        target.data = para_utc(target.data)

class Pagamento(db.Model):
    __tablename__ = 'pagamentos'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    data = db.Column(db.DateTime, default=db.func.current_timestamp())  # Armazena em UTC
    valor = db.Column(db.Float, nullable=False)
    metodo = db.Column(db.String(50), nullable=False)
    tipo_pagamento = db.Column(db.String(20), nullable=True)
    parcelas = db.Column(db.Integer, nullable=True)

# Evento para o modelo Pagamento
@listens_for(Pagamento, 'before_insert')
def ajustar_data_para_utc(mapper, connect, target):
    if target.data:
        target.data = para_utc(target.data)