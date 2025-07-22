from flask import Blueprint, render_template, request, redirect, url_for, flash, session # 🔹 Adicionado 'session'
# Importa os modelos do esquema antigo, e os novos modelos Utilizador e Papel
# 🔹 Importa Historico (não HistoricoServico)
from .models import db, Cliente, Telefone, Carro, Peca, Historico, Pagamento, Utilizador, Papel, utilizador_papeis 
from datetime import datetime, timedelta
import pytz
from werkzeug.security import generate_password_hash # Importa para hash de senha
from flask_login import login_user, logout_user, current_user, login_required # Importações do Flask-Login
from sqlalchemy import delete # Importa a função delete do SQLAlchemy
import uuid # 🔹 NOVO: Importar uuid para gerar tokens únicos

# Cria um Blueprint para organizar as rotas.
# O nome 'main' é usado para referenciar as rotas (ex: url_for('main.login')).
main = Blueprint('main', __name__)

# Função auxiliar para ajustar o horário para Brasília
def ajustar_para_brasilia(data_utc):
    """
    Ajusta um objeto datetime para o fuso horário de Brasília.
    """
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    if data_utc.tzinfo is None:  # Verifica se o objeto é "naive" (sem fuso horário)
        # Assume que o objeto sem fuso horário está em UTC, pois foi salvo assim
        data_utc = pytz.utc.localize(data_utc)
    # Se já tiver fuso horário (agora garantido como UTC), ajusta para o horário de Brasília
    return data_utc.astimezone(fuso_brasilia)

# 🔹 NOVO: Hook para verificar o token de sessão em cada requisição
@main.before_request
def check_single_session():
    # Aplica a verificação apenas para usuários autenticados e se não for a página de login/logout
    if current_user.is_authenticated and request.endpoint and \
       not request.endpoint.startswith('main.static') and \
       request.endpoint != 'main.login' and request.endpoint != 'main.logout':
        
        # Se o token da sessão do navegador não existir ou não corresponder ao do banco de dados
        if 'session_token' not in session or current_user.session_token != session['session_token']:
            flash('Você foi desconectado porque sua conta foi acessada em outro local.', 'warning')
            logout_user() # Desconecta o usuário atual
            return redirect(url_for('main.login'))
        
        # Se o token no banco de dados for None (por exemplo, primeiro login após a atualização do DB)
        # ou se o token da sessão não estiver definido, geramos um novo e o armazenamos.
        elif current_user.session_token is None:
            new_session_token = str(uuid.uuid4())
            current_user.session_token = new_session_token
            db.session.commit()
            session['session_token'] = new_session_token

# Rota para a página inicial
@main.route('/')
@login_required # Esta rota requer que o utilizador esteja logado para ser acedida.
def index():
    # Renderiza o template 'index.html'.
    return render_template('index.html')

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
    
    # Ajustar os horários dos históricos e pagamentos para o fuso de Brasília para exibição
    # Criar um novo atributo data_local para não sobrescrever o original (UTC)
    for historico in historicos:
        # ATENÇÃO AQUI: Garante que historico.data não é None antes de chamar ajustar_para_brasilia
        if historico.data: 
            historico.data_local = ajustar_para_brasilia(historico.data)
        else:
            historico.data_local = None # Define como None se a data original for None
        # Verifica se o histórico tem pagamento associado (lógica original)
        historico.tem_pagamento = any(pagamento.historico_id == historico.id for pagamento in pagamentos)
        
    for pagamento in pagamentos:
        if pagamento.data: # Verifica também para pagamentos, por consistência
            pagamento.data_local = ajustar_para_brasilia(pagamento.data)
        else:
            pagamento.data_local = None

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

# Rota: Apagar Cliente
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
    flash('Telefone removido com sucesso!', 'danger')
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
    data_str = request.form['data'] # A data vem como string 'YYYY-MM-DD'
    
    # Combina a data do formulário com a hora atual
    data_do_form = datetime.strptime(data_str, '%Y-%m-%d')
    hora_atual = datetime.now().time()
    data_historico_local = data_do_form.replace(
        hour=hora_atual.hour,
        minute=hora_atual.minute,
        second=hora_atual.second,
        microsecond=hora_atual.microsecond
    )
    
    carro = Carro.query.get_or_404(carro_id)

    # A função ajustar_data_para_utc será chamada no listener before_insert do modelo Historico.
    # Portanto, estamos a passar a data local (naive) para o construtor do Historico.
    novo_historico = Historico(cliente_id=carro.cliente_id, carro_id=carro.id, descricao=descricao, data=data_historico_local)
    
    db.session.add(novo_historico)
    db.session.commit()
    flash('Histórico adicionado com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=carro.cliente_id))

@main.route('/edit_historico/<int:id>', methods=['POST'])
@login_required # Protege a rota
def edit_historico(id):
    historico = Historico.query.get_or_404(id)
    descricao = request.form['descricao']
    data_str = request.form['data'] # A data vem como string 'YYYY-MM-DD'

    # Converte a string da data para objeto datetime e combina com a hora atual
    data_do_form = datetime.strptime(data_str, '%Y-%m-%d')
    hora_atual = datetime.now().time()
    data_atualizada_local = data_do_form.replace(
        hour=hora_atual.hour,
        minute=hora_atual.minute,
        second=hora_atual.second,
        microsecond=hora_atual.microsecond
    )

    historico.descricao = descricao
    historico.data = data_atualizada_local # Atribui a data local, o listener vai converter para UTC
    
    db.session.commit()
    flash('Histórico atualizado com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=historico.cliente_id))

@main.route('/delete_historico/<int:id>', methods=['POST']) # Nova rota para apagar histórico
@login_required # Protege a rota
def delete_historico(id):
    historico = Historico.query.get_or_404(id)
    cliente_id = historico.cliente_id # Guarda o ID do cliente para redirecionar
    db.session.delete(historico)
    db.session.commit()
    flash('Histórico removido com sucesso!', 'danger')
    return redirect(url_for('main.cliente', id=cliente_id))


@main.route('/add_carros_cliente/<int:cliente_id>', methods=['POST'])
@login_required # Protege a rota
def add_carros(cliente_id):
    print(request.form) 
    carros_data = request.form.to_dict(flat=False)

    # CORREÇÃO AQUI: Acessar as chaves com '[]'
    if 'marca[]' not in carros_data or not carros_data['marca[]']:
        flash('Erro: Nenhuma marca de carro fornecida. Por favor, adicione pelo menos um carro.', 'danger')
        return redirect(url_for('main.cliente', id=cliente_id))

    for i in range(len(carros_data['marca[]'])):
        try:
            # Garante que os campos numéricos são convertidos para int
            # CORREÇÃO AQUI: Acessar as chaves com '[]'
            ano_val = int(carros_data['ano[]'][i]) if carros_data['ano[]'][i] else None
            quilometragem_val = int(carros_data['quilometragem[]'][i]) if carros_data['quilometragem[]'][i] else None

            novo_carro = Carro(
                cliente_id=cliente_id,
                marca=carros_data['marca[]'][i],
                modelo=carros_data['modelo[]'][i],
                motor=carros_data['motor[]'][i],
                ano=ano_val,
                placa=carros_data['placa[]'][i],
                quilometragem=quilometragem_val
            )
            db.session.add(novo_carro)
        except (ValueError, KeyError) as e:
            flash(f'Erro ao adicionar carro: Verifique os dados inseridos. Erro: {e}', 'danger')
            db.session.rollback() # Desfaz quaisquer adições parciais
            return redirect(url_for('main.cliente', id=cliente_id))

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
        
        # Converter ano e quilometragem para int, com tratamento para valores vazios
        ano_str = request.form.get(f'ano_{carro.id}')
        if ano_str:
            carro.ano = int(ano_str)
        
        carro.placa = request.form.get(f'placa_{carro.id}', carro.placa)
        
        quilometragem_str = request.form.get(f'quilometragem_{carro.id}') # Corrigido de 'quilometro'
        if quilometragem_str:
            carro.quilometragem = int(quilometragem_str) # Corrigido de 'quilometro' para 'quilometragem'
        
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
    parcelas_str = request.form.get('parcelas') # Pega como string

    # Se a string estiver vazia, define parcelas como None; caso contrário, converte para int
    parcelas = int(parcelas_str) if parcelas_str and parcelas_str.strip() else None

    carro = Carro.query.get_or_404(carro_id)
    historico = Historico.query.get_or_404(historico_id)

    novo_pagamento = Pagamento(
        cliente_id=carro.cliente_id,
        carro_id=carro.id,
        historico_id=historico.id,
        valor=valor,
        metodo=metodo,
        tipo_pagamento=tipo_pagamento,
        parcelas=parcelas, # Passa None se a string for vazia
        data=datetime.now(pytz.utc) 
    )

    db.session.add(novo_pagamento)
    db.session.commit()
    flash('Pagamento registrado com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=carro.cliente_id))

@main.route('/edit_pagamento/<int:id>', methods=['POST']) # Adicionada a nova rota de edição de pagamento
@login_required # Protege a rota
def edit_pagamento(id):
    pagamento = Pagamento.query.get_or_404(id)
    
    # Atualiza os campos do pagamento com base nos dados do formulário
    pagamento.valor = float(request.form['valor'])
    pagamento.metodo = request.form['metodo']
    pagamento.tipo_pagamento = request.form.get('tipo_cartao')
    
    parcelas_str = request.form.get('parcelas')
    pagamento.parcelas = int(parcelas_str) if parcelas_str and parcelas_str.strip() else None # Lida com parcelas vazias

    db.session.commit()
    flash('Pagamento atualizado com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=pagamento.cliente_id))


@main.route('/delete_pagamento/<int:id>', methods=['POST']) # Adicionada a nova rota de delete
@login_required # Protege a rota
def delete_pagamento(id):
    pagamento = Pagamento.query.get_or_404(id)
    cliente_id = pagamento.cliente_id # Guarda o ID do cliente para redirecionar
    db.session.delete(pagamento)
    db.session.commit()
    flash('Pagamento removido com sucesso!', 'danger')
    return redirect(url_for('main.cliente', id=cliente_id))

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
#@login_required # 🔹 Mantido @login_required para consistência
def add_utilizador():

    papeis = Papel.query.all()
    if request.method == 'POST':
        nome = request.form['nome'].strip()
        email = request.form['email'].strip()
        senha = request.form['senha']
        confirmar_senha = request.form['confirmar_senha']
        papel_id = request.form.get('papel_id') 
        telefone = request.form.get('telefone', '').strip()
        palavras_chave = request.form.get('palavras_chave', '').strip()
        observacoes = request.form.get('observacoes', '').strip() # 🔹 NOVO: Pega observacoes

        if not nome or not email or not senha or not confirmar_senha or not papel_id:
            flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
            return render_template('utilizadores/add_utilizadores.html', papeis=papeis)

        if senha != confirmar_senha:
             flash('As senhas não coincidem.', 'danger')
             return render_template('utilizadores/add_utilizadores.html', papeis=papeis)

        email_existente = Utilizador.query.filter_by(email=email).first()
        if email_existente:
            flash('Este email já está registado.', 'danger')
            return render_template('utilizadores/add_utilizadores.html', papeis=papeis)

        # 🔹 Passa 'observacoes' para o construtor do Utilizador
        novo_utilizador = Utilizador(nome=nome, email=email, telefone=telefone, palavras_chave=palavras_chave, observacoes=observacoes)
        novo_utilizador.set_senha(senha)

        papel = Papel.query.get(int(papel_id))
        if papel:
            novo_utilizador.papeis.append(papel)

        db.session.add(novo_utilizador)
        db.session.commit()
        flash('Utilizador criado com sucesso!', 'success')
        return redirect(url_for('main.lista_utilizadores')) # Redireciona para a lista de utilizadores

    return render_template('utilizadores/add_utilizadores.html', papeis=papeis)

@main.route('/utilizadores/edit/<int:id>', methods=['GET', 'POST'])
@login_required # Protege a rota
def edit_utilizador(id):
    # Verifica se o utilizador atual é um administrador OU se está a editar a própria conta
    if not current_user.is_admin() and current_user.id != id: # 🔹 Adicionada verificação de admin
        flash('Você não tem permissão para editar utilizadores.', 'danger')
        return redirect(url_for('main.lista_utilizadores'))

    utilizador = Utilizador.query.get_or_404(id)
    papeis = Papel.query.all()

    if request.method == 'POST':
        nome = request.form['nome'].strip()
        email = request.form['email'].strip()
        senha = request.form['senha'].strip()
        confirmar_senha = request.form['confirmar_senha'].strip()
        papel_id = request.form.get('papel_id')
        telefone = request.form.get('telefone', '').strip()
        palavras_chave = request.form.get('palavras_chave', '').strip()
        observacoes = request.form.get('observacoes', '').strip() # 🔹 NOVO: Pega observacoes

        # Validação de campos obrigatórios
        if not nome or not email or not papel_id:
            flash('Por favor, preencha todos os campos obrigatórios (Nome, Email, Papel).', 'danger')
            return render_template('utilizadores/edit_utilizadores.html', utilizador=utilizador, papeis=papeis)

        # Validação de email duplicado (apenas se o email for alterado)
        if email != utilizador.email:
            email_existente = Utilizador.query.filter_by(email=email).first()
            if email_existente and email_existente.id != utilizador.id:
                flash('Este email já está registado por outro utilizador.', 'danger')
                return render_template('utilizadores/edit_utilizadores.html', utilizador=utilizador, papeis=papeis)

        # Validação e atualização de senha (se fornecida)
        if senha:
            if senha != confirmar_senha:
                flash('As senhas não coincidem.', 'danger')
                return render_template('utilizadores/edit_utilizadores.html', utilizador=utilizador, papeis=papeis)
            utilizador.set_senha(senha)

        # Atualiza os dados do utilizador
        utilizador.nome = nome
        utilizador.email = email
        utilizador.telefone = telefone
        utilizador.palavras_chave = palavras_chave
        utilizador.observacoes = observacoes # 🔹 NOVO: Atualiza observacoes

        # Atualiza o papel do utilizador
        papel_selecionado = Papel.query.get(int(papel_id))
        if papel_selecionado:
            # Remove todos os papéis existentes e adiciona o novo
            utilizador.papeis.clear()
            utilizador.papeis.append(papel_selecionado)

        db.session.commit()
        flash('Utilizador atualizado com sucesso!', 'success')
        return redirect(url_for('main.lista_utilizadores'))

    return render_template('utilizadores/edit_utilizadores.html', utilizador=utilizador, papeis=papeis)

@main.route('/utilizadores/delete/<int:id>', methods=['POST'])
@login_required # Protege a rota
def delete_utilizador(id):
    # Verifica se o utilizador atual é um administrador
    if not current_user.is_admin():
        flash('Você não tem permissão para apagar utilizadores.', 'danger')
        return redirect(url_for('main.lista_utilizadores'))

    utilizador = Utilizador.query.get_or_404(id)

    try:
        # Se o utilizador que está a ser apagado for o utilizador atualmente logado
        if utilizador.id == current_user.id:
            flash('Você não pode apagar a sua própria conta enquanto estiver logado.', 'danger')
            return redirect(url_for('main.lista_utilizadores'))

        # Remove as associações do utilizador com os papéis na tabela de associação
        # Isso é necessário porque o SQLAlchemy não faz "cascade delete" para relações many-to-many por padrão
        db.session.execute(delete(utilizador_papeis).where(utilizador_papeis.c.id_utilizador == utilizador.id))
        
        db.session.delete(utilizador)
        db.session.commit()
        flash('Utilizador apagado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback() # Em caso de erro, desfaz as operações no banco de dados
        flash(f'Erro ao apagar utilizador: {e}', 'danger')
    
    return redirect(url_for('main.lista_utilizadores'))


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
        remember = True if request.form.get('remember') else False # 🔹 NOVO: Adicionado 'remember'

        utilizador = Utilizador.query.filter_by(email=email).first()

        # Verifica as credenciais: se o utilizador existe E a senha está correta.
        if utilizador and utilizador.check_senha(senha):
            # 🔹 NOVO: Gerar e armazenar o token de sessão após um login bem-sucedido
            new_session_token = str(uuid.uuid4()) # Gera um UUID único
            utilizador.session_token = new_session_token
            db.session.commit()
            session['session_token'] = new_session_token # Armazena na sessão do Flask

            login_user(utilizador, remember=remember) # 🔹 Passa 'remember'
            #flash('Login bem-sucedido!', 'success')
            return redirect(url_for('main.index')) # Redireciona para a página inicial após login.
        else:
            flash('Email ou senha inválidos.', 'danger') # Mensagem de erro para credenciais inválidas.
    
    # Renderiza o template de login para requisições GET ou falha de POST.
    return render_template('login.html')

# Rota de Logout
@main.route('/logout')
@login_required # Garante que só utilizadores logados podem fazer logout.
def logout():
    # 🔹 NOVO: Limpar o token de sessão do navegador ao fazer logout
    if 'session_token' in session:
        session.pop('session_token', None)
    
    # Opcional: Limpar o token do banco de dados para indicar que o usuário não tem sessão ativa
    # if current_user.is_authenticated:
    #     current_user.session_token = None
    #     db.session.commit()

    logout_user() # Faz o logout do utilizador usando Flask-Login.
    #flash('Você foi desconectado.', 'info')
    return redirect(url_for('main.login')) # Redireciona para a página de login após logout.