# FPS pelo rastreamento de eventos do Windows (ETW), reserva para quando o PresentMon não consegue rodar (Backa).
#
# Alguns anti-cheats (ex.: o do Battlefield 6) impedem criar sessões de captura NOVAS enquanto o jogo está aberto,
# mas as sessões criadas antes continuam funcionando. Então:
#   - prepare(): cria a sessão "BackaFPS" (eventos de Present do DirectX) já quando o monitor abre. Ela fica ativa
#     até o PC reiniciar, então continua disponível mesmo se o monitor reiniciar no meio de um jogo;
#   - fps(pid): se o PresentMon estiver fora do ar, abre o leitor res/backa/etw-fps-reader.ps1 (C#, rápido) nas
#     sessões "BackaFPS*" que existirem e devolve o FPS do processo pedido.
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


def existing_sessions():
    # Sessões "BackaFPS*" rodando no Windows (as criadas antes de um jogo com anti-cheat continuam valendo)
    try:
        out = subprocess.run(["logman", "query", "-ets"], capture_output=True, text=True, errors="replace",
                             timeout=10, creationflags=NO_WINDOW).stdout
    except Exception:
        return []
    names = [line.split()[0] for line in out.splitlines() if line.strip().lower().startswith("backafps")]
    return sorted(names, key=lambda n: (n.lower() != SESSION.lower(), n))


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
    IDLE = 60  # sem ninguém pedindo FPS por este tempo (o PresentMon voltou): fecha o leitor
    RETRY = 30

    def __init__(self, script, logger=None):
        self.script, self.logger = str(script), logger
        self.lock = threading.Lock()
        self.proc = self.job = None
        self.values, self.at, self.session = {}, 0.0, None
        self.prepared = False
        self.retry_at = self.wanted_at = 0.0
        self.launches = 0

    def prepare(self):
        # Uma vez, ao abrir o monitor: cria a sessão BackaFPS enquanto nenhum jogo bloqueia
        now = time.monotonic()
        if not self.prepared:
            self.prepared = True
            err = start_session()
            if self.logger:
                self.logger.debug("FPS: sessão %s %s" % (SESSION, {0: "criada", ERROR_ALREADY_EXISTS: "já existia"}
                                                         .get(err, "não pôde ser criada (erro %s)" % err)))
        if self.proc is not None and now - self.wanted_at > self.IDLE:
            self.close()

    def _launch(self):
        self.launches += 1
        err = start_session()
        names = ([SESSION] if err in (0, ERROR_ALREADY_EXISTS) else []) + \
                [n for n in existing_sessions() if n.lower() != SESSION.lower()]
        log = self.logger.info if self.logger and self.launches == 1 else (self.logger.debug if self.logger else None)
        if not names:
            if log:
                log("FPS: nenhuma sessão de eventos disponível (erro %s ao criar %s)" % (err, SESSION))
            return
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
        if log:
            log("FPS: leitura direta dos eventos do Windows em %s" % ", ".join(names))
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
                        pid, _, fps = item.partition(":")
                        if pid.isdigit() and fps.isdigit():
                            values[int(pid)] = int(fps)
                    with self.lock:
                        self.values, self.at = values, time.monotonic()
                    if parts[1] != self.session:
                        self.session = parts[1]
                        if self.logger:
                            self.logger.debug("FPS: lendo os quadros pela sessão %s" % self.session)
                elif parts[0] == "END" and self.logger:
                    self.logger.debug("FPS: leitura da sessão %s terminou (código %s)" % tuple((parts + ["?"])[1:3]))
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        if self.proc is proc:
            self.proc = None
            self.retry_at = time.monotonic() + self.RETRY
            if self.logger:
                msg = " | ".join(tail)[-300:]
                self.logger.debug("FPS: leitor de eventos encerrado (código %s)%s" % (proc.returncode,
                                                                                    (": " + msg) if msg else ""))

    def fps(self, pid):
        now = time.monotonic()
        self.wanted_at = now
        if self.proc is None and now >= self.retry_at:
            self.retry_at = now + self.RETRY
            self._launch()
        with self.lock:
            if now - self.at > 2:
                return None
            return self.values.get(pid) or None

    def debug(self):
        with self.lock:
            top = sorted(((f, p) for p, f in self.values.items()), reverse=True)[:5]
            age = time.monotonic() - self.at if self.at else None
        return "leitor=%s sessão=%s há=%s top=%s" % ("ativo" if self.proc else "parado", self.session,
                                                     "%.1fs" % age if age is not None else "-",
                                                     ", ".join("%d:%d" % (p, f) for f, p in top))

    def close(self):
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass
        self.job = None
