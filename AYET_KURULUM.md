# Dua Ve Ayet — Kurulum Rehberi

> Dördüncü kanal. Diğer projelerden en farklı olanı: burada yapay zeka
> **ayet metni üretmiyor**, metin doğrudan API'den birebir alınıyor.

---

## Nasıl çalışıyor

1. Kaldığı yerden sıradaki ayet(ler)i API'den çeker (Arapça + Diyanet meali)
2. Yapay zeka sadece **başlık ve açıklama** yazar — ayete dokunmaz
3. Türkçe meali seslendirir
4. Senin cami videonun üstüne Arapça metni, Türkçe meali ve konum etiketini
   bindirir
5. YouTube'a yükler

**Neden yapay zeka ayet yazmıyor:** Uydurma ayet, harf hatası veya yanlış
meal riski var. Metin `api.alquran.cloud` üzerinden birebir alınıyor.

---

## Diğer kanallardan farklar

| | Diğerleri | Dua Ve Ayet |
|---|---|---|
| Çalışma saati | 08:00 / 11:00 / 14:00 | **06:00** |
| Görsel | Pexels stok foto | **Senin cami videon** |
| Ses | Puck / Aoede / Kore | **Charon** (derin, sakin) |
| Geçiş efekti | var | **yok** (ağırbaşlı ton) |
| İçerik üretimi | AI senaryo yazar | **API'den birebir metin** |

---

## Kurulum

### 1. Klasörü yerleştir
`ayet_otomasyon` klasörünü diğer projelerin yanına koy.

### 2. Arka plan videosunu ekle
Çektiğin cami videosunu şuraya koy:

```
assets/arkaplan/cami.mp4
```

Video **dikey** olmalı. Kısa olması sorun değil — kod otomatik döngüye alıyor.
Birden fazla video koyarsan her videoda rastgele seçilir.

### 3. YouTube kanalını aç
1. youtube.com → profil → **Ayarlar** → **Kanal ekle veya yönet**
2. **Kanal oluştur** → adı: `Dua Ve Ayet`
3. Studio → Özelleştirme → handle: `@duaveayet`

### 4. Yeni Gemini anahtarı
Başka bir Google hesabından:
1. Gizli pencere (Ctrl+Shift+N)
2. https://aistudio.google.com/apikey
3. **Create API key in new project**

### 5. `.env` dosyası

```
notepad .env
```

İçine:

```
GEMINI_API_KEY=AQ.yeni_anahtarin
GEMINI_MODEL=gemini-3.6-flash
SES_MOTORU=gemini
GEMINI_SESI=Charon
YOUTUBE_GIZLILIK=public
MOCK=0
```

Test:

```
python teshis.py
```

### 6. Müzik ekle (isteğe bağlı)
`assets/music` klasörüne sakin, telifsiz bir parça koyabilirsin.
Ses seviyesi düşük ayarlı (%10), anlatımın önüne geçmez.

### 7. client_secret.json
Başka bir projeden bu projenin `data` klasörüne kopyala.

### 8. YouTube yetkilendirmesi

```
python main.py --youtube-giris
```

Tarayıcıda **Dua Ve Ayet kanalını** seç.

### 9. İlk video

```
python main.py --adet 1
```

Fatiha 1. ayetten başlayacak.

---

## Komutlar

```
python main.py                    # 3 video üret
python main.py --adet 1           # tek video
python main.py --nerede           # kaldığın yeri göster
python main.py --atla 2 255       # Bakara 255'e atla
python main.py --montaj son       # videoyu yeniden oluştur
python main.py --yukle son        # YouTube'a yükle
python main.py --sesler           # ses seçenekleri
```

---

## Ayarlar (`config.py`)

```python
AYET_MIN = 1                  # video başına en az kaç ayet
AYET_MAX = 3                  # en fazla kaç ayet
ARKAPLAN_KARARTMA = 0.28      # 0 = karartma yok, 1 = simsiyah
ARAPCA_SATIR_UZUNLUGU = 26    # satır başına Arapça karakter
DIKEY_KAYDIRMA = -0.04        # metinleri yukarı/aşağı kaydır
MUZIK_SESI = 0.10
GUNLUK_ADET = 3
```

---

## Arapça yazı hakkında

Arapça sağdan sola yazılır ve harfler birbirine bağlanır. Kod bunu şöyle
çözüyor:

- **Satır bölme özel yapılıyor.** Normal satır bölme Arapça'da kelime
  sırasını bozuyor. Kod her satırı ayrı bir öge olarak çiziyor.
- **Punto otomatik ayarlanıyor.** Uzun ayetlerde yazı küçülüyor, kısa
  ayetlerde büyüyor.
- **Metinler asla üst üste binmiyor.** Arapça ve Türkçe blokların yüksekliği
  önceden hesaplanıp ekrana dağıtılıyor.

**Yazı tipi gereksinimi:**
- Windows: `Traditional Arabic` (hazır gelir)
- GitHub Actions: `fonts-hosny-amiri` (iş akışı otomatik kuruyor)

Harfler kutu olarak çıkıyorsa yazı tipi bulunamamış demektir.

---

## İlerleme takibi

Kaldığın yer `data/ayet_ilerleme.json` dosyasında tutuluyor. GitHub Actions
her çalıştığında bunu depoya geri yazıyor, böylece sıra kaybolmuyor.

Kuran bitince (6.236 ayet) otomatik olarak başa dönüyor.

---

## Dikkat edilecekler

**Ayet sınırı aşılmıyor.** Bir video birden fazla sureye yayılmıyor; konu
bütünlüğü korunuyor.

**Meal kaynağı açıklamada belirtiliyor.** Her videonun açıklamasında
"Meal: Diyanet İşleri Başkanlığı" yazıyor.

**Yorum yapılmıyor.** Yapay zekaya tefsir, hüküm veya yorum yazması yasak.
Sadece başlık ve kısa bir konu tanıtımı yazıyor.
