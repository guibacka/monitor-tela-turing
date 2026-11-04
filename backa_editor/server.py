# Editor visual de temas (presets) Backa - servidor local
# Roda só em 127.0.0.1 (nada fica acessível pela rede) e abre o editor no navegador.
# Uso: .venv\Scripts\python.exe backa_editor\server.py
import base64
import io
import json
import mimetypes
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Pasta do programa: na versão instalada (PyInstaller) é a pasta do editor.exe; em desenvolvimento, a raiz do projeto
FROZEN = getattr(sys, "frozen", False)
ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
if not FROZEN:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from library.backa import layout as L  # noqa: E402

HOST = "127.0.0.1"
# Endereço amigável: os navegadores enviam qualquer *.localhost para o próprio PC, sem configurar nada no Windows.
# Usa portas pouco comuns (não a 80) para não atrapalhar Docker, servidores web etc.: http://monitor.localhost:8765
# Para abrir sem digitar nada, há atalhos "Editor de Tela" na área de trabalho e no menu Iniciar.
FRIENDLY_NAME = "monitor.localhost"
PORTS = [int(os.environ["BACKA_EDITOR_PORT"])] if os.environ.get("BACKA_EDITOR_PORT") else [8765, 8766]
PORT = PORTS[0]


def editor_url(port: int) -> str:
    return f"http://{FRIENDLY_NAME}/" if port == 80 else f"http://{FRIENDLY_NAME}:{port}/"


URL = editor_url(PORT)
STATIC = ROOT / "backa_editor" / "static"
TOKEN = secrets.token_urlsafe(24)
IDLE_TIMEOUT_S = 30 * 60
NAME_RE = re.compile(r"^[A-Za-z0-9 _\-]{1,40}$")
last_request = time.time()


def active_theme() -> str:
    text = (ROOT / "config.yaml").read_text(encoding="utf-8")
    m = re.search(r"^\s*THEME:\s*(.+?)\s*$", text, re.M)
    return m.group(1).strip().strip('"\'') if m else ""


def set_active_theme(name: str):
    # Troca só a linha THEME do config.yaml, preservando o resto do arquivo (o monitor recarrega sozinho)
    path = ROOT / "config.yaml"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^(\s*THEME:\s*).*$", lambda m: m.group(1) + name, text, count=1, flags=re.M)
    path.write_text(text, encoding="utf-8")


def monitor_state() -> str:
    # running / reloading / stopped, a partir dos arquivos que o monitor grava
    try:
        st = json.loads((ROOT / ".monitor.state").read_text())
    except Exception:
        st = {"state": "stopped", "time": 0}
    if st.get("state") == "reloading" and time.time() - st.get("time", 0) < 40:
        return "reloading"
    try:
        import psutil
        pid = int((ROOT / ".monitor.pid").read_text())
        if psutil.pid_exists(pid) and psutil.Process(pid).name().lower() in ("python.exe", "pythonw.exe", "python", "main.exe"):
            return "running"
    except Exception:
        pass
    return "stopped"


def png_data_url(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    # --- respostas ---
    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, code=200):
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _error(self, msg, code=400):
        self._json({"error": msg}, code)

    # --- segurança: só localhost e com o token da página ---
    def _host_ok(self):
        # Só aceita os nomes do próprio PC (protege contra páginas de fora tentando falar com o editor)
        suffix = "" if PORT == 80 else f":{PORT}"
        allowed = {f"{name}{suffix}" for name in (FRIENDLY_NAME, "localhost", "127.0.0.1")}
        if PORT == 80:
            allowed |= {f"{name}:80" for name in (FRIENDLY_NAME, "localhost", "127.0.0.1")}
        return self.headers.get("Host", "") in allowed

    def _api_ok(self):
        return self._host_ok() and secrets.compare_digest(self.headers.get("X-Backa-Token", ""), TOKEN)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        if n > 25 * 1024 * 1024:
            raise ValueError("Arquivo grande demais (máx. 25 MB)")
        return json.loads(self.rfile.read(n) or b"{}")

    def _preset_name(self, name):
        if not name or not NAME_RE.match(name):
            raise ValueError("Nome inválido: use letras, números, espaço, - ou _ (até 40 caracteres)")
        return name

    # --- GET ---
    def do_GET(self):
        global last_request
        last_request = time.time()
        if not self._host_ok():
            return self._error("Host não permitido", 403)
        url = urlparse(self.path)
        if url.path == "/ping":
            # Usado para saber se o editor já está aberto nesta porta (não expõe nada)
            return self._json({"app": "backa-editor"})
        if url.path in ("/", "/index.html"):
            html = (STATIC / "index.html").read_text(encoding="utf-8").replace("{{TOKEN}}", TOKEN)
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        if url.path.startswith("/static/"):
            file = (STATIC / url.path[len("/static/"):]).resolve()
            if STATIC not in file.parents or not file.is_file():
                return self._error("Não encontrado", 404)
            return self._send(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
        if url.path in ("/icons/tabler-icons.ttf", "/icons/tabler-icons-filled.ttf"):
            # Fontes da biblioteca de ícones (a página usa para mostrar os ícones; a tela usa as mesmas)
            file = L.SYMBOLS_DIR / url.path.rsplit("/", 1)[1]
            if not file.is_file():
                return self._error("Não encontrado", 404)
            self.send_response(200)
            self.send_header("Content-Type", "font/ttf")
            self.send_header("Cache-Control", "max-age=86400")
            body = file.read_bytes()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not self._api_ok():
            return self._error("Não autorizado", 403)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path == "/api/catalog":
                return self._json({"sources": L.SOURCES, "widgets": L.WIDGET_LABELS, "static": L.STATIC_KINDS,
                                   "fonts": L.list_fonts()})
            if url.path == "/api/icons":
                return self._json(L.symbol_catalog())
            if url.path == "/api/presets":
                return self._json({"presets": L.list_presets(), "active": active_theme()})
            if url.path == "/api/preset":
                return self._json(L.load_layout(self._preset_name(q.get("name"))))
            if url.path == "/api/live":
                # Última imagem da tela real + estado do monitor (nos cabeçalhos)
                file = ROOT / f".live-preview-{active_theme()}.png"
                state = monitor_state()
                if not file.exists():
                    return self._json({"state": state}, 404)
                body = file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Monitor-State", state)
                self.send_header("X-Live-Age", f"{time.time() - file.stat().st_mtime:.1f}")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
        except Exception as e:
            return self._error(str(e))
        return self._error("Não encontrado", 404)

    # --- POST ---
    def do_POST(self):
        global last_request
        last_request = time.time()
        if not self._api_ok():
            return self._error("Não autorizado", 403)
        try:
            data = self._body()
            path = urlparse(self.path).path
            if path == "/api/render":
                layout = data["layout"]
                img, boxes = L.render_preview(layout, L.THEMES_DIR / self._preset_name(layout.get("name") or "BackaRGB"))
                return self._json({"image": png_data_url(img), "boxes": boxes, "problems": L.validate_layout(layout)})
            if path in ("/api/save", "/api/apply"):
                name = self._preset_name(data["name"])
                problems = L.validate_layout(data["layout"])
                if problems:
                    return self._json({"problems": problems})
                L.save_layout(name, data["layout"])
                problems = L.compile_layout(name)
                if path == "/api/apply" and not problems:
                    set_active_theme(name)
                return self._json({"problems": problems, "active": active_theme()})
            if path == "/api/upload":
                name = self._preset_name(data["name"])
                filename = re.sub(r"[^A-Za-z0-9_.\-]", "_", Path(data["filename"]).name)
                if Path(filename).suffix.lower() not in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"):
                    raise ValueError("Formato de imagem não suportado")
                raw = base64.b64decode(data["data"].split(",", 1)[-1])
                from PIL import Image
                Image.open(io.BytesIO(raw)).verify()  # garante que é uma imagem válida
                assets = L.THEMES_DIR / name / "assets"
                assets.mkdir(parents=True, exist_ok=True)
                (assets / filename).write_bytes(raw)
                return self._json({"src": f"assets/{filename}"})
            if path == "/api/shutdown":
                self._json({"ok": True})
                threading.Thread(target=lambda: (time.sleep(0.5), os._exit(0)), daemon=True).start()
                return
        except Exception as e:
            return self._error(str(e))
        return self._error("Não encontrado", 404)


def open_browser():
    # Pelo explorer.exe, o navegador abre como usuário comum mesmo que o editor tenha sido aberto como administrador
    if sys.platform == "win32":
        subprocess.Popen(["explorer.exe", URL])
    else:
        import webbrowser
        webbrowser.open(URL)


def idle_watchdog():
    while True:
        time.sleep(60)
        if time.time() - last_request > IDLE_TIMEOUT_S:
            os._exit(0)


def running_editor_port():
    # Procura um editor já aberto nas portas possíveis
    import urllib.request
    for port in PORTS:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=1) as r:
                if json.loads(r.read()).get("app") == "backa-editor":
                    return port
        except Exception:
            continue
    return None


def main():
    global PORT, URL
    # Se o editor já estiver aberto, só abre o navegador nele
    existing = running_editor_port()
    if existing:
        PORT, URL = existing, editor_url(existing)
        if not os.environ.get("BACKA_EDITOR_NO_BROWSER"):
            open_browser()
        return
    server = None
    for port in PORTS:
        try:
            server = ThreadingHTTPServer((HOST, port), Handler)
            PORT, URL = port, editor_url(port)
            break
        except OSError:
            continue
    if server is None:
        sys.exit("Nenhuma porta disponível para o editor (%s)" % ", ".join(map(str, PORTS)))
    threading.Thread(target=idle_watchdog, daemon=True).start()
    if not os.environ.get("BACKA_EDITOR_NO_BROWSER"):
        open_browser()
    server.serve_forever()


if __name__ == "__main__":
    main()
