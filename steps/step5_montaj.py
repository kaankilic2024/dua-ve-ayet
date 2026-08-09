# -*- coding: utf-8 -*-
"""
ADIM 5 - MONTAJ (ayet kanali)
Arka plan videosunun uzerine Arapca metni, Turkce meali ve konum etiketini
bindirip sesle birlestirir.

Arapca yazi hakkinda: FFmpeg'in libass + libfribidi bileseni Arapca'yi
sagdan sola dizer ve harfleri birlestirir. Bunun icin sistemde Arapca
destekli bir yazi tipi bulunmasi sart:
  Windows : "Traditional Arabic" (hazir gelir)
  Linux   : fonts-hosny-amiri paketi (is akisi kuruyor)
Yazi tipi yoksa harfler kutu olarak cikar.
"""
import random
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from utils import logger


class MontajHatasi(Exception):
    pass


def ffmpeg_yolu() -> str:
    sistem = shutil.which("ffmpeg")
    if sistem:
        return sistem
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    raise MontajHatasi(
        "FFmpeg bulunamadi.\nCoz: python -m pip install imageio-ffmpeg"
    )


def _calistir(komut: List[str], aciklama: str, klasor: Optional[Path] = None) -> None:
    sonuc = subprocess.run(
        komut, capture_output=True, text=True,
        cwd=str(klasor) if klasor else None,
    )
    if sonuc.returncode != 0:
        son = "\n".join(sonuc.stderr.strip().splitlines()[-12:])
        raise MontajHatasi(f"{aciklama} basarisiz:\n{son}")


def _sure_olc(yol: Path) -> float:
    """Ses/video suresini olcer.

    ffprobe kullanmiyoruz: imageio-ffmpeg paketi sadece ffmpeg saglıyor,
    ffprobe icermiyor. Bunun yerine ffmpeg'in cikti kaydini okuyoruz.
    """
    # 1) mutagen (mp3 icin en hizli)
    if yol.suffix.lower() == ".mp3":
        try:
            from mutagen.mp3 import MP3
            return float(MP3(str(yol)).info.length)
        except Exception:
            pass

    # 2) Sistemde ffprobe varsa onu kullan
    import shutil as _shutil
    ffprobe = _shutil.which("ffprobe")
    if ffprobe:
        try:
            sonuc = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(yol)],
                capture_output=True, text=True, timeout=30,
            )
            if sonuc.returncode == 0 and sonuc.stdout.strip():
                return float(sonuc.stdout.strip())
        except Exception:
            pass

    # 3) ffmpeg ile: dosyayi bosluga kodlayip sure bilgisini kayittan oku
    try:
        sonuc = subprocess.run(
            [ffmpeg_yolu(), "-i", str(yol), "-f", "null", "-"],
            capture_output=True, text=True, timeout=120,
        )
        import re as _re
        eslesmeler = _re.findall(r"time=(\d+):(\d+):(\d+\.?\d*)", sonuc.stderr)
        if eslesmeler:
            sa, dk, sn = eslesmeler[-1]
            return int(sa) * 3600 + int(dk) * 60 + float(sn)
    except Exception:
        pass

    return 0.0


def arkaplan_sec(sure: float) -> Optional[Path]:
    """Arka plan videosunu hazirlar.

    ARKAPLAN_TIPI = "uretilmis" ise kodla uretir (telif riski yok).
    "video" ise assets/arkaplan klasorundeki kendi videolarindan secer.
    """
    if config.ARKAPLAN_TIPI == "uretilmis":
        try:
            from utils import arkaplan
            yol = arkaplan.uret(sure)
            arkaplan.eskileri_temizle()
            return yol
        except Exception as e:                          # noqa: BLE001
            logger.uyari(f"Arka plan uretilemedi ({e}). Kendi videolarina bakiliyor.")

    if not config.ARKAPLAN_DIR.exists():
        return None
    adaylar = [
        p for p in config.ARKAPLAN_DIR.iterdir()
        if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")
        and not p.name.startswith("uretilmis_")
    ]
    return random.choice(adaylar) if adaylar else None


# ------------------------------------------------------------------ altyazi
def _ass_zaman(sn: float) -> str:
    sn = max(sn, 0)
    saat, kalan = divmod(sn, 3600)
    dakika, saniye = divmod(kalan, 60)
    return f"{int(saat)}:{int(dakika):02d}:{saniye:05.2f}"


def _satirla(metin: str, genislik: int) -> str:
    """Uzun metni satirlara boler. ASS'te satir sonu \\N ile yazilir."""
    return "\\N".join(textwrap.wrap(metin, width=genislik))


def _arapca_punto(metin: str, taban: int, kullanilabilir_genislik: int) -> int:
    """Arapca metnin TEK SATIRA sigmasi icin gereken puntoyu hesaplar.

    Sagdan sola yazida satir bolme okuma sirasini bozuyor (kelimeler yanlis
    siraya giriyor). Bu yuzden metnin mutlaka tek satirda kalmasi gerekiyor.
    Punto, metin uzunluguna gore kucultuluyor.

    Harekeler (fetha, kesra vb.) ayri karakter sayiliyor ama genislige
    neredeyse hic katkilari yok; bu yuzden onlari saymiyoruz.
    """
    # Hareke ve tecvid isaretlerini cikar: U+064B - U+0652, U+0670, U+06D6-U+06ED
    gorunur = [
        c for c in metin
        if not (0x064B <= ord(c) <= 0x0652
                or ord(c) == 0x0670
                or 0x06D6 <= ord(c) <= 0x06ED)
    ]
    n = max(len(gorunur), 1)

    # Arapca harfin ortalama genisligi punto'nun ~0.50 kati
    punto = int(kullanilabilir_genislik / (n * 0.50))
    return max(min(punto, taban), 26)      # 26'nin altina inme, okunmaz olur


def _arapca_gorunur_uzunluk(metin: str) -> int:
    """Harekeler haric karakter sayisi (genislik tahmini icin)."""
    return len([
        c for c in metin
        if not (0x064B <= ord(c) <= 0x0652
                or ord(c) == 0x0670
                or 0x06D6 <= ord(c) <= 0x06ED)
    ])


def _arapca_parcala(metin: str, satir_basina: int) -> List[str]:
    """Uzun Arapca metni satirlara boler.

    ONEMLI: Her satir AYRI bir Dialogue satiri olarak yazilacak. Boylece
    her satir kendi icinde sagdan sola dizilir ve okuma sirasi bozulmaz.
    Tek bir Dialogue icinde \\N ile bolmek siriyi bozuyor.

    Bolme kelime sinirlarindan yapilir; kelime ortasindan bolunmez.
    """
    kelimeler = metin.split()
    if not kelimeler:
        return []

    satirlar, birikim, uzunluk = [], [], 0
    for k in kelimeler:
        k_uzunluk = _arapca_gorunur_uzunluk(k) + 1      # +1 bosluk
        if birikim and uzunluk + k_uzunluk > satir_basina:
            satirlar.append(" ".join(birikim))
            birikim, uzunluk = [k], k_uzunluk
        else:
            birikim.append(k)
            uzunluk += k_uzunluk

    if birikim:
        satirlar.append(" ".join(birikim))
    return satirlar


def _ass_yaz(ayetler, zamanlar, etiket: str, hedef: Path) -> None:
    """Ayet metinlerini ekranda gosteren altyazi dosyasi uretir."""
    gen, yuk = config.GENISLIK, config.YUKSEKLIK
    ar_punto = int(yuk * config.ARAPCA_BOYUT_ORANI)
    tr_punto = int(yuk * config.TURKCE_BOYUT_ORANI)
    et_punto = int(yuk * config.ETIKET_BOYUT_ORANI)

    # Encoding 178 = Arabic, 1 = Default
    basliklar = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {gen}
PlayResY: {yuk}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Arapca,{config.ARAPCA_YAZI_TIPI},{ar_punto},{config.ARAPCA_RENK},{config.ARAPCA_RENK},{config.KENAR_RENGI},&HA0000000,0,0,0,0,100,100,0,0,1,{max(int(ar_punto*0.07),2)},3,5,30,30,0,178
Style: Turkce,{config.TURKCE_YAZI_TIPI},{tr_punto},{config.TURKCE_RENK},{config.TURKCE_RENK},{config.KENAR_RENGI},&HA0000000,0,0,0,0,100,100,0,0,1,{max(int(tr_punto*0.10),2)},2,5,80,80,0,1
Style: Etiket,{config.TURKCE_YAZI_TIPI},{et_punto},{config.ETIKET_RENK},{config.ETIKET_RENK},{config.KENAR_RENGI},&H00000000,0,0,0,0,100,100,0,0,1,2,1,8,40,40,{int(yuk*config.ETIKET_KONUM)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    satirlar = []
    toplam = zamanlar[-1][1] if zamanlar else 0

    satirlar.append(
        f"Dialogue: 0,{_ass_zaman(0)},{_ass_zaman(toplam)},Etiket,,0,0,0,,{etiket}"
    )

    for ayet, (basla, bitis) in zip(ayetler, zamanlar):
        # --- Arapca: her satir AYRI Dialogue; sagdan sola dizilim korunur
        ar = ayet["arapca"].strip()
        ar_satirlar = _arapca_parcala(ar, config.ARAPCA_SATIR_UZUNLUGU)
        ar_p = _arapca_punto(
            "ا" * config.ARAPCA_SATIR_UZUNLUGU, ar_punto, gen - 80
        )
        ar_satir_yuk = int(ar_p * 1.55)
        ar_toplam = ar_satir_yuk * len(ar_satirlar)

        # --- Turkce: satir sayisini onceden hesapla
        tr_satirlar = textwrap.wrap(ayet["turkce"].strip(), width=34)
        tr_satir_yuk = int(tr_punto * 1.35)
        tr_toplam = tr_satir_yuk * len(tr_satirlar)

        # --- Iki blogu ekrana dagit: ust ve alt bosluk esit, aralarinda
        #     sabit bir bosluk. Boylece metinler asla ust uste binmez.
        ara = int(yuk * 0.06)
        kullanilan = ar_toplam + ara + tr_toplam
        bas = (yuk - kullanilan) // 2 + int(yuk * config.DIKEY_KAYDIRMA)

        ar_ilk_y = bas + ar_satir_yuk // 2
        for satir_no, satir in enumerate(ar_satirlar):
            y = ar_ilk_y + satir_no * ar_satir_yuk
            satirlar.append(
                f"Dialogue: 0,{_ass_zaman(basla)},{_ass_zaman(bitis)},"
                f"Arapca,,0,0,0,,"
                f"{{\\an5\\pos({gen//2},{y})\\fs{ar_p}\\fad(400,400)}}{satir}"
            )

        tr_y = bas + ar_toplam + ara + tr_toplam // 2
        tr = "\\N".join(tr_satirlar)
        satirlar.append(
            f"Dialogue: 0,{_ass_zaman(basla)},{_ass_zaman(bitis)},Turkce,,0,0,0,,"
            f"{{\\an5\\pos({gen//2},{tr_y})\\fad(400,400)}}{tr}"
        )

    hedef.write_text(basliklar + "\n".join(satirlar) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ muzik
def _muzik_sec() -> Optional[Path]:
    if not config.MUZIK_KULLAN or not config.MUSIC_DIR.exists():
        return None
    parcalar = [
        p for p in config.MUSIC_DIR.iterdir()
        if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg")
    ]
    return random.choice(parcalar) if parcalar else None


def _ses_finali(ffmpeg: str, video: Path, muzik: Optional[Path], hedef: Path) -> None:
    norm = (
        f"loudnorm=I={config.HEDEF_SES_SEVIYESI}:TP=-1.5:LRA=11"
        if config.SES_NORMALIZE else "anull"
    )
    if muzik:
        komut = [
            ffmpeg, "-y", "-loglevel", "error",
            "-i", str(video), "-stream_loop", "-1", "-i", str(muzik),
            "-filter_complex",
            f"[1:a]volume={config.MUZIK_SESI},aformat=channel_layouts=stereo[m];"
            f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:"
            f"normalize=0[mix];[mix]alimiter=limit=0.97,{norm}[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            str(hedef),
        ]
    else:
        komut = [
            ffmpeg, "-y", "-loglevel", "error", "-i", str(video),
            "-af", norm, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            str(hedef),
        ]
    _calistir(komut, "Ses finali")


# ------------------------------------------------------------------ ana akis
def videoyu_olustur(proje_dir: Path, veri: Dict[str, Any]) -> Path:
    ffmpeg = ffmpeg_yolu()
    gen, yuk = config.GENISLIK, config.YUKSEKLIK
    ayetler = veri["ayetler"]

    gecici_dir = proje_dir / "gecici"
    gecici_dir.mkdir(exist_ok=True)

    # --- 1) Sesler ve zamanlama
    ses_dir = proje_dir / "ses"
    parcalar, zamanlar, an = [], [], 0.0

    for i, ayet in enumerate(ayetler, start=1):
        ses = (ses_dir / f"ayet_{i:02d}.mp3").resolve()
        if not ses.exists():
            raise MontajHatasi(f"Ayet {i} sesi eksik: {ses.name}")
        sure = _sure_olc(ses)
        son_mu = i == len(ayetler)
        bosluk = config.SON_BOSLUK if son_mu else config.AYET_ARASI_BOSLUK

        parcalar.append((ses, sure, bosluk))
        # Yazi, ses bittikten sonra da kisa sure ekranda kalsin
        zamanlar.append((an, an + sure + bosluk * 0.7))
        an += sure + bosluk

    toplam_sure = an
    logger.bilgi(f"Video suresi: {toplam_sure:.1f} sn ({len(ayetler)} ayet)")

    ses_girdileri, ses_filtreleri = [], []
    for i, (ses, sure, bosluk) in enumerate(parcalar):
        ses_girdileri += ["-i", str(ses)]
        ses_filtreleri.append(
            f"[{i}:a]apad=pad_dur={bosluk},aresample=48000,"
            f"aformat=channel_layouts=stereo[s{i}]"
        )
    birlestir = "".join(f"[s{i}]" for i in range(len(parcalar)))
    ses_filtresi = (
        ";".join(ses_filtreleri)
        + f";{birlestir}concat=n={len(parcalar)}:v=0:a=1[ses]"
    )

    ham_ses = (gecici_dir / "ses.m4a").resolve()
    _calistir(
        [ffmpeg, "-y", "-loglevel", "error"] + ses_girdileri
        + ["-filter_complex", ses_filtresi, "-map", "[ses]",
           "-c:a", "aac", "-b:a", "192k", str(ham_ses)],
        "Sesleri birlestirme",
    )

    # --- 2) Altyazi
    altyazi = (gecici_dir / "metin.ass").resolve()
    _ass_yaz(ayetler, zamanlar, veri.get("etiket", ""), altyazi)

    # --- 3) Arka plan + yazilar
    arkaplan = arkaplan_sec(toplam_sure)
    if arkaplan:
        logger.bilgi(f"Arka plan: {arkaplan.name}")
        girdi = ["-stream_loop", "-1", "-i", str(arkaplan.resolve())]
        karartma = (
            f"eq=brightness=-{config.ARKAPLAN_KARARTMA:.2f},"
            if config.ARKAPLAN_KARARTMA > 0.01 else ""
        )
        video_filtre = (
            f"[0:v]scale={gen}:{yuk}:force_original_aspect_ratio=increase,"
            f"crop={gen}:{yuk},fps={config.FPS},"
            f"{karartma}"
            f"subtitles={altyazi.name},format=yuv420p[v]"
        )
    else:
        logger.uyari(
            f"Arka plan videosu yok ({config.ARKAPLAN_DIR}). Duz renk kullanilacak."
        )
        girdi = ["-f", "lavfi", "-i",
                 f"color=c=0x0d1b2a:s={gen}x{yuk}:r={config.FPS}"]
        video_filtre = f"[0:v]subtitles={altyazi.name},format=yuv420p[v]"

    ham_video = (gecici_dir / "ham.mp4").resolve()
    _calistir(
        [ffmpeg, "-y", "-loglevel", "error"] + girdi
        + ["-i", str(ham_ses),
           "-filter_complex", video_filtre,
           "-map", "[v]", "-map", "1:a",
           "-t", f"{toplam_sure:.3f}",
           "-c:v", "libx264", "-preset", config.X264_HIZI,
           "-crf", str(config.X264_KALITE), "-r", str(config.FPS),
           "-c:a", "aac", "-b:a", "192k", str(ham_video)],
        "Video olusturma", klasor=gecici_dir,
    )
    logger.ok("Yazilar videoya islendi")

    # --- 4) Muzik ve normalizasyon
    final = proje_dir / "video.mp4"
    muzik = _muzik_sec()
    _ses_finali(ffmpeg, ham_video, muzik, final)

    if muzik:
        logger.ok(f"Arka plan muzigi: {muzik.name}")
    elif config.MUZIK_KULLAN:
        logger.bilgi(f"Muzik eklenmedi ({config.MUSIC_DIR} bos)")

    if config.GECICI_DOSYALARI_SIL:
        shutil.rmtree(gecici_dir, ignore_errors=True)

    boyut_mb = final.stat().st_size / (1024 * 1024)
    veri["video_suresi"] = round(toplam_sure, 1)
    logger.ok(f"VIDEO HAZIR: {final.name} ({toplam_sure:.0f} sn, {boyut_mb:.1f} MB)")
    return final
