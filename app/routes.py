from flask import Blueprint, render_template, request, redirect, url_for, flash
# Importa os modelos do esquema antigo, e os novos modelos Utilizador e Papel
from .models import db, Cliente, Telefone, Carro, Peca, Historico, Pagamento, Utilizador, Papel
from datetime import datetime, timedelta
import pytz
from werkzeug.security import generate_password_hash # Importa para hash de senha
from flask_login import login_user, logout_user, current_user, login_required # Importações do Flask-Login

# Cria um Blueprint para organizar as rotas.
# O nome 'main' é usado para referenciar as rotas (ex: url_for('main.login')).
main = Blueprint('main', __name__)

# Rota para a página inicial
@main.route('/')
@login_required # Esta rota requer que o utilizador esteja logado para ser acedida.
def index():
    # Renderiza o template 'index.html'.
    return render_template('index.html')

# Função auxiliar para ajustar o horário para Brasília
def ajustar_para_brasilia(data_utc):
    """
    Ajusta um objeto datetime para o fuso horário de Brasília.
    """
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    if data_utc.tzinfo is None:  # Verifica se o objeto é "naive" (sem fuso horário)
        return fuso_brasilia.localize(data_utc)  # Adiciona o fuso horário de Brasília
    else:
        # Se já tiver fuso horário, ajusta para o horário de Brasília
        return data_utc.astimezone(fuso_brasilia)

# ROTAS RELACIONADAS AO INVENTÁRIO E PEÇAS
@main.route('/inventario', methods=['GET'])
@login_required # Protege a rota
def inventario():
    query = request.args.get('query', '').lower()
    pecas = db.session.query(Peca).all()

    if query:
        pecas = [peca for peca in pecas if query in peca.nome.lower() or query in peca.descricao.lower()]

    return render_template('inventario.html', pecas=pecas, query=query)

# ROTAS RELACIONADAS A CLIENTES
@main.route('/listaclientes')
@login_required # Protege a rota
def client():
    query = request.args.get('query', '')  # Busca de clientes
    if query:
        clientes = Cliente.query.filter(Cliente.nome.ilike(f'%{query}%')).all()
    else:
        clientes = Cliente.query.all()
    return render_template('listacliente.html', clientes=clientes, search_query=query)

@main.route('/cliente/<int:id>')
@login_required # Protege a rota
def cliente(id):
    cliente = Cliente.query.get_or_404(id)
    telefones = Telefone.query.filter_by(cliente_id=id).all()
    historicos = Historico.query.filter_by(cliente_id=id).order_by(Historico.data.desc()).all()
    pagamentos = Pagamento.query.filter_by(cliente_id=id).order_by(Pagamento.data.desc()).all()
    carros = Carro.query.filter_by(cliente_id=id).all()  # Busca todos os carros do cliente
    
    # Ajustar os horários dos históricos e pagamentos para o fuso de Brasília
    for historico in historicos:
        historico.data = ajustar_para_brasilia(historico.data)
        # Verifica se o histórico tem pagamento associado (lógica original)
        historico.tem_pagamento = any(pagamento.historico_id == historico.id for pagamento in pagamentos)
        
    for pagamento in pagamentos:
        pagamento.data = ajustar_para_brasilia(pagamento.data)

    # Retorna o template com todos os dados
    return render_template('cliente.html', cliente=cliente, telefones=telefones, historicos=historicos, pagamentos=pagamentos, carros=carros)
    
@main.route('/add', methods=['POST'])
@login_required # Protege a rota
def add_cliente():
    nome = request.form['nome'].strip()
    numeros = request.form.getlist('numeros[]')
    cpf = request.form.get('cpf', '').strip()
    cnpj = request.form.get('cnpj', '').strip()
    apelido = request.form.get('apelido', '').strip()

    cliente_existente = Cliente.query.filter_by(nome=nome).first()
    if cliente_existente:
        flash('Erro: Este cliente já está cadastrado!', 'danger')
        return redirect(url_for('main.client'))

    novo_cliente = Cliente(nome=nome, cpf=cpf, cnpj=cnpj, apelido=apelido)
    db.session.add(novo_cliente)
    db.session.commit()

    for numero in numeros:
        if numero.strip():
            novo_telefone = Telefone(numero=numero, cliente_id=novo_cliente.id)
            db.session.add(novo_telefone)
    db.session.commit()
    flash('Cliente adicionado com sucesso!', 'success')
    return redirect(url_for('main.client'))

# NOVA ROTA: Apagar Cliente
@main.route('/delete_cliente/<int:id>', methods=['POST'])
@login_required # Protege a rota
def delete_cliente(id):
    # Apenas administradores podem apagar clientes
    if not current_user.is_admin():
        flash('Você não tem permissão para apagar clientes.', 'danger')
        return redirect(url_for('main.client'))

    cliente = Cliente.query.get_or_404(id)

    try:
        # Apagar pagamentos associados ao cliente
        Pagamento.query.filter_by(cliente_id=id).delete()
        # Apagar históricos associados ao cliente
        Historico.query.filter_by(cliente_id=id).delete()
        # Apagar carros associados ao cliente
        Carro.query.filter_by(cliente_id=id).delete()
        # Apagar telefones associados ao cliente
        Telefone.query.filter_by(cliente_id=id).delete()
        
        # Finalmente, apagar o cliente
        db.session.delete(cliente)
        db.session.commit()
        flash('Cliente e todos os seus dados foram apagados com sucesso!', 'success')
    except Exception as e:
        db.session.rollback() # Em caso de erro, desfaz as operações no banco de dados
        flash(f'Erro ao apagar cliente: {e}', 'danger')
    
    return redirect(url_for('main.client'))


@main.route('/add_telefone/<int:cliente_id>', methods=['POST'])
@login_required # Protege a rota
def add_telefone(cliente_id):
    numeros = request.form.getlist('numeros[]')

    for numero in numeros:
        if numero.strip():
            novo_telefone = Telefone(numero=numero, cliente_id=cliente_id)
            db.session.add(novo_telefone)

    db.session.commit()
    flash('Telefone(s) adicionado(s) com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=cliente_id))

@main.route('/update_telefone/<int:telefone_id>', methods=['POST'])
@login_required # Protege a rota
def update_telefone(telefone_id):
    novo_numero = request.form.get('numero', '').strip()
    
    telefone = Telefone.query.get_or_404(telefone_id)
    telefone.numero = novo_numero
    db.session.commit()
    flash('Telefone atualizado com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=telefone.cliente_id))

@main.route('/delete_telefone/<int:telefone_id>', methods=['POST'])
@login_required # Protege a rota
def delete_telefone(telefone_id):
    telefone = Telefone.query.get_or_404(telefone_id)
    db.session.delete(telefone)
    db.session.commit()
    flash('Telefone removido com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=telefone.cliente_id))

@main.route('/update_dados_cliente/<int:cliente_id>', methods=['POST'])
@login_required # Protege a rota
def update_dados_cliente(cliente_id):
    # Trata campos que podem vir como lista ou string única
    endereco = request.form.getlist('endereco[]')[0].strip() if request.form.getlist('endereco[]') else request.form.get('endereco', '').strip()
    bairro = request.form.getlist('bairro[]')[0].strip() if request.form.getlist('bairro[]') else request.form.get('bairro', '').strip()
    cidade = request.form.getlist('cidade[]')[0].strip() if request.form.getlist('cidade[]') else request.form.get('cidade', '').strip()
    cep = request.form.getlist('cep[]')[0].strip() if request.form.getlist('cep[]') else request.form.get('cep', '').strip()

    estado = request.form.get('estado', '').strip()
    cpf = request.form.get('cpf', '').strip()
    cnpj = request.form.get('cnpj', '').strip()
    apelido = request.form.get('apelido', '').strip()

    cliente = Cliente.query.get_or_404(cliente_id)
    cliente.cpf = cpf
    cliente.cnpj = cnpj
    cliente.endereco = endereco
    cliente.cidade = cidade
    cliente.estado = estado
    cliente.cep = cep
    cliente.bairro = bairro
    cliente.apelido = apelido 

    db.session.commit()
    flash('Dados do cliente atualizados com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=cliente_id))
    
# ROTAS RELACIONADAS AO HISTÓRICO
@main.route('/add_historico/<int:carro_id>', methods=['POST'])
@login_required # Protege a rota
def add_historico(carro_id):
    descricao = request.form['descricao']
    carro = Carro.query.get_or_404(carro_id)

    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    hora_brasilia = datetime.now(fuso_brasilia) - timedelta(hours=3) # Ajuste para o horário de Brasília

    novo_historico = Historico(cliente_id=carro.cliente_id, carro_id=carro.id, descricao=descricao, data=hora_brasilia)
    db.session.add(novo_historico)
    db.session.commit()
    flash('Histórico adicionado com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=carro.cliente_id))

@main.route('/add_carros_cliente/<int:cliente_id>', methods=['POST'])
@login_required # Protege a rota
def add_carros(cliente_id):
    print(request.form) 
    carros = request.form.to_dict(flat=False)

    for i in range(len(carros['marca'])):
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
    flash('Carro(s) adicionado(s) com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=cliente_id))

@main.route('/update_carros_cliente/<int:cliente_id>', methods=['POST'])
@login_required # Protege a rota
def update_carros(cliente_id):
    carros = Carro.query.filter_by(cliente_id=cliente_id).all()
    
    for carro in carros:
        carro.marca = request.form.get(f'marca_{carro.id}', carro.marca)
        carro.modelo = request.form.get(f'modelo_{carro.id}', carro.modelo)
        carro.motor = request.form.get(f'motor_{carro.id}', carro.motor)
        carro.ano = request.form.get(f'ano_{carro.id}', carro.ano)
        carro.placa = request.form.get(f'placa_{carro.id}', carro.placa)
        carro.quilometro = int(request.form.get(f'quilometro_{carro.id}', carro.quilometro))
        db.session.add(carro)

    db.session.commit()
    flash('Dados do carro atualizados com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=cliente_id))
    
# ROTAS RELACIONADAS AO PAGAMENTO
@main.route('/add_pagamento/<int:carro_id>/<int:historico_id>', methods=['POST'])
@login_required # Protege a rota
def add_pagamento(carro_id, historico_id):
    valor = float(request.form['valor'])  
    metodo = request.form['metodo']
    tipo_pagamento = request.form.get('tipo_cartao')  
    parcelas = request.form.get('parcelas')  

    if parcelas:
        parcelas = int(parcelas)

    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    hora_brasilia = datetime.now(fuso_brasilia) - timedelta(hours=3) # Ajuste para o horário de Brasília

    carro = Carro.query.get_or_404(carro_id)
    historico = Historico.query.get_or_404(historico_id)

    novo_pagamento = Pagamento(
        cliente_id=carro.cliente_id,
        carro_id=carro.id,
        historico_id=historico.id,
        valor=valor,
        metodo=metodo,
        tipo_pagamento=tipo_pagamento,
        parcelas=parcelas,
        data=hora_brasilia
    )
    
    db.session.add(novo_pagamento)
    db.session.commit()
    flash('Pagamento registrado com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=carro.cliente_id))

# ROTAS RELACIONADAS AO INVENTÁRIO E PEÇAS
@main.route('/add_peca', methods=['POST'])
@login_required # Protege a rota
def add_peca():
    nome = request.form['nome'].strip()
    descricao = request.form.get('descricao')
    quantidade = int(request.form['quantidade'])
    preco = float(request.form['preco'])

    peca_existente = Peca.query.filter_by(nome=nome).first()
    if peca_existente:
        pecas = Peca.query.all()
        flash('Erro: Esta peça já está cadastrada!', 'danger')
        return render_template('inventario.html', pecas=pecas, error="Erro: Esta peça já está cadastrada!")

    nova_peca = Peca(nome=nome, descricao=descricao, quantidade=quantidade, preco=preco)
    db.session.add(nova_peca)
    db.session.commit()
    flash('Peça adicionada com sucesso!', 'success')
    return redirect(url_for('main.inventario'))
   
@main.route('/update_peca/<int:id>', methods=['POST'])
@login_required # Protege a rota
def update_peca(id):
    peca = Peca.query.get_or_404(id)
    peca.nome = request.form['nome']
    peca.descricao = request.form.get('descricao')
    peca.quantidade = int(request.form['quantidade'])
    peca.preco = float(request.form['preco'])

    db.session.commit()
    flash('Peça atualizada com sucesso!', 'success')
    return redirect(url_for('main.inventario'))
    
@main.route('/delete_peca/<int:id>', methods=['POST'])
@login_required # Protege a rota
def delete_peca(id):
    try:
        peca = Peca.query.get_or_404(id)
        db.session.delete(peca)
        db.session.commit()
        flash('Peça removida com sucesso!', 'danger')
        return redirect(url_for('main.inventario'))
    except Exception as e:
        print(f"Erro ao remover peça: {e}")
        flash(f"Erro ao remover peça: {e}", 'danger')
        return "Erro interno ao remover a peça", 500

# Rotas para gestão de utilizadores
@main.route('/utilizadores')
@login_required # Protege a rota
def lista_utilizadores():
    utilizadores = Utilizador.query.all()
    # Renderiza o template de lista de utilizadores, que agora é autocontido
    return render_template('utilizadores/lista_utilizadores.html', utilizadores=utilizadores)

@main.route('/utilizadores/add', methods=['GET', 'POST'])
def add_utilizador():
    # A rota de adição de utilizador não é protegida por login_required
    # para permitir que novos utilizadores se registem.
    papeis = Papel.query.all()
    if request.method == 'POST':
        nome = request.form['nome'].strip()
        email = request.form['email'].strip()
        senha = request.form['senha']
        confirmar_senha = request.form['confirmar_senha']
        # ALTERAÇÃO AQUI: Agora obtemos um único papel_id, não uma lista
        papel_id = request.form.get('papel_id') 
        telefone = request.form.get('telefone', '').strip()
        observacoes = request.form.get('observacoes', '').strip()
        palavras_chave = request.form.get('palavras_chave', '').strip()

        if not nome or not email or not senha or not confirmar_senha or not papel_id: # Adicionado papel_id à validação
            flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
            return render_template('utilizadores/add_utilizador.html', papeis=papeis)

        if senha != confirmar_senha:
             flash('As senhas não coincidem.', 'danger')
             return render_template('utilizadores/add_utilizador.html', papeis=papeis)

        email_existente = Utilizador.query.filter_by(email=email).first()
        if email_existente:
            flash('Este email já está registado.', 'danger')
            return render_template('utilizadores/add_utilizador.html', papeis=papeis)

        novo_utilizador = Utilizador(nome=nome, email=email, telefone=telefone, palavras_chave=palavras_chave)
        novo_utilizador.set_senha(senha)

        # ALTERAÇÃO AQUI: Adiciona apenas o papel selecionado
        papel = Papel.query.get(int(papel_id))
        if papel:
            novo_utilizador.papeis.append(papel)

        db.session.add(novo_utilizador)
        db.session.commit()
        flash('Utilizador criado com sucesso! Faça login para aceder ao sistema.', 'success')
        return redirect(url_for('main.login')) # Redireciona para a página de login após o cadastro

    # Renderiza o template de adicionar utilizador
    return render_template('utilizadores/add_utilizadores.html', papeis=papeis)

# Rota de Login
@main.route('/login', methods=['GET', 'POST'])
def login():
    # Se o utilizador já estiver autenticado, redireciona para a página inicial.
    # Isso evita que um utilizador logado aceda novamente à página de login.
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form['email'].strip()
        senha = request.form['senha']
        
        utilizador = Utilizador.query.filter_by(email=email).first()

        # Verifica as credenciais: se o utilizador existe E a senha está correta.
        if utilizador and utilizador.check_senha(senha):
            login_user(utilizador) # Faz o login do utilizador usando Flask-Login.
            flash('Login bem-sucedido!', 'success')
            return redirect(url_for('main.index')) # Redireciona para a página inicial após login.
        else:
            flash('Email ou senha inválidos.', 'danger') # Mensagem de erro para credenciais inválidas.
    
    # Renderiza o template de login para requisições GET ou falha de POST.
    return render_template('login.html')

# Rota de Logout
@main.route('/logout')
@login_required # Garante que só utilizadores logados podem fazer logout.
def logout():
    logout_user() # Faz o logout do utilizador usando Flask-Login.
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('main.login')) # Redireciona para a página de login após logout.