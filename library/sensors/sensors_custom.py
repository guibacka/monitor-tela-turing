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
# Sensores do tema BackaRGB
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
        pic = Image.open(ICONS_DIR / f"{icon}.png").convert("RGBA").resize((size, size), Image.LANCZOS)
        tile.alpha_composite(pic)
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


# --- Alerta de desempenho ---
_throttle = {"time": 0.0, "active": False}


def _gpu_throttling() -> bool:
    # Pergunta à NVIDIA se a placa está reduzindo o clock por temperatura ou energia (a cada 6 s)
    if time.time() - _throttle["time"] < 6:
        return _throttle["active"]
    _throttle["time"] = time.time()
    for prefix in ("clocks_event_reasons", "clocks_throttle_reasons"):
        fields = ",".join(f"{prefix}.{f}" for f in ("hw_thermal_slowdown", "sw_thermal_slowdown", "hw_power_brake_slowdown"))
        try:
            out = subprocess.run(["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=5,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if out.returncode == 0:
                # Cada campo vem como "Active" ou "Not Active"
                values = [v.strip() for v in out.stdout.strip().split(",")]
                _throttle["active"] = any(v == "Active" for v in values)
                return _throttle["active"]
        except Exception:
            break
    _throttle["active"] = False
    return False


# --- Estado geral do PC: usado pela borda de status e pelo ícone de alerta ---
_status = {"time": 0.0, "level": 0, "reasons": []}


def _system_status():
    # Retorna (nível 0/1/2, motivos). Recalcula no máximo a cada 2 s, porque borda e alerta consultam juntos
    if time.time() - _status["time"] < 2:
        return _status["level"], _status["reasons"]
    found = []  # (nível, motivo)

    lhm = _lhm()
    if lhm is not None:
        cpu_t = lhm.Cpu.temperature()
        _, vram, _, _, gpu_t = lhm.Gpu.stats()
        found.append((_temp_level("BackaCpuTemp", cpu_t), f"CPU {cpu_t:.0f}°C"))
        found.append((_temp_level("BackaGpuTemp", gpu_t), f"GPU {gpu_t:.0f}°C"))
        if not _no_value(vram) and vram >= 95:
            found.append((1, f"VRAM {vram:.0f}%"))
    if _gpu_throttling():
        found.append((2, "GPU reduzindo clock"))
    if psutil.virtual_memory().percent >= 90:
        found.append((1, "RAM >= 90%"))
    for letter in BACKA_DISKS:
        ok, _, disk_t = _disk_health(letter)
        found.append((_temp_level(f"BackaDisk{letter}Temp", disk_t), f"SSD {letter}: {disk_t}°C"))
        if ok is False:
            found.append((2, f"SSD {letter}: saúde"))
        if psutil.disk_usage(f"{letter}:\\").percent >= 95:
            found.append((1, f"{letter}: quase cheio"))
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
            _draw_icon("alert", ("", "alert_warn", "alert_crit")[level], *_icon_pos("BackaAlert", (364, 8)))
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
