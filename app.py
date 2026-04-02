from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "familia123"


def conectar():
    return sqlite3.connect("familia.db")


def criar_banco():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE,
        senha TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tarefas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        horario TEXT,
        concluida INTEGER DEFAULT 0,
        usuario TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS medicacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        horario TEXT,
        tomado INTEGER DEFAULT 0,
        usuario TEXT
    )
    """)

    usuarios = [
        ("Gabi", "1234"),
        ("Leonardo", "1234"),
        ("Mayumi", "1234"),
        ("Akira", "1234"),
        ("Kenji", "1234")
    ]

    for nome, senha in usuarios:
        cur.execute(
            "INSERT OR IGNORE INTO usuarios (nome, senha) VALUES (?, ?)",
            (nome, senha)
        )

    medicacoes = [
        ("Carbonato de Lítio", "08:00", "Gabi"),
        ("Okralin", "08:00", "Gabi"),
        ("Moringa com Lugol - 2 gotas", "08:00", "Gabi"),
        ("Carbonato de Lítio", "20:00", "Gabi"),

        ("Glifage XR 500", "08:00", "Leonardo"),
        ("Rosuvastatina Cálcica", "08:00", "Leonardo"),
        ("Aradois", "08:00", "Leonardo"),
        ("Selozok", "08:00", "Leonardo"),
        ("Wellbutrin", "08:00", "Leonardo")
    ]

    for nome, horario, usuario in medicacoes:
        cur.execute(
            """
            INSERT OR IGNORE INTO medicacoes (nome, horario, usuario)
            VALUES (?, ?, ?)
            """,
            (nome, horario, usuario)
        )

    conn.commit()
    conn.close()


criar_banco()


@app.route("/", methods=["GET", "POST"])
def login():
    erro = None

    if request.method == "POST":
        nome = request.form["nome"]
        senha = request.form["senha"]

        conn = conectar()
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM usuarios WHERE nome=? AND senha=?",
            (nome, senha)
        )

        usuario = cur.fetchone()
        conn.close()

        if usuario:
            session["usuario"] = nome
            return redirect("/tarefas")
        else:
            erro = "Login inválido"

    return render_template("login.html", erro=erro)


@app.route("/tarefas", methods=["GET", "POST"])
def tarefas():
    if "usuario" not in session:
        return redirect("/")

    usuario = session["usuario"]

    conn = conectar()
    cur = conn.cursor()

    if request.method == "POST":
        tarefa = request.form["tarefa"]
        horario = request.form["horario"]

        cur.execute(
            "INSERT INTO tarefas (nome, horario, usuario) VALUES (?, ?, ?)",
            (tarefa, horario, usuario)
        )

        conn.commit()

    cur.execute(
        "SELECT * FROM tarefas WHERE usuario=?",
        (usuario,)
    )
    tarefas = cur.fetchall()

    conn.close()

    return render_template(
        "tarefas.html",
        usuario=usuario,
        tarefas=tarefas
    )


@app.route("/concluir/<int:id>")
def concluir(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute(
        "UPDATE tarefas SET concluida = 1 WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/tarefas")


@app.route("/excluir/<int:id>")
def excluir(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM tarefas WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/tarefas")


@app.route("/medicacao")
def medicacao():
    if "usuario" not in session:
        return redirect("/")

    usuario = session["usuario"]

    conn = conectar()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM medicacoes WHERE usuario=?",
        (usuario,)
    )

    medicacoes = cur.fetchall()

    conn.close()

    return render_template(
        "medicacao.html",
        usuario=usuario,
        medicacoes=medicacoes
    )


@app.route("/tomado/<int:id>")
def tomado(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute(
        "UPDATE medicacoes SET tomado = 1 WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/medicacao")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
    