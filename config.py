# -*- coding: utf-8 -*-
"""
Merkezi ayar dosyasi. Degistirmek istedigin her sey burada.
"""
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------- KLASORLER
KOK = Path(__file__).parent
OUTPUT_DIR = KOK / "output"
DATA_DIR = KOK / "data"
ASSETS_DIR = KOK / "assets"
MUSIC_DIR = ASSETS_DIR / "music"
SFX_DIR = ASSETS_DIR / "sfx"
ARKAPLAN_DIR = ASSETS_DIR / "arkaplan"

for _d in (OUTPUT_DIR, DATA_DIR, ASSETS_DIR, MUSIC_DIR, SFX_DIR, ARKAPLAN_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_YEDEK_MODELLER = [
    "gemini-3.6-flash", "gemini-flash-latest",
    "gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite",
]
GEMINI_DUSUNME_BUTCESI = 512

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)
GEMINI_MODEL_LISTESI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
)

# ---------------------------------------------------------------- KANAL
KANAL_ADI = "Dua Ve Ayet"

# ---------------------------------------------------------------- AYET KAYNAGI
# Metin API'den birebir alinir, yapay zekaya yazdirilmaz.
ARAPCA_KAYNAK = "quran-uthmani"      # Osmanli hatli standart metin
MEAL_KAYNAGI = "tr.diyanet"          # Diyanet Isleri Meali

# Video basina kac ayet (konu butunlugune gore degisir)
AYET_MIN = 1
AYET_MAX = 3

# ---------------------------------------------------------------- VIDEO
GENISLIK = 1080
YUKSEKLIK = 1920
FPS = 30

# ARKA PLAN
#   "uretilmis" -> kod uretir: koyu gradyan + suzulen silik altin zerreler
#   "video"     -> assets/arkaplan klasorune koydugun videolar kullanilir
ARKAPLAN_TIPI = os.getenv("ARKAPLAN_TIPI", "video")

ARKAPLAN_KARARTMA = 0.25     # 0 = karartma yok; yazi okunsun diye hafif koyultma
ZERRE_SAYISI = 26            # daha fazlasi = daha yogun, ama render yavaslar
ZERRE_YUMUSAKLIK = 2.5       # gblur sigma; buyudukce zerreler isik lekesine doner
ZERRE_YOGUNLUK = 0.55        # 0-1; zerrelerin ne kadar belirgin olacagi

# ---------------------------------------------------------------- YAZI
# Arapca yazi tipi. Windows'ta "Arabic Typesetting" veya "Traditional Arabic"
# bulunur; Linux'ta (GitHub Actions) Amiri kurulur.
ARAPCA_YAZI_TIPI = os.getenv(
    "ARAPCA_YAZI_TIPI",
    "Traditional Arabic" if sys.platform == "win32" else "Amiri"
)
TURKCE_YAZI_TIPI = os.getenv(
    "TURKCE_YAZI_TIPI",
    "Verdana" if sys.platform == "win32" else "DejaVu Sans"
)

ARAPCA_BOYUT_ORANI = 0.058       # video yuksekliginin orani
# Bir satirda kac Arapca karakter (hareke haric) olsun. Kucultursen punto
# buyur ama satir sayisi artar. 22-30 arasi iyi calisiyor.
ARAPCA_SATIR_UZUNLUGU = 26
TURKCE_BOYUT_ORANI = 0.040
ETIKET_BOYUT_ORANI = 0.024       # kosedeki "Bakara 255" etiketi

ARAPCA_RENK = "&H00FFFFFF"       # beyaz (ASS formati: &HAABBGGRR)
TURKCE_RENK = "&H00E8F0F5"       # kirik beyaz
ETIKET_RENK = "&H00B0D0E0"       # soluk mavi
KENAR_RENGI = "&H00202020"

# Arapca ve Turkce metin blogu ekranda otomatik ortalanir; asagidaki deger
# tum blogu yukari (negatif) veya asagi (pozitif) kaydirir.
DIKEY_KAYDIRMA = -0.04
ETIKET_KONUM = 0.06

# ---------------------------------------------------------------- SESLENDIRME
SES_MOTORU = os.getenv("SES_MOTORU", "gemini")
GEMINI_SES_MODELI = os.getenv("GEMINI_SES_MODELI", "gemini-2.5-flash-preview-tts")
GEMINI_SES_YEDEK_MODELLER = ["gemini-3.1-flash-tts-preview"]
GEMINI_SESI = os.getenv("GEMINI_SESI", "Charon")

GEMINI_SES_SECENEKLERI = [
    ("Charon", "derin, sakin"),
    ("Aoede", "havadar, yumusak"),
    ("Kore", "kararli, net"),
    ("Leda", "genc, parlak"),
]

GEMINI_SES_YONERGE = (
    "Asagidaki metni Turkce olarak, sakin, agirbasli ve saygili bir tonla oku. "
    "Acele etme, kelimeleri net soyle. Duygu katma, sade ve huzurlu bir "
    "anlatim yap. Sadece metni oku, baska hicbir sey soyleme:"
)

SES_ARASI_BEKLEME = float(os.getenv("SES_ARASI_BEKLEME", "6"))

# Gemini hiz limitine takilirsa: uzun uzun beklemek yerine hemen edge-tts'e
# dusmek daha mantikli. Beklemek istersen True yap.
GEMINI_HIZ_LIMITINDE_BEKLE = False
GEMINI_HIZ_LIMIT_BEKLEMESI = 20

# edge-tts yedegi icin
SES_TONLARI = {
    "sakin": {
        "ses": "tr-TR-AhmetNeural", "hiz": "-8%", "perde": "-2Hz",
        "aciklama": "Sakin ve agirbasli",
    },
    "sakin_kadin": {
        "ses": "tr-TR-EmelNeural", "hiz": "-8%", "perde": "-2Hz",
        "aciklama": "Sakin kadin sesi",
    },
}
SES_TONU = os.getenv("SES_TONU", "sakin")
_ton = SES_TONLARI.get(SES_TONU, SES_TONLARI["sakin"])
SES_ADI = os.getenv("SES_ADI", _ton["ses"])
SES_HIZI = os.getenv("SES_HIZI", _ton["hiz"])
SES_PERDESI = os.getenv("SES_PERDESI", _ton["perde"])

SESSIZLIK_KIRP = True
SESSIZLIK_ESIGI = "-50dB"
CUMLE_ARASI_DURAKLAMA = 0.55     # ayet arasi biraz daha uzun dursun

# ---------------------------------------------------------------- MONTAJ
X264_KALITE = 23
X264_HIZI = "veryfast"
AYET_ARASI_BOSLUK = 0.9          # ayetler arasi sessizlik
SON_BOSLUK = 0.4
GECICI_DOSYALARI_SIL = True

MUZIK_KULLAN = True
MUZIK_SESI = 0.10

# Bu kanalda gecis efekti kullanilmiyor: agirbasli ton bozulmasin
SFX_KULLAN = False
SFX_TIPI = "chime"
SFX_SESI = 0.15
SFX_TEPE_GENLIK = 0.5

SES_NORMALIZE = True
HEDEF_SES_SEVIYESI = -15

# ---------------------------------------------------------------- YOUTUBE
CLIENT_SECRET = DATA_DIR / "client_secret.json"
TOKEN_DOSYASI = DATA_DIR / "youtube_token.json"

YOUTUBE_KATEGORI_ID = "22"           # 22 = People & Blogs
YOUTUBE_GIZLILIK = os.getenv("YOUTUBE_GIZLILIK", "public")
COCUKLAR_ICIN = False
YOUTUBE_DIL = "tr"
ALTYAZI_YUKLE = False                # yazi zaten videoda gomulu

ACIKLAMA_SONU = (
    "Meal: Diyanet İşleri Başkanlığı\n"
    "Arapça metin: Kuran-ı Kerim (Osmanlı hattı)"
)

# Gunluk kac video
GUNLUK_ADET = int(os.getenv("GUNLUK_ADET", "3"))

# ---------------------------------------------------------------- GENEL
MOCK = os.getenv("MOCK", "0") == "1"
