from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from .models import db, Cliente, Telefone, Carro, Peca, Historico, Pagamento, Utilizador, Papel, utilizador_papeis, OrdemServico
from datetime import datetime, timedelta
import pytz
from werkzeug.security import generate_password_hash
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy import delete
import uuid
import json # Adicione esta importação
from werkzeug.utils import secure_filename
import os
import uuid
import json # Adicione esta importação

main = Blueprint('main', __name__)

UPLOAD_FOLDER = 'uploads' 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def ajustar_para_brasilia(data_utc):
    """
    Ajusta um objeto datetime para o fuso horário de Brasília.
    """
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    if data_utc.tzinfo is None:
        data_utc = pytz.utc.localize(data_utc)
    return data_utc.astimezone(fuso_brasilia)

@main.before_request
def check_single_session():
    if current_user.is_authenticated and request.endpoint and \
       not request.endpoint.startswith('main.static') and \
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
    return render_template('index.html')

@main.route('/inventario', methods=['GET'])
@login_required
def inventario():
    query = request.args.get('query', '').lower()
    pecas = db.session.query(Peca).all()

    if query:
        pecas = [peca for peca in pecas if query in peca.nome.lower() or query in peca.descricao.lower()]

    return render_template('inventario.html', pecas=pecas, query=query)

@main.route('/listaclientes')
@login_required
def client():
    query = request.args.get('query', '')
    if query:
        clientes = Cliente.query.filter(Cliente.nome.ilike(f'%{query}%')).all()
    else:
        clientes = Cliente.query.all()
    return render_template('listacliente.html', clientes=clientes, search_query=query)

@main.route('/cliente/<int:id>')
@login_required
def cliente(id):
    cliente = Cliente.query.get_or_404(id)
    telefones = Telefone.query.filter_by(cliente_id=id).all()
    historicos = Historico.query.filter_by(cliente_id=id).order_by(Historico.data.desc()).all()
    pagamentos = Pagamento.query.filter_by(cliente_id=id).order_by(Pagamento.data.desc()).all()
    carros = Carro.query.filter_by(cliente_id=id).all()
    
    for historico in historicos:
        if historico.data: 
            historico.data_local = ajustar_para_brasilia(historico.data)
        else:
            historico.data_local = None
        historico.tem_pagamento = any(pagamento.historico_id == historico.id for pagamento in pagamentos)
        
    for pagamento in pagamentos:
        if pagamento.data:
            pagamento.data_local = ajustar_para_brasilia(pagamento.data)
        else:
            pagamento.data_local = None

    return render_template('cliente.html', cliente=cliente, telefones=telefones, historicos=historicos, pagamentos=pagamentos, carros=carros)
    
@main.route('/add', methods=['POST'])
@login_required
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

@main.route('/delete_cliente/<int:id>', methods=['POST'])
@login_required
def delete_cliente(id):
    if not current_user.is_admin():
        flash('Você não tem permissão para apagar clientes.', 'danger')
        return redirect(url_for('main.client'))

    cliente = Cliente.query.get_or_404(id)

    try:
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
    active_tab = request.form.get('active_tab', 'telefones-pane') # 🔹 Obtém a aba ativa

    for numero in numeros:
        if numero.strip():
            novo_telefone = Telefone(numero=numero, cliente_id=cliente_id)
            db.session.add(novo_telefone)

    db.session.commit()
    flash('Telefone(s) adicionado(s) com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa

@main.route('/update_telefone/<int:telefone_id>', methods=['POST'])
@login_required
def update_telefone(telefone_id):
    novo_numero = request.form.get('numero', '').strip()
    active_tab = request.form.get('active_tab', 'telefones-pane') # 🔹 Obtém a aba ativa
    
    telefone = Telefone.query.get_or_404(telefone_id)
    telefone.numero = novo_numero
    db.session.commit()
    flash('Telefone atualizado com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=telefone.cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa

@main.route('/delete_telefone/<int:telefone_id>', methods=['POST'])
@login_required
def delete_telefone(telefone_id):
    telefone = Telefone.query.get_or_404(telefone_id)
    cliente_id = telefone.cliente_id
    active_tab = request.form.get('active_tab', 'telefones-pane') # 🔹 Obtém a aba ativa
    db.session.delete(telefone)
    db.session.commit()
    flash('Telefone removido com sucesso!', 'danger')
    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa

@main.route('/update_dados_cliente/<int:cliente_id>', methods=['POST'])
@login_required
def update_dados_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    active_tab = request.form.get('active_tab', 'dados-pessoais-pane') # 🔹 Obtém a aba ativa

    enderecos = request.form.getlist('endereco[]') if 'endereco[]' in request.form else []
    numeros = request.form.getlist('numero[]') if 'numero[]' in request.form else [] 
    complementos = request.form.getlist('complemento[]') if 'complemento[]' in request.form else [] 
    bairros = request.form.getlist('bairro[]') if 'bairro[]' in request.form else []
    cidades = request.form.getlist('cidade[]') if 'cidade[]' in request.form else []
    ceps = request.form.getlist('cep[]') if 'cep[]' in request.form else []
    estados = request.form.getlist('estado[]') if 'estado[]' in request.form else []

    cliente.endereco = "; ".join(filter(None, enderecos)) if any(filter(None, enderecos)) else None
    cliente.numero = "; ".join(filter(None, numeros)) if any(filter(None, numeros)) else None 
    cliente.complemento = "; ".join(filter(None, complementos)) if any(filter(None, complementos)) else None 
    cliente.bairro = "; ".join(filter(None, bairros)) if any(filter(None, bairros)) else None
    cliente.cidade = "; ".join(filter(None, cidades)) if any(filter(None, cidades)) else None
    cliente.cep = "; ".join(filter(None, ceps)) if any(filter(None, ceps)) else None
    cliente.estado = "; ".join(filter(None, estados)) if any(filter(None, estados)) else None

    cliente.apelido = request.form.get('apelido', '').strip()
    cliente.cpf = request.form.get('cpf', '').strip()
    cliente.cnpj = request.form.get('cnpj', '').strip()

    db.session.commit()
    flash('Dados do cliente atualizados com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa
    
@main.route('/add_historico/<int:carro_id>', methods=['POST'])
@login_required
def add_historico(carro_id):
    descricao = request.form['descricao']
    data_str = request.form['data']
    active_tab = request.form.get('active_tab', 'veiculos-pane') # 🔹 Obtém a aba ativa
    
    data_do_form = datetime.strptime(data_str, '%Y-%m-%d')
    hora_atual = datetime.now().time()
    data_historico_local = data_do_form.replace(
        hour=hora_atual.hour,
        minute=hora_atual.minute,
        second=hora_atual.second,
        microsecond=hora_atual.microsecond
    )
    
    carro = Carro.query.get_or_404(carro_id)

    novo_historico = Historico(cliente_id=carro.cliente_id, carro_id=carro.id, descricao=descricao, data=data_historico_local)
    
    db.session.add(novo_historico)
    db.session.commit()
    flash('Histórico adicionado com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=carro.cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa

@main.route('/edit_historico/<int:id>', methods=['POST'])
@login_required
def edit_historico(id):
    historico = Historico.query.get_or_404(id)
    descricao = request.form['descricao']
    data_str = request.form['data']
    active_tab = request.form.get('active_tab', 'veiculos-pane') # 🔹 Obtém a aba ativa

    data_do_form = datetime.strptime(data_str, '%Y-%m-%d')
    hora_atual = datetime.now().time()
    data_atualizada_local = data_do_form.replace(
        hour=hora_atual.hour,
        minute=hora_atual.minute,
        second=hora_atual.second,
        microsecond=hora_atual.microsecond
    )

    historico.descricao = descricao
    historico.data = data_atualizada_local
    
    db.session.commit()
    flash('Histórico atualizado com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=historico.cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa

@main.route('/delete_historico/<int:id>', methods=['POST'])
@login_required
def delete_historico(id):
    historico = Historico.query.get_or_404(id)
    cliente_id = historico.cliente_id
    active_tab = request.form.get('active_tab', 'veiculos-pane') # 🔹 Obtém a aba ativa
    db.session.delete(historico)
    db.session.commit()
    flash('Histórico removido com sucesso!', 'danger')
    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa


@main.route('/add_carros_cliente/<int:cliente_id>', methods=['POST'])
@login_required
def add_carros(cliente_id):
    active_tab = request.form.get('active_tab', 'veiculos-pane') # 🔹 Obtém a aba ativa
    carros_data = request.form.to_dict(flat=False)

    if 'marca[]' not in carros_data or not carros_data['marca[]']:
        flash('Erro: Nenhuma marca de carro fornecida. Por favor, adicione pelo menos um carro.', 'danger')
        return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa

    for i in range(len(carros_data['marca[]'])):
        try:
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
            db.session.rollback()
            return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa

    db.session.commit()
    flash('Carro(s) adicionado(s) com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa


@main.route('/update_carros_cliente/<int:cliente_id>', methods=['POST'])
@login_required
def update_carros(cliente_id):
    carros = Carro.query.filter_by(cliente_id=cliente_id).all()
    active_tab = request.form.get('active_tab', 'veiculos-pane') # 🔹 Obtém a aba ativa
    
    for carro in carros:
        carro.marca = request.form.get(f'marca_{carro.id}', carro.marca)
        carro.modelo = request.form.get(f'modelo_{carro.id}', carro.modelo)
        carro.motor = request.form.get(f'motor_{carro.id}', carro.motor)
        
        ano_str = request.form.get(f'ano_{carro.id}')
        if ano_str:
            carro.ano = int(ano_str)
        
        carro.placa = request.form.get(f'placa_{carro.id}', carro.placa)
        
        quilometragem_str = request.form.get(f'quilometragem_{carro.id}')
        if quilometragem_str:
            carro.quilometragem = int(quilometragem_str)
        
        db.session.add(carro)

    db.session.commit()
    flash('Dados do carro atualizados com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa
    
# ROTAS RELACIONADAS AO PAGAMENTO
@main.route('/add_pagamento/<int:carro_id>/<int:historico_id>', methods=['POST'])
@login_required
def add_pagamento(carro_id, historico_id):
    valor_str = request.form['valor'].replace(',', '.')
    valor = float(valor_str)  
    
    metodo = request.form['metodo']
    tipo_pagamento = request.form.get('tipo_pagamento')
    parcelas_str = request.form.get('parcelas')
    active_tab = request.form.get('active_tab', 'pagamentos-pane') # 🔹 Obtém a aba ativa

    parcelas = None
    if tipo_pagamento == 'Parcelado' and parcelas_str and parcelas_str.strip():
        try:
            parcelas = int(parcelas_str)
        except ValueError:
            flash('Número de parcelas inválido.', 'danger')
            return redirect(url_for('main.cliente', id=Carro.query.get_or_404(carro_id).cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa

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
        data=datetime.now(pytz.utc) 
    )

    db.session.add(novo_pagamento)
    db.session.commit()
    flash('Pagamento registrado com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=carro.cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa

@main.route('/edit_pagamento/<int:id>', methods=['POST'])
@login_required
def edit_pagamento(id):
    pagamento = Pagamento.query.get_or_404(id)
    active_tab = request.form.get('active_tab', 'pagamentos-pane') # 🔹 Obtém a aba ativa
    
    valor_str = request.form['valor'].replace(',', '.')
    pagamento.valor = float(valor_str)
    
    pagamento.metodo = request.form['metodo']
    pagamento.tipo_pagamento = request.form.get('tipo_pagamento')
    parcelas_str = request.form.get('parcelas')

    pagamento.parcelas = None
    if pagamento.tipo_pagamento == 'Parcelado' and parcelas_str and parcelas_str.strip():
        try:
            pagamento.parcelas = int(parcelas_str)
        except ValueError:
            flash('Número de parcelas inválido.', 'danger')
            return redirect(url_for('main.cliente', id=pagamento.cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa


    db.session.commit()
    flash('Pagamento atualizado com sucesso!', 'success')
    return redirect(url_for('main.cliente', id=pagamento.cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa

@main.route('/delete_pagamento/<int:id>', methods=['POST'])
@login_required
def delete_pagamento(id):
    pagamento = Pagamento.query.get_or_404(id)
    cliente_id = pagamento.cliente_id
    active_tab = request.form.get('active_tab', 'pagamentos-pane') # 🔹 Obtém a aba ativa
    db.session.delete(pagamento)
    db.session.commit()
    flash('Pagamento removido com sucesso!', 'danger')
    return redirect(url_for('main.cliente', id=cliente_id, tab=active_tab)) # 🔹 Passa a aba ativa

@main.route('/add_peca', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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

@main.route('/utilizadores')
@login_required
def lista_utilizadores():
    utilizadores = Utilizador.query.all()
    return render_template('utilizadores/lista_utilizadores.html', utilizadores=utilizadores)

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

    return render_template('utilizadores/edit_utilizadores.html', utilizador=utilizador, papeis=papeis)

@main.route('/utilizadores/delete/<int:id>', methods=['POST'])
@login_required
def delete_utilizador(id):
    if not current_user.is_admin():
        flash('Você não tem permissão para apagar utilizadores.', 'danger')
        return redirect(url_for('main.lista_utilizadores'))

    utilizador = Utilizador.query.get_or_404(id)

    try:
        if utilizador.id == current_user.id:
            flash('Você não pode apagar a sua própria conta enquanto estiver logado.', 'danger')
            return redirect(url_for('main.lista_utilizadores'))

        db.session.execute(delete(utilizador_papeis).where(utilizador_papeis.c.id_utilizador == utilizador.id))
        
        db.session.delete(utilizador)
        db.session.commit()
        flash('Utilizador apagado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao apagar utilizador: {e}', 'danger')
    
    return redirect(url_for('main.lista_utilizadores'))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Rota para servir os arquivos que foram upados
@main.route('/uploads/<filename>')
def get_uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(os.path.join(os.getcwd(), UPLOAD_FOLDER), filename)

# 1. Rota para carregar a página HTML
@main.route('/ordens_servico')
@login_required
def ordens_servico():
    return render_template('ordem_servico.html')

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