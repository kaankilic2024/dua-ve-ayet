# -*- coding: utf-8 -*-
"""
ARKA PLAN URETICI
Kodla sakin bir arka plan videosu uretir. Telif riski yok, sinirsiz cesit.

Gorunum: koyu lacivert-gece mavisi gradyan zemin, uzerinde yavasca yukselen
ve sonup yanan silik altin zerreler. Yazinin onune gecmeyecek kadar sakin.

Uretilen video onbellege alinir; ayni ayarlarla tekrar uretilmez.
"""
import hashlib
import math
import random
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

import config
from utils import logger


class ArkaplanHatasi(Exception):
    pass


# ------------------------------------------------------------------ renkler
# (ust renk, alt renk) - koyu tonlar, yazi okunabilir kalsin
RENK_SEMALARI = [
    ("0a1628", "1a2f4a"),      # gece mavisi
    ("0d1b2a", "1b3a4b"),      # derin lacivert
    ("111827", "1f2f45"),      # koyu gri-mavi
    ("0a1a1f", "163a3a"),      # koyu petrol
    ("14121f", "2a2440"),      # koyu mor-lacivert
]

# Altin ton: (kirmizi, yesil, mavi) carpanlari
ZERRE_RGB = (0.83, 0.69, 0.42)


def _filtre_kur(gen: int, yuk: int, sure: float, tohum: int) -> str:
    """FFmpeg filtre zincirini kurar.

    Zerreler icin drawbox yerine 'geq' kullaniyoruz: drawbox alfa degerinde
    ifade kabul etmiyor, dolayisiyla sonup yanma efekti yapilamiyor. geq ile
    her pikselin degerini matematiksel olarak hesaplayabiliyoruz -- hem daha
    esnek hem tek gecişte tum zerreleri ciziyor.
    """
    rastgele = random.Random(tohum)
    ust, alt = rastgele.choice(RENK_SEMALARI)

    # Zerre katmani: siyah zemin uzerine parlak noktalar.
    # Her zerre icin bir Gauss lekesi topluyoruz.
    terimler = []
    for _ in range(config.ZERRE_SAYISI):
        x = rastgele.uniform(0.04, 0.96)
        bas_y = rastgele.uniform(0, 1.0)
        hiz = rastgele.uniform(0.010, 0.028)      # ekran yuksekligi/saniye
        yaricap = rastgele.uniform(1.0, 2.4)      # kucuk cozunurluk olceginde
        faz = rastgele.uniform(0, 6.28)
        parlaklik = rastgele.uniform(0.55, 1.0)

        # Yukari suzulme; ekranin ustunden cikinca alttan tekrar girer
        # geq icinde zaman degiskeni T (buyuk harf) ve virgul kacirilmali
        yy = f"mod({bas_y:.3f}-T*{hiz:.4f}+2\\,1)*H"
        # Sonup yanma
        yanip = f"(0.55+0.45*sin(T*0.8+{faz:.2f}))"
        # Gauss lekesi
        terimler.append(
            f"{parlaklik:.2f}*{yanip}*"
            f"exp(-((X-{x:.3f}*W)^2+(Y-{yy})^2)/{yaricap ** 2:.1f})"
        )

    toplam = "+".join(terimler)

    # Zerre katmanini KUCUK cozunurlukte uretip buyutuyoruz.
    # geq her piksel icin 26 Gauss hesabi yapiyor; tam cozunurlukte bu
    # dakikalar suruyor. 1/4 boyutta uretip olceklemek gorsel olarak fark
    # yaratmiyor (zerreler zaten bulanik) ama 16 kat hizlandiriyor.
    k_gen, k_yuk = gen // 4, yuk // 4

    return (
        # 1) Dikey gradyan zemin
        f"gradients=s={gen}x{yuk}:c0=0x{ust}:c1=0x{alt}:"
        f"x0=0:y0=0:x1=0:y1={yuk}:d={sure:.1f}:speed=0.006[zemin];"
        # 2) Zerre katmani: kucuk cozunurlukte, gri tonlamali
        f"color=c=black:s={k_gen}x{k_yuk}:r={config.FPS}:d={sure:.1f},"
        f"format=gray,geq=lum='clip(255*({toplam})\\,0\\,255)'[zerre];"
        # 3) Buyut, yumusat, altin renge boya
        f"[zerre]scale={gen}:{yuk}:flags=bicubic,"
        f"gblur=sigma={config.ZERRE_YUMUSAKLIK}:steps=1,"
        f"format=gbrp,"
        f"colorchannelmixer="
        f"rr={ZERRE_RGB[0]:.2f}:gg={ZERRE_RGB[1]:.2f}:bb={ZERRE_RGB[2]:.2f}[isik];"
        # 4) Zemine ekle (screen: karanlik kisimlari bozmaz)
        f"[zemin][isik]blend=all_mode=screen:all_opacity={config.ZERRE_YOGUNLUK},"
        f"format=yuv420p[out]"
    )


def _ffmpeg() -> str:
    from steps.step5_montaj import ffmpeg_yolu
    return ffmpeg_yolu()


def uret(sure: float, tohum: Optional[int] = None) -> Path:
    """Arka plan videosu uretir ve yolunu dondurur.

    Ayni tohum + sure ikilisi icin onbellekten dondurulur.
    """
    gen, yuk = config.GENISLIK, config.YUKSEKLIK
    if tohum is None:
        tohum = random.randint(1, 999_999)

    # Sureyi yukari yuvarla: 10 sn'lik dilimler halinde onbellege al
    dilim = max(int(math.ceil(sure / 10.0) * 10), 10)

    anahtar = hashlib.md5(
        f"{gen}x{yuk}_{dilim}_{tohum}_{config.ZERRE_SAYISI}".encode()
    ).hexdigest()[:10]

    onbellek = config.ARKAPLAN_DIR / f"uretilmis_{anahtar}.mp4"
    if onbellek.exists() and onbellek.stat().st_size > 10_000:
        return onbellek

    logger.bilgi(f"Arka plan uretiliyor ({dilim} sn, {config.ZERRE_SAYISI} zerre)...")

    filtre = _filtre_kur(gen, yuk, dilim, tohum)
    gecici = onbellek.with_suffix(".uretiliyor.mp4")

    komut = [
        _ffmpeg(), "-y", "-loglevel", "error",
        "-filter_complex", filtre,
        "-map", "[out]",
        "-t", str(dilim),
        "-r", str(config.FPS),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-pix_fmt", "yuv420p",
        str(gecici),
    ]

    sonuc = subprocess.run(komut, capture_output=True, text=True)
    if sonuc.returncode != 0 or not gecici.exists():
        gecici.unlink(missing_ok=True)
        son = "\n".join(sonuc.stderr.strip().splitlines()[-8:])
        raise ArkaplanHatasi(f"Arka plan uretilemedi:\n{son}")

    gecici.replace(onbellek)
    kb = onbellek.stat().st_size // 1024
    logger.ok(f"Arka plan hazir ({kb} KB)")
    return onbellek


def eskileri_temizle(en_fazla: int = 6) -> None:
    """Onbellekte cok fazla dosya birikmesin."""
    dosyalar = sorted(
        config.ARKAPLAN_DIR.glob("uretilmis_*.mp4"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for eski in dosyalar[en_fazla:]:
        eski.unlink(missing_ok=True)
