# -*- coding: utf-8 -*-
"""
ADIM 6 - YOUTUBE'A YUKLEME

Kurulum icin YUKLEME_KURULUM.md dosyasini oku (tek seferlik, ~10 dakika).

Onemli:
- Videolar COCUKLAR ICIN isaretlenir (COPPA yasal zorunlulugu).
- Varsayilan gizlilik "private"tir; sen kontrol edip yayinlarsin.
- Gunluk API kotasi 10.000 birim, bir yukleme ~1.600 birim -> gunde ~6 video.
"""
import json
import random
import time
from pathlib import Path
from typing import Any, Dict, Optional

import config
from utils import logger

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",   # altyazi icin
]


class YuklemeHatasi(Exception):
    pass


# ------------------------------------------------------------------ kimlik
def _kutuphaneler():
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from googleapiclient.errors import HttpError
        return Credentials, InstalledAppFlow, Request, build, MediaFileUpload, HttpError
    except ImportError as e:
        raise YuklemeHatasi(
            f"Gerekli paketler kurulu degil ({e}).\n"
            "Coz: python -m pip install -r requirements.txt"
        )


def _kimlik_al(sessiz: bool = False):
    """Kayitli izni kullanir; yoksa tarayici acip izin ister."""
    Credentials, InstalledAppFlow, Request, *_ = _kutuphaneler()

    if not config.CLIENT_SECRET.exists():
        raise YuklemeHatasi(
            f"OAuth dosyasi bulunamadi: {config.CLIENT_SECRET}\n"
            "Google Cloud Console'dan indirdigin dosyayi bu isimle kaydet.\n"
            "Adim adim anlatim: YUKLEME_KURULUM.md"
        )

    izin = None
    if config.TOKEN_DOSYASI.exists():
        try:
            izin = Credentials.from_authorized_user_file(
                str(config.TOKEN_DOSYASI), SCOPES
            )
        except Exception:
            izin = None

    if izin and izin.valid:
        return izin

    if izin and izin.expired and izin.refresh_token:
        try:
            izin.refresh(Request())
            config.TOKEN_DOSYASI.write_text(izin.to_json(), encoding="utf-8")
            return izin
        except Exception as e:
            logger.uyari(f"Kayitli izin yenilenemedi ({e}). Tekrar izin istenecek.")
            config.TOKEN_DOSYASI.unlink(missing_ok=True)

    if sessiz:
        raise YuklemeHatasi(
            "Gecerli YouTube izni yok. Once su komutu calistir:\n"
            "    python main.py --youtube-giris"
        )

    logger.bilgi("Tarayici acilacak. Video yukleyecegin Google hesabini sec.")
    akis = InstalledAppFlow.from_client_secrets_file(str(config.CLIENT_SECRET), SCOPES)
    # "select_account" olmadan Google, tarayicida acik olan hesabi otomatik
    # seciyor ve hesap degistirmek mumkun olmuyor.
    izin = akis.run_local_server(
        port=0,
        prompt="select_account consent",
        authorization_prompt_message=(
            "Tarayici aciliyor. Acilmazsa su adresi kendin ac:\n{url}"
        ),
        success_message=(
            "Yetkilendirme tamam. Bu sekmeyi kapatip konsola donebilirsin."
        ),
    )

    config.TOKEN_DOSYASI.write_text(izin.to_json(), encoding="utf-8")
    logger.ok(f"Izin kaydedildi: {config.TOKEN_DOSYASI.name}")
    logger.bilgi("Bir daha sorulmayacak (uygulama 'Test' modundaysa 7 gunde bir).")
    return izin


def cikis_yap() -> None:
    """Kayitli YouTube iznini siler. Baska bir hesaba gecmek icin kullanilir."""
    logger.baslik("YOUTUBE OTURUMU KAPATMA")

    if config.TOKEN_DOSYASI.exists():
        config.TOKEN_DOSYASI.unlink()
        logger.ok(f"Kayitli izin silindi: {config.TOKEN_DOSYASI.name}")
    else:
        logger.bilgi("Zaten kayitli bir izin yoktu.")

    logger.bilgi(
        "Yeni hesapla baglanmak icin:\n"
        "    python main.py --youtube-giris\n"
        "Tarayici acildiginda YENI hesabi sec."
    )


def giris_yap() -> None:
    """Tek seferlik yetkilendirme. Kayitli izin varsa once onu siler."""
    logger.baslik("YOUTUBE YETKILENDIRME")

    if config.TOKEN_DOSYASI.exists():
        config.TOKEN_DOSYASI.unlink()
        logger.bilgi("Onceki izin silindi, bastan yetkilendirilecek.")

    izin = _kimlik_al(sessiz=False)

    _, _, _, build, *_ = _kutuphaneler()
    servis = build("youtube", "v3", credentials=izin)
    cevap = servis.channels().list(part="snippet", mine=True).execute()
    kanallar = cevap.get("items", [])
    if kanallar:
        logger.ok(f"Bagli kanal: {kanallar[0]['snippet']['title']}")
        logger.bilgi("Yanlis kanalsa: python main.py --youtube-giris ile tekrar dene.")
    else:
        logger.uyari(
            "Bu hesapta YouTube kanali bulunamadi. "
            "Once youtube.com'da kanal olusturman gerekiyor."
        )


# ------------------------------------------------------------------ dogrulama
def _meta_hazirla(senaryo: Dict[str, Any]) -> Dict[str, Any]:
    baslik = senaryo["baslik"].strip()[:100]

    aciklama = senaryo.get("aciklama", "").strip()
    if config.ACIKLAMA_SONU:
        aciklama = f"{aciklama}\n\n{config.ACIKLAMA_SONU}".strip()
    aciklama = aciklama[:4900]

    # YouTube etiketlerin toplam uzunlugunu 500 karakterle sinirliyor
    etiketler, uzunluk = [], 0
    for e in senaryo.get("etiketler", []):
        e = str(e).strip()
        if not e or len(e) > 60:
            continue
        if uzunluk + len(e) + 1 > 480:
            break
        etiketler.append(e)
        uzunluk += len(e) + 1

    return {
        "snippet": {
            "title": baslik,
            "description": aciklama,
            "tags": etiketler,
            "categoryId": config.YOUTUBE_KATEGORI_ID,
            "defaultLanguage": config.YOUTUBE_DIL,
            "defaultAudioLanguage": config.YOUTUBE_DIL,
        },
        "status": {
            "privacyStatus": config.YOUTUBE_GIZLILIK,
            # COPPA: cocuklara yonelik icerik yasal olarak isaretlenmeli
            "selfDeclaredMadeForKids": config.COCUKLAR_ICIN,
            "license": "youtube",
            "embeddable": True,
        },
    }


# ------------------------------------------------------------------ yukleme
def _video_yukle(servis, MediaFileUpload, HttpError, video: Path, govde: Dict) -> str:
    ortam = MediaFileUpload(
        str(video), chunksize=4 * 1024 * 1024, resumable=True, mimetype="video/mp4"
    )
    istek = servis.videos().insert(
        part="snippet,status", body=govde, media_body=ortam
    )

    cevap, deneme, son_yuzde = None, 0, -10
    while cevap is None:
        try:
            durum, cevap = istek.next_chunk()
            if durum:
                yuzde = int(durum.progress() * 100)
                if yuzde - son_yuzde >= 10:
                    logger.bilgi(f"  Yukleniyor... %{yuzde}")
                    son_yuzde = yuzde
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504):
                deneme += 1
                if deneme > 5:
                    raise YuklemeHatasi(f"Sunucu hatasi surekli tekrarladi: {e}")
                bekle = min(2 ** deneme + random.random(), 60)
                logger.uyari(f"  Sunucu hatasi {e.resp.status}, {bekle:.0f} sn bekleniyor")
                time.sleep(bekle)
            elif e.resp.status == 403 and "quota" in str(e).lower():
                raise YuklemeHatasi(
                    "Gunluk API kotasi doldu (gunde ~6 yukleme). "
                    "Yarin tekrar dene; video klasorde duruyor."
                )
            else:
                raise YuklemeHatasi(f"Yukleme hatasi: {e}")

    return cevap["id"]


def _altyazi_yukle(servis, MediaFileUpload, video_id: str, srt: Path) -> bool:
    try:
        servis.captions().insert(
            part="snippet",
            body={"snippet": {
                "videoId": video_id,
                "language": config.YOUTUBE_DIL,
                "name": "Turkce",
                "isDraft": False,
            }},
            media_body=MediaFileUpload(str(srt), mimetype="application/octet-stream"),
        ).execute()
        return True
    except Exception as e:                              # noqa: BLE001
        logger.uyari(f"Altyazi yuklenemedi ({e}). Video etkilenmedi.")
        return False


# ------------------------------------------------------------------ ana fonksiyon
def yukle(proje_dir: Path, senaryo: Dict[str, Any]) -> Optional[str]:
    _, _, _, build, MediaFileUpload, HttpError = _kutuphaneler()

    video = proje_dir / "video.mp4"
    if not video.exists():
        raise YuklemeHatasi(f"Video bulunamadi: {video}")

    boyut_mb = video.stat().st_size / (1024 * 1024)

    if senaryo.get("youtube_id"):
        logger.uyari(
            f"Bu proje zaten yuklenmis (id: {senaryo['youtube_id']}). "
            "Tekrar yuklenmeyecek."
        )
        return senaryo["youtube_id"]

    govde = _meta_hazirla(senaryo)

    logger.bilgi(f"Baslik  : {govde['snippet']['title']}")
    logger.bilgi(f"Gizlilik: {govde['status']['privacyStatus']}")
    logger.bilgi(f"Cocuk icerigi: {govde['status']['selfDeclaredMadeForKids']}")
    logger.bilgi(f"Dosya   : {boyut_mb:.1f} MB")

    servis = build("youtube", "v3", credentials=_kimlik_al(sessiz=True))
    video_id = _video_yukle(servis, MediaFileUpload, HttpError, video, govde)

    baglanti = f"https://www.youtube.com/watch?v={video_id}"
    senaryo["youtube_id"] = video_id
    senaryo["youtube_link"] = baglanti
    logger.ok(f"YUKLENDI: {baglanti}")

    srt = proje_dir / "altyazi.srt"
    if config.ALTYAZI_YUKLE and srt.exists():
        if _altyazi_yukle(servis, MediaFileUpload, video_id, srt):
            logger.ok("Altyazi yuklendi")

    if config.YOUTUBE_GIZLILIK == "private":
        logger.bilgi(
            "Video OZEL olarak yuklendi. YouTube Studio'dan izleyip "
            "yayina almayi unutma."
        )

    return video_id
