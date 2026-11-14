# Developed with assistance from Claude (Anthropic).
# d1_butunluk.py — Orbitrary v1.2, belge 17.3 D1 (bütünlük) + 17.2 zip açma.
# Girdi : veri/ (ham, salt okunur), kod/indirme_listesi.csv, kayit/E1_karolar.csv, kayit/indirme.csv
# Çıktı : veri/<govde>/<set>_<ad>/acik/  (zip içerikleri; ham zip silinmez)
#         kayit/D1.json, kayit/D1_dosyalar.csv, kayit/13_kasim_log.txt'ye bir satır
# Testler: (1) beklenen dosyalar var, fazla yok; (2) 0 bayt / HTML yok; (3) boyut = rapor;
#          (4) SHA-256 = indirme kaydı (indirmeden sonra değişmedi); (5) KONTROL dosyalarının içerik testi;
#          (6) zip açma (CRC zipfile tarafından, boyut = zip dizini); (7) açılış testleri (HDF4/HDF5/GeoTIFF/ENVI/vektör);
#          (8) raporun ek testleri (M5 11306 x 880, M6 259200 x 5). Geçmeyen test silinmez, FAIL yazılır.
import csv, hashlib, json, os, re, stat, sys, time, zipfile
from datetime import datetime
from pathlib import Path

KOK = Path.home() / "orbitrary"
VERI, KAYIT = KOK / "veri", KOK / "kayit"
PARCA = 8 * 1024 * 1024
IZINLI_EKSIK = {"mars/R4_tes_ti_albedo/nmsk2003.bin"}           # se.psi.edu açılmadı (kayıt: indirme.csv)
IZINLI_FAZLA_ON = "mars/R6_odyssey_grs/pds4_etiket/"           # R6 PDS4 etiketleri (kayıt: R6_karar.json)
ZIPLER = ["dunya/E3_glim/LiMW_GIS 2015.gdb.zip",
          "dunya/E7_permafrost_kuzey/UiO_PEX_PERPROB_5.0_20181128_2000_2016_NH.zip",
          "dunya/E8_permafrost_antarktika/UiO_PEX_PERPROB_5.0_20181205_2000_2017_ANT.zip",
          "dunya/E9_aridity/Global-AI_ET0__annual_v3_1.zip",
          "ay/M2_ay_jeoloji/Unified_Geologic_Map_of_the_Moon_GIS_v2.zip",
          "mars/R2_sim3292/sim3292_database.zip"]

TESTLER = []


def test(ad, gecti, detay=""):
    TESTLER.append({"test": ad, "durum": "PASS" if gecti else "FAIL", "detay": str(detay)})
    print(("[PASS] " if gecti else "[FAIL] ") + ad + ": " + str(detay)[:220], flush=True)


def dene(ad, f):
    try:
        g, d = f()
        test(ad, g, d)
    except Exception as e:
        test(ad, False, f"{type(e).__name__}: {e}")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(PARCA), b""):
            h.update(c)
    return h.hexdigest()


def main():
    t0 = time.time()
    from osgeo import gdal
    gdal.UseExceptions()
    import rasterio, pyogrio, h5py

    # ------------------------------------------------ beklenen dosyalar
    with open(KOK / "kod" / "indirme_listesi.csv", encoding="utf-8", newline="") as f:
        liste = list(csv.DictReader(f))
    with open(KAYIT / "E1_karolar.csv", encoding="utf-8", newline="") as f:
        karolar = list(csv.DictReader(f))
    beklenen = {}
    for r in liste:
        if r["yontem"] == "klasor":
            for k in karolar:
                beklenen["dunya/E1_etopo/" + k["ad"]] = dict(r, beklenen_bayt=k["bayt_HEAD"])
        else:
            beklenen[r["hedef"]] = r
    son = {}
    with open(KAYIT / "indirme.csv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["durum"] in ("PASS", "KONTROL"):
                son[row["hedef"]] = row                     # aynı dosyanın en son geçerli kaydı

    ham = sorted(p.relative_to(VERI).as_posix() for p in VERI.rglob("*")
                 if p.is_file() and "/acik/" not in "/" + p.relative_to(VERI).as_posix())
    hs = set(ham)
    eksik = sorted(h for h in beklenen if h not in hs)
    fazla = sorted(h for h in ham if h not in beklenen)
    test("D1_eksik_dosya_yok", set(eksik) <= IZINLI_EKSIK,
         f"{len(beklenen) - len(eksik)}/{len(beklenen)} var; eksik {eksik} (izinli: {sorted(IZINLI_EKSIK)})")
    test("D1_fazla_dosya_yok", all(h.startswith(IZINLI_FAZLA_ON) for h in fazla),
         f"fazla {len(fazla)} dosya: {fazla[:8]}")

    # ------------------------------------------------ dosya başına: 0 bayt, HTML, boyut, SHA-256
    satirlar, n_fail = [], 0
    print(f"SHA-256 yeniden hesaplanıyor: {len(ham)} dosya (birkaç dakika)...", flush=True)
    for i, h in enumerate(ham, 1):
        p = VERI / h
        b = p.stat().st_size
        with open(p, "rb") as f:
            bas = f.read(512)
        s = sha256(p)
        r = beklenen.get(h, {})
        bek = int(r["beklenen_bayt"]) if r.get("beklenen_bayt") else None
        kay = son.get(h, {}).get("sha256", "")
        html = bas.lstrip()[:15].lower().startswith((b"<!doctype", b"<html"))
        notlar = []
        if b == 0:
            notlar.append("0 bayt")
        if html:
            notlar.append("HTML")
        if bek is not None and b != bek:
            notlar.append(f"boyut {b} != rapor {bek}")
        if h in beklenen and kay != s:
            notlar.append("SHA-256 indirme kaydindan farkli" if kay else "indirme kaydi yok")
        durum = "FAIL" if notlar else "PASS"
        n_fail += durum == "FAIL"
        satirlar.append({"hedef": h, "set": h.split("/")[1].split("_")[0], "bayt": b, "rapor_bayt": bek or "",
                         "sha256": s, "durum": durum, "not": "; ".join(notlar)})
        if i % 50 == 0:
            print(f"   {i}/{len(ham)}", flush=True)
    test("D1_dosya_testleri", n_fail == 0,
         f"{len(satirlar) - n_fail}/{len(satirlar)} dosya: 0 bayt yok, HTML yok, boyut = rapor, SHA-256 = indirme kaydi"
         + ("" if n_fail == 0 else f"; FAIL: {[x['hedef'] for x in satirlar if x['durum'] == 'FAIL'][:8]}"))

    # ------------------------------------------------ KONTROL dosyalarının içerik testi
    def metin(h):
        return (VERI / h).read_text(encoding="utf-8", errors="replace")
    for oz in ("clay", "silt"):
        h = f"dunya/E10_soilgrids/{oz}/checksum.sha256.txt"
        deger = beklenen[f"dunya/E10_soilgrids/{oz}/{oz}_0-5cm_mean_1000.tif"]["saglama_degeri"]
        dene(f"KONTROL_{h}", lambda h=h, d=deger: (d.lower() in metin(h).lower(), "rapordaki SHA-256 dosyada geciyor"))
    for h in ("ay/M1_lola/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif.md5",
              "mars/R1_mola/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif.md5"):
        deger = beklenen[h[:-4]]["saglama_degeri"]
        dene(f"KONTROL_{h}", lambda h=h, d=deger: (d.lower() in metin(h).lower(), "rapordaki MD5 dosyada geciyor"))
    h = "ay/M1_lola/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.lbl"
    dene(f"KONTROL_{h}", lambda: (all(k in metin(h) for k in ("92160", "46080", "SignedWord"))
                                  and re.search(r"Multiplier\s*=\s*0\.5\b", metin(h)) is not None,
                                  "rapor M1: 92160 x 46080, SignedWord, Multiplier 0.5"))
    h2 = "mars/R1_mola/Mars_MGS_MOLA_DEM_mosaic_global_463m.lbl"
    dene(f"KONTROL_{h2}", lambda: ("46080" in metin(h2) and "23040" in metin(h2), "rapor R1: 46080 x 23040"))
    h3 = "mars/R2_sim3292/sim3292_readme.txt"
    dene(f"KONTROL_{h3}", lambda: ("3292" in metin(h3), f"metin dosyasi, '3292' geciyor ({(VERI / h3).stat().st_size} bayt)"))

    # ------------------------------------------------ zip açma (belge 17.2)
    acilan = {}
    for z in ZIPLER:
        def zip_ac(z=z):
            zp = VERI / z
            hedef = zp.parent / "acik"
            hedef.mkdir(exist_ok=True)
            with zipfile.ZipFile(zp) as zf:
                bilgi = [i for i in zf.infolist() if not i.is_dir()]
                yontem = sorted({i.compress_type for i in bilgi})
                if 9 in yontem:
                    raise RuntimeError("Deflate64 (9) var: inflate64 yolu gerekli (belge 17.2)")
                atla = [i for i in bilgi if i.filename.startswith("__MACOSX/") or Path(i.filename).name.startswith("._")]
                al = [i for i in bilgi if i not in atla]
                sifir = [i.filename for i in al if i.file_size == 0]
                n_yeni = 0
                for i in al:
                    out = hedef / i.filename
                    if out.exists() and out.stat().st_size == i.file_size:
                        continue
                    if out.exists():
                        os.chmod(out, stat.S_IWRITE | stat.S_IREAD)
                    zf.extract(i, hedef)                     # zipfile CRC'yi okurken denetler (hata -> BadZipFile)
                    n_yeni += 1
                    if out.stat().st_size != i.file_size or (i.file_size > 0 and out.stat().st_size == 0):
                        raise RuntimeError(f"acilan boyut tutmuyor: {i.filename}")
                    os.chmod(out, stat.S_IREAD)
                topl = sum(i.file_size for i in al)
            acilan[z] = hedef
            return True, (f"{len(al)} dosya ({n_yeni} yeni acildi), {topl / 1e9:.3f} GB, yontemler {yontem}, "
                          f"atlanan {len(atla)} (__MACOSX/._), zip dizininde 0 bayt girdi {len(sifir)}")
        dene(f"ZIP_{z}", zip_ac)

    # ------------------------------------------------ açılış testleri
    def ac(p):
        with rasterio.open(p) as d:
            return d.width, d.height, d.count, d.dtypes[0], str(d.crs)[:40] if d.crs else "CRS yok"
    def rast(ad, p):
        dene(ad, lambda: (True, ac(p)))

    # E1: 288 karonun hepsi açılıyor mu
    def e1():
        hata, tip = [], set()
        for k in karolar:
            try:
                w, h_, c, dt, _ = ac(VERI / "dunya/E1_etopo" / k["ad"])
                tip.add((w, h_, c, dt))
            except Exception as e:
                hata.append(k["ad"])
        return not hata, f"{len(karolar) - len(hata)}/{len(karolar)} acildi; (genislik, yukseklik, bant, tip) = {sorted(tip)}; acilmayan {hata[:5]}"
    dene("ACILIS_E1_288_karo", e1)

    # HDF4 (D0'da ertelenen test) ve HDF5
    def hdf4(ad, yol, aranan):
        def f():
            alt = [s[0] for s in gdal.Open(str(VERI / yol)).GetSubDatasets()]
            eks = [a for a in aranan if not any(a in s for s in alt)]
            return not eks, f"{len(alt)} alt veri seti; aranan {aranan}; eksik {eks}"
        dene(ad, f)
    hdf4("ACILIS_HDF4_E2", "dunya/E2_mcd12c1/MCD12C1.A2023001.061.2024251212901.hdf", ["Land_Cover_Type_1_Percent"])
    for r in [x for x in liste if x["set"] == "E5"]:
        hdf4(f"ACILIS_HDF4_{r['hedef'].rsplit('/', 1)[-1]}", r["hedef"], ["LST_Day_CMG", "LST_Night_CMG"])
    for r in [x for x in liste if x["set"] == "E6"]:
        hdf4(f"ACILIS_HDF4_{r['hedef'].rsplit('/', 1)[-1]}", r["hedef"], ["Albedo_WSA_shortwave"])
    e4_yapi = {}
    for r in [x for x in liste if x["set"] == "E4"]:
        def h5(r=r):
            adlar = []
            with h5py.File(VERI / r["hedef"], "r") as f:
                f.visititems(lambda n, o: adlar.append(n) if isinstance(o, h5py.Dataset) else None)
            e4_yapi[r["hedef"]] = adlar
            ok = any("Emissivity" in a for a in adlar) and any("NDVI" in a for a in adlar)
            return ok, f"{len(adlar)} veri seti: {adlar[:8]}"
        dene(f"ACILIS_HDF5_{r['hedef'].rsplit('/', 1)[-1]}", h5)

    # GeoTIFF'ler
    for h in ["ay/M1_lola/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif",
              "ay/M3_diviner_ghrm/dghrm_ra_sam_70s70n_tif.tif", "ay/M3_diviner_ghrm/dghrm_tbol_sam_70s70n_tif.tif",
              "ay/M7_pgda/AVGVISIB_65S_240M_201608.TIF", "ay/M7_pgda/AVGVISIB_65N_240M_201608.TIF",
              "ay/M7_pgda/LPSR_65S_240M_201608.TIF", "ay/M7_pgda/LPSR_65N_240M_201608.TIF",
              "mars/R1_mola/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif",
              "mars/R7_swim/SWIM4MIM_Ci_0_1.tif", "mars/R7_swim/SWIM4MIM_Ci_1_5.tif", "mars/R7_swim/SWIM4MIM_Ci_5.tif",
              "dunya/E10_soilgrids/clay/clay_0-5cm_mean_1000.tif", "dunya/E10_soilgrids/silt/silt_0-5cm_mean_1000.tif"]:
        rast(f"ACILIS_{h}", VERI / h)

    # zip içinden gelen rasterler
    def bul(z, desen):
        k = acilan.get(z)
        return sorted(k.rglob(desen)) if k else []
    for z, desen in [(ZIPLER[1], "UiO_PEX_PERPROB_5.0_20181128_2000_2016_NH.tif"),
                     (ZIPLER[2], "UiO_PEX_PERPROB_5.0_20181205_2000_2017_ANT.tif"),
                     (ZIPLER[3], "ai_v31_yr.tif")]:
        def f(z=z, desen=desen):
            b = [p for p in bul(z, desen) if "__MACOSX" not in p.parts]
            if len(b) != 1:
                return False, f"{desen}: {len(b)} adet bulundu"
            return True, (b[0].relative_to(VERI).as_posix(), ac(b[0]))
        dene(f"ACILIS_{desen}", f)

    # TES mineral ENVI (rapor R3: 1440 x 720 x 13, float32)
    def envi():
        d = gdal.Open(str(VERI / "mars/R3_tes_mineral/TES_mineral_maps_4_ppd.envi"))
        dt = gdal.GetDataTypeName(d.GetRasterBand(1).DataType)
        return (d.RasterXSize, d.RasterYSize, d.RasterCount, dt) == (1440, 720, 13, "Float32"), \
            f"{d.RasterXSize} x {d.RasterYSize} x {d.RasterCount}, {dt} (rapor: 1440 x 720 x 13 Float32)"
    dene("ACILIS_R3_ENVI", envi)

    # vektörler
    def glim():
        g = [p for p in bul(ZIPLER[0], "*.gdb") if p.is_dir()]
        if len(g) != 1:
            return False, f"{len(g)} .gdb klasoru"
        katman = [l[0] for l in pyogrio.list_layers(g[0])]
        bilgi = pyogrio.read_info(g[0], layer="GLiM_export")
        return "GLiM_export" in katman and "xx" in bilgi["fields"], \
            f"katmanlar {katman}; GLiM_export {bilgi['features']} kayit, sutun xx var: {'xx' in bilgi['fields']}, CRS {str(bilgi['crs'])[:60]}"
    dene("ACILIS_E3_GLiM", glim)

    def vek(z, desen, sutunlar, adet, essiz=None):
        def f():
            b = bul(z, desen)
            if len(b) != 1:
                return False, f"{desen}: {len(b)} adet"
            bilgi = pyogrio.read_info(b[0])
            ok = all(s in bilgi["fields"] for s in sutunlar) and bilgi["features"] == adet
            d = f"{b[0].relative_to(VERI).as_posix()}: {bilgi['features']} kayit (rapor {adet}), sutunlar {sutunlar} var: {all(s in bilgi['fields'] for s in sutunlar)}"
            if essiz:
                df = pyogrio.read_dataframe(b[0], columns=[essiz[0]], read_geometry=False)
                n = df[essiz[0]].nunique()
                ok = ok and n == essiz[1]
                d += f", essiz {essiz[0]} {n} (rapor {essiz[1]})"
            return ok, d
        return f
    dene("ACILIS_M2_GeoUnits", vek(ZIPLER[4], "GeoUnits.shp", ["FIRST_Unit", "AREA_GEO"], 12247))
    dene("ACILIS_R2_SIM3292", vek(ZIPLER[5], "SIM3292_Global_Geology.shp", ["Unit", "SphArea_km"], 1311, ("Unit", 44)))

    # ------------------------------------------------ raporun ek bütünlük testleri
    def m5():
        hb = (VERI / "ay/M5_lp_grs/lpgrs_high1_elem_abundance_2deg.tab").read_bytes()
        return len(hb) == 11306 * 880, f"{len(hb)} bayt = 11306 x 880 ({11306 * 880})"
    dene("EK_M5_11306x880", m5)

    def m6():
        n, bozuk, kotu = 0, 0, 0
        for s in (VERI / "ay/M6_lp_hidrojen/hydrogenhd.txt").read_text(encoding="ascii", errors="replace").splitlines():
            if not s.strip() or s.lstrip().startswith("#"):
                continue
            n += 1
            p = s.split(",")
            if len(p) != 5:
                kotu += 1
            if "*" in s:
                bozuk += 1
        return n == 259200 and kotu == 0 and bozuk == 1, \
            f"{n} veri satiri (rapor 259200), 5 sutun olmayan {kotu}, '*' iceren (bozuk hucre) {bozuk} (rapor 1)"
    dene("EK_M6_259200x5", m6)

    # ------------------------------------------------ kayıt
    with open(KAYIT / "D1_dosyalar.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["hedef", "set", "bayt", "rapor_bayt", "sha256", "durum", "not"])
        w.writeheader()
        w.writerows(satirlar)
    gecmeyen = [t["test"] for t in TESTLER if t["durum"] == "FAIL"]
    ozet = {"adim": "D1", "tarih": datetime.now().isoformat(timespec="seconds"),
            "sure_dk": round((time.time() - t0) / 60, 1),
            "ham_dosya": len(ham), "ham_bayt": sum(x["bayt"] for x in satirlar),
            "acik_bayt": sum(p.stat().st_size for k in acilan.values() for p in k.rglob("*") if p.is_file()),
            "eksik": eksik, "fazla": fazla, "e4_hdf5_yapisi_ornek": next(iter(e4_yapi.values()), []),
            "test_sayisi": len(TESTLER), "PASS": len(TESTLER) - len(gecmeyen), "FAIL": len(gecmeyen),
            "gecmeyenler": gecmeyen, "testler": TESTLER}
    (KAYIT / "D1.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(KAYIT / "13_kasim_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  D1 butunluk: {ozet['PASS']} PASS, {ozet['FAIL']} FAIL {gecmeyen}, "
                f"{ozet['sure_dk']} dk\n")
    print("=" * 60)
    print(f"D1: {ozet['PASS']}/{ozet['test_sayisi']} PASS | ham {ozet['ham_dosya']} dosya {ozet['ham_bayt'] / 1e9:.3f} GB | "
          f"acilan {ozet['acik_bayt'] / 1e9:.3f} GB | toplam {(ozet['ham_bayt'] + ozet['acik_bayt']) / 1e9:.3f} GB | {ozet['sure_dk']} dk")
    for g in gecmeyen:
        print("   FAIL:", g)
    print("Kayit: kayit/D1.json, kayit/D1_dosyalar.csv")
    return 1 if gecmeyen else 0


if __name__ == "__main__":
    sys.exit(main())
