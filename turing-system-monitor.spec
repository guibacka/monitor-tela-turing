# -*- mode: python ; coding: utf-8 -*-

# Configuration Wizard

configure_a = Analysis(
    ['configure.py'],
    pathex=[],
    binaries=[],
    datas=[('res', 'res'), ('config.yaml', '.'), ('external', 'external')],
    hiddenimports=['PIL', 'PIL._imagingtk', 'PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
configure_pyz = PYZ(configure_a.pure)

configure_exe = EXE(
    configure_pyz,
    configure_a.scripts,
    [],
    exclude_binaries=True,
    name='configure',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['res\\icons\\monitor-icon-17865\\icon.ico'],
    contents_directory='.',
    version='tools\\windows-installer\\pyinstaller-version-info.txt',
)

# System Monitor main program

main_a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('res', 'res'), ('config.yaml', '.'), ('external', 'external')],
    # [Backa] módulos do Windows usados pelo FPS (PresentMon) e pela janela em primeiro plano
    hiddenimports=['PIL', 'PIL._imagingtk', 'PIL._tkinter_finder', 'win32job', 'win32gui', 'win32process',
                   'win32api', 'win32con', 'requests'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
main_pyz = PYZ(main_a.pure)

main_exe = EXE(
    main_pyz,
    main_a.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['res\\icons\\monitor-icon-17865\\icon.ico'],
    contents_directory='.',
    version='tools\\windows-installer\\pyinstaller-version-info.txt',
)

# Theme Editor

editor_a = Analysis(
    ['theme-editor.py'],
    pathex=[],
    binaries=[],
    datas=[('res', 'res'), ('config.yaml', '.'), ('external', 'external')],
    hiddenimports=['PIL', 'PIL._imagingtk', 'PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
editor_pyz = PYZ(editor_a.pure)

editor_exe = EXE(
    editor_pyz,
    editor_a.scripts,
    [],
    exclude_binaries=True,
    name='theme-editor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['res\\icons\\monitor-icon-17865\\icon.ico'],
    contents_directory='.',
    version='tools\\windows-installer\\pyinstaller-version-info.txt',
)

# [Backa] Editor de tela (presets) no navegador

backa_editor_a = Analysis(
    ['backa_editor\\server.py'],
    pathex=['.'],
    binaries=[],
    datas=[('res', 'res'), ('config.yaml', '.'), ('external', 'external'), ('backa_editor\\static', 'backa_editor\\static')],
    hiddenimports=['library.backa.layout', 'babel.dates', 'psutil'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
backa_editor_pyz = PYZ(backa_editor_a.pure)

backa_editor_exe = EXE(
    backa_editor_pyz,
    backa_editor_a.scripts,
    [],
    exclude_binaries=True,
    name='editor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['res\\icons\\monitor-icon-17865\\icon.ico'],
    contents_directory='.',
    version='tools\\windows-installer\\pyinstaller-version-info.txt',
)

# [Backa] Iniciador do monitor pela tarefa agendada (sem janela, sem pedir UAC)

backa_start_a = Analysis(
    ['iniciar_monitor.pyw'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
backa_start_pyz = PYZ(backa_start_a.pure)

backa_start_exe = EXE(
    backa_start_pyz,
    backa_start_a.scripts,
    [],
    exclude_binaries=True,
    name='iniciar-monitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['res\\icons\\monitor-icon-17865\\icon.ico'],
    contents_directory='.',
    version='tools\\windows-installer\\pyinstaller-version-info.txt',
)

# Common collect task

coll = COLLECT(
    configure_exe,
    configure_a.binaries,
    configure_a.datas,
    main_exe,
    main_a.binaries,
    main_a.datas,
    editor_exe,
    editor_a.binaries,
    editor_a.datas,
    backa_editor_exe,
    backa_editor_a.binaries,
    backa_editor_a.datas,
    backa_start_exe,
    backa_start_a.binaries,
    backa_start_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='turing-system-monitor',
)
