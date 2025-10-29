from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from .models import db, Cliente, Telefone, Carro, Peca, Historico, Pagamento, Utilizador, Papel, utilizador_papeis, OrdemServico
from datetime import datetime, timedelta
import pytz
from werkzeug.security import generate_password_hash
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy import delete
import uuid
import json
from werkzeug.utils import secure_filename
import os

main = Blueprint('main', __name__)

UPLOAD_FOLDER = 'uploads' 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}

def ajustar_para_brasilia(data_utc):
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    if data_utc.tzinfo is None:
        data_utc = pytz.utc.localize(data_utc)
    return data_utc.astimezone(fuso_brasilia)

@main.before_request
def check_single_session():
    if current_user.is_authenticated and request.endpoint and \
       not request.endpoint.startswith('static') and \
       request.endpoint != 'main.login' and request.endpoint != 'main.logout':
        
        if 'session_token' not in session or current_user.session_token != session['session_token']:
            flash('Você foi desconectado porque sua conta foi acessada em outro local.', 'warning')
            logout_user()
            return redirect(url_for('main.login'))
        
        elif current_user.session_token is None:
            new_session_token = str(uuid.uuid4())
            current_user.session_token = new_session_token
            db.session.commit()
            session['session_token'] = new_session_token

@main.route('/')
@login_required
def index():
    return render_template('index.html', active_page='index')

@main.route('/inventario', methods=['GET'])
@login_required
def inventario():
    query = request.args.get('query', '').lower()
    pecas = db.session.query(Peca).all()

    if query:
        pecas = [peca for peca in pecas if query in peca.nome.lower() or (peca.descricao and query in peca.descricao.lower())]

    return render_template('inventario.html', pecas=pecas, search_query=query, active_page='inventario')

@main.route('/listaclientes')
@login_required
def client():
    query = request.args.get('query', '')
    if query:
        clientes = Cliente.query.filter(Cliente.nome.ilike(f'%{query}%')).all()
    else:
        clientes = Cliente.query.all()
    return render_template('listacliente.html', clientes=clientes, search_query=query, active_page='clientes')

@main.route('/cliente/<int:id>')
@login_required
def cliente(id):
    cliente = Cliente.query.get_or_404(id)
    telefones = Telefone.query.filter_by(cliente_id=id).all()
    carros = Carro.query.filter_by(cliente_id=id).all()
    # Eager load related data to avoid N+1 problem
    #historicos = Historico.query.filter_by(cliente_id=id).order_by(Historico.data.desc()).all()
    # Buscamos os pagamentos para passar para o template (útil para a aba de pagamentos)
    pagamentos = Pagamento.query.filter_by(cliente_id=id).order_by(Pagamento.data.desc()).all()
    
    # Create a set of historico_ids that have payments for faster lookup
    #historicos_com_pagamento_ids = {p.historico_id for p in pagamentos}

    ordens_servico = OrdemServico.query.filter_by(cliente_nome=cliente.nome).order_by(OrdemServico.data_criacao.desc()).all()

    #for historico in historicos:
    #    if historico.data: 
    #        historico.data_local = ajustar_para_brasilia(historico.data)
    #    else:
    #        historico.data_local = None
    #    historico.tem_pagamento = historico.id in historicos_com_pagamento_ids

    for p in pagamentos:
        p.data_local = ajustar_para_brasilia(p.data)

    #for pagamento in pagamentos:
    #    if pagamento.data:
    #        pagamento.data_local = ajustar_para_brasilia(pagamento.data)
    #    else:
    #        pagamento.data_local = None

    #return render_template('cliente.html', cliente=cliente, telefones=telefones, historicos=historicos, pagamentos=pagamentos, carros=carros, active_page='clientes')
    return render_template('cliente.html', 
        cliente=cliente, 
        carros=carros,
        ordens_servico=ordens_servico,
        pagamentos=pagamentos,
        telefones=telefones,
        active_page='clientes')

#@main.route('/add', methods=['POST'])
#@login_required
#def add_cliente():
#    nome = request.form['nome'].strip()
#    numeros = request.form.getlist('numeros[]')
#    cpf = request.form.get('cpf', '').strip()
#    cnpj = request.form.get('cnpj', '').strip()
#    apelido = request.form.get('apelido', '').strip()

#    cliente_existente = Cliente.query.filter_by(nome=nome).first()
#    if cliente_existente:
#        flash('Erro: Este cliente já está cadastrado!', 'danger')
#        return redirect(url_for('main.client'))

#    novo_cliente = Cliente(nome=nome, cpf=cpf or None, cnpj=cnpj or None, apelido=apelido or None)
#    db.session.add(novo_cliente)
#    db.session.commit()
#
#    for numero in numeros:
#        if numero.strip():
#            novo_telefone = Telefone(numero=numero.strip(), cliente_id=novo_cliente.id)
#            db.session.add(novo_telefone)
#    db.session.commit()
#    flash('Cliente adicionado com sucesso!', 'success')
#    return redirect(url_for('main.client'))

@main.route('/delete_cliente/<int:id>', methods=['POST'])
@login_required
def delete_cliente(id):
    if not current_user.is_admin():
        flash('Você não tem permissão para apagar clientes.', 'danger')
        return redirect(url_for('main.client'))

    cliente = Cliente.query.get_or_404(id)

    try:
        # Cascade delete should handle this, but explicit delete is safer
        Pagamento.query.filter_by(cliente_id=id).delete()
        Historico.query.filter_by(cliente_id=id).delete()
        Carro.query.filter_by(cliente_id=id).delete()
        Telefone.query.filter_by(cliente_id=id).delete()
        
        db.session.delete(cliente)
        db.session.commit()
        flash('Cliente e todos os seus dados foram apagados com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao apagar cliente: {e}', 'danger')
    
    return redirect(url_for('main.client'))

@main.route('/add_telefone/<int:cliente_id>', methods=['POST'])
@login_required
def add_telefone(cliente_id):
    numeros = request.form.getlist('numeros[]')
    active_tab = request.form.get('active_tab', 'telefones-pane')

    for numero in numeros:
        if numero.strip():
            novo_telefone = Telefone(numero=numero.strip(), cliente_id=cliente_id)
            db.session.add(novo_telefone)

    db.session.commit()
    flash('Telefone(s) adicionado(s) com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab))

@main.route('/delete_telefone/<int:telefone_id>', methods=['POST'])
@login_required
def delete_telefone(telefone_id):
    telefone = Telefone.query.get_or_404(telefone_id)
    cliente_id = telefone.cliente_id
    active_tab = request.form.get('active_tab', 'telefones-pane')
    db.session.delete(telefone)
    db.session.commit()
    flash('Telefone removido com sucesso!', 'danger')
    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab))

@main.route('/update_dados_cliente/<int:cliente_id>', methods=['POST'])
@login_required
def update_dados_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    active_tab = request.form.get('active_tab', 'dados-pessoais-pane')

    # Endereços
    enderecos = request.form.getlist('endereco[]')
    numeros = request.form.getlist('numero[]')
    complementos = request.form.getlist('complemento[]')
    bairros = request.form.getlist('bairro[]')
    cidades = request.form.getlist('cidade[]')
    ceps = request.form.getlist('cep[]')
    estados = request.form.getlist('estado[]')

    cliente.endereco = ";".join(filter(None, enderecos)) or None
    cliente.numero = ";".join(filter(None, numeros)) or None
    cliente.complemento = ";".join(filter(None, complementos)) or None
    cliente.bairro = ";".join(filter(None, bairros)) or None
    cliente.cidade = ";".join(filter(None, cidades)) or None
    cliente.cep = ";".join(filter(None, ceps)) or None
    cliente.estado = ";".join(filter(None, estados)) or None

    # Dados Gerais
    cliente.apelido = request.form.get('apelido', '').strip() or None
    cliente.cpf = request.form.get('cpf', '').strip() or None
    cliente.cnpj = request.form.get('cnpj', '').strip() or None

    db.session.commit()
    flash('Dados do cliente atualizados com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab))

@main.route('/add_historico/<int:carro_id>', methods=['POST'])
@login_required
def add_historico(carro_id):
    descricao = request.form['descricao']
    data_str = request.form['data']
    active_tab = request.form.get('active_tab', 'veiculos-pane')
    
    try:
        data_do_form = datetime.strptime(data_str, '%Y-%m-%d')
        data_historico_local = datetime.combine(data_do_form.date(), datetime.now().time())
        
        carro = Carro.query.get_or_404(carro_id)

        novo_historico = Historico(cliente_id=carro.cliente_id, carro_id=carro.id, descricao=descricao, data=data_historico_local)
        
        db.session.add(novo_historico)
        db.session.commit()
        flash('Histórico adicionado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar histórico: {e}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('main.cliente', id=Carro.query.get(carro_id).cliente_id, tab=active_tab))

@main.route('/edit_historico/<int:id>', methods=['POST'])
@login_required
def edit_historico(id):
    historico = Historico.query.get_or_404(id)
    active_tab = request.form.get('active_tab', 'veiculos-pane')
    
    try:
        historico.descricao = request.form['descricao']
        data_str = request.form['data']
        data_do_form = datetime.strptime(data_str, '%Y-%m-%d')
        # Mantém a hora original se existir, senão usa a hora atual
        hora_existente = historico.data.time() if historico.data else datetime.now().time()
        historico.data = datetime.combine(data_do_form.date(), hora_existente)
        
        db.session.commit()
        flash('Histórico atualizado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao editar histórico: {e}', 'danger')
        db.session.rollback()
        
    return redirect(url_for('main.cliente', id=historico.cliente_id, tab=active_tab))

@main.route('/delete_historico/<int:id>', methods=['POST'])
@login_required
def delete_historico(id):
    historico = Historico.query.get_or_404(id)
    cliente_id = historico.cliente_id
    active_tab = request.form.get('active_tab', 'veiculos-pane')
    db.session.delete(historico)
    db.session.commit()
    flash('Histórico removido com sucesso!', 'danger')
    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab))

@main.route('/add_carros_cliente/<int:cliente_id>', methods=['POST'])
@login_required
def add_carros(cliente_id):
    active_tab = request.form.get('active_tab', 'veiculos-pane')
    
    try:
        novo_carro = Carro(
            cliente_id=cliente_id,
            marca=request.form.get('marca[]'),
            modelo=request.form.get('modelo[]'),
            motor=request.form.get('motor[]') or None,
            ano=int(request.form['ano[]']) if request.form.get('ano[]') else None,
            placa=request.form.get('placa[]'),
            quilometragem=int(request.form['quilometragem[]']) if request.form.get('quilometragem[]') else None
        )
        db.session.add(novo_carro)
        db.session.commit()
        flash('Carro adicionado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar carro: {e}', 'danger')
        db.session.rollback()

    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab))

@main.route('/update_carros_cliente/<int:cliente_id>', methods=['POST'])
@login_required
def update_carros(cliente_id):
    active_tab = request.form.get('active_tab', 'veiculos-pane')
    carro_id = request.form.get('carro_id')
    
    try:
        carro = Carro.query.get_or_404(carro_id)
        if carro.cliente_id != cliente_id:
            flash('Operação não permitida.', 'danger')
            return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab))

        carro.marca = request.form.get(f'marca_{carro_id}')
        carro.modelo = request.form.get(f'modelo_{carro_id}')
        carro.motor = request.form.get(f'motor_{carro_id}') or None
        carro.ano = int(request.form[f'ano_{carro_id}']) if request.form.get(f'ano_{carro_id}') else None
        carro.placa = request.form.get(f'placa_{carro_id}')
        carro.quilometragem = int(request.form[f'quilometragem_{carro_id}']) if request.form.get(f'quilometragem_{carro_id}') else None
        
        db.session.commit()
        flash('Dados do carro atualizados com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar carro: {e}', 'danger')
        db.session.rollback()

    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab))
    
#@main.route('/add_pagamento/<int:cliente_id>/<int:carro_id>/<int:historico_id>', methods=['POST'])
#@login_required
#def add_pagamento(cliente_id, carro_id, historico_id):
#    active_tab = request.form.get('active_tab', 'pagamentos-pane')
#    try:
#        valor_str = request.form['valor'].replace('.', '').replace(',', '.')
#        valor = float(valor_str)
#        
#        metodo = request.form['metodo']
#        tipo_pagamento = request.form.get('tipo_pagamento')
#        parcelas_str = request.form.get('parcelas')
#        data_pagamento_str = request.form.get('data_pagamento')
#
#        data_pagamento = datetime.combine(
#            datetime.strptime(data_pagamento_str, '%Y-%m-%d').date(),
#            datetime.now().time()
#        )
#
#        parcelas = int(parcelas_str) if tipo_pagamento == 'Parcelado' and parcelas_str and parcelas_str.strip() else None
#
#        novo_pagamento = Pagamento(
#            cliente_id=cliente_id, carro_id=carro_id, historico_id=historico_id,
#            valor=valor, metodo=metodo, tipo_pagamento=tipo_pagamento,
#            parcelas=parcelas, data=data_pagamento
#        )
#        db.session.add(novo_pagamento)
#        db.session.commit()
#        flash('Pagamento registrado com sucesso!', 'success')
#    except Exception as e:
#        flash(f'Erro ao registrar pagamento: {e}', 'danger')
#        db.session.rollback()
#
#    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab))

#@main.route('/edit_pagamento/<int:id>', methods=['POST'])
#@login_required
#def edit_pagamento(id):
#    pagamento = Pagamento.query.get_or_404(id)
#    active_tab = request.form.get('active_tab', 'pagamentos-pane')
#    
#    try:
#        valor_str = request.form['valor'].replace('.', '').replace(',', '.')
#        pagamento.valor = float(valor_str)
#        pagamento.metodo = request.form['metodo']
#        pagamento.tipo_pagamento = request.form.get('tipo_pagamento')
#        parcelas_str = request.form.get('parcelas')
#        pagamento.parcelas = int(parcelas_str) if pagamento.tipo_pagamento == 'Parcelado' and parcelas_str and parcelas_str.strip() else None
#
#        db.session.commit()
#        flash('Pagamento atualizado com sucesso!', 'success')
#    except Exception as e:
#        flash(f'Erro ao atualizar pagamento: {e}', 'danger')
#        db.session.rollback()
#
#    return redirect(url_for('main.cliente', id=pagamento.cliente_id, tab=active_tab))

#@main.route('/delete_pagamento/<int:id>', methods=['POST'])
#@login_required
#def delete_pagamento(id):
#    pagamento = Pagamento.query.get_or_404(id)
#    cliente_id = pagamento.cliente_id
#    active_tab = request.form.get('active_tab', 'pagamentos-pane')
#    db.session.delete(pagamento)
#    db.session.commit()
#    flash('Pagamento removido com sucesso!', 'danger')
#    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab))

@main.route('/add_peca', methods=['POST'])
@login_required
def add_peca():
    nome = request.form['nome'].strip()
    descricao = request.form.get('descricao')
    quantidade = int(request.form['quantidade'])
    preco = float(request.form['preco'].replace(',', '.'))

    if Peca.query.filter_by(nome=nome).first():
        flash('Erro: Esta peça já está cadastrada!', 'danger')
        return redirect(url_for('main.inventario'))

    nova_peca = Peca(nome=nome, descricao=descricao, quantidade=quantidade, preco=preco)
    db.session.add(nova_peca)
    db.session.commit()
    flash('Peça adicionada com sucesso!', 'success')
    return redirect(url_for('main.inventario'))
   
@main.route('/update_peca/<int:id>', methods=['POST'])
@login_required
def update_peca(id):
    peca = Peca.query.get_or_404(id)
    peca.nome = request.form['nome']
    peca.descricao = request.form.get('descricao')
    peca.quantidade = int(request.form['quantidade'])
    peca.preco = float(request.form['preco'].replace(',', '.'))

    db.session.commit()
    flash('Peça atualizada com sucesso!', 'success')
    return redirect(url_for('main.inventario'))
    
@main.route('/delete_peca/<int:id>', methods=['POST'])
@login_required
def delete_peca(id):
    peca = Peca.query.get_or_404(id)
    db.session.delete(peca)
    db.session.commit()
    flash('Peça removida com sucesso!', 'danger')
    return redirect(url_for('main.inventario'))

@main.route('/utilizadores')
@login_required
def lista_utilizadores():
    utilizadores = Utilizador.query.all()
    return render_template('utilizadores/lista_utilizadores.html', utilizadores=utilizadores, active_page='usuarios')

@main.route('/utilizadores/add', methods=['GET', 'POST'])
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
        observacoes = request.form.get('observacoes', '').strip()

        if not nome or not email or not senha or not confirmar_senha or not papel_id:
            flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
            return render_template('utilizadores/add_utilizadores.html', papeis=papeis, nome=nome, email=email)

        if senha != confirmar_senha:
             flash('As senhas não coincidem.', 'danger')
             return render_template('utilizadores/add_utilizadores.html', papeis=papeis, nome=nome, email=email)

        email_existente = Utilizador.query.filter_by(email=email).first()
        if email_existente:
            flash('Este email já está registado.', 'danger')
            return render_template('utilizadores/add_utilizadores.html', papeis=papeis, nome=nome, email=email)

        novo_utilizador = Utilizador(nome=nome, email=email, telefone=telefone, palavras_chave=palavras_chave, observacoes=observacoes)
        novo_utilizador.set_senha(senha)

        papel = Papel.query.get(int(papel_id))
        if papel:
            novo_utilizador.papeis.append(papel)

        db.session.add(novo_utilizador)
        db.session.commit()
        flash('Utilizador criado com sucesso!', 'success')
        return redirect(url_for('main.lista_utilizadores'))

    return render_template('utilizadores/add_utilizadores.html', papeis=papeis)

@main.route('/utilizadores/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_utilizador(id):
    if not current_user.is_admin() and current_user.id != id:
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
        observacoes = request.form.get('observacoes', '').strip()

        if not nome or not email or not papel_id:
            flash('Por favor, preencha todos os campos obrigatórios (Nome, Email, Papel).', 'danger')
            return render_template('utilizadores/edit_utilizadores.html', utilizador=utilizador, papeis=papeis)

        if email != utilizador.email:
            email_existente = Utilizador.query.filter_by(email=email).first()
            if email_existente and email_existente.id != utilizador.id:
                flash('Este email já está registado por outro utilizador.', 'danger')
                return render_template('utilizadores/edit_utilizadores.html', utilizador=utilizador, papeis=papeis)

        if senha:
            if senha != confirmar_senha:
                flash('As senhas não coincidem.', 'danger')
                return render_template('utilizadores/edit_utilizadores.html', utilizador=utilizador, papeis=papeis)
            utilizador.set_senha(senha)

        utilizador.nome = nome
        utilizador.email = email
        utilizador.telefone = telefone
        utilizador.palavras_chave = palavras_chave
        utilizador.observacoes = observacoes

        papel_selecionado = Papel.query.get(int(papel_id))
        if papel_selecionado:
            utilizador.papeis.clear()
            utilizador.papeis.append(papel_selecionado)

        db.session.commit()
        flash('Utilizador atualizado com sucesso!', 'success')
        return redirect(url_for('main.lista_utilizadores'))
        
    return render_template('utilizadores/edit_utilizadores.html', utilizador=utilizador, papeis=papeis, active_page='usuarios')

@main.route('/utilizadores/delete/<int:id>', methods=['POST'])
@login_required
def delete_utilizador(id):
    if not current_user.is_admin():
        flash('Você não tem permissão para apagar utilizadores.', 'danger')
        return redirect(url_for('main.lista_utilizadores'))

    if id == current_user.id:
        flash('Você não pode apagar sua própria conta.', 'danger')
        return redirect(url_for('main.lista_utilizadores'))

    utilizador = Utilizador.query.get_or_404(id)
    db.session.delete(utilizador)
    db.session.commit()
    flash('Utilizador apagado com sucesso!', 'success')
    return redirect(url_for('main.lista_utilizadores'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main.route('/uploads/<filename>')
def get_uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(os.path.abspath(UPLOAD_FOLDER), filename)

# 1. Rota para carregar a página HTML
@main.route('/ordens_servico')
@login_required
def ordens_servico():
    # 1. Busca todos os utilizadores que têm o papel 'Mecânico'
    mecanicos = Utilizador.query.join(Utilizador.papeis).filter(Papel.nome == 'Mecanico').all()
    
    # 2. Formata a lista para ser facilmente usada no JavaScript
    mecanicos_list = [{'id': m.id, 'nome': m.nome} for m in mecanicos]
    
    # 3. Passa a lista para o template no formato JSON
    return render_template('ordem_servico.html', mecanicos_json=json.dumps(mecanicos_list), active_page='ordens_servico')

# 2. API para OBTER todas as Ordens de Serviço (GET)
@main.route('/api/ordens_servico', methods=['GET'])
@login_required
def get_ordens_servico():
    from .models import OrdemServico
    ordens = OrdemServico.query.order_by(OrdemServico.data_criacao.desc()).all()
    return jsonify([ordem.to_dict() for ordem in ordens])

# 3. API para ADICIONAR uma nova Ordem de Serviço (POST) - CORRIGIDA
@main.route('/api/ordens_servico', methods=['POST'])
@login_required
def add_ordem_servico():
    from .models import OrdemServico, Servico, PecaUtilizada, Foto
    data = request.form
    if not data or not data.get('clientName') or not data.get('vehicle'):
        return jsonify({'error': 'Dados insuficientes'}), 400
    
    data_previsao_str = data.get('dataPrevisaoEntrega')
    data_previsao_obj = None
    if data_previsao_str:
        data_previsao_obj = datetime.strptime(data_previsao_str, '%Y-%m-%d').date()
    
    # --- CORREÇÃO APLICADA AQUI ---
    nova_ordem = OrdemServico(
        cliente_nome=data['clientName'],
        veiculo=data['vehicle'],
        descricao=data.get('description', ''),
        status=data.get('status', 'Em Andamento'),
        desconto=float(data.get('desconto', 0.0)),
        dataPrevisaoEntrega=data_previsao_obj  # Corrigido de dataPrevisaoEntrega
    )
    db.session.add(nova_ordem)

    # O resto da função continua igual
    servicos_data = json.loads(data.get('servicos', '[]'))
    pecas_data = json.loads(data.get('pecas', '[]'))

    for servico_data in servicos_data:
        if servico_data.get('nome'):
            novo_servico = Servico(
                nome=servico_data['nome'],
                valor=float(servico_data.get('valor', 0.0)),
                responsavel=servico_data.get('responsavel', ''),
                ordem_servico=nova_ordem
            )
            db.session.add(novo_servico)

    for peca_data in pecas_data:
        if peca_data.get('nome'):
            nova_peca = PecaUtilizada(
                nome=peca_data['nome'],
                quantidade=int(peca_data.get('qtd', 1)),
                valor_unitario=float(peca_data.get('valor', 0.0)),
                ordem_servico=nova_ordem
            )
            db.session.add(nova_peca)

    files = request.files.getlist('photos[]')
    for file in files:
        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            extension = original_filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4()}.{extension}"
            file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
            nova_foto = Foto(filename=unique_filename, ordem_servico=nova_ordem)
            db.session.add(nova_foto)
    
    db.session.commit()
    return jsonify(nova_ordem.to_dict()), 201

# 4. API para ATUALIZAR uma Ordem de Serviço existente (PUT) - CORRIGIDA
@main.route('/api/ordens_servico/<int:id>', methods=['PUT'])
@login_required
def update_ordem_servico(id):
    from .models import OrdemServico, Servico, PecaUtilizada, Foto
    ordem = OrdemServico.query.get_or_404(id)
    
    # CORREÇÃO: Mudar de request.get_json() para request.form
    data = request.form

    # --- INÍCIO: LÓGICA PARA DELETAR FOTOS EXISTENTES ---
    photos_to_delete_str = data.get('photos_to_delete', '[]')
    photos_to_delete_ids = json.loads(photos_to_delete_str)
    if photos_to_delete_ids:
        fotos_a_deletar = Foto.query.filter(Foto.id.in_(photos_to_delete_ids), Foto.ordem_servico_id == id).all()
        for foto in fotos_a_deletar:
            try:
                os.remove(os.path.join(UPLOAD_FOLDER, foto.filename))
            except OSError as e:
                print(f"Erro ao deletar arquivo {foto.filename}: {e}")
            db.session.delete(foto)

    # --- ATUALIZAÇÃO DOS CAMPOS PRINCIPAIS ---
    ordem.cliente_nome = data.get('clientName', ordem.cliente_nome)
    ordem.veiculo = data.get('vehicle', ordem.veiculo)
    ordem.descricao = data.get('description', ordem.descricao)
    ordem.status = data.get('status', ordem.status)
    ordem.desconto = float(data.get('desconto', ordem.desconto))

    # CORREÇÃO: Lógica para atualizar a data de previsão
    data_previsao_str = data.get('dataPrevisaoEntrega')
    if data_previsao_str:
        ordem.dataPrevisaoEntrega = datetime.strptime(data_previsao_str, '%Y-%m-%d').date()
    else:
        ordem.dataPrevisaoEntrega = None

    # --- RECRIAÇÃO DE SERVIÇOS E PEÇAS ---
    Servico.query.filter_by(ordem_servico_id=id).delete()
    PecaUtilizada.query.filter_by(ordem_servico_id=id).delete()
    
    # CORREÇÃO: Decodificar serviços e peças a partir do 'data' (request.form)
    servicos_data = json.loads(data.get('servicos', '[]'))
    pecas_data = json.loads(data.get('pecas', '[]'))

    for servico_data in servicos_data:
        if servico_data.get('nome'):
            novo_servico = Servico(nome=servico_data['nome'], valor=float(servico_data.get('valor', 0.0)), responsavel=servico_data.get('responsavel', ''), ordem_servico_id=id)
            db.session.add(novo_servico)

    for peca_data in pecas_data:
        if peca_data.get('nome'):
            nova_peca = PecaUtilizada(nome=peca_data['nome'], quantidade=int(peca_data.get('qtd', 1)), valor_unitario=float(peca_data.get('valor', 0.0)), ordem_servico_id=id)
            db.session.add(nova_peca)
    
    # --- ADIÇÃO DE NOVAS FOTOS ---
    files = request.files.getlist('photos[]')
    for file in files:
        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            extension = original_filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4()}.{extension}"
            file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
            nova_foto = Foto(filename=unique_filename, ordem_servico_id=id)
            db.session.add(nova_foto)

    db.session.commit()
    return jsonify(ordem.to_dict())

# 5. API para DELETAR uma Ordem de Serviço (DELETE)
@main.route('/api/ordens_servico/<int:id>', methods=['DELETE'])
@login_required
def delete_ordem_servico(id):
    from .models import OrdemServico
    ordem = OrdemServico.query.get_or_404(id)
    # Adicionar lógica para apagar arquivos de fotos da pasta 'uploads' se desejar
    db.session.delete(ordem)
    db.session.commit()
    return jsonify({'success': 'Ordem de serviço deletada'}), 200

# --- INÍCIO: NOVAS ROTAS DE API PARA AUTOCOMPLETE ---

@main.route('/api/clientes/search')
@login_required
def search_clientes():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    
    # Busca tanto pelo ID quanto pelo nome
    if query.isdigit():
        clientes = Cliente.query.filter(
            (Cliente.id == int(query)) | (Cliente.nome.ilike(f'%{query}%'))
        ).limit(10).all()
    else:
        clientes = Cliente.query.filter(Cliente.nome.ilike(f'%{query}%')).limit(10).all()
    
    # O 'label' é o que o usuário vê (ID + Nome)
    results = [
        {'id': cliente.id, 'label': f"#{cliente.id} - {cliente.nome}", 'value': cliente.nome}
        for cliente in clientes
    ]
    return jsonify(results)

@main.route('/api/clientes/<int:cliente_id>/veiculos/search')
@login_required
def search_veiculos_cliente(cliente_id):
    query = request.args.get('q', '').strip().lower()
    
    carros = Carro.query.filter_by(cliente_id=cliente_id).all()
    
    # Filtra em memória se houver uma query
    if query:
        filtered_carros = [
            carro for carro in carros 
            if query in carro.full_description.lower()
        ]
    else:
        filtered_carros = carros

    results = [
        {'id': carro.id, 'label': carro.full_description, 'value': carro.full_description}
        for carro in filtered_carros[:10]
    ]
    return jsonify(results)

# --- FIM: NOVAS ROTAS DE API PARA AUTOCOMPLETE ---

# --- ROTAS DE ADIÇÃO MODIFICADAS PARA RETORNAR JSON ---
@main.route('/api/clientes', methods=['POST'])
@login_required
def api_add_cliente():
    data = request.get_json()
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'error': 'O nome do cliente é obrigatório.'}), 400
    
    if Cliente.query.filter_by(nome=nome).first():
        return jsonify({'error': 'Este cliente já está cadastrado.'}), 409

    novo_cliente = Cliente(
        nome=nome,
        apelido=data.get('apelido', '').strip() or None,
        cpf=data.get('cpf', '').strip() or None,
        cnpj=data.get('cnpj', '').strip() or None
    )
    db.session.add(novo_cliente)
    db.session.commit()

    # Adiciona os telefones
    numeros = data.get('numeros', [])
    for numero in numeros:
        if numero.strip():
            novo_telefone = Telefone(numero=numero.strip(), cliente_id=novo_cliente.id)
            db.session.add(novo_telefone)
    
    db.session.commit() # Commit final com os telefones
    
    # Retorna os dados do cliente criado para o frontend    
    return jsonify({
        'id': novo_cliente.id,
        'nome': novo_cliente.nome
    }), 201

# Adicione esta nova rota para carros
@main.route('/api/clientes/<int:cliente_id>/carros', methods=['POST'])
@login_required
def api_add_carro(cliente_id):
    if not Cliente.query.get(cliente_id):
        return jsonify({'error': 'Cliente não encontrado.'}), 404
        
    data = request.get_json()
    placa = data.get('placa', '').strip()
    if not placa:
        return jsonify({'error': 'A placa do veículo é obrigatória.'}), 400

    if Carro.query.filter_by(placa=placa).first():
        return jsonify({'error': 'Veículo com esta placa já cadastrado.'}), 409

    novo_carro = Carro(
        cliente_id=cliente_id,
        marca=data.get('marca', ''),
        modelo=data.get('modelo', ''),
        placa=placa,
        ano=data.get('ano') or None,
        motor=data.get('motor') or None,
        quilometragem=data.get('quilometragem') or None
    )
    db.session.add(novo_carro)
    db.session.commit()

    return jsonify(novo_carro.to_dict()), 201

# --- NOVA ROTA PARA ADICIONAR PAGAMENTO A UMA OS ---
@main.route('/api/ordens_servico/<int:os_id>/pagamento', methods=['POST'])
@login_required
def add_pagamento_os(os_id):
    ordem = OrdemServico.query.get_or_404(os_id)
    cliente = Cliente.query.filter_by(nome=ordem.cliente_nome).first()

    if not cliente:
        flash('Cliente associado à Ordem de Serviço não encontrado.', 'danger')
        return redirect(request.referrer or url_for('main.client'))

    if ordem.pagamento:
        flash('Esta Ordem de Serviço já possui um pagamento registrado.', 'warning')
        return redirect(url_for('main.cliente', id=cliente.id, tab='veiculos-pane'))
    
    try:
        data = request.form
        valor_str = data.get('valor').replace('.', '').replace(',', '.')
        valor = float(valor_str)
        
        novo_pagamento = Pagamento(
            cliente_id=cliente.id,
            ordem_servico_id=os_id,
            data=datetime.now(pytz.utc),
            valor=valor,
            metodo=data.get('metodo'),
            tipo_pagamento=data.get('tipo_pagamento'),
            parcelas=int(data.get('parcelas')) if data.get('parcelas') else None
        )
        db.session.add(novo_pagamento)
        db.session.commit()
        flash('Pagamento registrado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar pagamento: {e}', 'danger')

    return redirect(url_for('main.cliente', id=cliente.id, tab='veiculos-pane'))

# --- INÍCIO: NOVA ROTA PARA EDITAR PAGAMENTO ---
@main.route('/api/pagamentos/<int:pagamento_id>/edit', methods=['POST'])
@login_required
def edit_pagamento(pagamento_id):
    pagamento = Pagamento.query.get_or_404(pagamento_id)
    cliente_id = pagamento.cliente_id

    # Verificação de permissão (opcional)
    if pagamento.ordem_servico.cliente_nome != current_user.nome and not current_user.is_admin():
        flash('Você não tem permissão para editar este pagamento.', 'danger')
        return redirect(url_for('main.cliente', id=cliente_id, tab='pagamentos-pane'))

    try:
        data = request.form
        valor_str = data.get('valor').replace('.', '').replace(',', '.')
        pagamento.valor = float(valor_str)
        pagamento.metodo = data.get('metodo')
        pagamento.tipo_pagamento = data.get('tipo_pagamento')
        pagamento.parcelas = int(data.get('parcelas')) if data.get('parcelas') else None
        
        db.session.commit()
        flash('Pagamento atualizado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar pagamento: {e}', 'danger')
        
    return redirect(url_for('main.cliente', id=cliente_id, tab='pagamentos-pane'))

# --- FIM: NOVA ROTA ---

# --- INÍCIO: NOVA ROTA PARA DELETAR PAGAMENTO ---
@main.route('/api/pagamentos/<int:pagamento_id>/delete', methods=['POST'])
@login_required
def delete_pagamento(pagamento_id):
    pagamento = Pagamento.query.get_or_404(pagamento_id)
    cliente_id = pagamento.cliente_id # Guarda o ID do cliente para o redirecionamento
    
    # Verificação de permissão (opcional, mas recomendado)
    if pagamento.ordem_servico.cliente_nome != current_user.nome and not current_user.is_admin():
        flash('Você não tem permissão para deletar este pagamento.', 'danger')
        return redirect(url_for('main.cliente', id=cliente_id, tab='pagamentos-pane'))

    try:
        db.session.delete(pagamento)
        db.session.commit()
        flash('Pagamento removido com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao remover pagamento: {e}', 'danger')
        
    return redirect(url_for('main.cliente', id=cliente_id, tab='pagamentos-pane'))

# --- FIM: NOVA ROTA ---

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form['email'].strip()
        senha = request.form['senha']
        remember = True if request.form.get('remember') else False

        utilizador = Utilizador.query.filter_by(email=email).first()

        if utilizador and utilizador.check_senha(senha):
            new_session_token = str(uuid.uuid4())
            utilizador.session_token = new_session_token
            db.session.commit()
            session['session_token'] = new_session_token

            login_user(utilizador, remember=remember)
            return redirect(url_for('main.index'))
        else:
            flash('Email ou senha inválidos.', 'danger')
    
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    if 'session_token' in session:
        session.pop('session_token', None)
    
    logout_user()
    return redirect(url_for('main.login'))