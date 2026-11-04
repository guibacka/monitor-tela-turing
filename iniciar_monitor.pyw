# [Backa] Inicia o monitor da tela pela tarefa agendada "Monitor da Tela Turing" (como administrador, sem pedir UAC).
# É um .pyw: roda com pythonw, sem abrir nenhuma janela. Se o monitor já estiver rodando, a nova execução é
# cancelada silenciosamente pela trava de monitor único do main.py.
import subprocess

subprocess.run(["schtasks", "/Run", "/TN", "Monitor da Tela Turing"],
               capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
