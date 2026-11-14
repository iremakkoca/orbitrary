# Developed with assistance from Claude (Anthropic).
# d3_mars.py — Orbitrary v1.2, belge 17.3 D3 + 10.4: Mars setleri R1–R7 temiz\mars\<kod>_<ad>\ altına standart biçimde yazılır.
# Raster: fiziksel birim, float32 (GeoTIFF ya da .npy + .json), veri yok = NaN. Tablo: .npy. Vektör: GeoPackage. Her klasöre meta.json.
# TES TI (R4) kuzey üstte, boylam -180'den doğuya düzene çevrilir (albedo/DCI/TES ile aynı ızgara düzeni); dönüşüm testle doğrulanır.
# D3 testi (belge 17.3): rastgele 1000 piksel/satırda ham dosyadan yeniden hesaplanan değerle fark 0; NaN sayısı = veri-yok sayısı.
# Okuma kuralları d2_mars.py ile aynıdır (D2'de geçti). Ham veri (veri\) yalnız okunur.
import csv, json, math, re, shutil, time
from datetime import datetime
from pathlib import Path

import numpy as np

KOK = Path.home() / "orbitrary"
VERI, KAYIT, TEMIZ = KOK / "veri", KOK / "kayit", KOK / "temiz"
M = VERI / "mars"
D3CSV = KAYIT / "D3.csv"
TOHUM = 20261113
R_MARS = 3396190.0                     # m; SIM3292_README.txt

STATIK = {
    "R1": {"ad": "MGS MOLA DEM 463 m (128 ppd)", "doi": "10.1029/2000JE001364 (Smith ve ark. 2001)", "surum": "Edition 2003-03-21",
           "lisans": "CC0 (rapor Bölüm 4)", "birim": "m (areoid)"},
    "R2": {"ad": "Geologic Map of Mars SIM 3292", "doi": "10.3133/sim3292", "surum": "Tanaka ve ark. 2014, 1:20M",
           "lisans": "USGS yayını, kamu malı (rapor Bölüm 4)", "birim": "sınıf (Unit), km²"},
    "R3": {"ad": "TES mineral haritaları 4 ppd (Bandfield 2002)", "doi": "10.1029/2001JE001510 (makale)", "surum": "TES_mineral_maps_4_ppd",
           "lisans": "sayfada yok — 'açık' (rapor Bölüm 4)", "birim": "bolluk (oran)"},
    "R4": {"ad": "TES termal eylemsizlik 20 ppd (Putzig) + TES albedo 8 ppd", "doi": "Putzig ve ark. 2005, Icarus 173; Christensen ve ark. 2001",
           "surum": "ti_nmap2003.bin; global_albedo_8ppd", "lisans": "sayfada yok — 'açık' (rapor Bölüm 4)",
           "birim": "TI: J m⁻² K⁻¹ s⁻½; albedo: birimsiz"},
    "R5": {"ad": "TES Dust Cover Index 16 ppd", "doi": "10.1029/2001JE001580 (Ruff & Christensen 2002)", "surum": "dci_lo_ice_dust_16ppd_shifted",
           "lisans": "sayfada yok — 'açık' (rapor Bölüm 4)", "birim": "yayınım (1350–1400 cm⁻¹ ortalaması)"},
    "R6": {"ad": "Mars Odyssey GRS 5° x 5° yumuşatılmış", "doi": "ODY-M-GRS-5-ELEMENTS-V1.0 (PDS4'e taşınmış)", "surum": "V1.0",
           "lisans": "NASA PDS, kamuya açık (rapor Bölüm 4)", "birim": "ağırlık % (H2O, Fe, Si, Cl), ppm (K, Th) — PDS3 etiketleri"},
    "R7": {"ad": "SWIM4MIM Ci (0–1 m, 1–5 m, > 5 m)", "doi": "açık (rapor R7 künyesi)", "surum": "SWIM4MIM",
           "lisans": "sayfada yok — 'açık' (rapor Bölüm 4)", "birim": "tutarlılık indeksi -1…+1 (olasılık değil)"},
}

SATIRLAR = []

def csv_oku(yol):
    with open(yol, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sinav(set_, test, olculen, ok, d3):
    durum = "PASS" if ok else "FAIL"
    d3.append({"test": test, "olculen": olculen, "durum": durum})
    SATIRLAR.append({"govde": "mars", "set": set_, "test": test, "olculen": olculen, "durum": durum,
                     "zaman": datetime.now().isoformat(timespec="seconds")})
    print(f"[{durum}] {set_} {test}: {olculen}", flush=True)


def ham_klasor(kod):
    k = [p for p in (VERI / "mars").glob(f"{kod}_*") if p.is_dir()]
    assert len(k) == 1, f"{kod}: ham klasör {k}"
    return k[0]


def klasor(kod, ad):
    p = TEMIZ / "mars" / f"{kod}_{ad}"
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True)
    return p


def meta_yaz(p, kod, ek, d3, D1, IND, D2):
    ind = [r for r in IND if r["set"] == kod and r["durum"] != "FAIL"]
    adres = sorted({r["adres"] for r in ind if r["adres"]})
    m = {"set": kod, **STATIK[kod],
         "kaynak_adresleri": adres if len(adres) <= 8 else adres[:5] + [f"... toplam {len(adres)} adres (kayit/indirme.csv)"],
         "indirme_tarihi": [min(r["zaman"] for r in ind), max(r["zaman"] for r in ind)] if ind else None,
         "ham_sha256": {r["hedef"]: r["sha256"] for r in D1 if r["set"] == kod},
         "gercek_yer_testleri_D2": [{k: r[k] for k in ("test", "nokta", "beklenen", "tolerans_kurali", "beklenen_kaynagi", "olculen", "durum")}
                                    for r in D2 if r["govde"] == "mars" and r["set"] == kod],
         "D3_testleri": d3, **ek, "uretim_zamani": datetime.now().isoformat(timespec="seconds"), "uretim_kodu": "kod/d3_mars.py"}
    (p / "meta.json").write_text(json.dumps(m, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def esit(bek, tem):
    return (bek == tem) | (np.isnan(bek) & np.isnan(tem))


def npy_yaz(p, ad, v, bilgi):
    np.save(p / f"{ad}.npy", v)
    (p / f"{ad}.json").write_text(json.dumps({**bilgi, "sekil": list(v.shape), "dtype": str(v.dtype)},
                                             ensure_ascii=False, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------- GeoTIFF -> float32 GeoTIFF (NaN)
def _yok(a, v, nd, sabit_yok, ek_yok):
    y = np.zeros(a.shape, bool)
    if nd is not None:
        y |= np.isnan(a) if (isinstance(nd, float) and math.isnan(nd)) else (a == nd)
    for s in sabit_yok:
        y |= a == s
    if a.dtype.kind == "f":
        y |= ~np.isfinite(a)
    if ek_yok is not None:
        with np.errstate(invalid="ignore"):
            y |= ek_yok(v)
    return y


def tif_cevir(kaynak, hedef, olcek=1.0, ofset=0.0, sabit_yok=(), ek_yok=None, satir=256):
    import rasterio
    from rasterio.windows import Window
    with rasterio.open(kaynak) as s:
        assert s.count == 1, f"{kaynak.name}: {s.count} bant"
        dosya_ol = (s.scales[0], s.offsets[0])
        # rasterio ham DN döndürür; ölçek yalnız burada, bir kez uygulanır. Dosyada ölçek varsa etiketteki değerle aynı olmalı.
        assert dosya_ol in ((1.0, 0.0), (olcek, ofset)), f"{kaynak.name}: dosyada ölçek/ofset {dosya_ol}, uygulanacak {(olcek, ofset)}"
        nd = s.nodata
        prof = s.profile.copy()
        prof.update(driver="GTiff", dtype="float32", nodata=np.nan, count=1, compress="deflate", predictor=3,
                    tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES")
        n_yok, vmin, vmax = 0, np.inf, -np.inf
        with rasterio.open(hedef, "w", **prof) as t:
            for r0 in range(0, s.height, satir):
                w = Window(0, r0, s.width, min(satir, s.height - r0))
                a = s.read(1, window=w)
                v = (a.astype(np.float64) * olcek + ofset).astype(np.float32)
                yok = _yok(a, v, nd, sabit_yok, ek_yok)
                v[yok] = np.nan
                n_yok += int(yok.sum())
                if (~yok).any():
                    vmin, vmax = min(vmin, float(np.nanmin(v))), max(vmax, float(np.nanmax(v)))
                t.write(v, 1, window=w)
        return {"ham_dtype": s.dtypes[0], "ham_nodata": nd, "boyut": [s.width, s.height], "crs": str(s.crs),
                "transform": list(s.transform)[:6], "piksel": list(s.res), "olcek": olcek, "ofset": ofset,
                "sabit_veri_yok": list(sabit_yok), "veri_yok_sayisi": n_yok, "min": vmin, "max": vmax,
                "dosyadaki_gdal_olcek_ofset": list(dosya_ol)}


def tif_dogrula(kaynak, hedef, bilgi, rng, n, sabit_yok=(), ek_yok=None, ozel_nan=()):
    import rasterio
    from rasterio.windows import Window
    with rasterio.open(kaynak) as s, rasterio.open(hedef) as t:
        assert (s.width, s.height, s.transform) == (t.width, t.height, t.transform), f"{hedef.name}: geometri farklı"
        assert t.dtypes[0] == "float32"
        rr = list(rng.integers(0, s.height, n)) + [r for r, c in ozel_nan]
        cc = list(rng.integers(0, s.width, n)) + [c for r, c in ozel_nan]
        ham = np.array([s.read(1, window=Window(int(c), int(r), 1, 1))[0, 0] for r, c in zip(rr, cc)])
        tem = np.array([t.read(1, window=Window(int(c), int(r), 1, 1))[0, 0] for r, c in zip(rr, cc)], dtype=np.float32)
        bek = (ham.astype(np.float64) * bilgi["olcek"] + bilgi["ofset"]).astype(np.float32)
        bek[_yok(ham, bek, s.nodata, sabit_yok, ek_yok)] = np.nan
        if ozel_nan:
            bek[-len(ozel_nan):] = np.nan
        n_fark = int((~esit(bek, tem)).sum())
        n_nan = 0
        for r0 in range(0, t.height, 512):
            n_nan += int(np.isnan(t.read(1, window=Window(0, r0, t.width, min(512, t.height - r0)))).sum())
    return n_fark, n_nan


def main(setler=None):
    t0 = time.time()
    D1 = csv_oku(KAYIT / "D1_dosyalar.csv")
    IND = csv_oku(KAYIT / "indirme.csv")
    D2 = csv_oku(KAYIT / "D2.csv")
    secili = set(setler) if setler else set(STATIK)
    rng = np.random.default_rng(TOHUM)
    calisan = []

    def bolum(kod, f):
        if kod not in secili:
            return
        calisan.append(kod)
        t1 = time.time()
        print(f"\n--- {kod} başladı {datetime.now():%H:%M:%S}", flush=True)
        try:
            f()
        except Exception as e:
            sinav(kod, "bolum calisamadi", f"{type(e).__name__}: {e}", False, [])
        print(f"--- {kod} bitti, {round((time.time() - t1) / 60, 1)} dk", flush=True)

    # ------------------------------------------------ R1 MOLA: int16 m -> float32 GeoTIFF (konum kuralı belge 10.3)
    def r1():
        h = ham_klasor("R1")
        p = klasor("R1", "mola")
        k = h / "Mars_MGS_MOLA_DEM_mosaic_global_463m.tif"
        d3 = []
        b = tif_cevir(k, p / "mola_m.tif", 1.0, 0.0)
        f_, n_nan = tif_dogrula(k, p / "mola_m.tif", b, rng, 1000)
        sinav("R1", "rastgele piksel fark 0", f"1000 piksel, {f_} farkli", f_ == 0, d3)
        sinav("R1", "NaN sayisi = veri-yok sayisi", f"NaN {n_nan}, veri-yok {b['veri_yok_sayisi']}", n_nan == b["veri_yok_sayisi"], d3)
        sinav("R1", "uc degerler D2 ile ayni", f"min {b['min']}, max {b['max']} (D2: -8201 / 21241)", b["min"] == -8201 and b["max"] == 21241, d3)
        meta_yaz(p, "R1", {"crs": b["crs"], "cozunurluk": "128 ppd (463 m)", "olcek": 1.0, "ofset": 0.0,
                           "konum_kurali": "transform kullanılmaz: satır = ⌊(90 − φ)·128⌋, sütun = ⌊(λ + 180)·128⌋ (belge 10.3; D2 Jezero ile doğrulandı)",
                           "veri_yok_kurali": "dosya nodata -> NaN", "okuma": b, "dosyalar": "mola_m.tif"}, d3, D1, IND, D2)

    bolum("R1", r1)

    # ------------------------------------------------ R2 SIM 3292 -> GeoPackage (birim, alan_km2)
    def r2():
        import pyogrio, geopandas as gpd
        p = klasor("R2", "sim3292")
        shp = M / "R2_sim3292/acik/SIM3292_MarsGlobalGeologicGIS_20M/SIM3292_Shapefiles/SIM3292_Global_Geology.shp"
        df = pyogrio.read_dataframe(shp, columns=["Unit", "SphArea_km"])
        oran = float(df["SphArea_km"].sum()) / (4 * math.pi * (R_MARS / 1000) ** 2)
        assert len(df) == 1311 and df["Unit"].nunique() == 44 and abs(oran - 1) <= 1e-4, (len(df), df["Unit"].nunique(), oran)
        out = gpd.GeoDataFrame({"birim": df["Unit"].astype("string"), "alan_km2": df["SphArea_km"].astype(float)},
                               geometry=df.geometry, crs=df.crs)
        gp = p / "sim3292.gpkg"
        pyogrio.write_dataframe(out, gp, layer="sim3292", driver="GPKG")
        geri = pyogrio.read_dataframe(gp, layer="sim3292")
        i = rng.integers(0, len(df), 1000)
        b_ok = bool((geri["birim"].astype("string").iloc[i].fillna("<bos>").to_numpy()
                     == df["Unit"].astype("string").iloc[i].fillna("<bos>").to_numpy()).all())
        a_ok = bool((geri["alan_km2"].to_numpy()[i] == df["SphArea_km"].astype(float).to_numpy()[i]).all())
        d3 = []
        sinav("R2", "rastgele 1000 poligon: birim ve alan_km2 ham ile ayni",
              f"{len(geri)} kayit, {geri['birim'].nunique()} birim; birim {b_ok}; alan {a_ok}; SphArea_km toplami / 4πR² = {oran:.6f}",
              len(geri) == len(df) and b_ok and a_ok, d3)
        meta_yaz(p, "R2", {"crs": str(df.crs), "olcek": None, "ofset": None, "veri_yok_kurali": "vektör",
                           "alan_km2": "SphArea_km (README: geodesic area, km²); toplam / 4πR² = %.6f" % oran,
                           "kayit_sayisi": len(df), "birim_sayisi": int(df["Unit"].nunique()),
                           "dosyalar": "sim3292.gpkg (birim, alan_km2)"}, d3, D1, IND, D2)

    bolum("R2", r2)

    # ------------------------------------------------ R3 TES mineral: 13 bant -> 13 .npy (-1 = yok)
    def r3():
        p = klasor("R3", "tes_mineral")
        hdr = (M / "R3_tes_mineral/TES_mineral_maps_4_ppd.envi.hdr").read_text(encoding="ascii", errors="replace")
        hh = {k: int(re.search(r"(?im)^\s*" + k + r"\s*=\s*(\d+)", hdr).group(1)) for k in ("samples", "lines", "bands", "data type", "byte order")}
        assert hh == {"samples": 1440, "lines": 720, "bands": 13, "data type": 4, "byte order": 1}, hh
        kaynak = M / "R3_tes_mineral/TES_mineral_maps_4_ppd.envi"
        A = np.fromfile(kaynak, dtype=">f4").reshape(13, 720, 1440)
        adlar = ["quartz", "k_feldspar", "plagioclase", "amphibole", "low_ca_pyroxene", "high_ca_pyroxene", "olivine",
                 "hematite", "sulfates", "carbonates", "sheet_silicates_high_si_glass", "surface_dust", "rms_error"]
        GT = [-180.0, 0.25, 0.0, 90.0, 0.0, -0.25]
        d3, n_fark, nan_hata = [], 0, []
        for j, ad in enumerate(adlar):
            ham = A[j]
            v = ham.astype(np.float32)
            yok = (ham == -1) | ~np.isfinite(ham)
            v[yok] = np.nan
            dosya = f"b{j + 1:02d}_{ad}"
            npy_yaz(p, dosya, v, {"kaynak": "mars/R3_tes_mineral/TES_mineral_maps_4_ppd.envi", "bant": j + 1, "bilesen": ad,
                                  "geotransform": GT, "veri_yok": "-1 -> NaN (belge 10.3)", "dtype_ham": ">f4"})
            # bağımsız okuma: aynı dosyadan yalnız bu bandın baytları offset ile okunur
            bag = np.fromfile(kaynak, dtype=">f4", count=720 * 1440, offset=j * 720 * 1440 * 4).reshape(720, 1440)
            rr, cc = rng.integers(0, 720, 1000), rng.integers(0, 1440, 1000)
            h = bag[rr, cc].astype(np.float32)
            h[(bag[rr, cc] == -1) | ~np.isfinite(bag[rr, cc])] = np.nan
            t = np.load(p / f"{dosya}.npy")
            n_fark += int((~esit(h, t[rr, cc])).sum())
            if int(np.isnan(t).sum()) != int(((bag == -1) | ~np.isfinite(bag)).sum()):
                nan_hata.append(dosya)
        sinav("R3", "rastgele piksel fark 0", f"13 bant x 1000 piksel, {n_fark} farkli", n_fark == 0, d3)
        sinav("R3", "NaN sayisi = veri-yok (-1) sayisi", f"tutmayan bant {nan_hata}", not nan_hata, d3)
        meta_yaz(p, "R3", {"crs": "Mars 'ocentric, simple cylindrical", "geotransform": GT,
                           "geometri_kaynagi": "dosyalarda yok; ASU Mars Global Data Sets (TES Low-Calcium Pyroxene): "
                                               "Simple cylindrical, -180E to 180E, 90N to -90N; D2 hematit testiyle doğrulandı",
                           "bant_sirasi_kaynagi": "ASU ürün sayfası (rapor R3) = belge D11", "olcek": 1.0, "ofset": 0.0,
                           "bayt_sirasi": ".envi >f4 (hdr byte order 1); D2'de .isis <f4 ile birebir aynı",
                           "veri_yok_kurali": "-1 ve sonlu olmayan -> NaN", "dosyalar": "b01_quartz.npy … b13_rms_error.npy"}, d3, D1, IND, D2)

    bolum("R3", r3)

    # ------------------------------------------------ R4 TI (yeniden düzenlenir) + albedo
    def r4():
        p = klasor("R4", "tes_ti_albedo")
        d3 = []
        kaynak = M / "R4_tes_ti_albedo/ti_nmap2003.bin"
        bas = kaynak.open("rb").read(7200).decode("ascii", errors="replace")
        assert "west" in bas.lower() and "-90" in bas
        assert kaynak.stat().st_size == 7200 + 7200 * 3600 * 2
        ham = np.fromfile(kaynak, dtype=">i2", offset=7200).reshape(3600, 7200)      # ilk satır güney, boylam batıya 0-360
        yeni = np.roll(ham[::-1, ::-1], -3600, axis=1)                               # -> kuzey üstte, boylam -180'den doğuya
        v = yeni.astype(np.float32)
        v[yeni == 0] = np.nan                                                         # 0 = yok (başlık)
        GT_TI = [-180.0, 0.05, 0.0, 90.0, 0.0, -0.05]
        npy_yaz(p, "ti", v, {"kaynak": "mars/R4_tes_ti_albedo/ti_nmap2003.bin", "geotransform": GT_TI, "birim": "J m-2 K-1 s-1/2",
                             "veri_yok": "ham 0 -> NaN", "duzen": "ham: ilk satır -90, boylam 0–360 batı; temiz: ilk satır +90, boylam -180'den doğuya"})
        # bağımsız test: rastgele ham piksel (i, j) -> enlem/boylam -> temiz satır/sütun formülle hesaplanır
        i, j = rng.integers(0, 3600, 1000), rng.integers(0, 7200, 1000)
        enlem = -90 + (i + 0.5) / 20
        boylam_d = ((-(j + 0.5) / 20) + 180) % 360 - 180
        r2_, c2_ = np.floor((90 - enlem) * 20).astype(int), np.floor((boylam_d + 180) * 20).astype(int)
        hv = ham[i, j].astype(np.float32)
        hv[ham[i, j] == 0] = np.nan
        t = np.load(p / "ti.npy")
        n_fark = int((~esit(hv, t[r2_, c2_])).sum())
        n_nan = int(np.isnan(t).sum())
        sinav("R4", "TI rastgele piksel fark 0 (yeniden düzenleme dahil)", f"1000 piksel, {n_fark} farkli", n_fark == 0, d3)
        sinav("R4", "TI NaN sayisi = veri-yok (0) sayisi", f"NaN {n_nan}, 0 {int((ham == 0).sum())}", n_nan == int((ham == 0).sum()), d3)
        # albedo: etiketten (PC_REAL = <f4, kuzey üstte, -180'den doğuya); veri-yok tanımı yok -> sonlu olmayan ve <= 0 NaN (D2 ile aynı proje kararı)
        lbl = (M / "R4_tes_ti_albedo/global_albedo_8ppd.lbl").read_text(encoding="ascii", errors="replace")
        for anahtar, bek in (("LINES", "1440"), ("LINE_SAMPLES", "2880"), ("SAMPLE_TYPE", "PC_REAL"), ("SAMPLE_BITS", "32"),
                             ("MAXIMUM_LATITUDE", "90.0"), ("WESTERNMOST_LONGITUDE", "-180.0")):
            assert re.search(r"(?m)^\s*" + anahtar + r"\s*=\s*\"?" + re.escape(bek), lbl), anahtar
        akaynak = M / "R4_tes_ti_albedo/global_albedo_8ppd.img"
        a = np.fromfile(akaynak, dtype="<f4").reshape(1440, 2880)
        va = a.astype(np.float32)
        ayok = ~np.isfinite(a) | (a <= 0)
        va[ayok] = np.nan
        npy_yaz(p, "albedo", va, {"kaynak": "mars/R4_tes_ti_albedo/global_albedo_8ppd.img", "geotransform": [-180.0, 0.125, 0.0, 90.0, 0.0, -0.125],
                                  "birim": "bolometrik albedo", "veri_yok": "sonlu olmayan ve <= 0 -> NaN (etikette veri-yok yok; proje kararı, D2 ile aynı)"})
        bag = np.fromfile(akaynak, dtype="<f4").reshape(1440, 2880)
        rr, cc = rng.integers(0, 1440, 1000), rng.integers(0, 2880, 1000)
        hb = bag[rr, cc].astype(np.float32)
        hb[~np.isfinite(bag[rr, cc]) | (bag[rr, cc] <= 0)] = np.nan
        ta = np.load(p / "albedo.npy")
        sinav("R4", "albedo rastgele piksel fark 0", f"1000 piksel, {int((~esit(hb, ta[rr, cc])).sum())} farkli", bool(esit(hb, ta[rr, cc]).all()), d3)
        sinav("R4", "albedo NaN sayisi = veri-yok sayisi", f"NaN {int(np.isnan(ta).sum())}, beklenen {int(ayok.sum())}",
              int(np.isnan(ta).sum()) == int(ayok.sum()), d3)
        meta_yaz(p, "R4", {"crs": "Mars 'ocentric, simple cylindrical", "geotransform": {"ti": GT_TI, "albedo": [-180.0, 0.125, 0.0, 90.0, 0.0, -0.125]},
                           "olcek": 1.0, "ofset": 0.0, "ti_okuma": "ham >i2, 7200 bayt başlık, ilk satır güney, boylam 0–360 batı (başlık + rapor R4); "
                           "temizde kuzey üstte, -180'den doğuya", "ti_baslik": bas.strip()[:600],
                           "veri_yok_kurali": "TI 0 -> NaN; albedo sonlu olmayan ve <= 0 -> NaN",
                           "eksik": "interpolasyon maskesi nmsk2003.bin indirilemedi (belge 13.3 açık kontrol)",
                           "dosyalar": "ti.npy (3600 x 7200), albedo.npy (1440 x 2880)"}, d3, D1, IND, D2)

    bolum("R4", r4)

    # ------------------------------------------------ R5 DCI: 0,85 = yok
    def r5():
        p = klasor("R5", "tes_dci")
        kaynak = M / "R5_tes_dci/dci_lo_ice_dust_16ppd_shifted.pds"
        etk = kaynak.open("rb").read(1024).decode("ascii", errors="replace")
        assert re.search(r"CORE_ITEMS\s*=\s*\(\s*1\s*,\s*5760\s*,\s*2880\s*\)", etk) and "PC_REAL" in etk
        assert re.search(r"\^QUBE\s*=\s*3", etk) and re.search(r"RECORD_BYTES\s*=\s*512", etk)
        d = np.fromfile(kaynak, dtype="<f4", offset=1024).reshape(2880, 5760)
        v = d.astype(np.float32)
        yok = (d == np.float32(0.85)) | ~np.isfinite(d)
        v[yok] = np.nan
        GT = [-180.0, 1 / 16, 0.0, 90.0, 0.0, -1 / 16]
        npy_yaz(p, "dci", v, {"kaynak": "mars/R5_tes_dci/dci_lo_ice_dust_16ppd_shifted.pds", "geotransform": GT,
                              "veri_yok": "0,85 -> NaN (belge 10.3, veriden)"})
        d3 = []
        bag = np.memmap(kaynak, dtype="<f4", mode="r", offset=1024, shape=(2880, 5760))
        rr, cc = rng.integers(0, 2880, 1000), rng.integers(0, 5760, 1000)
        h = np.asarray(bag[rr, cc]).astype(np.float32)
        h[(h == np.float32(0.85)) | ~np.isfinite(h)] = np.nan
        t = np.load(p / "dci.npy")
        sinav("R5", "rastgele piksel fark 0", f"1000 piksel, {int((~esit(h, t[rr, cc])).sum())} farkli", bool(esit(h, t[rr, cc]).all()), d3)
        sinav("R5", "NaN sayisi = veri-yok (0,85) sayisi", f"NaN {int(np.isnan(t).sum())}, 0,85 {int(yok.sum())}", int(np.isnan(t).sum()) == int(yok.sum()), d3)
        meta_yaz(p, "R5", {"crs": "Mars 'ocentric, simple cylindrical", "geotransform": GT, "olcek": 1.0, "ofset": 0.0,
                           "okuma": "PDS3 QUBE: CORE_ITEMS (1,5760,2880), PC_REAL (<f4), veri 1025. bayttan (^QUBE = 3 x 512)",
                           "geometri_kaynagi": "etikette yok; rapor R5 (ikincil kayıt): -180 -> 180 doğu, 90 -> -90; D2 DCI-albedo korelasyonu -0,84",
                           "veri_yok_kurali": "0,85 -> NaN", "dosyalar": "dci.npy (2880 x 5760)"}, d3, D1, IND, D2)

    bolum("R5", r5)

    # ------------------------------------------------ R6 Odyssey GRS: 6 element tablosu (PDS4 alan konumları)
    def r6():
        p = klasor("R6", "odyssey_grs")
        d3, n_fark, nan_hata, bilgi = [], 0, [], {}
        for el in ("h2o", "fe", "si", "k", "th", "cl"):
            xml = (M / f"R6_odyssey_grs/pds4_etiket/{el}_sr_5x5.xml").read_text(encoding="utf-8", errors="replace")
            rl = int(re.search(r"<record_length[^>]*>(\d+)<", xml).group(1))
            nrec = int(re.search(r"<records>(\d+)<", xml).group(1))
            alan = [(re.search(r"<name>(.*?)</name>", b).group(1).strip(),
                     int(re.search(r"<field_location[^>]*>(\d+)<", b).group(1)),
                     int(re.search(r"<field_length[^>]*>(\d+)<", b).group(1)))
                    for b in re.findall(r"<Field_Character>(.*?)</Field_Character>", xml, re.S)]
            ham = (M / f"R6_odyssey_grs/{el}_sr_5x5.tab").read_bytes()
            assert len(ham) == rl * nrec, (el, len(ham), rl, nrec)
            sat = [ham[k * rl:(k + 1) * rl] for k in range(nrec)]
            T = np.array([[float(s[l - 1:l - 1 + n]) for (_, l, n) in alan] for s in sat])
            v = T.copy()
            v[np.isclose(T, 9999.999)] = np.nan
            v[:, :2] = T[:, :2]                                                     # enlem/boylam sütunlarına dokunulmaz
            lbl = (M / f"R6_odyssey_grs/{el}_sr_5x5.lbl").read_text(encoding="ascii", errors="replace")
            birimler = re.findall(r"UNIT\s*=\s*\"([^\"]+)\"", lbl)
            npy_yaz(p, f"{el}_tablo", v, {"kaynak": f"mars/R6_odyssey_grs/{el}_sr_5x5.tab", "sutunlar": [a[0] for a in alan],
                                          "birimler_pds3": birimler, "veri_yok": "9999.999 -> NaN",
                                          "okuma": f"PDS4 etiketi: record_length {rl}, {nrec} kayıt, alan konumları"})
            t = np.load(p / f"{el}_tablo.npy")
            i = rng.integers(0, nrec, 200)
            for k in i:
                s = ham[k * rl:(k + 1) * rl].decode("ascii")
                h = np.array([float(x) for x in s.split()])                          # bağımsız: boşlukla bölme
                h[2:][np.isclose(h[2:], 9999.999)] = np.nan
                n_fark += int((~esit(h, t[k])).sum()) if h.shape == t[k].shape else 1
            if int(np.isnan(t).sum()) != int(np.isclose(T[:, 2:], 9999.999).sum()):
                nan_hata.append(el)
            bilgi[el] = {"kayit": nrec, "record_length": rl, "sutunlar": [a[0] for a in alan], "birimler_pds3": birimler,
                         "nan": int(np.isnan(t).sum())}
        sinav("R6", "rastgele satir fark 0 (6 element x 200 satir, boslukla bolerek bagimsiz okuma)", f"{n_fark} farkli", n_fark == 0, d3)
        sinav("R6", "NaN sayisi = 9999.999 sayisi", f"tutmayan {nan_hata}", not nan_hata, d3)
        meta_yaz(p, "R6", {"crs": "Mars, 5° x 5° hücre merkezleri (derece, boylam doğuya)", "olcek": None, "ofset": None,
                           "okuma": "PDS4 etiketleri (pds4_etiket/*.xml): 72/66 bayt kayıt; PDS3 .lbl RECORD_BYTES (71/65) eski",
                           "veri_yok_kurali": "9999.999 -> NaN (belge 10.3); H2O yalnız 57,5°G–57,5°K (D2)", "puan": "puana girmez (çapraz kontrol)",
                           "elementler": bilgi, "dosyalar": "<element>_tablo.npy (h2o, fe, si, k, th, cl)"}, d3, D1, IND, D2)

    bolum("R6", r6)

    # ------------------------------------------------ R7 SWIM: 3 GeoTIFF, -30 = yok
    def r7():
        p = klasor("R7", "swim")
        d3, okuma = [], {}
        for ad in ("SWIM4MIM_Ci_0_1", "SWIM4MIM_Ci_1_5", "SWIM4MIM_Ci_5"):
            k = M / "R7_swim" / f"{ad}.tif"
            b = tif_cevir(k, p / f"{ad.lower()}.tif", 1.0, 0.0, sabit_yok=(-30,))
            f_, n_nan = tif_dogrula(k, p / f"{ad.lower()}.tif", b, rng, 1000, sabit_yok=(-30,))
            okuma[ad] = b
            sinav("R7", f"{ad} rastgele piksel fark 0", f"1000 piksel, {f_} farkli", f_ == 0, d3)
            sinav("R7", f"{ad} NaN sayisi = veri-yok sayisi", f"NaN {n_nan}, veri-yok {b['veri_yok_sayisi']}", n_nan == b["veri_yok_sayisi"], d3)
            sinav("R7", f"{ad} deger araligi [-1, 1]", f"min {b['min']}, max {b['max']}", b["min"] >= -1 and b["max"] <= 1, d3)
        meta_yaz(p, "R7", {"crs": okuma["SWIM4MIM_Ci_0_1"]["crs"], "cozunurluk": "20 ppd, 60°G–60°K", "olcek": 1.0, "ofset": 0.0,
                           "veri_yok_kurali": "-30 (GDAL_NODATA) -> NaN", "puan_katmani": "Ci 0–1 m (belge 10.3); 1–5 m ve > 5 m bilgi için",
                           "okuma": okuma, "dosyalar": "swim4mim_ci_0_1.tif, swim4mim_ci_1_5.tif, swim4mim_ci_5.tif"}, d3, D1, IND, D2)

    bolum("R7", r7)

    # ------------------------------------------------ kayıt
    eski = []
    if D3CSV.exists():
        eski = [r for r in csv_oku(D3CSV) if not (r["govde"] == "mars" and r["set"] in calisan)]
    with open(D3CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["govde", "set", "test", "olculen", "durum", "zaman"])
        w.writeheader()
        w.writerows(eski + SATIRLAR)
    say = {}
    for s in SATIRLAR:
        say[s["durum"]] = say.get(s["durum"], 0) + 1
    boyut = sum(f.stat().st_size for f in (TEMIZ / "mars").rglob("*") if f.is_file()) / 1e9
    with open(KAYIT / "13_kasim_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  D3 mars {calisan}: {say}, {round((time.time() - t0) / 60, 1)} dk, temiz/mars {boyut:.2f} GB\n")
    print("=" * 60)
    print(f"D3 Mars {calisan}: {say} | {round((time.time() - t0) / 60, 1)} dk | temiz\\mars {boyut:.2f} GB | kayit/D3.csv")
    return say
