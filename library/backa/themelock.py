# Trava do tema (Backa): evita "textos fantasmas" ao trocar de preset sem reiniciar.
#
# Cada atualização de sensor lê a posição/cores no tema e desenha. Se a troca de tema acontecer no meio disso,
# o sensor desenha na posição do tema ANTIGO por cima do fundo novo, e esse texto fica na tela.
# Os sensores usam reading() (vários ao mesmo tempo); a troca de tema usa writing(): espera os sensores em
# andamento terminarem e segura os próximos até o fundo novo ser desenhado. A troca tem preferência
# (sensores novos esperam), para não ficar esperando para sempre com tantos sensores rodando.
# A fila de envio para a tela NÃO usa a trava (a troca de tema espera a fila esvaziar).
import threading
from contextlib import contextmanager


class RWLock:
    def __init__(self):
        self._cond = threading.Condition(threading.Lock())
        self._readers = 0
        self._writer = False
        self._writers_waiting = 0

    @contextmanager
    def reading(self):
        with self._cond:
            while self._writer or self._writers_waiting:
                self._cond.wait()
            self._readers += 1
        try:
            yield
        finally:
            with self._cond:
                self._readers -= 1
                if not self._readers:
                    self._cond.notify_all()

    @contextmanager
    def writing(self):
        with self._cond:
            self._writers_waiting += 1
            while self._writer or self._readers:
                self._cond.wait()
            self._writers_waiting -= 1
            self._writer = True
        try:
            yield
        finally:
            with self._cond:
                self._writer = False
                self._cond.notify_all()


THEME_LOCK = RWLock()
