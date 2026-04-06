from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
import sqlite3

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "familia123"
USUARIO_ADMIN = "Gabi"
CRIANCAS = {"Mayumi", "Akira", "Kenji"}
DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
RECORRENCIAS = ["todos_os_dias", "segunda_a_sexta", "dias_escolhidos"]
RECOMPENSAS = {
    "jogo_familia": {"nome": "Escolher um jogo em família", "pontos": 200},
    "lanche_cantina": {"nome": "Comer lanche da cantina da escola", "pontos": 800},
}



def conectar():
    conn = sqlite3.connect("familia.db")
    conn.row_factory = sqlite3.Row
    return conn



def garantir_coluna(cur, tabela, coluna, definicao):
    cur.execute(f"PRAGMA table_info({tabela})")
    colunas = {linha[1] for linha in cur.fetchall()}
    if coluna not in colunas:
        cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")



def criar_banco():
    conn = conectar()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE,
            senha TEXT,
            pontuacao INTEGER DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            horario TEXT,
            concluida INTEGER DEFAULT 0,
            usuario TEXT,
            dias_semana TEXT DEFAULT '',
            pontos INTEGER DEFAULT 1,
            recorrencia TEXT DEFAULT 'todos_os_dias',
            ultima_conclusao_data TEXT DEFAULT ''
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS medicacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            horario TEXT,
            tomado INTEGER DEFAULT 0,
            usuario TEXT,
            recorrencia TEXT DEFAULT 'todos_os_dias',
            dias_semana TEXT DEFAULT '',
            ultima_tomada_data TEXT DEFAULT ''
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trocas_recompensas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            recompensa TEXT,
            pontos_gastos INTEGER,
            data_troca TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS eventos_habitos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            tipo TEXT,
            referencia_id INTEGER,
            data_evento TEXT,
            UNIQUE(usuario, tipo, referencia_id, data_evento)
        )
        """
    )

    garantir_coluna(cur, "usuarios", "pontuacao", "INTEGER DEFAULT 0")
    garantir_coluna(cur, "tarefas", "dias_semana", "TEXT DEFAULT ''")
    garantir_coluna(cur, "tarefas", "pontos", "INTEGER DEFAULT 1")
    garantir_coluna(cur, "tarefas", "recorrencia", "TEXT DEFAULT 'todos_os_dias'")
    garantir_coluna(cur, "tarefas", "ultima_conclusao_data", "TEXT DEFAULT ''")
    garantir_coluna(cur, "medicacoes", "recorrencia", "TEXT DEFAULT 'todos_os_dias'")
    garantir_coluna(cur, "medicacoes", "dias_semana", "TEXT DEFAULT ''")
    garantir_coluna(cur, "medicacoes", "ultima_tomada_data", "TEXT DEFAULT ''")

    usuarios = [
        ("Gabi", "1234"),
        ("Leonardo", "1234"),
        ("Mayumi", "1234"),
        ("Akira", "1234"),
        ("Kenji", "1234"),
    ]

    for nome, senha in usuarios:
        cur.execute("INSERT OR IGNORE INTO usuarios (nome, senha) VALUES (?, ?)", (nome, senha))

    medicacoes = [
        ("Carbonato de Lítio", "08:00", "Gabi"),
        ("Okralin", "08:00", "Gabi"),
        ("Moringa com Lugol - 2 gotas", "08:00", "Gabi"),
        ("Carbonato de Lítio", "20:00", "Gabi"),
        ("Glifage XR 500", "08:00", "Leonardo"),
        ("Rosuvastatina Cálcica", "08:00", "Leonardo"),
        ("Aradois", "08:00", "Leonardo"),
        ("Selozok", "08:00", "Leonardo"),
        ("Wellbutrin", "08:00", "Leonardo"),
    ]

    for nome, horario, usuario in medicacoes:
        cur.execute(
            "INSERT OR IGNORE INTO medicacoes (nome, horario, usuario, recorrencia) VALUES (?, ?, ?, 'todos_os_dias')",
            (nome, horario, usuario),
        )

    conn.commit()
    conn.close()


criar_banco()



def usuario_logado():
    return session.get("usuario")



def eh_admin():
    return usuario_logado() == USUARIO_ADMIN



def eh_crianca(nome):
    return nome in CRIANCAS



def login_obrigatorio(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not usuario_logado():
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return wrapper



def admin_obrigatorio(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not eh_admin():
            return redirect(url_for("tarefas"))
        return func(*args, **kwargs)

    return wrapper



def hoje_sigla():
    return DIAS_SEMANA[datetime.now().weekday()]



def hoje_data_iso():
    return datetime.now().strftime("%Y-%m-%d")



def parse_horario(horario):
    try:
        return datetime.strptime(horario, "%H:%M").time()
    except (TypeError, ValueError):
        return None



def lista_dias(dias_texto):
    return [d.strip() for d in (dias_texto or "").split(",") if d.strip()]



def agendado_hoje(recorrencia, dias_semana_texto, dia_atual):
    if recorrencia == "segunda_a_sexta":
        return dia_atual in {"Seg", "Ter", "Qua", "Qui", "Sex"}
    if recorrencia == "dias_escolhidos":
        dias = lista_dias(dias_semana_texto)
        return dia_atual in dias
    if recorrencia == "todos_os_dias":
        return True

    dias = lista_dias(dias_semana_texto)
    return dia_atual in dias if dias else True



def tarefa_concluida_hoje(tarefa, hoje_iso):
    return (tarefa["ultima_conclusao_data"] or "") == hoje_iso



def medicacao_tomada_hoje(med, hoje_iso):
    return (med["ultima_tomada_data"] or "") == hoje_iso



def tarefa_atrasada(tarefa, dia_atual, agora_hora, hoje_iso):
    if not agendado_hoje(tarefa["recorrencia"], tarefa["dias_semana"], dia_atual):
        return False
    if tarefa_concluida_hoje(tarefa, hoje_iso):
        return False
    horario = parse_horario(tarefa["horario"])
    return bool(horario and horario < agora_hora)



def medicacao_atrasada(med, dia_atual, agora_hora, hoje_iso):
    if not agendado_hoje(med["recorrencia"], med["dias_semana"], dia_atual):
        return False
    if medicacao_tomada_hoje(med, hoje_iso):
        return False
    horario = parse_horario(med["horario"])
    return bool(horario and horario < agora_hora)



def formatar_dias_lista(dias_string):
    if not dias_string:
        return "Todos os dias"
    return dias_string



def formatar_recorrencia(recorrencia, dias_string):
    if recorrencia == "segunda_a_sexta":
        return "Segunda a sexta"
    if recorrencia == "dias_escolhidos":
        return formatar_dias_lista(dias_string)
    return "Todos os dias"



def obter_pontuacao_usuario(nome):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT pontuacao FROM usuarios WHERE nome = ?", (nome,))
    row = cur.fetchone()
    conn.close()
    return row["pontuacao"] if row else 0



def obter_ranking_criancas(cur):
    marcadores = ",".join(["?"] * len(CRIANCAS))
    cur.execute(
        f"SELECT nome, pontuacao FROM usuarios WHERE nome IN ({marcadores}) ORDER BY pontuacao DESC, nome ASC",
        tuple(CRIANCAS),
    )
    return cur.fetchall()



def registrar_evento_habito(cur, usuario, tipo, referencia_id):
    cur.execute(
        "INSERT OR IGNORE INTO eventos_habitos (usuario, tipo, referencia_id, data_evento) VALUES (?, ?, ?, ?)",
        (usuario, tipo, referencia_id, hoje_data_iso()),
    )



def calcular_sequencia_tarefas(cur, usuario):
    cur.execute(
        "SELECT DISTINCT data_evento FROM eventos_habitos WHERE usuario = ? AND tipo = 'tarefa' ORDER BY data_evento DESC",
        (usuario,),
    )
    datas = {row["data_evento"] for row in cur.fetchall()}
    sequencia = 0
    dia = datetime.now().date()
    while dia.strftime("%Y-%m-%d") in datas:
        sequencia += 1
        dia = dia - timedelta(days=1)
    return sequencia



def tomou_remedio_corretamente_hoje(cur, usuario):
    dia_atual = hoje_sigla()
    hoje_iso = hoje_data_iso()
    cur.execute("SELECT * FROM medicacoes WHERE usuario = ?", (usuario,))
    meds = [m for m in cur.fetchall() if agendado_hoje(m["recorrencia"], m["dias_semana"], dia_atual)]
    if not meds:
        return False
    return all((m["ultima_tomada_data"] or "") == hoje_iso for m in meds)



def obter_medalhas_crianca(cur, usuario):
    medalhas = []
    sequencia = calcular_sequencia_tarefas(cur, usuario)
    if sequencia >= 7:
        medalhas.append({"nome": "🔥 Herói da Rotina", "descricao": "7 dias seguidos de tarefas concluídas!"})

    if tomou_remedio_corretamente_hoje(cur, usuario):
        medalhas.append({"nome": "💊 Mestre do Remédio", "descricao": "Tomou os remédios certinhos hoje!"})

    if not medalhas:
        medalhas.append({"nome": "🌟 Em progresso", "descricao": "Continue firme para desbloquear medalhas!"})

    return medalhas



def montar_dados_painel(cur):
    dia_atual = hoje_sigla()
    hoje_iso = hoje_data_iso()
    agora_hora = datetime.now().time()

    cur.execute("SELECT nome, pontuacao FROM usuarios ORDER BY nome")
    usuarios = cur.fetchall()

    cur.execute("SELECT * FROM tarefas ORDER BY usuario, horario")
    todas_tarefas = cur.fetchall()

    cur.execute("SELECT * FROM medicacoes ORDER BY usuario, horario")
    todas_meds = cur.fetchall()

    pendentes_por_pessoa = defaultdict(list)
    atrasadas = []
    hoje = []

    for tarefa in todas_tarefas:
        if not agendado_hoje(tarefa["recorrencia"], tarefa["dias_semana"], dia_atual):
            continue
        if tarefa_concluida_hoje(tarefa, hoje_iso):
            continue
        pendentes_por_pessoa[tarefa["usuario"]].append(tarefa)
        hoje.append(tarefa)
        if tarefa_atrasada(tarefa, dia_atual, agora_hora, hoje_iso):
            atrasadas.append(tarefa)

    med_tomado = defaultdict(list)
    med_pendente = defaultdict(list)

    for med in todas_meds:
        if not agendado_hoje(med["recorrencia"], med["dias_semana"], dia_atual):
            continue
        if medicacao_tomada_hoje(med, hoje_iso):
            med_tomado[med["usuario"]].append(med)
        else:
            med_pendente[med["usuario"]].append(med)

    ranking_criancas = obter_ranking_criancas(cur)

    return {
        "usuarios": usuarios,
        "tarefas": hoje,
        "medicacoes": [m for v in med_pendente.values() for m in v] + [m for v in med_tomado.values() for m in v],
        "pendentes_por_pessoa": dict(pendentes_por_pessoa),
        "atrasadas": atrasadas,
        "med_tomado": dict(med_tomado),
        "med_pendente": dict(med_pendente),
        "pontuacao_total": usuarios,
        "ranking_criancas": ranking_criancas,
        "hoje": hoje,
        "dia_atual": dia_atual,
        "hoje_iso": hoje_iso,
        "medicacoes_atrasadas": [
            m for m in [item for sublist in med_pendente.values() for item in sublist]
            if medicacao_atrasada(m, dia_atual, agora_hora, hoje_iso)
        ],
    }



def processar_acao_admin(cur):
    acao = request.form.get("acao")
    if acao == "criar_tarefa":
        usuario = request.form.get("usuario", "").strip()
        nome = request.form.get("nome", "").strip()
        horario = request.form.get("horario", "").strip()
        recorrencia = request.form.get("recorrencia", "todos_os_dias")
        dias_semana = ", ".join(request.form.getlist("dias_semana"))
        pontos = max(0, int(request.form.get("pontos", 1) or 1))
        if usuario and nome:
            cur.execute(
                "INSERT INTO tarefas (nome, horario, usuario, dias_semana, pontos, recorrencia) VALUES (?, ?, ?, ?, ?, ?)",
                (nome, horario, usuario, dias_semana, pontos, recorrencia),
            )

    elif acao == "criar_medicacao":
        usuario = request.form.get("usuario", "").strip()
        nome = request.form.get("nome", "").strip()
        horario = request.form.get("horario", "").strip()
        recorrencia = request.form.get("recorrencia", "todos_os_dias")
        dias_semana = ", ".join(request.form.getlist("dias_semana"))
        if usuario and nome:
            cur.execute(
                "INSERT INTO medicacoes (nome, horario, usuario, recorrencia, dias_semana) VALUES (?, ?, ?, ?, ?)",
                (nome, horario, usuario, recorrencia, dias_semana),
            )

    elif acao == "concluir_tarefa_admin":
        tarefa_id = request.form.get("tarefa_id", type=int)
        if tarefa_id:
            cur.execute("SELECT usuario, pontos, ultima_conclusao_data FROM tarefas WHERE id = ?", (tarefa_id,))
            tarefa = cur.fetchone()
            if tarefa and tarefa["ultima_conclusao_data"] != hoje_data_iso():
                cur.execute(
                    "UPDATE tarefas SET ultima_conclusao_data = ?, concluida = 1 WHERE id = ?",
                    (hoje_data_iso(), tarefa_id),
                )
                cur.execute(
                    "UPDATE usuarios SET pontuacao = pontuacao + ? WHERE nome = ?",
                    (tarefa["pontos"] or 0, tarefa["usuario"]),
                )
                registrar_evento_habito(cur, tarefa["usuario"], "tarefa", tarefa_id)

    elif acao == "tomado_admin":
        med_id = request.form.get("med_id", type=int)
        if med_id:
            cur.execute("SELECT usuario FROM medicacoes WHERE id = ?", (med_id,))
            med = cur.fetchone()
            cur.execute(
                "UPDATE medicacoes SET ultima_tomada_data = ?, tomado = 1 WHERE id = ?",
                (hoje_data_iso(), med_id),
            )
            if med:
                registrar_evento_habito(cur, med["usuario"], "remedio", med_id)


@app.context_processor
def variaveis_globais():
    return {"usuario_logado": usuario_logado(), "eh_admin": eh_admin(), "eh_crianca": eh_crianca(usuario_logado() or "")}


@app.route("/", methods=["GET", "POST"])
def login():
    erro = None
    if request.method == "POST":
        nome = request.form["nome"]
        senha = request.form["senha"]
        conn = conectar()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE nome=? AND senha=?", (nome, senha))
        usuario = cur.fetchone()
        conn.close()
        if usuario:
            session["usuario"] = nome
            return redirect(url_for("tarefas"))
        erro = "Login inválido"
    return render_template("login.html", erro=erro)


@app.route("/tarefas", methods=["GET", "POST"])
@login_obrigatorio
def tarefas():
    usuario = usuario_logado()
    dia_atual = hoje_sigla()
    hoje_iso = hoje_data_iso()

    conn = conectar()
    cur = conn.cursor()

    if request.method == "POST":
        tarefa = request.form["tarefa"].strip()
        horario = request.form.get("horario", "").strip()
        recorrencia = request.form.get("recorrencia", "todos_os_dias")
        dias_semana = ", ".join(request.form.getlist("dias_semana"))
        pontos = max(0, int(request.form.get("pontos", 1) or 1))
        if tarefa:
            cur.execute(
                "INSERT INTO tarefas (nome, horario, usuario, dias_semana, pontos, recorrencia) VALUES (?, ?, ?, ?, ?, ?)",
                (tarefa, horario, usuario, dias_semana, pontos, recorrencia),
            )
            conn.commit()

    cur.execute("SELECT * FROM tarefas WHERE usuario=? ORDER BY horario", (usuario,))
    lista_tarefas = [t for t in cur.fetchall() if agendado_hoje(t["recorrencia"], t["dias_semana"], dia_atual)]

    cur.execute("SELECT nome, pontuacao FROM usuarios ORDER BY nome")
    pontuacao_total = cur.fetchall()
    ranking_criancas = obter_ranking_criancas(cur)
    conn.close()

    return render_template(
        "tarefas.html",
        tarefas=lista_tarefas,
        dias_semana=DIAS_SEMANA,
        recorrencias=RECORRENCIAS,
        hoje_iso=hoje_iso,
        pontos_usuario=obter_pontuacao_usuario(usuario),
        pontuacao_total=pontuacao_total,
        ranking_criancas=ranking_criancas,
        formatar_recorrencia=formatar_recorrencia,
        tarefa_concluida_hoje=tarefa_concluida_hoje,
    )


@app.route("/concluir/<int:id>", methods=["POST"])
@login_obrigatorio
def concluir(id):
    conn = conectar()
    cur = conn.cursor()

    if eh_admin():
        cur.execute("SELECT usuario, pontos, ultima_conclusao_data FROM tarefas WHERE id = ?", (id,))
    else:
        cur.execute("SELECT usuario, pontos, ultima_conclusao_data FROM tarefas WHERE id = ? AND usuario = ?", (id, usuario_logado()))

    tarefa = cur.fetchone()
    if tarefa and tarefa["ultima_conclusao_data"] != hoje_data_iso():
        cur.execute("UPDATE tarefas SET ultima_conclusao_data = ?, concluida = 1 WHERE id = ?", (hoje_data_iso(), id))
        cur.execute("UPDATE usuarios SET pontuacao = pontuacao + ? WHERE nome = ?", (tarefa["pontos"] or 0, tarefa["usuario"]))
        registrar_evento_habito(cur, tarefa["usuario"], "tarefa", id)

    conn.commit()
    conn.close()
    return redirect(url_for("tarefas"))


@app.route("/excluir/<int:id>", methods=["POST"])
@login_obrigatorio
def excluir(id):
    conn = conectar()
    cur = conn.cursor()
    if eh_admin():
        cur.execute("DELETE FROM tarefas WHERE id = ?", (id,))
    else:
        cur.execute("DELETE FROM tarefas WHERE id = ? AND usuario = ?", (id, usuario_logado()))
    conn.commit()
    conn.close()
    return redirect(url_for("tarefas"))


@app.route("/medicacao", methods=["GET", "POST"])
@login_obrigatorio
def medicacao():
    usuario = usuario_logado()
    dia_atual = hoje_sigla()
    hoje_iso = hoje_data_iso()

    conn = conectar()
    cur = conn.cursor()

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        horario = request.form.get("horario", "").strip()
        recorrencia = request.form.get("recorrencia", "todos_os_dias")
        dias_semana = ", ".join(request.form.getlist("dias_semana"))
        if nome:
            cur.execute(
                "INSERT INTO medicacoes (nome, horario, usuario, recorrencia, dias_semana) VALUES (?, ?, ?, ?, ?)",
                (nome, horario, usuario, recorrencia, dias_semana),
            )
            conn.commit()

    cur.execute("SELECT * FROM medicacoes WHERE usuario=? ORDER BY horario", (usuario,))
    medicacoes = [m for m in cur.fetchall() if agendado_hoje(m["recorrencia"], m["dias_semana"], dia_atual)]
    conn.close()

    return render_template(
        "medicacao.html",
        medicacoes=medicacoes,
        dias_semana=DIAS_SEMANA,
        recorrencias=RECORRENCIAS,
        hoje_iso=hoje_iso,
        medicacao_tomada_hoje=medicacao_tomada_hoje,
        formatar_recorrencia=formatar_recorrencia,
    )


@app.route("/tomado/<int:id>", methods=["POST"])
@login_obrigatorio
def tomado(id):
    conn = conectar()
    cur = conn.cursor()
    if eh_admin():
        cur.execute("SELECT usuario FROM medicacoes WHERE id = ?", (id,))
        med = cur.fetchone()
        cur.execute("UPDATE medicacoes SET ultima_tomada_data = ?, tomado = 1 WHERE id = ?", (hoje_data_iso(), id))
    else:
        cur.execute("SELECT usuario FROM medicacoes WHERE id = ? AND usuario = ?", (id, usuario_logado()))
        med = cur.fetchone()
        cur.execute(
            "UPDATE medicacoes SET ultima_tomada_data = ?, tomado = 1 WHERE id = ? AND usuario = ?",
            (hoje_data_iso(), id, usuario_logado()),
        )

    if med:
        registrar_evento_habito(cur, med["usuario"], "remedio", id)

    conn.commit()
    conn.close()
    return redirect(url_for("medicacao"))


@app.route("/recompensas", methods=["GET", "POST"])
@login_obrigatorio
def recompensas():
    usuario = usuario_logado()
    mensagem = None
    erro = None

    conn = conectar()
    cur = conn.cursor()

    if request.method == "POST":
        premio = request.form.get("premio")
        config = RECOMPENSAS.get(premio)
        if not eh_crianca(usuario):
            erro = "Somente Mayumi, Akira e Kenji podem trocar pontos."
        elif not config:
            erro = "Recompensa inválida."
        else:
            cur.execute("SELECT pontuacao FROM usuarios WHERE nome = ?", (usuario,))
            pontos = cur.fetchone()["pontuacao"]
            if pontos < config["pontos"]:
                erro = "Pontos insuficientes para esta recompensa."
            else:
                cur.execute("UPDATE usuarios SET pontuacao = pontuacao - ? WHERE nome = ?", (config["pontos"], usuario))
                cur.execute(
                    "INSERT INTO trocas_recompensas (usuario, recompensa, pontos_gastos, data_troca) VALUES (?, ?, ?, ?)",
                    (usuario, config["nome"], config["pontos"], hoje_data_iso()),
                )
                mensagem = f"Troca realizada! Você usou {config['pontos']} pontos."
                conn.commit()

    cur.execute("SELECT nome, pontuacao FROM usuarios WHERE nome IN (?, ?, ?) ORDER BY pontuacao DESC, nome ASC", tuple(CRIANCAS))
    ranking = cur.fetchall()

    medalhas = []
    medalhas_por_crianca = {}
    if eh_crianca(usuario):
        medalhas = obter_medalhas_crianca(cur, usuario)
        cur.execute("SELECT * FROM trocas_recompensas WHERE usuario = ? ORDER BY id DESC", (usuario,))
    elif eh_admin():
        for nome in CRIANCAS:
            medalhas_por_crianca[nome] = obter_medalhas_crianca(cur, nome)
        cur.execute("SELECT * FROM trocas_recompensas ORDER BY id DESC")
    else:
        cur.execute("SELECT * FROM trocas_recompensas WHERE 1=0")

    historico = cur.fetchall()
    pontos_restantes = obter_pontuacao_usuario(usuario)

    conn.close()

    return render_template(
        "recompensas.html",
        recompensas=RECOMPENSAS,
        ranking=ranking,
        mensagem=mensagem,
        erro=erro,
        historico=historico,
        pontos_restantes=pontos_restantes,
        medalhas=medalhas,
        medalhas_por_crianca=medalhas_por_crianca,
        eh_crianca=eh_crianca(usuario),
        eh_admin=eh_admin(),
    )


@app.route("/painel-gabi", methods=["GET", "POST"])
@login_obrigatorio
@admin_obrigatorio
def painel_gabi():
    conn = conectar()
    cur = conn.cursor()

    if request.method == "POST":
        processar_acao_admin(cur)
        conn.commit()

    dados = montar_dados_painel(cur)
    modo_cansada = request.args.get("modo") == "cansada"

    tarefas_importantes = [t for t in dados["hoje"] if (t["pontos"] or 0) >= 5 or t["usuario"] == USUARIO_ADMIN]
    medicacoes_obrigatorias = [m for meds in dados["med_pendente"].values() for m in meds]
    pode_delegar = [t for t in dados["hoje"] if t["usuario"] != USUARIO_ADMIN and (t["pontos"] or 0) < 5]
    pode_esperar = [t for t in dados["tarefas"] if not agendado_hoje(t["recorrencia"], t["dias_semana"], dados["dia_atual"])]

    conn.close()
    return render_template(
        "painel_gabi.html",
        dias_semana=DIAS_SEMANA,
        recorrencias=RECORRENCIAS,
        formatar_recorrencia=formatar_recorrencia,
        modo_cansada=modo_cansada,
        tarefas_importantes=tarefas_importantes,
        medicacoes_obrigatorias=medicacoes_obrigatorias,
        pode_delegar=pode_delegar,
        pode_esperar=pode_esperar,
        **dados,
    )


@app.route("/api/notificacoes")
@login_obrigatorio
def api_notificacoes():
    usuario = usuario_logado()
    dia_atual = hoje_sigla()
    hoje_iso = hoje_data_iso()
    agora = datetime.now().time()

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tarefas WHERE usuario = ?", (usuario,))
    tarefas = cur.fetchall()
    cur.execute("SELECT * FROM medicacoes WHERE usuario = ?", (usuario,))
    meds = cur.fetchall()
    conn.close()

    notificacoes = []
    for tarefa in tarefas:
        if not agendado_hoje(tarefa["recorrencia"], tarefa["dias_semana"], dia_atual) or tarefa_concluida_hoje(tarefa, hoje_iso):
            continue
        horario = parse_horario(tarefa["horario"])
        if horario:
            notificacoes.append({
                "id": f"tarefa-{'atrasada' if horario <= agora else 'horario'}-{tarefa['id']}-{hoje_iso}",
                "titulo": "Tarefa atrasada" if horario <= agora else "Lembrete de tarefa",
                "mensagem": (f"{tarefa['nome']} está atrasada." if horario <= agora else f"{tarefa['nome']} às {tarefa['horario']}."),
            })

    for med in meds:
        if not agendado_hoje(med["recorrencia"], med["dias_semana"], dia_atual) or medicacao_tomada_hoje(med, hoje_iso):
            continue
        horario = parse_horario(med["horario"])
        if horario:
            notificacoes.append({
                "id": f"med-{'nao-tomado' if horario <= agora else 'horario'}-{med['id']}-{hoje_iso}",
                "titulo": "Remédio não tomado" if horario <= agora else "Lembrete de medicação",
                "mensagem": (f"{med['nome']} ainda não foi tomado." if horario <= agora else f"{med['nome']} às {med['horario']}."),
            })

    return jsonify({"notificacoes": notificacoes})


@app.route("/admin", methods=["GET", "POST"])
@login_obrigatorio
@admin_obrigatorio
def admin():
    return redirect(url_for("painel_gabi"))


@app.route("/manifest.webmanifest")
def manifest():
    return app.send_static_file("manifest.webmanifest")


@app.route("/service-worker.js")
def service_worker():
    return app.send_static_file("service-worker.js")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
       