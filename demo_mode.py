"""Ativa o modo demo: reseta o banco automaticamente a cada X horas.

SEGURANCA: so ativa se a variavel de ambiente DEMO_MODE=true estiver definida.
No deploy real da Distribuidora Emporio essa variavel NUNCA deve existir --
sem ela, este modulo nao faz absolutamente nada.
"""
import os
import time
import threading
from demo_seed import resetar_e_semear

RESET_INTERVAL_SECONDS = 3 * 60 * 60  # reseta a cada 3 horas


def esta_ativo():
    return os.environ.get("DEMO_MODE") == "true"


def ativar():
    if not esta_ativo():
        return  # ambiente real: nao faz nada, nunca

    resetar_e_semear()  # garante estado limpo assim que o processo sobe

    def loop_reset():
        while True:
            time.sleep(RESET_INTERVAL_SECONDS)
            resetar_e_semear()

    threading.Thread(target=loop_reset, daemon=True).start()
    print("[DEMO] Modo demo ativado -- reset automatico a cada 3h.")
