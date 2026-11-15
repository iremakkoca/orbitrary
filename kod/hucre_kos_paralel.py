# Developed with assistance from Claude (Anthropic).
# kos.py: paralel işçiler (P2 + P3 Dünya, sonucu değiştirmez), P0 anahtarı (sağlama_durum); D5 sonucu MAKALEYİ ETKİLER 56–57.
import sys, importlib
from pathlib import Path
KOK = Path.home() / "orbitrary"; KOD, KAYIT = KOK / "kod", KOK / "kayit"
(KOD / "kos.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 17.5: koşu hattı. Bu parça (1/2): P0 (sağlama + D4), P1 (ızgara), P2 (Dünya kara maskesi ve kapı
değişkenleri), P3 (pencere özellikleri), D5 (kuru koşu: süre ve disk tahmini). P4–P9 ikinci parçada.

Kullanım (Anaconda Prompt, orbitrary ortamı, kod\\ klasöründe):
    python kos.py d5            # kuru koşu: her cisimde 500 pencere, süre ve disk tahmini → kayit\\D5.json
    python kos.py dunya --isci 4   # P2 + P3 Dünya (bütün E′), 4 paralel işçi; kesilirse aynı komutla devam
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

    def __init__(self, yol, n, blok=BLOK, isci=None):
        self.yol, self.n, self.blok = Path(yol), int(n), int(blok)
        self.yol.mkdir(parents=True, exist_ok=True)
        self.nb = (self.n + self.blok - 1) // self.blok
        self._bitti_yol = self.yol / ("bitti.npy" if isci is None else f"bitti_{int(isci)}.npy")
        self.bitti = self.bitti_hepsi()
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

    def bitti_hepsi(self):
        """Bütün işçilerin bitti dosyalarının birleşimi (OR)."""
        b = np.zeros(self.nb, bool)
        for p in self.yol.glob("bitti*.npy"):
            x = np.load(p)
            assert x.shape == (self.nb,), "depo başka bir pencere sayısıyla kurulmuş: " + str(self.yol)
            b |= x
        return b

    def oku(self, ad):
        return np.load(self.yol / f"{ad}.npy", mmap_mode="r")

    def tamam(self):
        return bool(self.bitti_hepsi().all())


def bloklari_kos(depo, fonk, ad, her=20, isci_no=None, isci_sayi=1):
    """Bitmemiş blokları sırayla çalıştırır. fonk(a, z) → {alan: dizi (z − a, …)}. İlerleme ve kalan süre yazılır.
    isci_no/isci_sayi: paralel koşuda bu işçi yalnız b mod isci_sayi = isci_no bloklarını yapar."""
    kalan = np.flatnonzero(~depo.bitti)
    if isci_no is not None:
        kalan = kalan[kalan % isci_sayi == isci_no]
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


# ------------------------------------------------------------------ paralel koşu (sonucu değiştirmez)
def paralel(asama, govde, depo_yolu, n, isci_sayi, ilk_blok_fonk):
    """Aynı hesap, bloklar işçilere bölünür (b mod K). Şema ve dosyalar ana süreçte ilk blokla kurulur; her işçi kendi
    bitti_<i>.npy dosyasını yazar ve satırları çakışmaz. Her işçide NumPy tek iş parçacığı (aşırı yüklenmeyi önler)."""
    import os
    import subprocess
    depo = Depo(depo_yolu, n)
    if depo.sema is None or not depo.bitti.any():
        b = int(np.flatnonzero(~depo.bitti)[0])
        a, z = b * depo.blok, min(n, (b + 1) * depo.blok)
        depo.yaz(b, ilk_blok_fonk(a, z))
    ortam = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    kayit_kl = KAYIT / "isci"; kayit_kl.mkdir(exist_ok=True)
    surecler = []
    for i in range(isci_sayi):
        log = open(kayit_kl / f"{asama}_{govde}_{i}.txt", "a", encoding="utf-8")
        surecler.append((subprocess.Popen([sys.executable, "-u", str(KOD / "kos.py"), "isci", "--asama", asama,
                                           "--govde", govde, "--isci-no", str(i), "--isci-sayi", str(isci_sayi)],
                                          cwd=KOD, env=ortam, stdout=log, stderr=subprocess.STDOUT), log))
    t0 = time.time(); b0 = int(Depo(depo_yolu, n).bitti_hepsi().sum())
    while any(p.poll() is None for p, _ in surecler):
        time.sleep(60)
        b = int(Depo(depo_yolu, n).bitti_hepsi().sum()); nb = Depo(depo_yolu, n).nb
        hiz = (b - b0) / max(time.time() - t0, 1)
        kalan = (nb - b) / hiz / 60 if hiz > 0 else float("nan")
        print(f"   {asama} {govde}: {b}/{nb} blok  geçen {(time.time() - t0) / 60:.0f} dk  kalan ≈ {kalan:.0f} dk", flush=True)
    for p, log in surecler:
        log.close()
    kotu = [i for i, (p, _) in enumerate(surecler) if p.returncode != 0]
    assert not kotu, f"işçi hatası: {kotu} → kayit\\isci\\{asama}_{govde}_<i>.txt"
    son = Depo(depo_yolu, n)
    assert son.tamam(), "bütün işçiler bitti ama eksik blok var; aynı komutla yeniden başlat"
    return time.time() - t0


def _p3_kimlik(govde):
    df = izgara(govde)
    if govde == "dunya":
        d2 = Depo(ARA / "p2_dunya", len(df))
        assert d2.tamam(), "P2 bitmeden P3 (Dünya) başlamaz"
        kim = np.flatnonzero(d2.oku("E").astype(bool))
        p = ARA / "p3_dunya_kimlik.npy"
        if p.exists():
            assert np.array_equal(np.load(p), kim), "p3_dunya_kimlik.npy P2 ile tutmuyor"
        else:
            np.save(p, kim)
        return kim
    return np.load(ARA / f"p3_{govde}_kimlik.npy")


def isci(asama, govde, no, sayi):
    df = izgara(govde)
    if asama == "p2":
        p, l = _radyan(df, slice(None))
        depo = Depo(ARA / "p2_dunya", len(df), isci=no)
        bloklari_kos(depo, lambda a, z: p2_blok(p[a:z], l[a:z]), f"P2 işçi {no}", isci_no=no, isci_sayi=sayi)
    else:
        kim = _p3_kimlik(govde)
        p, l = _radyan(df, kim)
        depo = Depo(ARA / f"p3_{govde}", len(kim), isci=no)
        bloklari_kos(depo, lambda a, z: p3_blok(govde, p[a:z], l[a:z]), f"P3 {govde} işçi {no}", isci_no=no, isci_sayi=sayi)


def dunya(isci_sayi):
    """P2 + P3 (Dünya, bütün E′), paralel. Sonuç tek süreçli koşuyla aynıdır (aynı fonksiyon, aynı bloklar)."""
    df = izgara("dunya")
    p, l = _radyan(df, slice(None))
    s2 = paralel("p2", "dunya", ARA / "p2_dunya", len(df), isci_sayi, lambda a, z: p2_blok(p[a:z], l[a:z]))
    E = Depo(ARA / "p2_dunya", len(df)).oku("E").astype(bool)
    sure_yaz("P2", pencere=len(df), E_prime=int(E.sum()), sure_s=round(s2, 1), isci=isci_sayi)
    print("E′ pencere sayısı:", int(E.sum()), flush=True)
    kim = _p3_kimlik("dunya")
    pk, lk = _radyan(df, kim)
    s3 = paralel("p3", "dunya", ARA / "p3_dunya", len(kim), isci_sayi, lambda a, z: p3_blok("dunya", pk[a:z], lk[a:z]))
    sure_yaz("P3", govde="dunya", pencere=len(kim), sure_s=round(s3, 1), isci=isci_sayi)


# ------------------------------------------------------------------ P0
def p0():
    """Belge 17.5 P0: temiz\\ sağlaması (sabah kayit\\P0.json, PASS) + D4 (testler\\ tamamı)."""
    import test_kos
    j = json.loads((KAYIT / "P0.json").read_text(encoding="utf-8"))
    durum = j["sağlama_durum"]
    print("kayit\\P0.json sağlama_durum:", durum)
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
    ap.add_argument("asama", choices=["p0", "p1", "p2", "p3", "d5", "dunya", "isci"])
    ap.add_argument("--govde", default="dunya")
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--isci", type=int, default=4)
    ap.add_argument("--asama", dest="isci_asama")
    ap.add_argument("--isci-no", type=int)
    ap.add_argument("--isci-sayi", type=int)
    a = ap.parse_args(argv)
    t = time.time()
    if a.asama == "isci":
        isci(a.isci_asama, a.govde, a.isci_no, a.isci_sayi)
        return
    if a.asama == "dunya":
        dunya(a.isci)
    elif a.asama == "p0":
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
from pathlib import Path
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


def test_depo_iki_isci(tmp_path):
    # paralel koşu: ana süreç ilk bloğu yazar (şema), iki işçi b mod 2 bloklarını ayrı süreçte yapar; sonuç tek süreçliyle aynı
    import subprocess, sys, textwrap
    yol = tmp_path / "d"
    d = kos.Depo(yol, 1000, blok=100)
    d.yaz(0, _f(0, 100))
    kod = textwrap.dedent(f"""
        import sys; sys.path.insert(0, r"{Path(kos.__file__).parent}"); sys.path.insert(0, r"{Path(__file__).parent}")
        import numpy as np, kos
        from test_kos_hatti import _f
        no = int(sys.argv[1])
        d = kos.Depo(r"{yol}", 1000, blok=100, isci=no)
        kos.bloklari_kos(d, _f, "isci", isci_no=no, isci_sayi=2)
    """)
    ps = [subprocess.Popen([sys.executable, "-c", kod, str(i)]) for i in range(2)]
    assert all(p.wait() == 0 for p in ps)
    son = kos.Depo(yol, 1000, blok=100)
    assert son.tamam() and len(list(yol.glob("bitti*.npy"))) == 3
    np.testing.assert_array_equal(son.oku("x"), np.arange(1000) * 2.0)
    np.testing.assert_array_equal(son.oku("Q")[:, 2], np.arange(1000))
''', encoding="utf-8")
(KAYIT / "makaleyi_etkiler_14_kasim.md").write_text(r'''# MAKALEYİ ETKİLER — 14 Kasım 2026 (kod günü) toplu kayıt

Orbitrary · belge v1.2 (+ v1.2.1 talimatları). Kod yazılırken çıkan, makaleye giren her şey.
Kaynak: `kayit\degisiklik.md` (tarihli satırlar). Durum sütunu: **kaynaklı** = dış kaynağa dayanıyor; **onaylı** = ekip onayladı; **onay bekliyor** = proje kararı, dış kaynağı yok.

## 1. Parametre ve veri

| # | Ne değişti / netleşti | Belge bölümü | Durum | Makaleye not (Emir / Sude) |
|---|---|---|---|---|
| 1 | σv Ay = 10 m, Mars = 1 m (belgede değer yoktu; Dünya 7,17 m aynı) | 4.1, 8.4, T2 | kaynaklı: [105] Smith ve ark. 2010 "~10 m radial"; [104] Smith ve ark. 2001 "~1 m vertical" | T2'de σv = 7,17 / 10 / 1 m; Method'da iki kaynağa bu değerlerle atıf |
| 2 | MI geçerlilik aralığı [0,133; 7,5] = yayınım aralığından (0,604–1,000) türetilmiş matematiksel sınır | 6.4, 10.1 | onaylı (Sude) | ASTER en küçük yayınım 0,604 (belge 0,61 diyordu; talimat 7 UYARI) |
| 3 | I⊕ üst sınırı ≈ 82,1 = max C₁ (1,6426, ε = 23,44°) / 0,02 K | 6.5 | onaylı (Sude) | ölçülen en büyük 75,3 |

## 2. Yöntemin okunuşu (formül aynı, belgede tek anlama inmeyen yer netleşti)

| # | Karar | Belge bölümü | Durum | Makaleye not |
|---|---|---|---|---|
| 4 | P_f,B: "rastgele piksel" yerine alanca düzgün rastgele noktaların piksel değerleri (≤ 10⁶, tohum 20261113) | 5.2 | onaylı (Sude, 12:17) | "area-uniform random sample"; neden: enlem-boylam pikseli kutbu 1/cos φ ağırlıklandırır |
| 5 | Dünya Tmax = aylık gündüz LST'nin en büyüğü; T̄ = aylık (gündüz+gece)/2 yıllık ortalaması; Tgece = aylık gece yıllık ortalaması | 6.5 | onaylı (Sude, 12:17) | dayanak 6.5 "Aqua öğleden sonra geçişi maksimuma yakın" — veri MYD11C3 = Aqua (kaynak dosya MYD11C3.A2023…hdf; belge D1); Aqua ~13:30 / ~01:30 (NASA MODIS teknik sayfası). Sude'nin 'Terra ~10:30' düzeltmesi uygulanmadı: veri Terra değil |
| 6 | I⊕ aylık; C₁ = 0 ve ΔTg ≤ 0 ayları ortalamaya girmez (ΔTg ≤ 0 NaN, assert ve sayılar kayıtta) | 6.5 | ΔTg ≤ 0: onaylı (Sude); yıllık ortalama belgedeki gibi kalır | δ⊙: Michalsky 1988 (Astronomical Almanac düşük duyarlıklı algoritma) |
| 7 | ASTER MI her bandın 12 aylık ortalamasından; ortalamaya yalnız geçerli aylar (0 = yok → NaN) girer | 6.4 | onaylı (Sude, 12:17) | — |
| 8 | Ay aydınlanması: |φ| ≥ 65° PGDA ve < 65° Berger hücreleri kendi kapsamlarında ayrı sıralanır | 6.8 | onaylı (Sude, 12:17) | iki büyüklük farklı birimde; Limitations'a bir cümle |
| 9 | Sıfır kuralında kara hücresi = MCD12C1 kara payı ≥ 0,5 | 6.6 | onaylı, proje kararı (Sude, 12:17) | kar/buz < 0,5 ile aynı çoğunluk mantığı |
| 10 | Ay π⁺: hücrenin alt örneklerinin ≥ yarısında ice_depth ≠ −999 ise hücre pozitif | 6.6 | onaylı, proje kararı (Sude, 12:17) | — |

## 3. Test tanımı

| # | Ne | Belge bölümü | Not |
|---|---|---|---|
| 11 | "Halka ızgarası" testi: formül aralıkları her halkada 20 km ± %5; gerçek komşu uzaklığı kutup ilk halkası (m = 3, ~17,3 km) dışında ± %5; ≤ 5 km sapan tıklama kendi penceresi = en yakın merkez; her nokta kendi hücresine eşlenir, merkeze uzaklık hücre köşe uzaklığını aşmaz (kutup halka 0: 17,3 km, halka 1: 15,6 km, diğer ≤ 14,7 km); en yakın merkeze uzaklık < 15 km | 8.3, T5 | formülün en yakın merkezi verme oranı %96,2 (`kayit\izgara_bilgi.json`) |
| 12 | K12 kontrolü: belgedeki SW (1/π, yarım çember) = Carrière ve ark. (1/2π, S¹); sabit aynı, K12 tetiklenmedi, Ψ₂ değişmez | 6.2, 8.1, 11 | test: `test_sw_tek_nokta_analitik_ve_K12` |

## 4. Hedefler, jeoloji, doğrulama (Sude dönüşü)

| # | Ne | Belge bölümü | Not |
|---|---|---|---|
| 13 | R-UTO ikiye ayrıldı: R-UTO Viking 2 (47,64 / 134,29, NSSDCA), R-ZHU Zhurong (25,066 / 109,925, Liu ve ark. 2022) | 9.2 | iki iniş yeri ~1600 km uzak |
| 14 | R-OLY = IAU Gazetteer özellik merkezi; sitede "feature centre" | 9.2 | "zirve" denmez |
| 15 | R-JEZ belge değeri 18,44 / 77,45 kaldı (Wikipedia hassas değeri kullanılmadı) | 9.2 | kaynak: JPL basın kiti + belge |
| 16 | GLiM pb = gabro, norit, peridotit (Hartmann & Moosdorf 2012, Ek A4.1.4, para. [71]); anortozit geçmez; Ay → pb eşlemesi değişmez, gerekçe cümlesi düzeltildi | 6.3, 13.3 | açık kontrol kısmen kapandı |
| 17 | lApd (kutup kumulları), Hpe (kutup yapıları), Nhe (yayla yapıları) ön kayıtlı kurala göre gruplandı (DMU tanımından farklı) | 6.3, L12 | Limitations cümlesi |
| 18 | V1: 11 çiftin hepsi kaynakla tutuyor; JETT5 NTRS kimliği doğrulanamadı → makalede yalnız USGS kaynağıyla atıf; Dumont Dunes 11 Mayıs haber tarihi; JETT1 kesin tarih yok | 9.3 | onaylı (Sude) |

## 5. Implementation (yöntem aynı; makale Bölüm 8 için)

- Hücre ortalaması (4.4): hücreden ince katmanda hücre içinde s × s alt nokta (piksel kenarı başına ≥ 2, s ≤ 10) → alan ağırlıklı piksel ortalaması.
- Vektör jeoloji (4.4): her pencerede hücre başına 5 × 5 nokta, poligon içi testi (shapely, hazırlanmış poligon). GLiM rasterleştirilmedi.
- Topografya (6.1): "2 hücre dışarıdan" her ölçekte → DEM 8 ince hücre dışından okunur (2 km'de 2 blok).
- F⁻¹ (5.1): ECDF genelleştirilmiş tersi, k = ⌈n(2m − 1)/2M⌉ tam sayı aritmetiğiyle.
- SW doğrultuları orta nokta θ_j = −π/2 + (j − ½)π/Mθ.
- Diviner PRP hücreye: en yakın üçgen merkezi, ortanca komşu aralığının 3 katı eşik (proje kararı, onaylı Sude 12:17), arama eşikle sınırlı.
- H₀: GUDHI CubicalComplex; bağımsız union-find (8-komşuluk) ile 203 pencerede birebir aynı.
- Berger f(φ): 0,001° tablo + doğrusal ara değer (ölçülen en büyük hata 1,2e-9).

## 6. Bekleyen ölçüm (Sude Limitations cümlesini yazacak)

- I⊕: ΔTg < 1 K olan geçerli ayı bulunan piksel oranı 0,329 (2 913 886 / 8 638 888). I⊕ yüzdelikleri: %1 0,0112; %50 0,0541; %99 0,5152; %99,9 3,9962 (`kayit\iarti_teshis.json`).
- Ek ölçümler (en büyük ayın yıllık toplamdaki payı; |u_ort − u_ortanca|; en büyük farkın 10 pikseli) → `kayit\iarti_olcum.json`.

## 7. Son gönderimden sonra eklenenler (12:17'den itibaren)

| # | Ne | Belge bölümü | Durum | Not |
|---|---|---|---|---|
| 19 | Madde 5 "Terra ~10:30" düzeltmesi önerildi, uygulanmadı: veri MYD11C3 (Aqua, ~13:30 / ~01:30) | 6.5, D1 | Sude'ye bildirildi | Limitations'taki I⊕ cümlesinde Terra etkisi yazılmaz |
| 20 | K-1: kapılarda W° "kara hücresi" = kara payı ≥ 0,5 (madde 9 ile aynı) | 7.2 | onaylı, proje kararı (Sude) | — |
| 21 | K-2: Pv için 12 aylık ASTER NDVI → yıllık ortalama (geçerli aylar) → Pv; pencerede **ortanca** (belge 7.2 açıkça "medyan_{W°} P_v" diyor) | 7.2 | onaylı (Sude) | yıllık en büyük kullanılmaz (yağmur sonrası yeşeren çöller) |
| 22 | K-3: Geology kapısında kar/buz payı = W° üzerinde ortalama | 7.2 | onaylı (Sude) | alan payının beklenen değeri |
| 23 | K-4: hedefte verisi olmayan kategori iki taraftan da çıkar; "en fazla 1 eksik" yalnız hedefin verisi olan kategoriler üzerinden | 7.2 | onaylı (Sude) | — |
| 24 | K-5: X'in leave-one-out'u yalnız V1'in kendi Geology satırlarında; diğer hedeflerde X = 7 Geology çiftinin hepsiyle | 7.2, D7 | onaylı (Sude) | — |
| 25 | Gözlem: Ice kapısı (G_buz) yalnız permafrost ortalaması; kar/buz < 0,5 şartı yalnız Geology'de. Grönland/Antarktika içi (kar/buz ≥ 0,5 hücreleri sıfır kuralında hesap dışı) Ice'ta "could not be checked" ile geçer (belge 7.2 kural 2) | 7.2 | kayda yazıldı, değişiklik yok | sonuç tablosunda görünecek |

## 8. Açık sorular (onele / puan / teorem / dogrula) — 12:25 soruldu, 12:33 cevaplandı

Hepsi KAYNAK YOK — onay gerekir. Öneri İrem/Claude'un; karar ekibin.

| # | Soru | Belge | Öneri | Karar |
|---|---|---|---|---|
| Q-1 | z'de MAD = 0 ise | 7.1 | O bileşende Rousseeuw–Croux Qn [96]; Qn de 0 ise bileşen çıkar | **Değişti (Sude):** Qn kullanılmaz (Qn'nin de dayanma sınırı %50, aynı durumda 0 çıkar); MAD = 0 olan bileşen z'den çıkar, kayda yazılır. z yalnız ön elemede; kaybı V5 ölçer |
| Q-2 | Kategori şampiyonu hangi kümeden | 7.4 | E_K(T, g) içindeki uygun adaylar; k = 2 için son 30 aday | onaylı (Sude) |
| Q-3 | V2 "sınıf 2 ≥ %90" düzeyi | 8.3, D6 | Pencere ortalaması MCD12C1 sınıf payı ≥ %90 | onaylı (Sude) |
| Q-4 | V4/V5 "rastgele 200 hedef" cismi | 8.3 | 100 Ay + 100 Mars ızgara penceresi, tohum 20261113 (alt tohum V4/V5) | onaylı (Sude) |
| Q-5 | V5 tam sıralama topoloji dahil mi | 8.3, 7.4 | Topolojisiz (V1 gibi), iki taraf aynı puan | onaylı (Sude) |
| Q-6 | V7 gürültü nereye | 8.3 | Yalnız hedef + 20 komşusunun DEM'i; Dünya tarafı sabit; liste hedeflerinin hepsi | onaylı (Sude) |
| Q-7 | V6 "bütün (E, T) çiftleri" | 8.3 | Liste hedefleri × E_K adayları (8 s_k'nin hepsi olan) | onaylı (Sude) |
| Q-8 | ε* ikiye bölme hassasiyeti | 8.1 | 0,01 m; aralık σv'den başlayıp ikiye katlanır (≤ 10⁵ m) | onaylı (Sude); sınıra kadar bulunamazsa kayda "bulunamadı" |

## 9. Dış inceleme (12:33) — maddeler ve durumu

| # | Bulgu | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 26 | Makale v0.5'te "I⊕ = C₁/ΔT (MOD11C3 in v1.0)", "Aqua replaces Terra", "Replaces MOD11C3 (Terra) of v1.0" yazıyor; belge D1 ise bunu kaynakça hatası diyor. Bugünkü koşu MYD11C3 (testle doğrulandı). | D1, D12 | Hayır | Makaledeki sonuçlar v1.2 koşusundan gelecek; D12 gereği v1.0 karşılaştırma cümleleri makaleden çıkar (Emir/Sude) |
| 27 | Aqua gece geçişi 01:30, günlük minimum gün doğumuna yakın → ΔTg = T₁₃:₃₀ − T₀₁:₃₀ < T_max − T_min → I⊕ olduğundan büyük | 6.5 | Hayır | Limitations cümlesi sapmanın yönünü söyler (Sude) |
| 28 | Puan sıra tabanlı: her yerde aynı oranda sapma sırayı değiştirmez; etkiyi yalnız yerden yere değişen sapma yapar (tarama açısı, enlem, açık gün seçimi) | 5.2, 6.5 | Hayır | Limitations cümlesi "olduğundan büyük" yerine bunu söyler (Sude) |
| 29 | I⊕ yıllık değeri: oranların ortalaması (belge) küçük paydalı aylara duyarlı. **Karar (Sude, 12:57; D8'den önce, sonuçlara bakılmadan):** ortalamaların oranı, I⊕ = Σ C₁(1 − α) / Σ ΔTg, toplam C₁ > 0, ΔTg > 0 (ve α var) olan geçerli aylar üzerinden. Cebirsel olarak aylık I⊕'nin ΔTg ağırlıklı ortalaması; ΔTg ≈ 0 olan ay yıllık değeri ele geçiremez. MI'deki "önce ortalama" (madde 7) ile tutarlı | 6.5 | Evet: yalnız ozellik_diger yıllık I⊕ (`I_arti_yillik`) ve ara\cmg_iarti.npy yeniden üretildi; sınır (≤ 82,1) aynı | uygulandı; gerekçe büyüklüğü `kayit\iarti_olcum.json` (|u_eski − u_yeni|: ortanca, %95, en büyük); Sude gerekçe cümlesini yazdı (13:14): sıra farkı ortanca 0,021, %95 0,228 |
| 30 | Pv'de ortanca: Pv NDVI'nin azalmayan fonksiyonu → medyan Pv < 0,5 ⇔ medyan NDVI < 0,2 + 0,3√0,5 ≈ 0,412; belgedeki "NDVI < 0,41" cümlesi tam doğru | 7.2 | Hayır | Method'a gerekçe olarak (Emir) |
| 31 | Buz tabakası pencereleri Ice kapısından "could not be checked" geçer, s₆ tanımsız, ağırlık termal/aydınlanmaya kayar → Ay kutup hedeflerinde üst sıralara çıkabilir. Kavramsal soru: buz tabakası "donmuş zemin" mi? | 6.6, 7.2 | Şimdi hayır | Koşudan sonra Ice Top-3/ilk 10'da "could not be checked" oranı ozet.json'a otomatik yazılır; yorum ekip |
| 32 | Madde 8 (PGDA/Berger) gerekçesi: bu "cisim içi sıra"nın kendisi değil; Ay iki referansa bölünüyor, 65°'de süreksizlik (64,9° ve 65,1° çok farklı sıra alabilir) | 6.8 | Hayır | Limitations cümlesi süreksizliği açıkça söyler (Sude) |
| 33 | Sude'nin numaralandırması kayıttakiyle farklı ("6. MI" = madde 7, "7. aydınlanma" = 8, "8." = 9 ve 10) | — | Hayır | Bu belgede numaralar düzeltilmiş halde |

## 10. teorem.py (12:45)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 34 | Lemma 1 (a)–(e), Ψ₁, Ψ₂ ve Teorem 1 sayısal testten geçti (rastgele DEM + |e| ≤ ε; sınırlar her tekrarda tuttu; 0,9·ε* gürültüde s₁ sırası değişmedi). **Erken uyarı:** sentetik arazide ε*₁ ≈ 0,02–2 mm (σv = 7,17 m). Ψ₁'i H₄ terimi büyütüyor (IQR_T(H₄) ~1e-5). Gerçek dağılım D6/uzun koşuda (F15) | 8.1 | Hayır | Emir: "güvenli hata yarıçapı ölçülür ve raporlanır" cümlesini büyüklükten bağımsız doğru kalacak biçimde yazar; sayılar ozet.json'dan |
| 35 | ε* < 0,01 m (Q-8 hassasiyeti) ise kayda "0,01 m'den küçük" yazılır (0 yalnız gerçek eşitlikte) | 8.1, Q-8 | Hayır (kayıt biçimi) | — |

## 11. onele.py (12:55)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 36 | Q-1 uygulandı: MAD = 0 olan z bileşeni çıkar; hangi bileşenin çıktığı `ozet.json`'a yazılır. **Olası durum:** n↓ ve n↑ sayım; Dünya pencerelerinin yarısından fazlasında aynı değer (ör. 0) çıkarsa MAD = 0 olur ve bileşen düşer. Sonuç P4'te görülür | 7.1, Q-1 | Hayır (karar onaylı) | makalede "z'den çıkan bileşenler" cümlesi ozet.json'dan |
| 37 | Okuma (formül aynı): z'si eksik (NaN) Dünya penceresi KD-ağacına girmez, sayısı kayda yazılır. Bu yalnız DEM'i eksik pencerelerde olur; bunlar topoloji kategorisi olmadığı için zaten uygun değil (7.2). Aynı uzaklıkta pencere kimliği küçük olan önce | 7.1, 7.2 | Hayır | kayda yazıldı |
| 38 | **Q-9 (onaylı, proje kararı, Sude 12:51):** V5'te {100, 200, 400, 800} hiçbiri ortalama recall ≥ 0,9 sağlamazsa Kön = 800 (denenenlerin en büyüğü), koşu durmaz. Listeye yeni değer eklenmez (sonuçtan sonra ayarı genişletmek önceden kilitleme ilkesine aykırı) | 7.1, 8.3 V5 | onele.kon_sec → (K, eşik sağlandı mı) | makaleye "recall did not reach 0.9 (mean ± CI)" sınırlılığı; ozet.json'da bayrak |
| 39 | **Q-10 (onaylı, proje kararı, Sude 12:51):** şart ortalama recall'a (r̄) uygulanır. GA = r̄ ± 1,96 s_d/√200 (s_d örneklem std, ddof = 1) hesaplanır, ozet.json'a yazılır; r̄ ≥ 0,9 ama alt uç < 0,9 ise makalede tek cümleyle belirtilir | 8.3 V5 | onele.recall_ozet | — |
| 40 | Hedef penceresinin z'sinde (tutulan bileşende) NaN varsa ön eleme yapılmaz, hata verir (sessiz karar yok). Ay/Mars DEM'leri küresel tam olduğu için beklenmiyor; olursa pilotta görülür | 7.1 | Hayır | kayda yazıldı |

## 12. I⊕ formülü uygulaması (13:10)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 41 | **(1 − α) çarpanı kaldı.** Sude'nin notunda "21 sette Dünya albedosu yok, çarpan alınmayacak" deniyor; ama belge 6.5'teki formül I⊕ = C₁(1 − α)/ΔTg, veri tablosunda MCD43C3 beyaz gök albedo (E6, 2023'ün her ayının 15'i) var, set temiz\ altında (P0 24/24 PASS) ve kod 13 Kasım'dan beri çarpanı kullanıyor. Çarpanı atmak belgeden sapma olurdu. v1.0'daki seçim gerekçe olamaz (D12: eski sürümle karşılaştırma yok) | 6.5, 10.1 | Hayır (zaten öyleydi) | Sude'ye bildirildi; makalede formül belge 6.5'teki gibi (1 − α)'lı yazılır, albedo kaynağı [67] |
| 42 | Yalnız yıllık I⊕ değişti; Tmax, T̄, Tgece, MI dosyaları yeniden yazılmadı (değiştirilmedikleri kontrol edildi). I⊕'nin cisim içi sıra referansı (ara\ref_dunya_iarti.npy) silinip yeni değerden üretilir | 6.5, 5.2 | iç iş | — |

## 13. puan.py (13:25)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 43 | **Q-11 (onaylı, proje kararı, Sude 13:14; öneri değişti):** ζ_k'nın paydası (R_k uzaklıklarının ortancası) 0 ise d = 0 → **ζ = 1**, d > 0 → ζ = +∞. Payda 0 iken referansların yarıdan fazlası hedefe tam eşit uzaklıktadır; d = 0 olan pencere istisnai değil, tipik bir referans kadar yakındır (s_k'nin ½ eşitlik sayımıyla tutarlı). Paydası 0 olan aday sayısı kayda/ozet.json'a | 5.4, 7.4 | Evet: puan.zeta_k (uygulandı) | — |
| 44 | **Q-12 (onaylı, proje kararı, Sude 13:14):** 100 km kuralı sitedeki ilk 10 listesine de uygulanır; Top-3 = ilk 10'un ilk üçü | 7.4, 17.6 | Yalnız kos.py | — |
| 45 | **Q-13 (onaylı, proje kararı, Sude 13:14):** τb ana koşunun son 30 adayı üzerinden; alternatif şemada (eşit ağırlık, geometrik ortalama) aynı 30 aday yeniden puanlanır, iki sıralama aynı küme üzerinde karşılaştırılır. Top-3 Jaccard'da üç sıralamaya da 100 km kuralı | 7.4 | Yalnız kos.py | — |
| 46 | Okuma: eşitlik kırıcı zinciri P azalan → Q artan → **pencere kimliği artan** (belge 8.3 "tekrar koşuda aynı" şartı; Q de eşitse sıra yine deterministik) | 7.4, 8.3 | Hayır | kayda yazıldı |
| 47 | Okuma: "en az 100 km" ≥ 100 km (tam 100 km olan aday alınır) | 7.4 | Hayır | kayda yazıldı |
| 48 | Test tanımı: 8.2 "sıra biçimi N = 5, (1, 2, 2, 3, 4)" satırı formül sınaması; |R_k| < 100 → null kuralı bu testte devre dışı (en_az = 1), kural ayrı testte (8.3 "99 / 100") | 5.4, 8.2 | Hayır | T5 tablosunda not |
| 49 | Görev ağırlıkları belge 7.3 formülünden (0,80/m, 0,20/(n − m)) üretilir; tablo testle doğrulandı. kos.py çalışırken ayar.json'daki ağırlıklarla birebir aynı olduğunu assert eder | 7.3 | Hayır | — |
| 50 | puan.py sabitleri ayar.json'dan okunur ve belge 8.4 ile assert edilir: referans.en_kucuk 100, siralama.top3_en_az_km 100, topoloji.aday_sayisi 30, agirlik.ana_pay 0,8; ana kategoriler belge 7.3 tablosuyla testte karşılaştırıldı | 8.4, 7.3 | Hayır | — |

## 14. dogrula.py (13:40)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 51 | V1–V3, V6, V9 formülleri belge 8.3'teki gibi; H₀ altında (Π ~ U(0, 1)) Fisher p-değerinin düzgün dağıldığı 4000 tekrarlı testle doğrulandı. V1 kapıdan kalan analog Π = 0 (K14). V3 p-değeri tek yönlü Mann–Whitney [63] | 8.3 | Hayır | — |
| 52 | Okuma: V3 %95 GA = 2000 bootstrap, A ve B′ ayrı ayrı yerine koyarak yeniden örneklenir, yüzdelik yöntemi (Efron & Tibshirani [28]); alt tohum V3. B′ hedef başına ayrı rastgele akış | 8.3 V3 | Hayır | kayda yazıldı |
| 53 | Okuma: V2'de aynı pencere iki çiftte seçilmez (22 farklı pencere); alt tohum V2 | 8.3 V2, D6 | Hayır | kayda yazıldı |
| 54 | **Q-14 (onaylı, proje kararı, Sude 13:22):** ayar.json'a `alt_tohum.V4_hedef = 6` eklendi, D8'de kilitlenir; V4 ve V5'in 200 hedefi ayrı kümeler (Q-4'ün amacı) | 8.3 V4, Q-4 | ayar.json + kos.py | uygulandı |
| 55 | **Q-15 (onaylı, proje kararı, Sude 13:22):** rastgele 200 hedefte τb, E_K adaylarının R ve R′ ile iki topolojisiz sıralaması arasında; Katman A–B'de liste hedeflerinin son 30 adayı; Top-3 değişimi Jaccard ile. **Ek:** τb iki sıralamanın ortak aday kümesinde (E_K R'ye bağlıysa kesişim; kesişim boyutu kayda). ozet.json: 200 hedefin τb ortancası ve %5–%95 aralığı (K4 kuralı belgedeki gibi τ̄b ortalamasıyla) | 8.3 V4 | dogrula.tau_ortak, dogrula.v4_ozet | uygulandı |

## 15. D5 kuru koşu (14:03) ve K1 / K2

Ölçüm (`kayit\D5.json`; her cisimde 500 pencere, tek süreç, AMD Family 25 Model 97, Windows 11): Dünya E′ oranı örneklemde 0,264 → |E′| ≈ 336 727 (kesin sayı P2'den, ozet.json'a). Pencere başına P3 süresi: Dünya 0,097 s, Ay 0,224 s, Mars 0,061 s. Tek süreç tahmini: P2 Dünya 3,6 sa, P3 Dünya 9,1 sa, **Katman B'nin yalnız özellik kısmı (Ay + Mars) 12,1 sa** (Ay 5,9 sa, Mars 6,2 sa); puanlama süresi henüz eklenmedi. Disk tahmini 39,7 GB (boş 107,6 GB). Bütün pencerelerde DEM tam (dem_tam oranı 1,0).

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 56 | **Q-16 (okuma, onay gerekir):** K1 "Katman B tahmini > 10 saat → Katman B yalnız Ay; Mars'ta tıklama en yakın liste hedefini açar". Tek süreçli ölçümde yalnız özellik kısmı 12,1 sa, yani **K1 tetiklendi**. Aynı hesap 4 paralel işçiyle (sonuç değişmez) kabaca 3–4 sa'e iner; o zaman eşik altında kalabilir. **Öneri:** kural ölçüldüğü gibi uygulanır (tek süreç ölçümü, sonuç görülmeden yazılmış eşik) → Katman B yalnız Ay. Paralellik kuralı aşmanın yolu olarak kullanılmaz; kazanılan süre Katman A ve doğrulamaya (V1–V10) gider. K2 (Katman A > 4 sa → kategori 1 referansı 2000 → 1000) puanlama süresi ölçülünce (kos.py 2. parça) aynı biçimde karar verilir | 3.2, 11 K1/K2, 17.5 | Evet (P7 yalnız Ay) | ekip kararı; sitede Explore metni, makalede Implementation (K1'in sonucu) |
| 57 | İç iş: P2/P3 paralel işçilerle (blok mod K); aynı fonksiyon, aynı bloklar, sonuç tek süreçliyle birebir aynı (testle) | 17.5 | Hayır | — |
''', encoding="utf-8")
import os; print("işlemci çekirdeği (mantıksal):", os.cpu_count())
try:
    import psutil; print("RAM (GB):", round(psutil.virtual_memory().total / 1e9, 1))
except ImportError:
    print("psutil yok (RAM yazılmadı)")
with open(KAYIT / "degisiklik.md", "a", encoding="utf-8") as f:
    f.write("- 2026-11-14 | D5: P2 3,6 sa, P3 Dünya 9,1 sa, Katman B özellik 12,1 sa (tek süreç) → K1 tetiklendi (Q-16 ekipte); kos.py paralel işçiler (sonuç aynı) | etkisi: MAKALEYİ ETKİLER 56–57\n")
if str(KOD) not in sys.path: sys.path.insert(0, str(KOD))
import test_kos; importlib.reload(test_kos)
test_kos.calistir("D4_test_kos_hatti", "testler/test_kos_hatti.py")
