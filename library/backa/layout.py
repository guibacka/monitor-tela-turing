# Layouts editáveis (presets) para o turing-smart-screen-python
#
# Um preset é um tema com um arquivo layout.json, onde CADA item da tela é um componente:
#   - fundo: cor sólida, imagem ou nenhum
#   - estáticos: painel, retângulo, texto, imagem, linha  -> desenhados no background.png
#   - dados: valores dos sensores (texto, barra, gráfico, medidor), clima, alerta, borda de status -> theme.yaml
# compile_layout() gera background.png + theme.yaml (+ preview.png) na pasta do tema, a partir do layout.json.
# render_preview() desenha o layout com dados de exemplo (usado pelo editor), com a mesma biblioteca de imagens da tela.
import copy
import datetime
import json
import math
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

MAIN_DIRECTORY = Path(__file__).resolve().parent.parent.parent
THEMES_DIR = MAIN_DIRECTORY / "res" / "themes"
FONTS_DIR = MAIN_DIRECTORY / "res" / "fonts"
ICONS_DIR = MAIN_DIRECTORY / "res" / "backa" / "icons"
# Biblioteca de ícones do editor (Tabler Icons, licença MIT), gerada por res/backa/make_icon_catalog.py
SYMBOLS_DIR = MAIN_DIRECTORY / "res" / "backa" / "tabler-icons"
LAYOUT_FILE = "layout.json"

# Chave do widget no editor -> chave usada no theme.yaml
WIDGET_KEYS = {"text": "TEXT", "bar": "GRAPH", "line_graph": "LINE_GRAPH", "radial": "RADIAL"}
WIDGET_LABELS = {"text": "Texto", "bar": "Barra", "line_graph": "Gráfico de linha", "radial": "Medidor redondo",
                 "weather": "Clima (ícone + texto)", "icon": "Ícone", "border": "Borda de status"}

# ---------------------------------------------------------------------------
# Catálogo de fontes de dados
#   path: caminho em STATS do theme.yaml (sensores nativos) | custom: classe em sensors_custom.py
#   interval_at: onde fica o INTERVAL (segundos) desse sensor no theme.yaml
#   sample: valor de exemplo (número 0-100 para barras/gráficos) | sample_text: texto de exemplo
# ---------------------------------------------------------------------------
SOURCES = {
    "CPU_PERCENT": {"group": "CPU", "label": "Uso (%)", "path": ["CPU", "PERCENTAGE"], "interval_at": ["CPU", "PERCENTAGE"],
                    "interval": 2, "widgets": ["text", "bar", "line_graph", "radial"], "sample": 23, "sample_text": " 23%"},
    "CPU_FREQ": {"group": "CPU", "label": "Clock", "path": ["CPU", "FREQUENCY"], "interval_at": ["CPU", "FREQUENCY"],
                 "interval": 3, "widgets": ["text"], "sample_text": "4.85 GHz"},
    "CPU_TEMP": {"group": "CPU", "label": "Temperatura (cor por nível)", "custom": "BackaCpuTemp", "widgets": ["text"],
                 "sample_text": " 52°C", "temp_levels": {"AMARELO": 70, "VERMELHO": 85}},
    "CPU_POWER": {"group": "CPU", "label": "Potência (W)", "custom": "BackaCpuPower", "widgets": ["text", "bar", "line_graph"],
                  "sample": 41, "sample_text": "  62 W", "max": 150},
    "GPU_PERCENT": {"group": "GPU", "label": "Uso (%)", "path": ["GPU", "PERCENTAGE"], "interval_at": ["GPU"], "interval": 2,
                    "widgets": ["text", "bar", "line_graph", "radial"], "sample": 41, "sample_text": " 41%"},
    "GPU_FREQ": {"group": "GPU", "label": "Clock", "path": ["GPU", "FREQUENCY"], "interval_at": ["GPU"], "interval": 2,
                 "widgets": ["text"], "sample_text": "2.61 GHz"},
    "GPU_TEMP": {"group": "GPU", "label": "Temperatura (cor por nível)", "custom": "BackaGpuTemp", "widgets": ["text"],
                 "sample_text": " 58°C", "temp_levels": {"AMARELO": 70, "VERMELHO": 80}},
    "GPU_VRAM": {"group": "GPU", "label": "VRAM (GB)", "custom": "BackaVram", "widgets": ["text", "bar"],
                 "sample": 33, "sample_text": " 2.6 / 8.0 GB"},
    "GPU_FAN": {"group": "GPU", "label": "Fan (%)", "path": ["GPU", "FAN_SPEED"], "interval_at": ["GPU"], "interval": 2,
                "widgets": ["text", "bar", "radial"], "sample": 35, "sample_text": " 35%"},
    "GPU_POWER": {"group": "GPU", "label": "Potência (W)", "custom": "BackaGpuPower", "widgets": ["text", "bar", "line_graph"],
                  "sample": 59, "sample_text": " 118 W", "max": 200},
    "GPU_FPS": {"group": "GPU", "label": "FPS do jogo em primeiro plano", "custom": "BackaFps", "widgets": ["text", "line_graph"],
                "sample": 60, "sample_text": " 144 FPS", "max": 240, "fast_refresh": 1},
    "RAM_USED": {"group": "RAM", "label": "Em uso (GB)", "custom": "BackaRamUsed", "widgets": ["text", "bar", "line_graph"],
                 "sample": 45, "sample_text": "14.4 GB"},
    "RAM_FREE": {"group": "RAM", "label": "Livre (GB)", "custom": "BackaRamFree", "widgets": ["text"], "sample_text": "16.8 GB"},
    "DISK_C_FREE": {"group": "Disco C:", "label": "Espaço livre", "custom": "BackaDiskCFree", "widgets": ["text", "bar"],
                    "sample": 32, "sample_text": " 636 GB livres"},
    "DISK_C_HEALTH": {"group": "Disco C:", "label": "Saúde do SSD", "custom": "BackaDiskCHealth", "widgets": ["text"],
                      "sample_text": "NV3     OK      desg.  0%"},
    "DISK_C_TEMP": {"group": "Disco C:", "label": "Temperatura (cor por nível)", "custom": "BackaDiskCTemp", "widgets": ["text"],
                    "sample_text": " 40°C", "temp_levels": {"AMARELO": 55, "VERMELHO": 70}},
    "DISK_J_FREE": {"group": "Disco J:", "label": "Espaço livre", "custom": "BackaDiskJFree", "widgets": ["text", "bar"],
                    "sample": 52, "sample_text": " 456 GB livres"},
    "DISK_J_HEALTH": {"group": "Disco J:", "label": "Saúde do SSD", "custom": "BackaDiskJHealth", "widgets": ["text"],
                      "sample_text": "S11 Pro OK      desg.  4%"},
    "DISK_J_TEMP": {"group": "Disco J:", "label": "Temperatura (cor por nível)", "custom": "BackaDiskJTemp", "widgets": ["text"],
                    "sample_text": " 37°C", "temp_levels": {"AMARELO": 55, "VERMELHO": 70}},
    "NET_DOWN": {"group": "Rede", "label": "Download", "path": ["NET", "ETH", "DOWNLOAD"], "interval_at": ["NET"], "interval": 1,
                 "widgets": ["text", "line_graph"], "sample": 30, "sample_text": " 12.4M"},
    "NET_UP": {"group": "Rede", "label": "Upload", "path": ["NET", "ETH", "UPLOAD"], "interval_at": ["NET"], "interval": 1,
               "widgets": ["text", "line_graph"], "sample": 10, "sample_text": "  1.1M"},
    "PING": {"group": "Rede", "label": "Ping (ms)", "path": ["PING"], "interval_at": ["PING"], "interval": 3,
             "widgets": ["text", "bar", "line_graph"], "sample": 12, "sample_text": "    12ms", "max": 150},
    # Conexão: no editor, escolhe-se qual adaptador é o cabo e qual é o Wi-Fi
    "NET_CABLE": {"group": "Rede", "label": "Cabo de rede conectado", "custom": "BackaNetCable", "net_kind": "cabo",
                  "widgets": ["text", "icon"], "sample_text": "Cabo: 1 Gbps          ",
                  "states": [["OK", "Conectado"], ["DESCONECTADO", "Desconectado"]],
                  "default_icons": {"OK": "sym:plug-connected:outline:90,220,120",
                                    "DESCONECTADO": "sym:plug-connected-x:outline:255,77,77"},
                  "text_states": [["OK", "Conectado", None], ["DESCONECTADO", "Desconectado", [255, 77, 77]]]},
    "NET_WIFI": {"group": "Rede", "label": "Wi-Fi conectado", "custom": "BackaNetWifi", "net_kind": "wifi",
                 "widgets": ["text", "icon"], "sample_text": "Wi-Fi: MinhaRede 82%  ",
                 "states": [["OK", "Conectado"], ["DESCONECTADO", "Desconectado"]],
                 "default_icons": {"OK": "sym:wifi:outline:90,220,120", "DESCONECTADO": "sym:wifi-off:outline:255,77,77"},
                 "text_states": [["OK", "Conectado", None], ["DESCONECTADO", "Desconectado", [255, 77, 77]]]},
    "DATE": {"group": "Data e hora", "label": "Data", "path": ["DATE", "DAY"], "interval_at": ["DATE"], "interval": 1,
             "widgets": ["text"], "format": "EEE, dd/MM/yyyy"},
    "TIME": {"group": "Data e hora", "label": "Hora", "path": ["DATE", "HOUR"], "interval_at": ["DATE"], "interval": 1,
             "widgets": ["text"], "format": "HH:mm:ss"},
    "UPTIME": {"group": "Data e hora", "label": "Tempo ligado", "path": ["UPTIME", "FORMATTED"], "interval_at": ["UPTIME"],
               "interval": 5, "widgets": ["text"], "sample_text": "0d 04:12:33"},
    "WEATHER": {"group": "Extras", "label": "Clima (Open-Meteo)", "custom": "BackaWeather", "widgets": ["weather"],
                "sample_text": " 20°C Céu limpo   ", "sample_icon": "clear_night"},
    "ALERT": {"group": "Extras", "label": "Ícone de alerta", "custom": "BackaAlert", "widgets": ["icon"],
              "states": [["AMARELO", "Atenção"], ["VERMELHO", "Crítico"]],
              "default_icons": {"AMARELO": "alert_warn", "VERMELHO": "alert_crit"}},
    "STATUS_BORDER": {"group": "Extras", "label": "Borda de status", "custom": "BackaStatusBorder", "widgets": ["border"]},
    # Throttle: ícone só aparece quando há redução de clock; o texto muda de cor conforme o estado
    "CPU_THROTTLE": {"group": "CPU", "label": "Throttle (limite de temperatura)", "custom": "BackaCpuThrottle",
                     "widgets": ["text", "icon"], "sample_text": "Sem limite  ",
                     "states": [["TERMICO", "Térmico"]], "default_icons": {"TERMICO": "sym:flame:filled:255,77,77"},
                     "text_states": [["OK", "Sem limite", None], ["TERMICO", "Térmico", [255, 77, 77]]]},
    "GPU_THROTTLE": {"group": "GPU", "label": "Throttle (temperatura / energia)", "custom": "BackaGpuThrottle",
                     "widgets": ["text", "icon"], "sample_text": "Sem limite  ",
                     "states": [["TERMICO", "Térmico"], ["ENERGIA", "Limite de energia"]],
                     "default_icons": {"TERMICO": "sym:flame:filled:255,77,77", "ENERGIA": "sym:bolt:filled:255,200,0"},
                     "text_states": [["OK", "Sem limite", None], ["TERMICO", "Térmico", [255, 77, 77]],
                                     ["ENERGIA", "Limite de energia", [255, 200, 0]]]},
    "POWER_MODE": {"group": "Sistema", "label": "Modo de energia", "custom": "BackaPowerMode", "widgets": ["text"],
                   "sample_text": "Alto desempenho     "},
    "UPDATE_WINDOWS": {"group": "Sistema", "label": "Atualizações do Windows", "custom": "BackaWinUpdate",
                       "widgets": ["text", "icon"], "sample_text": "Windows: 2 atualiz.   ",
                       "states": [["ATIVO", "Atualização disponível"]],
                       "default_icons": {"ATIVO": "sym:brand-windows:filled:77,166,255"},
                       "text_states": [["OK", "Em dia", None], ["ATIVO", "Atualização disponível", [255, 200, 0]]]},
    "UPDATE_NVIDIA": {"group": "Sistema", "label": "Driver NVIDIA novo", "custom": "BackaNvidiaUpdate",
                      "widgets": ["text", "icon"], "sample_text": "Driver 621.14 novo    ",
                      "states": [["ATIVO", "Driver novo disponível"]],
                      "default_icons": {"ATIVO": "sym:device-desktop-down:outline:118,185,0"},
                      "text_states": [["OK", "Em dia", None], ["ATIVO", "Driver novo disponível", [255, 200, 0]]]},
}

SOURCES.update({
    "RAM_TEMP": {"group": "RAM", "label": "Temperatura (pente mais quente)", "custom": "BackaRamTemp", "widgets": ["text"],
                 "sample_text": " 42°C", "temp_levels": {"AMARELO": 60, "VERMELHO": 75}},
    "TOP_CPU": {"group": "Sistema", "label": "Processo que mais usa CPU", "custom": "BackaTopCpu", "widgets": ["text"],
                "sample_text": "chrome          12%"},
    "TOP_RAM": {"group": "Sistema", "label": "Processo que mais usa RAM", "custom": "BackaTopRam", "widgets": ["text"],
                "sample_text": "chrome          3.2 GB"},
})

# Leitura e escrita de cada disco (MB/s)
for _letter in ("C", "J"):
    for _key, _label, _cls in (("READ", "Leitura (MB/s)", "Read"), ("WRITE", "Escrita (MB/s)", "Write")):
        SOURCES[f"DISK_{_letter}_{_key}"] = {"group": f"Disco {_letter}:", "label": _label, "custom": f"BackaDisk{_letter}{_cls}",
                                             "widgets": ["text", "bar", "line_graph"], "sample": 20,
                                             "sample_text": " 12.4 MB/s", "max": 500}

# Sensores escolhidos no editor (cada item mostra um sensor físico, da lista que o monitor grava):
#   fans (FAN_1 ... FAN_8) e temperaturas extras da placa-mãe/RAM (TEMP_1 ... TEMP_4)
FAN_SLOTS, TEMP_SLOTS = 8, 4
for _n in range(1, FAN_SLOTS + 1):
    SOURCES[f"FAN_{_n}"] = {"group": "Fans", "label": f"Fan {_n} (RPM)", "custom": f"BackaFan{_n}", "hw_kind": "fan",
                            "hw_slot": _n, "widgets": ["text", "bar", "line_graph"], "sample": 55,
                            "sample_text": " 1250 RPM", "max": 2000}
for _n in range(1, TEMP_SLOTS + 1):
    SOURCES[f"TEMP_{_n}"] = {"group": "Temperaturas extras", "label": f"Temperatura {_n}", "custom": f"BackaTemp{_n}",
                             "hw_kind": "temp", "hw_slot": _n, "widgets": ["text"], "sample_text": " 37°C",
                             "temp_levels": {"AMARELO": 60, "VERMELHO": 80}}


def icon_spec(entry) -> str:
    # Ícone escolhido no editor ({icon, style, color}) -> texto usado pelo monitor: "sym:<nome>:<estilo>:<r>,<g>,<b>"
    if isinstance(entry, str):
        return entry
    r, g, b = _rgb(entry.get("color"), (240, 240, 245))
    return f"sym:{entry.get('icon', '')}:{entry.get('style', 'outline')}:{r},{g},{b}"


def item_state_icon(item: dict, state: str) -> str:
    src = SOURCES.get(item.get("source"), {})
    chosen = (item.get("state_icons") or {}).get(state)
    return icon_spec(chosen) if chosen else (src.get("default_icons") or {}).get(state, src.get("sample_icon", ""))

STATIC_KINDS = {"panel": "Painel", "label": "Texto", "image": "Imagem", "symbol": "Ícone", "line": "Linha"}

GRAY = (130, 138, 150)


def list_fonts():
    return sorted(str(p.relative_to(FONTS_DIR)).replace("\\", "/") for p in FONTS_DIR.rglob("*.tt[fc]"))


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONTS_DIR / name), int(size))
    except Exception:
        return ImageFont.truetype(str(FONTS_DIR / "roboto-mono/RobotoMono-Bold.ttf"), int(size))


_symbol_catalog = None


def symbol_catalog() -> dict:
    global _symbol_catalog
    if _symbol_catalog is None:
        try:
            _symbol_catalog = json.loads((SYMBOLS_DIR / "catalog.json").read_text(encoding="utf-8"))
        except Exception:
            _symbol_catalog = {"version": "", "suggested": [], "icons": {}}
    return _symbol_catalog


def _draw_symbol(img: Image.Image, item: dict):
    # Ícone da biblioteca: um caractere da fonte de ícones, centralizado num quadrado de "size" px, na cor escolhida.
    # Se o estilo preenchido não existir para esse ícone, usa o de contorno.
    entry = symbol_catalog()["icons"].get(item.get("icon") or "")
    if not entry:
        return
    size = max(4, int(item.get("size", 32)))
    filled = item.get("style") == "filled" and entry[1]
    code = entry[1] if filled else entry[0]
    if not code:
        code, filled = entry[1], True
    try:
        font = ImageFont.truetype(str(SYMBOLS_DIR / ("tabler-icons-filled.ttf" if filled else "tabler-icons.ttf")), size)
    except Exception:
        return
    ImageDraw.Draw(img).text((int(item["x"]) + size / 2, int(item["y"]) + size / 2), chr(code), font=font,
                             fill=_rgb(item.get("color")), anchor="mm")


def _rgb(c, default=(255, 255, 255)):
    if c is None:
        return default
    if isinstance(c, str):
        c = [int(v) for v in c.replace(" ", "").split(",")]
    return tuple(int(v) for v in c[:3])


def _yaml_color(c):
    r, g, b = _rgb(c)
    return f"{r}, {g}, {b}"


# ---------------------------------------------------------------------------
# Leitura / gravação
# ---------------------------------------------------------------------------
def list_presets():
    return sorted(p.parent.name for p in THEMES_DIR.glob(f"*/{LAYOUT_FILE}"))


def load_layout(name: str) -> dict:
    with open(THEMES_DIR / name / LAYOUT_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_layout(name: str, layout: dict):
    folder = THEMES_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    layout = dict(layout, name=name)
    with open(folder / LAYOUT_FILE, "w", encoding="utf-8") as f:
        json.dump(layout, f, ensure_ascii=False, indent=2)


def validate_layout(layout: dict) -> list:
    # Retorna lista de problemas (vazia = ok). Cada fonte de dado + widget só pode aparecer uma vez na tela
    problems, seen = [], set()
    for item in layout.get("items", []):
        if item.get("kind") == "data":
            src, widget = item.get("source"), item.get("widget")
            if src not in SOURCES:
                problems.append(f"Fonte de dados desconhecida: {src}")
                continue
            if widget not in SOURCES[src]["widgets"]:
                problems.append(f"{src} não aceita o widget {widget}")
            if (src, widget) in seen:
                problems.append(f"'{SOURCES[src]['group']} - {SOURCES[src]['label']}' ({WIDGET_LABELS[widget]}) aparece mais de uma vez")
            seen.add((src, widget))
        elif item.get("kind") not in STATIC_KINDS:
            problems.append(f"Tipo de item desconhecido: {item.get('kind')}")
    return problems


# ---------------------------------------------------------------------------
# Desenho dos itens estáticos (fundo)
# ---------------------------------------------------------------------------
def _draw_background(layout: dict, folder: Path) -> Image.Image:
    w, h = layout.get("width", 480), layout.get("height", 320)
    bg = layout.get("background") or {"type": "none"}
    img = Image.new("RGB", (w, h), (0, 0, 0))
    if bg.get("type") == "color":
        img.paste(_rgb(bg.get("color"), (0, 0, 0)), (0, 0, w, h))
    elif bg.get("type") == "image" and bg.get("src"):
        try:
            src = Image.open(folder / bg["src"]).convert("RGB")
            # "cover": preenche a tela inteira, cortando o que sobrar
            scale = max(w / src.width, h / src.height)
            src = src.resize((math.ceil(src.width * scale), math.ceil(src.height * scale)), Image.LANCZOS)
            left, top = (src.width - w) // 2, (src.height - h) // 2
            img.paste(src.crop((left, top, left + w, top + h)), (0, 0))
        except Exception:
            pass
    d = ImageDraw.Draw(img)

    for item in layout.get("items", []):
        if item.get("hidden"):
            continue
        kind = item.get("kind")
        if kind == "panel":
            x, y, iw, ih = item["x"], item["y"], item["w"], item["h"]
            outline = _rgb(item["outline"]) if item.get("outline") else None
            fill = _rgb(item["fill"]) if item.get("fill") else None
            d.rounded_rectangle((x, y, x + iw, y + ih), radius=int(item.get("radius", 0)), fill=fill,
                                outline=outline, width=int(item.get("outline_width", 1)) if outline else 0)
        elif kind == "label":
            d.text((item["x"], item["y"]), item.get("text", ""), font=_font(item.get("font", "roboto/Roboto-Bold.ttf"), item.get("size", 12)),
                   fill=_rgb(item.get("color")), anchor=item.get("anchor", "la"))
        elif kind == "line":
            d.line((item["x"], item["y"], item["x2"], item["y2"]), fill=_rgb(item.get("color")), width=int(item.get("width", 1)))
        elif kind == "image" and item.get("src"):
            try:
                pic = Image.open(folder / item["src"]).convert("RGBA").resize((int(item["w"]), int(item["h"])), Image.LANCZOS)
                img.paste(pic, (int(item["x"]), int(item["y"])), pic)
            except Exception:
                pass
        elif kind == "symbol":
            _draw_symbol(img, item)
        elif kind == "data" and item.get("widget") == "bar" and item.get("track"):
            # Trilho da barra de progresso: faz parte do fundo
            d.rectangle((item["x"], item["y"], item["x"] + item["w"] - 1, item["y"] + item["h"] - 1), fill=_rgb(item["track"]))
    return img


# ---------------------------------------------------------------------------
# Compilação: layout.json -> theme.yaml + background.png
# ---------------------------------------------------------------------------
def _text_block(item: dict) -> dict:
    anchor = item.get("anchor", "lt")
    block = {"SHOW": True, "X": int(item["x"]), "Y": int(item["y"]),
             "FONT": item.get("font", "roboto-mono/RobotoMono-Bold.ttf"), "FONT_SIZE": int(item.get("size", 14)),
             "FONT_COLOR": _yaml_color(item.get("color", (240, 240, 245))), "BACKGROUND_IMAGE": "background.png",
             "ANCHOR": anchor, "ALIGN": {"r": "right", "m": "center"}.get(anchor[0], "left")}
    if "show_unit" in item:
        block["SHOW_UNIT"] = bool(item["show_unit"])
    if item.get("format"):
        block["FORMAT"] = item["format"]
    return block


def _widget_block(item: dict) -> dict:
    widget = item["widget"]
    if widget == "text":
        return _text_block(item)
    src_max = SOURCES.get(item.get("source"), {}).get("max", 100)
    base = {"SHOW": True, "X": int(item["x"]), "Y": int(item["y"]), "BACKGROUND_IMAGE": "background.png",
            "MIN_VALUE": item.get("min", 0), "MAX_VALUE": item.get("max", src_max)}
    if widget == "bar":
        base.update(WIDTH=int(item["w"]), HEIGHT=int(item["h"]), BAR_COLOR=_yaml_color(item.get("color")),
                    BAR_OUTLINE=bool(item.get("outline", False)))
    elif widget == "line_graph":
        base.update(WIDTH=int(item["w"]), HEIGHT=int(item["h"]), LINE_COLOR=_yaml_color(item.get("color")),
                    LINE_WIDTH=int(item.get("line_width", 1)), AUTOSCALE=bool(item.get("autoscale", False)),
                    AXIS=bool(item.get("axis", False)), HISTORY_SIZE=int(item.get("history", 50)))
    elif widget == "radial":
        # No editor, x/y/w/h é a caixa do medidor; no tema, X/Y é o centro
        r = int(min(item["w"], item["h"]) // 2)
        base.update(X=int(item["x"] + r), Y=int(item["y"] + r), RADIUS=r - int(item.get("thickness", 10)) // 2,
                    WIDTH=int(item.get("thickness", 10)), ANGLE_START=item.get("angle_start", 135),
                    ANGLE_END=item.get("angle_end", 45), ANGLE_STEPS=1, ANGLE_SEP=0, CLOCKWISE=True,
                    BAR_COLOR=_yaml_color(item.get("color")), SHOW_TEXT=bool(item.get("show_text", True)),
                    SHOW_UNIT=True, FONT=item.get("font", "roboto-mono/RobotoMono-Bold.ttf"),
                    FONT_SIZE=int(item.get("size", 16)), FONT_COLOR=_yaml_color(item.get("text_color", (240, 240, 245))))
    return base


def weather_text_pos(item: dict):
    # Texto do clima fica à direita do ícone, centralizado na altura dele
    icon = int(item.get("icon_size", 22))
    return int(item["x"]) + icon + 4, int(item["y"]) + max(0, (icon - int(item.get("size", 12))) // 2)


def _set_path(root: dict, path: list, value):
    node = root
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value


def build_theme(layout: dict) -> dict:
    theme = {"author": layout.get("author", ""),
             "display": {"DISPLAY_SIZE": '3.5"', "DISPLAY_ORIENTATION": layout.get("orientation", "landscape")},
             "static_images": {"BACKGROUND": {"PATH": "background.png", "X": 0, "Y": 0,
                                              "WIDTH": layout.get("width", 480), "HEIGHT": layout.get("height", 320)}},
             "STATS": {}}
    stats = theme["STATS"]
    custom = {}

    for item in layout.get("items", []):
        if item.get("kind") != "data" or item.get("hidden"):
            continue
        src = SOURCES[item["source"]]
        widget = item["widget"]
        if "custom" in src:
            block = custom.setdefault(src["custom"], {})
            if widget in WIDGET_KEYS:
                block[WIDGET_KEYS[widget]] = _widget_block(item)
            if widget == "weather":
                tx, ty = weather_text_pos(item)
                block["TEXT"] = _text_block(dict(item, x=tx, y=ty))
                block["ICON"] = {"X": int(item["x"]), "Y": int(item["y"]), "SIZE": int(item.get("icon_size", 22))}
            elif widget == "icon":
                block["ICON"] = {"X": int(item["x"]), "Y": int(item["y"]), "SIZE": int(item.get("size", 22))}
                if item.get("state_icons"):
                    block["ICON"]["STATES"] = {state: icon_spec(entry) for state, entry in item["state_icons"].items()
                                               if entry and state in dict(src.get("states") or [])}
            elif widget == "border":
                block["WIDTH"] = int(item.get("thickness", 4))
                if item.get("colors"):
                    block["COLORS"] = {k: list(_rgb(v)) for k, v in item["colors"].items()}
            if src.get("temp_levels"):
                block["TEMP_LEVELS"] = dict(item.get("temp_levels") or src["temp_levels"])
            if src.get("text_states") and widget == "text":
                # Cor do texto em cada estado; "OK" usa a cor normal do item
                chosen = item.get("state_colors") or {}
                block["STATE_COLORS"] = {state: list(_rgb(chosen.get(state) or default or item.get("color", (240, 240, 245))))
                                         for state, _, default in src["text_states"]}
            if src.get("hw_slot") and item.get("sensor"):
                block["SENSOR"] = str(item["sensor"])
            if src.get("net_kind") and item.get("adapter"):
                block["ADAPTER"] = str(item["adapter"])
            if src.get("net_kind") and widget == "icon" and item.get("hide_ok"):
                block["ICON"]["HIDE_OK"] = True
            if src.get("fast_refresh") and widget == "text":
                # Ritmo próprio do texto (ex.: FPS a cada 1 s), independente do intervalo dos sensores personalizados
                block["REFRESH"] = float(item.get("interval") or src["fast_refresh"])
        else:
            _set_path(stats, src["path"] + [WIDGET_KEYS[widget]], _widget_block(item))
            _set_path(stats, src["interval_at"] + ["INTERVAL"], int(item.get("interval", src.get("interval", 2))))

    if custom:
        stats["CUSTOM"] = {"INTERVAL": int(layout.get("custom_interval", 3)), **custom}
    return theme


def compile_layout(name: str, layout: dict = None) -> list:
    # Gera background.png, theme.yaml e preview.png na pasta do tema. Retorna problemas (vazio = ok)
    layout = layout or load_layout(name)
    problems = validate_layout(layout)
    if problems:
        return problems
    folder = THEMES_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    _draw_background(layout, folder).save(folder / "background.png")
    header = ("# Tema gerado pelo editor Backa a partir de layout.json - edite pelo editor, não à mão\n"
              "# (alterações feitas aqui são sobrescritas ao salvar no editor)\n---\n")
    with open(folder / "theme.yaml", "w", encoding="utf-8") as f:
        f.write(header + yaml.safe_dump(build_theme(layout), allow_unicode=True, sort_keys=False))
    render_preview(layout, folder)[0].save(folder / "preview.png")
    return []


# ---------------------------------------------------------------------------
# Prévia com dados de exemplo (editor): retorna a imagem e a caixa (x, y, w, h) de cada item
# ---------------------------------------------------------------------------
def _sample_text(item: dict) -> str:
    src = SOURCES[item["source"]]
    if item["source"] in ("DATE", "TIME"):
        try:
            from babel.dates import format_datetime
            return format_datetime(datetime.datetime.now(), item.get("format") or src["format"], locale="pt_BR")
        except Exception:
            return datetime.datetime.now().strftime("%d/%m/%Y" if item["source"] == "DATE" else "%H:%M:%S")
    text = src.get("sample_text", "--")
    if item.get("show_unit") is False:
        text = text.replace("%", "").replace(" GHz", "").replace(" FPS", "")
    return text


def _sample_color(item: dict):
    src = SOURCES[item["source"]]
    if src.get("temp_levels"):
        return (90, 220, 120)  # temperaturas aparecem em verde no exemplo
    return _rgb(item.get("color", (240, 240, 245)))


def _icon(name: str, size: int = 22) -> Image.Image:
    # name: PNG de res/backa/icons ou "sym:<nome>:<estilo>:<r>,<g>,<b>" (biblioteca Tabler)
    size = int(size)
    if name.startswith("sym:"):
        _, icon, style, color = (name.split(":") + ["", "", ""])[:4]
        pic = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        _draw_symbol(pic, {"icon": icon, "style": style, "color": color or "240,240,245", "x": 0, "y": 0, "size": size})
        return pic
    try:
        return Image.open(ICONS_DIR / f"{name}.png").convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def render_preview(layout: dict, folder: Path = None):
    folder = folder or (THEMES_DIR / layout.get("name", ""))
    img = _draw_background(layout, folder).convert("RGBA")
    d = ImageDraw.Draw(img)
    boxes = {}

    for item in layout.get("items", []):
        iid = item.get("id")
        kind = item.get("kind")
        if kind == "panel" or (kind == "image"):
            boxes[iid] = [item["x"], item["y"], item["w"], item["h"]]
        elif kind == "label":
            bb = d.textbbox((item["x"], item["y"]), item.get("text", "") or " ",
                            font=_font(item.get("font", "roboto/Roboto-Bold.ttf"), item.get("size", 12)), anchor=item.get("anchor", "la"))
            boxes[iid] = [bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1]]
        elif kind == "symbol":
            size = int(item.get("size", 32))
            boxes[iid] = [item["x"], item["y"], size, size]
        elif kind == "line":
            x0, x1 = sorted((item["x"], item["x2"]))
            y0, y1 = sorted((item["y"], item["y2"]))
            boxes[iid] = [x0, y0, max(x1 - x0, 1), max(y1 - y0, 1)]
        if kind != "data" or item.get("hidden"):
            continue

        widget, src = item["widget"], SOURCES[item["source"]]
        x, y = item["x"], item["y"]
        if widget == "text":
            font = _font(item.get("font", "roboto-mono/RobotoMono-Bold.ttf"), item.get("size", 14))
            text = _sample_text(item)
            d.text((x, y), text, font=font, fill=_sample_color(item), anchor=item.get("anchor", "lt"))
            bb = d.textbbox((x, y), text, font=font, anchor=item.get("anchor", "lt"))
            boxes[iid] = [bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1]]
        elif widget == "bar":
            w, h = item["w"], item["h"]
            fill_w = int(w * src.get("sample", 50) / 100)
            if fill_w > 0:
                d.rectangle((x, y, x + fill_w - 1, y + h - 1), fill=_rgb(item.get("color")))
            boxes[iid] = [x, y, w, h]
        elif widget == "line_graph":
            w, h = item["w"], item["h"]
            pts = [(x + i * (w - 1) / 39, y + h - 1 - (h - 2) * (0.35 + 0.25 * math.sin(i / 4) + 0.1 * math.sin(i * 1.7))) for i in range(40)]
            d.line(pts, fill=_rgb(item.get("color")), width=int(item.get("line_width", 1)))
            boxes[iid] = [x, y, w, h]
        elif widget == "radial":
            w, h = item["w"], item["h"]
            size = min(w, h)
            t = int(item.get("thickness", 10))
            a0, a1 = item.get("angle_start", 135), item.get("angle_end", 45)
            span = (a1 - a0) % 360 or 360
            d.arc((x + t / 2, y + t / 2, x + size - t / 2, y + size - t / 2), a0 + 90, a0 + 90 + span, fill=(40, 44, 54), width=t)
            d.arc((x + t / 2, y + t / 2, x + size - t / 2, y + size - t / 2), a0 + 90, a0 + 90 + span * src.get("sample", 50) / 100,
                  fill=_rgb(item.get("color")), width=t)
            if item.get("show_text", True):
                d.text((x + size / 2, y + size / 2), _sample_text(dict(item, widget="text")).strip(),
                       font=_font(item.get("font", "roboto-mono/RobotoMono-Bold.ttf"), item.get("size", 16)),
                       fill=_rgb(item.get("text_color", (240, 240, 245))), anchor="mm")
            boxes[iid] = [x, y, size, size]
        elif widget == "weather":
            icon = int(item.get("icon_size", 22))
            img.alpha_composite(_icon(src["sample_icon"], icon), (int(x), int(y)))
            font = _font(item.get("font", "roboto-mono/RobotoMono-Bold.ttf"), item.get("size", 12))
            tx, ty = weather_text_pos(item)
            d.text((tx, ty), src["sample_text"], font=font, fill=_rgb(item.get("color", (220, 220, 228))), anchor="lt")
            bb = d.textbbox((tx, ty), src["sample_text"], font=font, anchor="lt")
            boxes[iid] = [x, y, bb[2] - x, max(icon, bb[3] - y)]
        elif widget == "icon":
            # Mostra o ícone do primeiro estado (ex.: "Atenção" no alerta, "Térmico" no throttle)
            size = int(item.get("size", 22))
            states = src.get("states") or [[None]]
            img.alpha_composite(_icon(item_state_icon(item, states[0][0]), size), (int(x), int(y)))
            boxes[iid] = [x, y, size, size]
        elif widget == "border":
            w, h = img.size
            color = _rgb((item.get("colors") or {}).get("VERDE", (90, 220, 120)))
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=14, outline=color, width=int(item.get("thickness", 4)))
            boxes[iid] = [0, 0, w, h]
    return img.convert("RGB"), boxes
