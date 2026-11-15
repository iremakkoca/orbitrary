# Developed with assistance from Claude (Anthropic).
# Düzeltme (16:19): kos.py'de 2. parça "if __name__ == '__main__'" satırından sonra kalmıştı; komut satırından
# çalışınca d6 tanımlanmadan main() çağrılıyordu (NameError). Satır dosyanın sonuna taşındı. Testler modülü import ettiği
# için bu hatayı görmemişti; komut satırı denetimi eklendi.
import sys, subprocess, importlib
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
# Windows konsolu/dosya yönlendirmesi cp1254: "≈", "′" gibi karakterler yazılamaz → çıktı UTF-8
for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
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
    ortam = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", PYTHONIOENCODING="utf-8")
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
    ap.add_argument("asama", choices=["p0", "p1", "p2", "p3", "d5", "dunya", "isci", "d6"])
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
    elif a.asama == "d6":
        print(json.dumps(d6(), ensure_ascii=False, indent=1))
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



# =====================================================================================================
# 2. parça: P4–P6 (Katman A), D6 pilot. Belge 7.1–7.4, 5.4, 8.1.
# =====================================================================================================
SONUC = A.KLASOR["sonuc"]
GOREVLER = ["genel", "mobility", "geology", "ice", "astro"]
HEDEF_MERKEZ = "koordinat"   # Q-17 (onay bekliyor): liste hedefinin penceresi hedef koordinatına ortalanır


class Dunya:
    """P2/P3 çıktıları (E′ sırasıyla). Büyük diziler memmap; küçükler belleğe alınır."""

    def __init__(self):
        df = izgara("dunya")
        self.kim = np.load(ARA / "p3_dunya_kimlik.npy")
        self.n = len(self.kim)
        self.d3 = Depo(ARA / "p3_dunya", self.n)
        d2 = Depo(ARA / "p2_dunya", len(df))
        assert self.d3.tamam() and d2.tamam(), "P2/P3 Dünya tamam değil"
        self.lat = df["enlem"].to_numpy()[self.kim]
        self.lon = df["boylam"].to_numpy()[self.kim]
        for k in ("buz", "astro", "pv", "karbuz"):
            setattr(self, k, np.asarray(d2.oku(k))[self.kim].astype(float))
        assert np.asarray(d2.oku("E"))[self.kim].all()
        self.z = np.asarray(self.d3.oku("z"), float)
        self.q3 = np.asarray(self.d3.oku("q3"), float)
        self.mob = np.asarray(self.d3.oku("mob"), float)
        self.lnR = np.asarray(self.d3.oku("lnR"), float)
        self.R = np.asarray(self.d3.oku("R"), float)
        self.Om1 = np.asarray(self.d3.oku("Omega_1"), float)
        self.Om4 = np.asarray(self.d3.oku("Omega_4"), float)
        self.dem_tam = np.asarray(self.d3.oku("dem_tam")).astype(bool)
        self.x4g = np.asarray(self.d3.oku("x4_gecerli"), float)
        self.konum = {int(k): i for i, k in enumerate(self.kim)}

    def Q(self, ad):
        return self.d3.oku(ad)

    def Q1(self, idx):
        idx = np.asarray(idx, int)
        o = np.argsort(idx)
        out = np.empty((len(idx), 6, 1000), np.float32)
        out[o] = self.d3.oku("Q1")[idx[o]]
        return out


def referans_kumeleri(n):
    """Belge 5.4 R(k): kategori 1 için 2000, 2 ve 8 için 200 pencere, E′'den bir kez, tohum 20261113 (alt R_orneklem).
    Okuma: tek permütasyon; R(1) = ilk 2000, R(2) = R(8) = ilk 200 (aynı örnek, belge 5.4 'aydınlanma aynı örneği kullanır')."""
    p = ARA / "ref_kumeleri.npz"
    ka = A.ayar("referans.katman_A")
    assert (int(ka["1"]), int(ka["2"]), int(ka["8"])) == (2000, 200, 200), ka
    if p.exists():
        z = np.load(p)
        assert int(z["n"]) == n
        return z["R1"], z["R28"]
    perm = A.rng(int(A.ayar("alt_tohum")["R_orneklem"])).permutation(n)
    R1, R28 = perm[:2000], perm[:200]
    np.savez(p, R1=R1, R28=R28, n=n)
    return R1, R28


def dunya_diyagram(D, idx):
    import ozellik_topoloji as TP
    idx = np.asarray(idx, int)
    phi, lam = np.radians(D.lat[idx]), np.radians(D.lon[idx])
    h, _, _ = K.hucreye(K.ac("etopo"), phi, lam, _r("dunya"))
    return [TP.diyagramlar(h[w], "dunya") for w in range(len(idx))]


def ref_diyagramlari(D, R28):
    import pickle
    p = ARA / "ref2_diyagram.pkl"
    if p.exists():
        return pickle.loads(p.read_bytes())
    dg = dunya_diyagram(D, R28)
    p.write_bytes(pickle.dumps(dg))
    return dg


def hedef_hazirla(satir):
    """Belge 4.2, 6.1–6.8: hedef penceresi T ve N(T) (en yakın 20 ızgara penceresi); IQR_T, F_T; T'nin özellikleri,
    diyagramı, π⁺ (ıslak/kuru), F₅."""
    import ozellik_diger as OD
    import ozellik_topo as T
    import ozellik_topoloji as TP
    g = satir["cisim"]
    H = Z.Halka(g)
    lat, lon = float(satir["enlem"]), float(satir["boylam"])
    if HEDEF_MERKEZ == "izgara":
        lat, lon = (float(v) for v in H.merkez_der(H.tikla(lat, lon)))
    kom, _ = H.komsular(lat, lon)
    phi = np.r_[np.radians(lat), H.phi[kom]]
    lam = np.r_[np.radians(lon) % (2 * np.pi), H.lam[kom]]
    r = _r(g)
    h, _, _ = K.hucreye(K.ac(DEM[g]), phi, lam, r, genisletme=T.GEN)
    oz = T.ozellikler(h, g)
    iqr = T.iqr_hedef([{f: oz[f][i] for f in T.OZELLIKLER} for i in range(len(phi))])
    f = p3_blok(g, phi[:1], lam[:1])
    dg = TP.diyagramlar(h[0, T.GEN:-T.GEN, T.GEN:-T.GEN], g)
    pi = float(np.asarray(f.get("pi_arti", [np.nan]))[0])
    F5 = OD.termal_ozellikleri(g, lat)
    hz = {"kimlik": satir["kimlik"], "ad": satir["ad"], "govde": g, "enlem": lat, "boylam": lon,
          "kaynak": satir.get("kaynak", ""), "iqr": iqr, "dg": dg, "pi_arti": pi, "islak": bool(OD.islak_mi(pi)),
          "F5": F5, "komsu": [int(k) for k in kom]}
    for k, v in f.items():
        hz[k] = np.asarray(v)[0]
    hz["z"] = np.asarray(f["z"], float)[0]
    return hz


def hedef_kategorileri(hz):
    """K(T): hedefte verisi olan kategoriler (8,). 6: kuru hedefte null (belge 6.6); 4: değerli hücre < %50 null."""
    esik = float(A.ayar("mineraloji.gecerlilik_orani"))
    K_ = np.zeros(8, bool)
    K_[0] = np.isfinite(hz["Q1"]).all() and np.isfinite(hz["lnR"])
    K_[1] = hz["dg"] is not None
    K_[2] = np.isfinite(hz["q3"]).all()
    K_[3] = np.isfinite(hz["Q4"]).all() and float(hz["x4_gecerli"]) >= esik
    K_[4] = all(np.isfinite(hz[f"Q5_{f}"]).all() for f in hz["F5"])
    K_[5] = hz["islak"] and np.isfinite(hz["Q6"]).all()
    K_[6] = np.isfinite(hz["Q7"]).all()
    K_[7] = np.isfinite(hz["Q8"]).all()
    return K_


def dunya_uzakliklari(D, hedefler, parca=8192):
    """Kategori 3–8 için bütün E′ pencerelerinin her hedefe uzaklığı (belge 6.3–6.8); tek geçişte. Dönüş {k: (nE, nT)}."""
    import uzaklik as U
    nT = len(hedefler)
    KT = np.array([hedef_kategorileri(h) for h in hedefler])
    q3T = np.array([h["q3"] for h in hedefler], float)
    QT = {ad: np.array([h[ad] for h in hedefler], float) for ad in ("Q4", "Q6", "Q7", "Q8")}
    F5hep = sorted({f for h in hedefler for f in h["F5"]})
    Q5T = {f: np.array([h.get(f"Q5_{f}", np.full(1000, np.nan)) for h in hedefler], float) for f in F5hep}
    esik = float(A.ayar("mineraloji.gecerlilik_orani"))
    out = {k: np.full((D.n, nT), np.nan) for k in (3, 4, 5, 6, 7, 8)}
    eK = np.ones((D.n, 8), bool)                       # Dünya tarafında kategori verisi var mı (eksik veri tarafı için)
    eK[:, 0] = np.isfinite(D.lnR)
    eK[:, 1] = D.dem_tam
    mm = {ad: D.Q(ad) for ad in ("Q4", "Q6", "Q7", "Q8")}
    mm5 = {f: D.Q(f"Q5_{f}") for f in F5hep}
    t0 = time.time()
    for a in range(0, D.n, parca):
        z = min(D.n, a + parca)
        qa = D.q3[a:z]
        eK[a:z, 2] = np.isfinite(qa).all(axis=1)
        out[3][a:z] = U.tv(qa[:, None, :], q3T[None, :, :])
        q4 = np.asarray(mm["Q4"][a:z])
        eK[a:z, 3] = np.isfinite(q4).all(axis=1) & (D.x4g[a:z] >= esik)
        out[4][a:z] = U.w1_matris(q4, QT["Q4"])
        out[4][a:z][D.x4g[a:z] < esik, :] = np.nan
        q5 = {f: np.asarray(mm5[f][a:z]) for f in F5hep}
        eK[a:z, 4] = np.all([np.isfinite(q5[f]).all(axis=1) for f in F5hep], axis=0)
        W5 = {f: U.w1_matris(q5[f], Q5T[f]) for f in F5hep}
        for j, h in enumerate(hedefler):
            out[5][a:z, j] = np.mean(np.stack([W5[f][:, j] for f in h["F5"]]), axis=0)
        for k, ad in ((6, "Q6"), (7, "Q7"), (8, "Q8")):
            q = np.asarray(mm[ad][a:z])
            eK[a:z, k - 1] = np.isfinite(q).all(axis=1)
            out[k][a:z] = U.w1_matris(q, QT[ad])
    for k in (3, 4, 5, 6, 7, 8):
        out[k][:, ~KT[:, k - 1]] = np.nan   # hedefte yoksa kategori null (iki taraftan da)
    print(f"   Dünya uzaklıkları: {D.n} × {nT} hedef, {(time.time() - t0) / 60:.1f} dk", flush=True)
    return out, eK


def _psi1(e, A_, gA, B_, gB, iqr):
    """Lemma 2 Ψ₁, iki pencere farklı cisimlerden (ℓ her pencerenin kendi σv'siyle)."""
    import teorem as TM
    iqr = np.asarray(iqr, float)
    FT = np.isfinite(iqr) & (iqr > 0)
    LA = TM._Lam_vektor(A_["Omega_1"], A_["Omega_4"], e)
    LB = TM._Lam_vektor(B_["Omega_1"], B_["Omega_4"], e)
    top = np.sum(((LA + LB) / np.where(FT, iqr, 1.0))[..., FT], axis=-1)
    return e / (FT.sum() + 1) * (top + 2 / TM.ell(A_["R"], gA, e) + 2 / TM.ell(B_["R"], gB, e))


def _psi2(e, RA, gA, RB, gB):
    import teorem as TM
    N = int(A.ayar("izgara.N"))
    return 32 * (2 * N + 1) ** 2 * e * (1 / TM.ell_top(RA, gA, e) + 1 / TM.ell_top(RB, gB, e))


def kapilar(D, gorev, hz, X):
    """Belge 7.2: G_g ve durum (bütün E′ üzerinde; yedek kuralı E′ sayımıyla). Genel: kapı yok."""
    import kapi
    n = D.n
    if gorev == "genel":
        return np.ones(n, bool), np.full(n, kapi.UYGULANMAZ, dtype=object), {"yedek": False}
    if gorev == "mobility":
        G, d = kapi.kapi_mobility(D.mob)
        return G, d, {"yedek": False}
    if gorev == "ice":
        return kapi.kapi_buz(D.buz, hz["islak"])
    if gorev == "astro":
        return kapi.kapi_astro(D.astro)
    c = int(np.nanargmax(hz["q3"]))
    G, d = kapi.kapi_jeoloji(D.pv, D.karbuz, D.q3[:, c], X)
    return G, d, {"yedek": False, "c_yildiz": c, "X": X}


def X_hesapla(D, hz_sozluk, ciftler):
    """Belge 7.2 / D7 + K-5: V1 Geology çiftlerinde q_{c*(T_a)}(E_a); X_tam ve LOO."""
    import kapi
    H = Z.Halka("dunya")
    paylar = {}
    for _, c in ciftler.iterrows():
        if c["tur"] != "V1" or c["gorev"] != "geology":
            continue
        hz = hz_sozluk[c["hedef_kimlik"]]
        k = int(H.tikla(float(c["enlem"]), float(c["boylam"])))
        assert k in D.konum, f"V1 sahası E′ dışında: {c['dunya_saha']}"
        paylar[int(c["cift_no"])] = float(D.q3[D.konum[k], int(np.nanargmax(hz["q3"]))])
    return kapi.X_degerleri(paylar), paylar


def bilinen_analoglar():
    """B1.3 / v1.2.1 madde 4: V1 sahaları + Mission-prep K1/K2 (kod\\site_girdi). Dönüş (id, enlem, boylam) listesi."""
    import pandas as pd
    out = []
    c = pd.read_csv(KOD / "dogrulama_ciftleri.csv")
    am = KOD / "site_girdi" / "analog_metin.csv"
    sid = {}
    if am.exists():
        a = pd.read_csv(am, encoding="utf-8-sig")
        sid = {int(r["cift_no"]): r["saha_id"] for _, r in a.iterrows()}
    for _, r in c[c["tur"] == "V1"].iterrows():
        out.append((sid.get(int(r["cift_no"]), f"v1-{int(r['cift_no'])}"), float(r["enlem"]), float(r["boylam"])))
    mp = KOD / "site_girdi" / "mission_prep.csv"
    if mp.exists():
        m = pd.read_csv(mp, encoding="utf-8-sig")
        for _, r in m.iterrows():
            if str(r.get("kalite", "")).strip() in ("K1", "K2") and pd.notna(r.get("enlem")) and pd.notna(r.get("boylam")):
                out.append((r["id"], float(r["enlem"]), float(r["boylam"])))
    tek = {}
    for i, la, lo in out:
        tek.setdefault(i, (la, lo))
    return [(i, la, lo) for i, (la, lo) in tek.items()]


def puanla(D, hz, Dk, eK, j, olcek, R1, R28, diy28, gorev, Kon, X, analoglar):
    """Bir hedef ve görev için belge 7.1–7.4 akışı: kapı → ön eleme → s_k, ζ_k → P, Q (topolojisiz) → ilk 30'da topoloji →
    yeniden sıralama → Top-3 / ilk 10 (≥ 100 km) → şampiyonlar → duyarlılık → ε*."""
    import onele
    import ozellik_topo as T
    import ozellik_topoloji as TP
    import puan as Pn
    import teorem as TM
    gT = hz["govde"]
    if gorev == "ice" and not hz["islak"]:
        return {"durum": "not applicable", "neden": "dry target (π⁺ < 0.5)"}
    G, durum, bilgi = kapilar(D, gorev, hz, X)
    KT = hedef_kategorileri(hz)
    agac = onele.Agac(olcek, D.z, G, kimlik=D.kim)
    idx, _, _ = agac.sorgu(hz["z"], Kon)
    n = len(idx)
    S = np.full((n, 8), np.nan); Zt = np.full((n, 8), np.nan); Dm = np.full((n, 8), np.nan)
    # kategori 1 (R(1) = 2000)
    p1 = {int(v): q for q, v in enumerate(R1)}
    p28 = {int(v): q for q, v in enumerate(R28)}
    rk1 = np.array([p1.get(int(i), -1) for i in idx])
    d1c = T.d1(D.Q1(idx), D.lnR[idx], hz["Q1"], float(hz["lnR"]), hz["iqr"])
    d1r = T.d1(D.Q1(R1), D.lnR[R1], hz["Q1"], float(hz["lnR"]), hz["iqr"])
    if KT[0]:
        S[:, 0], Zt[:, 0], Dm[:, 0] = Pn.s_k(d1c, d1r, rk1), Pn.zeta_k(d1c, d1r, rk1), d1c
    # kategori 3–7 (R = bütün E′), 8 (R(8) = 200)
    for k in (3, 4, 5, 6, 7):
        d = Dk[k][:, j]
        S[:, k - 1], Zt[:, k - 1], Dm[:, k - 1] = Pn.s_k(d[idx], d, idx), Pn.zeta_k(d[idx], d, idx), d[idx]
    rk8 = np.array([p28.get(int(i), -1) for i in idx])
    d8 = Dk[8][:, j]
    S[:, 7], Zt[:, 7], Dm[:, 7] = Pn.s_k(d8[idx], d8[R28], rk8), Pn.zeta_k(d8[idx], d8[R28], rk8), d8[idx]
    # uygunluk (topoloji: DEM tamsa hesaplanabilir)
    KE = np.isfinite(S); KE[:, 1] = D.dem_tam[idx] & KT[1]
    uyg = __import__("kapi").uygun(KE, KT)
    w = Pn.gorev_agirligi(gorev)
    P0, Q0 = Pn.P_Q(S, Zt, w, uyg)
    sira0 = Pn.sirala(P0, Q0, D.kim[idx])
    ilk30 = np.array([i for i in sira0 if uyg[i]][:Pn.TOPOLOJI_ADAY], int)
    # kategori 2: ilk 30'da (R(2) = 200)
    if KT[1] and len(ilk30):
        dgc = dunya_diyagram(D, idx[ilk30])
        d2c = np.array([np.nan if x is None else TP.d2(x, hz["dg"]) for x in dgc])
        d2r = np.array([np.nan if x is None else TP.d2(x, hz["dg"]) for x in diy28])
        rk2 = np.array([p28.get(int(i), -1) for i in idx[ilk30]])
        S[ilk30, 1], Zt[ilk30, 1], Dm[ilk30, 1] = Pn.s_k(d2c, d2r, rk2), Pn.zeta_k(d2c, d2r, rk2), d2c
    else:
        d2r = None
    P, Q = Pn.P_Q(S, Zt, w, uyg)
    yeni = Pn.yeniden_sirala(ilk30, P, Q, D.kim[idx])
    lat, lon = D.lat[idx], D.lon[idx]
    ilk10 = Pn.aralikli_liste(yeni, lat, lon, 10, gecer=uyg)          # Q-12: 100 km kuralı ilk 10'da da
    # şampiyonlar (Q-2): uygun adaylar; k = 2 yalnız ilk 30
    mask = np.broadcast_to(uyg[:, None], S.shape).copy()
    m2 = np.zeros(n, bool); m2[ilk30] = True
    mask[:, 1] &= m2
    samp = Pn.sampiyonlar(S, Zt, D.kim[idx], mask)
    # duyarlılık (Q-13): ilk 30 üzerinde
    Pe, _ = Pn.P_Q(S, Zt, Pn.gorev_agirligi(gorev, "esit"), uyg)
    Pg = Pn.P_geometrik(S, w, uyg)
    duy = {}
    for ad, Pa in (("esit", Pe), ("geometrik", Pg)):
        sa = Pn.yeniden_sirala(ilk30, Pa, Q, D.kim[idx])
        t3 = Pn.aralikli_liste(sa, lat, lon, 3, gecer=uyg)
        duy[ad] = {"tau_b": Pn.kendall_tau_b(P[ilk30], Pa[ilk30]), "jaccard_top3": Pn.jaccard(D.kim[idx][ilk10[:3]], D.kim[idx][t3]),
                   "top3": [int(x) for x in D.kim[idx][t3]]}
    # ε* (belge 8.1) ilk 10 için
    refs1 = {"R": D.R[R1], "Omega_1": D.Om1[R1], "Omega_4": D.Om4[R1]}
    Tw = {"R": float(hz["R"]), "Omega_1": float(hz["Omega_1"]), "Omega_4": float(hz["Omega_4"])}
    kayit_satirlari = []
    for i in ilk10:
        e = int(idx[i])
        Ew = {"R": D.R[e], "Omega_1": D.Om1[e], "Omega_4": D.Om4[e]}
        dr = np.where(R1 == e, np.nan, d1r)
        eps1, b1 = TM.eps_yildiz(d1c[i], dr, lambda x: _psi1(x, Ew, "dunya", Tw, gT, hz["iqr"]),
                                 lambda x: _psi1(x, refs1, "dunya", Tw, gT, hz["iqr"]), "dunya")
        if d2r is not None and np.isfinite(Dm[i, 1]):
            dr2 = np.where(R28 == e, np.nan, d2r)
            eps2, b2 = TM.eps_yildiz(Dm[i, 1], dr2, lambda x: _psi2(x, D.R[e], "dunya", float(hz["R"]), gT),
                                     lambda x: _psi2(x, D.R[R28], "dunya", float(hz["R"]), gT), "dunya")
        else:
            eps2, b2 = None, {"durum": "topoloji yok"}
        import puan as Pn2
        yakin = None
        if analoglar:
            dd = Pn2.gc_km(lat[i], lon[i], np.array([a[1] for a in analoglar]), np.array([a[2] for a in analoglar]))
            m = int(np.argmin(dd)); yakin = {"id": analoglar[m][0], "km": round(float(dd[m]), 1)}
        eksik = []
        for k in range(8):
            if np.isfinite(S[i, k]):
                eksik.append(None)
            elif not KT[k]:
                eksik.append("iki_taraf" if not eK[e, k] else "hedef")
            else:
                eksik.append("dunya")
        kayit_satirlari.append({
            "kimlik": int(D.kim[e]), "enlem": round(float(lat[i]), 4), "boylam": round(float(lon[i]), 4),
            "P": float(P[i]), "Q": float(Q[i]), "s": [None if not np.isfinite(v) else float(v) for v in S[i]],
            "d": [None if not np.isfinite(v) else float(v) for v in Dm[i]], "kapsama": float(np.isfinite(S[i]).sum() / 8),
            "eksik_taraf": eksik, "kapi_durumu": str(durum[e]), "eps1": eps1, "eps1_durum": b1["durum"],
            "eps2": eps2, "eps2_durum": b2["durum"], "en_yakin_analog": yakin})
    samp_out = []
    for k in range(8):
        i = samp[k]
        samp_out.append(None if i < 0 else {"kimlik": int(D.kim[idx][i]), "enlem": round(float(lat[i]), 4),
                                              "boylam": round(float(lon[i]), 4), "s": float(S[i, k]), "d": float(Dm[i, k])})
    return {"durum": "computed", "kapi_yedek": bool(bilgi.get("yedek", False)), "kapi_bilgi": {k: v for k, v in bilgi.items() if k != "X"},
            "E_g": int(G.sum()), "aday": n, "uygun": int(uyg.sum()), "ilk10": kayit_satirlari, "sampiyonlar": samp_out,
            "duyarlilik": duy, "esitlik_payi_ilk30": {str(k + 1): float(np.mean(S[ilk30, k] == np.nanmax(S[ilk30, k])))
                                                       if np.isfinite(S[ilk30, k]).any() else None for k in range(8)}}


def katman_a(kimlikler, cikti, Kon):
    """P4–P6 verilen liste hedefleri için; her hedefin JSON'u bitince yazılır (sonuc\\<cikti>\\liste_<kimlik>.json)."""
    import pandas as pd
    import onele
    t0 = time.time()
    D = Dunya()
    olcek = onele.Olcek(D.z)
    R1, R28 = referans_kumeleri(D.n)
    diy28 = ref_diyagramlari(D, R28)
    hedefler = pd.read_csv(KOD / "hedefler.csv", encoding="utf-8-sig").dropna(subset=["kimlik"])
    ciftler = pd.read_csv(KOD / "dogrulama_ciftleri.csv", encoding="utf-8-sig")
    gerek = set(kimlikler) | set(ciftler.loc[ciftler["gorev"] == "geology", "hedef_kimlik"])
    hz = {}
    for _, r in hedefler[hedefler["kimlik"].isin(gerek)].iterrows():
        t = time.time()
        hz[r["kimlik"]] = hedef_hazirla(r.to_dict())
        print(f"   hedef hazır: {r['kimlik']} ({time.time() - t:.0f} s)", flush=True)
    (X_tam, loo), paylar = X_hesapla(D, hz, ciftler)
    print(f"   X = {X_tam:.4f} (Geology çiftleri: {paylar})", flush=True)
    sira = [k for k in kimlikler if k in hz]
    Dk, eK = dunya_uzakliklari(D, [hz[k] for k in sira])
    analoglar = bilinen_analoglar()
    kl = SONUC / cikti
    kl.mkdir(parents=True, exist_ok=True)
    sureler = {}
    for j, k in enumerate(sira):
        t = time.time()
        h = hz[k]
        out = {"hedef": {"kimlik": k, "ad": h["ad"], "cisim": h["govde"], "enlem": h["enlem"], "boylam": h["boylam"],
                         "kaynak": h["kaynak"], "islak": h["islak"], "pi_arti": None if not np.isfinite(h["pi_arti"]) else h["pi_arti"],
                         "kategori_var": [bool(x) for x in hedef_kategorileri(h)], "F5": h["F5"]},
               "parametre": {"K_on": Kon, "hedef_merkez": HEDEF_MERKEZ, "X": X_tam}, "gorevler": {}}
        for g in GOREVLER:
            out["gorevler"][g] = puanla(D, h, Dk, eK, j, olcek, R1, R28, diy28, g, Kon, X_tam, analoglar)
        (kl / f"liste_{k}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
        sureler[k] = round(time.time() - t, 1)
        print(f"   {k}: {sureler[k]} s → sonuc\\{cikti}\\liste_{k}.json", flush=True)
    sure_yaz("katman_A", cikti=cikti, hedef=len(sira), K_on=Kon, sure_s=round(time.time() - t0, 1), hedef_sure=sureler)
    return sureler


def d6():
    """Belge 17.5 D6 pilot: Jezero, Apollo 15, bir Artemis bölgesi (A3-03 Malapert). Kön: V5'ten önce adayların en büyüğü (800)."""
    import onele
    return katman_a(["R-JEZ", "M-A15", "A3-03"], "pilot", max(onele.K_ON_ADAYLARI))


if __name__ == "__main__":
    main()
''', encoding="utf-8")
r = subprocess.run([sys.executable, str(KOD / "kos.py"), "--help"], cwd=KOD, capture_output=True, text=True)
print(r.stdout.splitlines()[0] if r.stdout else r.stderr)
assert r.returncode == 0 and "d6" in r.stdout, "komut satırı denetimi geçmedi"
with open(KAYIT / "degisiklik.md", "a", encoding="utf-8") as f:
    f.write("- 2026-11-14 | kos.py d6 NameError: __main__ bloğu 2. parçanın önünde kalmıştı → sona taşındı; komut satırı denetimi | iç iş\n")
print("kos.py komut satırı: PASS")
