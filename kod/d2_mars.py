# Developed with assistance from Claude (Anthropic).
# d2_mars.py — Orbitrary v1.2, belge 17.3 D2 (gerçek-yer testleri), Mars setleri R1–R7.
# Sonuçlar kayit/D2.csv'ye (govde = mars), okuma ayrıntıları kayit/D2_okuma_mars.json'a yazılır.
import csv, json, math, re, time
from datetime import datetime
from pathlib import Path

import numpy as np

KOK = Path.home() / "orbitrary"
VERI, KAYIT = KOK / "veri", KOK / "kayit"
M = VERI / "mars"
D2CSV = KAYIT / "D2.csv"
ALANLAR = ["govde", "set", "test", "nokta", "enlem", "boylam", "koordinat_kaynagi", "beklenen",
           "tolerans_kurali", "beklenen_kaynagi", "olculen", "durum", "zaman"]
R_MARS = 3396190.0          # m; SIM3292_README.txt: "GCS_Mars_2000_Sphere, 3396190.0 radius"

N = {
    "jezero": (18.44, 77.45, "belge 17.3 D2 (Jezero merkezi)"),
    "opportunity": (-1.9462, 354.4734 - 360.0,
                    "PDS Geosciences mer_mission.txt: 1.9462 S, 354.4734 E (MOLA IAU 2000); Meridiani hematit bölgesi"),
}
SATIRLAR, OKUMA = [], {}


def kaydet(set_, test, nokta, beklenen, kural, bek_kaynak, olculen, durum):
    e, b, k = (N[nokta] if nokta in N else ("", "", ""))
    SATIRLAR.append({"govde": "mars", "set": set_, "test": test, "nokta": nokta, "enlem": e, "boylam": b,
                     "koordinat_kaynagi": k, "beklenen": beklenen, "tolerans_kurali": kural,
                     "beklenen_kaynagi": bek_kaynak, "olculen": olculen, "durum": durum,
                     "zaman": datetime.now().isoformat(timespec="seconds")})
    print(f"[{durum}] {set_} {test} {nokta}: ölçülen {olculen} | beklenen {beklenen} ({kural})", flush=True)


def dene(set_, test, nokta, beklenen, kural, bek_kaynak, f):
    try:
        olculen, ok = f()
        kaydet(set_, test, nokta, beklenen, kural, bek_kaynak, olculen, "PASS" if ok else "FAIL")
    except Exception as e:
        kaydet(set_, test, nokta, beklenen, kural, bek_kaynak, f"{type(e).__name__}: {e}", "FAIL")


def bolum(ad, f):
    try:
        f()
    except Exception as e:
        kaydet(ad, "bolum calisamadi", "", "", "", "", f"{type(e).__name__}: {e}", "FAIL")


def gc_km(f1, l1, f2, l2):
    f1, l1, f2, l2 = map(np.radians, (f1, l1, f2, l2))
    a = np.sin((f2 - f1) / 2) ** 2 + np.cos(f1) * np.cos(f2) * np.sin((l2 - l1) / 2) ** 2
    return 2 * R_MARS / 1000 * np.arcsin(np.sqrt(a))


def pds(t, *anahtarlar):
    # PDS3 / ISIS etiketinde "ANAHTAR = deger <birim>" satırının değeri
    for a in anahtarlar:
        m = re.search(r"(?im)^\s*" + re.escape(a) + r"\s*=\s*\"?([^\"\r\n<]*?)\"?\s*(<[^>]*>)?\s*$", t)
        if m:
            return m.group(1).strip()
    return None


def sayi(s):
    return float(re.match(r"\s*([-+]?[\d.]+(?:[Ee][-+]?\d+)?)", s).group(1))


def kor(a, b):
    from scipy.stats import spearmanr
    return float(np.corrcoef(a, b)[0, 1]), float(spearmanr(a, b).correlation)


def albedo_oku():
    # TES albedo 8 ppd: etiketten okunur (PC_REAL = little-endian float32, kuzey üstte, -180'den doğuya)
    lbl = (M / "R4_tes_ti_albedo/global_albedo_8ppd.lbl").read_text(encoding="ascii", errors="replace")
    sat, sut = int(sayi(pds(lbl, "LINES"))), int(sayi(pds(lbl, "LINE_SAMPLES")))
    tip, bit = pds(lbl, "SAMPLE_TYPE"), int(sayi(pds(lbl, "SAMPLE_BITS")))
    maxlat, bati = sayi(pds(lbl, "MAXIMUM_LATITUDE")), sayi(pds(lbl, "WESTERNMOST_LONGITUDE"))
    yon, cozun = pds(lbl, "POSITIVE_LONGITUDE_DIRECTION"), sayi(pds(lbl, "MAP_RESOLUTION"))
    OKUMA["R4_albedo"] = {"satir": sat, "sutun": sut, "tip": tip, "bit": bit, "maxlat": maxlat, "bati": bati,
                          "yon": yon, "ppd": cozun}
    assert (sat, sut, tip, bit, maxlat, bati, yon, cozun) == (1440, 2880, "PC_REAL", 32, 90.0, -180.0, "EAST", 8.0), OKUMA["R4_albedo"]
    p = M / "R4_tes_ti_albedo/global_albedo_8ppd.img"
    assert p.stat().st_size == sat * sut * 4
    a = np.fromfile(p, dtype="<f4").reshape(sat, sut).astype(float)
    OKUMA["R4_albedo"]["sonlu_olmayan"] = int((~np.isfinite(a)).sum())
    OKUMA["R4_albedo"]["sifir_ve_alti"] = int((a <= 0).sum())
    a[~np.isfinite(a) | (a <= 0)] = np.nan          # proje kararı: albedo > 0 geçerli (etikette veri-yok değeri yok)
    lat = 90 - (np.arange(sat) + 0.5) / 8
    lon = -180 + (np.arange(sut) + 0.5) / 8
    return a, lat, lon


def main():
    t0 = time.time()
    import rasterio

    # ------------------------------------------------ R1 MOLA (int16 m; transform kullanılmaz)
    def r1():
        p = M / "R1_mola/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif"
        with rasterio.open(p) as d:
            OKUMA["R1"] = {"boyut": [d.width, d.height], "dtype": d.dtypes[0], "nodata": d.nodata,
                           "olcek": d.scales[0], "ofset": d.offsets[0], "crs": str(d.crs), "transform": list(d.transform)[:6]}
            assert (d.width, d.height, d.dtypes[0]) == (46080, 23040, "int16"), OKUMA["R1"]
            assert d.scales[0] == 1.0 and d.offsets[0] == 0.0, f"dosyada ölçek/ofset var: {d.scales[0]}, {d.offsets[0]}"
            nd = d.nodata

            def t_uc():
                mn, mx, rmn, rmx, n_yok = 10 ** 9, -10 ** 9, None, None, 0
                for r0 in range(0, d.height, 512):
                    a = d.read(1, window=rasterio.windows.Window(0, r0, d.width, min(512, d.height - r0)))
                    gec = np.ones(a.shape, bool) if nd is None else (a != nd)
                    n_yok += int((~gec).sum())
                    v = np.where(gec, a, 32767)
                    i = np.unravel_index(np.argmin(v), v.shape)
                    if v[i] < mn:
                        mn, rmn = int(v[i]), (r0 + i[0], i[1])
                    v = np.where(gec, a, -32768)
                    i = np.unravel_index(np.argmax(v), v.shape)
                    if v[i] > mx:
                        mx, rmx = int(v[i]), (r0 + i[0], i[1])
                yer = lambda rc: (round(90 - (rc[0] + 0.5) / 128, 2), round((rc[1] + 0.5) / 128 - 180, 2))
                OKUMA["R1"].update({"min": mn, "min_yeri": yer(rmn), "max": mx, "max_yeri": yer(rmx), "nodata_sayisi": n_yok})
                return f"en kucuk {mn} m {yer(rmn)}, en buyuk {mx} m {yer(rmx)}; veri-yok {n_yok}", \
                    abs(mn + 8200) <= 100 and 21129 <= mx <= 21400
            dene("R1", "kuresel min / max", "", "yaklasik -8200 (Hellas) / 21229-21300 m (Olympus)",
                 "min -8200 +-100; max 21129-21400 (21229-21300 +-100; proje karari)", "belge 17.3 D2 (PGDA MOLA katalogu)", t_uc)

            def t_jez():
                e, b = N["jezero"][:2]
                r, c = int(math.floor((90 - e) * 128)), int(math.floor((b + 180) * 128))
                v = int(d.read(1, window=rasterio.windows.Window(c, r, 1, 1))[0, 0])
                return f"{v} m (satir {r}, sutun {c})", abs(v + 2570) <= 100
            dene("R1", "Jezero yuksekligi", "jezero", "yaklasik -2570 m", "+-100 m (proje karari; 463 m piksel)",
                 "belge 17.3 D2 (PDS MEGDR çapraz ürün)", t_jez)

    bolum("R1", r1)

    # ------------------------------------------------ R2 SIM 3292: alan toplamı
    def r2():
        import pyogrio
        shp = M / "R2_sim3292/acik/SIM3292_MarsGlobalGeologicGIS_20M/SIM3292_Shapefiles/SIM3292_Global_Geology.shp"
        df = pyogrio.read_dataframe(shp, read_geometry=False)
        OKUMA["R2"] = {"kayit": len(df), "alanlar": list(df.columns), "birim_sayisi": int(df["Unit"].nunique())}

        def t_alan():
            oran = float(df["SphArea_km"].sum()) / (4 * math.pi * (R_MARS / 1000) ** 2)
            return f"{len(df)} kayit, {df['Unit'].nunique()} birim, alan / 4πR² = {oran:.6f}", \
                len(df) == 1311 and df["Unit"].nunique() == 44 and abs(oran - 1) <= 1e-4
        dene("R2", "alan toplami", "", "4πR² (R = 3396,19 km); 1311 kayit, 44 birim", "+-%0,01",
             "belge 17.3 D2; R: SIM3292_README.txt", t_alan)

    bolum("R2", r2)

    # ------------------------------------------------ R3 TES mineral
    def qube(etk):
        # PDS3 QUBE etiketi (TES .isis ve DCI .pds): eksenler, tip, veri başlangıcı, taban/çarpan
        ci = tuple(int(x) for x in re.search(r"CORE_ITEMS\s*=\s*\(([^)]*)\)", etk).group(1).split(","))
        eksen = re.search(r"AXES_NAME\s*=\s*\(([^)]*)\)", etk).group(1).replace(" ", "")
        return {"core_items": ci, "eksenler": eksen, "tip": pds(etk, "CORE_ITEM_TYPE"),
                "bayt": int(sayi(pds(etk, "CORE_ITEM_BYTES"))),
                "veri_baslangici": (int(sayi(pds(etk, "^QUBE"))) - 1) * int(sayi(pds(etk, "RECORD_BYTES"))),
                "taban": sayi(pds(etk, "CORE_BASE")), "carpan": sayi(pds(etk, "CORE_MULTIPLIER"))}

    def r3():
        hdr = (M / "R3_tes_mineral/TES_mineral_maps_4_ppd.envi.hdr").read_text(encoding="ascii", errors="replace")
        h = {k: int(sayi(pds(hdr, k))) for k in ("samples", "lines", "bands", "header offset", "data type", "byte order")}
        OKUMA["R3_hdr"] = h
        assert h == {"samples": 1440, "lines": 720, "bands": 13, "header offset": 0, "data type": 4, "byte order": 1}, h
        p = M / "R3_tes_mineral/TES_mineral_maps_4_ppd.envi"
        assert p.stat().st_size == 1440 * 720 * 13 * 4
        a = np.fromfile(p, dtype=">f4").reshape(13, 720, 1440)
        # aynı verinin .isis kopyası kendi etiketiyle okunur: iki dosya aynı sayıları vermeli (bayt sırası çapraz kontrolü)
        pi = M / "R3_tes_mineral/TES_mineral_maps_4_ppd.isis"
        etk = pi.open("rb").read(1024).decode("ascii", errors="replace")
        q = qube(etk)
        OKUMA["R3_isis_etiket"], OKUMA["R3_isis"] = etk.strip(), q
        assert (q["core_items"], q["eksenler"], q["tip"], q["bayt"], q["veri_baslangici"], q["taban"], q["carpan"]) == \
            ((1440, 720, 13), "SAMPLE,LINE,BAND", "PC_REAL", 4, 1024, 0.0, 1.0), q
        assert pi.stat().st_size == 1024 + 1440 * 720 * 13 * 4
        b = np.fromfile(pi, dtype="<f4", offset=1024).reshape(13, 720, 1440)
        dene("R3", "envi (>f4) ile isis (<f4) ayni veri", "", "fark 0", "butun degerler esit",
             "iki dosyanın kendi etiketleri (.envi.hdr byte order 1; .isis PC_REAL)",
             lambda: (f"{int(np.sum(~((a == b) | (np.isnan(a) & np.isnan(b)))))} farkli deger", bool(np.array_equal(a, b, equal_nan=True))))
        # geometri: .envi.hdr'de de .isis etiketinde de yok -> ASU'nun aynı ürün için verdiği tanım
        g = {"maxlat": 90.0, "bati": -180.0, "dogu": True, "ppd": 1440 / 360,
             "kaynak": "dosyalarda yok; ASU Mars Global Data Sets, TES Low-Calcium Pyroxene (Bandfield 2002, 4 ppd, 1440x720): "
                       "Simple cylindrical, -180E to 180E, 90N to -90N, 'ocentric"}
        OKUMA["R3_geometri"] = g

        def lonlat(r, c):
            lat = g["maxlat"] - (r + 0.5) / g["ppd"]
            lon = g["bati"] + (c + 0.5) / g["ppd"]
            return lat, (lon + 180) % 360 - 180

        def t_hem():
            b8 = a[7].astype(float)
            OKUMA["R3_bant8_-1_sayisi"] = int((b8 == -1).sum())
            b8[(b8 == -1) | ~np.isfinite(b8)] = np.nan
            lat_sat = g["maxlat"] - (np.arange(720) + 0.5) / 4
            b8[np.abs(lat_sat) > 30, :] = np.nan
            r, c = np.unravel_index(np.nanargmax(b8), b8.shape)
            e, b = lonlat(r, c)
            u = float(gc_km(e, b, *N["opportunity"][:2]))
            return f"bant 8 en buyuk {b8[r, c]:.3f} @ ({e:.2f}, {b:.2f}); Opportunity'ye {u:.0f} km", u <= 500
        dene("R3", "bant 8 (hematit) ekvator maksimumu", "opportunity", "Sinus Meridiani",
             "|enlem| <= 30° içindeki en buyuk deger Opportunity inis noktasina <= 500 km (proje karari)",
             "belge 17.3 D2; Bandfield 2002", t_hem)

        kaydet("R3", "bant 3/5/6 sirasi (acik kontrol)", "", "3 plajiyoklaz, 5 dusuk-Ca piroksen, 6 yuksek-Ca piroksen",
               "belge D11 ile urun sayfasi listesi ayni", "indirme_raporu3 R3 (ASU sayfası, 13 Kasım 17:40; Bandfield 2002)",
               "sayfadaki 13 bilesen sirasi belgeyle ayni (veri testi degil, belge karsilastirmasi)", "PASS")

    bolum("R3", r3)

    # ------------------------------------------------ R4 TI <-> albedo
    alb = {}

    def r4():
        p = M / "R4_tes_ti_albedo/ti_nmap2003.bin"
        bas = p.open("rb").read(7200).decode("ascii", errors="replace")
        OKUMA["R4_ti_baslik"] = bas.strip()[:1500]
        assert "west" in bas.lower() and "-90" in bas, "TI başlığında 'West' / '-90' yok"
        assert p.stat().st_size == 7200 + 7200 * 3600 * 2
        ti = np.fromfile(p, dtype=">i2", offset=7200).reshape(3600, 7200)
        gec = ti != 0
        OKUMA["R4_ti"] = {"veri_yok_0": int((~gec).sum()), "min": int(ti[gec].min()), "max": int(ti[gec].max())}
        dene("R4", "TI aralik (big-endian dogrulama)", "", "24-800", "gecerli degerler 24-800 icinde",
             "TI dosya başlığı (indirme_raporu3 R4)",
             lambda: (f"min {OKUMA['R4_ti']['min']}, max {OKUMA['R4_ti']['max']}, veri-yok {OKUMA['R4_ti']['veri_yok_0']}",
                      OKUMA['R4_ti']['min'] >= 24 and OKUMA['R4_ti']['max'] <= 800))
        a, lat, lon = albedo_oku()
        alb.update(a=a, lat=lat, lon=lon)

        def t_kor():
            LA, LO = np.meshgrid(lat, lon, indexing="ij")
            r = np.floor((LA + 90) * 20).astype(int)               # ilk satır güney (-90)
            c = np.floor(((-LO) % 360) * 20).astype(int) % 7200    # boylam batıya 0-360
            t = ti[r, c].astype(float)
            s = (np.abs(LA) <= 60) & np.isfinite(a) & (t != 0)
            pe, sp = kor(a[s], t[s])
            return f"Pearson {pe:.3f}, Spearman {sp:.3f} ({int(s.sum())} piksel)", pe < 0 and sp < 0
        dene("R4", "TI-albedo korelasyonu", "", "negatif (tozlu = parlak = dusuk TI)",
             "|enlem| <= 60° (proje karari: kutup buzu disarida), Pearson ve Spearman < 0", "Putzig ve ark. 2005", t_kor)

    bolum("R4", r4)

    # ------------------------------------------------ R5 DCI <-> albedo
    def r5():
        p = M / "R5_tes_dci/dci_lo_ice_dust_16ppd_shifted.pds"
        etk = p.open("rb").read(1024).decode("ascii", errors="replace")
        q = qube(etk)
        g = {"maxlat": 90.0, "bati": -180.0,
             "kaynak": "etikette yok; indirme_raporu3 R5 (ikincil kayıt mars.asu.edu/data/tes_ruffdust: simple cylindrical, -180->180 doğu, 90->-90)"}
        OKUMA["R5_etiket"], OKUMA["R5"] = etk.strip(), {**q, **g}
        assert (q["core_items"], q["eksenler"], q["tip"], q["bayt"], q["veri_baslangici"], q["taban"], q["carpan"]) == \
            ((1, 5760, 2880), "BAND,SAMPLE,LINE", "PC_REAL", 4, 1024, 0.0, 1.0), q
        assert p.stat().st_size == 1024 + 5760 * 2880 * 4
        d = np.fromfile(p, dtype="<f4", offset=1024).reshape(2880, 5760).astype(float)
        yok = d == np.float32(0.85)
        OKUMA["R5"]["0.85_sayisi"] = int(yok.sum())
        d[yok | ~np.isfinite(d)] = np.nan
        if not alb:
            alb.update(zip(("a", "lat", "lon"), albedo_oku()))

        def t_kor():
            LA, LO = np.meshgrid(alb["lat"], alb["lon"], indexing="ij")
            r = np.floor((g["maxlat"] - LA) * 16).astype(int)
            c = np.floor(((LO - g["bati"]) % 360) * 16).astype(int) % 5760
            v = d[r, c]
            s = (np.abs(LA) <= 60) & np.isfinite(alb["a"]) & np.isfinite(v)
            pe, sp = kor(alb["a"][s], v[s])
            return f"Pearson {pe:.3f}, Spearman {sp:.3f} ({int(s.sum())} piksel); 0,85 sayisi {int(yok.sum())}", pe < 0 and sp < 0
        dene("R5", "DCI-albedo korelasyonu", "", "negatif", "|enlem| <= 60° (R4 ile ayni), Pearson ve Spearman < 0",
             "Ruff & Christensen 2002", t_kor)

    bolum("R5", r5)

    # ------------------------------------------------ R6 Odyssey GRS H2O (PDS4 alan konumlarıyla)
    def r6():
        xml = (M / "R6_odyssey_grs/pds4_etiket/h2o_sr_5x5.xml").read_text(encoding="utf-8", errors="replace")
        rl = int(re.search(r"<record_length[^>]*>(\d+)<", xml).group(1))
        nrec = int(re.search(r"<records>(\d+)<", xml).group(1))
        alan = []
        for blok in re.findall(r"<Field_Character>(.*?)</Field_Character>", xml, re.S):
            alan.append((re.search(r"<name>(.*?)</name>", blok).group(1).strip(),
                         int(re.search(r"<field_location[^>]*>(\d+)<", blok).group(1)),
                         int(re.search(r"<field_length[^>]*>(\d+)<", blok).group(1))))
        OKUMA["R6"] = {"record_length": rl, "records": nrec, "alanlar": alan}
        ham = (M / "R6_odyssey_grs/h2o_sr_5x5.tab").read_bytes()
        assert len(ham) == rl * nrec, f"boyut {len(ham)} != {rl} x {nrec}"
        sat = [ham[i * rl:(i + 1) * rl] for i in range(nrec)]
        T = np.array([[float(s[l - 1:l - 1 + n]) for (_, l, n) in alan] for s in sat])
        lat, v = T[:, 0], T[:, 2]

        def t_h2o():
            dis = np.abs(lat) > 57.5
            yok = np.isclose(v, 9999.999)
            return f"{alan[2][0]}: 57,5° disi {int(dis.sum())} hucre, hepsi veri-yok: {bool(yok[dis].all())}; " \
                   f"ici {int((~dis).sum())} hucre, gecerli {int((~yok[~dis]).sum())}", \
                bool(yok[dis].all()) and bool((~yok[~dis]).any())
        dene("R6", "H2O kapsami", "", "yalniz 57,5°G-57,5°K'de deger; disi 9999,999",
             "|enlem| > 57,5 olan butun hucreler 9999,999", "belge 10.3 / rapor R6", t_h2o)

    bolum("R6", r6)

    # ------------------------------------------------ R7 SWIM enlem profili
    def r7():
        from pyproj import CRS, Transformer
        for ad in ("SWIM4MIM_Ci_0_1", "SWIM4MIM_Ci_1_5", "SWIM4MIM_Ci_5"):
            def t_sw(ad=ad):
                with rasterio.open(M / "R7_swim" / f"{ad}.tif") as d:
                    OKUMA[f"R7_{ad}"] = {"boyut": [d.width, d.height], "dtype": d.dtypes[0], "nodata": d.nodata,
                                         "crs": str(d.crs), "transform": list(d.transform)[:6]}
                    assert (d.width, d.height) == (7200, 2400), OKUMA[f"R7_{ad}"]
                    a = d.read(1).astype(float)
                    nd = d.nodata
                    xs, ys = d.transform * (np.full(d.height, d.width / 2), np.arange(d.height) + 0.5)
                    crs = CRS.from_wkt(d.crs.to_wkt())
                    lat = ys if crs.is_geographic else \
                        Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True).transform(xs, ys)[1]
                lat = np.asarray(lat)
                yok = (a == -30) | ~np.isfinite(a) | ((a == nd) if nd is not None else False)
                OKUMA[f"R7_{ad}"].update({"-30_sayisi": int((a == -30).sum()), "enlem_araligi": [float(lat.min()), float(lat.max())]})
                a[yok] = np.nan
                aralik = np.nanmin(a) >= -1 and np.nanmax(a) <= 1
                k = np.nanmean(a[(lat >= 40) & (lat <= 60)])
                q = np.nanmean(a[np.abs(lat) <= 10])
                return f"40-60°K ortalama {k:.3f}, |enlem|<=10° ortalama {q:.3f}; gecerli aralik [{np.nanmin(a):.2f}, {np.nanmax(a):.2f}]", \
                    bool(aralik and k > q)
            dene("R7", f"enlem profili {ad}", "", "kuzey orta-yuksek > ekvator; -1..+1",
                 "40-60°K ortalamasi > |enlem| <= 10° ortalamasi (proje karari); -30 = veri yok", "Morgan ve ark. 2025", t_sw)

    bolum("R7", r7)

    # ------------------------------------------------ kayıt
    eski = []
    if D2CSV.exists():
        with open(D2CSV, encoding="utf-8", newline="") as f:
            eski = [r for r in csv.DictReader(f) if r["govde"] != "mars"]
    with open(D2CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ALANLAR)
        w.writeheader()
        w.writerows(eski + SATIRLAR)
    (KAYIT / "D2_okuma_mars.json").write_text(json.dumps(OKUMA, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    say = {}
    for s in SATIRLAR:
        say[s["durum"]] = say.get(s["durum"], 0) + 1
    with open(KAYIT / "13_kasim_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  D2 mars: {say}, {round((time.time() - t0) / 60, 1)} dk\n")
    print("=" * 60)
    print(f"D2 Mars: {say} | {round((time.time() - t0) / 60, 1)} dk | kayit/D2.csv, kayit/D2_okuma_mars.json")
    return say
