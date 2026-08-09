# -*- coding: utf-8 -*-
"""
ADIM 4 - SESLENDIRME (ayet kanali)
Her ayetin Turkce mealini seslendirir.

Diger kanallardan farki: kelime zamanlarina ihtiyac yok, cunku ekranda
karaoke altyazi degil sabit ayet metni gosteriliyor. Bu yuzden sadece ses
dosyasi ve suresi yeterli.
"""
import asyncio
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import config
from utils import logger


class SesHatasi(Exception):
    pass


def _ffmpeg() -> str:
    from steps.step5_montaj import ffmpeg_yolu
    return ffmpeg_yolu()


def _sure_olc(yol: Path) -> float:
    """Ses suresini olcer. ffprobe'a bagimli degildir."""
    from steps.step5_montaj import _sure_olc as olc
    sure = olc(yol)
    if sure <= 0:
        raise SesHatasi(f"Ses suresi olculemedi: {yol.name}")
    return sure


def _calistir(coro):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    return asyncio.run(coro)


async def _edge_seslendir(metin: str, hedef: Path) -> None:
    import edge_tts
    gecici = hedef.with_suffix(".uretiliyor")
    await edge_tts.Communicate(
        text=metin, voice=config.SES_ADI,
        rate=config.SES_HIZI, pitch=config.SES_PERDESI,
    ).save(str(gecici))
    if not gecici.exists() or gecici.stat().st_size < 1024:
        gecici.unlink(missing_ok=True)
        raise SesHatasi("Uretilen ses dosyasi bos.")
    gecici.replace(hedef)


# Bir videoda ses ortada degismesin: ilk ayette hangi motor calistiysa
# video boyunca o kullanilir.
_video_motoru: str = ""


def _motoru_sifirla() -> None:
    global _video_motoru
    _video_motoru = ""


def _uret(metin: str, hedef: Path) -> str:
    """Secili motorla seslendirir. Kullanilan motoru dondurur.

    Ayni video icinde motor degistirmiyoruz: bir ayet Gemini, digeri
    edge-tts ile okunursa ses ortada degisiyor ve kotu duruyor.
    """
    global _video_motoru

    if _video_motoru == "edge":
        _calistir(_edge_seslendir(metin, hedef))
        return "edge"

    if config.SES_MOTORU == "gemini":
        from utils import gemini_ses
        ok, bilgi = gemini_ses.seslendir_tek(metin, hedef)
        if ok:
            _video_motoru = "gemini"
            return "gemini"

        if _video_motoru == "gemini":
            # Video Gemini ile basladi ama devami gelmedi. Tutarlilik icin
            # bastan edge-tts ile uretmek gerekir; cagiran kod bunu yapar.
            raise SesHatasi(f"Gemini surekli basarisiz ({bilgi})")

        logger.uyari(f"  Gemini kullanilamiyor ({bilgi}). edge-tts'e geciliyor.")

    _calistir(_edge_seslendir(metin, hedef))
    _video_motoru = "edge"
    return "edge"


def _sessizligi_kirp(yol: Path) -> bool:
    """Bastaki ve sondaki sessizligi atar."""
    if not config.SESSIZLIK_KIRP:
        return False
    esik = config.SESSIZLIK_ESIGI
    gecici = yol.with_suffix(".kirpiliyor.mp3")
    filtre = (
        f"silenceremove=start_periods=1:start_duration=0:"
        f"start_threshold={esik}:detection=peak,"
        f"areverse,"
        f"silenceremove=start_periods=1:start_duration=0:"
        f"start_threshold={esik}:detection=peak,areverse"
    )
    sonuc = subprocess.run(
        [_ffmpeg(), "-y", "-loglevel", "error", "-i", str(yol),
         "-af", filtre, "-c:a", "libmp3lame", "-q:a", "4", str(gecici)],
        capture_output=True, text=True,
    )
    if sonuc.returncode != 0 or not gecici.exists() or gecici.stat().st_size < 512:
        gecici.unlink(missing_ok=True)
        return False
    try:
        if _sure_olc(gecici) < 0.3:
            gecici.unlink(missing_ok=True)
            return False
    except Exception:
        gecici.unlink(missing_ok=True)
        return False
    gecici.replace(yol)
    return True


def sesleri_listele() -> None:
    logger.baslik("SES KARAKTERLERI")
    if config.SES_MOTORU == "gemini":
        for ad, aciklama in config.GEMINI_SES_SECENEKLERI:
            isaret = " <-- secili" if ad == config.GEMINI_SESI else ""
            print(f"  {ad:10} {aciklama}{isaret}")
        print("\nDegistirmek icin .env dosyasina:  GEMINI_SESI=Aoede")
    else:
        for ad, ayar in config.SES_TONLARI.items():
            isaret = " <-- secili" if ad == config.SES_TONU else ""
            print(f"  {ad:14} {ayar['aciklama']}{isaret}")


def seslendir(proje_dir: Path, veri: Dict[str, Any]) -> List[Path]:
    """Ayetleri seslendirir.

    Gemini video ortasinda kesilirse, tutarlilik icin butun ayetler
    edge-tts ile bastan uretilir.
    """
    _motoru_sifirla()
    try:
        return _seslendir(proje_dir, veri)
    except SesHatasi as e:
        if "surekli basarisiz" not in str(e):
            raise
        logger.uyari(f"{e}")
        logger.bilgi("Ses tutarliligi icin tum ayetler edge-tts ile yenileniyor.")

        for eski in (proje_dir / "ses").glob("ayet_*.mp3"):
            eski.unlink(missing_ok=True)

        global _video_motoru
        _video_motoru = "edge"
        return _seslendir(proje_dir, veri)


def _seslendir(proje_dir: Path, veri: Dict[str, Any]) -> List[Path]:
    ses_dir = proje_dir / "ses"
    ses_dir.mkdir(exist_ok=True)

    ayetler = veri["ayetler"]
    motor = "Gemini/" + config.GEMINI_SESI if config.SES_MOTORU == "gemini" else "edge-tts"
    logger.bilgi(f"{len(ayetler)} ayet seslendirilecek (motor: {motor})")

    yollar, basarisiz = [], []

    for i, ayet in enumerate(ayetler, start=1):
        hedef = ses_dir / f"ayet_{i:02d}.mp3"
        etiket = f"{ayet['sure_adi']} {ayet['ayet_no']}"

        if hedef.exists() and hedef.stat().st_size > 1024:
            sure = _sure_olc(hedef)
            ayet["ses_suresi"] = round(sure, 2)
            yollar.append(hedef)
            logger.bilgi(f"  {etiket}: zaten var ({sure:.1f} sn)")
            continue

        for deneme in range(1, 4):
            try:
                kullanilan = _uret(ayet["turkce"], hedef)
                _sessizligi_kirp(hedef)
                sure = _sure_olc(hedef)
                ayet["ses_suresi"] = round(sure, 2)
                yollar.append(hedef)
                logger.ok(f"  {etiket}: hazir ({sure:.1f} sn, {kullanilan})")
                if config.SES_MOTORU == "gemini" and config.SES_ARASI_BEKLEME:
                    time.sleep(config.SES_ARASI_BEKLEME)
                break
            except Exception as e:                     # noqa: BLE001
                if deneme < 3:
                    logger.uyari(f"  {etiket}: deneme {deneme} basarisiz ({e})")
                    time.sleep(2 * deneme)
                else:
                    logger.hata(f"  {etiket}: SESLENDIRILEMEDI - {e}")
                    basarisiz.append(i)

    if basarisiz:
        raise SesHatasi(f"{len(basarisiz)} ayet seslendirilemedi: {basarisiz}")

    toplam = sum(a.get("ses_suresi", 0) for a in ayetler)
    veri["toplam_ses_suresi"] = round(toplam, 1)
    logger.ok(f"Tum sesler hazir. Toplam: {toplam:.1f} sn")
    return yollar
