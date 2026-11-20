import os
import base64
import re
import secrets
from zoneinfo import ZoneInfo
from datetime import datetime
from functools import wraps
from threading import Lock
from urllib.parse import quote

from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client import OAuthError
from joserfc.errors import JoseError
from requests.exceptions import RequestException
from sqlalchemy.exc import IntegrityError
from flask import abort, jsonify, Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect, text

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")))
RECIFE = ZoneInfo("America/Recife")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI")
GOOGLE_ENABLED = all(os.environ.get(key) for key in (
    "SECRET_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"
))
oauth = OAuth(app)
if GOOGLE_ENABLED:
    oauth.register(
        name="google",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
    )

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


class ContaGoogle(db.Model):
    subject = db.Column(db.String(255), primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), unique=True, nullable=False)
    usuario = db.relationship("Usuario")


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


class Servico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), unique=True, nullable=False)
    valor = db.Column(db.String(30), nullable=False)


SERVICOS_PADRAO = [
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


class Avaliacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), unique=True, nullable=False)
    estrelas = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.String(1000))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    cliente = db.relationship("Usuario", backref=db.backref("avaliacao", uselist=False))


HORARIOS_PADRAO = ["09:00", "11:30", "14:00", "16:30", "18:00", "20:00"]
HORARIOS_QUINTA = ["09:00", "14:00", "16:30", "18:00", "20:00"]
FORMAS_PAGAMENTO = ["Cartão de crédito", "Cartão de débito", "Pix", "Dinheiro"]


def horarios_para_data(data_str):
    """Retorna os horários permitidos para a data escolhida."""
    try:
        data_obj = datetime.strptime(data_str, "%Y-%m-%d")
    except ValueError:
        return []

    if data_obj.strftime("%Y-%m-%d") != data_str:
        return []

    # Python: segunda=0, terça=1, quarta=2, quinta=3, sexta=4, sábado=5, domingo=6
    dia_semana = data_obj.weekday()

    # Atendimento somente de terça a sábado.
    if dia_semana not in [1, 2, 3, 4, 5]:
        return []

    # Quinta-feira não possui o horário das 11:30.
    if dia_semana == 3:
        return HORARIOS_QUINTA

    return HORARIOS_PADRAO


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("usuario_id"):
            if request.endpoint == "agendar":
                session["agendar_apos_login"] = request.args.get("servico", "")[:120]
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



COLUNAS_LEGADAS = {
    "agendamento": {
        "forma_pagamento": "VARCHAR(30)",
        "valor_original": "VARCHAR(30)",
        "desconto_aplicado": "VARCHAR(30)",
        "promocao_titulo": "VARCHAR(120)",
    },
    "promocao": {
        "servico_nome": "VARCHAR(120)",
        "valor_promocional": "VARCHAR(30)",
    },
    "usuario": {
        "email": "VARCHAR(160)",
        "endereco": "VARCHAR(180)",
        "numero": "VARCHAR(30)",
        "complemento": "VARCHAR(120)",
        "bairro": "VARCHAR(120)",
        "cidade": "VARCHAR(120)",
        "foto_perfil": "TEXT",
    },
}

banco_pronto = False
banco_lock = Lock()


def criar_admin(conexao):
    admin_user = os.environ.get("ADMIN_USER", "laura.laura")
    admin_password = os.environ.get("ADMIN_PASSWORD")

    if admin_password:
        tabela = Usuario.__table__
        existente = conexao.execute(
            tabela.select().with_only_columns(tabela.c.id).where(tabela.c.whatsapp == admin_user)
        ).first()
        if not existente:
            conexao.execute(tabela.insert().values(
                nome="Laura Silva",
                whatsapp=admin_user,
                senha_hash=generate_password_hash(admin_password),
                perfil="admin",
            ))


@app.before_request
def garantir_banco():
    global banco_pronto

    if banco_pronto or request.endpoint in (None, "static"):
        return
    with banco_lock:
        if banco_pronto:
            return
        with db.engine.begin() as conexao:
            if conexao.dialect.name == "postgresql":
                conexao.execute(text("SELECT pg_advisory_xact_lock(708543122)"))
            elif conexao.dialect.name == "sqlite":
                conexao.execute(text("BEGIN IMMEDIATE"))

            db.metadata.create_all(bind=conexao)
            inspetor = inspect(conexao)
            for tabela, novas_colunas in COLUNAS_LEGADAS.items():
                colunas = {coluna["name"] for coluna in inspetor.get_columns(tabela)}
                for nome, tipo in novas_colunas.items():
                    if nome not in colunas:
                        conexao.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}"))
            criar_admin(conexao)
        banco_pronto = True


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

        return entrar_com_usuario(usuario)

    return render_template("cadastro.html")


def entrar_com_usuario(usuario):
    servico = session.get("agendar_apos_login")
    session.clear()
    session.update(usuario_id=usuario.id, nome=usuario.nome, perfil=usuario.perfil)
    if usuario.perfil == "admin":
        return redirect(url_for("admin"))
    if servico is not None:
        return redirect(url_for("agendar", servico=servico or None))
    return redirect(url_for("meus_agendamentos"))


@app.context_processor
def contexto_acesso():
    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    return {"google_enabled": GOOGLE_ENABLED, "csrf_token": csrf_token}


@app.before_request
def validar_csrf():
    if request.method == "POST" and request.endpoint in {
        "login", "cadastro", "google_vincular", "google_completar", "agendar", "cancelar"
    }:
        esperado = session.get("csrf_token")
        recebido = request.form.get("csrf_token", "")
        if not esperado or not secrets.compare_digest(esperado.encode(), recebido.encode()):
            abort(400)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        whatsapp = request.form.get("whatsapp", "").strip()
        senha = request.form.get("senha", "")

        usuario = Usuario.query.filter_by(whatsapp=whatsapp).first()
        if not usuario or not check_password_hash(usuario.senha_hash, senha):
            flash("Usuário ou senha inválidos.", "erro")
            return redirect(url_for("login"))

        return entrar_com_usuario(usuario)

    return render_template("login.html")


@app.get("/login/google")
def google_login():
    if not GOOGLE_ENABLED:
        abort(404)
    if session.get("usuario_id"):
        return redirect(url_for("perfil_cliente"))
    session.pop("google_pendente", None)
    return iniciar_google("entrar")


@app.post("/perfil/vincular-google")
@login_required
def google_vincular():
    if not GOOGLE_ENABLED:
        abort(404)
    usuario = db.session.get(Usuario, session["usuario_id"])
    if not usuario or usuario.perfil != "cliente":
        abort(403)
    return iniciar_google("vincular", usuario.id)


def iniciar_google(modo, usuario_id=None):
    state = secrets.token_urlsafe(32)
    try:
        resposta = oauth.google.authorize_redirect(GOOGLE_REDIRECT_URI, state=state, prompt="select_account")
    except (OAuthError, RequestException):
        flash("O login com Google está indisponível. Tente novamente.", "aviso")
        return redirect(url_for("perfil_cliente" if modo == "vincular" else "login"))
    session["google_fluxo"] = {"modo": modo, "usuario_id": usuario_id, "state": state}
    return resposta


@app.get("/login/google/callback")
def google_callback():
    if not GOOGLE_ENABLED:
        abort(404)
    fluxo = session.get("google_fluxo")
    if not fluxo or fluxo["state"] != request.args.get("state"):
        return redirect(url_for("login"))
    session.pop("google_fluxo")
    try:
        token = oauth.google.authorize_access_token()
        identidade = token.get("userinfo") or {}
        subject = identidade.get("sub")
        email = identidade.get("email", "")
        if not subject or len(subject) > 255 or not email or len(email) > 160 or identidade.get("email_verified") is not True:
            raise OAuthError(error="invalid_userinfo")
    except (OAuthError, JoseError, RequestException):
        flash("Não foi possível entrar com o Google. Tente novamente.", "aviso")
        return redirect(url_for("perfil_cliente" if fluxo["modo"] == "vincular" else "login"))

    conta = db.session.get(ContaGoogle, subject)
    if fluxo["modo"] == "vincular":
        usuario = db.session.get(Usuario, fluxo["usuario_id"])
        if not usuario or usuario.perfil != "cliente" or usuario.id != session.get("usuario_id"):
            abort(403)
        if conta and conta.usuario_id == usuario.id:
            flash("Google já vinculado à sua conta.", "sucesso")
            return redirect(url_for("perfil_cliente"))
        db.session.add(ContaGoogle(subject=subject, usuario_id=usuario.id))
        try:
            db.session.commit()
            flash("Google vinculado à sua conta.", "sucesso")
        except IntegrityError:
            db.session.rollback()
            flash("Uma das contas já tem um vínculo com o Google.", "aviso")
        return redirect(url_for("perfil_cliente"))

    if session.get("usuario_id"):
        return redirect(url_for("perfil_cliente"))
    if conta:
        if conta.usuario.perfil != "cliente":
            abort(403)
        return entrar_com_usuario(conta.usuario)

    session["google_pendente"] = {
        "subject": subject,
        "email": email,
        "nome": (identidade.get("name") or "")[:120],
        "expira": int(datetime.now(RECIFE).timestamp()) + 600,
    }
    return redirect(url_for("google_completar"))


@app.route("/login/google/completar", methods=["GET", "POST"])
def google_completar():
    if not GOOGLE_ENABLED:
        abort(404)
    if session.get("usuario_id"):
        return redirect(url_for("perfil_cliente"))
    dados = session.get("google_pendente")
    if not dados or dados["expira"] <= datetime.now(RECIFE).timestamp():
        session.pop("google_pendente", None)
        return redirect(url_for("login"))
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        digitos = re.sub(r"\D", "", whatsapp)
        if not nome or len(nome) > 120 or len(whatsapp) > 40 or not re.fullmatch(r"(?:55)?[1-9][0-9]{9,10}", digitos):
            flash("Informe seu nome e um WhatsApp com DDD.", "aviso")
            return render_template("google_completar.html", dados=dados, whatsapp=whatsapp), 400

        numero_local = digitos[2:] if len(digitos) in (12, 13) else digitos
        existentes = Usuario.query.with_entities(Usuario.whatsapp).filter_by(perfil="cliente")
        if any(re.sub(r"\D", "", numero) in {numero_local, "55" + numero_local} for (numero,) in existentes):
            flash("Este WhatsApp já tem cadastro. Entre com sua senha e vincule o Google no perfil.", "aviso")
            return redirect(url_for("login"))

        usuario = Usuario(
            nome=nome, whatsapp=numero_local, email=dados["email"],
            senha_hash=generate_password_hash(secrets.token_urlsafe(32)), perfil="cliente",
        )
        db.session.add(usuario)
        try:
            db.session.flush()
            db.session.add(ContaGoogle(subject=dados["subject"], usuario_id=usuario.id))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Já existe um cadastro com esses dados. Entre na sua conta para continuar.", "aviso")
            return redirect(url_for("login"))
        return entrar_com_usuario(usuario)

    return render_template("google_completar.html", dados=dados)


@app.route("/redefinir-senha", methods=["GET", "POST"])
@app.route("/esqueci-senha", methods=["GET", "POST"])
def esqueci_senha():
    session.pop("redefinir_usuario_id", None)
    return render_template("esqueci_senha.html")


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
            Agendamento.data.desc(),
            Agendamento.horario.desc()
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

    return render_template(
        "clientes.html",
        clientes=lista,
        total_clientes=len(lista),
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
        google_vinculado=ContaGoogle.query.filter_by(usuario_id=usuario.id).first() is not None,
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


def agora_recife():
    return datetime.now(RECIFE).strftime("%Y-%m-%d %H:%M")


def bloquear_agenda():
    # Serializa alterações que podem ocupar um horário, mesmo entre workers.
    if db.engine.dialect.name == "postgresql":
        db.session.execute(text("SELECT pg_advisory_xact_lock(708543121)"))
    elif db.engine.dialect.name == "sqlite":
        db.session.execute(text("BEGIN IMMEDIATE"))


def horario_ocupado(data, horario, exceto=None):
    consulta = Agendamento.query.filter_by(data=data, horario=horario).filter(
        Agendamento.status != "Cancelado"
    )
    if exceto is not None:
        consulta = consulta.filter(Agendamento.id != exceto)
    return consulta.first() is not None


@app.get("/agendar/horarios")
@login_required
def horarios_disponiveis():
    data = request.args.get("data", "")
    permitidos = horarios_para_data(data)
    if not permitidos:
        return jsonify(horarios=[])
    agora = agora_recife()
    ocupados = {horario for (horario,) in db.session.query(Agendamento.horario).filter(
        Agendamento.data == data, Agendamento.status != "Cancelado"
    )}
    resposta = jsonify(horarios=[
        hora for hora in permitidos
        if f"{data} {hora}" > agora and hora not in ocupados
    ])
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


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

        bloquear_agenda()
        servico = Servico.query.filter_by(nome=servico_nome).first()

        horarios_validos = horarios_para_data(data)

        if not servico or not data or horario not in horarios_validos:
            flash(
                "Escolha uma data de terça a sábado e um dos horários disponíveis para esse dia.",
                "erro"
            )
            return redirect(url_for("agendar"))

        if forma_pagamento not in FORMAS_PAGAMENTO:
            flash("Selecione uma forma de pagamento.", "erro")
            return redirect(url_for("agendar"))

        if f"{data} {horario}" <= agora_recife():
            flash("Escolha um horário futuro.", "erro")
            return redirect(url_for("agendar", servico=servico_nome))

        if horario_ocupado(data, horario):
            flash("Esse horário já foi reservado. Escolha outro horário.", "aviso")
            return redirect(url_for("agendar", servico=servico_nome))

        if len(observacao) > 500:
            flash("A observação pode ter até 500 caracteres.", "aviso")
            return redirect(url_for("agendar", servico=servico_nome))

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

        return redirect(url_for("meus_agendamentos", reserva=novo.id))

    return render_template(
        "agendar.html",
        servicos=obter_servicos(),
        hoje=agora_recife()[:10],
        formas_pagamento=FORMAS_PAGAMENTO,
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
    agora = agora_recife()
    proximos = [
        item for item in itens
        if item.status in ("Agendado", "Confirmado") and f"{item.data} {item.horario}" > agora
    ]
    historico = [item for item in reversed(itens) if item not in proximos]
    reserva_id = request.args.get("reserva", type=int)
    reserva = next((item for item in proximos if item.id == reserva_id), None)
    whatsapp_url = None
    if reserva:
        data = "/".join(reversed(reserva.data.split("-")))
        mensagem = (
            f"Olá Laura! Agendei {reserva.servico} pelo site para {data} às {reserva.horario}. "
            f"Meu nome é {session['nome']}."
        )
        whatsapp_url = "https://wa.me/5581983066312?text=" + quote(mensagem)
    return render_template(
        "meus_agendamentos.html", proximos=proximos, historico=historico, whatsapp_url=whatsapp_url
    )


@app.route("/cancelar/<int:id>", methods=["POST"])
@login_required
def cancelar(id):
    item = Agendamento.query.get_or_404(id)
    if session.get("perfil") != "admin" and item.usuario_id != session["usuario_id"]:
        flash("Você não pode alterar esse agendamento.", "erro")
        return redirect(url_for("meus_agendamentos"))

    if session.get("perfil") != "admin" and (
        item.status not in ("Agendado", "Confirmado") or f"{item.data} {item.horario}" <= agora_recife()
    ):
        flash("Esse horário já está no histórico.", "aviso")
        return redirect(url_for("meus_agendamentos"))

    item.status = "Cancelado"
    db.session.commit()
    flash("Agendamento cancelado.", "sucesso")
    return redirect(url_for("admin" if session.get("perfil") == "admin" else "meus_agendamentos"))


@app.route("/admin")
@admin_required
def admin():
    # A tela principal mostra somente agendamentos que ainda fazem parte da operação.
    # Cancelados ficam exclusivamente no histórico de cancelamentos.
    itens = Agendamento.query.filter(
        Agendamento.status != "Cancelado"
    ).order_by(
        Agendamento.data.desc(),
        Agendamento.horario.desc()
    ).all()

    clientes = Usuario.query.filter_by(perfil="cliente").all()
    resumo_clientes = []

    for cliente in clientes:
        historico = Agendamento.query.filter_by(usuario_id=cliente.id).order_by(
            Agendamento.data.desc(),
            Agendamento.horario.desc()
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


@app.route("/avaliar", methods=["GET", "POST"])
@login_required
def avaliar():
    if session.get("perfil") == "admin":
        return redirect(url_for("admin_avaliacoes"))

    usuario_id = session["usuario_id"]
    avaliacao = Avaliacao.query.filter_by(usuario_id=usuario_id).first()

    if request.method == "POST":
        estrelas = request.form.get("estrelas", type=int)
        comentario = request.form.get("comentario", "").strip()

        if estrelas not in [1, 2, 3, 4, 5]:
            flash("Escolha uma nota de 1 a 5 estrelas.", "erro")
            return redirect(url_for("avaliar"))

        if avaliacao is None:
            avaliacao = Avaliacao(
                usuario_id=usuario_id,
                estrelas=estrelas,
                comentario=comentario or None,
            )
            db.session.add(avaliacao)
            mensagem = "Avaliação enviada com sucesso. Obrigado pelo feedback!"
        else:
            avaliacao.estrelas = estrelas
            avaliacao.comentario = comentario or None
            avaliacao.atualizado_em = datetime.utcnow()
            mensagem = "Avaliação atualizada com sucesso."

        db.session.commit()
        flash(mensagem, "sucesso")
        return redirect(url_for("avaliar"))

    return render_template("avaliar.html", avaliacao=avaliacao)


@app.route("/admin/avaliacoes")
@admin_required
def admin_avaliacoes():
    avaliacoes = Avaliacao.query.order_by(Avaliacao.atualizado_em.desc()).all()
    total_avaliacoes = len(avaliacoes)

    if total_avaliacoes:
        media = round(sum(item.estrelas for item in avaliacoes) / total_avaliacoes, 1)
    else:
        media = 0

    distribuicao = {nota: 0 for nota in range(1, 6)}
    for item in avaliacoes:
        if item.estrelas in distribuicao:
            distribuicao[item.estrelas] += 1

    return render_template(
        "admin_avaliacoes.html",
        avaliacoes=avaliacoes,
        total_avaliacoes=total_avaliacoes,
        media=media,
        distribuicao=distribuicao,
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
    bloquear_agenda()
    item = Agendamento.query.get_or_404(id)
    status = request.form.get("status", "")
    if status in ["Agendado", "Confirmado", "Concluído", "Cancelado"]:
        if item.status == "Cancelado" and status != "Cancelado" and horario_ocupado(item.data, item.horario, item.id):
            flash("Outro atendimento já ocupa esse horário.", "aviso")
            return redirect(url_for("admin"))
        item.status = status
        db.session.commit()
        flash("Status atualizado.", "sucesso")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
