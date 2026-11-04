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
from library.backa import automation as A  # noqa: E402
from library.backa import alerts as AL  # noqa: E402

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


def hardware_inventory(key: str) -> list:
    # Fans / adaptadores de rede encontrados pelo monitor (ele grava .monitor.hw.json a cada 30 s; o editor não lê
    # os sensores direto porque isso exige administrador)
    try:
        return json.loads((ROOT / ".monitor.hw.json").read_text(encoding="utf-8")).get(key) or []
    except Exception:
        return []


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


def monitor_info() -> dict:
    # Estado do monitor (running / reloading / stopped) e o preset que está na tela agora (rodízio/modo jogo)
    try:
        st = json.loads((ROOT / ".monitor.state").read_text(encoding="utf-8"))
    except Exception:
        st = {"state": "stopped", "time": 0}
    info = {"theme": st.get("theme") or active_theme(), "reason": st.get("reason") or "normal"}
    if st.get("state") == "reloading" and time.time() - st.get("time", 0) < 40:
        return dict(info, state="reloading")
    try:
        import psutil
        pid = int((ROOT / ".monitor.pid").read_text())
        if psutil.pid_exists(pid) and psutil.Process(pid).name().lower() in ("python.exe", "pythonw.exe", "python", "main.exe"):
            return dict(info, state="running")
    except Exception:
        pass
    return dict(info, state="stopped", theme=active_theme(), reason="normal")


def monitor_state() -> str:
    return monitor_info()["state"]


# --- Excluir preset: vai para a Lixeira do Windows (dá para recuperar) ---
def send_to_recycle_bin(path: Path):
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 3, 0x4, 0x10, 0x40, 0x400
    # pFrom termina com dois caracteres nulos: um aqui e outro colocado pelo ctypes
    op = SHFILEOPSTRUCTW(None, FO_DELETE, str(path) + "\0", None,
                         FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI, False, None, None)
    code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if code != 0 or op.fAnyOperationsAborted or path.exists():
        raise OSError(f"Não foi possível enviar para a Lixeira (código {code})")


def delete_preset(name: str) -> dict:
    presets = L.list_presets()
    if name not in presets:
        raise ValueError("Preset não encontrado")
    if len(presets) <= 1:
        raise ValueError("É o único preset: crie outro antes de excluir este")
    info = monitor_info()
    if name in (active_theme(), info.get("theme")):
        raise ValueError("Este preset está na tela agora: aplique outro antes de excluir")
    settings = A.load_settings()
    if settings["game"]["preset"] == name:
        raise ValueError("Este é o preset do modo jogo: troque em Automação… antes de excluir")
    note = ""
    if name in settings["rotation"]["presets"]:
        settings["rotation"]["presets"] = [p for p in settings["rotation"]["presets"] if p != name]
        note = "Ele também saiu do rodízio."
        if settings["rotation"]["enabled"] and len(settings["rotation"]["presets"]) < 2:
            settings["rotation"]["enabled"] = False
            note = "Ele também saiu do rodízio, que foi desligado (ficou com menos de 2 presets)."
        A.save_settings(settings)
    send_to_recycle_bin(L.THEMES_DIR / name)
    preview = ROOT / f".live-preview-{name}.png"
    if preview.exists():
        preview.unlink()
    return {"deleted": name, "note": note}


# --- Exportar / importar presets (.zip com o layout.json e as imagens) ---
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
ZIP_MAX_FILES = 300
ZIP_MAX_BYTES = 60 * 1024 * 1024


def export_preset(name: str) -> bytes:
    import zipfile
    folder = L.THEMES_DIR / name
    if not (folder / L.LAYOUT_FILE).is_file():
        raise ValueError("Preset não encontrado")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(folder / L.LAYOUT_FILE, L.LAYOUT_FILE)
        for f in sorted((folder / "assets").rglob("*")) if (folder / "assets").is_dir() else []:
            if f.is_file() and f.suffix.lower() in IMAGE_EXT:
                z.write(f, "assets/" + f.relative_to(folder / "assets").as_posix())
        if (folder / "preview.png").is_file():
            z.write(folder / "preview.png", "preview.png")
    return buf.getvalue()


def read_preset_zip(raw: bytes):
    # Lê o .zip com cuidado: só layout.json e imagens em assets/, sem caminhos estranhos, com limite de tamanho.
    # Aceita o layout.json na raiz ou dentro de uma única pasta (zip feito "compactando a pasta").
    import zipfile
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise ValueError("O arquivo não é um .zip válido")
    entries = [i for i in z.infolist() if not i.is_dir()]
    if len(entries) > ZIP_MAX_FILES or sum(i.file_size for i in entries) > ZIP_MAX_BYTES:
        raise ValueError("O .zip é grande demais para um preset")
    layouts = [i.filename for i in entries if i.filename.replace("\\", "/").rsplit("/", 1)[-1] == L.LAYOUT_FILE]
    if not layouts:
        raise ValueError("Não encontrei o layout.json dentro do .zip (exporte o preset pelo editor)")
    prefix = min(layouts, key=len).replace("\\", "/")[:-len(L.LAYOUT_FILE)]
    try:
        layout = json.loads(z.read(min(layouts, key=len)).decode("utf-8"))
    except Exception:
        raise ValueError("O layout.json do .zip está corrompido")
    if not isinstance(layout, dict) or not isinstance(layout.get("items"), list):
        raise ValueError("O layout.json do .zip não é de um preset deste editor")
    assets = {}
    for i in entries:
        name = i.filename.replace("\\", "/")
        if not name.startswith(prefix + "assets/"):
            continue
        rel = name[len(prefix + "assets/"):]
        parts = rel.split("/")
        if not rel or any(part in ("", ".", "..") for part in parts) or ":" in rel:
            continue
        if Path(rel).suffix.lower() not in IMAGE_EXT:
            continue
        assets[rel] = z.read(i)
    return layout, assets


def import_preset(raw: bytes, name: str, overwrite: bool) -> dict:
    import shutil
    layout, assets = read_preset_zip(raw)
    folder = L.THEMES_DIR / name
    if folder.exists() and not overwrite:
        n = 2
        while (L.THEMES_DIR / f"{name} {n}").exists():
            n += 1
        return {"exists": True, "suggested": f"{name} {n}"[:40]}
    problems = L.validate_layout(layout)
    if problems:
        return {"problems": problems}
    if (folder / "assets").is_dir():
        shutil.rmtree(folder / "assets")
    for rel, data in assets.items():
        dest = (folder / "assets" / rel).resolve()
        if (folder / "assets").resolve() not in dest.parents:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    L.save_layout(name, layout)
    return {"name": name, "problems": L.compile_layout(name)}


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
        m = re.fullmatch(r"/icons/png/([a-z0-9_]{1,40})\.png", url.path)
        if m:
            # Ícones padrão (PNG) do alerta e do clima, para o editor mostrar ao lado dos escolhidos
            file = L.ICONS_DIR / f"{m.group(1)}.png"
            if not file.is_file():
                return self._error("Não encontrado", 404)
            return self._send(200, file.read_bytes(), "image/png")
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
                                   "fonts": L.list_fonts(), "fans": hardware_inventory("fans"),
                                   "temps": hardware_inventory("temps"), "nets": hardware_inventory("nets")})
            if url.path == "/api/fans":
                return self._json({"fans": hardware_inventory("fans"), "temps": hardware_inventory("temps"),
                                   "nets": hardware_inventory("nets")})
            if url.path == "/api/alerts":
                rules = [{"key": k, "label": lbl, "unit": unit, "kind": kind} for k, lbl, unit, kind, _ in AL.RULES]
                return self._json({"settings": AL.load_settings(), "rules": rules, "defaults": AL.normalize({})})
            if url.path == "/api/icons":
                return self._json(L.symbol_catalog())
            if url.path == "/api/automation":
                return self._json({"settings": A.load_settings(), "presets": L.list_presets(), "active": active_theme(),
                                   "games": A.known_game_names(), "monitor": monitor_info()})
            if url.path == "/api/export":
                name = self._preset_name(q.get("name"))
                body = export_preset(name)
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if url.path == "/api/presets":
                return self._json({"presets": L.list_presets(), "active": active_theme()})
            if url.path == "/api/preset":
                return self._json(L.load_layout(self._preset_name(q.get("name"))))
            if url.path == "/api/live":
                # Última imagem da tela real + estado do monitor (nos cabeçalhos).
                # Com rodízio/modo jogo, o preset na tela pode ser outro que o do config.yaml
                from urllib.parse import quote
                info = monitor_info()
                state = info["state"]
                file = ROOT / f".live-preview-{info['theme']}.png"
                if not file.exists():
                    return self._json(info, 404)
                body = file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Monitor-State", state)
                self.send_header("X-Monitor-Theme", quote(info["theme"]))
                self.send_header("X-Monitor-Reason", quote(info["reason"]))
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
                img, boxes = L.render_preview(layout, L.THEMES_DIR / self._preset_name(layout.get("name") or "Backa"))
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
            if path == "/api/automation":
                settings = A.normalize(data.get("settings"))
                presets = set(L.list_presets())
                settings["rotation"]["presets"] = [p for p in settings["rotation"]["presets"] if p in presets]
                if settings["game"]["preset"] and settings["game"]["preset"] not in presets:
                    raise ValueError("Preset do modo jogo não encontrado")
                if settings["rotation"]["enabled"] and len(settings["rotation"]["presets"]) < 2:
                    raise ValueError("Escolha pelo menos 2 presets para o rodízio")
                if settings["game"]["enabled"] and not settings["game"]["preset"]:
                    raise ValueError("Escolha o preset do modo jogo")
                return self._json({"settings": A.save_settings(settings)})
            if path == "/api/delete":
                return self._json(delete_preset(self._preset_name(data["name"])))
            if path == "/api/alerts":
                return self._json({"settings": AL.save_settings(data.get("settings"))})
            if path == "/api/import":
                name = self._preset_name(data["name"])
                raw = base64.b64decode(data["data"].split(",", 1)[-1])
                return self._json(import_preset(raw, name, bool(data.get("overwrite"))))
            if path == "/api/import-info":
                # Nome sugerido para o preset que está no .zip
                layout, assets = read_preset_zip(base64.b64decode(data["data"].split(",", 1)[-1]))
                suggested = re.sub(r"[^A-Za-z0-9 _\-]", "", str(layout.get("name") or Path(data.get("filename", "")).stem))[:40]
                return self._json({"suggested": suggested.strip() or "Importado", "images": len(assets),
                                   "items": len(layout["items"])})
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
