# -*- coding: utf-8 -*-
"""
SES EFEKTI SENTEZLEYICI
Gecis sesleri uretir. Sadece standart kutuphane kullanir; ek paket gerektirmez.

Kullanilabilir efektler:
    chime     -- yumusak "ciiink" (zil)
    pop       -- kisa "pop" (baloncuk)
    whoosh    -- "vuuşş" (hava akimi)
    arp       -- yukselen uc nota
    sparkle   -- parilti (yildiz tozu)
    marimba   -- sicak ahsap tik
"""
import math
import random
import struct
import wave
from pathlib import Path
from typing import Callable, List

ORNEKLEME = 48000


# ------------------------------------------------------------------ yardimcilar
def _zarf_us(t: float, sure: float, hiz: float = 5.0) -> float:
    """Ussel sonumleme: baslangicta yuksek, sonra hizla azalir."""
    return math.exp(-hiz * t / sure)


def _zarf_atak(t: float, atak: float = 0.005) -> float:
    """Cok kisa yumusak giris (tik sesi olmasin diye)."""
    return min(t / atak, 1.0) if atak > 0 else 1.0


def _can(t: float, sure: float) -> float:
    """Can egrisi: ortada tepe yapar (whoosh icin)."""
    x = t / sure
    return math.sin(math.pi * x) ** 1.5


# ------------------------------------------------------------------ efektler
def _chime(t: float, sure: float) -> float:
    z = _zarf_us(t, sure, 4.5) * _zarf_atak(t)
    return z * (
        1.00 * math.sin(2 * math.pi * 880 * t)
        + 0.55 * math.sin(2 * math.pi * 1320 * t)
        + 0.20 * math.sin(2 * math.pi * 1760 * t)
    ) / 1.75


def _pop(t: float, sure: float) -> float:
    # Frekans hizla dusuyor: "pop" hissi bundan geliyor
    frekans = 620 * math.exp(-14 * t)
    faz = 2 * math.pi * 620 * (1 - math.exp(-14 * t)) / 14
    z = _zarf_us(t, sure, 9.0) * _zarf_atak(t, 0.002)
    return z * (math.sin(faz) + 0.3 * math.sin(2 * faz))


def _whoosh(t: float, sure: float, _durum: List[float] = [0.0, 0.0]) -> float:
    # Beyaz gurultu + zamanla acilan alcak geciren suzgec
    gurultu = random.uniform(-1, 1)
    kesim = 0.02 + 0.35 * (t / sure)          # suzgec giderek aciliyor
    _durum[0] += kesim * (gurultu - _durum[0])
    _durum[1] += kesim * (_durum[0] - _durum[1])
    return _can(t, sure) * (_durum[0] - _durum[1]) * 6.0


def _arp(t: float, sure: float) -> float:
    notalar = [523.25, 659.25, 783.99]        # do - mi - sol
    adim = sure / (len(notalar) + 1)
    toplam = 0.0
    for i, f in enumerate(notalar):
        basla = i * adim
        if t < basla:
            continue
        yerel = t - basla
        z = _zarf_us(yerel, sure - basla, 6.0) * _zarf_atak(yerel, 0.004)
        toplam += z * (math.sin(2 * math.pi * f * yerel)
                       + 0.3 * math.sin(2 * math.pi * f * 2 * yerel))
    return toplam / 2.0


def _sparkle(t: float, sure: float) -> float:
    tanecikler = [(0.00, 2093), (0.06, 2637), (0.13, 3136),
                  (0.19, 2637), (0.26, 3520)]
    toplam = 0.0
    for basla, f in tanecikler:
        if t < basla:
            continue
        yerel = t - basla
        z = _zarf_us(yerel, 0.22, 9.0) * _zarf_atak(yerel, 0.003)
        toplam += z * math.sin(2 * math.pi * f * yerel)
    return toplam / 2.2


def _marimba(t: float, sure: float) -> float:
    # Ahsap tini: temel + 4. harmonik, hizli sonumleme
    z = _zarf_us(t, sure, 7.0) * _zarf_atak(t, 0.003)
    temel = 587.33                            # re
    return z * (
        1.00 * math.sin(2 * math.pi * temel * t)
        + 0.45 * math.sin(2 * math.pi * temel * 4 * t) * math.exp(-12 * t)
        + 0.15 * math.sin(2 * math.pi * temel * 9 * t) * math.exp(-22 * t)
    ) / 1.6


EFEKTLER = {
    "chime":   (_chime,   0.55),
    "pop":     (_pop,     0.28),
    "whoosh":  (_whoosh,  0.45),
    "arp":     (_arp,     0.60),
    "sparkle": (_sparkle, 0.55),
    "marimba": (_marimba, 0.50),
}


# ------------------------------------------------------------------ uretim
def uret(ad: str, hedef: Path, tepe: float = 0.5) -> Path:
    """Efekti uretip WAV olarak kaydeder. tepe: 0-1 arasi genlik."""
    if ad not in EFEKTLER:
        raise ValueError(
            f"Bilinmeyen efekt: {ad}. Secenekler: {', '.join(EFEKTLER)}"
        )

    fonksiyon, sure = EFEKTLER[ad]
    random.seed(42)                            # whoosh her seferinde ayni olsun

    n = int(ORNEKLEME * sure)
    ornekler = [fonksiyon(i / ORNEKLEME, sure) for i in range(n)]

    # Tepe degerine gore normalize et
    en_buyuk = max(abs(x) for x in ornekler) or 1.0
    carpan = tepe / en_buyuk

    hedef.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(hedef), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(ORNEKLEME)
        veri = bytearray()
        for x in ornekler:
            deger = int(max(-1.0, min(1.0, x * carpan)) * 32767)
            veri += struct.pack("<hh", deger, deger)
        f.writeframes(bytes(veri))

    return hedef
