# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Copyright (C) 2021 Matthieu Houdebine (mathoudebine)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# This file allows to add custom data source as sensors and display them in System Monitor themes
# There is no limitation on how much custom data source classes can be added to this file
# See CustomDataExample theme for the theme implementation part

import math
import platform
from abc import ABC, abstractmethod
from typing import List


# Custom data classes must be implemented in this file, inherit the CustomDataSource and implement its 2 methods
class CustomDataSource(ABC):
    @abstractmethod
    def as_numeric(self) -> float:
        # Numeric value will be used for graph and radial progress bars
        # If there is no numeric value, keep this function empty
        pass

    @abstractmethod
    def as_string(self) -> str:
        # Text value will be used for text display and radial progress bar inner text
        # Numeric value can be formatted here to be displayed as expected
        # It is also possible to return a text unrelated to the numeric value
        # If this function is empty, the numeric value will be used as string without formatting
        pass

    @abstractmethod
    def last_values(self) -> List[float]:
        # List of last numeric values will be used for plot graph
        # If you do not want to draw a line graph or if your custom data has no numeric values, keep this function empty
        pass


# Example for a custom data class that has numeric and text values
class ExampleCustomNumericData(CustomDataSource):
    # This list is used to store the last 10 values to display a line graph
    last_val = [math.nan] * 10  # By default, it is filed with math.nan values to indicate there is no data stored

    def as_numeric(self) -> float:
        # Numeric value will be used for graph and radial progress bars
        # Here a Python function from another module can be called to get data
        # Example: self.value = my_module.get_rgb_led_brightness() / audio.system_volume() ...
        self.value = 75.845

        # Store the value to the history list that will be used for line graph
        self.last_val.append(self.value)
        # Also remove the oldest value from history list
        self.last_val.pop(0)

        return self.value

    def as_string(self) -> str:
        # Text value will be used for text display and radial progress bar inner text.
        # Numeric value can be formatted here to be displayed as expected
        # It is also possible to return a text unrelated to the numeric value
        # If this function is empty, the numeric value will be used as string without formatting
        # Example here: format numeric value: add unit as a suffix, and keep 1 digit decimal precision
        return f'{self.value:>5.1f}%'
        # Important note! If your numeric value can vary in size, be sure to display it with a default size.
        # E.g. if your value can range from 0 to 9999, you need to display it with at least 4 characters every time.
        # --> return f'{self.as_numeric():>4}%'
        # Otherwise, part of the previous value can stay displayed ("ghosting") after a refresh

    def last_values(self) -> List[float]:
        # List of last numeric values will be used for plot graph
        return self.last_val


# Example for a custom data class that only has text values
class ExampleCustomTextOnlyData(CustomDataSource):
    def as_numeric(self) -> float:
        # If there is no numeric value, keep this function empty
        pass

    def as_string(self) -> str:
        # If a custom data class only has text values, it won't be possible to display graph or radial bars
        return "Python: " + platform.python_version()

    def last_values(self) -> List[float]:
        # If a custom data class only has text values, it won't be possible to display line graph
        pass


# ---------------------------------------------------------------------------
# Sensores dos presets Backa
# Os textos têm largura fixa (fonte monoespaçada) para não deixar "fantasmas" ao atualizar
# ---------------------------------------------------------------------------
import psutil

from library import config

GB = 1024 ** 3

# Letra da unidade -> (nome do SSD no LibreHardwareMonitor, apelido curto na tela)
BACKA_DISKS = {
    "C": ("KINGSTON SNV3S1000G", "NV3"),
    "J": ("XPG GAMMIX S11 Pro", "S11 Pro"),
}


def _lhm():
    # Só usa o LibreHardwareMonitor se ele estiver ativo no config.yaml (precisa de admin)
    if config.CONFIG_DATA["config"].get("HW_SENSORS", "AUTO") in ("LHM", "AUTO") and platform.system() == "Windows":
        try:
            import library.sensors.sensors_librehardwaremonitor as lhm
            return lhm
        except Exception:
            return None
    return None


def _push(history: List[float], value: float):
    history.append(value)
    history.pop(0)


class BackaVram(CustomDataSource):
    used_gb = math.nan
    total_gb = math.nan

    def as_numeric(self) -> float:
        lhm = _lhm()
        if lhm is None:
            return math.nan
        _, mem_percent, used_mb, total_mb, _ = lhm.Gpu.stats()
        self.used_gb, self.total_gb = used_mb / 1024, total_mb / 1024
        return mem_percent

    def as_string(self) -> str:
        if math.isnan(self.used_gb):
            return "  -- / -- GB"
        return f"{self.used_gb:4.1f} / {self.total_gb:3.1f} GB"

    def last_values(self) -> List[float]:
        pass


class BackaRamUsed(CustomDataSource):
    last_val = [math.nan] * 30

    def as_numeric(self) -> float:
        mem = psutil.virtual_memory()
        self.used = mem.used / GB
        _push(self.last_val, mem.percent)
        return mem.percent

    def as_string(self) -> str:
        return f"{self.used:4.1f} GB"

    def last_values(self) -> List[float]:
        return self.last_val


class BackaRamFree(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        return f"{psutil.virtual_memory().available / GB:4.1f} GB"

    def last_values(self) -> List[float]:
        pass


class _BackaDiskFree(CustomDataSource):
    letter = "C"

    def as_numeric(self) -> float:
        usage = psutil.disk_usage(f"{self.letter}:\\")
        self.free_gb = usage.free / GB
        return usage.percent

    def as_string(self) -> str:
        return f"{self.free_gb:4.0f} GB livres"

    def last_values(self) -> List[float]:
        pass


class BackaDiskCFree(_BackaDiskFree):
    letter = "C"


class BackaDiskJFree(_BackaDiskFree):
    letter = "J"


def _disk_health(letter: str):
    # Retorna (ok, desgaste %, temperatura °C) do SSD pela leitura SMART do LibreHardwareMonitor
    hw_name, _ = BACKA_DISKS[letter]
    lhm = _lhm()
    temp = wear = spare = spare_min = None
    if lhm is not None:
        for hw in lhm.handle.Hardware:
            if hw.HardwareType == lhm.Hardware.HardwareType.Storage and str(hw.Name) == hw_name:
                hw.Update()
                for s in hw.Sensors:
                    name, value = str(s.Name), s.Value
                    if value is None:
                        continue
                    if s.SensorType == lhm.Hardware.SensorType.Temperature and temp is None:
                        temp = float(value)
                    elif name == "Percentage Used":
                        wear = float(value)
                    elif name == "Available Spare":
                        spare = float(value)
                    elif name == "Available Spare Threshold":
                        spare_min = float(value)
    if temp is None and wear is None:
        return None, None, None
    ok = (wear is None or wear < 90) and (spare is None or spare_min is None or spare > spare_min)
    return ok, wear, temp


class _BackaDiskHealth(CustomDataSource):
    letter = "C"

    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        _, short = BACKA_DISKS[self.letter]
        ok, wear, temp = _disk_health(self.letter)
        if ok is None:
            return f"{short:<7} saúde: --"
        status = "OK" if ok else "ATENÇÃO"
        wear_txt = f"{wear:3.0f}%" if wear is not None else " --%"
        return f"{short:<7} {status:<7} desg.{wear_txt}"

    def last_values(self) -> List[float]:
        pass


class BackaDiskCHealth(_BackaDiskHealth):
    letter = "C"


class BackaDiskJHealth(_BackaDiskHealth):
    letter = "J"


# ---------------------------------------------------------------------------
# Temperaturas com cor por nível (verde / amarelo / vermelho)
# Limites individuais no theme.yaml, em cada sensor:
#   TEMP_LEVELS: { AMARELO: 70, VERMELHO: 85 }   -> verde < 70 <= amarelo < 85 <= vermelho
# Cores opcionais por sensor: TEMP_COLORS: { VERDE: ..., AMARELO: ..., VERMELHO: ... }
# ---------------------------------------------------------------------------
TEMP_COLORS_DEFAULT = {"VERDE": (90, 220, 120), "AMARELO": (255, 200, 0), "VERMELHO": (255, 70, 70)}
LEVEL_NAMES = ("VERDE", "AMARELO", "VERMELHO")


def _no_value(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _temp_level(sensor_name: str, value) -> int:
    # 0 = verde, 1 = amarelo, 2 = vermelho, conforme TEMP_LEVELS do sensor no theme.yaml
    if _no_value(value):
        return 0
    levels = (config.THEME_DATA["STATS"]["CUSTOM"].get(sensor_name) or {}).get("TEMP_LEVELS") or {}
    if value >= levels.get("VERMELHO", 85):
        return 2
    if value >= levels.get("AMARELO", 70):
        return 1
    return 0


def _temp_text(sensor_name: str, value, width: int = 3) -> str:
    # Formata a temperatura e ajusta a cor do texto no tema conforme o nível
    sensor_cfg = config.THEME_DATA["STATS"]["CUSTOM"].get(sensor_name) or {}
    text_cfg = sensor_cfg.get("TEXT")
    if _no_value(value):
        if text_cfg is not None:
            text_cfg["FONT_COLOR"] = (130, 138, 150)
        return f"{'--':>{width}}°C"
    colors = {**TEMP_COLORS_DEFAULT, **(sensor_cfg.get("TEMP_COLORS") or {})}
    if text_cfg is not None:
        text_cfg["FONT_COLOR"] = colors[LEVEL_NAMES[_temp_level(sensor_name, value)]]
    return f"{value:{width}.0f}°C"


class BackaCpuTemp(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        lhm = _lhm()
        return _temp_text("BackaCpuTemp", lhm.Cpu.temperature() if lhm else None)

    def last_values(self) -> List[float]:
        pass


class BackaGpuTemp(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        lhm = _lhm()
        return _temp_text("BackaGpuTemp", lhm.Gpu.stats()[4] if lhm else None)

    def last_values(self) -> List[float]:
        pass


class _BackaDiskTemp(CustomDataSource):
    letter = "C"

    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        _, _, temp = _disk_health(self.letter)
        return _temp_text(type(self).__name__, temp)

    def last_values(self) -> List[float]:
        pass


class BackaDiskCTemp(_BackaDiskTemp):
    letter = "C"


class BackaDiskJTemp(_BackaDiskTemp):
    letter = "J"


# ---------------------------------------------------------------------------
# Ícones (clima e alerta): desenhados direto na tela, só quando mudam
# ---------------------------------------------------------------------------
import os
import subprocess
import time
from pathlib import Path

import requests
from PIL import Image

from library.log import logger

ICON_SIZE = 22
_bg_cache = None
_drawn_icons = {}


def _theme_dir() -> Path:
    return Path(config.MAIN_DIRECTORY) / "res" / "themes" / config.CONFIG_DATA["config"]["THEME"]


ICONS_DIR = Path(config.MAIN_DIRECTORY) / "res" / "backa" / "icons"


def _icon_pos(sensor_name: str, default):
    # Posição e tamanho do ícone definidos no tema (ICON: {X, Y, SIZE}); usa os padrões se o tema não definir
    icon_cfg = (config.THEME_DATA["STATS"]["CUSTOM"].get(sensor_name) or {}).get("ICON") or {}
    return int(icon_cfg.get("X", default[0])), int(icon_cfg.get("Y", default[1])), int(icon_cfg.get("SIZE", ICON_SIZE))


def _icon_image(icon: str, size: int) -> Image.Image:
    # icon: nome de um PNG em res/backa/icons, ou "sym:<nome>:<estilo>:<r>,<g>,<b>" (ícone da biblioteca Tabler)
    from library.backa import layout as backa_layout
    return backa_layout._icon(icon, size)


def _state_icon(sensor_name: str, state: str, default: str) -> str:
    # Ícone escolhido no editor para esse estado (ICON: {STATES: {estado: "sym:..."}}), ou o padrão
    states = ((config.THEME_DATA["STATS"]["CUSTOM"].get(sensor_name) or {}).get("ICON") or {}).get("STATES") or {}
    return states.get(state) or default


def _draw_icon(slot: str, icon: str, x: int, y: int, size: int = ICON_SIZE):
    # Desenha o ícone (ou apaga, se icon == "") sobre o pedaço do fundo, só se mudou desde a última vez
    global _bg_cache
    key = (icon, x, y, size)
    if _drawn_icons.get(slot) == key:
        return
    from library.display import display
    if _bg_cache is None:
        _bg_cache = Image.open(_theme_dir() / "background.png").convert("RGBA")
    tile = _bg_cache.crop((x, y, x + size, y + size)).copy()
    if icon:
        tile.alpha_composite(_icon_image(icon, size))
    display.lcd.DisplayPILImage(tile.convert("RGB"), x, y)
    _drawn_icons[slot] = key


def backa_reset_caches():
    # Chamado pelo monitor ao trocar o tema sem reiniciar: força redesenhar ícones e borda com o fundo novo
    global _bg_cache
    _bg_cache = None
    _drawn_icons.clear()
    _border["level"] = None
    _status["time"] = 0.0
    globals().get("_fps_draw", {})["last"] = None


# --- Clima (Open-Meteo: gratuito, sem chave) ---
WEATHER_REFRESH_S = 600
_weather = {"time": 0.0, "temp": None, "code": None, "is_day": 1}

# Código WMO -> (ícone de dia, ícone de noite, texto)
_WMO = [
    ((0, 1), "clear_day", "clear_night", None),
    ((2,), "partly_day", "partly_night", "Parc. nubl."),
    ((3,), "cloudy", "cloudy", "Nublado"),
    ((45, 48), "fog", "fog", "Neblina"),
    ((51, 53, 55, 56, 57), "drizzle", "drizzle", "Garoa"),
    ((61, 63, 65, 66, 67), "rain", "rain", "Chuva"),
    ((80, 81, 82), "rain", "rain", "Pancadas"),
    ((71, 73, 75, 77, 85, 86), "snow", "snow", "Neve"),
    ((95, 96, 99), "storm", "storm", "Tempestade"),
]


def _update_weather():
    if time.time() - _weather["time"] < WEATHER_REFRESH_S:
        return
    _weather["time"] = time.time()
    cfg = config.CONFIG_DATA["config"]
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=8, params={
            "latitude": cfg.get("WEATHER_LATITUDE"),
            "longitude": cfg.get("WEATHER_LONGITUDE"),
            "current": "temperature_2m,weather_code,is_day",
            "timezone": "America/Sao_Paulo",
        })
        cur = r.json()["current"]
        _weather.update(temp=cur["temperature_2m"], code=cur["weather_code"], is_day=cur["is_day"])
    except Exception as e:
        logger.warning("Clima: falha ao consultar Open-Meteo (%s)" % e)
        _weather["time"] = time.time() - WEATHER_REFRESH_S + 60  # tenta de novo em 1 min


class BackaWeather(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        try:
            _update_weather()
            code = _weather["code"]
            if code is None:
                _draw_icon("weather", "", *_icon_pos("BackaWeather", (172, 8)))
                return f"{'--°C':>5} {'sem dados':<11}"
            day = _weather["is_day"] == 1
            icon, label = "cloudy", "Nublado"
            for codes, icon_day, icon_night, text in _WMO:
                if code in codes:
                    icon = icon_day if day else icon_night
                    label = text or ("Ensolarado" if day else "Céu limpo")
                    break
            _draw_icon("weather", icon, *_icon_pos("BackaWeather", (172, 8)))
            return f"{_weather['temp']:>3.0f}°C {label:<11}"
        except Exception as e:
            logger.warning("Clima: %s" % e)
            return f"{'--°C':>5} {'':<11}"

    def last_values(self) -> List[float]:
        pass


# --- Throttle (redução de clock) ---
_throttle = {"time": 0.0, "termico": False, "energia": False}


def _gpu_throttle():
    # Pergunta à NVIDIA por que a placa está reduzindo o clock (a cada 3 s). Retorna {"termico": bool, "energia": bool}:
    #   termico = temperatura (hw/sw thermal slowdown) ou freio de energia do hardware (hw_power_brake)
    #   energia = chegou no limite de potência da placa (sw_power_cap): comum com a GPU em 100%, não é defeito
    if time.time() - _throttle["time"] < 3:
        return _throttle
    _throttle["time"] = time.time()
    names = ("hw_thermal_slowdown", "sw_thermal_slowdown", "hw_power_brake_slowdown", "sw_power_cap")
    for prefix in ("clocks_event_reasons", "clocks_throttle_reasons"):
        fields = ",".join(f"{prefix}.{f}" for f in names)
        try:
            out = subprocess.run(["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=5,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if out.returncode == 0:
                # Cada campo vem como "Active" ou "Not Active"
                active = [v.strip() == "Active" for v in out.stdout.strip().split(",")]
                if len(active) == len(names):
                    _throttle.update(termico=any(active[:3]), energia=active[3])
                    return _throttle
        except Exception:
            break
    _throttle.update(termico=False, energia=False)
    return _throttle


def _cpu_throttle(temp=None) -> bool:
    # A CPU AMD não informa throttle diretamente: considera "no limite" quando a temperatura chega ao limite
    # configurado em Alertas (padrão 89 °C, o máximo do Ryzen 7 7800X3D), onde ela começa a reduzir o clock
    if temp is None:
        lhm = _lhm()
        temp = lhm.Cpu.temperature() if lhm else None
    return not _no_value(temp) and temp >= _alert_rules()["cpu_throttle"]["limite"]


# --- Estado geral do PC: usado pela borda de status e pelo ícone de alerta ---
_status = {"time": 0.0, "level": 0, "reasons": []}
_alerts_cache = None


def _alert_rules() -> dict:
    global _alerts_cache
    if _alerts_cache is None:
        from library.backa import alerts
        _alerts_cache = alerts.Cached()
    return _alerts_cache.get()


def _system_status():
    # Retorna (nível 0/1/2, motivos). Recalcula no máximo a cada 2 s, porque borda e alerta consultam juntos.
    # As regras (o que conta e a partir de quanto) vêm de alertas.json (botão "Alertas…" do editor).
    if time.time() - _status["time"] < 2:
        return _status["level"], _status["reasons"]
    from library.backa.alerts import level_of, state_level
    rules = _alert_rules()
    found = []  # (nível, motivo)

    lhm = _lhm()
    cpu_t = None
    if lhm is not None:
        cpu_t = lhm.Cpu.temperature()
        _, vram, _, _, gpu_t = lhm.Gpu.stats()
        if not _no_value(cpu_t):
            found.append((level_of(rules["cpu_temp"], cpu_t), f"CPU {cpu_t:.0f}°C"))
        if not _no_value(gpu_t):
            found.append((level_of(rules["gpu_temp"], gpu_t), f"GPU {gpu_t:.0f}°C"))
        if not _no_value(vram):
            found.append((level_of(rules["vram"], vram), f"VRAM {vram:.0f}%"))
    found.append((state_level(rules["cpu_throttle"], _cpu_throttle(cpu_t)), "CPU no limite de temperatura"))
    gpu = _gpu_throttle()
    found.append((state_level(rules["gpu_throttle"], gpu["termico"]), "GPU reduzindo clock (temperatura)"))
    found.append((state_level(rules["gpu_power"], gpu["energia"]), "GPU no limite de energia"))
    ram = psutil.virtual_memory().percent
    found.append((level_of(rules["ram"], ram), f"RAM {ram:.0f}%"))
    if rules["ram_temp"]["on"]:
        ram_t = _ram_temp()
        if ram_t is not None:
            found.append((level_of(rules["ram_temp"], ram_t), f"RAM {ram_t:.0f}°C"))
    for letter in BACKA_DISKS:
        ok, _, disk_t = _disk_health(letter)
        if disk_t is not None:
            found.append((level_of(rules["ssd_temp"], disk_t), f"SSD {letter}: {disk_t:.0f}°C"))
        found.append((state_level(rules["ssd_health"], ok is False), f"SSD {letter}: saúde"))
        used = psutil.disk_usage(f"{letter}:\\").percent
        found.append((level_of(rules["disk_full"], used), f"{letter}: {used:.0f}% cheio"))
    # Atualizações só são verificadas se a regra estiver ligada (ou se houver um item delas na tela)
    if rules["update_windows"]["on"]:
        found.append((state_level(rules["update_windows"], bool(_win_update_state()["pending"])), "Atualização do Windows"))
    if rules["update_nvidia"]["on"]:
        found.append((state_level(rules["update_nvidia"], _nvidia_update_state()["available"]), "Driver NVIDIA novo"))
    if os.environ.get("BACKA_ALERT_TEST"):  # só para testar: força "atenção"
        found.append((1, "teste"))

    level = max((lv for lv, _ in found), default=0)
    reasons = [r for lv, r in found if lv == level and lv > 0]
    if level != _status["level"]:
        if level:
            logger.warning("Estado %s: %s" % (LEVEL_NAMES[level], ", ".join(reasons)))
        else:
            logger.info("Estado normalizado (VERDE)")
    _status.update(time=time.time(), level=level, reasons=reasons)
    return level, reasons


class BackaAlert(CustomDataSource):
    # Ícone no topo: aparece em amarelo ou vermelho junto com a borda de status
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        try:
            level, _ = _system_status()
            icon = ("", _state_icon("BackaAlert", "AMARELO", "alert_warn"),
                    _state_icon("BackaAlert", "VERMELHO", "alert_crit"))[level]
            _draw_icon("alert", icon, *_icon_pos("BackaAlert", (364, 8)))
        except Exception as e:
            logger.warning("Alerta: %s" % e)
        return None

    def last_values(self) -> List[float]:
        pass


# --- Borda de status: moldura da tela na cor do estado (verde / amarelo / vermelho) ---
BORDER_WIDTH = 4  # espessura padrão; o tema pode definir BackaStatusBorder: { WIDTH: n }
_border = {"level": None}


def _border_width() -> int:
    return int((config.THEME_DATA["STATS"]["CUSTOM"].get("BackaStatusBorder") or {}).get("WIDTH", BORDER_WIDTH))


def _border_frame(color, width: int, strip: int) -> Image.Image:
    # Fundo do tema + moldura colorida com brilho suave, contida na faixa de `strip` px da borda
    from PIL import ImageDraw, ImageFilter
    global _bg_cache
    if _bg_cache is None:
        _bg_cache = Image.open(_theme_dir() / "background.png").convert("RGBA")
    w, h = _bg_cache.size
    frame = _bg_cache.copy()
    solid = Image.new("RGBA", (w, h), tuple(color) + (255,))
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=14, fill=255)
    d.rounded_rectangle((width, width, w - 1 - width, h - 1 - width), radius=10, fill=0)
    glow = mask.filter(ImageFilter.GaussianBlur(3)).point(lambda v: int(v * 0.6))
    inner = Image.new("L", (w, h), 255)
    ImageDraw.Draw(inner).rectangle((strip, strip, w - 1 - strip, h - 1 - strip), fill=0)
    glow = Image.composite(glow, Image.new("L", (w, h), 0), inner)
    frame.paste(solid, (0, 0), glow)
    frame.paste(solid, (0, 0), mask)
    return frame.convert("RGB")


class BackaStatusBorder(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        try:
            level, _ = _system_status()
            if level == _border["level"]:
                return None
            from library.display import display
            cfg = config.THEME_DATA["STATS"]["CUSTOM"].get("BackaStatusBorder") or {}
            colors = {**TEMP_COLORS_DEFAULT, **(cfg.get("COLORS") or {})}
            width = max(1, _border_width())
            s = width + 4  # faixa redesenhada: a borda + o brilho
            frame = _border_frame(colors[LEVEL_NAMES[level]], width, s)
            w, h = frame.width, frame.height
            for x, y, sw, sh in ((0, 0, w, s), (0, h - s, w, s), (0, s, s, h - 2 * s), (w - s, s, s, h - 2 * s)):
                display.lcd.DisplayPILImage(frame.crop((x, y, x + sw, y + sh)), x, y)
            _border["level"] = level
        except Exception as e:
            logger.warning("Borda de status: %s" % e)
        return None

    def last_values(self) -> List[float]:
        pass


# ---------------------------------------------------------------------------
# Potência (W) da CPU e da GPU, pelo LibreHardwareMonitor
# ---------------------------------------------------------------------------
def _power_watts(kind: str):
    lhm = _lhm()
    if lhm is None:
        return None
    try:
        if kind == "cpu":
            hw = lhm.get_hw_and_update(lhm.Hardware.HardwareType.Cpu)
        else:
            hw = lhm.Gpu.get_gpu_to_use()
            if hw is not None:
                hw.Update()
        if hw is None:
            return None
        powers = [(str(s.Name), float(s.Value)) for s in hw.Sensors
                  if s.SensorType == lhm.Hardware.SensorType.Power and s.Value is not None]
        if not powers:
            return None
        # "Package" é o consumo total do chip; se não houver, usa a maior leitura
        package = [v for n, v in powers if "Package" in n]
        return package[0] if package else max(v for _, v in powers)
    except Exception:
        return None


class _BackaPower(CustomDataSource):
    kind = "cpu"
    last_val = [math.nan] * 30

    def as_numeric(self) -> float:
        self.watts = _power_watts(self.kind)
        value = math.nan if self.watts is None else self.watts
        _push(self.last_val, value)
        return value

    def as_string(self) -> str:
        return "  -- W" if self.watts is None else f"{self.watts:4.0f} W"

    def last_values(self) -> List[float]:
        return self.last_val


class BackaCpuPower(_BackaPower):
    kind = "cpu"
    last_val = [math.nan] * 30


class BackaGpuPower(_BackaPower):
    kind = "gpu"
    last_val = [math.nan] * 30


# ---------------------------------------------------------------------------
# FPS do programa em primeiro plano, medido pelo PresentMon (Intel, código aberto)
# Desligado por padrão: ative com FPS_PRESENTMON: true no config.yaml.
# O PresentMon fica em external/PresentMon/PresentMon.exe e é encerrado junto com o monitor.
# ---------------------------------------------------------------------------
import threading
from collections import deque

PRESENTMON = Path(config.MAIN_DIRECTORY) / "external" / "PresentMon" / "PresentMon.exe"
_fps = {"proc": None, "job": None, "started": False, "frames": {}, "lock": threading.Lock()}


def _fps_enabled() -> bool:
    return bool(config.CONFIG_DATA["config"].get("FPS_PRESENTMON", False))


def _kill_with_parent(proc):
    # Coloca o PresentMon num "job" do Windows: se o monitor fechar (até à força), o PresentMon fecha junto
    try:
        import win32api
        import win32con
        import win32job
        job = win32job.CreateJobObject(None, "")
        info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        info["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
        handle = win32api.OpenProcess(win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, proc.pid)
        win32job.AssignProcessToJobObject(job, handle)
        _fps["job"] = job  # o job precisa continuar aberto enquanto o monitor roda
    except Exception as e:
        logger.warning("FPS: não foi possível vincular o PresentMon ao monitor (%s)" % e)


def _drain_stderr(proc, tail):
    # Lê os avisos do PresentMon o tempo todo. Sem isso, com o jogo pesado ele avisa "eventos perdidos" várias
    # vezes, o canal enche e o PresentMon TRAVA esperando alguém ler (o FPS some e fica em "-- FPS").
    try:
        for line in proc.stderr:
            line = line.strip()
            if line:
                tail.append(line)
    except Exception:
        pass


def _read_presentmon(proc):
    # Lê a saída CSV do PresentMon: uma linha por quadro apresentado, de qualquer programa
    tail = deque(maxlen=5)
    threading.Thread(target=_drain_stderr, args=(proc, tail), daemon=True, name="PresentMon_err").start()
    pid_col = ms_col = None
    try:
        for line in proc.stdout:
            cols = line.rstrip("\r\n").split(",")
            if pid_col is None:
                if "ProcessID" in cols:
                    _fps["fails"] = 0  # o PresentMon está entregando dados: zera as tentativas
                    pid_col = cols.index("ProcessID")
                    for name in ("MsBetweenPresents", "FrameTime", "MsBetweenDisplayChange"):
                        if name in cols:
                            ms_col = cols.index(name)
                            break
                continue
            try:
                pid, ms = int(cols[pid_col]), float(cols[ms_col])
            except (ValueError, IndexError, TypeError):
                continue
            now = time.time()
            with _fps["lock"]:
                frames = _fps["frames"].setdefault(pid, deque())
                frames.append((now, ms))
                while frames and now - frames[0][0] > 2:
                    frames.popleft()
    except Exception as e:
        logger.warning("FPS: erro lendo o PresentMon (%s)" % e)
        try:
            proc.kill()
        except Exception:
            pass
    # O PresentMon fechou: registra o motivo e agenda uma nova tentativa
    try:
        proc.wait(timeout=5)
    except Exception:
        pass
    err = " | ".join(tail)[-300:]
    _fps["fails"] = _fps.get("fails", 0) + 1
    delay = min(60, 5 * _fps["fails"])
    if _fps.get("stopping"):
        return  # encerrado de propósito pelo monitor
    # "Acesso negado" (código 6) se repete enquanto um anti-cheat bloqueia: avisa uma vez, depois só no modo debug
    log = logger.debug if proc.returncode == 6 and _fps.get("denied_warned") else logger.warning
    if proc.returncode == 6 and not _fps.get("denied_warned"):
        _fps["denied_warned"] = True
        err += " (o FPS continua pela leitura direta dos eventos, se houver uma sessão disponível)"
    log("FPS: o PresentMon foi encerrado (código %s). %s Nova tentativa em %d s"
        % (proc.returncode, ("Mensagem: " + err + ".") if err else "", delay))
    _fps["proc"] = None
    _fps["started"] = False
    _fps["retry_at"] = time.time() + delay


# Sessão de captura com nome próprio por processo do monitor: se uma sessão ficar presa no Windows
# (PresentMon derrubado à força), ela não bloqueia a próxima. Sessões presas somem ao reiniciar o PC.
PRESENTMON_SESSION = "BackaFPS-%d" % os.getpid()


def backa_shutdown():
    # Chamado pelo monitor antes de sair/reiniciar: encerra o PresentMon do jeito certo, liberando a sessão de captura
    if _etw.get("reader"):
        _etw["reader"].close()  # leitor direto de eventos (a sessão BackaFPS continua, de propósito)
    proc = _fps.get("proc")
    if proc is None or proc.poll() is not None:
        return
    _fps["stopping"] = True
    try:
        subprocess.run([str(PRESENTMON), "--terminate_existing_session", "--session_name", PRESENTMON_SESSION],
                       capture_output=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        proc.wait(timeout=3)
    except Exception:
        pass
    if proc.poll() is None:
        proc.terminate()


# Reserva: leitura direta dos eventos de vídeo do Windows (library/backa/etwfps.py). Usada quando o PresentMon não
# consegue abrir uma sessão nova (ex.: anti-cheat do Battlefield 6 com o jogo aberto). Também deixa a sessão
# "BackaFPS" criada desde o início do monitor, para que um reinício durante o jogo continue tendo FPS.
_etw = {"reader": None}


def _etw_reader():
    reader = _etw["reader"]
    if reader is None:
        try:
            from library.backa import etwfps
            reader = _etw["reader"] = etwfps.Reader(
                Path(config.MAIN_DIRECTORY) / "res" / "backa" / "etw-fps-reader.ps1", logger)
        except Exception as e:
            reader = _etw["reader"] = False
            logger.warning("FPS: leitura direta indisponível (%s)" % e)
    return reader or None


def _etw_fps(pid, launch):
    # launch=True: o PresentMon está fora do ar, pode abrir o leitor. False: só usa se ele já estiver aberto.
    reader = _etw_reader()
    if reader is None:
        return None
    try:
        reader.prepare()
        if not launch and reader.proc is None:
            return None
        value = reader.fps(pid)
        if time.time() >= _etw.get("debug_at", 0):
            _etw["debug_at"] = time.time() + 60
            logger.debug("FPS (leitura direta) pid=%s fps=%s: %s" % (pid, value, reader.debug()))
        return value
    except Exception as e:
        logger.debug("FPS (leitura direta): %s" % e)
        return None


def _start_presentmon():
    _fps["started"] = True
    if not PRESENTMON.exists():
        logger.warning("FPS: PresentMon não encontrado em %s" % PRESENTMON)
        return
    try:
        proc = subprocess.Popen(
            [str(PRESENTMON), "--output_stdout", "--no_csv", "--no_console_stats",
             "--session_name", PRESENTMON_SESSION, "--stop_existing_session"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:
        logger.warning("FPS: falha ao iniciar o PresentMon (%s)" % e)
        return
    _kill_with_parent(proc)
    _fps["proc"] = proc
    threading.Thread(target=_read_presentmon, args=(proc,), daemon=True, name="PresentMon").start()
    logger.info("FPS: PresentMon iniciado (sessão %s)" % PRESENTMON_SESSION)


def _foreground_pid():
    try:
        import win32gui
        import win32process
        return win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[1]
    except Exception:
        return None


def current_fps():
    # FPS médio do último segundo do programa em primeiro plano; None ("-- FPS") se ele não está desenhando quadros
    if not _fps_enabled():
        return None
    if config.CONFIG_DATA["config"].get("FPS_LEITURA_DIRETA", False):
        return _etw_fps(_foreground_pid(), True)  # forçado no config.yaml: não usa o PresentMon
    if not _fps["started"] and time.time() >= _fps.get("retry_at", 0):
        _start_presentmon()
    pid, now = _foreground_pid(), time.time()
    if _fps["proc"] is None:
        return _etw_fps(pid, True)  # PresentMon fora do ar (ex.: bloqueado pelo anti-cheat): usa a leitura direta
    with _fps["lock"]:
        for old in [p for p, f in _fps["frames"].items() if not f or now - f[-1][0] > 5]:
            del _fps["frames"][old]
        recent = [ms for t, ms in _fps["frames"].get(pid, ()) if now - t <= 1.0]
        busy = sorted(((len(f), p) for p, f in _fps["frames"].items()), reverse=True)[:4] if not recent else None
    if not recent:
        # O PresentMon não vê quadros do programa em primeiro plano (anti-cheat, PresentMon reiniciando...):
        # tenta a leitura direta dos eventos
        etw = _etw_fps(pid, True)
        if etw:
            return etw
    else:
        _etw_fps(pid, False)  # só para fechar o leitor direto quando o PresentMon voltou (após 1 min sem uso)
    if not recent:
        # Diagnóstico (no máximo 1 vez por minuto): quem está desenhando quadros, se não é o programa em primeiro plano
        if now - _fps.get("diag_at", 0) >= 60:
            _fps["diag_at"] = now
            logger.debug("FPS: sem quadros do programa em primeiro plano (PID %s); com quadros: %s"
                         % (pid, ", ".join("PID %d (%d)" % (p, n) for n, p in busy) or "nenhum"))
        return None
    avg = sum(recent) / len(recent)
    return int(round(1000.0 / avg)) if avg > 0 else None


def _fps_text(fps) -> str:
    return "  -- FPS" if fps is None else f"{fps:4d} FPS"


_fps_draw = {"thread": None, "last": None}


def _fps_fast_loop():
    # O texto do FPS tem ritmo próprio (REFRESH, padrão 1 s), mais rápido que os outros sensores personalizados.
    # Só redesenha quando o valor muda, para não ocupar a tela à toa.
    from library import stats
    from library.backa.themelock import THEME_LOCK
    while True:
        cfg = config.THEME_DATA["STATS"]["CUSTOM"].get("BackaFps") or {}
        time.sleep(max(0.25, float(cfg.get("REFRESH", 1))))
        # Lê o tema DEPOIS de esperar e dentro da trava: se o preset trocou nesse meio tempo, usa a posição nova
        with THEME_LOCK.reading():
            cfg = config.THEME_DATA["STATS"]["CUSTOM"].get("BackaFps") or {}
            text_cfg = cfg.get("TEXT")
            if not text_cfg or not text_cfg.get("SHOW"):
                continue
            text = _fps_text(current_fps())
            if text != _fps_draw["last"]:
                try:
                    stats.display_themed_value(theme_data=text_cfg, value=text)
                    _fps_draw["last"] = text
                except Exception as e:
                    logger.debug("FPS: %s" % e)


class BackaFps(CustomDataSource):
    last_val = [math.nan] * 30

    def as_numeric(self) -> float:
        if _fps_draw["thread"] is None:
            _fps_draw["thread"] = threading.Thread(target=_fps_fast_loop, daemon=True, name="FPS_Fast")
            _fps_draw["thread"].start()
        self.fps = current_fps()
        value = math.nan if self.fps is None else float(self.fps)
        _push(self.last_val, value)
        return value

    def as_string(self) -> str:
        text = _fps_text(self.fps)
        _fps_draw["last"] = text
        return text

    def last_values(self) -> List[float]:
        return self.last_val


# ---------------------------------------------------------------------------
# Marcadores extras: throttle, fans, modo de energia e atualizações
# Os textos têm largura fixa (fonte monoespaçada) para não deixar "fantasmas" ao mudar.
# ---------------------------------------------------------------------------
import json
import re

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _cfg(sensor_name: str) -> dict:
    return config.THEME_DATA["STATS"]["CUSTOM"].get(sensor_name) or {}


def _state_text(sensor_name: str, state: str, text: str) -> str:
    # Cor do texto conforme o estado (STATE_COLORS no tema, definido no editor: {OK: ..., TERMICO: ..., ...})
    cfg = _cfg(sensor_name)
    color = (cfg.get("STATE_COLORS") or {}).get(state)
    if cfg.get("TEXT") is not None and color:
        cfg["TEXT"]["FONT_COLOR"] = tuple(color)
    return text


def _state_icon_draw(sensor_name: str, slot: str, state: str, defaults: dict):
    # Ícone que só aparece em alguns estados (ex.: chama quando há throttle térmico); some no estado "OK"
    if _cfg(sensor_name).get("ICON") is None:
        return
    icon = _state_icon(sensor_name, state, defaults[state]) if state in defaults else ""
    _draw_icon(slot, icon, *_icon_pos(sensor_name, (0, 0)))


# --- Throttle ---
THROTTLE_ICONS = {"TERMICO": "sym:flame:filled:255,77,77", "ENERGIA": "sym:bolt:filled:255,200,0"}
THROTTLE_LABELS = {"OK": "Sem limite", "TERMICO": "Térmico", "ENERGIA": "Lim. energia"}


class BackaGpuThrottle(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        t = _gpu_throttle()
        state = "TERMICO" if t["termico"] else "ENERGIA" if t["energia"] else "OK"
        _state_icon_draw("BackaGpuThrottle", "gpu_throttle", state, THROTTLE_ICONS)
        return _state_text("BackaGpuThrottle", state, f"{THROTTLE_LABELS[state]:<12}")

    def last_values(self) -> List[float]:
        pass


class BackaCpuThrottle(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        state = "TERMICO" if _cpu_throttle() else "OK"
        _state_icon_draw("BackaCpuThrottle", "cpu_throttle", state, THROTTLE_ICONS)
        return _state_text("BackaCpuThrottle", state, f"{THROTTLE_LABELS[state]:<12}")

    def last_values(self) -> List[float]:
        pass


# --- Fans (RPM), cada uma num item próprio: BackaFan1 ... BackaFan8 ---
# No tema, SENSOR escolhe qual fan (identificador do LibreHardwareMonitor, ex.: /lpc/nct6799d/0/fan/1);
# sem SENSOR, usa a N-ésima fan encontrada. A lista de fans vai para .monitor.hw.json, que o editor lê.
FAN_SLOTS = 8
HW_INVENTORY_FILE = Path(config.MAIN_DIRECTORY) / ".monitor.hw.json"
# Tipo de sensor -> (tipo no LibreHardwareMonitor, componentes onde procurar, campo do valor)
#   fan:  fans e bombas da placa-mãe, controladoras e GPU (RPM)
#   temp: temperaturas extras: placa-mãe (chipset, VRM...) e pentes de memória (CPU, GPU e SSDs têm itens próprios)
SENSOR_KINDS = {
    "fan": ("Fan", ("Motherboard", "SuperIO", "Cooler", "EmbeddedController", "GpuNvidia", "GpuAmd", "GpuIntel"), "rpm"),
    "temp": ("Temperature", ("Motherboard", "SuperIO", "EmbeddedController", "Memory"), "value"),
}
_hw_sensors = {kind: {"time": 0.0, "list": []} for kind in SENSOR_KINDS}
_hw_lock = threading.Lock()


def _sensor_list(kind: str) -> list:
    # [{id, name, rpm|value}] dos sensores desse tipo. Relê no máximo a cada 2 s.
    with _hw_lock:
        cache = _hw_sensors[kind]
        if time.time() - cache["time"] < 2:
            return cache["list"]
        cache["time"] = time.time()
        lhm = _lhm()
        out = []
        if lhm is not None:
            sensor_type, hw_names, field = SENSOR_KINDS[kind]
            wanted = getattr(lhm.Hardware.SensorType, sensor_type)
            types = [getattr(lhm.Hardware.HardwareType, t) for t in hw_names if hasattr(lhm.Hardware.HardwareType, t)]

            memory = getattr(lhm.Hardware.HardwareType, "Memory", None)

            def hw_label(hw) -> str:
                # Pentes de memória: o nome gravado no pente às vezes vem com caracteres estranhos -> "Memória (#0)"
                name = str(hw.Name)
                if memory is not None and hw.HardwareType == memory:
                    slot = re.search(r"\(#\d+\)", name)
                    return f"Memória {slot.group(0)}" if slot else "Memória"
                return re.sub(r"[\x00-\x1f]", "", name)

            def walk(hw, parent=""):
                hw.Update()
                for s in hw.Sensors:
                    if s.SensorType == wanted:
                        value = None if s.Value is None else float(s.Value)
                        out.append({"id": str(s.Identifier), "name": f"{parent or hw_label(hw)} · {s.Name}",
                                    field: None if value is None else (round(value) if kind == "fan" else round(value, 1))})
                for sub in hw.SubHardware:
                    walk(sub, hw_label(hw))

            try:
                for hw in lhm.handle.Hardware:
                    if hw.HardwareType in types:
                        walk(hw)
            except Exception as e:
                logger.debug("Sensores (%s): %s" % (kind, e))
        cache["list"] = out
        return out


def _fan_list() -> list:
    return _sensor_list("fan")


def _fan_rpm(sensor_id, slot: int):
    fans = _fan_list()
    if sensor_id:
        return next((f["rpm"] for f in fans if f["id"] == sensor_id), None)
    return fans[slot - 1]["rpm"] if len(fans) >= slot else None


def backa_write_inventory():
    # Chamado pelo monitor de tempos em tempos: grava as fans encontradas para o editor oferecer na lista
    data = {"time": time.time(), "fans": _fan_list(), "temps": _temp_sensors(), "nets": backa_net_inventory()}
    temp = HW_INVENTORY_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, HW_INVENTORY_FILE)


class _BackaFan(CustomDataSource):
    slot = 1
    last_val = [math.nan] * 30

    def as_numeric(self) -> float:
        self.rpm = _fan_rpm(_cfg(type(self).__name__).get("SENSOR"), self.slot)
        value = math.nan if self.rpm is None else float(self.rpm)
        _push(self.last_val, value)
        return value

    def as_string(self) -> str:
        return "   -- RPM" if self.rpm is None else f"{self.rpm:5.0f} RPM"

    def last_values(self) -> List[float]:
        return self.last_val


for _slot in range(1, FAN_SLOTS + 1):
    globals()[f"BackaFan{_slot}"] = type(f"BackaFan{_slot}", (_BackaFan,), {"slot": _slot, "last_val": [math.nan] * 30})


# --- Modo de energia do Windows ---
POWER_BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
POWER_OVERLAYS = {"ded574b5-45a0-4f42-8737-46345c09c238": "Melhor desempenho",
                  "961cc777-2547-4f9d-8174-7d86181b8a7a": "Melhor eficiência",
                  "00000000-0000-0000-0000-000000000000": "Equilibrado"}
_power = {"time": 0.0, "text": None}


def _power_mode():
    # Nome do plano de energia ativo (ex.: "Alto desempenho"). No plano Equilibrado, mostra o "modo de energia"
    # escolhido em Configurações > Energia (Melhor desempenho / Equilibrado / Melhor eficiência). Relê a cada 10 s.
    if time.time() - _power["time"] < 10:
        return _power["text"]
    _power["time"] = time.time()
    import ctypes
    import uuid

    class GUID(ctypes.Structure):
        _fields_ = [("b", ctypes.c_ubyte * 16)]

    text = None
    try:
        powrprof, kernel32 = ctypes.WinDLL("powrprof"), ctypes.WinDLL("kernel32")
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        ptr = ctypes.POINTER(GUID)()
        if powrprof.PowerGetActiveScheme(None, ctypes.byref(ptr)) == 0:
            scheme = str(uuid.UUID(bytes_le=bytes(ptr.contents.b)))
            size = ctypes.c_ulong(0)
            powrprof.PowerReadFriendlyName(None, ptr, None, None, None, ctypes.byref(size))
            buf = ctypes.create_string_buffer(max(2, size.value))
            powrprof.PowerReadFriendlyName(None, ptr, None, None, buf, ctypes.byref(size))
            text = ctypes.wstring_at(buf) or None
            kernel32.LocalFree(ctypes.cast(ptr, ctypes.c_void_p))
            if scheme == POWER_BALANCED:
                overlay = GUID()
                if powrprof.PowerGetEffectiveOverlayScheme(ctypes.byref(overlay)) == 0:
                    text = POWER_OVERLAYS.get(str(uuid.UUID(bytes_le=bytes(overlay.b))), text)
    except Exception as e:
        logger.debug("Modo de energia: %s" % e)
    _power["text"] = text
    return text


class BackaPowerMode(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        return f"{(_power_mode() or '--')[:20]:<20}"

    def last_values(self) -> List[float]:
        pass


# --- Atualizações disponíveis: Windows Update e driver NVIDIA (verificadas em segundo plano) ---
UPDATE_WIN_EVERY = 30 * 60  # usa o resultado da última verificação do próprio Windows: é rápido, sem baixar nada
UPDATE_NV_EVERY = 6 * 3600  # consulta o site da NVIDIA
UPDATE_ICONS = {"win": "sym:brand-windows:filled:77,166,255", "nv": "sym:device-desktop-down:outline:118,185,0"}
_upd = {"win": {"time": 0.0, "running": False, "pending": None, "reboot": False},
        "nv": {"time": 0.0, "running": False, "installed": None, "latest": None, "available": False, "ids": None}}

WU_SCRIPT = ("$s = New-Object -ComObject Microsoft.Update.Session; $q = $s.CreateUpdateSearcher(); $q.Online = $false; "
             "$r = $q.Search('IsInstalled=0 and IsHidden=0'); "
             "$b = (New-Object -ComObject Microsoft.Update.SystemInfo).RebootRequired; "
             "Write-Output ('{0}|{1}' -f $r.Updates.Count, $b)")


def _in_background(key: str, fn, every: int):
    st = _upd[key]
    if st["running"] or time.time() - st["time"] < every:
        return
    st.update(running=True, time=time.time())

    def run():
        try:
            fn(st)
        except Exception as e:
            logger.debug("Atualizações (%s): %s" % (key, e))
            st["time"] = time.time() - every + 600  # tenta de novo em 10 min
        finally:
            st["running"] = False

    threading.Thread(target=run, daemon=True, name="Update_%s" % key).start()


def _check_windows(st):
    out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", WU_SCRIPT],
                         capture_output=True, text=True, errors="replace", timeout=180, creationflags=NO_WINDOW)
    count, reboot = out.stdout.strip().splitlines()[-1].split("|")
    st.update(pending=int(count), reboot=reboot.strip().lower() == "true")


def _version(v) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or ""))


def _check_nvidia(st):
    out = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                         capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW)
    name, installed = [v.strip() for v in out.stdout.strip().splitlines()[0].split(",")[:2]]
    if not st["ids"] or st["ids"][0] != name:
        # Código da placa na lista de produtos da NVIDIA (psid = série, pfid = modelo)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(requests.get("https://www.nvidia.com/Download/API/lookupValueSearch.aspx?TypeID=3",
                                          timeout=20).content)
        target = name.lower().replace("nvidia ", "").strip()
        for lv in root.iter("LookupValue"):
            item = (lv.findtext("Name") or lv.get("Name") or "").lower().replace("nvidia ", "").strip()
            if item == target:
                st["ids"] = (name, lv.get("ParentID") or lv.findtext("ParentID"), lv.findtext("Value") or lv.get("Value"))
                break
        else:
            raise ValueError("placa %s não encontrada na lista da NVIDIA" % name)
    _, psid, pfid = st["ids"]
    r = requests.get("https://gfwsl.geforce.com/services_toolkit/services/com/nvidia/services/AjaxDriverService.php",
                     params={"func": "DriverManualLookup", "psid": psid, "pfid": pfid, "osID": 57, "languageCode": 1033,
                             "isWHQL": 1, "dch": 1, "upCRD": 0, "sort1": 0, "numberOfResults": 1}, timeout=20)
    latest = r.json()["IDS"][0]["downloadInfo"]["Version"]
    st.update(installed=installed, latest=latest, available=_version(latest) > _version(installed))
    if st["available"]:
        logger.info("Driver NVIDIA novo disponível: %s (instalado: %s)" % (latest, installed))


def _win_update_state() -> dict:
    _in_background("win", _check_windows, UPDATE_WIN_EVERY)
    return _upd["win"]


def _nvidia_update_state() -> dict:
    _in_background("nv", _check_nvidia, UPDATE_NV_EVERY)
    return _upd["nv"]


class BackaWinUpdate(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        st = _win_update_state()
        state = "ATIVO" if st["pending"] or st["reboot"] else "OK"
        _state_icon_draw("BackaWinUpdate", "update_win", state, {"ATIVO": UPDATE_ICONS["win"]})
        if st["pending"] is None:
            text = "Windows: verificando"
        elif st["reboot"]:
            text = "Windows: reiniciar"
        elif st["pending"]:
            text = f"Windows: {st['pending']} atualiz."
        else:
            text = "Windows em dia"
        return _state_text("BackaWinUpdate", state, f"{text:<22}")

    def last_values(self) -> List[float]:
        pass


class BackaNvidiaUpdate(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        st = _nvidia_update_state()
        state = "ATIVO" if st["available"] else "OK"
        _state_icon_draw("BackaNvidiaUpdate", "update_nv", state, {"ATIVO": UPDATE_ICONS["nv"]})
        if st["latest"] is None:
            text = "NVIDIA: verificando"
        elif st["available"]:
            text = f"Driver {st['latest']} novo"
        else:
            text = f"Driver {st['installed']} em dia"
        return _state_text("BackaNvidiaUpdate", state, f"{text:<22}")

    def last_values(self) -> List[float]:
        pass


# --- Conexão de rede: cabo e Wi-Fi ---
# No tema, ADAPTER escolhe o adaptador (nome do Windows, ex.: "Ethernet", "Wi-Fi 2"); sem ADAPTER, usa o primeiro
# adaptador físico do tipo (adaptadores virtuais, como os do VMware, ficam de fora). A lista vai para .monitor.hw.json.
NET_ICONS = {
    "cabo": {"OK": "sym:plug-connected:outline:90,220,120", "DESCONECTADO": "sym:plug-connected-x:outline:255,77,77"},
    "wifi": {"OK": "sym:wifi:outline:90,220,120", "DESCONECTADO": "sym:wifi-off:outline:255,77,77"},
}
NET_SCRIPT = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
              "@(Get-NetAdapter | Select-Object Name, InterfaceDescription, PhysicalMediaType, Virtual) "
              "| ConvertTo-Json -Compress")
_nets = {"time": 0.0, "list": None, "running": False}
_wifi = {"time": 0.0, "info": {}}


def _net_kind(media: str, name: str) -> str:
    text = f"{media} {name}".lower()
    if "802.11" in text or "wireless" in text or "wi-fi" in text or "wlan" in text:
        return "wifi"
    if "802.3" in text or "ethernet" in text:
        return "cabo"
    return "outro"


def _load_net_adapters():
    try:
        out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", NET_SCRIPT],
                             capture_output=True, timeout=30, creationflags=NO_WINDOW)
        rows = json.loads(out.stdout.decode("utf-8", "replace") or "[]")
        rows = rows if isinstance(rows, list) else [rows]
        _nets["list"] = [{"name": r.get("Name"), "desc": r.get("InterfaceDescription") or "",
                          "kind": _net_kind(r.get("PhysicalMediaType") or "", r.get("Name") or ""),
                          "virtual": bool(r.get("Virtual"))} for r in rows if r.get("Name")]
    except Exception as e:
        logger.debug("Adaptadores de rede: %s" % e)
    finally:
        _nets.update(time=time.time(), running=False)


def _net_adapters(wait: bool = False) -> list:
    # [{name, desc, kind (cabo/wifi/outro), virtual}] pelo Windows (relido a cada 5 min, em segundo plano)
    if (_nets["list"] is None or time.time() - _nets["time"] > 300) and not _nets["running"]:
        _nets["running"] = True
        if wait:
            _load_net_adapters()
        else:
            threading.Thread(target=_load_net_adapters, daemon=True, name="Adaptadores").start()
    if _nets["list"] is not None:
        return _nets["list"]
    # Enquanto a lista não chega: adivinha o tipo pelo nome
    return [{"name": n, "desc": "", "kind": _net_kind("", n), "virtual": "vmware" in n.lower() or "virtual" in n.lower()}
            for n in psutil.net_if_stats()]


def backa_net_inventory() -> list:
    # Para o editor: adaptadores com o estado de agora
    stats = psutil.net_if_stats()
    return [dict(a, up=bool(stats.get(a["name"]) and stats[a["name"]].isup),
                 speed=stats[a["name"]].speed if a["name"] in stats else 0) for a in _net_adapters(wait=True)]


def _net_adapter(sensor_name: str, kind: str):
    chosen = _cfg(sensor_name).get("ADAPTER")
    if chosen:
        return chosen
    physical = [a for a in _net_adapters() if a["kind"] == kind and not a["virtual"]]
    stats = psutil.net_if_stats()
    up = [a for a in physical if stats.get(a["name"]) and stats[a["name"]].isup]
    return (up or physical or [{}])[0].get("name")


def _wifi_info(adapter: str) -> dict:
    # Rede (SSID) e sinal (%) do adaptador Wi-Fi, pelo netsh (relido a cada 10 s)
    if time.time() - _wifi["time"] >= 10:
        _wifi["time"] = time.time()
        info, current = {}, None
        try:
            out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, timeout=10,
                                 creationflags=NO_WINDOW).stdout.decode("oem", "replace")
            for line in out.splitlines():
                key, sep, value = line.partition(":")
                if not sep:
                    continue
                key, value = key.strip().lower(), value.strip()
                if key in ("nome", "name"):
                    current = info.setdefault(value, {})
                elif current is not None and key == "ssid":
                    current["ssid"] = value
                elif current is not None and key in ("sinal", "signal"):
                    current["signal"] = int(re.sub(r"\D", "", value) or 0)
        except Exception as e:
            logger.debug("Wi-Fi: %s" % e)
        _wifi["info"] = info
    return _wifi["info"].get(adapter or "", {})


def _speed_text(mbps: int) -> str:
    if not mbps:
        return ""
    return f"{mbps / 1000:g} Gbps" if mbps >= 1000 else f"{mbps} Mbps"


class _BackaNet(CustomDataSource):
    kind = "cabo"

    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        name = type(self).__name__
        adapter = _net_adapter(name, self.kind)
        stat = psutil.net_if_stats().get(adapter or "")
        up = bool(stat and stat.isup)
        state = "OK" if up else "DESCONECTADO"
        icons = dict(NET_ICONS[self.kind])
        info = _wifi_info(adapter) if self.kind == "wifi" and up else {}
        if self.kind == "wifi" and info.get("signal") is not None and info["signal"] < 70:
            icons["OK"] = icons["OK"].replace("sym:wifi:", "sym:wifi-%d:" % (1 if info["signal"] < 40 else 2))
        if up and _cfg(name).get("ICON", {}).get("HIDE_OK"):
            icons.pop("OK")  # "esconder quando conectado": o ícone só aparece se cair
        _state_icon_draw(name, f"net_{self.kind}", state, icons)
        if self.kind == "cabo":
            text = f"Cabo: {_speed_text(stat.speed) or 'conectado'}" if up else "Cabo desconectado"
        elif up:
            ssid = (info.get("ssid") or "conectado")[:12]
            text = f"Wi-Fi: {ssid}" + (f" {info['signal']}%" if info.get("signal") is not None else "")
        else:
            text = "Wi-Fi desconectado"
        if not adapter:
            text = "Cabo: sem adaptador" if self.kind == "cabo" else "Wi-Fi: sem adaptador"
        return _state_text(name, state, f"{text:<22}")

    def last_values(self) -> List[float]:
        pass


class BackaNetCable(_BackaNet):
    kind = "cabo"


class BackaNetWifi(_BackaNet):
    kind = "wifi"


# --- Temperaturas extras: RAM e placa-mãe ---
# BackaRamTemp: pente de memória mais quente. BackaTemp1..4: qualquer sensor escolhido no editor (SENSOR no tema),
# por exemplo um pente específico ou uma das temperaturas da placa-mãe.
TEMP_SLOTS = 4


def _temp_sensors() -> list:
    # Tira as "temperaturas" que na verdade são limites/resolução gravados no pente (sempre iguais)
    return [t for t in _sensor_list("temp") if not re.search(r"limit|resolution", t["name"], re.I)]


def _ram_temp():
    values = [t["value"] for t in _temp_sensors() if t["id"].startswith("/memory/") and t["value"]]
    return max(values) if values else None


class BackaRamTemp(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        return _temp_text("BackaRamTemp", _ram_temp())

    def last_values(self) -> List[float]:
        pass


class _BackaTempExtra(CustomDataSource):
    slot = 1

    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        name = type(self).__name__
        temps = _temp_sensors()
        sensor_id = _cfg(name).get("SENSOR")
        if sensor_id:
            value = next((t["value"] for t in temps if t["id"] == sensor_id), None)
        else:
            value = temps[self.slot - 1]["value"] if len(temps) >= self.slot else None
        return _temp_text(name, value)

    def last_values(self) -> List[float]:
        pass


for _slot in range(1, TEMP_SLOTS + 1):
    globals()[f"BackaTemp{_slot}"] = type(f"BackaTemp{_slot}", (_BackaTempExtra,), {"slot": _slot})


# --- Leitura e escrita dos discos (MB/s), por letra de unidade ---
DISK_MAP_SCRIPT = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
                   "@(Get-Partition | Where-Object DriveLetter | Select-Object @{n='L';e={[string]$_.DriveLetter}}, "
                   "DiskNumber) | ConvertTo-Json -Compress")
_disk_map = {"time": 0.0, "map": {}, "running": False}
_disk_io = {"time": 0.0, "last": None, "rates": {}, "lock": threading.Lock()}


def _load_disk_map():
    try:
        out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", DISK_MAP_SCRIPT],
                             capture_output=True, timeout=30, creationflags=NO_WINDOW)
        rows = json.loads(out.stdout.decode("utf-8", "replace") or "[]")
        rows = rows if isinstance(rows, list) else [rows]
        _disk_map["map"] = {str(r["L"]).upper(): f"PhysicalDrive{r['DiskNumber']}" for r in rows if r.get("L")}
    except Exception as e:
        logger.debug("Discos (letras): %s" % e)
    finally:
        _disk_map.update(time=time.time(), running=False)


def _disk_rates() -> dict:
    # {letra: (leitura B/s, escrita B/s)}, medido entre duas leituras (no mínimo 1 s de intervalo)
    if (not _disk_map["map"] or time.time() - _disk_map["time"] > 600) and not _disk_map["running"]:
        _disk_map["running"] = True
        threading.Thread(target=_load_disk_map, daemon=True, name="Discos").start()
    with _disk_io["lock"]:
        now = time.time()
        if now - _disk_io["time"] < 1:
            return _disk_io["rates"]
        counters = psutil.disk_io_counters(perdisk=True) or {}
        last = _disk_io["last"]
        if last:
            dt = now - _disk_io["time"]
            rates = {}
            for letter, drive in _disk_map["map"].items():
                cur, prev = counters.get(drive), last.get(drive)
                if cur and prev:
                    rates[letter] = (max(0, cur.read_bytes - prev.read_bytes) / dt,
                                     max(0, cur.write_bytes - prev.write_bytes) / dt)
            _disk_io["rates"] = rates
        _disk_io.update(time=now, last=counters)
        return _disk_io["rates"]


def _rate_text(bps) -> str:
    if bps is None:
        return "   -- MB/s"
    if bps < 1024 ** 2:
        return f"{bps / 1024:5.0f} KB/s"
    return f"{bps / 1024 ** 2:5.1f} MB/s"


class _BackaDiskIO(CustomDataSource):
    letter, write = "C", False
    last_val = [math.nan] * 30

    def as_numeric(self) -> float:
        rate = _disk_rates().get(self.letter)
        self.bps = None if rate is None else rate[1 if self.write else 0]
        value = math.nan if self.bps is None else self.bps / 1024 ** 2
        _push(self.last_val, value)
        return value

    def as_string(self) -> str:
        return _rate_text(self.bps)

    def last_values(self) -> List[float]:
        return self.last_val


for _letter in BACKA_DISKS:
    for _write, _suffix in ((False, "Read"), (True, "Write")):
        _name = f"BackaDisk{_letter}{_suffix}"
        globals()[_name] = type(_name, (_BackaDiskIO,), {"letter": _letter, "write": _write, "last_val": [math.nan] * 30})


# --- Processo mais pesado (CPU e RAM), somando processos com o mesmo nome (ex.: todas as abas do navegador) ---
PROCESS_SKIP = {"system idle process", "idle", "memory compression", "registry"}
_procs = {"time": 0.0, "cpu": None, "ram": None, "lock": threading.Lock()}


def _top_processes():
    with _procs["lock"]:
        if time.time() - _procs["time"] < 3:
            return _procs["cpu"], _procs["ram"]
        _procs["time"] = time.time()
        ncpu = psutil.cpu_count() or 1
        cpu_by, ram_by = {}, {}
        # process_iter reaproveita os objetos entre chamadas, então cpu_percent() mede desde a leitura anterior
        for p in psutil.process_iter(["name"]):
            try:
                name = p.info["name"] or ""
                if not name or p.pid == 0 or name.lower() in PROCESS_SKIP:
                    continue
                name = re.sub(r"\.exe$", "", name, flags=re.I)
                cpu_by[name] = cpu_by.get(name, 0.0) + p.cpu_percent(None) / ncpu
                ram_by[name] = ram_by.get(name, 0) + p.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        _procs["cpu"] = max(cpu_by.items(), key=lambda kv: kv[1]) if cpu_by else None
        _procs["ram"] = max(ram_by.items(), key=lambda kv: kv[1]) if ram_by else None
        return _procs["cpu"], _procs["ram"]


class BackaTopCpu(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        top, _ = _top_processes()
        if not top:
            return f"{'--':<14}   --%"
        return f"{top[0][:14]:<14} {min(top[1], 100):3.0f}%"

    def last_values(self) -> List[float]:
        pass


class BackaTopRam(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        _, top = _top_processes()
        if not top:
            return f"{'--':<14}   -- GB"
        size = top[1] / GB
        return f"{top[0][:14]:<14} {size:4.1f} GB" if size >= 1 else f"{top[0][:14]:<14} {top[1] / 1024 ** 2:4.0f} MB"

    def last_values(self) -> List[float]:
        pass
