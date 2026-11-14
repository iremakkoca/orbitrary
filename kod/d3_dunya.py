# Developed with assistance from Claude (Anthropic).
# d3_dunya.py — Orbitrary v1.2, belge 17.3 D3 + 10.4: Dünya setleri E1–E10 temiz\dunya\<kod>_<ad>\ altına standart biçimde yazılır.
# Raster: fiziksel birim, float32, veri yok = NaN (GeoTIFF; büyük ızgaralarda bant başına .npy + aynı adlı .json).
# Vektör: GeoPackage (birim, alan_km2). Her klasöre meta.json.
# D3 testi (belge 17.3): 1000 rastgele pikselde ham dosyadan yeniden hesaplanan değerle fark 0; NaN sayısı = veri-yok sayısı.
# Okuma kuralları d2_dunya.py ile aynıdır (D2'de geçti). Ham veri (veri\) yalnız okunur.
import csv, json, math, re, shutil, sys, time
from datetime import datetime
from pathlib import Path

import numpy as np

KOK = Path.home() / "orbitrary"
VERI, KAYIT, TEMIZ = KOK / "veri", KOK / "kayit", KOK / "temiz"
D3CSV = KAYIT / "D3.csv"
TOHUM = 20261113                      # belge V2 tohumu
CMG_GT = [-180.0, 0.05, 0.0, 90.0, 0.0, -0.05]   # 0,05° CMG: sol üst (-180, 90); D2'de cmg_rc ile doğrulandı

# meta.json'un sabit alanları (kaynak: belge 10.1 ve indirme_raporu3 blokları / Bölüm 4 lisans tablosu)
STATIK = {
    "E1": {"ad": "ETOPO 2022 15\" surface", "doi": "10.25921/fd45-gt74", "surum": "ETOPO 2022 v1, 15 yay-saniye, surface",
           "lisans": "CC0 1.0 (data.gov kaydı; rapor Bölüm 4)", "birim": "m (EGM2008)"},
    "E2": {"ad": "MODIS MCD12C1", "doi": "10.5067/MODIS/MCD12C1.061", "surum": "v061, 2023",
           "lisans": "EOSDIS Data Use Policy (rapor Bölüm 4)", "birim": "% (sınıf payı)"},
    "E3": {"ad": "GLiM", "doi": "10.1029/2012GC004370 (makale)", "surum": "LiMW_GIS 2015.gdb, katman GLiM_export",
           "lisans": "sayfada yok — 'açık' (belge CC BY diyor, doğrulanamadı; rapor Bölüm 4)", "birim": "sınıf (xx), km²"},
    "E4": {"ad": "ASTER GED AG5KMMOH", "doi": "açık (rapor E4 künyesi)", "surum": "v041, 2015, 12 ay",
           "lisans": "EOSDIS Data Use Policy (rapor Bölüm 4)", "birim": "yayınım (birimsiz), NDVI (birimsiz)"},
    "E5": {"ad": "MODIS MYD11C3", "doi": "10.5067/MODIS/MYD11C3.061", "surum": "v061 (Aqua), 2023, 12 ay",
           "lisans": "EOSDIS Data Use Policy (rapor Bölüm 4)", "birim": "K"},
    "E6": {"ad": "MODIS MCD43C3", "doi": "10.5067/MODIS/MCD43C3.061", "surum": "v061, 2023'ün her ayının 15'i",
           "lisans": "EOSDIS Data Use Policy (rapor Bölüm 4)", "birim": "albedo (birimsiz)"},
    "E7": {"ad": "Permafrost PERPROB kuzey (Obu ve ark.)", "doi": "10.1594/PANGAEA.888600", "surum": "PERPROB 5.0, 2000–2016",
           "lisans": "CC-BY-3.0 (rapor Bölüm 4)", "birim": "olasılık 0–1"},
    "E8": {"ad": "Permafrost PERPROB Antarktika (Obu ve ark.)", "doi": "10.1594/PANGAEA.902576", "surum": "PERPROB 5.0, 2000–2017",
           "lisans": "CC-BY-4.0 (rapor Bölüm 4)", "birim": "olasılık 0–1"},
    "E9": {"ad": "Global Aridity Index v3.1 (yıllık)", "doi": "10.6084/m9.figshare.7504448", "surum": "v3.1, 1970–2000 ortalaması",
           "lisans": "CC BY 4.0 (rapor Bölüm 4; sayfanın eski metni 'non-commercial use' da diyor)", "birim": "AI (birimsiz)"},
    "E10": {"ad": "SoilGrids 2.0 kil + silt 0–5 cm 1000 m", "doi": "silt: 10.17027/isric-soilgrids/08a4990c-ca15-4871-8d12-ea21dae6b354; kil: açık",
            "surum": "SoilGrids 2.0 (latest, data_aggregated 1000m)", "lisans": "CC BY 4.0 (rapor Bölüm 4)", "birim": "‰ (g/kg)"},
}

SATIRLAR, _TUT = [], []


def csv_oku(yol):
    with open(yol, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sinav(set_, test, olculen, ok, d3):
    durum = "PASS" if ok else "FAIL"
    d3.append({"test": test, "olculen": olculen, "durum": durum})
    SATIRLAR.append({"govde": "dunya", "set": set_, "test": test, "olculen": olculen, "durum": durum,
                     "zaman": datetime.now().isoformat(timespec="seconds")})
    print(f"[{durum}] {set_} {test}: {olculen}", flush=True)


def klasor(kod, ad):
    p = TEMIZ / "dunya" / f"{kod}_{ad}"
    if p.exists():
        shutil.rmtree(p)                  # temiz\ yeniden üretilebilir; ham veri\ hiç silinmez
    p.mkdir(parents=True)
    return p


def meta_yaz(p, kod, ek, d3, D1, IND, D2):
    ind = [r for r in IND if r["set"] == kod and r["durum"] != "FAIL"]
    adres = sorted({r["adres"] for r in ind if r["adres"]})
    m = {"set": kod, **STATIK[kod],
         "kaynak_adresleri": adres if len(adres) <= 5 else adres[:3] + [f"... toplam {len(adres)} adres (kayit/indirme.csv)"],
         "indirme_tarihi": [min(r["zaman"] for r in ind), max(r["zaman"] for r in ind)] if ind else None,
         "ham_sha256": {r["hedef"]: r["sha256"] for r in D1 if r["set"] == kod},
         "gercek_yer_testleri_D2": [{k: r[k] for k in ("test", "nokta", "beklenen", "tolerans_kurali", "beklenen_kaynagi", "olculen", "durum")}
                                    for r in D2 if r["govde"] == "dunya" and r["set"] == kod],
         "D3_testleri": d3, **ek, "uretim_zamani": datetime.now().isoformat(timespec="seconds"),
         "uretim_kodu": "kod/d3_dunya.py"}
    (p / "meta.json").write_text(json.dumps(m, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def esit(bek, tem):
    # fark 0: iki değer birebir aynı ya da ikisi de NaN
    return (bek == tem) | (np.isnan(bek) & np.isnan(tem))


# ---------------------------------------------------------------- tek bantlı GeoTIFF -> float32 GeoTIFF (NaN)
def tif_cevir(kaynak, hedef, olcek=1.0, ofset=0.0, beklenen_nd="dosyadan", satir=512):
    import rasterio
    from rasterio.windows import Window
    with rasterio.open(kaynak) as s:
        assert s.count == 1, f"{kaynak.name}: {s.count} bant"
        assert s.scales[0] == 1.0 and s.offsets[0] == 0.0, f"{kaynak.name}: dosyada ölçek/ofset {s.scales[0]}/{s.offsets[0]}"
        nd = s.nodata
        if beklenen_nd != "dosyadan":
            assert nd == beklenen_nd, f"{kaynak.name}: nodata {nd} != {beklenen_nd}"
        prof = s.profile.copy()
        prof.update(driver="GTiff", dtype="float32", nodata=np.nan, count=1, compress="deflate", predictor=3,
                    tiled=True, blockxsize=512, blockysize=512, BIGTIFF="IF_SAFER")
        n_yok, n_sonsuz, vmin, vmax = 0, 0, np.inf, -np.inf
        with rasterio.open(hedef, "w", **prof) as t:
            for r0 in range(0, s.height, satir):
                w = Window(0, r0, s.width, min(satir, s.height - r0))
                a = s.read(1, window=w)
                yok = np.zeros(a.shape, bool)
                if nd is not None:
                    yok |= np.isnan(a) if (isinstance(nd, float) and math.isnan(nd)) else (a == nd)
                if a.dtype.kind == "f":
                    sonsuz = ~np.isfinite(a) & ~yok
                    n_sonsuz += int(sonsuz.sum())
                    yok |= sonsuz
                v = (a.astype(np.float64) * olcek + ofset).astype(np.float32)
                v[yok] = np.nan
                n_yok += int(yok.sum())
                if (~yok).any():
                    vmin, vmax = min(vmin, float(np.nanmin(v))), max(vmax, float(np.nanmax(v)))
                t.write(v, 1, window=w)
        bilgi = {"ham_dtype": s.dtypes[0], "ham_nodata": nd, "boyut": [s.width, s.height], "crs": str(s.crs),
                 "transform": list(s.transform)[:6], "piksel": list(s.res), "olcek": olcek, "ofset": ofset,
                 "veri_yok_sayisi": n_yok, "sonlu_olmayan_ham": n_sonsuz, "min": vmin, "max": vmax}
    return bilgi


def tif_dogrula(kaynak, hedef, bilgi, rng, n):
    # bağımsız: ham dosyadan rastgele pikseller tek tek okunur, formül yeniden uygulanır; çıktı dosyası baştan okunur
    import rasterio
    from rasterio.windows import Window
    with rasterio.open(kaynak) as s, rasterio.open(hedef) as t:
        assert (s.width, s.height, s.transform, s.crs) == (t.width, t.height, t.transform, t.crs), f"{hedef.name}: geometri farklı"
        assert t.dtypes[0] == "float32"
        rr, cc = rng.integers(0, s.height, n), rng.integers(0, s.width, n)
        ham = np.array([s.read(1, window=Window(int(c), int(r), 1, 1))[0, 0] for r, c in zip(rr, cc)])
        tem = np.array([t.read(1, window=Window(int(c), int(r), 1, 1))[0, 0] for r, c in zip(rr, cc)], dtype=np.float32)
        nd = s.nodata
        bek = (ham.astype(np.float64) * bilgi["olcek"] + bilgi["ofset"]).astype(np.float32)
        if nd is not None:
            bek[np.isnan(ham) if (isinstance(nd, float) and math.isnan(nd)) else (ham == nd)] = np.nan
        if ham.dtype.kind == "f":
            bek[~np.isfinite(ham)] = np.nan
        n_fark = int((~esit(bek, tem)).sum())
        n_nan = 0
        for r0 in range(0, t.height, 512):
            n_nan += int(np.isnan(t.read(1, window=Window(0, r0, t.width, min(512, t.height - r0)))).sum())
    return n_fark, n_nan


def npy_yaz(p, ad, v, bilgi):
    assert v.dtype == np.float32
    np.save(p / f"{ad}.npy", v)
    (p / f"{ad}.json").write_text(json.dumps({**bilgi, "sekil": list(v.shape), "dtype": "float32", "veri_yok": "NaN"},
                                             ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def npy_dogrula(p, ad, ham, formul, yok_maskesi, rng, n):
    # kaydedilen .npy diskten yeniden açılır; ham diziden bağımsız formülle karşılaştırılır
    t = np.load(p / f"{ad}.npy", mmap_mode="r")
    assert t.shape == ham.shape and t.dtype == np.float32
    rr, cc = rng.integers(0, ham.shape[0], n), rng.integers(0, ham.shape[1], n)
    h = ham[rr, cc]
    bek = formul(h).astype(np.float32)
    bek[yok_maskesi(h)] = np.nan
    n_fark = int((~esit(bek, np.asarray(t[rr, cc]))).sum())
    n_nan = int(np.isnan(t).sum())
    n_yok = int(yok_maskesi(ham).sum())
    return n_fark, n_nan, n_yok


def main(setler=None):
    t0 = time.time()
    from osgeo import gdal
    gdal.UseExceptions()
    import h5py

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

    def alt(yol, ad):
        s = [x[0] for x in gdal.Open(str(yol)).GetSubDatasets() if x[0].endswith(":" + ad) or x[0].endswith(ad)]
        assert len(s) >= 1, f"{ad} alt veri seti yok"
        ds = gdal.Open(s[0])
        _TUT.append(ds)
        return ds

    def tarih(dosya):
        return re.search(r"\.?A(\d{7})", dosya.name).group(1)

    # ------------------------------------------------ E1 ETOPO: 288 karo -> 288 float32 GeoTIFF
    def e1():
        p = klasor("E1", "etopo")
        karolar = sorted((VERI / "dunya/E1_etopo").glob("ETOPO_2022_v1_15s_*_surface.tif"))
        assert len(karolar) == 288, len(karolar)
        d3, n_fark, n_ornek, nan_hata, toplam_yok = [], 0, 0, [], 0
        for i, k in enumerate(karolar):
            b = tif_cevir(k, p / k.name, 1.0, 0.0, beklenen_nd=-99999)
            assert b["ham_dtype"] == "float32"
            f, n_nan = tif_dogrula(k, p / k.name, b, rng, 4)
            n_fark, n_ornek, toplam_yok = n_fark + f, n_ornek + 4, toplam_yok + b["veri_yok_sayisi"]
            if n_nan != b["veri_yok_sayisi"]:
                nan_hata.append(k.name)
            if (i + 1) % 48 == 0:
                print(f"    {i + 1}/288 karo", flush=True)
        sinav("E1", "rastgele piksel fark 0", f"{n_ornek} piksel (288 karo x 4), {n_fark} farkli", n_fark == 0, d3)
        sinav("E1", "NaN sayisi = veri-yok sayisi", f"288 karo; tutmayan karo {len(nan_hata)} {nan_hata[:5]}; toplam veri-yok {toplam_yok}",
              not nan_hata, d3)
        meta_yaz(p, "E1", {"crs": b["crs"], "cozunurluk": "15 yay-saniye", "olcek": 1.0, "ofset": 0.0,
                           "veri_yok_kurali": "ham -99999 -> NaN", "dosyalar": "288 karo, adlar ham ile aynı (üst-sol köşe)",
                           "toplam_veri_yok": toplam_yok}, d3, D1, IND, D2)

    bolum("E1", e1)

    # ------------------------------------------------ E2 MCD12C1: 17 sınıf payı -> 17 .npy
    def e2():
        p = klasor("E2", "mcd12c1")
        lc = alt(VERI / "dunya/E2_mcd12c1/MCD12C1.A2023001.061.2024251212901.hdf", "Land_Cover_Type_1_Percent")
        md = lc.GetMetadata()
        assert (lc.RasterXSize, lc.RasterYSize, lc.RasterCount) == (7200, 3600, 17)
        fill = int(float(md["_FillValue"])) if "_FillValue" in md else 255
        fill_kaynak = "dosya _FillValue" if "_FillValue" in md else "dosyada yok -> belge 10.1 (255)"
        assert fill == 255, f"_FillValue {fill}"
        assert float(md.get("scale_factor", 1)) == 1.0 and float(md.get("add_offset", 0)) == 0.0, md
        d3, n_fark, n_nan_hata = [], 0, []
        for k in range(17):                                   # bant k+1 = sınıf k (D2'de doğrulandı)
            ham = lc.GetRasterBand(k + 1).ReadAsArray()
            v = ham.astype(np.float32)
            v[ham == fill] = np.nan
            ad = f"sinif_{k:02d}_yuzde"
            npy_yaz(p, ad, v, {"kaynak": "dunya/E2_mcd12c1/MCD12C1.A2023001.061.2024251212901.hdf",
                               "alt_veri_seti": "Land_Cover_Type_1_Percent", "bant": k + 1, "sinif": k,
                               "geotransform": CMG_GT, "gdal_geotransform": lc.GetGeoTransform(), "crs": "EPSG:4326 (CMG 0,05°)",
                               "birim": "%", "olcek": 1.0, "ofset": 0.0, "veri_yok_ham": fill})
            f, n_nan, n_yok = npy_dogrula(p, ad, ham, lambda h: h.astype(np.float64), lambda h: h == fill, rng, 1000)
            n_fark += f
            if n_nan != n_yok:
                n_nan_hata.append(k)
        sinav("E2", "rastgele piksel fark 0", f"17 sinif x 1000 piksel, {n_fark} farkli", n_fark == 0, d3)
        sinav("E2", "NaN sayisi = veri-yok sayisi", f"tutmayan sinif {n_nan_hata}", not n_nan_hata, d3)
        meta_yaz(p, "E2", {"crs": "EPSG:4326 (CMG 0,05°)", "geotransform": CMG_GT, "cozunurluk": "0,05°", "olcek": 1.0, "ofset": 0.0,
                           "veri_yok_kurali": f"ham {fill} -> NaN ({fill_kaynak})",
                           "dosyalar": "sinif_00_yuzde.npy ... sinif_16_yuzde.npy (bant k+1 = sınıf k)"}, d3, D1, IND, D2)

    bolum("E2", e2)

    # ------------------------------------------------ E3 GLiM: GDB -> GeoPackage (birim, alan_km2)
    def e3():
        import pyogrio
        p = klasor("E3", "glim")
        gdb = VERI / "dunya/E3_glim/acik/LiMW_GIS 2015.gdb"
        katman = [x[0] for x in pyogrio.list_layers(gdb)]
        assert "GLiM_export" in katman, katman
        info = pyogrio.read_info(gdb, layer="GLiM_export")
        alanlar = list(info["fields"])
        assert "xx" in alanlar, alanlar
        sutun = ["xx"] + (["Shape_Area"] if "Shape_Area" in alanlar else [])
        df = pyogrio.read_dataframe(gdb, layer="GLiM_export", columns=sutun)
        wkt = df.crs.to_wkt()
        assert "eckert_iv" in wkt.lower().replace(" ", "_"), "CRS Eckert IV değil (belge 10.1)"
        alan = df.geometry.area.to_numpy() / 1e6               # eş-alanlı Eckert IV, m² -> km²
        import geopandas as gpd
        out = gpd.GeoDataFrame({"birim": df["xx"].astype("string"), "alan_km2": alan}, geometry=df.geometry, crs=df.crs)
        gp = p / "glim.gpkg"
        pyogrio.write_dataframe(out, gp, layer="glim", driver="GPKG")
        d3 = []
        geri = pyogrio.read_dataframe(gp, layer="glim")
        i = rng.integers(0, len(df), 1000)
        b_ok = bool((geri["birim"].astype("string").iloc[i].fillna("<bos>").to_numpy()
                     == df["xx"].astype("string").iloc[i].fillna("<bos>").to_numpy()).all())
        a_geri = geri["alan_km2"].to_numpy()[i]
        a_yeni = geri.geometry.area.to_numpy()[i] / 1e6
        fark = float(np.max(np.abs(a_geri - a_yeni) / np.where(a_yeni > 0, a_yeni, 1)))
        sinav("E3", "rastgele 1000 poligon: birim ayni, alan_km2 yeniden hesapla ayni",
              f"{len(geri)} kayit (ham {len(df)}); birim esit {b_ok}; alan en buyuk goreli fark {fark:.2e}",
              len(geri) == len(df) and b_ok and fark <= 1e-12, d3)
        n_bos_birim, n_bos_geo = int(df["xx"].isna().sum()), int(df.geometry.isna().sum())
        sinav("E3", "bos birim / bos geometri sayisi (kayit)", f"bos birim {n_bos_birim}, bos geometri {n_bos_geo}", True, d3)
        sa = None
        if "Shape_Area" in df:
            sa = float(np.nanmax(np.abs(df["Shape_Area"].to_numpy() / 1e6 - alan) / np.where(alan > 0, alan, 1)))
        meta_yaz(p, "E3", {"crs": "World Eckert IV (ham CRS korundu)", "crs_wkt": wkt, "olcek": None, "ofset": None,
                           "veri_yok_kurali": "vektör; boş birim kayda yazılır, NaN yok",
                           "kayit_sayisi": len(df), "birim_sayisi": int(df["xx"].nunique()),
                           "alan_km2": "geometrinin Eckert IV (eş-alanlı) alanı / 1e6",
                           "Shape_Area_ile_en_buyuk_goreli_fark": sa, "dosyalar": "glim.gpkg (katman glim: birim, alan_km2)"},
                 d3, D1, IND, D2)

    bolum("E3", e3)

    # ------------------------------------------------ E4 ASTER GED: 12 ay x (5 yayınım bandı + NDVI) -> .npy
    def att(d, ad):
        for k, v in d.items():
            if k.strip().lower() == ad.lower():
                return float(np.ravel(v)[0]) if not isinstance(v, (bytes, str)) else float(v)
        return None

    def e4():
        p = klasor("E4", "aster_ged")
        dosyalar = sorted((VERI / "dunya/E4_aster_ged").glob("ASTER_GEDv4.1_A2015*.h5"))
        assert len(dosyalar) == 12
        d3, n_fark, nan_hata, bayrak_hata, ndvi_bilgi = [], 0, [], [], {}
        for dosya in dosyalar:
            tr = tarih(dosya)
            with h5py.File(dosya, "r") as f:
                em, nd = f["SDS/Emissivity"], f["SDS/NDVI"]
                ea, na = dict(em.attrs), dict(nd.attrs)
                olcek, ofset = att(ea, "Scale Factor"), att(ea, "Offset")
                n_olcek, n_ofset = att(na, "Scale Factor"), att(na, "Offset")
                assert olcek == 0.002 and ofset is not None and abs(ofset - 0.49) < 1e-9, (olcek, ofset)
                assert n_olcek == 0.001 and n_ofset == 0.0, (n_olcek, n_ofset)
                assert not [k for k in na if "fill" in k.lower() or "missing" in k.lower()], "NDVI'de fill çıktı: kural gözden geçirilmeli"
                eksen = [i for i, s in enumerate(em.shape) if s == 5]
                assert len(eksen) == 1, em.shape
                E = np.moveaxis(em[...], eksen[0], 0)            # (5, satır, sütun): 0 = bant 10 ... 4 = bant 14
                N_ = nd[...]
            assert E.shape[1:] == (3600, 7200) and N_.shape == (3600, 7200), (E.shape, N_.shape)
            assert int(N_.min()) >= 0, f"NDVI ham negatif: {N_.min()}"
            ndvi_bilgi[tr] = {"oznitelikler": {k: (v.tolist() if hasattr(v, "tolist") else str(v)) for k, v in na.items()},
                              "ham_min": int(N_.min()), "ham_max": int(N_.max())}
            for j in range(5):
                ham = E[j]
                v = (ham.astype(np.float64) * olcek + ofset).astype(np.float32)
                v[ham == 0] = np.nan                            # 0 = yok (rapor E4)
                ad = f"yayinim_b{10 + j}_{tr}"
                npy_yaz(p, ad, v, {"kaynak": f"dunya/E4_aster_ged/{dosya.name}", "veri_seti": "SDS/Emissivity", "bant": 10 + j,
                                   "geotransform": CMG_GT, "crs": "EPSG:4326 (0,05°)", "birim": "yayınım", "olcek": olcek,
                                   "ofset": ofset, "ofset_kaynagi": "dosya özniteliği (talimat 7)", "veri_yok_ham": 0})
                f_, n_nan, n_yok = npy_dogrula(p, ad, ham, lambda h: h.astype(np.float64) * 0.002 + 0.49, lambda h: h == 0, rng, 1000)
                n_fark += f_
                if n_nan != n_yok:
                    nan_hata.append(ad)
            em_yok = (E == 0).all(axis=0)                        # yayınımın 5 bandı da yok = ürünün boş pikseli
            v = (N_.astype(np.float64) * n_olcek).astype(np.float32)
            v[em_yok] = np.nan
            bay = ((N_ == 0) & ~em_yok).astype(np.uint8)          # 1 = kara pikselinde ham 0 (bitki yok ya da kırpılmış negatif)
            ad = f"ndvi_{tr}"
            npy_yaz(p, ad, v, {"kaynak": f"dunya/E4_aster_ged/{dosya.name}", "veri_seti": "SDS/NDVI", "geotransform": CMG_GT,
                               "crs": "EPSG:4326 (0,05°)", "birim": "NDVI", "olcek": n_olcek, "ofset": n_ofset,
                               "veri_yok_kurali": "dosyada fill yok; yayınımın 5 bandı da 0 olan piksel -> NaN",
                               "bayrak_dosyasi": f"ndvi_bayrak_{tr}.npy"})
            np.save(p / f"ndvi_bayrak_{tr}.npy", bay)
            (p / f"ndvi_bayrak_{tr}.json").write_text(json.dumps(
                {"kaynak": f"dunya/E4_aster_ged/{dosya.name}", "sekil": list(bay.shape), "dtype": "uint8", "geotransform": CMG_GT,
                 "anlam": "1 = yayınım verisi olan pikselde NDVI ham 0 (bitki yok ya da kırpılmış negatif; belgelenmemiş kod); 0 = yok"},
                ensure_ascii=False, indent=2), encoding="utf-8")
            # D3 testi: kaydedilenler diskten açılır, ham dizilerden yeniden hesaplanır
            t = np.load(p / f"{ad}.npy", mmap_mode="r")
            rr, cc = rng.integers(0, 3600, 1000), rng.integers(0, 7200, 1000)
            bek = (N_[rr, cc].astype(np.float64) * 0.001).astype(np.float32)
            bek[(E[:, rr, cc] == 0).all(axis=0)] = np.nan
            n_fark += int((~esit(bek, np.asarray(t[rr, cc]))).sum())
            if int(np.isnan(t).sum()) != int(((E == 0).sum(axis=0) == 5).sum()):
                nan_hata.append(ad)
            tb = np.load(p / f"ndvi_bayrak_{tr}.npy")
            if int(tb.sum()) != int(((N_ == 0) & ((E != 0).any(axis=0))).sum()):
                bayrak_hata.append(tr)
            ndvi_bilgi[tr].update({"nan": int(em_yok.sum()), "bayrak_1": int(bay.sum())})
            print(f"    {tr} tamam (NDVI NaN {int(em_yok.sum())}, bayrak {int(bay.sum())})", flush=True)
        sinav("E4", "rastgele piksel fark 0", f"12 ay x 6 dizi x 1000 piksel, {n_fark} farkli", n_fark == 0, d3)
        sinav("E4", "NaN sayisi = veri-yok sayisi", f"tutmayan dizi {nan_hata}", not nan_hata, d3)
        sinav("E4", "NDVI bayrak sayisi = ham 0 (yayinim olan piksel) sayisi", f"tutmayan ay {bayrak_hata}", not bayrak_hata, d3)
        meta_yaz(p, "E4", {"crs": "EPSG:4326 (0,05°)", "geotransform": CMG_GT, "cozunurluk": "0,05°",
                           "olcek": {"yayinim": 0.002, "ndvi": 0.001}, "ofset": {"yayinim": 0.49, "ndvi": 0.0},
                           "ofset_kaynagi": "dosya öznitelikleri: Emissivity 'Offset' = 0,49 (talimat 7); NDVI 'Offset' = 0",
                           "veri_yok_kurali": "yayınım ham 0 -> NaN (bant başına); NDVI: dosyada fill yok, yayınımın 5 bandı da 0 -> NaN",
                           "bayrak": "ndvi_bayrak_<YYYYDDD>.npy: 1 = yayınım olan pikselde NDVI ham 0 (bitki yok ya da kırpılmış negatif)",
                           "ndvi_inceleme": "2015001 dosyası: NDVI ham 0–999, negatif yok; yayınımın boş olduğu 17 321 730 pikselin 17 260 156'sında NDVI 0",
                           "ndvi_oznitelikleri": ndvi_bilgi,
                           "dosyalar": "yayinim_b10..b14_<YYYYDDD>.npy, ndvi_<YYYYDDD>.npy, ndvi_bayrak_<YYYYDDD>.npy (12 ay)"}, d3, D1, IND, D2)

    bolum("E4", e4)

    # ------------------------------------------------ E5 MYD11C3: 12 ay x gündüz/gece LST -> .npy (K)
    def e5():
        p = klasor("E5", "myd11c3")
        dosyalar = sorted((VERI / "dunya/E5_myd11c3").glob("MYD11C3.A2023*.hdf"))
        assert len(dosyalar) == 12
        d3, n_fark, nan_hata, gecersiz = [], 0, [], {}
        for dosya in dosyalar:
            tr = tarih(dosya)
            for deg, kisa in (("LST_Day_CMG", "gunduz"), ("LST_Night_CMG", "gece")):
                ds = alt(dosya, deg)
                md = ds.GetMetadata()
                assert float(md["scale_factor"]) == 0.02 and int(float(md["_FillValue"])) == 0, md
                assert float(md.get("add_offset", 0)) == 0.0, md
                ham = ds.GetRasterBand(1).ReadAsArray()
                assert ham.shape == (3600, 7200)
                v = (ham.astype(np.float64) * 0.02).astype(np.float32)
                v[ham == 0] = np.nan
                vr = md.get("valid_range")
                if vr:
                    lo, hi = [float(x) for x in re.split(r"[,\s]+", vr.strip()) if x]
                    gecersiz[f"{kisa}_{tr}"] = int(((ham != 0) & ((ham < lo) | (ham > hi))).sum())
                ad = f"lst_{kisa}_{tr}"
                npy_yaz(p, ad, v, {"kaynak": f"dunya/E5_myd11c3/{dosya.name}", "alt_veri_seti": deg, "geotransform": CMG_GT,
                                   "crs": "EPSG:4326 (CMG 0,05°)", "birim": "K", "olcek": 0.02, "ofset": 0.0, "veri_yok_ham": 0,
                                   "valid_range": vr})
                f_, n_nan, n_yok = npy_dogrula(p, ad, ham, lambda h: h.astype(np.float64) * 0.02, lambda h: h == 0, rng, 1000)
                n_fark += f_
                if n_nan != n_yok:
                    nan_hata.append(ad)
        sinav("E5", "rastgele piksel fark 0", f"12 ay x 2 x 1000 piksel, {n_fark} farkli", n_fark == 0, d3)
        sinav("E5", "NaN sayisi = veri-yok sayisi", f"tutmayan dizi {nan_hata}", not nan_hata, d3)
        sinav("E5", "valid_range disi (fill olmayan) deger sayisi (kayit)", f"toplam {sum(gecersiz.values())}", True, d3)
        meta_yaz(p, "E5", {"crs": "EPSG:4326 (CMG 0,05°)", "geotransform": CMG_GT, "cozunurluk": "0,05°", "olcek": 0.02, "ofset": 0.0,
                           "veri_yok_kurali": "ham 0 -> NaN (dosya _FillValue)", "valid_range_disi": gecersiz,
                           "dosyalar": "lst_gunduz_<YYYYDDD>.npy, lst_gece_<YYYYDDD>.npy (12 ay)"}, d3, D1, IND, D2)

    bolum("E5", e5)

    # ------------------------------------------------ E6 MCD43C3: 12 tarih albedo -> .npy
    def e6():
        p = klasor("E6", "mcd43c3")
        dosyalar = sorted((VERI / "dunya/E6_mcd43c3").glob("MCD43C3.A2023*.hdf"))
        assert len(dosyalar) == 12
        d3, n_fark, nan_hata = [], 0, []
        yok = lambda h: (h < 0) | (h > 32766)                   # belge 10.1: geçerli 0–32 766
        for dosya in dosyalar:
            tr = tarih(dosya)
            ds = alt(dosya, "Albedo_WSA_shortwave")
            md = ds.GetMetadata()
            assert float(md["scale_factor"]) == 0.001 and int(float(md["_FillValue"])) == 32767, md
            assert float(md.get("add_offset", 0)) == 0.0, md
            ham = ds.GetRasterBand(1).ReadAsArray()
            assert ham.shape == (3600, 7200)
            v = (ham.astype(np.float64) * 0.001).astype(np.float32)
            v[yok(ham)] = np.nan
            ad = f"albedo_wsa_{tr}"
            npy_yaz(p, ad, v, {"kaynak": f"dunya/E6_mcd43c3/{dosya.name}", "alt_veri_seti": "Albedo_WSA_shortwave",
                               "geotransform": CMG_GT, "crs": "EPSG:4326 (CMG 0,05°)", "birim": "albedo", "olcek": 0.001,
                               "ofset": 0.0, "veri_yok_ham": "0–32766 dışı (fill 32767)"})
            f_, n_nan, n_yok = npy_dogrula(p, ad, ham, lambda h: h.astype(np.float64) * 0.001, yok, rng, 1000)
            n_fark += f_
            if n_nan != n_yok:
                nan_hata.append(ad)
        sinav("E6", "rastgele piksel fark 0", f"12 tarih x 1000 piksel, {n_fark} farkli", n_fark == 0, d3)
        sinav("E6", "NaN sayisi = veri-yok sayisi", f"tutmayan dizi {nan_hata}", not nan_hata, d3)
        meta_yaz(p, "E6", {"crs": "EPSG:4326 (CMG 0,05°)", "geotransform": CMG_GT, "cozunurluk": "0,05°", "olcek": 0.001, "ofset": 0.0,
                           "veri_yok_kurali": "ham 0–32766 dışı -> NaN (fill 32767)",
                           "dosyalar": "albedo_wsa_<YYYYDDD>.npy (12 tarih)"}, d3, D1, IND, D2)

    bolum("E6", e6)

    # ------------------------------------------------ tek tif setleri: E7, E8, E9, E10
    def tek_tif(kod, ad, kaynaklar, olcek, aralik, ek):
        p = klasor(kod, ad)
        d3, n_fark, nan_hata, bilgiler = [], 0, [], {}
        for k, hedef_ad in kaynaklar:
            b = tif_cevir(k, p / hedef_ad, olcek, 0.0)
            f_, n_nan = tif_dogrula(k, p / hedef_ad, b, rng, 1000)
            n_fark += f_
            if n_nan != b["veri_yok_sayisi"]:
                nan_hata.append(hedef_ad)
            bilgiler[hedef_ad] = b
            print(f"    {hedef_ad}: min {b['min']}, max {b['max']}, veri-yok {b['veri_yok_sayisi']}", flush=True)
        sinav(kod, "rastgele piksel fark 0", f"{len(kaynaklar)} dosya x 1000 piksel, {n_fark} farkli", n_fark == 0, d3)
        sinav(kod, "NaN sayisi = veri-yok sayisi", f"tutmayan {nan_hata}", not nan_hata, d3)
        lo, hi = aralik
        mn, mx = min(b["min"] for b in bilgiler.values()), max(b["max"] for b in bilgiler.values())
        sinav(kod, f"gecerli deger araligi [{lo}, {hi}]", f"min {mn}, max {mx}", lo <= mn and mx <= hi, d3)
        b0 = next(iter(bilgiler.values()))
        meta_yaz(p, kod, {"crs": b0["crs"], "piksel": b0["piksel"], "olcek": olcek, "ofset": 0.0,
                          "veri_yok_kurali": "ham nodata (dosyadan) ve sonlu olmayan değerler -> NaN",
                          "okuma": bilgiler, **ek}, d3, D1, IND, D2)

    bolum("E7", lambda: tek_tif("E7", "permafrost_kuzey",
                                [(VERI / "dunya/E7_permafrost_kuzey/acik/UiO_PEX_PERPROB_5.0_20181128_2000_2016_NH.tif", "perprob_kuzey.tif")],
                                1.0, (0.0, 1.0), {"dosyalar": "perprob_kuzey.tif"}))
    bolum("E8", lambda: tek_tif("E8", "permafrost_antarktika",
                                [(VERI / "dunya/E8_permafrost_antarktika/acik/UiO_PEX_PERPROB_5.0_20181205_2000_2017_ANT.tif", "perprob_antarktika.tif")],
                                1.0, (0.0, 1.0), {"dosyalar": "perprob_antarktika.tif"}))
    def e9():
        import rasterio
        from rasterio.windows import Window
        p = klasor("E9", "aridity")
        k = VERI / "dunya/E9_aridity/acik/Global-AI_ET0__annual_v3_1/ai_v31_yr.tif"
        su = np.load(TEMIZ / "dunya/E2_mcd12c1/sinif_00_yuzde.npy", mmap_mode="r")      # MCD12C1 sınıf 0 = su (%), 0,05°
        n = {"nan": 0, "bayrak_1": 0, "bayrak_2": 0}
        vmin, vmax = np.inf, -np.inf
        with rasterio.open(k) as s:
            tr = s.transform
            assert s.count == 1 and s.dtypes[0] == "uint16" and s.nodata is None, (s.count, s.dtypes, s.nodata)
            assert s.scales[0] == 1.0 and s.offsets[0] == 0.0
            assert abs(tr.a - 1 / 120) < 1e-9 and abs(tr.e + 1 / 120) < 1e-9 and abs(tr.c + 180) < 1e-6 and abs(tr.f - 90) < 1e-6, list(tr)
            assert s.height % 6 == 0 and s.width == 43200
            prof = s.profile.copy()
            prof.update(driver="GTiff", dtype="float32", nodata=np.nan, compress="deflate", predictor=3,
                        tiled=True, blockxsize=512, blockysize=512, BIGTIFF="IF_SAFER")
            bprof = s.profile.copy()
            bprof.update(driver="GTiff", dtype="uint8", nodata=None, compress="deflate", tiled=True, blockxsize=512, blockysize=512)
            with rasterio.open(p / "ai.tif", "w", **prof) as t, rasterio.open(p / "ai_bayrak.tif", "w", **bprof) as tb:
                for r0 in range(0, s.height, 1200):
                    h = min(1200, s.height - r0)
                    w = Window(0, r0, s.width, h)
                    a = s.read(1, window=w)
                    su_w = np.asarray(su[r0 // 6:(r0 + h) // 6, :]).repeat(6, 0).repeat(6, 1)
                    yok = (a == 0) & (su_w == 100)
                    b = np.zeros(a.shape, np.uint8)
                    b[(a == 0) & ~yok] = 1
                    b[a == 65535] = 2
                    v = (a.astype(np.float64) * 1e-4).astype(np.float32)
                    v[yok] = np.nan
                    n["nan"] += int(yok.sum()); n["bayrak_1"] += int((b == 1).sum()); n["bayrak_2"] += int((b == 2).sum())
                    if (~yok).any():
                        vmin, vmax = min(vmin, float(np.nanmin(v))), max(vmax, float(np.nanmax(v)))
                    t.write(v, 1, window=w)
                    tb.write(b, 1, window=w)
        d3 = []
        with rasterio.open(k) as s, rasterio.open(p / "ai.tif") as t, rasterio.open(p / "ai_bayrak.tif") as tb:
            assert (s.width, s.height, s.transform, s.crs) == (t.width, t.height, t.transform, t.crs) == (tb.width, tb.height, tb.transform, tb.crs)
            rr, cc = rng.integers(0, s.height, 1000), rng.integers(0, s.width, 1000)
            ham = np.array([s.read(1, window=Window(int(c), int(r), 1, 1))[0, 0] for r, c in zip(rr, cc)])
            tem = np.array([t.read(1, window=Window(int(c), int(r), 1, 1))[0, 0] for r, c in zip(rr, cc)], dtype=np.float32)
            tbo = np.array([tb.read(1, window=Window(int(c), int(r), 1, 1))[0, 0] for r, c in zip(rr, cc)])
            sw = np.asarray(su)[rr // 6, cc // 6]
            bek = (ham.astype(np.float64) / 10000).astype(np.float32)
            bek[(ham == 0) & (sw == 100)] = np.nan
            bekb = np.where(ham == 65535, 2, np.where((ham == 0) & ~(sw == 100), 1, 0))
            n_fark = int((~esit(bek, tem)).sum()) + int((bekb != tbo).sum())
            n_nan = n1 = n2 = 0
            for r0 in range(0, t.height, 1200):
                w = Window(0, r0, t.width, min(1200, t.height - r0))
                n_nan += int(np.isnan(t.read(1, window=w)).sum())
                bb = tb.read(1, window=w)
                n1 += int((bb == 1).sum()); n2 += int((bb == 2).sum())
        sinav("E9", "rastgele piksel fark 0 (deger + bayrak)", f"1000 piksel, {n_fark} farkli", n_fark == 0, d3)
        sinav("E9", "NaN sayisi = veri-yok sayisi (ham 0 ve su %100)", f"NaN {n_nan}, beklenen {n['nan']}", n_nan == n["nan"], d3)
        sinav("E9", "bayrak sayilari (1: karada ham 0, 2: ham 65535)", f"1: {n1} (beklenen {n['bayrak_1']}), 2: {n2} (beklenen {n['bayrak_2']})",
              n1 == n["bayrak_1"] and n2 == n["bayrak_2"], d3)
        sinav("E9", "gecerli deger araligi [0, 6.5535]", f"min {vmin}, max {vmax}", 0 <= vmin and vmax <= 6.5535 + 1e-6, d3)
        meta_yaz(p, "E9", {"crs": "EPSG:4326", "piksel": [1 / 120, 1 / 120], "olcek": 1e-4, "ofset": 0.0,
                           "carpan_kaynagi": "Readme v3.1: 'Global-AI values need to be multiplied by 0.0001'",
                           "veri_yok_kurali": "dosyada nodata yok; ham 0 olan ve MCD12C1 sınıf 0 (su) %100 olan piksel -> NaN "
                                              "(su maskesi: temiz/dunya/E2_mcd12c1/sinif_00_yuzde.npy, 0,05° = 6 x 6 piksel)",
                           "bayrak": "ai_bayrak.tif: 1 = karada ham 0 (aşırı kurak ya da kıyı/örtüşme; belirsiz), "
                                     "2 = ham 65535 (uint16 tavanı, AI >= 6,5535; kırpılmış)",
                           "inceleme": {"ham_0_su": 550911298, "ham_0_kara": 4883730, "ham_65535_su": 256, "ham_65535_kara": 1202807,
                                        "65535_enlem": "çoğu 70–90°K (Grönland) ve 40–60°G; buz örtüsü (veriden çıkarım)",
                                        "nokta": "Point Nemo ham 0, Atacama Yungay ham 0, Manaus ham 19257"},
                           "sayilar": n, "dosyalar": "ai.tif (AI, NaN = veri yok), ai_bayrak.tif (uint8)"}, d3, D1, IND, D2)

    bolum("E9", e9)
    bolum("E10", lambda: tek_tif("E10", "soilgrids",
                                 [(VERI / "dunya/E10_soilgrids/clay/clay_0-5cm_mean_1000.tif", "kil_0-5cm.tif"),
                                  (VERI / "dunya/E10_soilgrids/silt/silt_0-5cm_mean_1000.tif", "silt_0-5cm.tif")],
                                 1.0, (0.0, 1000.0), {"dosyalar": "kil_0-5cm.tif, silt_0-5cm.tif (‰)"}))

    # ------------------------------------------------ kayıt
    eski = []
    if D3CSV.exists():
        eski = [r for r in csv_oku(D3CSV) if not (r["govde"] == "dunya" and r["set"] in calisan)]
    with open(D3CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["govde", "set", "test", "olculen", "durum", "zaman"])
        w.writeheader()
        w.writerows(eski + SATIRLAR)
    say = {}
    for s in SATIRLAR:
        say[s["durum"]] = say.get(s["durum"], 0) + 1
    boyut = sum(f.stat().st_size for f in (TEMIZ / "dunya").rglob("*") if f.is_file()) / 1e9
    with open(KAYIT / "13_kasim_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  D3 dunya {calisan}: {say}, {round((time.time() - t0) / 60, 1)} dk, temiz/dunya {boyut:.2f} GB\n")
    print("=" * 60)
    print(f"D3 Dünya {calisan}: {say} | {round((time.time() - t0) / 60, 1)} dk | temiz\\dunya {boyut:.2f} GB | kayit/D3.csv")
    return say
