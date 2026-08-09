# -*- coding: utf-8 -*-
"""
Gemini API ile konusma katmani.
- JSON formatinda cevap ister
- Cevap bozuksa temizleyip tekrar ayristirmayi dener
- Basarisiz olursa birkac kez tekrar dener
- MOCK=1 ise internete cikmadan ornek veri dondurur (test icin)
"""
import copy
import json
import re
import time
from typing import Any, Dict

import config
from utils import logger


class AIHatasi(Exception):
    pass


# Calisan model bulununca oturum boyunca onu kullaniriz
_aktif_model: str | None = None


def _model_adaylari() -> list:
    """Denenecek modeller: once secili olan, sonra yedekler."""
    adaylar = [config.GEMINI_MODEL]
    for m in getattr(config, "GEMINI_YEDEK_MODELLER", []):
        if m not in adaylar:
            adaylar.append(m)
    return adaylar


# --------------------------------------------------------------- JSON temizle
def _json_ayikla(metin: str) -> Dict[str, Any]:
    """Model bazen ```json ... ``` icinde veya onune yazi ekleyerek cevap verir."""
    metin = metin.strip()

    # Kod blogu isaretlerini temizle
    metin = re.sub(r"^```(?:json)?\s*", "", metin)
    metin = re.sub(r"\s*```$", "", metin)

    try:
        return json.loads(metin)
    except json.JSONDecodeError:
        pass

    # Ilk { ile son } arasini almayi dene
    ilk, son = metin.find("{"), metin.rfind("}")
    if ilk != -1 and son > ilk:
        try:
            return json.loads(metin[ilk:son + 1])
        except json.JSONDecodeError:
            pass

    raise AIHatasi("Model gecerli JSON dondurmedi:\n" + metin[:500])


# --------------------------------------------------------------- Ana cagri
def sor(
    sistem: str,
    istek: str,
    sicaklik: float = 0.9,
    max_deneme: int = 3,
    mock_cevap: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Gemini'ye sorar ve JSON sozluk dondurur."""

    if config.MOCK:
        logger.uyari("MOCK modu acik - sahte veri donduruluyor.")
        if mock_cevap is None:
            raise AIHatasi("MOCK modu icin ornek cevap tanimlanmamis.")
        time.sleep(0.2)
        # Kopya donduruyoruz; yoksa ayni sozluk her cagrida tekrar degistirilir
        return copy.deepcopy(mock_cevap)

    if not config.GEMINI_API_KEY:
        raise AIHatasi(
            "GEMINI_API_KEY bulunamadi. .env dosyasini olusturdun mu? "
            "(Detay icin KURULUM.md)"
        )

    import requests  # burada import ediyoruz ki MOCK modda gerekmesin

    global _aktif_model

    adaylar = _model_adaylari()
    if _aktif_model and _aktif_model in adaylar:
        adaylar.remove(_aktif_model)
        adaylar.insert(0, _aktif_model)
    model_sirasi = 0

    basliklar = {
        "x-goog-api-key": config.GEMINI_API_KEY,
        "Content-Type": "application/json",
    }
    govde = {
        "systemInstruction": {"parts": [{"text": sistem}]},
        "contents": [{"role": "user", "parts": [{"text": istek}]}],
        "generationConfig": {
            "temperature": sicaklik,
            "topP": 0.95,
            "maxOutputTokens": 16384,
            "responseMimeType": "application/json",
        },
    }

    # Yeni nesil modeller cevap yazmadan once "dusunuyor" ve bu da token
    # sinirindan dusuyor. Butceyi sinirlayarak cevaba yer birakiyoruz.
    if config.GEMINI_DUSUNME_BUTCESI is not None:
        govde["generationConfig"]["thinkingConfig"] = {
            "thinkingBudget": config.GEMINI_DUSUNME_BUTCESI
        }

    son_hata = None
    for deneme in range(1, max_deneme + 1):
        try:
            model = adaylar[model_sirasi]
            url = config.GEMINI_URL.format(model=model)
            cevap = requests.post(url, json=govde, headers=basliklar, timeout=120)

            if cevap.status_code == 429:
                detay = cevap.text[:600]

                # "limit: 0" -> bu modelin ucretsiz kotasi hic yok.
                # Beklemek ise yaramaz, baska modele gecmek gerekir.
                if "limit: 0" in detay and model_sirasi + 1 < len(adaylar):
                    model_sirasi += 1
                    logger.uyari(
                        f"'{model}' modelinin ucretsiz kotasi yok. "
                        f"'{adaylar[model_sirasi]}' deneniyor..."
                    )
                    continue

                son_hata = AIHatasi(f"HTTP 429 (kota/limit). Sunucu cevabi:\n{detay}")
                logger.uyari(f"Kota limiti (429). Sunucu diyor ki:\n{detay}")

                if deneme == max_deneme:
                    break
                bekle = 20 * deneme
                logger.uyari(f"{bekle} sn beklenip tekrar denenecek...")
                time.sleep(bekle)
                continue

            if cevap.status_code != 200:
                raise AIHatasi(f"HTTP {cevap.status_code}: {cevap.text[:300]}")

            veri = cevap.json()
            adaylar = veri.get("candidates", [])
            if not adaylar:
                sebep = veri.get("promptFeedback", {})
                raise AIHatasi(f"Model bos cevap dondu. Detay: {sebep}")

            aday = adaylar[0]
            parcalar = aday.get("content", {}).get("parts", [])
            metin = "".join(p.get("text", "") for p in parcalar)

            if not metin.strip():
                sebep = aday.get("finishReason", "bilinmiyor")
                if sebep == "MAX_TOKENS":
                    raise AIHatasi(
                        "Model token sinirina takildi ve cevap uretemedi. "
                        "Yeni nesil modeller cevap yazmadan once 'dusunuyor' ve "
                        "bu da sinirdan sayiliyor. config.py icindeki "
                        "GEMINI_DUSUNME_BUTCESI degerini dusur veya daha kisa "
                        "bir video tipi dene."
                    )
                raise AIHatasi(f"Model bos metin dondu (sebep: {sebep}).")

            _aktif_model = model          # bu model calisti, aklimizda tutalim
            return _json_ayikla(metin)

        except Exception as e:          # noqa: BLE001
            son_hata = e
            logger.uyari(f"Deneme {deneme}/{max_deneme} basarisiz: {e}")
            if deneme < max_deneme:
                time.sleep(3 * deneme)

    raise AIHatasi(f"AI cagrisi {max_deneme} denemede basarisiz oldu: {son_hata}")
