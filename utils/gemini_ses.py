# -*- coding: utf-8 -*-
"""
GEMINI TTS
Gemini'nin ses modeliyle seslendirme yapar.

edge-tts'ten farki: Gemini kelime zamanlarini vermiyor. Karaoke altyazi icin
zamanlar, kelime uzunluklarina gore ORANTILI olarak tahmin ediliyor. Bu tam
isabetli degil ama 3-5 kelimelik altyazi parcalari icin yeterli dogrulukta.

Gemini calismazsa cagiran kod edge-tts'e duser (bkz. step4_ses.py).
"""
import base64
import re
import time
import wave
from pathlib import Path
from typing import Any, Dict, List, Tuple

import config
from utils import logger

URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)


class GeminiSesHatasi(Exception):
    pass


# ------------------------------------------------------------------ zamanlama
# Turkce'de sesli harf sayisi hece sayisina yakindir; sure tahmini icin
# harf sayisindan daha iyi bir olcut.
_SESLILER = set("aeıioöuüAEIİOÖUÜ")


def _agirlik(kelime: str) -> float:
    """Bir kelimenin okunma suresine katkisi."""
    sesli = sum(1 for h in kelime if h in _SESLILER)
    return max(sesli, 1) + len(kelime) * 0.12


def kelime_zamanlari(metin: str, toplam_sure: float) -> List[Dict[str, Any]]:
    """Kelime zamanlarini orantili olarak tahmin eder.

    Noktalama isaretlerinden sonra duraklama payi birakilir; boylece
    tahmin gercek konusmaya daha yakin olur.
    """
    kelimeler = [k for k in re.split(r"\s+", metin.strip()) if k]
    if not kelimeler:
        return []

    agirliklar, duraklamalar = [], []
    for k in kelimeler:
        agirliklar.append(_agirlik(k))
        son = k[-1] if k else ""
        if son in ".!?…":
            duraklamalar.append(0.35)
        elif son in ",;:":
            duraklamalar.append(0.18)
        else:
            duraklamalar.append(0.0)

    duraklama_toplam = sum(duraklamalar)
    konusma_suresi = max(toplam_sure - duraklama_toplam, toplam_sure * 0.5)
    birim = konusma_suresi / sum(agirliklar)

    sonuc, an = [], 0.0
    for kelime, agirlik, duraklama in zip(kelimeler, agirliklar, duraklamalar):
        sure = agirlik * birim
        sonuc.append({
            "metin": kelime,
            "basla": round(an, 3),
            "sure": round(sure, 3),
        })
        an += sure + duraklama

    return sonuc


# ------------------------------------------------------------------ uretim
def _wav_yaz(pcm: bytes, yol: Path, hiz: int = 24000) -> None:
    with wave.open(str(yol), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(hiz)
        f.writeframes(pcm)


def _istek(metin: str, model: str, ses: str) -> bytes:
    import requests

    govde = {
        "contents": [{"parts": [{"text": f"{config.GEMINI_SES_YONERGE}\n\n{metin}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": ses}}
            },
        },
    }
    basliklar = {
        "x-goog-api-key": config.GEMINI_API_KEY,
        "Content-Type": "application/json",
    }

    cevap = requests.post(
        URL.format(model=model), json=govde, headers=basliklar, timeout=180
    )

    if cevap.status_code == 429:
        if "limit: 0" in cevap.text:
            raise GeminiSesHatasi("ucretsiz kota yok")
        raise GeminiSesHatasi("hiz limiti")
    if cevap.status_code != 200:
        raise GeminiSesHatasi(f"HTTP {cevap.status_code}: {cevap.text[:120]}")

    try:
        parcalar = cevap.json()["candidates"][0]["content"]["parts"]
    except Exception as e:                              # noqa: BLE001
        raise GeminiSesHatasi(f"cevap islenemedi: {e}")

    for p in parcalar:
        if "inlineData" in p:
            return base64.b64decode(p["inlineData"]["data"])

    raise GeminiSesHatasi("cevapta ses verisi yok")


def seslendir_tek(metin: str, hedef_mp3: Path) -> Tuple[bool, str]:
    """Tek bir metni seslendirir. (basarili, mesaj) dondurur.

    Cikti mp3 olarak kaydedilir (montaj zinciri mp3 bekliyor).
    """
    import subprocess
    from steps.step5_montaj import ffmpeg_yolu

    modeller = [config.GEMINI_SES_MODELI] + [
        m for m in config.GEMINI_SES_YEDEK_MODELLER
        if m != config.GEMINI_SES_MODELI
    ]

    ham = hedef_mp3.with_suffix(".ham.wav")
    son_hata = "bilinmiyor"

    for model in modeller:
        for deneme in range(1, 4):
            try:
                pcm = _istek(metin, model, config.GEMINI_SESI)
                _wav_yaz(pcm, ham)

                # mp3'e cevir
                sonuc = subprocess.run(
                    [ffmpeg_yolu(), "-y", "-loglevel", "error", "-i", str(ham),
                     "-c:a", "libmp3lame", "-q:a", "3", str(hedef_mp3)],
                    capture_output=True, text=True,
                )
                ham.unlink(missing_ok=True)

                if sonuc.returncode != 0 or not hedef_mp3.exists():
                    raise GeminiSesHatasi("mp3 donusumu basarisiz")

                return True, model

            except GeminiSesHatasi as e:
                son_hata = str(e)
                ham.unlink(missing_ok=True)

                if "kota yok" in son_hata:
                    break                       # bu modelde israr etme

                # Hiz limitinde uzun beklemek yerine hizlica yedege dusmek
                # daha mantikli: edge-tts zaten hazir ve kaliteli. Uzun
                # bekleme uretimi dakikalarca kilitliyordu.
                if "hiz limiti" in son_hata:
                    if not config.GEMINI_HIZ_LIMITINDE_BEKLE:
                        break
                    if deneme < 2:
                        time.sleep(config.GEMINI_HIZ_LIMIT_BEKLEMESI)
                    else:
                        break
                elif deneme < 3:
                    time.sleep(4 * deneme)
            except Exception as e:              # noqa: BLE001
                son_hata = str(e)[:80]
                ham.unlink(missing_ok=True)
                if deneme < 3:
                    time.sleep(4 * deneme)

    return False, son_hata


def sesleri_listele() -> None:
    """Kullanilabilir Gemini ses karakterlerini yazar."""
    logger.baslik("GEMINI SES KARAKTERLERI")
    for ad, aciklama in config.GEMINI_SES_SECENEKLERI:
        isaret = " <-- secili" if ad == config.GEMINI_SESI else ""
        print(f"  {ad:10} {aciklama}{isaret}")
    print(f"\nDegistirmek icin .env dosyasina ekle:  GEMINI_SESI=Charon")
