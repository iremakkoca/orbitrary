# Developed with assistance from Claude (Anthropic).
# d2_ay.py — Orbitrary v1.2, belge 17.3 D2 (gerçek-yer testleri), Ay setleri M1–M7 + talimat 6 (PRP ice_depth).
# Sonuçlar kayit/D2.csv'ye (govde = ay), okuma ayrıntıları kayit/D2_okuma_ay.json'a yazılır.
import csv, json, math, re, time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path.home() / "orbitrary"
VERI, KAYIT = KOK / "veri", KOK / "kayit"
D2CSV = KAYIT / "D2.csv"
ALANLAR = ["govde", "set", "test", "nokta", "enlem", "boylam", "koordinat_kaynagi", "beklenen",
           "tolerans_kurali", "beklenen_kaynagi", "olculen", "durum", "zaman"]
R_AY = 1737400.0                                   # m, belge 4.1 (r_B = 1737,4 km)

N = {
    "apollo11": (0.67416, 23.47314, "NSSDCA Apollo Landing Site Coordinates (LRO, Wagner ve ark. 2017): LM 0.67416N 23.47314E"),
    "shackleton": (-89.67, 129.78, "IAU Gazetteer of Planetary Nomenclature, Feature 5450: -89.67, 129.78 (cap 21 km)"),
}
SATIRLAR, OKUMA, _TUT = [], {}, []


def kaydet(set_, test, nokta, beklenen, kural, bek_kaynak, olculen, durum):
    e, b, k = (N[nokta] if nokta in N else ("", "", ""))
    SATIRLAR.append({"govde": "ay", "set": set_, "test": test, "nokta": nokta, "enlem": e, "boylam": b,
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


def gc_km(f1, l1, f2, l2):
    f1, l1, f2, l2 = map(np.radians, (f1, l1, f2, l2))
    a = np.sin((f2 - f1) / 2) ** 2 + np.cos(f1) * np.cos(f2) * np.sin((l2 - l1) / 2) ** 2
    return 2 * R_AY / 1000 * np.arcsin(np.sqrt(a))


def lbl_sutunlar(lbl):
    # PDS3 etiketindeki COLUMN nesnelerinin NAME alanları, sırasıyla
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
    return df, baslik


def main():
    t0 = time.time()
    from osgeo import gdal
    gdal.UseExceptions()
    import rasterio

    def bolum(ad, f):
        try:
            f()
        except Exception as e:
            kaydet(ad, "bolum calisamadi", "", "", "", "", f"{type(e).__name__}: {e}", "FAIL")

    # ------------------------------------------------ M1 LOLA (int16 x 0,5 m)
    def m1():
        lola = VERI / "ay/M1_lola/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif"
        lbl = (VERI / "ay/M1_lola/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.lbl").read_text(encoding="ascii", errors="replace")
        m_c, m_b = re.search(r"Multiplier\s*=\s*([-\d.Ee+]+)", lbl), re.search(r"Base\s*=\s*([-\d.Ee+]+)", lbl)
        carpan = float(m_c.group(1)) if m_c else None
        taban = float(m_b.group(1)) if m_b else None
        with rasterio.open(lola) as d:
            tr = d.transform
            OKUMA["M1"] = {"boyut": [d.width, d.height], "dtype": d.dtypes[0], "nodata": d.nodata, "transform": list(tr)[:6],
                           "lbl_multiplier": carpan, "lbl_base": taban}
            assert (d.width, d.height, d.dtypes[0]) == (92160, 46080, "int16"), OKUMA["M1"]
            assert carpan == 0.5 and taban == 0.0, f"etiket Multiplier {carpan}, Base {taban} (belge: x 0,5)"
            piksel = 2 * math.pi * R_AY / 92160
            assert abs(tr.a - piksel) < 0.01 and abs(tr.c + math.pi * R_AY) < 1 and abs(tr.f - math.pi * R_AY / 2) < 1, \
                f"transform {list(tr)[:6]}: 256 ppd, -180..180 ve R = 1737,4 km ile tutmuyor"

            def lola_rc(e, b):
                return int(math.floor((90 - e) * 256)), int(math.floor((b + 180) * 256))

            def t_uc():
                mn, mx, n_yok = 32767, -32768, 0
                for r0 in range(0, d.height, 512):
                    a = d.read(1, window=rasterio.windows.Window(0, r0, d.width, min(512, d.height - r0)))
                    yok = a == -32768
                    n_yok += int(yok.sum())
                    v = a[~yok]
                    if v.size:
                        mn, mx = min(mn, int(v.min())), max(mx, int(v.max()))
                OKUMA["M1"]["yok_sayisi_-32768"] = n_yok
                emn, emx = mn * carpan + taban, mx * carpan + taban
                return f"en kucuk {emn:.1f} m, en buyuk {emx:.1f} m (ham {mn}/{mx}); -32768 sayisi {n_yok}", \
                    abs(emn + 9128) <= 50 and abs(emx - 10782) <= 50
            dene("M1", "ham x 0,5 uc degerler", "", "-9128 / +10782 m", "her biri +-50 m (proje karari)",
                 "belge 17.3 D2 (yayımlanmış LOLA uç değerleri)", t_uc)

            def t_a11():
                r, c = lola_rc(*N["apollo11"][:2])
                v = int(d.read(1, window=rasterio.windows.Window(c, r, 1, 1))[0, 0]) * carpan + taban
                return f"{v:.1f} m", abs(v + 1926) <= 50
            dene("M1", "Apollo 11 yuksekligi", "apollo11", "yaklasik -1926 m", "+-50 m (proje karari)", "belge 17.3 D2 (LOLA/LROC)", t_a11)

    bolum('M1', m1)

    # ------------------------------------------------ M4 PRP (talimat 6) ve Shackleton
    prp = {}                                   # PRP tabloları (M4 ve M7 testleri kullanır)

    def m4():
        for yari in ("north", "south"):
            tab = VERI / f"ay/M4_diviner_prp_gcp/dlre_prp_{yari}.tab"
            adlar = lbl_sutunlar(tab.with_suffix(".lbl"))
            df, baslik = oku_tablo(tab, adlar)
            prp[yari] = df
            OKUMA[f"M4_prp_{yari}"] = {"satir": len(df), "sutunlar": list(df.columns), "dosyada_baslik": baslik}
        for yari, df in prp.items():
            dene("M4", f"PRP {yari} yapi", "", "2 880 000 kayit; tri_clon, tri_clat, temp_avg, temp_max, ice_depth",
                 "esitlik", "rapor M4",
                 lambda df=df: (f"{len(df)} kayit, sutunlar {list(df.columns)}",
                                len(df) == 2880000 and all(c in df.columns for c in ("tri_clon", "tri_clat", "temp_avg", "temp_max", "ice_depth"))))
        def t6():
            sonuc, ok = {}, True
            for yari, df in prp.items():
                ice, tmax = df["ice_depth"].to_numpy(), df["temp_max"].to_numpy()
                negler = sorted(set(np.unique(ice[ice < 0]).tolist()))
                bir = ice == -1
                sonuc[yari] = {"negatif_degerler": negler, "n_0": int((ice == 0).sum()), "n_-1": int(bir.sum()),
                               "n_pozitif": int((ice > 0).sum()), "n_-999": int((ice == -999).sum()),
                               "-1_temp_max_en_buyuk": float(tmax[bir].max()) if bir.any() else None}
                ok &= set(negler) <= {-1.0, -999.0}
                ok &= (not bir.any()) or tmax[bir].max() <= 101.3
            OKUMA["M4_ice_depth_sayilari"] = sonuc
            return json.dumps(sonuc, ensure_ascii=False), ok
        dene("M4", "ice_depth negatifleri ve -1 sicakligi (talimat 6)", "",
             "negatifler yalniz {-1, -999}; -1 olan butun ucgenlerde temp_max <= 101,3 K", "iki assert (talimat 6)",
             "talimat 6; Fisher ve ark. 2017, Icarus 292, 74-85", t6)
        def t_shack():
            df = prp["south"]
            u = gc_km(N["shackleton"][0], N["shackleton"][1], df["tri_clat"].to_numpy(), df["tri_clon"].to_numpy())
            sec = df["temp_max"].to_numpy()[u <= 3.0]
            return f"merkezin 3 km icinde {sec.size} ucgen, temp_max ortanca {np.median(sec):.1f} K (en buyuk {sec.max():.1f})", \
                sec.size > 0 and np.median(sec) < 90
        dene("M4", "Shackleton tabani Tmax", "shackleton", "Tmax < 90 K",
             "merkezin 3 km icindeki ucgenlerde temp_max ortancasi < 90 K (proje karari; IAU merkezi tam olmayabilir)",
             "belge 17.3 D2; Paige ve ark. 2010", t_shack)

    bolum('M4', m4)

    # ------------------------------------------------ M3 GHRM <-> M4 GCP, 70° bandı gece yarısı
    def m34():
        def ghrm_bant(kuzey):
            yol = VERI / "ay/M3_diviner_ghrm/dghrm_tbol_sam_70s70n_tif.tif"
            with rasterio.open(yol) as d:
                tr = d.transform
                OKUMA["M3"] = {"boyut": [d.width, d.height], "dtype": d.dtypes[0], "nodata": d.nodata, "transform": list(tr)[:6], "crs": str(d.crs)}
                assert abs(tr.a - 1 / 128) < 1e-9 and abs(tr.e + 1 / 128) < 1e-9 and abs(tr.f - 70) < 1e-6, f"GHRM transform {list(tr)[:6]}"
                r0 = 0 if kuzey else d.height - 64                       # 0,5° = 64 satır: 70..69,5 ya da -69,5..-70
                a = d.read(1, window=rasterio.windows.Window(0, r0, d.width, 64)).astype(float)
            a[~np.isfinite(a) | (a >= 250)] = np.nan                     # belge 10.2: tbol >= 250 K yok sayılır
            return float(np.nanmean(a)), int(np.isfinite(a).sum())
        def gcp_bant(dosya, enlem):
            df = pd.read_csv(VERI / "ay/M4_diviner_prp_gcp" / dosya, skipinitialspace=True)
            df.columns = [c.strip().lower() for c in df.columns]
            OKUMA[f"M4_{dosya}"] = {"satir": len(df), "sutunlar": list(df.columns)}
            s = df[(np.isclose(df["clat"], enlem)) & ((df["ltim"] < 0.25) | (df["ltim"] > 23.75)) & (df["tbol"] != -9999)]
            return float(s["tbol"].mean()), len(s), len(df)
        for kuzey, dosya, enlem in [(True, "global_cumul_avg_cyl_70n80n_002.tab", 70.25), (False, "global_cumul_avg_cyl_80s70s_002.tab", -70.25)]:
            def t_b(kuzey=kuzey, dosya=dosya, enlem=enlem):
                g, ng = ghrm_bant(kuzey)
                c, nc, toplam = gcp_bant(dosya, enlem)
                return f"GHRM {g:.2f} K ({ng} piksel) | GCP {c:.2f} K ({nc} satir, dosya {toplam} satir) | fark {abs(g - c):.2f} K", abs(g - c) < 1.0
            dene("M3/M4", f"GCP-GHRM 70 bandi ({'kuzey' if kuzey else 'guney'})", "", "fark < 1 K",
                 "GHRM 69,5-70° ortalamasi ile GCP 70-70,5° gece yarisi (ltim < 0,25 ya da > 23,75) ortalamasi farki < 1 K",
                 "belge 17.3 D2 ve 6.5 (kuzey 82,6/83,3 K, güney 82,1/82,9 K)", t_b)

    bolum('M3/M4', m34)

    # ------------------------------------------------ M5 LP GRS: alan toplamı = 4πR²
    def m5():
        def t_grs():
            satir = (VERI / "ay/M5_lp_grs/lpgrs_high1_elem_abundance_2deg.tab").read_text(encoding="ascii").splitlines()
            alan = 0.0
            for s in satir:
                v = [float(x) for x in re.split(r"[,\s]+", s.strip())[:5]]
                fs, fn, lw, le = math.radians(v[1]), math.radians(v[2]), v[3], v[4]
                dl = (le - lw) % 360 or 360
                alan += math.radians(dl) * (math.sin(fn) - math.sin(fs))
            oran = alan / (4 * math.pi)
            return f"{len(satir)} piksel, alan / 4πR² = {oran:.6f}", len(satir) == 11306 and abs(oran - 1) <= 1e-4
        dene("M5", "alan toplami", "", "4πR²", "+-%0,01 (belge 17.3 SIM 3292 ile ayni tolerans; proje karari)", "belge 17.3 D2", t_grs)

    bolum('M5', m5)

    # ------------------------------------------------ M6 LP hidrojen
    def m6b():
        def m6():
            satirlar = []
            for s in (VERI / "ay/M6_lp_hidrojen/hydrogenhd.txt").read_text(encoding="ascii", errors="replace").splitlines():
                if not s.strip() or s.lstrip().startswith("#"):
                    continue
                p = [x.strip() for x in s.split(",")]
                h = float("nan") if "*" in p[4] else float(p[4])
                satirlar.append((float(p[0]), float(p[1]), float(p[2]), float(p[3]), h))
            return np.array(satirlar)
        H = m6()
        def t_bozuk():
            b = H[np.isnan(H[:, 4])]
            return f"bozuk hucre(ler): {b[:, :4].tolist()}", len(b) == 1 and b[0, :4].tolist() == [43.0, 43.5, 153.5, 154.0]
        dene("M6", "bozuk hucrenin yeri", "", "43,0-43,5°K 153,5-154,0°D", "esitlik", "rapor M6 / belge 10.2", t_bozuk)
        def t_neg():
            n = int((H[:, 4] < 0).sum())
            return f"{n} negatif hucre", n == 4180
        dene("M6", "negatif hucre sayisi", "", "4180", "esitlik (kirpilmaz)", "rapor M6 / belge 10.2", t_neg)
        def t_kutup():
            e = (H[:, 0] + H[:, 1]) / 2
            k = np.nanmean(H[np.abs(e) >= 80, 4])
            q = np.nanmean(H[np.abs(e) <= 10, 4])
            return f">=80° ortalama {k:.1f} ppm, |enlem|<=10° ortalama {q:.1f} ppm", k > q
        dene("M6", "kutuplar zengin", "", ">= 80° ortalama > ekvator ortalamasi",
             "|enlem| >= 80 ortalamasi > |enlem| <= 10 ortalamasi (proje karari: ekvator bandi +-10°)", "Feldman ve ark. 2001", t_kutup)

    bolum('M6', m6b)

    # ------------------------------------------------ M7 PGDA
    def m7():
        def pgda(ad):
            p = VERI / "ay/M7_pgda" / f"{ad}_240M_201608.TIF"
            lb = (VERI / "ay/M7_pgda" / f"{ad}_240M_201608.LBL").read_text(encoding="ascii", errors="replace")
            sf = float(re.search(r"SCALING_FACTOR\s*=\s*([-\d.Ee+]+)", lb).group(1))
            of = float(re.search(r"\bOFFSET\s*=\s*([-\d.Ee+]+)", lb).group(1))
            with rasterio.open(p) as d:
                a = d.read(1).astype(float)
                OKUMA[f"M7_{ad}"] = {"boyut": [d.width, d.height], "dtype": d.dtypes[0], "nodata": d.nodata,
                                     "transform": list(d.transform)[:6], "lbl_scaling": sf, "lbl_offset": of}
            return a * sf + of, sf, of
        for kutup in ("S", "N"):
            def t_vis(kutup=kutup):
                av, s1, o1 = pgda(f"AVGVISIB_65{kutup}")
                ps, s2, o2 = pgda(f"LPSR_65{kutup}")
                assert (s1, o1) == (0.00004, 0.0) and (s2, o2) == (0.000025, 0.5), f"etiket olcek/ofset {s1},{o1} / {s2},{o2}"
                g = np.isclose(ps, 1.0)
                return f"LPSR=1 piksel {int(g.sum())}; bunlarda AVGVISIB en buyuk {av[g].max():.5f}, sifir orani {np.mean(av[g] == 0):.4f}", \
                    bool(g.any() and av[g].max() == 0)
            dene("M7", f"LPSR=1 -> AVGVISIB 0 ({kutup})", "", "0", "LPSR = 1 olan butun piksellerde AVGVISIB = 0; etiket olcek/ofset belgeyle ayni",
                 "etiket tanımı; belge 10.2", t_vis)
        def t_soguk():
            sonuc, ok = [], True
            for kutup, yari in (("S", "south"), ("N", "north")):
                ps, _, _ = pgda(f"LPSR_65{kutup}")
                n = ps.shape[0]
                yarim = n * 240 / 2
                df = prp[yari]
                df = df[np.abs(df["tri_clat"]) >= 85].nsmallest(100, "temp_max")
                kol = np.radians(90 - np.abs(df["tri_clat"].to_numpy()))
                rho = 2 * R_AY * np.tan(kol / 2)
                lam = np.radians(df["tri_clon"].to_numpy())
                x, y = rho * np.sin(lam), rho * np.cos(lam)          # belge 6.8 / 10.2: iki kutupta da x = ρ sin λ, y = ρ cos λ
                c = np.floor((x + yarim) / 240).astype(int)
                r = np.floor((yarim - y) / 240).astype(int)
                ic = (r >= 0) & (r < n) & (c >= 0) & (c < n)
                oran = float(np.mean(np.isclose(ps[r[ic], c[ic]], 1.0)))
                sonuc.append(f"{kutup}: en soguk 100 ucgen (temp_max {df['temp_max'].min():.1f}-{df['temp_max'].max():.1f} K), LPSR=1 orani {oran:.2f}")
                ok &= oran >= 0.9
            return " | ".join(sonuc), ok
        dene("M7", "Diviner en soguk ucgenler -> LPSR=1 (iki kutup)", "", "LPSR = 1",
             "|enlem| >= 85° en dusuk temp_max'li 100 PRP ucgeninin >= %90'i LPSR = 1 (proje karari); x = ρ sin λ, y = ρ cos λ",
             "belge 17.3 D2 (bağımsız ürün); belge 6.8", t_soguk)

    bolum('M7', m7)

    # ------------------------------------------------ kayıt
    eski = []
    if D2CSV.exists():
        with open(D2CSV, encoding="utf-8", newline="") as f:
            eski = [r for r in csv.DictReader(f) if r["govde"] != "ay"]
    with open(D2CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ALANLAR)
        w.writeheader()
        w.writerows(eski + SATIRLAR)
    (KAYIT / "D2_okuma_ay.json").write_text(json.dumps(OKUMA, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    say = {}
    for s in SATIRLAR:
        say[s["durum"]] = say.get(s["durum"], 0) + 1
    with open(KAYIT / "13_kasim_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  D2 ay: {say}, {round((time.time() - t0) / 60, 1)} dk\n")
    print("=" * 60)
    print(f"D2 Ay: {say} | {round((time.time() - t0) / 60, 1)} dk | kayit/D2.csv, kayit/D2_okuma_ay.json")
    return say
