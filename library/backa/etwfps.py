# Captura de FPS própria (Backa), pelo rastreamento de eventos do Windows (ETW) — o mesmo caminho da Xbox Game Bar.
#
# O Windows anuncia um evento a cada quadro apresentado pelo DirectX (DXGI: DirectX 10/11/12; D3D9). Quem escuta não
# toca no jogo. Alguns anti-cheats (ex.: o do Battlefield 6) impedem criar escutas NOVAS com o jogo aberto, mas as que
# já existem continuam funcionando. Por isso:
#   - start(): o monitor chama ao iniciar (antes de qualquer jogo): cria a sessão "BackaFPS" e abre o leitor
#     res/backa/etw-fps-reader.ps1 (C#, rápido), que fica ligado o tempo todo. A sessão dura até o PC reiniciar,
#     então um reinício do monitor no meio do jogo só se reconecta a ela;
#   - fps(pid) / low(pid): FPS do último segundo e "1% low" dos últimos 10 s do processo pedido.
# O PresentMon fica como reserva, para quando esta captura não estiver funcionando.
# Precisa rodar como administrador (o monitor já roda assim).
import ctypes
import subprocess
import threading
import time
import uuid
from collections import deque

SESSION = "BackaFPS"
DXGI = uuid.UUID("CA11C036-0102-4A2D-A6AD-F03CFED5D3C9")
D3D9 = uuid.UUID("783ACA0A-790E-4D7F-8451-AA850511C6B9")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ULONG, USHORT, UCHAR = ctypes.c_ulong, ctypes.c_ushort, ctypes.c_ubyte


class GUID(ctypes.Structure):
    _fields_ = [("Data1", ULONG), ("Data2", USHORT), ("Data3", USHORT), ("Data4", UCHAR * 8)]

    @classmethod
    def of(cls, u: uuid.UUID):
        g = cls()
        ctypes.memmove(ctypes.byref(g), u.bytes_le, 16)
        return g


class WNODE_HEADER(ctypes.Structure):
    _fields_ = [("BufferSize", ULONG), ("ProviderId", ULONG), ("HistoricalContext", ctypes.c_ulonglong),
                ("TimeStamp", ctypes.c_longlong), ("Guid", GUID), ("ClientContext", ULONG), ("Flags", ULONG)]


class EVENT_TRACE_PROPERTIES(ctypes.Structure):
    _fields_ = [("Wnode", WNODE_HEADER), ("BufferSize", ULONG), ("MinimumBuffers", ULONG), ("MaximumBuffers", ULONG),
                ("MaximumFileSize", ULONG), ("LogFileMode", ULONG), ("FlushTimer", ULONG), ("EnableFlags", ULONG),
                ("AgeLimit", ctypes.c_long), ("NumberOfBuffers", ULONG), ("FreeBuffers", ULONG),
                ("EventsLost", ULONG), ("BuffersWritten", ULONG), ("LogBuffersLost", ULONG),
                ("RealTimeBuffersLost", ULONG), ("LoggerThreadId", ctypes.c_void_p), ("LogFileNameOffset", ULONG),
                ("LoggerNameOffset", ULONG)]


class _Props(ctypes.Structure):
    _fields_ = [("p", EVENT_TRACE_PROPERTIES), ("name", ctypes.c_wchar * 1024)]


EVENT_TRACE_REAL_TIME_MODE = 0x100
WNODE_FLAG_TRACED_GUID = 0x20000
ERROR_ALREADY_EXISTS = 183


def start_session(name=SESSION):
    # Cria a sessão de tempo real e liga os eventos de Present do DirectX. Retorna o código do Windows
    # (0 = criada, 183 = já existia, 5 = acesso negado: sem administrador ou bloqueado por anti-cheat)
    advapi = ctypes.WinDLL("advapi32")
    advapi.StartTraceW.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.c_wchar_p, ctypes.c_void_p]
    advapi.EnableTraceEx2.argtypes = [ctypes.c_uint64, ctypes.POINTER(GUID), ULONG, UCHAR, ctypes.c_ulonglong,
                                      ctypes.c_ulonglong, ULONG, ctypes.c_void_p]
    props = _Props()
    props.p.Wnode.BufferSize = ctypes.sizeof(_Props)
    props.p.Wnode.Flags = WNODE_FLAG_TRACED_GUID
    props.p.Wnode.ClientContext = 1  # relógio QPC
    props.p.LogFileMode = EVENT_TRACE_REAL_TIME_MODE
    props.p.BufferSize = 64
    props.p.MinimumBuffers = 8
    props.p.MaximumBuffers = 64
    props.p.FlushTimer = 1
    props.p.LoggerNameOffset = _Props.name.offset
    handle = ctypes.c_uint64()
    err = advapi.StartTraceW(ctypes.byref(handle), name, ctypes.byref(props))
    if err == 0:
        for provider in (DXGI, D3D9):
            advapi.EnableTraceEx2(handle.value, ctypes.byref(GUID.of(provider)), 1, 4, 0xFFFFFFFFFFFFFFFF, 0, 0, None)
    return err


KNOWN_FILE = None  # definido pelo Reader: arquivo com as sessões vistas por último (o logman pode ser bloqueado)


def existing_sessions(logger=None):
    # Sessões "BackaFPS*" rodando no Windows (as criadas antes de um jogo com anti-cheat continuam valendo).
    # Lista pelo logman; se ele falhar (alguns anti-cheats bloqueiam), usa as que funcionaram da última vez.
    names = []
    try:
        out = subprocess.run(["logman", "query", "-ets"], capture_output=True, text=True, errors="replace",
                             timeout=10, creationflags=NO_WINDOW)
        names = [line.split()[0] for line in out.stdout.splitlines() if line.strip().lower().startswith("backafps")]
        if not names and logger:
            logger.debug("FPS: logman não listou sessões (código %s)" % out.returncode)
    except Exception as e:
        if logger:
            logger.debug("FPS: logman falhou (%s)" % e)
    if KNOWN_FILE is not None:
        try:
            if names:
                KNOWN_FILE.write_text("\n".join(names), encoding="utf-8")
            else:
                names = [n for n in KNOWN_FILE.read_text(encoding="utf-8").split() if n]
        except Exception:
            pass
    return sorted(set(names), key=lambda n: (n.lower() != SESSION.lower(), n))


def _kill_with_parent(proc, logger=None):
    # Coloca o leitor num "job" do Windows: se o monitor fechar (até à força), ele fecha junto
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
        return job
    except Exception as e:
        if logger:
            logger.warning("FPS: não foi possível vincular o leitor de eventos ao monitor (%s)" % e)
        return None


class Reader:
    RETRY = 30

    def __init__(self, script, logger=None):
        global KNOWN_FILE
        self.script, self.logger = str(script), logger
        from pathlib import Path
        KNOWN_FILE = Path(script).resolve().parents[2] / ".monitor.etw-sessions"
        self.lock = threading.Lock()
        self.proc = self.job = None
        self.values, self.at, self.session = {}, 0.0, None
        self.retry_at = 0.0
        self.launches = 0
        self.launched_at = 0.0

    def start(self):
        # Ao abrir o monitor: cria a sessão e já deixa o leitor escutando (antes de qualquer jogo abrir)
        if self.proc is None:
            self.retry_at = time.monotonic() + self.RETRY
            self._launch()

    def _ensure(self):
        if self.proc is None and time.monotonic() >= self.retry_at:
            self.retry_at = time.monotonic() + self.RETRY
            self._launch()

    def _launch(self):
        self.launches += 1
        err = start_session()
        if self.logger:
            self.logger.debug("FPS: sessão %s %s" % (SESSION, {0: "criada", ERROR_ALREADY_EXISTS: "já existia"}
                                                     .get(err, "não pôde ser criada agora (erro %s)" % err)))
        # A BackaFPS entra sempre: mesmo que o Windows negue criá-la agora (anti-cheat), ela pode já existir
        # desde antes do jogo. As outras BackaFPS* (de PresentMon) só entram se a BackaFPS não pôde ser criada.
        names = [SESSION]
        if err not in (0, ERROR_ALREADY_EXISTS):
            names += [n for n in existing_sessions(self.logger) if n.lower() != SESSION.lower()]
        log = self.logger.info if self.logger and self.launches == 1 else (self.logger.debug if self.logger else None)
        try:
            proc = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", self.script,
                 "-Sessions", ",".join(names)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True, bufsize=1,
                errors="replace", creationflags=NO_WINDOW)
        except Exception as e:
            if self.logger:
                self.logger.warning("FPS: falha ao abrir o leitor de eventos (%s)" % e)
            return
        self.job = _kill_with_parent(proc, self.logger)
        self.proc = proc
        self.launched_at = time.monotonic()
        if log:
            log("FPS: captura própria escutando %s" % ", ".join(names))
        tail = deque(maxlen=5)
        threading.Thread(target=self._drain, args=(proc, tail), daemon=True, name="ETW_FPS_err").start()
        threading.Thread(target=self._read, args=(proc, tail), daemon=True, name="ETW_FPS").start()

    @staticmethod
    def _drain(proc, tail):
        try:
            for line in proc.stderr:
                if line.strip():
                    tail.append(line.strip())
        except Exception:
            pass

    def _read(self, proc, tail):
        try:
            for line in proc.stdout:
                parts = line.split()
                if not parts:
                    continue
                if parts[0] == "FPS" and len(parts) >= 2:
                    values = {}
                    for item in parts[2:]:
                        fields = item.split(":")
                        if len(fields) >= 2 and all(f.isdigit() for f in fields):
                            values[int(fields[0])] = (int(fields[1]), int(fields[2]) if len(fields) > 2 else 0)
                    with self.lock:
                        self.values, self.at = values, time.monotonic()
                    if parts[1] != self.session:
                        self.session = parts[1]
                        if self.logger:
                            self.logger.info("FPS: captura própria recebendo os quadros pela sessão %s" % self.session)
                elif parts[0] == "END" and self.logger:
                    self.logger.debug("FPS: sessão %s indisponível (código %s)" % tuple((parts + ["?"])[1:3]))
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        if self.proc is proc:
            self.proc = None
            self.session = None
            self.retry_at = time.monotonic() + self.RETRY
            if self.logger:
                msg = " | ".join(tail)[-300:]
                self.logger.warning("FPS: captura própria parou (código %s)%s. Nova tentativa em %d s; enquanto isso, "
                                    "o PresentMon é usado como reserva" % (proc.returncode, (": " + msg) if msg else "",
                                                                           self.RETRY))

    def healthy(self) -> bool:
        # Leitor rodando e conectado a uma sessão que está entregando (ele informa a cada 0,5 s)
        self._ensure()
        with self.lock:
            return self.proc is not None and self.session is not None and time.monotonic() - self.at < 3

    def starting(self) -> bool:
        # Acabou de abrir e ainda não recebeu nada (leva ~1 s): não é hora de recorrer à reserva
        return self.proc is not None and self.session is None and time.monotonic() - self.launched_at < 10

    def best(self, pids):
        # (fps, low) do processo pedido; se ele não desenha quadros, do processo filho que mais desenha
        # (navegadores e apps como Discord desenham num processo filho; jogos desenham no próprio processo)
        with self.lock:
            if time.monotonic() - self.at >= 3:
                return None, None
            values = self.values
        if not pids:
            return None, None
        own = values.get(pids[0])
        if own and own[0]:
            return own[0], own[1] or None
        kids = [values[p] for p in pids[1:] if p in values and values[p][0]]
        if not kids:
            return None, None
        fps, low = max(kids)
        return fps, low or None

    def fps(self, pid):
        return self.best([pid])[0]

    def low(self, pid):
        return self.best([pid])[1]

    def debug(self):
        with self.lock:
            top = sorted(((f[0], f[1], p) for p, f in self.values.items()), reverse=True)[:5]
            age = time.monotonic() - self.at if self.at else None
        return "leitor=%s sessão=%s há=%s top=%s" % ("ativo" if self.proc else "parado", self.session,
                                                     "%.1fs" % age if age is not None else "-",
                                                     ", ".join("%d:%d/%d" % (p, f, lo) for f, lo, p in top))

    def close(self):
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass
        self.job = None
