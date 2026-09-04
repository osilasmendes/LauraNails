import os
import base64
from datetime import datetime
from functools import wraps
from urllib.parse import quote

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect, text

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "chave-local-laura-nails")

database_url = os.environ.get("DATABASE_URL", "sqlite:///laura_nails.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    whatsapp = db.Column(db.String(40), unique=True, nullable=False)
    email = db.Column(db.String(160))
    endereco = db.Column(db.String(180))
    numero = db.Column(db.String(30))
    complemento = db.Column(db.String(120))
    bairro = db.Column(db.String(120))
    cidade = db.Column(db.String(120))
    foto_perfil = db.Column(db.Text)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.String(20), default="cliente", nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class Agendamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    servico = db.Column(db.String(120), nullable=False)
    valor = db.Column(db.String(30), nullable=False)
    data = db.Column(db.String(10), nullable=False)
    horario = db.Column(db.String(5), nullable=False)
    observacao = db.Column(db.String(500))
    forma_pagamento = db.Column(db.String(30))
    valor_original = db.Column(db.String(30))
    desconto_aplicado = db.Column(db.String(30))
    promocao_titulo = db.Column(db.String(120))
    status = db.Column(db.String(30), default="Agendado", nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    cliente = db.relationship("Usuario", backref="agendamentos")


<<<<<<< HEAD
class Avaliacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), unique=True, nullable=False)
    estrelas = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.String(1000))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    cliente = db.relationship("Usuario", backref=db.backref("avaliacao", uselist=False))


SERVICOS = [
=======
class Servico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), unique=True, nullable=False)
    valor = db.Column(db.String(30), nullable=False)


SERVICOS_PADRAO = [
>>>>>>> a4b7643 (Atualiza painel, promocoes, clientes e financeiro)
    {"nome": "Unha em gel na tips", "valor": "R$ 90,00"},
    {"nome": "Banho de gel", "valor": "R$ 85,00"},
    {"nome": "Postiça realista", "valor": "R$ 50,00"},
    {"nome": "Esmaltação em gel", "valor": "R$ 45,00"},
    {"nome": "Pé e mão", "valor": "R$ 40,00"},
    {"nome": "Só o pé ou a mão", "valor": "R$ 25,00"},
    {"nome": "Manutenção - unha em gel", "valor": "R$ 85,00"},
    {"nome": "Manutenção - banho de gel", "valor": "R$ 80,00"},
]


def obter_servicos():
    """Retorna os serviços do banco, criando os padrões somente se a tabela estiver vazia."""
    if Servico.query.count() == 0:
        for item in SERVICOS_PADRAO:
            db.session.add(Servico(nome=item["nome"], valor=item["valor"]))
        db.session.commit()
    return Servico.query.order_by(Servico.id.asc()).all()


def valor_para_float(valor):
    """Converte valores como R$ 90,00 para número."""
    if valor is None:
        return None
    texto = str(valor).replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except (TypeError, ValueError):
        return None


def formatar_valor(numero):
    return f"R$ {numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

class Promocao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(30), default="Promoção", nullable=False)
    titulo = db.Column(db.String(120), nullable=False)
    mensagem = db.Column(db.String(500), nullable=False)
    servico_nome = db.Column(db.String(120))
    valor_promocional = db.Column(db.String(30))
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


HORARIOS_PADRAO = ["09:00", "11:30", "14:00", "16:30", "18:00", "20:00"]
HORARIOS_QUINTA = ["09:00", "14:00", "16:30", "18:00", "20:00"]
FORMAS_PAGAMENTO = ["Cartão de crédito", "Cartão de débito", "Pix", "Dinheiro"]


def horarios_para_data(data_str):
    try:
        data_obj = datetime.strptime(data_str, "%Y-%m-%d")
    except ValueError:
        return []

    dia_semana = data_obj.weekday()
    if dia_semana not in [1, 2, 3, 4, 5]:
        return []
    if dia_semana == 3:
        return HORARIOS_QUINTA
    return HORARIOS_PADRAO


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("usuario_id"):
            flash("Entre na sua conta para continuar.", "aviso")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("usuario_id") or session.get("perfil") != "admin":
            flash("Acesso exclusivo da administração.", "erro")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def garantir_coluna_forma_pagamento():
    inspetor = inspect(db.engine)
    if "agendamento" not in inspetor.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspetor.get_columns("agendamento")}
    if "forma_pagamento" not in colunas:
        with db.engine.begin() as conexao:
            conexao.execute(text("ALTER TABLE agendamento ADD COLUMN forma_pagamento VARCHAR(30)"))


def garantir_colunas_promocao():
    """Adiciona os campos de serviço/preço promocional sem apagar promoções existentes."""
    inspetor = inspect(db.engine)
    if "promocao" not in inspetor.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspetor.get_columns("promocao")}
    novas_colunas = {
        "servico_nome": "VARCHAR(120)",
        "valor_promocional": "VARCHAR(30)",
    }

    with db.engine.begin() as conexao:
        for nome, tipo in novas_colunas.items():
            if nome not in colunas:
                conexao.execute(text(f"ALTER TABLE promocao ADD COLUMN {nome} {tipo}"))


def garantir_colunas_promocao_agendamento():
    """Registra preço original e desconto nos novos agendamentos, preservando os antigos."""
    inspetor = inspect(db.engine)
    if "agendamento" not in inspetor.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspetor.get_columns("agendamento")}
    novas_colunas = {
        "valor_original": "VARCHAR(30)",
        "desconto_aplicado": "VARCHAR(30)",
        "promocao_titulo": "VARCHAR(120)",
    }

    with db.engine.begin() as conexao:
        for nome, tipo in novas_colunas.items():
            if nome not in colunas:
                conexao.execute(text(f"ALTER TABLE agendamento ADD COLUMN {nome} {tipo}"))


def garantir_colunas_usuario():
    """Adiciona os campos do perfil em bancos existentes sem apagar clientes."""
    inspetor = inspect(db.engine)
    if "usuario" not in inspetor.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspetor.get_columns("usuario")}
    novas_colunas = {
        "email": "VARCHAR(160)",
        "endereco": "VARCHAR(180)",
        "numero": "VARCHAR(30)",
        "complemento": "VARCHAR(120)",
        "bairro": "VARCHAR(120)",
        "cidade": "VARCHAR(120)",
        "foto_perfil": "TEXT",
    }

    with db.engine.begin() as conexao:
        for nome, tipo in novas_colunas.items():
            if nome not in colunas:
                conexao.execute(text(f"ALTER TABLE usuario ADD COLUMN {nome} {tipo}"))


def criar_admin():
    admin_user = os.environ.get("ADMIN_USER", "laura.laura")
    admin_password = os.environ.get("ADMIN_PASSWORD")

    if admin_password:
        existente = Usuario.query.filter_by(whatsapp=admin_user).first()
        if not existente:
            admin = Usuario(
                nome="Laura Silva",
                whatsapp=admin_user,
                senha_hash=generate_password_hash(admin_password),
                perfil="admin",
            )
            db.session.add(admin)
            db.session.commit()


@app.before_request
def garantir_banco():
    db.create_all()
    garantir_coluna_forma_pagamento()
    garantir_colunas_usuario()
    garantir_colunas_promocao()
    garantir_colunas_promocao_agendamento()
    criar_admin()


@app.route("/")
def inicio():
    return render_template("index.html", servicos=obter_servicos(), promocao=Promocao.query.filter_by(ativo=True).order_by(Promocao.id.desc()).first())


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        senha = request.form.get("senha", "")

        if not nome or not whatsapp or len(senha) < 6:
            flash("Preencha todos os dados corretamente.", "erro")
            return redirect(url_for("cadastro"))

        if Usuario.query.filter_by(whatsapp=whatsapp).first():
            flash("Já existe uma conta com esse WhatsApp.", "aviso")
            return redirect(url_for("login"))

        usuario = Usuario(
            nome=nome,
            whatsapp=whatsapp,
            senha_hash=generate_password_hash(senha),
            perfil="cliente"
        )
        db.session.add(usuario)
        db.session.commit()

        # A cliente já entra na conta e segue direto para o novo perfil.
        session["usuario_id"] = usuario.id
        session["nome"] = usuario.nome
        session["perfil"] = usuario.perfil
        flash("Conta criada com sucesso! Complete seu cadastro.", "sucesso")
        return redirect(url_for("perfil_cliente"))

    return render_template("cadastro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        whatsapp = request.form.get("whatsapp", "").strip()
        senha = request.form.get("senha", "")

        usuario = Usuario.query.filter_by(whatsapp=whatsapp).first()
        if not usuario or not check_password_hash(usuario.senha_hash, senha):
            flash("Usuário ou senha inválidos.", "erro")
            return redirect(url_for("login"))

        session["usuario_id"] = usuario.id
        session["nome"] = usuario.nome
        session["perfil"] = usuario.perfil
<<<<<<< HEAD
        return redirect(url_for("admin" if usuario.perfil == "admin" else "agendar"))
=======

        return redirect(url_for("admin" if usuario.perfil == "admin" else "perfil_cliente"))
>>>>>>> a4b7643 (Atualiza painel, promocoes, clientes e financeiro)

    return render_template("login.html")


@app.route("/esqueci-senha", methods=["GET", "POST"])
def esqueci_senha():
    if request.method == "POST":
        whatsapp = request.form.get("whatsapp", "").strip()
        usuario = Usuario.query.filter_by(whatsapp=whatsapp, perfil="cliente").first()

        if not usuario:
            flash("Não encontramos uma conta de cliente com esse WhatsApp.", "erro")
            return redirect(url_for("esqueci_senha"))

        session["redefinir_usuario_id"] = usuario.id
        return redirect(url_for("redefinir_senha"))

    return render_template("esqueci_senha.html")


@app.route("/redefinir-senha", methods=["GET", "POST"])
def redefinir_senha():
    usuario_id = session.get("redefinir_usuario_id")
    if not usuario_id:
        flash("Inicie a recuperação informando seu WhatsApp.", "aviso")
        return redirect(url_for("esqueci_senha"))

    usuario = Usuario.query.get(usuario_id)
    if not usuario or usuario.perfil != "cliente":
        session.pop("redefinir_usuario_id", None)
        flash("Não foi possível localizar a conta.", "erro")
        return redirect(url_for("login"))

    if request.method == "POST":
        senha = request.form.get("senha", "")
        confirmar = request.form.get("confirmar_senha", "")

        if len(senha) < 6:
            flash("A nova senha precisa ter pelo menos 6 caracteres.", "erro")
            return redirect(url_for("redefinir_senha"))

        if senha != confirmar:
            flash("As senhas informadas não são iguais.", "erro")
            return redirect(url_for("redefinir_senha"))

        usuario.senha_hash = generate_password_hash(senha)
        db.session.commit()
        session.pop("redefinir_usuario_id", None)
        flash("Senha alterada com sucesso. Entre com sua nova senha.", "sucesso")
        return redirect(url_for("login"))

    return render_template("redefinir_senha.html", usuario=usuario)


@app.route("/admin/clientes/novo", methods=["GET", "POST"])
@admin_required
def admin_novo_cliente():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        senha = request.form.get("senha", "")
        email = request.form.get("email", "").strip()

        if not nome or not whatsapp or len(senha) < 6:
            flash("Informe nome, WhatsApp e uma senha com pelo menos 6 caracteres.", "erro")
            return redirect(url_for("admin_novo_cliente"))

        if Usuario.query.filter_by(whatsapp=whatsapp).first():
            flash("Já existe uma conta cadastrada com esse WhatsApp.", "aviso")
            return redirect(url_for("admin_novo_cliente"))

        if email and ("@" not in email or "." not in email.split("@")[-1]):
            flash("Informe um e-mail válido ou deixe o campo vazio.", "erro")
            return redirect(url_for("admin_novo_cliente"))

        cliente = Usuario(
            nome=nome,
            whatsapp=whatsapp,
            email=email or None,
            endereco=request.form.get("endereco", "").strip() or None,
            numero=request.form.get("numero", "").strip() or None,
            complemento=request.form.get("complemento", "").strip() or None,
            bairro=request.form.get("bairro", "").strip() or None,
            cidade=request.form.get("cidade", "").strip() or None,
            senha_hash=generate_password_hash(senha),
            perfil="cliente",
        )

        db.session.add(cliente)
        db.session.commit()
        flash(f"Cliente {cliente.nome} cadastrado com sucesso.", "sucesso")
        return redirect(url_for("admin_cliente_detalhes", id=cliente.id))

    return render_template("admin_novo_cliente.html")


@app.route("/admin/clientes")
@admin_required
def admin_clientes():
    clientes = Usuario.query.filter_by(perfil="cliente").order_by(Usuario.criado_em.desc()).all()
    lista = []

    for cliente in clientes:
        historico = Agendamento.query.filter_by(usuario_id=cliente.id).order_by(
            Agendamento.data.desc(), Agendamento.horario.desc()
        ).all()

        validos = [a for a in historico if a.status != "Cancelado"]
        concluidos_cliente = [a for a in historico if a.status == "Concluído"]
        cancelados_cliente = [a for a in historico if a.status == "Cancelado"]
        ultimo = historico[0] if historico else None

        lista.append({
            "id": cliente.id,
            "nome": cliente.nome,
            "whatsapp": cliente.whatsapp,
            "email": cliente.email,
            "endereco": cliente.endereco,
            "numero": cliente.numero,
            "complemento": cliente.complemento,
            "bairro": cliente.bairro,
            "cidade": cliente.cidade,
            "foto_perfil": cliente.foto_perfil,
            "criado_em": cliente.criado_em,
            "total": len(validos),
            "concluidos": len(concluidos_cliente),
            "cancelados": len(cancelados_cliente),
            "ultimo_servico": ultimo.servico if ultimo else "Nenhum atendimento",
            "ultima_data": ultimo.data if ultimo else "—",
        })

    return render_template("clientes.html", clientes=lista, total_clientes=len(lista))


@app.route("/avaliar", methods=["GET", "POST"])
@login_required
def avaliar():
    if session.get("perfil") == "admin":
        return redirect(url_for("admin_avaliacoes"))

    avaliacao = Avaliacao.query.filter_by(usuario_id=session["usuario_id"]).first()

    if request.method == "POST":
        try:
            estrelas = int(request.form.get("estrelas", "0"))
        except ValueError:
            estrelas = 0
        comentario = request.form.get("comentario", "").strip()

        if estrelas < 1 or estrelas > 5:
            flash("Escolha uma nota de 1 a 5 estrelas.", "erro")
            return redirect(url_for("avaliar"))

        if len(comentario) > 1000:
            flash("O comentário pode ter no máximo 1000 caracteres.", "erro")
            return redirect(url_for("avaliar"))

        if avaliacao:
            avaliacao.estrelas = estrelas
            avaliacao.comentario = comentario
            avaliacao.atualizado_em = datetime.utcnow()
            mensagem = "Sua avaliação foi atualizada. Obrigada pelo feedback!"
        else:
            avaliacao = Avaliacao(
                usuario_id=session["usuario_id"],
                estrelas=estrelas,
                comentario=comentario,
            )
            db.session.add(avaliacao)
            mensagem = "Avaliação enviada com sucesso. Obrigada pelo feedback!"

        db.session.commit()
        flash(mensagem, "sucesso")
        return redirect(url_for("avaliar"))

    return render_template("avaliar.html", avaliacao=avaliacao)


@app.route("/admin/avaliacoes")
@admin_required
def admin_avaliacoes():
    avaliacoes = Avaliacao.query.order_by(Avaliacao.atualizado_em.desc()).all()
    total_avaliacoes = len(avaliacoes)
    media = round(sum(a.estrelas for a in avaliacoes) / total_avaliacoes, 1) if total_avaliacoes else 0
    distribuicao = {nota: 0 for nota in range(1, 6)}
    for item in avaliacoes:
        distribuicao[item.estrelas] += 1

    return render_template(
        "admin_avaliacoes.html",
        avaliacoes=avaliacoes,
        total_avaliacoes=total_avaliacoes,
        media=media,
        distribuicao=distribuicao,
    )


@app.route("/admin/clientes/<int:id>")
@admin_required
def admin_cliente_detalhes(id):
    cliente = Usuario.query.filter_by(id=id, perfil="cliente").first_or_404()
    historico = Agendamento.query.filter_by(usuario_id=cliente.id).order_by(
        Agendamento.data.desc(),
        Agendamento.horario.desc()
    ).all()

    total = len([a for a in historico if a.status != "Cancelado"])
    concluidos = len([a for a in historico if a.status == "Concluído"])
    cancelados = len([a for a in historico if a.status == "Cancelado"])

    return render_template(
        "cliente_detalhes.html",
        cliente=cliente,
        historico=historico,
        total=total,
        concluidos=concluidos,
        cancelados=cancelados,
    )


@app.route("/perfil")
@login_required
def perfil_cliente():
    if session.get("perfil") == "admin":
        return redirect(url_for("admin"))

    usuario = Usuario.query.get_or_404(session["usuario_id"])
    total_agendamentos = Agendamento.query.filter_by(usuario_id=usuario.id).count()
    proximos = Agendamento.query.filter_by(usuario_id=usuario.id).filter(
        Agendamento.status != "Cancelado"
    ).order_by(Agendamento.data.asc(), Agendamento.horario.asc()).limit(3).all()

    return render_template(
        "perfil.html",
        usuario=usuario,
        total_agendamentos=total_agendamentos,
        proximos=proximos,
    )


@app.route("/meu-cadastro", methods=["GET", "POST"])
@login_required
def meu_cadastro():
    if session.get("perfil") == "admin":
        return redirect(url_for("admin"))

    usuario = Usuario.query.get_or_404(session["usuario_id"])

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        email = request.form.get("email", "").strip()

        if not nome or not whatsapp:
            flash("Nome e WhatsApp são obrigatórios.", "erro")
            return redirect(url_for("meu_cadastro"))

        outro = Usuario.query.filter(Usuario.whatsapp == whatsapp, Usuario.id != usuario.id).first()
        if outro:
            flash("Esse WhatsApp já está vinculado a outra conta.", "erro")
            return redirect(url_for("meu_cadastro"))

        if email and ("@" not in email or "." not in email.split("@")[-1]):
            flash("Informe um e-mail válido.", "erro")
            return redirect(url_for("meu_cadastro"))

        foto = request.files.get("foto_perfil")
        if foto and foto.filename:
            tipo = (foto.mimetype or "").lower()
            tipos_permitidos = {"image/jpeg", "image/png", "image/webp"}
            if tipo not in tipos_permitidos:
                flash("A foto precisa ser JPG, PNG ou WEBP.", "erro")
                return redirect(url_for("meu_cadastro"))

            conteudo = foto.read()
            if len(conteudo) > 2 * 1024 * 1024:
                flash("A foto deve ter no máximo 2 MB.", "erro")
                return redirect(url_for("meu_cadastro"))

            usuario.foto_perfil = f"data:{tipo};base64," + base64.b64encode(conteudo).decode("ascii")

        usuario.nome = nome
        usuario.whatsapp = whatsapp
        usuario.email = email or None
        usuario.endereco = request.form.get("endereco", "").strip() or None
        usuario.numero = request.form.get("numero", "").strip() or None
        usuario.complemento = request.form.get("complemento", "").strip() or None
        usuario.bairro = request.form.get("bairro", "").strip() or None
        usuario.cidade = request.form.get("cidade", "").strip() or None

        db.session.commit()
        session["nome"] = usuario.nome
        flash("Cadastro atualizado com sucesso!", "sucesso")
        return redirect(url_for("perfil_cliente"))

    return render_template("meu_cadastro.html", usuario=usuario)


@app.route("/remover-foto-perfil", methods=["POST"])
@login_required
def remover_foto_perfil():
    if session.get("perfil") == "admin":
        return redirect(url_for("admin"))
    usuario = Usuario.query.get_or_404(session["usuario_id"])
    usuario.foto_perfil = None
    db.session.commit()
    flash("Foto de perfil removida.", "sucesso")
    return redirect(url_for("meu_cadastro"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "sucesso")
    return redirect(url_for("inicio"))


@app.route("/agendar", methods=["GET", "POST"])
@login_required
def agendar():
    if session.get("perfil") == "admin":
        return redirect(url_for("admin"))

    if request.method == "POST":
        servico_nome = request.form.get("servico", "")
        data = request.form.get("data", "")
        horario = request.form.get("horario", "")
        observacao = request.form.get("observacao", "").strip()
        forma_pagamento = request.form.get("forma_pagamento", "").strip()
<<<<<<< HEAD
        servico = next((s for s in SERVICOS if s["nome"] == servico_nome), None)
=======

        servico = Servico.query.filter_by(nome=servico_nome).first()

>>>>>>> a4b7643 (Atualiza painel, promocoes, clientes e financeiro)
        horarios_validos = horarios_para_data(data)

        if not servico or not data or horario not in horarios_validos:
            flash("Escolha uma data de terça a sábado e um dos horários disponíveis para esse dia.", "erro")
            return redirect(url_for("agendar"))

        if forma_pagamento not in FORMAS_PAGAMENTO:
            flash("Selecione uma forma de pagamento.", "erro")
            return redirect(url_for("agendar"))

        try:
            data_escolhida = datetime.strptime(data, "%Y-%m-%d").date()
            if data_escolhida < datetime.now().date():
                flash("Não é possível realizar agendamento para uma data passada.", "erro")
                return redirect(url_for("agendar"))
        except ValueError:
            flash("Selecione uma data válida.", "erro")
            return redirect(url_for("agendar"))

        conflito = Agendamento.query.filter_by(data=data, horario=horario).filter(
            Agendamento.status != "Cancelado"
        ).first()
        if conflito:
            flash("Esse horário já foi reservado.", "aviso")
            return redirect(url_for("agendar"))

        promocao_ativa = Promocao.query.filter_by(ativo=True).order_by(Promocao.id.desc()).first()
        valor_final = servico.valor
        valor_original = None
        desconto_aplicado = None
        promocao_titulo = None

        if (
            promocao_ativa
            and promocao_ativa.tipo == "Promoção"
            and promocao_ativa.servico_nome == servico.nome
            and promocao_ativa.valor_promocional
        ):
            original_num = valor_para_float(servico.valor)
            promo_num = valor_para_float(promocao_ativa.valor_promocional)

            if original_num is not None and promo_num is not None and 0 <= promo_num < original_num:
                valor_original = servico.valor
                valor_final = formatar_valor(promo_num)
                desconto_aplicado = formatar_valor(original_num - promo_num)
                promocao_titulo = promocao_ativa.titulo

        novo = Agendamento(
            usuario_id=session["usuario_id"],
            servico=servico.nome,
            valor=valor_final,
            valor_original=valor_original,
            desconto_aplicado=desconto_aplicado,
            promocao_titulo=promocao_titulo,
            data=data,
            horario=horario,
            observacao=observacao,
            forma_pagamento=forma_pagamento,
        )
        db.session.add(novo)
        db.session.commit()
        flash("Agendamento realizado com sucesso!", "sucesso")

        usuario = Usuario.query.get(session["usuario_id"])
        nome_cliente = usuario.nome if usuario else session.get("nome", "Cliente")
        data_formatada = data
        try:
            data_formatada = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            pass

        mensagem_whatsapp = (
            "Olá Laura! Acabei de realizar um agendamento pelo site.\n\n"
            f"Cliente: {nome_cliente}\n"
            f"Serviço: {servico.nome}\n"
            f"Valor final: {valor_final}\n"
            + (f"Preço original: {valor_original}\nDesconto aplicado: {desconto_aplicado}\nPromoção: {promocao_titulo}\n" if desconto_aplicado else "")
            + f"Data: {data_formatada}\n"
            f"Horário: {horario}\n"
            f"Forma de pagamento: {forma_pagamento}\n"
        )
        if observacao:
            mensagem_whatsapp += f"Observação: {observacao}\n"
        mensagem_whatsapp += "\nAgendamento registrado no site Laura Silva Nail Designer."

        whatsapp_url = "https://wa.me/5581983066312?text=" + quote(mensagem_whatsapp)
        return redirect(whatsapp_url)

    ocupados = [
        {"data": a.data, "horario": a.horario}
        for a in Agendamento.query.filter(Agendamento.status != "Cancelado").all()
    ]

    return render_template(
        "agendar.html",
        servicos=obter_servicos(),
        horarios_padrao=HORARIOS_PADRAO,
        horarios_quinta=HORARIOS_QUINTA,
        formas_pagamento=FORMAS_PAGAMENTO,
        ocupados=ocupados,
        promocao=Promocao.query.filter_by(ativo=True).order_by(Promocao.id.desc()).first(),
        servico_selecionado=request.args.get("servico", ""),
    )


@app.route("/meus-agendamentos")
@login_required
def meus_agendamentos():
    if session.get("perfil") == "admin":
        return redirect(url_for("admin"))

    itens = Agendamento.query.filter_by(usuario_id=session["usuario_id"]).order_by(
        Agendamento.data.asc(), Agendamento.horario.asc()
    ).all()
    return render_template("meus_agendamentos.html", agendamentos=itens)


@app.route("/cancelar/<int:id>", methods=["POST"])
@login_required
def cancelar(id):
    item = Agendamento.query.get_or_404(id)
    if session.get("perfil") != "admin" and item.usuario_id != session["usuario_id"]:
        flash("Você não pode alterar esse agendamento.", "erro")
        return redirect(url_for("meus_agendamentos"))

    item.status = "Cancelado"
    db.session.commit()
    flash("Agendamento cancelado.", "sucesso")
    return redirect(url_for("admin" if session.get("perfil") == "admin" else "meus_agendamentos"))


@app.route("/admin")
@admin_required
def admin():
<<<<<<< HEAD
    itens = Agendamento.query.order_by(Agendamento.data.desc(), Agendamento.horario.desc()).all()
=======
    # A tela principal mostra somente agendamentos que ainda fazem parte da operação.
    # Cancelados ficam exclusivamente no histórico de cancelamentos.
    itens = Agendamento.query.filter(
        Agendamento.status != "Cancelado"
    ).order_by(
        Agendamento.data.desc(),
        Agendamento.horario.desc()
    ).all()

>>>>>>> a4b7643 (Atualiza painel, promocoes, clientes e financeiro)
    clientes = Usuario.query.filter_by(perfil="cliente").all()
    resumo_clientes = []

    for cliente in clientes:
        historico = Agendamento.query.filter_by(usuario_id=cliente.id).order_by(
            Agendamento.data.desc(), Agendamento.horario.desc()
        ).all()
        validos = [a for a in historico if a.status != "Cancelado"]
        concluidos_cliente = [a for a in validos if a.status == "Concluído"]

        if validos:
            ultimo = validos[0]
            resumo_clientes.append({
                "id": cliente.id,
                "nome": cliente.nome,
                "whatsapp": cliente.whatsapp,
                "total": len(validos),
                "concluidos": len(concluidos_cliente),
                "ultimo_servico": ultimo.servico,
                "ultima_data": ultimo.data,
            })

    resumo_clientes.sort(key=lambda c: (c["total"], c["concluidos"]), reverse=True)
    cliente_top = resumo_clientes[0] if resumo_clientes and resumo_clientes[0]["total"] > 0 else None

    # Ganhos: entram apenas os agendamentos marcados como Concluído.
    ganhos_por_mes = {}
    meses_pt = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
    }

    concluidos_lista = Agendamento.query.filter_by(status="Concluído").all()
    for item in concluidos_lista:
        try:
            data_obj = datetime.strptime(item.data, "%Y-%m-%d")
        except (TypeError, ValueError):
            continue

        valor_num = valor_para_float(item.valor)
        if valor_num is None:
            continue

        chave = data_obj.strftime("%Y-%m")
        if chave not in ganhos_por_mes:
            ganhos_por_mes[chave] = {
                "chave": chave,
                "ano": data_obj.year,
                "mes_num": data_obj.month,
                "total": 0.0,
                "quantidade": 0,
            }

        ganhos_por_mes[chave]["total"] += valor_num
        ganhos_por_mes[chave]["quantidade"] += 1

    ganhos_mensais = []
    for chave in sorted(ganhos_por_mes.keys(), reverse=True):
        item = ganhos_por_mes[chave]
        ganhos_mensais.append({
            "chave": chave,
            "label": f"{meses_pt[item['mes_num']]} de {item['ano']}",
            "total": formatar_valor(item["total"]),
            "quantidade": item["quantidade"],
        })

    mes_atual = datetime.now().strftime("%Y-%m")
    ganho_mes_atual_num = ganhos_por_mes.get(mes_atual, {}).get("total", 0.0)
    concluidos_mes_atual = ganhos_por_mes.get(mes_atual, {}).get("quantidade", 0)

    return render_template(
        "admin.html",
        agendamentos=itens,
        resumo_clientes=resumo_clientes,
        cliente_top=cliente_top,
        total=Agendamento.query.filter(Agendamento.status != "Cancelado").count(),
        agendados=Agendamento.query.filter_by(status="Agendado").count(),
        confirmados=Agendamento.query.filter_by(status="Confirmado").count(),
        concluidos=Agendamento.query.filter_by(status="Concluído").count(),
        total_clientes=Usuario.query.filter_by(perfil="cliente").count(),
        ganho_mes_atual=formatar_valor(ganho_mes_atual_num),
        concluidos_mes_atual=concluidos_mes_atual,
        ganhos_mensais=ganhos_mensais,
    )


@app.route("/admin/cancelamentos")
@admin_required
def admin_cancelamentos():
    cancelados = Agendamento.query.filter_by(status="Cancelado").order_by(
        Agendamento.data.desc(),
        Agendamento.horario.desc()
    ).all()

    return render_template(
        "admin_cancelamentos.html",
        cancelados=cancelados,
        total_cancelados=len(cancelados),
    )


@app.route("/admin/promocao", methods=["GET", "POST"])
@admin_required
def admin_promocao():
    promocao = Promocao.query.order_by(Promocao.id.desc()).first()

    if request.method == "POST":
        acao = request.form.get("acao", "salvar").strip()

        if acao == "remover":
            if promocao:
                db.session.delete(promocao)
                db.session.commit()
                flash("Promoção/aviso removido do site com sucesso.", "sucesso")
            else:
                flash("Não há promoção/aviso ativo para remover.", "aviso")
            return redirect(url_for("admin_promocao"))

        tipo = request.form.get("tipo", "Promoção").strip()
        titulo = request.form.get("titulo", "").strip()
        mensagem = request.form.get("mensagem", "").strip()
        servico_nome = request.form.get("servico_nome", "").strip()
        valor_promocional_informado = request.form.get("valor_promocional", "").strip()
        ativo = request.form.get("ativo") == "on"

        if tipo not in ["Promoção", "Aviso", "Novidade"]:
            tipo = "Promoção"

        if not titulo or not mensagem:
            flash("Informe o título e a mensagem.", "erro")
            return redirect(url_for("admin_promocao"))

        valor_promocional = None
        if tipo == "Promoção":
            servico = Servico.query.filter_by(nome=servico_nome).first()
            promo_num = valor_para_float(valor_promocional_informado)
            original_num = valor_para_float(servico.valor) if servico else None

            if not servico or promo_num is None or promo_num < 0:
                flash("Para uma promoção, selecione o serviço e informe um preço promocional válido.", "erro")
                return redirect(url_for("admin_promocao"))

            if original_num is None or promo_num >= original_num:
                flash("O preço promocional precisa ser menor que o preço normal do serviço.", "erro")
                return redirect(url_for("admin_promocao"))

            valor_promocional = formatar_valor(promo_num)
        else:
            servico_nome = None

        if promocao is None:
            promocao = Promocao(
                tipo=tipo,
                titulo=titulo,
                mensagem=mensagem,
                servico_nome=servico_nome or None,
                valor_promocional=valor_promocional,
                ativo=ativo,
            )
            db.session.add(promocao)
        else:
            promocao.tipo = tipo
            promocao.titulo = titulo
            promocao.mensagem = mensagem
            promocao.servico_nome = servico_nome or None
            promocao.valor_promocional = valor_promocional
            promocao.ativo = ativo
            promocao.atualizado_em = datetime.utcnow()

        db.session.commit()
        flash("Promoção/aviso atualizado com sucesso.", "sucesso")
        return redirect(url_for("admin_promocao"))

    return render_template("admin_promocao.html", promocao=promocao, servicos=obter_servicos())


@app.route("/admin/servicos", methods=["GET", "POST"])
@admin_required
def admin_servicos():
    servicos = obter_servicos()

    if request.method == "POST":
        servico_id = request.form.get("servico_id", type=int)
        valor = request.form.get("valor", "").strip()

        servico = Servico.query.get_or_404(servico_id)

        # Aceita "100", "100,00" ou "R$ 100,00" e mantém o padrão visual do site.
        valor_limpo = valor.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
        try:
            numero = float(valor_limpo)
            if numero < 0:
                raise ValueError
        except ValueError:
            flash("Informe um preço válido.", "erro")
            return redirect(url_for("admin_servicos"))

        servico.valor = f"R$ {numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        db.session.commit()
        flash(f"Preço de {servico.nome} atualizado com sucesso.", "sucesso")
        return redirect(url_for("admin_servicos"))

    return render_template("admin_servicos.html", servicos=servicos)


@app.route("/admin/status/<int:id>", methods=["POST"])
@admin_required
def admin_status(id):
    item = Agendamento.query.get_or_404(id)
    status = request.form.get("status", "")
    if status in ["Agendado", "Confirmado", "Concluído", "Cancelado"]:
        item.status = status
        db.session.commit()
        flash("Status atualizado.", "sucesso")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        garantir_coluna_forma_pagamento()
        garantir_colunas_usuario()
        garantir_colunas_promocao()
        garantir_colunas_promocao_agendamento()
        criar_admin()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
