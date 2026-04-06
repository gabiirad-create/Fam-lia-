if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js");
  });
}

async function pedirPermissaoNotificacao() {
  if (!("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "default") {
    const p = await Notification.requestPermission();
    return p === "granted";
  }
  return false;
}

function jaNotificada(id) {
  const key = `notif-${id}`;
  return localStorage.getItem(key) === "1";
}

function marcarNotificada(id) {
  localStorage.setItem(`notif-${id}`, "1");
}

async function checarNotificacoes() {
  const ok = await pedirPermissaoNotificacao();
  if (!ok) return;

  try {
    const resp = await fetch("/api/notificacoes");
    if (!resp.ok) return;

    const data = await resp.json();
    (data.notificacoes || []).forEach((n) => {
      if (jaNotificada(n.id)) return;
      new Notification(n.titulo, { body: n.mensagem, tag: n.id, renotify: false });
      marcarNotificada(n.id);
    });
  } catch (_e) {
    // silencioso para não quebrar a UI
  }
}

window.addEventListener("load", () => {
  checarNotificacoes();
  setInterval(checarNotificacoes, 60 * 1000);
});
