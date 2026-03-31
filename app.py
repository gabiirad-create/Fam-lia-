from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

def criar_banco():
    conn = sqlite3.connect("familia.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tarefas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        responsavel TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

criar_banco()

@app.route("/")
def index():
    conn = sqlite3.connect("familia.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM tarefas")
    tarefas = cur.fetchall()
    conn.close()

    return render_template("index.html", tarefas=tarefas)

@app.route("/adicionar", methods=["POST"])
def adicionar():
    nome = request.form["nome"]
    responsavel = request.form["responsavel"]

    conn = sqlite3.connect("familia.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tarefas (nome, responsavel) VALUES (?, ?)",
        (nome, responsavel)
    )
    conn.commit()
    conn.close()

    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
    