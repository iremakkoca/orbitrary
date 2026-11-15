# Developed with assistance from Claude (Anthropic).
# 17.4 sıra 13 (1/2): kod\\kos.py (P0–P3 + D5 kuru koşu) + testler\\test_kos_hatti.py; ayar.json alt_tohum.D5_kuru = 12.
import sys, json, importlib
from pathlib import Path
KOK = Path.home() / "orbitrary"; KOD, KAYIT = KOK / "kod", KOK / "kayit"
(KOD / "kos.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 17.5: koşu hattı. Bu parça (1/2): P0 (sağlama + D4), P1 (ızgara), P2 (Dünya kara maskesi ve kapı
değişkenleri), P3 (pencere özellikleri), D5 (kuru koşu: süre ve disk tahmini). P4–P9 ikinci parçada.

Kullanım (Anaconda Prompt, orbitrary ortamı, kod\\ klasöründe):
    python kos.py d5            # kuru koşu: her cisimde 500 pencere, süre ve disk tahmini → kayit\\D5.json
    python kos.py p0 | p1 | p2 | p3 --govde dunya

Kaldığı yerden devam (K16): P2/P3 blok blok yazılır; her blok diske yazılıp kapandıktan sonra "bitti" işaretlenir.
Kesilen koşu aynı komutla yeniden başlatılınca bitmiş bloklar atlanır. Süreler kayit\\kos_sure.jsonl'e eklenir.
"""
import argparse
import datetime
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

import ayar as A
import izgara as Z
import katman as K

ARA, KAYIT, KOD = A.KLASOR["ara"], A.KLASOR["kayit"], A.KLASOR["kod"]
DEM = {"dunya": "etopo", "ay": "lola", "mars": "mola"}
BLOK = 256  # pencere / blok (bellek: Dünya DEM 56 × 56 hücre × 9 alt nokta × 256 ≈ 7 M nokta)


# ------------------------------------------------------------------ kayıt
def sure_yaz(asama, **bilgi):
    s = {"zaman": datetime.datetime.now().isoformat(timespec="seconds"), "asama": asama, **bilgi}
    with open(KAYIT / "kos_sure.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(s, ensure_ascii=False) + "\n")
    return s


# ------------------------------------------------------------------ blok deposu (kaldığı yerden devam)
class Depo:
    """Pencere başına alanlar diskteki .npy (memmap) dosyalarında; ilk bloktan şema çıkarılır.
    yol/sema.json: alan → (kuyruk biçimi, dtype); yol/bitti.npy: blok başına bool."""

    def __init__(self, yol, n, blok=BLOK):
        self.yol, self.n, self.blok = Path(yol), int(n), int(blok)
        self.yol.mkdir(parents=True, exist_ok=True)
        self.nb = (self.n + self.blok - 1) // self.blok
        self._bitti_yol = self.yol / "bitti.npy"
        self.bitti = np.load(self._bitti_yol) if self._bitti_yol.exists() else np.zeros(self.nb, bool)
        assert self.bitti.shape == (self.nb,), "depo başka bir pencere sayısıyla kurulmuş: " + str(self.yol)
        sp = self.yol / "sema.json"
        self.sema = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else None
        self._mm = {}

    def _ac(self, ad, mod):
        if ad not in self._mm:
            kuyruk, dt = self.sema[ad]
            p = self.yol / f"{ad}.npy"
            if mod == "w+" and not p.exists():
                self._mm[ad] = np.lib.format.open_memmap(p, mode="w+", dtype=dt, shape=(self.n, *kuyruk))
                self._mm[ad][:] = np.nan if np.dtype(dt).kind == "f" else 0
            else:
                self._mm[ad] = np.load(p, mmap_mode="r+")
        return self._mm[ad]

    def yaz(self, b, sonuc):
        if self.sema is None:
            self.sema = {k: [list(np.asarray(v).shape[1:]), str(np.asarray(v).dtype)] for k, v in sonuc.items()}
            (self.yol / "sema.json").write_text(json.dumps(self.sema, ensure_ascii=False, indent=1), encoding="utf-8")
        assert set(sonuc) == set(self.sema), (set(sonuc) ^ set(self.sema))
        a, z = b * self.blok, min(self.n, (b + 1) * self.blok)
        for k, v in sonuc.items():
            v = np.asarray(v)
            assert v.shape == (z - a, *self.sema[k][0]), (k, v.shape)
            mm = self._ac(k, "w+")
            mm[a:z] = v
            mm.flush()
        self.bitti[b] = True
        np.save(self._bitti_yol, self.bitti)

    def oku(self, ad):
        return np.load(self.yol / f"{ad}.npy", mmap_mode="r")

    def tamam(self):
        return bool(self.bitti.all())


def bloklari_kos(depo, fonk, ad, her=20):
    """Bitmemiş blokları sırayla çalıştırır. fonk(a, z) → {alan: dizi (z − a, …)}. İlerleme ve kalan süre yazılır."""
    kalan = np.flatnonzero(~depo.bitti)
    t0 = time.time()
    for say, b in enumerate(kalan, 1):
        a, z = b * depo.blok, min(depo.n, (b + 1) * depo.blok)
        depo.yaz(b, fonk(a, z))
        if say % her == 0 or say == len(kalan):
            gecen = time.time() - t0
            print(f"   {ad}: blok {say}/{len(kalan)}  geçen {gecen / 60:.1f} dk  kalan ≈ {gecen / say * (len(kalan) - say) / 60:.1f} dk",
                  flush=True)
    return time.time() - t0


# ------------------------------------------------------------------ P1 ızgara
def izgara(govde):
    """P1: halka ızgarası (belge 4.2) → ara\\izgara_<govde>.parquet (kimlik, enlem, boylam derece)."""
    import pandas as pd
    p = ARA / f"izgara_{govde}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    h = Z.Halka(govde)
    lat, lon = h.merkez_der(np.arange(h.n))
    df = pd.DataFrame({"kimlik": np.arange(h.n, dtype=np.int64), "enlem": lat, "boylam": lon})
    df.to_parquet(p, index=False)
    return df


def p1():
    out = {}
    for g in ("dunya", "ay", "mars"):
        t = time.time()
        out[g] = len(izgara(g))
        sure_yaz("P1", govde=g, pencere=out[g], sure_s=round(time.time() - t, 1))
    return out


# ------------------------------------------------------------------ P2 Dünya kara maskesi + kapı değişkenleri
def _r(govde):
    return float(A.ayar("cisim.yaricap_km")[govde])


def kara_hucreleri(phi0, lam0):
    import kapi
    v, _, _ = K.hucreye(K.ac("mcd12c1_00"), phi0, lam0, _r("dunya"))
    return kapi.kara_payi(v)


def p2_blok(phi0, lam0):
    """Belge 7.1–7.2: kara oranı, E′ bayrağı ve E′ pencerelerinde buz / astro / Pv / kar-buz kapı değişkenleri.
    Hareket kapısı (eğim) P3'te, Geology'nin kayaç payı koşulu P4'te (hedefe bağlı)."""
    import kapi
    import ozellik_diger as OD
    r = _r("dunya")
    kara = kara_hucreleri(phi0, lam0)
    E = kapi.maskeden_gecer(kara)
    n = len(phi0)
    out = {"kara_orani": np.nan_to_num(kara, nan=0.0).mean(axis=(-2, -1)).astype(np.float32), "E": E.astype(np.uint8)}
    for k in ("buz", "astro", "pv", "karbuz"):
        out[k] = np.full(n, np.nan, np.float32)
    if E.any():
        p, l, ka = phi0[E], lam0[E], kara[E]
        h = lambda kat: K.hucreye(kat, p, l, r)[0]
        d = kapi.degiskenler(ka, perm=h(OD.ac("perm_sifir")), ai=h(K.ac("ai")), pv=kapi.Pv(h(kapi.ndvi_yillik())),
                             kar_buz=h(K.ac("mcd12c1_15")) / 100.0)
        for k in ("buz", "astro", "pv", "karbuz"):
            out[k][E] = d[k]
    return out


# ------------------------------------------------------------------ P3 pencere özellikleri
def p3_blok(govde, phi0, lam0):
    """Belge 6.1–6.8, 7.1: topografya (yüzdelik vektörleri, ln R, Ω, R), topoloji sayıları (n↓, n↑), z vektörü,
    kategori 3–8 temsilleri; Dünya'da hareket kapısı değişkeni (W°'da θ < 20° oranı)."""
    import onele
    import ozellik_diger as OD
    import ozellik_topo as T
    import ozellik_topoloji as TP
    r = _r(govde)
    h, _, _ = K.hucreye(K.ac(DEM[govde]), phi0, lam0, r, genisletme=T.GEN)
    oz = T.ozellikler(h, govde)
    W = h[:, T.GEN:-T.GEN, T.GEN:-T.GEN]
    n2 = np.array([TP.n_onemli(TP.diyagramlar(W[w], govde), govde) for w in range(len(phi0))], float)
    z = np.column_stack([np.asarray(T.z_topo(oz), float).reshape(len(phi0), 4), n2])
    out = {"Q1": T.yuzdelik_vektorleri(oz).astype(np.float32), "lnR": np.asarray(oz["lnR"], np.float32),
           "R": np.asarray(oz["R"], np.float32), "Omega_1": np.asarray(oz["Omega_1"], np.float32),
           "Omega_4": np.asarray(oz["Omega_4"], np.float32), "dem_tam": np.asarray(oz["dem_tam"], np.uint8),
           "z": z.astype(np.float64)}
    assert out["z"].shape == (len(phi0), len(onele.BILESENLER))
    for k, v in OD.pencere_temsili(govde, phi0, lam0).items():
        v = np.asarray(v)
        out[k] = v.astype(np.float32) if v.dtype.kind in "fb" else v
    if govde == "dunya":
        import kapi
        out["mob"] = np.asarray(kapi.degiskenler(kara_hucreleri(phi0, lam0), egim_rad=oz["theta_1"])["mob"], np.float32)
    return out


def _radyan(df, idx):
    return np.radians(df["enlem"].to_numpy()[idx]), np.radians(df["boylam"].to_numpy()[idx])


def p2():
    df = izgara("dunya")
    depo = Depo(ARA / "p2_dunya", len(df))
    p, l = _radyan(df, slice(None))
    s = bloklari_kos(depo, lambda a, z: p2_blok(p[a:z], l[a:z]), "P2 dünya")
    E = depo.oku("E").astype(bool)
    sure_yaz("P2", pencere=len(df), E_prime=int(E.sum()), sure_s=round(s, 1))
    return int(E.sum())


def p3(govde, kimlikler=None, ad=None):
    """Dünya: bütün E′ (P2'den); Ay/Mars: verilen kimlikler (liste hedefleri ve komşuları ya da Katman B)."""
    df = izgara(govde)
    if kimlikler is None:
        assert govde == "dunya"
        d2 = Depo(ARA / "p2_dunya", len(df))
        assert d2.tamam(), "P2 bitmeden P3 (Dünya) başlamaz"
        kimlikler = np.flatnonzero(d2.oku("E").astype(bool))
    kimlikler = np.asarray(kimlikler, np.int64)
    ad = ad or f"p3_{govde}"
    np.save(ARA / f"{ad}_kimlik.npy", kimlikler)
    depo = Depo(ARA / ad, len(kimlikler))
    p, l = _radyan(df, kimlikler)
    s = bloklari_kos(depo, lambda a, z: p3_blok(govde, p[a:z], l[a:z]), f"P3 {govde}")
    sure_yaz("P3", govde=govde, ad=ad, pencere=len(kimlikler), sure_s=round(s, 1))
    return depo


# ------------------------------------------------------------------ P0
def p0():
    """Belge 17.5 P0: temiz\\ sağlaması (sabah kayit\\P0.json, PASS) + D4 (testler\\ tamamı)."""
    import test_kos
    j = json.loads((KAYIT / "P0.json").read_text(encoding="utf-8"))
    durum = j.get("durum") or j.get("sonuc")
    print("kayit\\P0.json durum:", durum)
    assert str(durum).upper().startswith("PASS"), "P0 sağlaması PASS değil"
    kod = test_kos.calistir("D4_tam", "testler", bekci_dk=30)
    assert kod == 0, "D4: bütün testler PASS değil"
    sure_yaz("P0", D4="PASS")


# ------------------------------------------------------------------ D5 kuru koşu
def _bayt(depo):
    return sum(int(np.prod(k)) * np.dtype(dt).itemsize for k, dt in depo.sema.values()) if depo.sema else 0


def d5(n=500):
    """Belge 17.5 D5: her cisimde n pencere için P2/P3 süresi → toplam tahmin; disk tahmini; K1, K2 için girdi.
    Örnek pencereler tohum 20261113, alt tohum D5_kuru. İlk (ısınma) blok ayrı ölçülür: sıra referansları (P_f,B) ve
    büyük dosyaların ilk açılışı bir kez yapılır, pencere başına süreye katılmaz. Puanlama (P5–P7) süresi 2. parçada."""
    import shutil
    rng = A.rng(int(A.ayar("alt_tohum")["D5_kuru"]))
    kuru = ARA / "kuru"
    if kuru.exists():
        shutil.rmtree(kuru)
    sonuc = {"n": n, "bilgisayar": {"platform": platform.platform(), "islemci": platform.processor(),
                                    "python": sys.version.split()[0]}, "govde": {}}
    # Dünya P2: 4n rastgele pencere (E′ oranı da buradan)
    df = izgara("dunya")
    idx = np.sort(rng.choice(len(df), 4 * n, replace=False))
    p, l = _radyan(df, idx)
    t = time.time(); isinma = p2_blok(p[:8], l[:8]); t_is2 = time.time() - t
    d2 = Depo(kuru / "p2", len(idx))
    s2 = bloklari_kos(d2, lambda a, z: p2_blok(p[a:z], l[a:z]), "D5 P2 dünya")
    E = d2.oku("E").astype(bool)
    oran = float(E.mean())
    sonuc["govde"]["dunya"] = {"P2_isinma_s": round(t_is2, 1), "P2_s_pencere": s2 / len(idx), "E_orani_orneklem": oran,
                               "E_prime_tahmin": int(round(oran * len(df))), "toplam_pencere": len(df)}
    # P3: Dünya'da örneğin E′ olanlarından ilk n; Ay ve Mars'ta n rastgele pencere
    for g in ("dunya", "ay", "mars"):
        dfg = izgara(g)
        kim = idx[E][:n] if g == "dunya" else np.sort(rng.choice(len(dfg), n, replace=False))
        p, l = _radyan(dfg, kim)
        t = time.time(); p3_blok(g, p[:8], l[:8]); t_is = time.time() - t
        d3 = Depo(kuru / f"p3_{g}", len(kim))
        s3 = bloklari_kos(d3, lambda a, z: p3_blok(g, p[a:z], l[a:z]), f"D5 P3 {g}")
        b = _bayt(d3)
        dem = d3.oku("dem_tam").astype(bool)
        bilgi = sonuc["govde"].setdefault(g, {"toplam_pencere": len(dfg)})
        bilgi.update({"P3_isinma_s": round(t_is, 1), "P3_n": int(len(kim)), "P3_s_pencere": s3 / len(kim),
                      "bayt_pencere": b, "dem_tam_orani": float(dem.mean())})
    # tahminler (saat)
    G = sonuc["govde"]
    t_P2 = G["dunya"]["P2_s_pencere"] * G["dunya"]["toplam_pencere"] / 3600
    t_P3d = G["dunya"]["P3_s_pencere"] * G["dunya"]["E_prime_tahmin"] / 3600
    t_B = sum(G[g]["P3_s_pencere"] * G[g]["toplam_pencere"] for g in ("ay", "mars")) / 3600
    disk = (G["dunya"]["bayt_pencere"] * G["dunya"]["E_prime_tahmin"]
            + sum(G[g]["bayt_pencere"] * G[g]["toplam_pencere"] for g in ("ay", "mars"))) / 1e9
    bos = shutil.disk_usage(ARA).free / 1e9
    sonuc["tahmin_saat"] = {"P2_dunya": round(t_P2, 2), "P3_dunya": round(t_P3d, 2),
                            "KatmanB_ozellik_ay_mars": round(t_B, 2),
                            "not": "Katman A puanlama (P5–P6) ve Katman B puanlama süresi 2. parçada ölçülür; K1/K2 kararı o zaman"}
    sonuc["disk_GB"] = {"ozellik_tahmini": round(disk, 1), "bos": round(bos, 1), "yeterli": bool(disk < 0.8 * bos)}
    (KAYIT / "D5.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    sure_yaz("D5", **sonuc["tahmin_saat"], disk=sonuc["disk_GB"])
    return sonuc


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("asama", choices=["p0", "p1", "p2", "p3", "d5"])
    ap.add_argument("--govde", default="dunya")
    ap.add_argument("--n", type=int, default=500)
    a = ap.parse_args(argv)
    t = time.time()
    if a.asama == "p0":
        p0()
    elif a.asama == "p1":
        print(p1())
    elif a.asama == "p2":
        print("E′ pencere sayısı:", p2())
    elif a.asama == "p3":
        p3(a.govde)
    elif a.asama == "d5":
        print(json.dumps(d5(a.n), ensure_ascii=False, indent=1))
    print(f"bitti: {a.asama} ({(time.time() - t) / 60:.1f} dk)")


if __name__ == "__main__":
    main()
''', encoding="utf-8")
(KOD / "testler" / "test_kos_hatti.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""kos.py hattı: blok deposu (kaldığı yerden devam, K16), şema denetimi, ızgara sayıları."""
import numpy as np
import pytest

import izgara as Z
import kos


def _f(a, z):
    i = np.arange(a, z)
    return {"x": (i * 2.0).astype(np.float32), "Q": np.tile(i[:, None], (1, 3)).astype(np.float32), "b": (i % 2).astype(np.uint8)}


def test_depo_tam_kosu(tmp_path):
    d = kos.Depo(tmp_path / "d", 1000, blok=128)
    kos.bloklari_kos(d, _f, "test")
    assert d.tamam() and d.nb == 8
    np.testing.assert_array_equal(d.oku("x"), np.arange(1000) * 2.0)
    np.testing.assert_array_equal(d.oku("Q")[:, 1], np.arange(1000))


def test_depo_kesilip_devam_K16(tmp_path):
    sayac = {"n": 0}

    def kirik(a, z):
        sayac["n"] += 1
        if sayac["n"] == 4:
            raise KeyboardInterrupt("elektrik gitti")
        return _f(a, z)

    d = kos.Depo(tmp_path / "d", 1000, blok=128)
    with pytest.raises(KeyboardInterrupt):
        kos.bloklari_kos(d, kirik, "test")
    assert d.bitti.sum() == 3 and not d.tamam()
    cagri = []
    d2 = kos.Depo(tmp_path / "d", 1000, blok=128)          # yeniden başlat
    kos.bloklari_kos(d2, lambda a, z: (cagri.append(a), _f(a, z))[1], "test")
    assert cagri == [384, 512, 640, 768, 896]                # bitmiş 3 blok atlandı
    np.testing.assert_array_equal(d2.oku("x"), np.arange(1000) * 2.0)
    np.testing.assert_array_equal(d2.oku("b"), np.arange(1000) % 2)


def test_depo_sema_ve_boyut(tmp_path):
    d = kos.Depo(tmp_path / "d", 300, blok=100)
    d.yaz(0, _f(0, 100))
    with pytest.raises(AssertionError):
        d.yaz(1, {"x": np.zeros(100, np.float32)})          # eksik alan
    with pytest.raises(AssertionError):
        kos.Depo(tmp_path / "d", 301, blok=100)             # başka pencere sayısı
    yeni = kos.Depo(tmp_path / "d", 300, blok=100)
    assert np.isnan(yeni.oku("x")[150])                      # yazılmamış blok NaN, 0 değil


def test_izgara_sayilari():
    # belge 4.2: Ay ≈ 95 bin, Mars ≈ 361 bin (kesin sayılar ozet.json'a)
    assert Z.Halka("ay").n == 94864 and Z.Halka("mars").n == 360654 and Z.Halka("dunya").n == 1275482
''', encoding="utf-8")
# D5 örnek pencereleri için alt tohum (yalnız süre ölçümü; sonuca girmez)
ay = KOD / "ayar.json"; d = json.load(open(ay, encoding="utf-8"))
at = d["parametreler"]["alt_tohum"]
if "D5_kuru" not in at["deger"]:
    assert 12 not in at["deger"].values(), at
    at["deger"]["D5_kuru"] = 12
    if isinstance(at.get("kaynak"), str):
        at["kaynak"] += " | D5_kuru = 12: D5 kuru koşu örnek pencereleri (yalnız süre/disk ölçümü, sonuca girmez)"
    ay.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
print("alt_tohum:", json.load(open(ay, encoding="utf-8"))["parametreler"]["alt_tohum"]["deger"])
P0 = json.loads((KAYIT / "P0.json").read_text(encoding="utf-8"))
print("kayit\\P0.json anahtarları:", list(P0)[:12])
yol = KOD / "FONKSIYONLAR.md"; metin = yol.read_text(encoding="utf-8")
bas, son = "<!-- kos.py -->", "<!-- /kos.py -->"
blok = bas + "\n## kos.py\n" + "\n".join("- " + s for s in [
    "17.5 P1 ızgara → `kos.izgara`, `kos.p1`; P2 kara maskesi + kapı değişkenleri → `kos.p2_blok`, `kos.p2`",
    "17.5 P3 pencere özellikleri (topografya, n↓/n↑, z, kategori 3–8, hareket kapısı) → `kos.p3_blok`, `kos.p3`",
    "17.5 kaldığı yerden devam (K16) → `kos.Depo`, `kos.bloklari_kos`; süre kaydı → `kos.sure_yaz`",
    "17.5 D5 kuru koşu → `kos.d5`; P0 → `kos.p0`"]) + "\n" + son
metin = (metin.split(bas)[0] + blok + metin.split(son)[1]) if bas in metin else (metin.rstrip() + "\n\n" + blok + "\n")
yol.write_text(metin, encoding="utf-8")
with open(KAYIT / "degisiklik.md", "a", encoding="utf-8") as f:
    f.write("- 2026-11-14 | kos.py 1. parça: P0–P3, blok deposu (kaldığı yerden devam), D5 kuru koşu; ayar alt_tohum.D5_kuru = 12 (yalnız ölçüm) | iç iş\n")
if str(KOD) not in sys.path: sys.path.insert(0, str(KOD))
import test_kos; importlib.reload(test_kos)
test_kos.calistir("D4_test_kos_hatti", "testler/test_kos_hatti.py")
