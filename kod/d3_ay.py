# Developed with assistance from Claude (Anthropic).
# d3_ay.py — Orbitrary v1.2, belge 17.3 D3 + 10.4: Ay setleri M1–M7 temiz\ay\<kod>_<ad>\ altına standart biçimde yazılır.
# Raster: fiziksel birim, float32 GeoTIFF, veri yok = NaN. Tablo: sütun başına .npy (+ aynı adlı .json). Vektör: GeoPackage.
# Bayraklar (sansürlü, belgelenmemiş kod) ayrı uint8 dizide; NaN'a çevrilmez (belge 10.4). Her klasöre meta.json.
# D3 testi (belge 17.3): rastgele 1000 piksel/satırda ham dosyadan yeniden hesaplanan değerle fark 0; NaN sayısı = veri-yok sayısı.
# Okuma kuralları d2_ay.py ile aynıdır (D2'de geçti). Ham veri (veri\) yalnız okunur.
import csv, json, math, re, shutil, time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path.home() / "orbitrary"
VERI, KAYIT, TEMIZ = KOK / "veri", KOK / "kayit", KOK / "temiz"
D3CSV = KAYIT / "D3.csv"
TOHUM = 20261113
R_AY = 1737400.0                       # m, belge 4.1

STATIK = {
    "M1": {"ad": "LOLA Global LDEM 118 m (256 ppd)", "doi": "açık (rapor M1 künyesi)", "surum": "Mar2014",
           "lisans": "public domain; 'Please cite authors' (rapor Bölüm 4)", "birim": "m"},
    "M2": {"ad": "Unified Geologic Map of the Moon 1:5M", "doi": "açık (rapor M2 künyesi)", "surum": "2020",
           "lisans": "CC0, but please cite authors (rapor Bölüm 4)", "birim": "sınıf (FIRST_Unit), km²"},
    "M3": {"ad": "Diviner GHRM ra_sam + tbol_sam", "doi": "10.17189/wj0s-w188", "surum": "lro_diviner_derived1 v5.0",
           "lisans": "NASA PDS, kamuya açık (rapor Bölüm 4)", "birim": "ra: kaya bolluğu (birimsiz); tbol: K"},
    "M4": {"ad": "Diviner PRP (kuzey/güney) + GCP", "doi": "10.17189/wj0s-w188", "surum": "PRP LRO-L-DLRE-5-PRP-V2.0; GCP LRO-L-DLRE-5-GCP-V1.0",
           "lisans": "NASA PDS, kamuya açık (rapor Bölüm 4)", "birim": "K; m (ice_depth); derece"},
    "M5": {"ad": "Lunar Prospector GRS element bollukları 2°", "doi": "açık (rapor M5 künyesi)", "surum": "lpgrs_high1_elem_abundance_2deg",
           "lisans": "NASA PDS, kamuya açık (rapor Bölüm 4)", "birim": "etiketteki sütun birimleri"},
    "M6": {"ad": "Lunar Prospector hidrojen 0,5° (hydrogenhd)", "doi": "açık (rapor M6 künyesi)", "surum": "PDS Geosciences reduced special products",
           "lisans": "NASA PDS, kamuya açık (rapor Bölüm 4)", "birim": "ppm H"},
    "M7": {"ad": "PGDA AVGVISIB + LPSR 65° kutup 240 m", "doi": "açık (rapor M7 künyesi)", "surum": "201608",
           "lisans": "NASA, kamuya açık (rapor Bölüm 4)", "birim": "oran (0–1)"},
}

SATIRLAR = []


def csv_oku(yol):
    with open(yol, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sinav(set_, test, olculen, ok, d3):
    durum = "PASS" if ok else "FAIL"
    d3.append({"test": test, "olculen": olculen, "durum": durum})
    SATIRLAR.append({"govde": "ay", "set": set_, "test": test, "olculen": olculen, "durum": durum,
                     "zaman": datetime.now().isoformat(timespec="seconds")})
    print(f"[{durum}] {set_} {test}: {olculen}", flush=True)


def ham_klasor(kod):
    k = [p for p in (VERI / "ay").glob(f"{kod}_*") if p.is_dir()]
    assert len(k) == 1, f"{kod}: ham klasör {k}"
    return k[0]


def klasor(kod, ad):
    p = TEMIZ / "ay" / f"{kod}_{ad}"
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
                                    for r in D2 if r["govde"] == "ay" and (r["set"] == kod or kod in r["set"].split("/"))],
         "D3_testleri": d3, **ek, "uretim_zamani": datetime.now().isoformat(timespec="seconds"), "uretim_kodu": "kod/d3_ay.py"}
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


def lbl_sutunlar(lbl):
    t = lbl.read_text(encoding="ascii", errors="replace")
    adlar = []
    for blok in re.findall(r"OBJECT\s*=\s*COLUMN(.*?)END_OBJECT\s*=\s*COLUMN", t, re.S):
        m = re.search(r"\bNAME\s*=\s*\"?([A-Za-z0-9_]+)\"?", blok)
        if m:
            adlar.append(m.group(1).lower())
    return adlar


def oku_tablo(tab, adlar):
    ilk = tab.open(encoding="ascii", errors="replace").readline()
    baslik = any(c.isalpha() for c in ilk.replace("e", "").replace("E", ""))
    df = pd.read_csv(tab, header=0 if baslik else None, names=None if baslik else adlar, skipinitialspace=True)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def main(setler=None):
    t0 = time.time()
    D1 = csv_oku(KAYIT / "D1_dosyalar.csv")
    IND = csv_oku(KAYIT / "indirme.csv")
    D2 = csv_oku(KAYIT / "D2.csv")
    D2OK = json.loads((KAYIT / "D2_okuma_ay.json").read_text(encoding="utf-8"))
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

    # ------------------------------------------------ M1 LOLA: int16 x 0,5 m -> float32 GeoTIFF
    def m1():
        h = ham_klasor("M1")
        p = klasor("M1", "lola")
        k = h / "Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif"
        lbl = (h / "Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.lbl").read_text(encoding="ascii", errors="replace")
        carpan = float(re.search(r"Multiplier\s*=\s*([-\d.Ee+]+)", lbl).group(1))
        taban = float(re.search(r"Base\s*=\s*([-\d.Ee+]+)", lbl).group(1))
        assert (carpan, taban) == (0.5, 0.0), (carpan, taban)
        d3 = []
        b = tif_cevir(k, p / "lola_m.tif", carpan, taban, sabit_yok=(-32768,))
        f_, n_nan = tif_dogrula(k, p / "lola_m.tif", b, rng, 1000, sabit_yok=(-32768,))
        sinav("M1", "rastgele piksel fark 0", f"1000 piksel, {f_} farkli", f_ == 0, d3)
        sinav("M1", "NaN sayisi = veri-yok sayisi", f"NaN {n_nan}, veri-yok {b['veri_yok_sayisi']}", n_nan == b["veri_yok_sayisi"], d3)
        sinav("M1", "uc degerler D2 ile ayni", f"min {b['min']}, max {b['max']} (D2: -9128,5 / 10781,5)",
              b["min"] == -9128.5 and b["max"] == 10781.5, d3)
        meta_yaz(p, "M1", {"crs": b["crs"], "transform": b["transform"], "cozunurluk": "256 ppd (~118 m)",
                           "olcek": carpan, "ofset": taban, "olcek_kaynagi": "etiket Multiplier / Base",
                           "veri_yok_kurali": "ham -32768 ve dosya nodata -> NaN", "okuma": b, "dosyalar": "lola_m.tif"}, d3, D1, IND, D2)

    bolum("M1", m1)

    # ------------------------------------------------ M2 Ay jeolojisi: GeoUnits.shp -> GeoPackage
    def m2():
        import pyogrio, geopandas as gpd
        h = ham_klasor("M2")
        p = klasor("M2", "jeoloji")
        shp = [x for x in h.rglob("GeoUnits.shp") if x.parent.name == "Shapefiles" and x.parent.parent.name == "Lunar_GIS"]
        assert len(shp) == 1, shp
        df = pyogrio.read_dataframe(shp[0], columns=["FIRST_Unit", "AREA_GEO"])
        oran = float(df["AREA_GEO"].sum()) / (4 * math.pi * R_AY ** 2)
        assert abs(oran - 1) <= 1e-3, f"AREA_GEO toplamı / 4πR² (m²) = {oran}: birim m² değil ya da kapsam eksik"
        out = gpd.GeoDataFrame({"birim": df["FIRST_Unit"].astype("string"), "alan_km2": df["AREA_GEO"].astype(float) / 1e6},
                               geometry=df.geometry, crs=df.crs)
        gp = p / "ay_jeoloji.gpkg"
        pyogrio.write_dataframe(out, gp, layer="ay_jeoloji", driver="GPKG")
        geri = pyogrio.read_dataframe(gp, layer="ay_jeoloji")
        i = rng.integers(0, len(df), 1000)
        b_ok = bool((geri["birim"].astype("string").iloc[i].fillna("<bos>").to_numpy()
                     == df["FIRST_Unit"].astype("string").iloc[i].fillna("<bos>").to_numpy()).all())
        a_ok = bool((geri["alan_km2"].to_numpy()[i] == df["AREA_GEO"].astype(float).to_numpy()[i] / 1e6).all())
        d3 = []
        sinav("M2", "rastgele 1000 poligon: birim ve alan_km2 ham ile ayni",
              f"{len(geri)} kayit (ham {len(df)}); birim {b_ok}; alan {a_ok}; AREA_GEO toplami / 4πR² = {oran:.6f}",
              len(geri) == len(df) and b_ok and a_ok, d3)
        sinav("M2", "bos birim sayisi (kayit)", f"{int(df['FIRST_Unit'].isna().sum())}", True, d3)
        meta_yaz(p, "M2", {"crs": str(df.crs), "olcek": None, "ofset": None, "veri_yok_kurali": "vektör",
                           "kayit_sayisi": len(df), "birim_sayisi": int(df["FIRST_Unit"].nunique()),
                           "alan_km2": "AREA_GEO (belge 10.2) birimi m² (toplam / 4πR² m² = %.6f); alan_km2 = AREA_GEO / 1e6" % oran,
                           "ham_shp": str(shp[0].relative_to(VERI)), "dosyalar": "ay_jeoloji.gpkg (birim, alan_km2)"}, d3, D1, IND, D2)

    bolum("M2", m2)

    # ------------------------------------------------ M3 GHRM: ra_sam, tbol_sam (tbol >= 250 K yok sayılır)
    def m3():
        h = ham_klasor("M3")
        p = klasor("M3", "diviner_ghrm")
        d3, okuma = [], {}
        for desen, cikti, ek in (("dghrm_ra_sam*.tif", "ra_sam.tif", None),
                                 ("dghrm_tbol_sam*.tif", "tbol_sam_K.tif", lambda v: v >= 250)):
            k = sorted(h.glob(desen))
            assert len(k) == 1, (desen, k)
            b = tif_cevir(k[0], p / cikti, 1.0, 0.0, ek_yok=ek)
            f_, n_nan = tif_dogrula(k[0], p / cikti, b, rng, 1000, ek_yok=ek)
            okuma[cikti] = b
            sinav("M3", f"{cikti} rastgele piksel fark 0", f"1000 piksel, {f_} farkli", f_ == 0, d3)
            sinav("M3", f"{cikti} NaN sayisi = veri-yok sayisi", f"NaN {n_nan}, veri-yok {b['veri_yok_sayisi']}",
                  n_nan == b["veri_yok_sayisi"], d3)
            print(f"    {cikti}: min {b['min']}, max {b['max']}", flush=True)
        sinav("M3", "tbol gecerli < 250 K", f"max {okuma['tbol_sam_K.tif']['max']}", okuma["tbol_sam_K.tif"]["max"] < 250, d3)
        meta_yaz(p, "M3", {"crs": okuma["ra_sam.tif"]["crs"], "cozunurluk": "128 ppd, 70°G–70°K", "olcek": 1.0, "ofset": 0.0,
                           "veri_yok_kurali": "NaN = yok; tbol >= 250 K -> NaN (belge 10.2)", "okuma": okuma,
                           "dosyalar": "ra_sam.tif, tbol_sam_K.tif"}, d3, D1, IND, D2)

    bolum("M3", m3)

    # ------------------------------------------------ M4 PRP (kuzey/güney) + GCP: sütun başına .npy
    def m4():
        h = ham_klasor("M4")
        p = klasor("M4", "diviner_prp_gcp")
        d3, sayi = [], {}
        for yari in ("north", "south"):
            tab = h / f"dlre_prp_{yari}.tab"
            df = oku_tablo(tab, lbl_sutunlar(tab.with_suffix(".lbl")))
            assert len(df) == 2880000, len(df)
            ice = df["ice_depth"].to_numpy(dtype=np.float64)
            negler = set(np.unique(ice[ice < 0]).tolist())
            assert negler <= {-1.0, -999.0}, negler                                   # talimat 6
            assert df["temp_max"].to_numpy()[ice == -1].max() <= 101.3                 # talimat 6
            for c in ("tri_clon", "tri_clat", "temp_avg", "temp_max"):
                npy_yaz(p, f"prp_{yari}_{c}", df[c].to_numpy(dtype=np.float64),
                        {"kaynak": f"ay/{h.name}/{tab.name}", "sutun": c, "birim": "derece" if "tri_c" in c else "K", "veri_yok": "yok"})
            v = ice.copy()
            v[ice == -999] = np.nan                                                   # sansürlü (> 2,87 m): değer bilinmiyor
            bay = np.zeros(len(ice), np.uint8)
            bay[ice == -999] = 1
            bay[ice == -1] = 2
            npy_yaz(p, f"prp_{yari}_ice_depth_m", v, {"kaynak": f"ay/{h.name}/{tab.name}", "sutun": "ice_depth", "birim": "m",
                                                       "veri_yok": "-999 (sansürlü, > 2,87 m) -> NaN; -1 değer olarak kalır (bayrak 2)"})
            npy_yaz(p, f"prp_{yari}_ice_depth_bayrak", bay, {"anlam": "1 = -999 sansürlü (> 2,87 m); 2 = -1 belgelenmemiş (talimat 6: "
                                                             "yüzeyde kararlı yorumu, Fisher ve ark. 2017); 0 = yok"})
            sayi[yari] = {"n_0": int((ice == 0).sum()), "n_-1": int((ice == -1).sum()), "n_pozitif": int((ice > 0).sum()),
                          "n_-999": int((ice == -999).sum())}
            d2 = {k: D2OK["M4_ice_depth_sayilari"][yari][k] for k in sayi[yari]}
            sinav("M4", f"PRP {yari} talimat 6 sayilari D2 ile ayni", f"{sayi[yari]}", sayi[yari] == d2, d3)
            # D3 testi: tablo diskten yeniden okunur, kaydedilenlerle karşılaştırılır
            df2 = oku_tablo(tab, lbl_sutunlar(tab.with_suffix(".lbl")))           # bağımsız ikinci okuma
            i = rng.integers(0, len(df2), 1000)
            hi = df2["ice_depth"].to_numpy(dtype=np.float64)[i]
            bek = np.where(hi == -999, np.nan, hi)
            n_fark = int((~esit(bek, np.load(p / f"prp_{yari}_ice_depth_m.npy")[i])).sum())
            bekb = np.where(hi == -999, 1, np.where(hi == -1, 2, 0))
            n_fark += int((bekb != np.load(p / f"prp_{yari}_ice_depth_bayrak.npy")[i]).sum())
            for c in ("tri_clon", "tri_clat", "temp_avg", "temp_max"):
                n_fark += int((df2[c].to_numpy(dtype=np.float64)[i] != np.load(p / f"prp_{yari}_{c}.npy")[i]).sum())
            n_nan = int(np.isnan(np.load(p / f"prp_{yari}_ice_depth_m.npy")).sum())
            sinav("M4", f"PRP {yari} rastgele 1000 satir fark 0", f"{n_fark} farkli", n_fark == 0, d3)
            sinav("M4", f"PRP {yari} NaN sayisi = -999 sayisi", f"NaN {n_nan}, -999 {sayi[yari]['n_-999']}", n_nan == sayi[yari]["n_-999"], d3)
        gcp = sorted(h.glob("global_cumul_avg_cyl_*_002.tab"))
        assert len(gcp) == 4, gcp
        gbilgi = {}
        for tab in gcp:
            kisa = re.search(r"cyl_(\w+?)_002", tab.name).group(1)
            df = pd.read_csv(tab, skipinitialspace=True)
            df.columns = [c.strip().lower() for c in df.columns]
            assert {"clat", "ltim", "tbol"} <= set(df.columns), list(df.columns)
            n_fark, nan_hata = 0, []
            i = rng.integers(0, len(df), 1000)
            df2 = pd.read_csv(tab, skipinitialspace=True)
            df2.columns = [c.strip().lower() for c in df2.columns]
            for c in df.columns:
                ham = df[c].to_numpy(dtype=np.float64)
                v = np.where(ham == -9999, np.nan, ham)                              # belge 10.2: -9999 = yok
                npy_yaz(p, f"gcp_{kisa}_{c}", v, {"kaynak": f"ay/{h.name}/{tab.name}", "sutun": c, "veri_yok": "-9999 -> NaN"})
                t = np.load(p / f"gcp_{kisa}_{c}.npy")
                h2 = df2[c].to_numpy(dtype=np.float64)
                n_fark += int((~esit(np.where(h2[i] == -9999, np.nan, h2[i]), t[i])).sum())
                if int(np.isnan(t).sum()) != int((h2 == -9999).sum() + np.isnan(h2).sum()):
                    nan_hata.append(c)
            gbilgi[kisa] = {"satir": len(df), "sutunlar": list(df.columns)}
            sinav("M4", f"GCP {kisa} rastgele 1000 satir fark 0", f"{len(df.columns)} sutun, {n_fark} farkli", n_fark == 0, d3)
            sinav("M4", f"GCP {kisa} NaN sayisi = -9999 sayisi", f"tutmayan sutun {nan_hata}", not nan_hata, d3)
        meta_yaz(p, "M4", {"crs": "Ay coğrafi (derece)", "olcek": None, "ofset": None,
                           "veri_yok_kurali": "PRP ice_depth -999 -> NaN + bayrak 1; -1 değer + bayrak 2; GCP -9999 -> NaN",
                           "talimat6_sayilari": sayi, "gcp": gbilgi,
                           "dosyalar": "prp_<north|south>_<sutun>.npy, prp_*_ice_depth_m.npy, prp_*_ice_depth_bayrak.npy, gcp_<bant>_<sutun>.npy"},
                 d3, D1, IND, D2)

    bolum("M4", m4)

    # ------------------------------------------------ M5 LP GRS: tablo -> .npy
    def m5():
        h = ham_klasor("M5")
        p = klasor("M5", "lp_grs")
        tab = h / "lpgrs_high1_elem_abundance_2deg.tab"
        satirlar = [s for s in tab.read_text(encoding="ascii").splitlines() if s.strip()]
        T = np.array([[float(x) for x in re.split(r"[,\s]+", s.strip()) if x] for s in satirlar])
        assert T.shape[0] == 11306, T.shape
        adlar = []
        for etk in sorted(h.glob("*.lbl")) + sorted(h.glob("*.fmt")):
            a = lbl_sutunlar(etk)
            if len(a) == T.shape[1]:
                adlar = a
                break
        npy_yaz(p, "lpgrs_tablo", T, {"kaynak": f"ay/{h.name}/{tab.name}", "sutun_adlari": adlar or "açık (etikette sütun sayısı tutmadı)",
                                      "veri_yok": "tanımlı değil; ham değerler aynen"})
        d3 = []
        i = rng.integers(0, len(satirlar), 1000)
        t = np.load(p / "lpgrs_tablo.npy")
        n_fark = sum(int((np.array([float(x) for x in re.split(r"[,\s]+", satirlar[k].strip()) if x]) != t[k]).sum()) for k in i)
        sinav("M5", "rastgele 1000 satir fark 0", f"{T.shape[0]} x {T.shape[1]}, {n_fark} farkli; sutun adlari {'var' if adlar else 'yok'}",
              n_fark == 0, d3)
        sinav("M5", "NaN sayisi = 0 (veri-yok tanimli degil)", f"{int(np.isnan(t).sum())}", int(np.isnan(t).sum()) == 0, d3)
        meta_yaz(p, "M5", {"crs": "Ay coğrafi, 2° eş-alanlı pikseller", "olcek": None, "ofset": None, "veri_yok_kurali": "yok",
                           "sutun_adlari": adlar, "dosyalar": "lpgrs_tablo.npy (11306 satır)"}, d3, D1, IND, D2)

    bolum("M5", m5)

    # ------------------------------------------------ M6 LP hidrojen: hydrogenhd -> .npy
    def m6():
        h = ham_klasor("M6")
        p = klasor("M6", "lp_hidrojen")
        kaynak = h / "hydrogenhd.txt"
        satirlar = [s for s in kaynak.read_text(encoding="ascii", errors="replace").splitlines()
                    if s.strip() and not s.lstrip().startswith("#")]

        def coz(s):
            q = [x.strip() for x in s.split(",")]
            return [float(q[0]), float(q[1]), float(q[2]), float(q[3]), float("nan") if "*" in q[4] else float(q[4])]
        T = np.array([coz(s) for s in satirlar])
        assert T.shape == (259200, 5), T.shape
        npy_yaz(p, "hidrojen_tablo", T, {"kaynak": f"ay/{h.name}/{kaynak.name}",
                                         "sutunlar": ["enlem_g", "enlem_k", "boylam_b", "boylam_d", "H_ppm"],
                                         "veri_yok": "'**********' hücresi -> NaN (1 hücre); 4180 negatif hücre kırpılmaz"})
        d3 = []
        t = np.load(p / "hidrojen_tablo.npy")
        i = rng.integers(0, len(satirlar), 1000)
        n_fark = sum(int((~esit(np.array(coz(satirlar[k])), t[k])).sum()) for k in i)
        sinav("M6", "rastgele 1000 satir fark 0", f"{n_fark} farkli", n_fark == 0, d3)
        n_yildiz = sum(1 for s in satirlar if "*" in s.split(",")[4])
        sinav("M6", "NaN sayisi = bozuk hucre sayisi", f"NaN {int(np.isnan(t).sum())}, '*' {n_yildiz}", int(np.isnan(t).sum()) == n_yildiz == 1, d3)
        sinav("M6", "negatif hucre sayisi korundu", f"{int((t[:, 4] < 0).sum())}", int((t[:, 4] < 0).sum()) == 4180, d3)
        meta_yaz(p, "M6", {"crs": "Ay coğrafi, 0,5°", "olcek": None, "ofset": None,
                           "veri_yok_kurali": "'**********' -> NaN; negatifler kırpılmaz (belge 10.2)",
                           "not": "hydrogenlow ve epis çapraz kontrol dosyaları temiz'e yazılmadı (puan yalnız hydrogenhd'yi kullanır)",
                           "dosyalar": "hidrojen_tablo.npy (259200 x 5)"}, d3, D1, IND, D2)

    bolum("M6", m6)

    # ------------------------------------------------ M7 PGDA: DN -> oran; kuzeydeki anormal piksel NaN
    def m7():
        h = ham_klasor("M7")
        p = klasor("M7", "pgda")
        d3, okuma = [], {}
        for ad in ("AVGVISIB_65S", "AVGVISIB_65N", "LPSR_65S", "LPSR_65N"):
            k = h / f"{ad}_240M_201608.TIF"
            lb = (h / f"{ad}_240M_201608.LBL").read_text(encoding="ascii", errors="replace")
            sf = float(re.search(r"SCALING_FACTOR\s*=\s*([-\d.Ee+]+)", lb).group(1))
            of = float(re.search(r"\bOFFSET\s*=\s*([-\d.Ee+]+)", lb).group(1))
            assert (sf, of) == ((0.00004, 0.0) if ad.startswith("AVG") else (0.000025, 0.5)), (ad, sf, of)
            ozel = []
            if ad.endswith("N"):
                import rasterio
                with rasterio.open(k) as s:
                    n = s.height
                e, b = 88.435, 106.602                                     # belge 10.2: anormal piksel
                rho = 2 * R_AY * math.tan(math.radians(90 - e) / 2)
                x, y = rho * math.sin(math.radians(b)), rho * math.cos(math.radians(b))   # belge 6.8: x = ρ sin λ, y = ρ cos λ
                yarim = n * 240 / 2
                ozel = [(int(math.floor((yarim - y) / 240)), int(math.floor((x + yarim) / 240)))]
            cikti = f"{ad.lower()}.tif"
            b = tif_cevir(k, p / cikti, sf, of)
            if ozel:
                import rasterio
                from rasterio.windows import Window
                r, c = ozel[0]
                with rasterio.open(k) as s:
                    pen = s.read(1, window=Window(c - 2, r - 2, 5, 5)).astype(float) * sf + of
                with rasterio.open(p / cikti, "r+") as t:
                    once = float(t.read(1, window=Window(c, r, 1, 1))[0, 0])
                    t.write(np.array([[np.nan]], dtype=np.float32), 1, window=Window(c, r, 1, 1))
                b["anormal_piksel"] = {"enlem": 88.435, "boylam": 106.602, "satir": r, "sutun": c, "ham_deger_olcekli": once,
                                       "5x5_komsu_ortanca": float(np.median(np.delete(pen.ravel(), 12)))}
                b["veri_yok_sayisi"] += 0 if np.isnan(once) else 1
                print(f"    {ad} anormal piksel ({r}, {c}): değer {once}, komşu ortancası {b['anormal_piksel']['5x5_komsu_ortanca']}", flush=True)
            f_, n_nan = tif_dogrula(k, p / cikti, b, rng, 1000, ozel_nan=ozel)
            okuma[cikti] = b
            sinav("M7", f"{cikti} rastgele piksel fark 0", f"1000 piksel{' + anormal piksel' if ozel else ''}, {f_} farkli", f_ == 0, d3)
            sinav("M7", f"{cikti} NaN sayisi = veri-yok sayisi", f"NaN {n_nan}, beklenen {b['veri_yok_sayisi']}", n_nan == b["veri_yok_sayisi"], d3)
            sinav("M7", f"{cikti} deger araligi [0, 1]", f"min {b['min']}, max {b['max']}", b["min"] >= 0 and b["max"] <= 1 + 1e-6, d3)
        meta_yaz(p, "M7", {"crs": "dosyadaki CRS korundu; belge 10.2: kuzey CRS'i yanlış — konum x = ρ sin λ, y = ρ cos λ "
                                  "(ρ = 2R tan(kolatitüd/2), R = 1737,4 km) ile hesaplanır; D2'de doğrulandı",
                           "cozunurluk": "240 m, 65° kutup", "olcek": {"AVGVISIB": 0.00004, "LPSR": 0.000025},
                           "ofset": {"AVGVISIB": 0.0, "LPSR": 0.5}, "olcek_kaynagi": "etiket SCALING_FACTOR / OFFSET",
                           "veri_yok_kurali": "dosya nodata -> NaN; anormal piksel 88,435°K 106,602°D (kuzey) -> NaN (belge 10.2)",
                           "okuma": okuma, "dosyalar": "avgvisib_65s.tif, avgvisib_65n.tif, lpsr_65s.tif, lpsr_65n.tif"}, d3, D1, IND, D2)

    bolum("M7", m7)

    # ------------------------------------------------ kayıt
    eski = []
    if D3CSV.exists():
        eski = [r for r in csv_oku(D3CSV) if not (r["govde"] == "ay" and r["set"] in calisan)]
    with open(D3CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["govde", "set", "test", "olculen", "durum", "zaman"])
        w.writeheader()
        w.writerows(eski + SATIRLAR)
    say = {}
    for s in SATIRLAR:
        say[s["durum"]] = say.get(s["durum"], 0) + 1
    boyut = sum(f.stat().st_size for f in (TEMIZ / "ay").rglob("*") if f.is_file()) / 1e9
    with open(KAYIT / "13_kasim_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  D3 ay {calisan}: {say}, {round((time.time() - t0) / 60, 1)} dk, temiz/ay {boyut:.2f} GB\n")
    print("=" * 60)
    print(f"D3 Ay {calisan}: {say} | {round((time.time() - t0) / 60, 1)} dk | temiz\\ay {boyut:.2f} GB | kayit/D3.csv")
    return say
