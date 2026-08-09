# -*- coding: utf-8 -*-
"""
AYET KAYNAGI
Kuran metnini ve Turkce meali guvenilir bir kaynaktan ceker.

ONEMLI: Ayet metni ASLA yapay zekaya yazdirilmaz. Yapay zeka harf atlayabilir,
kelime degistirebilir, uydurma ayet uretebilir. Bu yuzden metin her zaman
API'den birebir alinir ve dogrulanir.

Kaynak: alquran.cloud (ucretsiz, anahtar gerektirmez)
  - Arapca: quran-uthmani (Osmanli hatli standart metin)
  - Turkce: tr.diyanet (Diyanet Isleri Meali)
"""
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from utils import logger

TEMEL_URL = "https://api.alquran.cloud/v1"

# Kuran'daki sure isimleri ve ayet sayilari (dogrulama icin)
# Toplam 114 sure, 6236 ayet
SURE_BILGISI_DOSYASI = "sure_bilgisi.json"


class AyetHatasi(Exception):
    pass


# ------------------------------------------------------------------ ilerleme
def _ilerleme_dosyasi() -> Path:
    return config.DATA_DIR / "ayet_ilerleme.json"


def ilerleme_oku() -> Dict[str, Any]:
    """Kaldigimiz yeri dondurur."""
    yol = _ilerleme_dosyasi()
    if yol.exists():
        try:
            return json.loads(yol.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Bastan basla: Fatiha 1. ayet
    return {"sure": 1, "ayet": 1, "tamamlanan_video": 0}


def ilerleme_yaz(sure: int, ayet: int, video_sayisi: int) -> None:
    _ilerleme_dosyasi().write_text(
        json.dumps(
            {"sure": sure, "ayet": ayet, "tamamlanan_video": video_sayisi},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )


# ------------------------------------------------------------------ API
def _istek(yol: str, deneme: int = 3) -> Dict[str, Any]:
    import requests

    son_hata = None
    for i in range(1, deneme + 1):
        try:
            c = requests.get(f"{TEMEL_URL}{yol}", timeout=60)
            if c.status_code == 200:
                veri = c.json()
                if veri.get("code") == 200:
                    return veri["data"]
                raise AyetHatasi(f"API hatasi: {veri.get('status')}")
            son_hata = f"HTTP {c.status_code}"
        except Exception as e:                          # noqa: BLE001
            son_hata = str(e)[:80]
        if i < deneme:
            time.sleep(3 * i)

    raise AyetHatasi(f"Ayet metni alinamadi: {son_hata}")


def sure_listesi() -> List[Dict[str, Any]]:
    """114 surenin bilgisini dondurur (isim, ayet sayisi)."""
    onbellek = config.DATA_DIR / SURE_BILGISI_DOSYASI
    if onbellek.exists():
        try:
            return json.loads(onbellek.read_text(encoding="utf-8"))
        except Exception:
            pass

    veri = _istek("/surah")
    liste = [
        {
            "no": s["number"],
            "ad": s["name"],                       # Arapca ad
            "ad_tr": s["englishName"],             # latin harfli ad
            "ayet_sayisi": s["numberOfAyahs"],
        }
        for s in veri
    ]
    onbellek.write_text(
        json.dumps(liste, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return liste


def ayet_getir(sure_no: int, ayet_no: int) -> Dict[str, str]:
    """Tek bir ayetin Arapca metnini ve Turkce mealini dondurur."""
    arapca = _istek(f"/ayah/{sure_no}:{ayet_no}/{config.ARAPCA_KAYNAK}")
    turkce = _istek(f"/ayah/{sure_no}:{ayet_no}/{config.MEAL_KAYNAGI}")

    metin_ar = (arapca.get("text") or "").strip()
    metin_tr = (turkce.get("text") or "").strip()

    if not metin_ar or not metin_tr:
        raise AyetHatasi(f"{sure_no}:{ayet_no} icin metin bos geldi")

    return {
        "sure_no": sure_no,
        "ayet_no": ayet_no,
        "sure_adi": arapca.get("surah", {}).get("englishName", ""),
        "sure_adi_ar": arapca.get("surah", {}).get("name", ""),
        "arapca": metin_ar,
        "turkce": metin_tr,
        "sayfa": arapca.get("page"),
        "cuz": arapca.get("juz"),
    }


# ------------------------------------------------------------------ secim
def sonraki_ayetler(adet_min: int = 1, adet_max: int = 3) -> List[Dict[str, str]]:
    """Kaldigi yerden sonraki ayetleri getirir.

    Sure sonuna gelirse sonraki sureye gecer; ayetler sure siniri asmaz
    (konu butunlugu bozulmasin diye).
    """
    ilerleme = ilerleme_oku()
    sure_no, ayet_no = ilerleme["sure"], ilerleme["ayet"]

    sureler = {s["no"]: s for s in sure_listesi()}

    if sure_no > 114:
        logger.uyari("Kuran tamamlandi! Bastan basliyoruz.")
        sure_no, ayet_no = 1, 1

    sure = sureler[sure_no]
    kalan = sure["ayet_sayisi"] - ayet_no + 1

    if kalan <= 0:
        # Bu sure bitti, sonrakine gec
        sure_no += 1
        ayet_no = 1
        if sure_no > 114:
            sure_no = 1
        sure = sureler[sure_no]
        kalan = sure["ayet_sayisi"]

    adet = min(adet_max, kalan)
    adet = max(adet, min(adet_min, kalan))

    ayetler = []
    for i in range(adet):
        ayetler.append(ayet_getir(sure_no, ayet_no + i))
        time.sleep(0.4)          # API'yi yormayalim

    return ayetler


def ilerlemeyi_kaydet(ayetler: List[Dict[str, str]]) -> None:
    """Kullanilan ayetlerden sonrasina gec."""
    if not ayetler:
        return
    son = ayetler[-1]
    sure_no, ayet_no = son["sure_no"], son["ayet_no"] + 1

    sureler = {s["no"]: s for s in sure_listesi()}
    if ayet_no > sureler[sure_no]["ayet_sayisi"]:
        sure_no += 1
        ayet_no = 1
        if sure_no > 114:
            sure_no = 1

    onceki = ilerleme_oku()
    ilerleme_yaz(sure_no, ayet_no, onceki.get("tamamlanan_video", 0) + 1)


def konum_etiketi(ayetler: List[Dict[str, str]]) -> str:
    """Ekranin kosesinde gosterilecek etiket: 'Bakara 255' veya 'Bakara 1-3'."""
    if not ayetler:
        return ""
    ad = ayetler[0]["sure_adi"]
    ilk = ayetler[0]["ayet_no"]
    son = ayetler[-1]["ayet_no"]
    return f"{ad} {ilk}" if ilk == son else f"{ad} {ilk}-{son}"
