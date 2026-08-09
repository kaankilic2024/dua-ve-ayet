# -*- coding: utf-8 -*-
"""
OAUTH TESHIS
YouTube yetkilendirmesinde hata alindiginda sorunun nerede oldugunu bulur.

Kullanim:
    python teshis_oauth.py
"""
import json
import sys
from urllib.parse import parse_qs, urlparse

import config

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def cizgi(baslik=""):
    print("\n" + "=" * 64)
    if baslik:
        print(f"  {baslik}\n" + "=" * 64)


def gizle(deger: str, bas: int = 12) -> str:
    if not deger:
        return "(bos)"
    return f"{deger[:bas]}...{deger[-6:]}  ({len(deger)} karakter)"


# ------------------------------------------------------------ 1. DOSYA
cizgi("1) client_secret.json YAPISI")

if not config.CLIENT_SECRET.exists():
    print(f"SONUC: ✗ Dosya yok: {config.CLIENT_SECRET}")
    sys.exit(1)

try:
    veri = json.loads(config.CLIENT_SECRET.read_text(encoding="utf-8-sig"))
except Exception as e:
    print(f"SONUC: ✗ Dosya okunamadi/bozuk: {e}")
    sys.exit(1)

tur = list(veri.keys())[0] if veri else None
print(f"Uygulama turu : {tur}")

if tur != "installed":
    print("\nSONUC: ✗ Tur 'installed' olmali (Masaustu uygulamasi).")
    print("   Google Cloud > Musteriler > OAuth istemcisi olustur")
    print("   > Uygulama turu: 'Masaustu uygulamasi' secmelisin.")
    sys.exit(1)

icerik = veri[tur]
print(f"Alanlar       : {', '.join(sorted(icerik.keys()))}")
print(f"client_id     : {gizle(icerik.get('client_id', ''))}")
print(f"client_secret : {gizle(icerik.get('client_secret', ''), 6)}")
print(f"auth_uri      : {icerik.get('auth_uri', '(yok)')}")
print(f"token_uri     : {icerik.get('token_uri', '(yok)')}")
print(f"redirect_uris : {icerik.get('redirect_uris', '(yok)')}")

eksikler = [a for a in ("client_id", "client_secret", "auth_uri", "token_uri")
            if not icerik.get(a)]
if eksikler:
    print(f"\nSONUC: ✗ Su alanlar eksik: {eksikler}")
    print("   Dosya tam indirilmemis olabilir. Yeniden indir.")
    sys.exit(1)

if not icerik.get("client_id", "").endswith(".apps.googleusercontent.com"):
    print("\nUYARI: client_id beklenen bicimde degil.")

print("\nSONUC: ✓ Dosya yapisi dogru gorunuyor.")


# ------------------------------------------------------------ 2. ADRES
cizgi("2) YETKILENDIRME ADRESI OLUSTURULUYOR")

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError as e:
    print(f"SONUC: ✗ Paket eksik ({e})")
    print("   Coz: python -m pip install -r requirements.txt")
    sys.exit(1)

try:
    akis = InstalledAppFlow.from_client_secrets_file(
        str(config.CLIENT_SECRET), SCOPES
    )
    akis.redirect_uri = "http://localhost:8080/"
    adres, _ = akis.authorization_url(prompt="select_account consent")
except Exception as e:
    print(f"SONUC: ✗ Adres olusturulamadi: {e}")
    sys.exit(1)

parcalar = urlparse(adres)
parametreler = parse_qs(parcalar.query)

print(f"Sunucu : {parcalar.scheme}://{parcalar.netloc}{parcalar.path}")
print("Parametreler:")
for anahtar in sorted(parametreler):
    deger = parametreler[anahtar][0]
    if anahtar == "client_id":
        deger = gizle(deger)
    elif len(deger) > 90:
        deger = deger[:90] + "..."
    print(f"   {anahtar:16} = {deger}")

sorunlar = []
if "scope" not in parametreler:
    sorunlar.append("scope parametresi yok")
if "redirect_uri" not in parametreler:
    sorunlar.append("redirect_uri parametresi yok")
elif "localhost" not in parametreler["redirect_uri"][0]:
    sorunlar.append(f"redirect_uri beklenmedik: {parametreler['redirect_uri'][0]}")
if "response_type" not in parametreler:
    sorunlar.append("response_type parametresi yok")

if sorunlar:
    print("\nSONUC: ✗ Adreste sorun var:")
    for s in sorunlar:
        print(f"   - {s}")
else:
    print("\nSONUC: ✓ Adres dogru olusturuluyor.")


# ------------------------------------------------------------ 3. ELLE DENEME
cizgi("3) ELLE DENEME")

print("Asagidaki adresi kopyalayip tarayicida ac.")
print("Google yine 400 verirse sorun Google Cloud ayarlarindadir,")
print("kodda degil. O durumda adres cubugundaki hatayi bana gonder.\n")
print("-" * 64)
print(adres)
print("-" * 64)
print("\nBeklenen: hesap secim ekrani veya 'Google bu uygulamayi dogrulamadi' uyarisi.")
print("Uyari cikarsa: Gelismis > ...uygulamaya git (guvenli degil)")
