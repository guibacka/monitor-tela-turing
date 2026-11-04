# Regras de alerta (Backa): o que deixa o ícone de alerta e a borda de status em amarelo (atenção) ou vermelho (crítico).
#
# Ficam em alertas.json, na pasta do programa: valem para todos os presets. O editor de tela grava (botão
# "Alertas…") e o monitor relê sozinho. A aparência (ícone de cada nível, cores e espessura da borda) fica nas
# propriedades dos itens de cada preset.
#
# Regras com limites: "AMARELO"/"VERMELHO" = valor a partir do qual entra no nível (None = esse nível não é usado).
# Regras de estado (throttle, saúde, atualizações): "nivel" = AMARELO ou VERMELHO.
import copy
import json
import os
from pathlib import Path

MAIN_DIRECTORY = Path(__file__).resolve().parent.parent.parent
SETTINGS_FILE = MAIN_DIRECTORY / "alertas.json"

# Ordem e textos usados pelo editor
RULES = [
    # chave, rótulo, unidade, tipo, padrão
    ("cpu_temp", "Temperatura da CPU", "°C", "limits", {"on": True, "AMARELO": 70, "VERMELHO": 85}),
    ("gpu_temp", "Temperatura da GPU", "°C", "limits", {"on": True, "AMARELO": 70, "VERMELHO": 80}),
    ("ssd_temp", "Temperatura dos SSDs", "°C", "limits", {"on": True, "AMARELO": 55, "VERMELHO": 70}),
    ("ram_temp", "Temperatura da RAM (pente mais quente)", "°C", "limits", {"on": True, "AMARELO": 60, "VERMELHO": 75}),
    ("vram", "VRAM em uso", "%", "limits", {"on": True, "AMARELO": 95, "VERMELHO": None}),
    ("ram", "RAM em uso", "%", "limits", {"on": True, "AMARELO": 90, "VERMELHO": None}),
    ("disk_full", "Disco quase cheio", "%", "limits", {"on": True, "AMARELO": 95, "VERMELHO": None}),
    ("cpu_throttle", "CPU no limite de temperatura (throttle)", "°C", "state",
     {"on": True, "nivel": "VERMELHO", "limite": 89}),
    ("gpu_throttle", "GPU reduzindo clock por temperatura (throttle)", "", "state", {"on": True, "nivel": "VERMELHO"}),
    ("gpu_power", "GPU no limite de energia", "", "state", {"on": False, "nivel": "AMARELO"}),
    ("ssd_health", "Saúde dos SSDs", "", "state", {"on": True, "nivel": "VERMELHO"}),
    ("update_windows", "Atualização do Windows disponível", "", "state", {"on": False, "nivel": "AMARELO"}),
    ("update_nvidia", "Driver NVIDIA novo disponível", "", "state", {"on": False, "nivel": "AMARELO"}),
]
DEFAULTS = {key: default for key, _, _, _, default in RULES}
LEVELS = ("AMARELO", "VERMELHO")


def _num(v, lo, hi):
    if v is None or v == "":
        return None
    try:
        return max(lo, min(hi, int(float(v))))
    except (TypeError, ValueError):
        return None


def normalize(data) -> dict:
    # Preenche o que faltar e corrige tipos (o arquivo pode ter sido editado à mão)
    data = data if isinstance(data, dict) else {}
    out = {}
    for key, _, unit, kind, default in RULES:
        rule = copy.deepcopy(default)
        given = data.get(key) if isinstance(data.get(key), dict) else {}
        rule["on"] = bool(given.get("on", default["on"]))
        if kind == "limits":
            hi = 150 if unit == "°C" else 100
            for level in LEVELS:
                rule[level] = _num(given[level], 1, hi) if level in given else default[level]
            if rule["AMARELO"] is not None and rule["VERMELHO"] is not None and rule["VERMELHO"] < rule["AMARELO"]:
                rule["VERMELHO"] = rule["AMARELO"]
        else:
            rule["nivel"] = given.get("nivel") if given.get("nivel") in LEVELS else default["nivel"]
            if "limite" in default:
                rule["limite"] = _num(given.get("limite"), 40, 120) or default["limite"]
        out[key] = rule
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


def level_of(rule: dict, value) -> int:
    # Nível (0 verde, 1 amarelo, 2 vermelho) de um valor numa regra com limites
    if not rule.get("on") or value is None:
        return 0
    if rule.get("VERMELHO") is not None and value >= rule["VERMELHO"]:
        return 2
    if rule.get("AMARELO") is not None and value >= rule["AMARELO"]:
        return 1
    return 0


def state_level(rule: dict, active: bool) -> int:
    if not rule.get("on") or not active:
        return 0
    return 2 if rule.get("nivel") == "VERMELHO" else 1


class Cached:
    # Relê alertas.json só quando o arquivo muda (o monitor consulta a cada 2 s)
    def __init__(self):
        self.mtime = None
        self.data = normalize({})

    def get(self) -> dict:
        try:
            mtime = SETTINGS_FILE.stat().st_mtime
        except OSError:
            mtime = 0
        if mtime != self.mtime:
            self.mtime = mtime
            self.data = load_settings()
        return self.data
