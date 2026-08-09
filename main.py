# -*- coding: utf-8 -*-
"""
DUA VE AYET - OTOMASYON

Kullanim:
    python main.py                      # gunluk plani calistir
    python main.py --adet 1             # tek video
    python main.py --mock               # API'siz test
    python main.py --montaj son         # videoyu yeniden olustur
    python main.py --yukle son          # YouTube'a yukle
    python main.py --nerede             # kalinan yeri goster
    python main.py --atla 2 255         # belirli bir ayete atla
"""
import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

import config
from utils import ayet_kaynak, logger
from steps import step2_metin, step4_ses, step5_montaj, step6_yukle


def _klasor_adi(etiket: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    ad = etiket.translate(tr)
    ad = "".join(c if c.isalnum() else "_" for c in ad).strip("_").lower()
    damga = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{damga}_{ad}"[:80]


def tek_video(yukle: bool = False) -> Path:
    logger.baslik("YENI VIDEO")

    # --- ADIM 1: ayetleri getir
    logger.adim("ADIM 1/5  Ayetler getiriliyor")
    ayetler = ayet_kaynak.sonraki_ayetler()
    etiket = ayet_kaynak.konum_etiketi(ayetler)

    logger.ok(f"{len(ayetler)} ayet: {etiket}")
    for a in ayetler:
        print(f"\n   {a['sure_adi']} {a['ayet_no']}")
        print(f"   {a['arapca'][:70]}")
        print(f"   {a['turkce'][:90]}")
    print()

    # --- ADIM 2: baslik ve aciklama
    logger.adim("ADIM 2/5  Baslik ve aciklama")
    meta = step2_metin.metin_uret(ayetler, etiket)

    veri = {
        "ayetler": ayetler,
        "etiket": etiket,
        "baslik": meta["baslik"],
        "aciklama": meta["aciklama"],
        "etiketler": meta["etiketler"],
        "genislik": config.GENISLIK,
        "yukseklik": config.YUKSEKLIK,
    }

    proje_dir = config.OUTPUT_DIR / _klasor_adi(etiket)
    sayac = 2
    while proje_dir.exists():
        proje_dir = proje_dir.with_name(f"{proje_dir.name}_{sayac}")
        sayac += 1
    proje_dir.mkdir(parents=True)
    (proje_dir / "ses").mkdir()

    _kaydet(proje_dir, veri)

    # --- ADIM 3: seslendirme
    logger.adim("ADIM 3/5  Seslendirme")
    step4_ses.seslendir(proje_dir, veri)
    _kaydet(proje_dir, veri)

    # --- ADIM 4: montaj
    logger.adim("ADIM 4/5  Video olusturuluyor")
    step5_montaj.videoyu_olustur(proje_dir, veri)
    _kaydet(proje_dir, veri)

    # Ilerlemeyi kaydet: bu ayetler kullanildi
    ayet_kaynak.ilerlemeyi_kaydet(ayetler)

    # --- ADIM 5: yukleme
    if not yukle:
        logger.bilgi(
            f"Video hazir. Yuklemek icin: python main.py --yukle {proje_dir.name}"
        )
        return proje_dir

    logger.adim("ADIM 5/5  YouTube'a yukleniyor")
    try:
        step6_yukle.yukle(proje_dir, veri)
    except Exception as e:                            # noqa: BLE001
        logger.hata(f"Yukleme basarisiz: {e}")
    finally:
        _kaydet(proje_dir, veri)

    return proje_dir


def _kaydet(proje_dir: Path, veri: dict) -> None:
    (proje_dir / "veri.json").write_text(
        json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Insan gozuyle okunacak ozet
    satirlar = [
        f"BASLIK : {veri['baslik']}",
        f"KONUM  : {veri['etiket']}",
        "",
        "ACIKLAMA:",
        veri["aciklama"],
        "",
        "ETIKETLER: " + ", ".join(veri["etiketler"]),
        "",
        "=" * 70,
    ]
    for a in veri["ayetler"]:
        satirlar += [
            f"\n[{a['sure_adi']} {a['ayet_no']}]",
            f"  {a['arapca']}",
            f"  {a['turkce']}",
        ]
    (proje_dir / "ozet.txt").write_text("\n".join(satirlar), encoding="utf-8")


def _proje_bul(klasor: str) -> Path:
    if klasor.lower() in ("son", "last", "sonuncu"):
        projeler = sorted(
            (d for d in config.OUTPUT_DIR.iterdir()
             if d.is_dir() and (d / "veri.json").exists()),
            key=lambda d: d.stat().st_mtime,
        )
        if not projeler:
            raise FileNotFoundError("Hic proje yok. Once bir video uret.")
        logger.bilgi(f"En son proje: {projeler[-1].name}")
        return projeler[-1]

    yol = Path(klasor)
    if not yol.is_absolute():
        yol = config.OUTPUT_DIR / klasor
    if (yol / "veri.json").exists():
        return yol

    mevcut = sorted(
        (d.name for d in config.OUTPUT_DIR.iterdir()
         if d.is_dir() and (d / "veri.json").exists()), reverse=True
    )
    mesaj = f"'{klasor}' bulunamadi."
    if mevcut:
        mesaj += "\n\nMevcut projeler:\n" + "\n".join(f"    {a}" for a in mevcut[:10])
        mesaj += "\n\nEn sonuncusu icin:  python main.py --montaj son"
    raise FileNotFoundError(mesaj)


def main() -> int:
    p = argparse.ArgumentParser(description="Dua Ve Ayet otomasyonu")
    p.add_argument("--adet", type=int, help="Kac video uretilecek")
    p.add_argument("--mock", action="store_true", help="API'siz test")
    p.add_argument("--yukle-otomatik", action="store_true",
                   help="Uretim bitince otomatik yukle")
    p.add_argument("--montaj", metavar="KLASOR", help="Videoyu yeniden olustur")
    p.add_argument("--yukle", metavar="KLASOR", help="YouTube'a yukle")
    p.add_argument("--youtube-giris", action="store_true", help="Yetkilendirme")
    p.add_argument("--youtube-cikis", action="store_true", help="Izni sil")
    p.add_argument("--sesler", action="store_true", help="Ses secenekleri")
    p.add_argument("--nerede", action="store_true", help="Kalinan yeri goster")
    p.add_argument("--atla", nargs=2, type=int, metavar=("SURE", "AYET"),
                   help="Belirli bir ayete atla")
    args = p.parse_args()

    if args.mock:
        config.MOCK = True

    try:
        if args.nerede:
            i = ayet_kaynak.ilerleme_oku()
            sureler = {s["no"]: s for s in ayet_kaynak.sure_listesi()}
            s = sureler.get(i["sure"], {})
            logger.baslik("KALINAN YER")
            print(f"  Sure  : {i['sure']} - {s.get('ad_tr', '?')}")
            print(f"  Ayet  : {i['ayet']} / {s.get('ayet_sayisi', '?')}")
            print(f"  Video : {i.get('tamamlanan_video', 0)} tane uretildi")
            return 0

        if args.atla:
            sure, ayet = args.atla
            ayet_kaynak.ilerleme_yaz(sure, ayet,
                                     ayet_kaynak.ilerleme_oku().get("tamamlanan_video", 0))
            logger.ok(f"Sonraki video {sure}:{ayet} ayetinden baslayacak.")
            return 0

        if args.sesler:
            step4_ses.sesleri_listele()
            return 0

        if args.youtube_cikis:
            step6_yukle.cikis_yap()
            return 0

        if args.youtube_giris:
            step6_yukle.giris_yap()
            return 0

        if args.montaj:
            proje = _proje_bul(args.montaj)
            veri = json.loads((proje / "veri.json").read_text(encoding="utf-8"))
            logger.baslik(f"MONTAJ  •  {veri['baslik']}")
            step5_montaj.videoyu_olustur(proje, veri)
            _kaydet(proje, veri)
            return 0

        if args.yukle:
            proje = _proje_bul(args.yukle)
            veri = json.loads((proje / "veri.json").read_text(encoding="utf-8"))
            logger.baslik(f"YUKLEME  •  {veri['baslik']}")
            try:
                step6_yukle.yukle(proje, veri)
            finally:
                _kaydet(proje, veri)
            return 0

    except Exception as e:                            # noqa: BLE001
        logger.hata(str(e))
        return 1

    # --- uretim
    adet = args.adet or config.GUNLUK_ADET
    logger.baslik(f"{adet} video uretilecek")

    basarili, basarisiz = [], []
    for i in range(1, adet + 1):
        print(f"\n\033[1m### {i}/{adet} ###\033[0m")
        try:
            basarili.append(tek_video(yukle=args.yukle_otomatik))
        except Exception as e:                        # noqa: BLE001
            logger.hata(f"Basarisiz: {e}")
            traceback.print_exc()
            basarisiz.append(str(e))

    logger.baslik("OZET")
    logger.ok(f"Basarili: {len(basarili)}")
    for yol in basarili:
        print(f"   → {yol.name}")
    if basarisiz:
        logger.hata(f"Basarisiz: {len(basarisiz)}")
        for h in basarisiz:
            print(f"   → {h}")

    return 0 if basarili else 1


if __name__ == "__main__":
    sys.exit(main())
