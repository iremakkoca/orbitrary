# Developed with assistance from Claude (Anthropic).
# d2_dunya.py — Orbitrary v1.2, belge 17.3 D2 (gerçek-yer testleri), Dünya setleri E1–E10.
# Her test: nokta, koordinat ve kaynağı, beklenen değer ve kaynağı, tolerans kuralı -> kayit/D2.csv
# Okuma ayrıntıları (ölçek, ofset, veri-yok, boyut) dosyadan okunur ve kayit/D2_okuma_dunya.json'a yazılır.
# Geçmeyen test silinmez; FAIL yazılır. Talimat 7 (ASTER): en küçük yayınım 0,52–0,61 -> UYARI (iş sürer),
# <= 0,51 -> FAIL (ofset uygulanmamış demektir).
import csv, json, math, time
from datetime import datetime
from pathlib import Path

import numpy as np

KOK = Path.home() / "orbitrary"
VERI, KAYIT = KOK / "veri", KOK / "kayit"
D2CSV = KAYIT / "D2.csv"
ALANLAR = ["govde", "set", "test", "nokta", "enlem", "boylam", "koordinat_kaynagi", "beklenen",
           "tolerans_kurali", "beklenen_kaynagi", "olculen", "durum", "zaman"]

# Test noktaları (koordinat + kaynak). Kaynaklar 14 Kasım 2026'da açıldı.
N = {
    "challenger": (11.3733, 142.5917, "GEBCO Gazetteer (Wikipedia 'Challenger Deep' infobox): 11°22.4'N 142°35.5'E"),
    "olu_deniz": (31.5, 35.5, "Wikipedia 'Dead Sea' infobox: 31°30'N 35°30'E"),
    "sahra": (23.0, 13.0, "Wikipedia 'Sahara' infobox: 23°N 13°E"),
    "summit": (72.5795833, -38.4591861, "Wikipedia 'Summit Camp' (UNAVCO GPS, Temmuz 2009): 72.5795833°N 38.4591861°W"),
    "nemo": (-48.876667, -123.393333, "NOAA National Ocean Service (Point Nemo): 48°52.6'S 123°23.6'W"),
    "rub_al_khali": (20.0, 50.0, "Wikipedia 'Rub' al Khali' infobox: 20°N 50°E"),
    "yakutsk": (62.03, 129.73, "Wikipedia 'Yakutsk' infobox: 62.03°N 129.73°E"),
    "kahire": (30.04444, 31.23583, "Wikipedia 'Cairo' infobox: 30.04444°N 31.23583°E"),
    "kuru_vadiler": (-77.467, 162.517, "Wikipedia 'McMurdo Dry Valleys': 77.467°S 162.517°E"),
    "atacama_yungay": (-24.0656, -69.8639, "indirme_raporu3 B4 R-01 (K2, wondermondo): -24.0656, -69.8639"),
    "manaus": (-3.11889, -60.02167, "Wikipedia 'Manaus' infobox: 3.11889°S 60.02167°W"),
}

SATIRLAR, OKUMA, _TUT = [], {}, []      # _TUT: açık GDAL veri setleri (silinirlerse bantları geçersiz olur)


def kaydet(set_, test, nokta, beklenen, kural, bek_kaynak, olculen, durum):
    e, b, k = (N[nokta] if nokta in N else ("", "", ""))
    SATIRLAR.append({"govde": "dunya", "set": set_, "test": test, "nokta": nokta, "enlem": e, "boylam": b,
                     "koordinat_kaynagi": k, "beklenen": beklenen, "tolerans_kurali": kural,
                     "beklenen_kaynagi": bek_kaynak, "olculen": olculen, "durum": durum,
                     "zaman": datetime.now().isoformat(timespec="seconds")})
    print(f"[{durum}] {set_} {test} {nokta}: ölçülen {olculen} | beklenen {beklenen} ({kural})", flush=True)


def dene(set_, test, nokta, beklenen, kural, bek_kaynak, f):
    try:
        olculen, ok = f()
        kaydet(set_, test, nokta, beklenen, kural, bek_kaynak, olculen, ok if isinstance(ok, str) else ("PASS" if ok else "FAIL"))
    except Exception as e:
        kaydet(set_, test, nokta, beklenen, kural, bek_kaynak, f"{type(e).__name__}: {e}", "FAIL")


def cmg_rc(enlem, boylam, adim=0.05):
    # 0,05° küresel CMG ızgarası: sol üst köşe (-180, 90); satır güneye, sütun doğuya artar
    return int(math.floor((90.0 - enlem) / adim)), int(math.floor((boylam + 180.0) / adim))


def main():
    t0 = time.time()
    from osgeo import gdal
    gdal.UseExceptions()
    import rasterio, h5py
    from pyproj import Transformer

    # ------------------------------------------------ E1 ETOPO 2022 (yükseklik, m)
    def etopo(enlem, boylam, pencere=0):
        kuzey = (math.floor(enlem / 15.0) + 1) * 15            # karo adı = üst-sol köşe
        bati = math.floor(boylam / 15.0) * 15
        ad = f"ETOPO_2022_v1_15s_{'N' if kuzey >= 0 else 'S'}{abs(kuzey):02d}{'E' if bati >= 0 else 'W'}{abs(bati):03d}_surface.tif"
        with rasterio.open(VERI / "dunya/E1_etopo" / ad) as d:
            tr = d.transform
            assert abs(tr.c - bati) < 1e-6 and abs(tr.f - kuzey) < 1e-6, f"{ad}: transform köşesi {tr.c},{tr.f} karo adıyla tutmuyor"
            assert abs(tr.a - 15 / 3600) < 1e-12 and abs(tr.e + 15 / 3600) < 1e-12, f"{ad}: piksel {tr.a},{tr.e} != 15 yay-saniye"
            assert d.dtypes[0] == "float32", d.dtypes[0]
            OKUMA.setdefault("E1", {"nodata": d.nodata, "dtype": d.dtypes[0], "piksel_derece": tr.a})
            assert d.nodata == -99999, f"nodata {d.nodata} (belge 10.1: -99999)"
            r, c = d.index(boylam, enlem)
            w = rasterio.windows.Window(max(c - pencere, 0), max(r - pencere, 0), 2 * pencere + 1, 2 * pencere + 1)
            a = d.read(1, window=w).astype(float)
            a[a == d.nodata] = np.nan
            return ad, a
    def t_mariana():
        ad, a = etopo(*N["challenger"][:2], pencere=20)       # ±20 piksel (~±9 km): piksel konumu belirsizliği
        v = float(np.nanmin(a))
        return f"{v:.1f} m (±20 piksel penceresinin en düşüğü, {ad})", -11000 <= v <= -10000
    dene("E1", "Mariana derinligi", "challenger", "yaklasik -10550 m", "[-11000, -10000] m (proje karari)",
         "belge 17.3 D2; piksel ortalaması nedeniyle tam uç değil", t_mariana)
    def t_olu():
        ad, a = etopo(*N["olu_deniz"][:2], pencere=0)
        v = float(a[0, 0])
        return f"{v:.1f} m ({ad})", -450 <= v <= -400
    dene("E1", "Olu Deniz yuzeyi", "olu_deniz", "yaklasik -430 m", "[-450, -400] m (proje karari)",
         "belge 17.3 D2; Wikipedia 'Dead Sea' yüzey -430,5 m (2016)", t_olu)

    # ------------------------------------------------ E2 MCD12C1 Land_Cover_Type_1_Percent
    def alt(yol, ad):
        s = [x[0] for x in gdal.Open(str(yol)).GetSubDatasets() if x[0].endswith(":" + ad) or x[0].endswith(ad)]
        assert len(s) >= 1, f"{ad} alt veri seti yok"
        ds = gdal.Open(s[0])
        _TUT.append(ds)                      # referans tutulur
        return ds
    lc = alt(VERI / "dunya/E2_mcd12c1/MCD12C1.A2023001.061.2024251212901.hdf", "Land_Cover_Type_1_Percent")
    md = lc.GetMetadata()
    OKUMA["E2"] = {"boyut": [lc.RasterXSize, lc.RasterYSize, lc.RasterCount], "geotransform": lc.GetGeoTransform(),
                   "metadata": {k: md[k] for k in md if k in ("_FillValue", "valid_range", "units", "scale_factor")}}
    assert (lc.RasterXSize, lc.RasterYSize, lc.RasterCount) == (7200, 3600, 17), f"E2 boyut {OKUMA['E2']['boyut']}"
    def sinif(nokta):
        r, c = cmg_rc(*N[nokta][:2])
        return [int(lc.GetRasterBand(k + 1).ReadAsArray(c, r, 1, 1)[0, 0]) for k in range(17)]   # bant k+1 = sınıf k
    for nokta, k, ad in [("sahra", 16, "ciplak"), ("summit", 15, "kar/buz"), ("nemo", 0, "su")]:
        dene("E2", f"sinif {k} ({ad}) payi", nokta, "%100", ">= %95 ve 17 sinif toplami 100 (proje karari)",
             "belge 17.3 D2 (ürün tanımı)",
             lambda nokta=nokta, k=k: ((lambda v: (f"sinif{k}=%{v[k]}, toplam {sum(v)}", v[k] >= 95 and sum(v) == 100))(sinif(nokta))))

    # ------------------------------------------------ E4 ASTER GED (yayınım + NDVI), talimat 7
    e4 = sorted((VERI / "dunya/E4_aster_ged").glob("ASTER_GEDv4.1_A2015*.h5"))
    assert len(e4) == 12
    with h5py.File(e4[0], "r") as f:
        em, nd = f["SDS/Emissivity"], f["SDS/NDVI"]
        em_att = {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in em.attrs.items()}
        nd_att = {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in nd.attrs.items()}
        em_sekil, nd_sekil = em.shape, nd.shape
    def att(d, ad):
        for k, v in d.items():
            if k.strip().lower() == ad.lower():
                return float(np.ravel(v)[0]) if not isinstance(v, (bytes, str)) else float(v)
        return None
    olcek, ofset, ndvi_olcek = att(em_att, "Scale Factor"), att(em_att, "Offset"), att(nd_att, "Scale Factor")
    ofset_kaynak = "dosya özniteliği" if ofset is not None else "ofset dosyada yok, kaynak belge 10.1 / Hulley 2015"
    if ofset is None:
        ofset = 0.49
    OKUMA["E4"] = {"emissivity_sekil": em_sekil, "ndvi_sekil": nd_sekil, "emissivity_oznitelik": em_att,
                   "ndvi_oznitelik": nd_att, "scale": olcek, "offset": ofset, "offset_kaynagi": ofset_kaynak,
                   "ndvi_scale": ndvi_olcek}
    bant_ekseni = [i for i, s in enumerate(em_sekil) if s == 5]
    dene("E4", "olcek/ofset dosyadan", "", "Scale 0,002; Offset 0,49; NDVI Scale 0,001",
         "esitlik (talimat 7: Offset dosyada yoksa belge 10.1)", "rapor E4; belge 10.1",
         lambda: (f"Scale {olcek}, Offset {ofset} ({ofset_kaynak}), NDVI Scale {ndvi_olcek}, sekil {em_sekil}",
                  olcek == 0.002 and abs(ofset - 0.49) < 1e-9 and ndvi_olcek == 0.001 and len(bant_ekseni) == 1))
    def em_oku(f):
        a = f["SDS/Emissivity"][...]
        return np.moveaxis(a, bant_ekseni[0], 0)                # (5, satır, sütun); 0 = bant 10 ... 4 = bant 14
    def t_aralik():
        mn, mx = 255, 0
        for p in e4:
            with h5py.File(p, "r") as f:
                a = em_oku(f)
            v = a[a > 0]                                       # 0 = yok (rapor E4)
            mn, mx = min(mn, int(v.min())), max(mx, int(v.max()))
        emn, emx = mn * olcek + ofset, mx * olcek + ofset
        if emn >= 0.61 - 1e-9 and emx <= 1.0 + 1e-9:
            d = "PASS"
        elif emn > 0.51 + 1e-9:
            d = "UYARI"
        else:
            d = "FAIL"
        return f"en kucuk {emn:.3f} (DN {mn}), en buyuk {emx:.3f} (DN {mx}), 12 ay", d
    dene("E4", "gecerli yayinim araligi", "", "0,61-1,00",
         "min >= 0,61 PASS; 0,52-0,61 UYARI (kayda yazilir, is surer); <= 0,51 FAIL (talimat 7)",
         "v1.0 indirmesinde ölçülen en küçük değer 0,612; Hulley ve Hook 2009 (HyspIRI Workshop) kum tepesi "
         "sahalarındaki 0,6–0,96 aralığıyla tutarlı", t_aralik)
    def t_kuvars():
        r, c = cmg_rc(*N["rub_al_khali"][:2])
        top, say = np.zeros(5), np.zeros(5)
        for p in e4:
            with h5py.File(p, "r") as f:
                a = em_oku(f)[:, r, c].astype(float)
            ok = a > 0
            top[ok] += a[ok] * olcek + ofset
            say[ok] += 1
        m = top / np.where(say > 0, say, np.nan)
        return (f"yillik ort. bant10..14 = {np.round(m, 3).tolist()} (gecerli ay {say.astype(int).tolist()})",
                bool(np.nanmax(m[:3]) < np.nanmin(m[3:])))
    dene("E4", "kuvars cukuru", "rub_al_khali", "bant 10-12 < bant 13-14",
         "bantlar 10-12'nin en buyugu < bantlar 13-14'un en kucugu (yillik ortalama)",
         "belge 17.3 D2; Hulley ve ark. 2015", t_kuvars)

    # ------------------------------------------------ E5 MYD11C3 (LST)
    e5 = sorted((VERI / "dunya/E5_myd11c3").glob("MYD11C3.A2023*.hdf"))
    gun = alt(e5[0], "LST_Day_CMG")
    m5 = gun.GetMetadata()
    OKUMA["E5"] = {"boyut": [gun.RasterXSize, gun.RasterYSize], "metadata": {k: m5[k] for k in m5 if k in ("scale_factor", "_FillValue", "valid_range", "units")}}
    dene("E5", "olcek/veri-yok dosyadan", "", "scale 0,02; fill 0", "esitlik", "rapor E5",
         lambda: (str(OKUMA["E5"]), float(m5.get("scale_factor", "nan")) == 0.02 and int(float(m5.get("_FillValue", "-1"))) == 0
                  and (gun.RasterXSize, gun.RasterYSize) == (7200, 3600)))
    def t_okyanus():
        r, c = cmg_rc(*N["nemo"][:2])
        v = []
        for p in e5:
            for ad in ("LST_Day_CMG", "LST_Night_CMG"):
                v.append(int(alt(p, ad).GetRasterBand(1).ReadAsArray(c, r, 1, 1)[0, 0]))
        return f"24 deger (12 ay x gece/gunduz): {sorted(set(v))}", all(x == 0 for x in v)
    dene("E5", "acik okyanus veri yok", "nemo", "veri yok (fill 0)", "24 degerin hepsi 0", "belge 17.3 D2 (kara ürünü)", t_okyanus)

    # ------------------------------------------------ E6 MCD43C3 (albedo)
    e6 = sorted((VERI / "dunya/E6_mcd43c3").glob("MCD43C3.A2023*.hdf"))
    alb = alt(e6[0], "Albedo_WSA_shortwave")
    m6 = alb.GetMetadata()
    OKUMA["E6"] = {"boyut": [alb.RasterXSize, alb.RasterYSize], "metadata": {k: m6[k] for k in m6 if k in ("scale_factor", "_FillValue", "valid_range", "units")}}
    dene("E6", "olcek/veri-yok dosyadan", "", "scale 0,001; fill 32767", "esitlik", "rapor E6",
         lambda: (str(OKUMA["E6"]), float(m6.get("scale_factor", "nan")) == 0.001 and int(float(m6.get("_FillValue", "-1"))) == 32767
                  and (alb.RasterXSize, alb.RasterYSize) == (7200, 3600)))
    def alb_ort(nokta):
        r, c = cmg_rc(*N[nokta][:2])
        v = [int(alt(p, "Albedo_WSA_shortwave").GetRasterBand(1).ReadAsArray(c, r, 1, 1)[0, 0]) for p in e6]
        g = [x * 0.001 for x in v if 0 <= x <= 32766]
        return (float(np.mean(g)) if g else float("nan")), len(g)
    def t_albedo():
        gs, ng = alb_ort("summit")
        sh, ns = alb_ort("sahra")
        mx = 0
        for p in e6:
            a = alt(p, "Albedo_WSA_shortwave").GetRasterBand(1).ReadAsArray()
            v = a[(a >= 0) & (a <= 32766)]
            mx = max(mx, int(v.max()))
        return (f"Gronland {gs:.3f} ({ng} ay), Sahra {sh:.3f} ({ns} ay), kuresel en buyuk {mx * 0.001:.3f}",
                gs > 0.6 and 0.2 <= sh <= 0.5 and gs > sh and mx * 0.001 <= 1.0)
    dene("E6", "Gronland yuksek / Sahra orta; 0-1", "summit", "yuksek / orta; 0-1 araligi",
         "Gronland > 0,6; Sahra 0,2-0,5; kuresel en buyuk <= 1,0 (proje karari)", "belge 17.3 D2 (ürün tanımı)", t_albedo)

    # ------------------------------------------------ E7, E8 PERPROB
    def perprob(yol, nokta, pencere):
        with rasterio.open(yol) as d:
            tr = Transformer.from_crs("EPSG:4326", d.crs, always_xy=True)
            x, y = tr.transform(N[nokta][1], N[nokta][0])
            r, c = d.index(x, y)
            w = rasterio.windows.Window(c - pencere, r - pencere, 2 * pencere + 1, 2 * pencere + 1)
            a = d.read(1, window=w, boundless=True, fill_value=np.nan).astype(float)
            if d.nodata is not None:
                a[a == d.nodata] = np.nan
            OKUMA.setdefault(yol.parent.parent.name, {"crs": str(d.crs), "nodata": d.nodata, "piksel": d.res, "dtype": d.dtypes[0]})
            return a
    nh = VERI / "dunya/E7_permafrost_kuzey/acik/UiO_PEX_PERPROB_5.0_20181128_2000_2016_NH.tif"
    an = VERI / "dunya/E8_permafrost_antarktika/acik/UiO_PEX_PERPROB_5.0_20181205_2000_2017_ANT.tif"
    dene("E7", "Yakutsk", "yakutsk", "yaklasik 1", ">= 0,9 (proje karari)", "Obu ve ark. 2019",
         lambda: ((lambda a: (f"{a[0, 0]}", a[0, 0] >= 0.9))(perprob(nh, "yakutsk", 0))))
    dene("E7", "Kahire", "kahire", "yaklasik 0", "<= 0,1 ya da veri yok (sifir kurali, belge 6.6)", "Obu ve ark. 2019",
         lambda: ((lambda a: (f"{a[0, 0]}", bool(np.isnan(a[0, 0]) or a[0, 0] <= 0.1)))(perprob(nh, "kahire", 0))))
    dene("E8", "Kuru Vadiler", "kuru_vadiler", "yuksek", "+-5 piksel (~+-5 km) penceresinde gecerli degerlerin en buyugu >= 0,9 (proje karari)",
         "Obu ve ark. 2020",
         lambda: ((lambda a: (f"merkez {a[5, 5]}, pencere en buyuk {np.nanmax(a) if np.isfinite(a).any() else 'yok'}",
                              bool(np.isfinite(a).any() and np.nanmax(a) >= 0.9)))(perprob(an, "kuru_vadiler", 5))))

    # ------------------------------------------------ E9 Aridity (× 10 000, belge D9)
    ai_yol = VERI / "dunya/E9_aridity/acik/Global-AI_ET0__annual_v3_1/ai_v31_yr.tif"
    with rasterio.open(ai_yol) as d:
        ds9 = gdal.Open(str(ai_yol))
        _TUT.append(ds9)
        bant = ds9.GetRasterBand(1)
        OKUMA["E9"] = {"dtype": d.dtypes[0], "nodata": d.nodata, "crs": str(d.crs), "piksel": d.res,
                       "gdal_scale": bant.GetScale(), "gdal_offset": bant.GetOffset()}
        def ai(nokta):
            r, c = d.index(N[nokta][1], N[nokta][0])
            return int(d.read(1, window=rasterio.windows.Window(c, r, 1, 1))[0, 0])
        at, am = ai("atacama_yungay"), ai("manaus")
    dene("E9", "carpan x 10000 (K9)", "", "AI = ham / 10000",
         "dosyada baska olcek yok ve Atacama ham < 300, Amazon ham > 6500 (sinif sinirlari x 10000 ile tutarli)",
         "rapor E9 (figshare açıklaması); belge D9, K9",
         lambda: (f"GDAL scale {OKUMA['E9']['gdal_scale']}, offset {OKUMA['E9']['gdal_offset']}, nodata {OKUMA['E9']['nodata']}; "
                  f"Atacama ham {at}, Manaus ham {am}",
                  (OKUMA["E9"]["gdal_scale"] in (None, 1.0)) and at < 300 and am > 6500))
    dene("E9", "Atacama", "atacama_yungay", "< 0,03", "ham/10000 < 0,03", "Zomer ve ark. 2022 sınıfları",
         lambda: (f"{at / 10000:.4f}", at / 10000 < 0.03))
    dene("E9", "Amazon", "manaus", "> 0,65", "ham/10000 > 0,65", "Zomer ve ark. 2022 sınıfları",
         lambda: (f"{am / 10000:.4f}", am / 10000 > 0.65))

    # ------------------------------------------------ E10 SoilGrids silt + kil
    def t_soil():
        cy = VERI / "dunya/E10_soilgrids/clay/clay_0-5cm_mean_1000.tif"
        sy = VERI / "dunya/E10_soilgrids/silt/silt_0-5cm_mean_1000.tif"
        mn, mx = 10 ** 9, -10 ** 9
        with rasterio.open(cy) as dc, rasterio.open(sy) as ds:
            assert (dc.width, dc.height, dc.transform) == (ds.width, ds.height, ds.transform)
            OKUMA["E10"] = {"crs": str(dc.crs), "nodata_clay": dc.nodata, "nodata_silt": ds.nodata, "dtype": dc.dtypes[0],
                            "piksel": dc.res, "bounds": tuple(dc.bounds)}
            for r0 in range(0, dc.height, 1024):
                w = rasterio.windows.Window(0, r0, dc.width, min(1024, dc.height - r0))
                a, b = dc.read(1, window=w).astype(np.int32), ds.read(1, window=w).astype(np.int32)
                ok = (a != dc.nodata) & (b != ds.nodata)
                if ok.any():
                    t = a[ok] + b[ok]
                    mn, mx = min(mn, int(t.min())), max(mx, int(t.max()))
            tr = Transformer.from_crs("EPSG:4326", dc.crs, always_xy=True)
            x, y = tr.transform(N["kuru_vadiler"][1], N["kuru_vadiler"][0])
            b = dc.bounds
            disari = not (b.left <= x <= b.right and b.bottom <= y <= b.top)
            if disari:
                ant = "raster disinda"
            else:
                r, c = dc.index(x, y)
                ant = int(dc.read(1, window=rasterio.windows.Window(c, r, 1, 1))[0, 0])
                disari = ant == dc.nodata
        return f"silt+kil en kucuk {mn}, en buyuk {mx} (‰); Antarktika noktasi: {ant}", (0 <= mn and mx <= 1000 and disari)
    dene("E10", "silt+kil araligi; Antarktika veri yok", "kuru_vadiler", "0-1000 ‰; Antarktika veri yok",
         "gecerli piksellerde 0 <= silt+kil <= 1000 ve Antarktika noktasi veri yok ya da raster disi", "ISRIC", t_soil)

    # ------------------------------------------------ kayıt
    eski = []
    if D2CSV.exists():
        with open(D2CSV, encoding="utf-8", newline="") as f:
            eski = [r for r in csv.DictReader(f) if r["govde"] != "dunya"]
    with open(D2CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ALANLAR)
        w.writeheader()
        w.writerows(eski + SATIRLAR)
    (KAYIT / "D2_okuma_dunya.json").write_text(json.dumps(OKUMA, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    say = {}
    for s in SATIRLAR:
        say[s["durum"]] = say.get(s["durum"], 0) + 1
    with open(KAYIT / "13_kasim_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  D2 dunya: {say}, {round((time.time() - t0) / 60, 1)} dk\n")
    print("=" * 60)
    print(f"D2 Dünya: {say} | {round((time.time() - t0) / 60, 1)} dk | kayit/D2.csv, kayit/D2_okuma_dunya.json")
    return say
