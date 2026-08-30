import os
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
    status = db.Column(db.String(30), default="Agendado", nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    cliente = db.relationship("Usuario", backref="agendamentos")


class Avaliacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), unique=True, nullable=False)
    estrelas = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.String(1000))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    cliente = db.relationship("Usuario", backref=db.backref("avaliacao", uselist=False))


SERVICOS = [
    {"nome": "Unha em gel na tips", "valor": "R$ 90,00"},
    {"nome": "Banho de gel", "valor": "R$ 85,00"},
    {"nome": "Postiça realista", "valor": "R$ 50,00"},
    {"nome": "Esmaltação em gel", "valor": "R$ 45,00"},
    {"nome": "Pé e mão", "valor": "R$ 40,00"},
    {"nome": "Só o pé ou a mão", "valor": "R$ 25,00"},
    {"nome": "Manutenção - unha em gel", "valor": "R$ 85,00"},
    {"nome": "Manutenção - banho de gel", "valor": "R$ 80,00"},
]

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
    criar_admin()


@app.route("/")
def inicio():
    return render_template("index.html", servicos=SERVICOS)


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
        flash("Conta criada com sucesso.", "sucesso")
        return redirect(url_for("login"))

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
        return redirect(url_for("admin" if usuario.perfil == "admin" else "agendar"))

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
        servico = next((s for s in SERVICOS if s["nome"] == servico_nome), None)
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

        novo = Agendamento(
            usuario_id=session["usuario_id"],
            servico=servico["nome"],
            valor=servico["valor"],
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
            f"Serviço: {servico['nome']}\n"
            f"Data: {data_formatada}\n"
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
        servicos=SERVICOS,
        horarios_padrao=HORARIOS_PADRAO,
        horarios_quinta=HORARIOS_QUINTA,
        formas_pagamento=FORMAS_PAGAMENTO,
        ocupados=ocupados,
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
    itens = Agendamento.query.order_by(Agendamento.data.desc(), Agendamento.horario.desc()).all()
    clientes = Usuario.query.filter_by(perfil="cliente").all()
    resumo_clientes = []

    for cliente in clientes:
        historico = Agendamento.query.filter_by(usuario_id=cliente.id).order_by(
            Agendamento.data.desc(), Agendamento.horario.desc()
        ).all()
        validos = [a for a in historico if a.status != "Cancelado"]
        concluidos_cliente = [a for a in historico if a.status == "Concluído"]
        cancelados_cliente = [a for a in historico if a.status == "Cancelado"]

        if historico:
            ultimo = historico[0]
            resumo_clientes.append({
                "id": cliente.id,
                "nome": cliente.nome,
                "whatsapp": cliente.whatsapp,
                "total": len(validos),
                "concluidos": len(concluidos_cliente),
                "cancelados": len(cancelados_cliente),
                "ultimo_servico": ultimo.servico,
                "ultima_data": ultimo.data,
            })

    resumo_clientes.sort(key=lambda c: (c["total"], c["concluidos"]), reverse=True)
    cliente_top = resumo_clientes[0] if resumo_clientes and resumo_clientes[0]["total"] > 0 else None

    return render_template(
        "admin.html",
        agendamentos=itens,
        resumo_clientes=resumo_clientes,
        cliente_top=cliente_top,
        total=Agendamento.query.count(),
        agendados=Agendamento.query.filter_by(status="Agendado").count(),
        confirmados=Agendamento.query.filter_by(status="Confirmado").count(),
        concluidos=Agendamento.query.filter_by(status="Concluído").count(),
        total_clientes=Usuario.query.filter_by(perfil="cliente").count(),
    )


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
        criar_admin()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
