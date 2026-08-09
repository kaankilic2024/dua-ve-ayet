# -*- coding: utf-8 -*-
"""
TESHIS ARACI
API anahtarinin durumunu ve hangi modellere erisimin oldugunu kontrol eder.

Kullanim:
    python teshis.py
"""
import json
import sys

import config

try:
    import requests
except ImportError:
    print("HATA: 'requests' paketi kurulu degil.")
    print("Coz: python -m pip install -r requirements.txt")
    sys.exit(1)


def cizgi(baslik=""):
    print("\n" + "=" * 64)
    if baslik:
        print(f"  {baslik}")
        print("=" * 64)


# ------------------------------------------------------------ 1. ANAHTAR
cizgi("1) API ANAHTARI KONTROLU")

anahtar = config.GEMINI_API_KEY

if not anahtar:
    print("SONUC: ✗ Anahtar okunamadi.")
    print("\nKontrol et:")
    print("  - Proje klasorunde '.env' adinda bir dosya var mi?")
    print("  - Dosya adi '.env.txt' olmasin, tam olarak '.env' olmali.")
    print("  - Icinde su satir olmali: GEMINI_API_KEY=AIza...")
    sys.exit(1)

print(f"Uzunluk    : {len(anahtar)} karakter")
print(f"Basi/sonu  : {anahtar[:8]}...{anahtar[-4:]}")

# Google'in bilinen anahtar onekleri:
#   AIza... -> klasik format
#   AQ....  -> yeni AI Studio formati
BILINEN_ONEKLER = ("AIza", "AQ.")

olumcul = []
uyarilar = []

if anahtar.strip() != anahtar:
    olumcul.append("Anahtarin basinda/sonunda bosluk var.")
if "buraya" in anahtar.lower() or "yapistir" in anahtar.lower():
    olumcul.append("Ornek metin hala duruyor, gercek anahtar yapistirilmamis.")
if len(anahtar) < 30:
    olumcul.append("Anahtar cok kisa - eksik kopyalanmis olabilir.")
if not anahtar.startswith(BILINEN_ONEKLER):
    uyarilar.append(
        "Anahtar bilinen bir onekle baslamiyor (AIza / AQ.). "
        "Yeni bir format olabilir - yine de denenecek."
    )

if olumcul:
    print("\nSONUC: ✗ Anahtarda sorun var:")
    for s in olumcul:
        print(f"  - {s}")
    sys.exit(1)

for u in uyarilar:
    print(f"NOT: {u}")

print("SONUC: ✓ Anahtar okundu. Gercek testlere geciliyor.")


# ------------------------------------------------------------ 2. MODEL LISTESI
cizgi("2) HANGI MODELLERE ERISIMIN VAR?")

try:
    r = requests.get(
        config.GEMINI_MODEL_LISTESI_URL,
        headers={"x-goog-api-key": anahtar},
        timeout=60,
    )
except Exception as e:
    print(f"SONUC: ✗ Internete cikilamadi: {e}")
    print("Guvenlik duvari / VPN / antivirus engelliyor olabilir.")
    sys.exit(1)

print(f"HTTP durum : {r.status_code}")

if r.status_code != 200:
    print("\nSONUC: ✗ Model listesi alinamadi.")
    print("Sunucu cevabi:")
    print(r.text[:1200])
    if r.status_code in (400, 403):
        print("\nMuhtemel sebep: Anahtar gecersiz ya da 'Generative Language API'")
        print("projede etkin degil.")
    sys.exit(1)

modeller = r.json().get("models", [])
uretebilenler = [
    m for m in modeller
    if "generateContent" in m.get("supportedGenerationMethods", [])
]

print(f"Toplam {len(uretebilenler)} kullanilabilir model bulundu:\n")
isimler = []
for m in sorted(uretebilenler, key=lambda x: x["name"]):
    kisa = m["name"].replace("models/", "")
    isimler.append(kisa)
    print(f"  • {kisa}")

secili = config.GEMINI_MODEL
print(f"\nAyarlardaki model: {secili}")
if secili in isimler:
    print("SONUC: ✓ Bu modele erisimin var.")
else:
    print("SONUC: ✗ Bu model listede YOK.")
    print("   config.py veya .env icindeki GEMINI_MODEL degerini")
    print("   yukaridaki listeden biriyle degistir.")


# ------------------------------------------------------------ 3. GERCEK ISTEK
cizgi("3) KUCUK BIR DENEME ISTEGI")

url = config.GEMINI_URL.format(model=secili)
govde = {
    "contents": [{"role": "user", "parts": [{"text": "Sadece 'merhaba' yaz."}]}],
    "generationConfig": {"maxOutputTokens": 400},
}

try:
    r = requests.post(
        url,
        json=govde,
        headers={"x-goog-api-key": anahtar, "Content-Type": "application/json"},
        timeout=60,
    )
except Exception as e:
    print(f"SONUC: ✗ Istek gonderilemedi: {e}")
    sys.exit(1)

print(f"HTTP durum : {r.status_code}")

if r.status_code == 200:
    try:
        metin = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        print(f"Model cevabi: {metin.strip()!r}")
    except Exception:
        print("Cevap geldi ama beklenen formatta degil:")
        print(r.text[:600])
    print("\nSONUC: ✓ HER SEY CALISIYOR. 'python main.py --tip shorts' calistirabilirsin.")

elif r.status_code == 429:
    print("\nSONUC: ✗ KOTA/LIMIT HATASI (429)")
    print("Sunucunun tam cevabi (BUNU BANA GONDER):")
    print("-" * 64)
    try:
        print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:2000])
    except Exception:
        print(r.text[:2000])
    print("-" * 64)
    print("\nEn sik sebepler:")
    print("  a) Bu model ucretsiz katmanda sunulmuyor -> baska model dene")
    print("  b) Anahtar, faturalandirmasi olmayan eski bir projede olusturulmus")
    print("  c) Gunluk ucretsiz istek hakki gercekten dolmus -> yarin tekrar dene")

else:
    print(f"\nSONUC: ✗ Beklenmedik hata.")
    print("Sunucunun tam cevabi (BUNU BANA GONDER):")
    print("-" * 64)
    print(r.text[:2000])
    print("-" * 64)
