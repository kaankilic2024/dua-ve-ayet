# -*- coding: utf-8 -*-
"""Basit, renkli terminal ciktisi."""
import sys
from datetime import datetime

RENK = {
    "bilgi": "\033[36m",   # cyan
    "ok": "\033[32m",      # yesil
    "uyari": "\033[33m",   # sari
    "hata": "\033[31m",    # kirmizi
    "adim": "\033[35m",    # mor
    "sifirla": "\033[0m",
}

ISARET = {"bilgi": "•", "ok": "✓", "uyari": "!", "hata": "✗", "adim": "▶"}


def _yaz(tip: str, mesaj: str) -> None:
    saat = datetime.now().strftime("%H:%M:%S")
    renk = RENK.get(tip, "")
    isaret = ISARET.get(tip, "•")
    print(f"{renk}[{saat}] {isaret} {mesaj}{RENK['sifirla']}", flush=True)


def bilgi(m):  _yaz("bilgi", m)
def ok(m):     _yaz("ok", m)
def uyari(m):  _yaz("uyari", m)
def hata(m):   _yaz("hata", m)


def adim(m):
    print()
    _yaz("adim", f"\033[1m{m}\033[0m\033[35m")


def baslik(m):
    cizgi = "═" * 60
    print(f"\n\033[1;36m{cizgi}\n  {m}\n{cizgi}\033[0m", flush=True)
