# Automação da tela (Backa): rodízio de presets e modo jogo.
#
# As configurações ficam em automacao.json, na pasta do programa (o editor de tela grava; o monitor relê sozinho):
#   rotation: alterna entre os presets da lista a cada N segundos
#   game:     mostra um preset próprio enquanto um jogo está em primeiro plano
#
# Trocar de preset sem reiniciar só é possível quando as tarefas agendadas (intervalos dos sensores) são as mesmas.
# Por isso o monitor já inicia com os intervalos de TODOS os presets envolvidos mesclados (merge_intervals):
# assim o rodízio e o modo jogo trocam de tela em ~3 s, sem reiniciar.
import copy
import json
import os
import time
from pathlib import Path

MAIN_DIRECTORY = Path(__file__).resolve().parent.parent.parent
THEMES_DIR = MAIN_DIRECTORY / "res" / "themes"
SETTINGS_FILE = MAIN_DIRECTORY / "automacao.json"

DEFAULTS = {
    "rotation": {"enabled": False, "presets": [], "seconds": 30},
    "game": {"enabled": False, "preset": "", "fullscreen": True, "enter_seconds": 3, "exit_seconds": 20},
}

CPU_KEYS = ("PERCENTAGE", "FREQUENCY", "LOAD", "TEMPERATURE", "FAN_SPEED")
TOP_KEYS = ("GPU", "MEMORY", "DISK", "NET", "DATE", "UPTIME", "CUSTOM", "WEATHER", "PING")


# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------
def normalize(data) -> dict:
    # Preenche o que faltar e corrige tipos (o arquivo pode ter sido editado à mão)
    out = copy.deepcopy(DEFAULTS)
    data = data if isinstance(data, dict) else {}
    rot, game = data.get("rotation") or {}, data.get("game") or {}
    out["rotation"]["enabled"] = bool(rot.get("enabled", False))
    out["rotation"]["presets"] = [str(p) for p in rot.get("presets", []) if isinstance(p, str) and p][:10]
    out["rotation"]["seconds"] = max(5, min(3600, int(rot.get("seconds", 30) or 30)))
    out["game"]["enabled"] = bool(game.get("enabled", False))
    out["game"]["preset"] = str(game.get("preset") or "")
    out["game"]["fullscreen"] = bool(game.get("fullscreen", True))
    out["game"]["enter_seconds"] = max(1, min(60, int(game.get("enter_seconds", 3) or 3)))
    out["game"]["exit_seconds"] = max(2, min(600, int(game.get("exit_seconds", 20) or 20)))
    return out


def load_settings() -> dict:
    try:
        return normalize(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    except Exception:
        return normalize({})


def save_settings(data) -> dict:
    data = normalize(data)
    temp = SETTINGS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, SETTINGS_FILE)
    return data


def preset_exists(name: str) -> bool:
    return bool(name) and (THEMES_DIR / name / "theme.yaml").is_file()


def rotation_list(settings: dict) -> list:
    if not settings["rotation"]["enabled"]:
        return []
    names = [p for p in dict.fromkeys(settings["rotation"]["presets"]) if preset_exists(p)]
    return names if len(names) >= 2 else []


def game_preset(settings: dict) -> str:
    g = settings["game"]
    return g["preset"] if g["enabled"] and preset_exists(g["preset"]) else ""


def involved_presets(settings: dict, base: str) -> list:
    # Presets que podem aparecer na tela com estas configurações (o do config.yaml primeiro)
    names = [base] + rotation_list(settings) + ([game_preset(settings)] if game_preset(settings) else [])
    return list(dict.fromkeys(n for n in names if n))


# ---------------------------------------------------------------------------
# Intervalos das tarefas agendadas
# ---------------------------------------------------------------------------
def signature(theme_data) -> tuple:
    stats = theme_data["STATS"]
    cpu = stats.get("CPU", {})
    return (tuple((cpu.get(k) or {}).get("INTERVAL", 0) for k in CPU_KEYS) +
            tuple((stats.get(k) or {}).get("INTERVAL", 0) for k in TOP_KEYS))


def _load_theme_data(config, name: str):
    data = config.load_yaml(THEMES_DIR / name / "theme.yaml")
    data = copy.deepcopy(data)
    config.copy_default(copy.deepcopy(config.THEME_DEFAULT), data)
    return data


def merged_signature(config, names: list) -> tuple:
    # Para cada tarefa: o menor intervalo (diferente de zero) entre os presets; zero se nenhum preset usa
    merged = None
    for name in names:
        try:
            sig = signature(_load_theme_data(config, name))
        except Exception:
            continue
        merged = sig if merged is None else tuple(
            min(a, b) if a and b else (a or b) for a, b in zip(merged, sig))
    return merged


def merge_intervals(config, base: str, settings: dict = None, logger=None) -> tuple:
    # Chamado antes de importar o agendador: grava em config.THEME_DATA os intervalos mesclados
    settings = settings or load_settings()
    names = involved_presets(settings, base)
    merged = merged_signature(config, names) if len(names) > 1 else None
    if merged:
        stats = config.THEME_DATA["STATS"]
        values = list(merged)
        for k in CPU_KEYS:
            stats.setdefault("CPU", {}).setdefault(k, {})["INTERVAL"] = values.pop(0)
        for k in TOP_KEYS:
            stats.setdefault(k, {})["INTERVAL"] = values.pop(0)
        if logger:
            logger.info("Automação da tela: intervalos preparados para %s" % ", ".join(names))
    return signature(config.THEME_DATA)


# ---------------------------------------------------------------------------
# Detecção de jogo em primeiro plano
# ---------------------------------------------------------------------------
# Programas que desenham em tela cheia mas não são jogos (navegadores, players, o próprio Windows)
NOT_GAMES = {
    "explorer.exe", "searchhost.exe", "shellexperiencehost.exe", "startmenuexperiencehost.exe", "lockapp.exe",
    "applicationframehost.exe", "textinputhost.exe", "systemsettings.exe", "taskmgr.exe", "dwm.exe",
    "chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "opera_gx.exe", "brave.exe", "vivaldi.exe",
    "msedgewebview2.exe", "steamwebhelper.exe", "steam.exe", "epicgameslauncher.exe", "battle.net.exe",
    "eadesktop.exe", "galaxyclient.exe", "ubisoftconnect.exe", "xboxpcapp.exe", "gamebar.exe",
    "vlc.exe", "mpc-hc64.exe", "mpc-hc.exe", "mpc-be64.exe", "potplayermini64.exe", "potplayermini.exe",
    "wmplayer.exe", "microsoft.media.player.exe", "video.ui.exe", "netflix.exe", "spotify.exe", "discord.exe",
    "obs64.exe", "code.exe", "devenv.exe", "powerpnt.exe", "winword.exe", "excel.exe", "teams.exe", "ms-teams.exe",
    "zoom.exe", "slack.exe", "whatsapp.exe", "telegram.exe", "vmware.exe", "vmware-vmx.exe", "mstsc.exe",
    "windowsterminal.exe", "claude.exe", "python.exe", "pythonw.exe", "main.exe", "editor.exe", "configure.exe",
}

_known = {"time": 0.0, "paths": {}}


def known_games() -> dict:
    # Jogos que o próprio Windows reconheceu (Xbox Game Bar): caminho normalizado do .exe -> caminho original.
    # Relido a cada minuto (jogos novos entram sozinhos depois de abertos uma vez com a Game Bar ativa).
    if time.time() - _known["time"] < 60:
        return _known["paths"]
    paths = {}
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"System\GameConfigStore\Children") as root:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root, sub) as key:
                        exe = winreg.QueryValueEx(key, "MatchedExeFullPath")[0]
                        if exe:
                            paths[os.path.normcase(str(exe))] = str(exe)
                except OSError:
                    continue
    except Exception:
        pass
    _known.update(time=time.time(), paths=paths)
    return paths


def known_game_names() -> list:
    # Para o editor mostrar quais jogos o Windows já conhece
    names = {os.path.basename(p) for p in known_games().values()}
    return sorted((n for n in names if n.lower() not in NOT_GAMES), key=str.lower)


def foreground_window():
    # (pid, caminho do .exe, tela cheia?) da janela em primeiro plano
    try:
        import psutil
        import win32api
        import win32con
        import win32gui
        import win32process
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None, "", False
        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        try:
            exe = psutil.Process(pid).exe()
        except Exception:
            exe = ""
        rect = win32gui.GetWindowRect(hwnd)
        mon = win32api.GetMonitorInfo(win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST))["Monitor"]
        fullscreen = rect[0] <= mon[0] and rect[1] <= mon[1] and rect[2] >= mon[2] and rect[3] >= mon[3]
        return pid, exe, fullscreen
    except Exception:
        return None, "", False


class GameDetector:
    """Decide se há um jogo na tela. Entra no modo jogo depois de alguns segundos com o jogo em primeiro plano
    e sai quando o jogo fecha ou fica um tempo sem estar em primeiro plano (alt+tab rápido não troca a tela)."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.active = False
        self.name = ""
        self.pid = None
        self.candidate = None
        self.candidate_since = 0.0
        self.last_seen = 0.0
        return False

    def _is_game(self, exe: str, fullscreen: bool, fps_fn, use_fullscreen: bool) -> bool:
        if not exe or os.path.basename(exe).lower() in NOT_GAMES:
            return False
        if os.path.normcase(exe) in known_games():
            return True
        if not (use_fullscreen and fullscreen):
            return False
        # Tela cheia que o Windows não reconhece como jogo: com o FPS ligado, exige que esteja desenhando quadros
        if fps_fn is None:
            return True
        fps = fps_fn()
        return fps is not None and fps >= 20

    def poll(self, game_settings: dict, fps_fn=None, fps_enabled=False) -> bool:
        import psutil
        now = time.time()
        pid, exe, fullscreen = foreground_window()
        is_game = self._is_game(exe, fullscreen, fps_fn if fps_enabled else None, game_settings["fullscreen"])
        if is_game:
            if self.candidate != pid:
                self.candidate, self.candidate_since = pid, now
            if self.active and pid == self.pid:
                self.last_seen = now
            elif now - self.candidate_since >= game_settings["enter_seconds"]:
                # Jogo em primeiro plano por tempo suficiente (ou outro jogo assumiu o lugar do anterior)
                self.active, self.pid, self.name, self.last_seen = True, pid, os.path.basename(exe), now
        else:
            self.candidate = None
        if self.active:
            gone = self.pid is not None and not psutil.pid_exists(self.pid)
            if (gone and now - self.last_seen >= 2) or now - self.last_seen >= game_settings["exit_seconds"]:
                self.reset()
        return self.active
