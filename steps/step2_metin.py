# -*- coding: utf-8 -*-
"""
ADIM 2 - BASLIK VE ACIKLAMA (ayet kanali)

ONEMLI: Ayet metni burada URETILMEZ. Metin API'den birebir gelir.
Yapay zeka sadece YouTube basligi ve aciklamasi yazar; ayete dokunmaz.
Boylece uydurma ayet riski tamamen ortadan kalkar.
"""
import re
from typing import Any, Dict, List

import config
from utils import ai, logger

SISTEM = """Sen bir YouTube kanalinin icerik editorusun.

KANAL: {kanal_adi}
Kanalda Kuran ayetleri Arapca metni ve Turkce meali ile paylasilir.

GOREVIN: Verilen ayet(ler) icin YouTube basligi ve aciklamasi yazmak.

KESIN KURALLAR:
- AYET METNINI DEGISTIRME, YENIDEN YAZMA, YORUMLAMA.
- Dini hukum verme, tefsir yapma, "bu ayet sunu emrediyor" deme.
- Kendi yorumunu katma. Sadece ayetin konusuna isaret et.
- Mezhep tartismasina girme, karsilastirma yapma.
- Abartili vaat etme ("bu ayeti okuyan sunu kazanir" gibi).
- Baslikta clickbait yapma. Saygili ve sade ol.

BASLIK KURALLARI:
- Sure adi ve ayet numarasi mutlaka gecsin.
- 60 karakteri gecmesin.
- Ayetin konusuna kisa bir isaret ekleyebilirsin.
- Ornek: "Bakara Suresi 255 - Ayetel Kursi"
- Ornek: "Fatiha Suresi 1-3"
- Ornek: "Duha Suresi 5 - Rabbinin Lutfu"

ACIKLAMA KURALLARI:
- 2-3 cumle. Ayetin hangi konudan bahsettigini sade dille belirt.
- Yorum yapma, sadece konu basligi soyler gibi yaz.
- Sonra bos satir, sonra 5 hashtag.

Cevabini SADECE su JSON formatinda ver:
{{
  "baslik": "YouTube basligi",
  "aciklama": "Aciklama metni, sonra bos satir, sonra hashtagler",
  "etiketler": ["8", "adet", "turkce", "etiket"]
}}"""

MOCK = {
    "baslik": "Fatiha Suresi 1-3",
    "aciklama": "Fatiha Suresi'nin ilk üç ayeti. Rahman ve Rahim olan Allah'ın "
                "adıyla başlayan bu ayetler hamd ve şükrü dile getirir.\n\n"
                "#kuran #ayet #meal #fatiha #duaveayet",
    "etiketler": ["kuran", "ayet", "meal", "fatiha suresi", "kuran meali",
                  "türkçe meal", "dua ve ayet", "diyanet meali"],
}


def _temizle_baslik(baslik: str) -> str:
    baslik = re.sub(r"\s+", " ", baslik).strip()
    return baslik[:95]


def metin_uret(ayetler: List[Dict[str, str]], etiket: str) -> Dict[str, Any]:
    """Ayetler icin baslik ve aciklama uretir."""
    logger.bilgi(f"Baslik ve aciklama yaziliyor... ({etiket})")

    ayet_listesi = "\n\n".join(
        f"{a['sure_adi']} Suresi, {a['ayet_no']}. ayet\n"
        f"Meal: {a['turkce']}"
        for a in ayetler
    )

    istek = (
        f"Su ayet(ler) icin baslik ve aciklama yaz.\n"
        f"Konum: {etiket}\n\n{ayet_listesi}"
    )

    sonuc = ai.sor(
        SISTEM.format(kanal_adi=config.KANAL_ADI),
        istek, sicaklik=0.6, mock_cevap=MOCK,
    )

    baslik = _temizle_baslik(str(sonuc.get("baslik", "")))
    if not baslik:
        baslik = etiket           # yapay zeka basarisiz olursa konum etiketi yeter

    aciklama = str(sonuc.get("aciklama", "")).strip()
    if config.ACIKLAMA_SONU:
        aciklama = f"{aciklama}\n\n{config.ACIKLAMA_SONU}".strip()

    etiketler = [str(e).strip() for e in sonuc.get("etiketler", []) if str(e).strip()]
    if not etiketler:
        etiketler = ["kuran", "ayet", "meal", "türkçe meal", "dua ve ayet"]

    logger.ok(f"Baslik: {baslik}")

    return {
        "baslik": baslik,
        "aciklama": aciklama[:4900],
        "etiketler": etiketler[:15],
    }
