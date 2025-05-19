from flask import Blueprint, render_template, request, redirect, url_for
from .models import db, Cliente, Telefone, Historico, Pagamento, Carro, Peca
from datetime import datetime, timedelta
import pytz

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

# Função para ajustar o horário
def ajustar_para_brasilia(data_utc):
    if data_utc.tzinfo is None:  # Verifica se o objeto é "naive" (sem fuso horário)
        fuso_brasilia = pytz.timezone('America/Sao_Paulo')
        return fuso_brasilia.localize(data_utc)  # Adiciona o fuso horário de Brasília
    else:
        # Se já tiver fuso horário, ajusta para o horário de Brasília
        fuso_brasilia = pytz.timezone('America/Sao_Paulo')
        return data_utc.astimezone(fuso_brasilia)

@main.route('/inventario', methods=['GET'])
def inventario():
    query = request.args.get('query', '').lower()
    pecas = db.session.query(Peca).all()

    if query:
        pecas = [peca for peca in pecas if query in peca.nome.lower() or query in peca.descricao.lower()]

    return render_template('inventario.html', pecas=pecas, query=query)

@main.route('/listaclientes')
def client():
    query = request.args.get('query', '')  # Busca de clientes
    if query:
        clientes = Cliente.query.filter(Cliente.nome.ilike(f'%{query}%')).all()
    else:
        clientes = Cliente.query.all()
    return render_template('listacliente.html', clientes=clientes, search_query=query)

@main.route('/cliente/<int:id>')
def cliente(id):
    cliente = Cliente.query.get_or_404(id)
    telefones = Telefone.query.filter_by(cliente_id=id).all()
    historicos = Historico.query.filter_by(cliente_id=id).order_by(Historico.data.desc()).all()
    pagamentos = Pagamento.query.filter_by(cliente_id=id).order_by(Pagamento.data.desc()).all()
    carros = Carro.query.filter_by(cliente_id=id).all()  # Busca todos os carros do cliente
    # Ajustar os horários dos históricos e pagamentos para o fuso de Brasília
    for historico in historicos:
        historico.data = ajustar_para_brasilia(historico.data)

    for pagamento in pagamentos:
        pagamento.data = ajustar_para_brasilia(pagamento.data)

    return render_template('cliente.html', cliente=cliente, telefones=telefones, historicos=historicos, pagamentos=pagamentos, carros=carros)
    
@main.route('/add', methods=['POST'])
def add_cliente():
    nome = request.form['nome'].strip()
    numeros = request.form.getlist('numeros[]')
    cpf = request.form.get('cpf', '').strip()
    apelido = request.form['apelido'].strip()
    cliente_existente = Cliente.query.filter_by(nome=nome).first()
    if cliente_existente:
        return redirect(url_for('main.client', error="Cliente já cadastrado"))

    novo_cliente = Cliente(nome=nome, cpf=cpf, apelido=apelido)
    db.session.add(novo_cliente)
    db.session.commit()

    for numero in numeros:
        if numero.strip():
            novo_telefone = Telefone(numero=numero, cliente_id=novo_cliente.id)
            db.session.add(novo_telefone)
    db.session.commit()
    return redirect(url_for('main.client'))


@main.route('/add_telefone/<int:cliente_id>', methods=['POST'])
def add_telefone(cliente_id):
    numeros = request.form.getlist('numeros[]')  # Receber múltiplos números de telefone

    # Salvar os números de telefone no banco de dados
    for numero in numeros:
        if numero.strip():  # Certificar-se de que o número não está vazio
            novo_telefone = Telefone(numero=numero, cliente_id=cliente_id)
            db.session.add(novo_telefone)

    db.session.commit()  # Confirma as alterações no banco de dados

    # Redirecionar de volta para a página de detalhes do cliente
    #return redirect(url_for('main.listaclientes', id=cliente_id))
    return redirect(url_for('main.cliente', id=cliente_id))

@main.route('/update_telefone/<int:telefone_id>', methods=['POST'])
def update_telefone(telefone_id):
    novo_numero = request.form.get('numero', '').strip()
    
    telefone = Telefone.query.get_or_404(telefone_id)
    telefone.numero = novo_numero  # Atualiza o número no banco de dados
    db.session.commit()

    return redirect(url_for('main.cliente', id=telefone.cliente_id))

@main.route('/delete_telefone/<int:telefone_id>', methods=['POST'])
def delete_telefone(telefone_id):
    telefone = Telefone.query.get_or_404(telefone_id)
    db.session.delete(telefone)  # Remove o telefone do banco de dados
    db.session.commit()

    return redirect(url_for('main.cliente', id=telefone.cliente_id))

@main.route('/update_dados_cliente/<int:cliente_id>', methods=['POST'])
def update_dados_cliente(cliente_id):
    endereco = request.form['endereco']
    cidade = request.form['cidade']
    estado = request.form['estado']
    bairro = request.form['bairro']
    cep = request.form['cep']
    cpf = request.form['cpf']
    apelido = request.form['apelido']
    cliente = Cliente.query.get_or_404(cliente_id)
    cliente.cpf = cpf
    cliente.endereco = endereco
    cliente.cidade = cidade
    cliente.estado = estado
    cliente.cep = cep
    cliente.bairro = bairro
    cliente.apelido = apelido
    db.session.commit()

    return redirect(url_for('main.cliente', id=cliente_id))
    #return redirect(url_for('main.listaclientes', id=cliente_id))

@main.route('/add_historico/<int:cliente_id>', methods=['POST'])
def add_historico(cliente_id):
    descricao = request.form['descricao']

    # Obtém o horário atual no fuso horário de Brasília
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    hora_brasilia = datetime.now(fuso_brasilia)

    # Subtrai 3 horas diretamente
    hora_brasilia_menos_3 = hora_brasilia - timedelta(hours=3)

    # Cria o registro no banco de dados
    novo_historico = Historico(cliente_id=cliente_id, descricao=descricao, data=hora_brasilia_menos_3)
    db.session.add(novo_historico)
    db.session.commit()

    return redirect(url_for('main.cliente', id=cliente_id))
    #return redirect(url_for('main.listaclientes', id=cliente_id))

@main.route('/add_carros_cliente/<int:cliente_id>', methods=['POST'])
def add_carros(cliente_id):
    print(request.form) 
    carros = request.form.to_dict(flat=False)  # Pega todos os dados enviados

    for i in range(len(carros['marca'])):  # Itera pelos carros enviados
        novo_carro = Carro(
            cliente_id=cliente_id,
            marca=carros['marca'][i],
            modelo=carros['modelo'][i],
            motor=carros['motor'][i],
            ano=int(carros['ano'][i]),
            placa=carros['placa'][i],
            quilometro=int(carros['quilometro'][i])
        )
        db.session.add(novo_carro)

    db.session.commit()
    #print(url_for('main.cliente'))
    # Redireciona para a página do cliente
    return redirect(url_for('main.cliente', id=cliente_id))
    #return redirect(url_for('main.listaclientes', id=cliente_id))

@main.route('/update_carros_cliente/<int:cliente_id>', methods=['POST'])
def update_carros(cliente_id):
    # Busca todos os carros associados ao cliente
    carros = Carro.query.filter_by(cliente_id=cliente_id).all()
    
    for carro in carros:
        # Atualiza os dados dos carros usando os valores do formulário
        carro.marca = request.form.get(f'marca_{carro.id}', carro.marca)
        carro.modelo = request.form.get(f'modelo_{carro.id}', carro.modelo)
        carro.motor = request.form.get(f'motor{carro.id}', carro.motor)
        carro.ano = request.form.get(f'ano_{carro.id}', carro.ano)
        carro.placa = request.form.get(f'placa_{carro.id}', carro.placa)
        carro.quilometro = request.form.get(f'quilometro_{carro.id}', carro.quilometro)
        db.session.add(carro)

    db.session.commit()

    # Redireciona para a página do cliente
    return redirect(url_for('main.cliente', id=cliente_id))
    #return redirect(url_for('main.listaclientes', id=cliente_id))

@main.route('/add_pagamento/<int:cliente_id>', methods=['POST'])
def add_pagamento(cliente_id):
    valor = float(request.form['valor'])  # Pega o valor do pagamento
    metodo = request.form['metodo']  # Método de pagamento
    tipo_pagamento = request.form.get('tipo_cartao')  # Tipo: À vista ou Parcelado
    parcelas = request.form.get('parcelas')  # Número de parcelas (opcional)

    if parcelas:
        parcelas = int(parcelas)

    # Obter o horário atual no fuso de Brasília
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    hora_brasilia = datetime.now(fuso_brasilia)

    # Subtrair 3 horas diretamente
    hora_brasilia_menos_3 = hora_brasilia - timedelta(hours=3)

    # Criar o registro com o horário ajustado
    novo_pagamento = Pagamento(
        cliente_id=cliente_id,
        valor=valor,
        metodo=metodo,
        tipo_pagamento=tipo_pagamento,
        parcelas=parcelas,
        data=hora_brasilia_menos_3
    )
    db.session.add(novo_pagamento)
    db.session.commit()

    # Redirecionar para a página de detalhes do cliente
    return redirect(url_for('main.cliente', id=cliente_id))
    #return redirect(url_for('main.listaclientes', id=cliente_id))

@main.route('/add_peca', methods=['POST'])
def add_peca():
    nome = request.form['nome'].strip()
    descricao = request.form.get('descricao')
    quantidade = int(request.form['quantidade'])
    preco = float(request.form['preco'])

    # 🔹 Verificar se a peça já existe
    peca_existente = Peca.query.filter_by(nome=nome).first()
    if peca_existente:
        pecas = Peca.query.all()  # Mantém os dados do inventário visíveis
        return render_template('inventario.html', pecas=pecas, error="Erro: Esta peça já está cadastrada!")

    # 🔹 Criar nova peça
    nova_peca = Peca(nome=nome, descricao=descricao, quantidade=quantidade, preco=preco)
    db.session.add(nova_peca)
    db.session.commit()

    return redirect(url_for('main.inventario'))
   
@main.route('/update_peca/<int:id>', methods=['POST'])
def update_peca(id):
    peca = Peca.query.get_or_404(id)
    peca.nome = request.form['nome']
    peca.descricao = request.form.get('descricao')
    peca.quantidade = int(request.form['quantidade'])
    peca.preco = float(request.form['preco'])

    db.session.commit()

    return redirect(url_for('main.inventario'))
    
@main.route('/delete_peca/<int:id>', methods=['POST'])
def delete_peca(id):
    try:
        peca = Peca.query.get_or_404(id)  # Busca a peça pelo ID
        db.session.delete(peca)  # Remove a peça do banco de dados
        db.session.commit()  # Confirma a remoção
        return redirect(url_for('main.inventario'))  # Redireciona para a página do inventário
    except Exception as e:
        print(f"Erro ao remover peça: {e}")
        return "Erro interno ao remover a peça", 500