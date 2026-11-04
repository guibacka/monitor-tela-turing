#!/usr/bin/env python
# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Copyright (C) 2021 Matthieu Houdebine (mathoudebine)
# Copyright (C) 2022 Rollbacke
# Copyright (C) 2022 Ebag333
# Copyright (C) 2022 w1ld3r
# Copyright (C) 2022 Charles Ferguson (gerph)
# Copyright (C) 2022 Russ Nelson (RussNelson)
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

# This file is the system monitor main program to display HW sensors on your screen using themes (see README)

from library.pythoncheck import check_python_version
check_python_version()

import os
import sys

# [Backa] Se esta instância veio de uma recarga automática, espera a anterior terminar ANTES de importar o display:
# a porta da tela é aberta já na importação de library.display
if os.environ.get("BACKA_WAIT_PID"):
    import time as _time
    try:
        import psutil as _psutil
        _old_pid = int(os.environ.pop("BACKA_WAIT_PID"))
        for _ in range(100):
            if not _psutil.pid_exists(_old_pid):
                break
            _time.sleep(0.1)
    except Exception:
        pass
    _time.sleep(1)  # margem para o driver USB da tela liberar a porta

# [Backa] Só um monitor por vez: se outro já está rodando (ou reiniciando), este sai antes de disputar a porta da tela
if __name__ == "__main__" and "--theme-screenshots" not in sys.argv and "-t" not in sys.argv:
    import json as _json
    import time as _time
    from pathlib import Path as _Path
    _dir = _Path(__file__).resolve().parent
    try:
        import psutil as _psutil
        _other = int((_dir / ".monitor.pid").read_text())
        _alive = _other != os.getpid() and _psutil.pid_exists(_other) and _psutil.Process(_other).name().lower() in ("python.exe", "pythonw.exe", "python", "main.exe")
    except Exception:
        _alive = False
    try:
        _st = _json.loads((_dir / ".monitor.state").read_text())
        _reloading = _st.get("state") == "reloading" and _time.time() - _st.get("time", 0) < 40
    except Exception:
        _reloading = False
    _restarted = os.environ.pop("BACKA_RESTARTED", None)  # a nova instância de uma recarga pode seguir
    if _alive or (_reloading and not _restarted):
        try:
            from library.log import logger as _logger
            _logger.warning("Já existe um monitor rodando (ou reiniciando): esta nova instância vai fechar")
        except Exception:
            pass
        os._exit(0)

try:
    import argparse
    import atexit
    import locale
    import platform
    import signal
    import subprocess
    import time
    from pathlib import Path
    from PIL import Image

    if platform.system() == 'Windows':
        import win32api
        import win32con
        import win32gui

    from library.log import logger
    # [Backa] Antes de importar o agendador (os intervalos são fixados na importação): mescla os intervalos dos
    # presets do rodízio e do modo jogo, para a tela trocar entre eles sem reiniciar
    from library import config as backa_cfg
    from library.backa import automation as backa_auto
    BACKA_RUNNING_SIG = backa_auto.merge_intervals(backa_cfg, backa_cfg.CONFIG_DATA["config"]["THEME"], logger=logger)
    import library.scheduler as scheduler
    from library.display import display

except Exception as e:
    print("""Import error: %s
Please follow start guide to install required packages: https://github.com/mathoudebine/turing-smart-screen-python/wiki/System-monitor-:-how-to-start
Or the troubleshooting page: https://github.com/mathoudebine/turing-smart-screen-python/wiki/Troubleshooting#all-os-tkinter-dependency-not-installed""" % str(
        e))
    try:
        sys.exit(0)
    except:
        os._exit(0)

try:
    import pystray
except:
    # If pystray cannot be loaded do not stop the program, just ignore it. The tray icon will not be displayed.
    pass

MAIN_DIRECTORY = Path(__file__).resolve().parent
DELAY_BETWEEN_THREADS = 0.25

if __name__ == "__main__":

    # Apply system locale to this program
    locale.setlocale(locale.LC_ALL, '')

    logger.debug("Using Python %s" % sys.version)


    def wait_for_empty_queue(timeout: int = 5):
        # Waiting for all pending request to be sent to display
        logger.info("Waiting for all pending request to be sent to display (%ds max)..." % timeout)

        wait_time = 0
        while not scheduler.is_queue_empty() and wait_time < timeout:
            time.sleep(0.1)
            wait_time = wait_time + 0.1

        logger.debug("(Waited %.1fs)" % wait_time)

    def backa_shutdown_sensors():
        # [Backa] Encerra o PresentMon (FPS) do jeito certo, para não deixar a sessão de captura presa no Windows
        try:
            import library.sensors.sensors_custom as sensors_custom
            sensors_custom.backa_shutdown()
        except Exception:
            pass

    def clean_stop(tray_icon=None):
        # [Backa] Avisa o editor que o monitor foi encerrado e fecha o PresentMon
        try:
            (MAIN_DIRECTORY / ".monitor.state").write_text('{"state": "stopped", "time": %f}' % time.time())
        except Exception:
            pass
        backa_shutdown_sensors()

        # Turn screen and LEDs off before stopping
        display.turn_off()

        # Do not stop the program now in case data transmission was in progress
        # Instead, ask the scheduler to empty the action queue before stopping
        scheduler.STOPPING = True

        # Waiting for all pending request to be sent to display
        wait_for_empty_queue(5)

        # Remove tray icon just before exit
        if tray_icon:
            tray_icon.visible = False

        # We force the exit to avoid waiting for other scheduled tasks: they may have a long delay!
        try:
            sys.exit(0)
        except:
            os._exit(0)

    def on_signal_caught(signum, frame=None):
        logger.info("Caught signal %d, exiting" % signum)
        clean_stop()

    def on_configure_tray(tray_icon, item):
        logger.info("Configure from tray icon")

        try:
            # Load Python file with local python interpreter (useful for venvs)
            configure_file = next(MAIN_DIRECTORY.glob("configure.py"))
            subprocess.Popen([sys.executable, str(configure_file)])
        except:
            # Load binary (for releases) or Python file with system interpreter
            configure_file = next(MAIN_DIRECTORY.glob("configure*"))
            if platform.system() == "Windows":
                subprocess.Popen([str(configure_file)], shell=True)
            else:
                subprocess.Popen([str(configure_file)])

        # [Backa] O monitor continua rodando enquanto a configuração está aberta:
        # ao salvar, o vigia de arquivos (watch_config_files) aplica as mudanças na tela

    def backa_launch(script: str, exe: str, env=None):
        # [Backa] Abre um componente do projeto: em desenvolvimento roda o .py com o Python do venv;
        # na versão instalada (PyInstaller) roda o .exe correspondente, que fica na pasta do programa
        if getattr(sys, "frozen", False):
            command = [str(MAIN_DIRECTORY / exe)]
        else:
            command = [sys.executable, str(MAIN_DIRECTORY / script)]
        subprocess.Popen(command, cwd=str(MAIN_DIRECTORY), env=env)

    # [Backa] Arquivo que indica que o monitor está rodando (o configurador usa para não abrir um segundo monitor)
    PID_FILE = MAIN_DIRECTORY / ".monitor.pid"

    STATE_FILE = MAIN_DIRECTORY / ".monitor.state"

    # [Backa] Preset do config.yaml ("base") x preset que está na tela agora ("showing": rodízio ou modo jogo)
    import threading as backa_threading
    BACKA = {"base": backa_cfg.CONFIG_DATA["config"]["THEME"], "showing": backa_cfg.CONFIG_DATA["config"]["THEME"],
             "reason": "normal", "settings": backa_auto.load_settings(), "base_applied": False}
    SWITCH_LOCK = backa_threading.RLock()

    def write_state(state: str):
        # Estado do monitor para o editor: running / reloading / stopped, e o preset que está na tela
        import json as _json
        try:
            STATE_FILE.write_text(_json.dumps({"state": state, "time": time.time(), "theme": BACKA["showing"],
                                               "base": BACKA["base"], "reason": BACKA["reason"]}, ensure_ascii=False),
                                  encoding="utf-8")
        except Exception:
            pass

    def schedule_signature(theme_data):
        # Intervalos de cada tarefa agendada: definidos ao iniciar o programa, não mudam sem reiniciar
        return backa_auto.signature(theme_data)

    def hot_reload_theme(theme_name: str, automatic: bool = False):
        # Troca o tema sem reiniciar o programa (~3 s, quase só o tempo de desenhar o fundo).
        # Retorna True (trocou), False (precisa reiniciar: os intervalos dos sensores mudaram) ou
        # None (preset inválido ou incompatível: fica como está).
        import copy
        from library import config
        import library.sensors.sensors_custom as sensors_custom
        try:
            candidate = config.load_yaml(MAIN_DIRECTORY / "res" / "themes" / theme_name / "theme.yaml")
            candidate = copy.deepcopy(candidate)
            config.copy_default(copy.deepcopy(config.THEME_DEFAULT), candidate)
        except Exception as e:
            logger.warning("Preset %s inválido (%s): mantendo a tela como está" % (theme_name, e))
            return None
        if candidate["display"].get("DISPLAY_ORIENTATION") != config.THEME_DATA["display"].get("DISPLAY_ORIENTATION"):
            if automatic:
                logger.warning("Preset %s tem outra orientação de tela: o rodízio/modo jogo vai pular ele" % theme_name)
                return None
            return False
        # Os intervalos que o monitor usa precisam continuar valendo para os presets envolvidos
        names = backa_auto.involved_presets(BACKA["settings"], BACKA["base"]) + [theme_name]
        if backa_auto.merged_signature(config, list(dict.fromkeys(names))) != BACKA_RUNNING_SIG:
            return False
        from library.backa.themelock import THEME_LOCK
        with SWITCH_LOCK, THEME_LOCK.writing():
            # Com a trava, nenhum sensor desenha com o tema antigo por cima do fundo novo
            BACKA["showing"] = theme_name
            write_state("reloading")
            logger.info("Mostrando o preset %s (%s)" % (theme_name, BACKA["reason"]))
            config.CONFIG_DATA["config"]["THEME"] = theme_name
            config.load_theme()
            display.lcd.image_cache.clear()
            sensors_custom.backa_reset_caches()
            display.display_static_images()
            display.display_static_text()
            wait_for_empty_queue(10)
            write_state("running")
        return True

    def restart_monitor(tray_icon=None):
        # Libera a porta da tela e abre uma nova instância com a configuração/tema atualizados
        logger.info("Configuração ou tema alterados: reiniciando o monitor para aplicar na tela")
        write_state("reloading")
        scheduler.STOPPING = True
        wait_for_empty_queue(5)
        backa_shutdown_sensors()
        if tray_icon:
            tray_icon.visible = False
        # A nova instância espera este processo terminar antes de abrir a porta da tela (BACKA_WAIT_PID).
        # Não fechamos a porta aqui: algum sensor ainda pode tentar escrever e reabri-la; ao sair, o Windows a libera.
        env = dict(os.environ, BACKA_WAIT_PID=str(os.getpid()), BACKA_RESTARTED="1")
        backa_launch("main.py", "main.exe", env=env)
        os._exit(0)

    def intervals_still_valid() -> bool:
        # Os presets que podem aparecer na tela ainda cabem nos intervalos com que o monitor iniciou?
        from library import config
        names = backa_auto.involved_presets(BACKA["settings"], BACKA["base"])
        return backa_auto.merged_signature(config, names) in (BACKA_RUNNING_SIG, None)

    def watch_config_files_safe(tray_icon=None):
        # Mantém o vigia de arquivos vivo: se der erro, registra no log e recomeça
        import traceback
        while True:
            try:
                watch_config_files(tray_icon)
            except Exception:
                logger.error("Vigia de arquivos: " + traceback.format_exc().replace("\n", " | "))
                time.sleep(2)

    def watch_config_files(tray_icon=None):
        # Vigia config.yaml, automacao.json, os arquivos dos presets na tela e o código dos sensores.
        #   brilho -> aplicado na hora | preset (arquivos ou troca) -> sem reiniciar, se possível
        #   resto do config.yaml ou código dos sensores -> reinicia o monitor
        import copy
        import yaml
        from library import config

        config_file = MAIN_DIRECTORY / "config.yaml"
        sensors_file = MAIN_DIRECTORY / "library" / "sensors" / "sensors_custom.py"
        automation_file = backa_auto.SETTINGS_FILE
        themes_dir = MAIN_DIRECTORY / "res" / "themes"

        def theme_files(name):
            return [themes_dir / name / "theme.yaml", themes_dir / name / "background.png"]

        def watched():
            files = [config_file, sensors_file, automation_file] + theme_files(BACKA["showing"])
            if BACKA["base"] != BACKA["showing"]:
                files += theme_files(BACKA["base"])
            return files

        def snapshot(files):
            return {f: (f.stat().st_mtime if f.exists() else 0) for f in files}

        def changed_files(files, before, after):
            # Arquivos que acabaram de entrar na lista (o preset na tela mudou) não contam como alterados
            return [f for f in files if f in before and after[f] != before[f]]

        last = snapshot(watched())
        # Força conferir o config.yaml logo na primeira volta: ele pode ter mudado enquanto o monitor iniciava
        last[config_file] = 0
        while True:
            time.sleep(0.5)
            files = watched()
            current = snapshot(files)
            if not changed_files(files, last, current):
                last = current
                continue
            time.sleep(0.5)  # espera os arquivos terminarem de ser gravados
            current = snapshot(files)
            changed = changed_files(files, last, current)
            last = current

            if sensors_file in changed:
                restart_monitor(tray_icon)
            new_base = BACKA["base"]
            reverse_changed = False
            if config_file in changed:
                try:
                    with open(config_file, encoding="utf-8") as f:
                        new_cfg = yaml.safe_load(f)
                    new_rest, old_rest = copy.deepcopy(new_cfg), copy.deepcopy(config.CONFIG_DATA)
                    new_brightness = new_rest["display"].pop("BRIGHTNESS")
                    old_rest["display"].pop("BRIGHTNESS")
                    new_base = new_rest["config"].pop("THEME")
                    old_rest["config"].pop("THEME")
                    new_reverse = new_rest["display"].pop("DISPLAY_REVERSE", False)
                    old_rest["display"].pop("DISPLAY_REVERSE", None)
                except Exception as e:
                    logger.warning("Não foi possível ler o config.yaml alterado: %s" % e)
                    continue
                if new_rest != old_rest:
                    # Ex.: porta COM, modelo da tela, leitura de sensores: só reiniciando o monitor
                    restart_monitor(tray_icon)
                if new_brightness != config.CONFIG_DATA["display"]["BRIGHTNESS"]:
                    config.CONFIG_DATA["display"]["BRIGHTNESS"] = new_brightness
                    display.lcd.SetBrightness(new_brightness)
                    logger.info("Brilho alterado para %d%%" % new_brightness)
                reverse_changed = bool(new_reverse) != bool(config.CONFIG_DATA["display"].get("DISPLAY_REVERSE", False))
                if reverse_changed:
                    # Inverter a tela: muda a orientação e redesenha tudo, sem reiniciar
                    import library.display as display_module
                    config.CONFIG_DATA["display"]["DISPLAY_REVERSE"] = bool(new_reverse)
                    display.lcd.SetOrientation(display_module._get_theme_orientation())
                    logger.info("Tela %s" % ("invertida" if new_reverse else "na orientação normal"))

            automation_changed = automation_file in changed
            if automation_changed:
                BACKA["settings"] = backa_auto.load_settings()
                logger.info("Automação da tela alterada: %s" % BACKA["settings"])
            base_changed = new_base != BACKA["base"]
            if base_changed:
                # Outro preset aplicado (editor/configurador): o controlador da automação mostra ele em seguida
                BACKA["base"] = new_base
                BACKA["base_applied"] = True
            showing_changed = any(f in changed for f in theme_files(BACKA["showing"]))
            base_files_changed = BACKA["base"] != BACKA["showing"] and any(f in changed for f in theme_files(BACKA["base"]))

            if (automation_changed or base_changed or showing_changed or base_files_changed) and not intervals_still_valid():
                # Algum preset envolvido passou a precisar de outros intervalos de atualização
                restart_monitor(tray_icon)
            if (showing_changed or reverse_changed) and not (base_changed and BACKA["base"] != BACKA["showing"]):
                # O preset que está na tela foi salvo de novo (ou a tela foi invertida): redesenha
                if hot_reload_theme(BACKA["showing"]) is False:
                    restart_monitor(tray_icon)
            last = snapshot(watched())

    def backa_automation_loop(tray_icon=None):
        # [Backa] Decide qual preset fica na tela: modo jogo > rodízio > preset do config.yaml
        import traceback
        import library.sensors.sensors_custom as sensors_custom
        detector = backa_auto.GameDetector()
        rotation = {"current": BACKA["base"], "since": time.time()}
        skip = {}  # presets com problema: ficam de fora por um tempo
        while True:
            time.sleep(1)
            try:
                settings, now = BACKA["settings"], time.time()
                game = backa_auto.game_preset(settings)
                in_game = bool(game) and skip.get(game, 0) < now and detector.poll(
                    settings["game"], fps_fn=sensors_custom.current_fps, fps_enabled=sensors_custom._fps_enabled())
                if not game:
                    detector.reset()
                rlist = [p for p in backa_auto.rotation_list(settings) if skip.get(p, 0) < now]
                if BACKA.pop("base_applied", False):
                    # Preset recém-aplicado: aparece agora, e o rodízio segue a partir dele
                    rotation.update(current=BACKA["base"], since=now)
                    BACKA["base_applied"] = False
                if in_game:
                    target, reason = game, "modo jogo: %s" % detector.name
                    rotation["since"] = now  # ao sair do jogo, o rodízio recomeça a contar
                elif len(rlist) >= 2:
                    if rotation["current"] not in rlist and rotation["current"] != BACKA["base"]:
                        rotation.update(current=rlist[0], since=now)
                    elif now - rotation["since"] >= settings["rotation"]["seconds"]:
                        i = rlist.index(rotation["current"]) + 1 if rotation["current"] in rlist else 0
                        rotation.update(current=rlist[i % len(rlist)], since=now)
                    target, reason = rotation["current"], "rodízio"
                else:
                    target, reason = BACKA["base"], "normal"
                    rotation.update(current=BACKA["base"])
                if target == BACKA["showing"]:
                    if BACKA["reason"] != reason:
                        BACKA["reason"] = reason
                        write_state("running")
                    continue
                if skip.get(target, 0) > now:
                    continue  # deu problema há pouco: tenta de novo depois
                BACKA["reason"] = reason
                result = hot_reload_theme(target, automatic=target != BACKA["base"])
                if result is None:
                    skip[target] = now + 60
                elif result is False:
                    if intervals_still_valid():
                        skip[target] = now + 60
                    else:
                        restart_monitor(tray_icon)
            except Exception:
                logger.error("Automação da tela: " + traceback.format_exc().replace("\n", " | "))
                time.sleep(5)

    def backa_inventory_loop():
        # [Backa] Grava a lista de fans encontradas (.monitor.hw.json) para o editor oferecer na hora de escolher
        import library.sensors.sensors_custom as sensors_custom
        time.sleep(5)
        while True:
            try:
                sensors_custom.backa_write_inventory()
            except Exception as e:
                logger.debug("Lista de sensores para o editor: %s" % e)
            time.sleep(30)

    def on_editor_tray(tray_icon, item):
        # [Backa] Abre o editor visual de presets no navegador (se já estiver aberto, só abre a página)
        logger.info("Editor de tela aberto pela bandeja")
        backa_launch("backa_editor/server.py", "editor.exe")

    def on_exit_tray(tray_icon, item):
        logger.info("Exit from tray icon")
        clean_stop(tray_icon)


    def on_clean_exit(*args):
        logger.info("Program will now exit")
        clean_stop()


    if platform.system() == "Windows":
        def on_win32_ctrl_event(event):
            """Handle Windows console control events (like Ctrl-C)."""
            if event in (win32con.CTRL_C_EVENT, win32con.CTRL_BREAK_EVENT, win32con.CTRL_CLOSE_EVENT):
                logger.debug("Caught Windows control event %s, exiting" % event)
                clean_stop()
            return 0


        def on_win32_wm_event(hWnd, msg, wParam, lParam):
            """Handle Windows window message events (like ENDSESSION, CLOSE, DESTROY)."""
            logger.debug("Caught Windows window message event %s" % msg)
            if msg == win32con.WM_POWERBROADCAST:
                # WM_POWERBROADCAST is used to detect computer going to/resuming from sleep
                if wParam == win32con.PBT_APMSUSPEND:
                    logger.info("Computer is going to sleep, display will turn off")
                    display.turn_off()
                elif wParam == win32con.PBT_APMRESUMEAUTOMATIC:
                    logger.info("Computer is resuming from sleep, display will turn on")
                    display.turn_on()
                    # Some models have troubles displaying back the previous bitmap after being turned off/on
                    display.display_static_images()
                    display.display_static_text()
            else:
                # For any other events, the program will stop
                logger.info("Program will now exit")
                clean_stop()

    # Create a tray icon for the program, with an Exit entry in menu
    try:
        tray_icon = pystray.Icon(
            name='Turing System Monitor',
            title='Turing System Monitor',
            icon=Image.open(MAIN_DIRECTORY / "res/icons/monitor-icon-17865/64.png"),
            menu=pystray.Menu(
                pystray.MenuItem(
                    text='Editor de tela',
                    action=on_editor_tray,
                    default=True),
                pystray.MenuItem(
                    text='Configurar',
                    action=on_configure_tray),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    text='Sair',
                    action=on_exit_tray)
            )
        )

        # For platforms != macOS, display the tray icon now with non-blocking function
        if platform.system() != "Darwin":
            tray_icon.run_detached()
            logger.info("Tray icon has been displayed")
    except:
        tray_icon = None
        logger.warning("Tray icon is not supported on your platform")

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Turing System Monitor")
    parser.add_argument(
        "-t", "--theme-screenshots",
        type=int,
        default=None,
        help="Run n iterations in automated mode to generate themes screenshots."
    )
    args = parser.parse_args()

    # Set the different stopping event handlers, to send a complete frame to the LCD before exit
    atexit.register(on_clean_exit)
    signal.signal(signal.SIGINT, on_signal_caught)
    signal.signal(signal.SIGTERM, on_signal_caught)
    is_posix = os.name == 'posix'
    if is_posix:
        signal.signal(signal.SIGQUIT, on_signal_caught)
    if platform.system() == "Windows":
        win32api.SetConsoleCtrlHandler(on_win32_ctrl_event, True)

    # Initialize the display
    logger.info("Initialize display")
    display.initialize_display()

    # [Backa] Espelho da tela: guarda uma cópia de tudo que é enviado ao display, para a prévia ao vivo do configurador
    import threading
    from library import config as backa_config

    mirror_lock = threading.Lock()
    screen_mirror = Image.new("RGB", (display.lcd.get_width(), display.lcd.get_height()), (0, 0, 0))
    original_display_pil_image = display.lcd.DisplayPILImage

    def mirrored_display_pil_image(image, x=0, y=0, image_width=0, image_height=0):
        try:
            w, h = image_width or image.size[0], image_height or image.size[1]
            with mirror_lock:
                screen_mirror.paste(image.convert("RGB").crop((0, 0, w, h)), (x, y))
        except Exception:
            pass
        return original_display_pil_image(image, x, y, image_width, image_height)

    display.lcd.DisplayPILImage = mirrored_display_pil_image

    def on_screen_reconnected():
        # [Backa] A tela foi desconectada e voltou: ela reiniciou (orientação padrão, tela de fábrica).
        # Roda na thread da fila de envio, então nada mais escreve na tela ao mesmo tempo.
        import queue as queue_module
        import library.sensors.sensors_custom as sensors_custom
        logger.info("Tela reconectada: reconfigurando orientação, brilho e fundo")
        write_state("reloading")
        try:
            while True:
                display.lcd.update_queue.get_nowait()  # descarta o que acumulou durante a desconexão
        except queue_module.Empty:
            pass
        display.initialize_display()
        sensors_custom.backa_reset_caches()
        display.display_static_images()
        display.display_static_text()
        write_state("running")

    display.lcd.on_reconnect = on_screen_reconnected

    def save_live_preview():
        # Grava a prévia a cada 1 s (arquivo temporário + troca, para o configurador nunca ler um arquivo pela metade)
        while True:
            time.sleep(1)
            # O nome acompanha o preset ativo (ele pode mudar sem reiniciar)
            target = MAIN_DIRECTORY / (".live-preview-%s.png" % backa_config.CONFIG_DATA["config"]["THEME"])
            temp = target.with_suffix(".tmp.png")
            try:
                with mirror_lock:
                    snapshot = screen_mirror.copy()
                snapshot.save(temp)
                os.replace(temp, target)
            except Exception as e:
                logger.debug("Prévia ao vivo: %s" % e)

    # Start serial queue handler
    if not args.theme_screenshots:
        scheduler.QueueHandler()

    # Create all static images
    display.display_static_images()

    # Create all static texts
    display.display_static_text()

    # Wait for static images/text to be displayed before starting monitoring (to avoid filling the queue while waiting)
    if not args.theme_screenshots:
        wait_for_empty_queue(10)

    # Start sensor scheduled reading. Avoid starting them all at the same time to optimize load
    logger.info("Starting system monitoring")
    import library.stats as stats

    if not args.theme_screenshots:
        scheduler.CPUPercentage(); time.sleep(DELAY_BETWEEN_THREADS)
        scheduler.CPUFrequency(); time.sleep(DELAY_BETWEEN_THREADS)
        scheduler.CPULoad(); time.sleep(DELAY_BETWEEN_THREADS)
        scheduler.CPUTemperature(); time.sleep(DELAY_BETWEEN_THREADS)
        scheduler.CPUFanSpeed(); time.sleep(DELAY_BETWEEN_THREADS)
        if stats.Gpu.is_available():
            scheduler.GpuStats(); time.sleep(DELAY_BETWEEN_THREADS)
        scheduler.MemoryStats(); time.sleep(DELAY_BETWEEN_THREADS)
        scheduler.DiskStats(); time.sleep(DELAY_BETWEEN_THREADS)
        scheduler.NetStats(); time.sleep(DELAY_BETWEEN_THREADS)
        scheduler.DateStats(); time.sleep(DELAY_BETWEEN_THREADS)
        scheduler.SystemUptimeStats(); time.sleep(DELAY_BETWEEN_THREADS)
        scheduler.CustomStats(); time.sleep(DELAY_BETWEEN_THREADS)
        scheduler.WeatherStats(); time.sleep(DELAY_BETWEEN_THREADS)
        scheduler.PingStats(); time.sleep(DELAY_BETWEEN_THREADS)

        # [Backa] Registra o monitor como ativo, liga a recarga automática ao salvar configuração/tema e a prévia ao vivo
        PID_FILE.write_text(str(os.getpid()))
        write_state("running")
        threading.Thread(target=watch_config_files_safe, args=(tray_icon,), daemon=True).start()
        threading.Thread(target=backa_automation_loop, args=(tray_icon,), daemon=True, name="Automacao").start()
        threading.Thread(target=backa_inventory_loop, daemon=True, name="Inventario").start()
        threading.Thread(target=save_live_preview, daemon=True).start()
    else:
        logger.info("Theme screenshots mode enabled - program will run %d iterations then close." % args.theme_screenshots)
        # Run a predefined number of time to generate theme screenshot then close
        for i in range(0, args.theme_screenshots):
            logger.debug("Iteration #" + str(i))
            stats.CPU.percentage()
            stats.CPU.frequency()
            stats.CPU.load()
            stats.CPU.temperature()
            stats.CPU.fan_speed()
            stats.Gpu.stats()
            stats.Memory.stats()
            stats.Disk.stats()
            stats.Net.stats()
            stats.Date.stats()
            stats.SystemUptime.stats()
            stats.Custom.stats()
            stats.Weather.stats()
            stats.Ping.stats()
        logger.debug("Finished theme generation, program will close.")
        clean_stop()

    # OS-specific tasks
    if tray_icon and platform.system() == "Darwin":  # macOS-specific
        from AppKit import NSBundle, NSApp, NSApplicationActivationPolicyProhibited

        # Hide Python Launcher icon from macOS dock
        info = NSBundle.mainBundle().infoDictionary()
        info["LSUIElement"] = "1"
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyProhibited)

        # For macOS: display the tray icon now with blocking function
        tray_icon.run()

    elif platform.system() == "Windows":  # Windows-specific
        # Create a hidden window just to be able to receive window message events (for shutdown/logoff clean stop)
        hinst = win32api.GetModuleHandle(None)
        wndclass = win32gui.WNDCLASS()
        wndclass.hInstance = hinst
        wndclass.lpszClassName = "turingEventWndClass"
        messageMap = {win32con.WM_QUERYENDSESSION: on_win32_wm_event,
                      win32con.WM_ENDSESSION: on_win32_wm_event,
                      win32con.WM_QUIT: on_win32_wm_event,
                      win32con.WM_DESTROY: on_win32_wm_event,
                      win32con.WM_CLOSE: on_win32_wm_event,
                      win32con.WM_POWERBROADCAST: on_win32_wm_event}

        wndclass.lpfnWndProc = messageMap

        try:
            myWindowClass = win32gui.RegisterClass(wndclass)
            hwnd = win32gui.CreateWindowEx(win32con.WS_EX_LEFT,
                                           myWindowClass,
                                           "turingEventWnd",
                                           0,
                                           0,
                                           0,
                                           win32con.CW_USEDEFAULT,
                                           win32con.CW_USEDEFAULT,
                                           0,
                                           0,
                                           hinst,
                                           None)
            while True:
                # Receive and dispatch window messages
                win32gui.PumpWaitingMessages()
                time.sleep(0.5)

        except Exception as e:
            logger.error("Exception while creating event window: %s" % str(e))
