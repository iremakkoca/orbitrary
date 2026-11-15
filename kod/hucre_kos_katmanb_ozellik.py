# Developed with assistance from Claude (Anthropic).
# kos.py: Katman B hedef tarafı (P3B: Ay ve Mars'ın bütün pencereleri + diyagramlar) + test; MAKALEYİ ETKİLER 74–75.
import sys, subprocess, importlib, shutil, time
from pathlib import Path
KOK = Path.home() / "orbitrary"; KOD, KAYIT, ARA = KOK / "kod", KOK / "kayit", KOK / "ara"
shutil.copy2(KOD / "kos.py", KAYIT / f"kos_yedek_{time.strftime('%H%M')}.py")
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
def p3_blok(govde, phi0, lam0, diy=None):
    """Belge 6.1–6.8, 7.1: topografya (yüzdelik vektörleri, ln R, Ω, R), topoloji sayıları (n↓, n↑), z vektörü,
    kategori 3–8 temsilleri; Dünya'da hareket kapısı değişkeni (W°'da θ < 20° oranı).
    Ay/Mars (Katman B hedefi): ayrıca 6 topografya alanının ham değerleri (ham_<f>; IQR_T için, belge 6.1) ve
    diy listesi verilirse pencerelerin H₀ diyagramları (topoloji, belge 6.2)."""
    import onele
    import ozellik_diger as OD
    import ozellik_topo as T
    import ozellik_topoloji as TP
    r = _r(govde)
    h, _, _ = K.hucreye(K.ac(DEM[govde]), phi0, lam0, r, genisletme=T.GEN)
    oz = T.ozellikler(h, govde)
    W = h[:, T.GEN:-T.GEN, T.GEN:-T.GEN]
    dgl = [TP.diyagramlar(W[w], govde) for w in range(len(phi0))]
    n2 = np.array([TP.n_onemli(d, govde) for d in dgl], float)
    if diy is not None:
        diy.extend(dgl)
    z = np.column_stack([np.asarray(T.z_topo(oz), float).reshape(len(phi0), 4), n2])
    out = {"Q1": T.yuzdelik_vektorleri(oz).astype(np.float32), "lnR": np.asarray(oz["lnR"], np.float32),
           "R": np.asarray(oz["R"], np.float32), "Omega_1": np.asarray(oz["Omega_1"], np.float32),
           "Omega_4": np.asarray(oz["Omega_4"], np.float32), "dem_tam": np.asarray(oz["dem_tam"], np.uint8),
           "z": z.astype(np.float64)}
    assert out["z"].shape == (len(phi0), len(onele.BILESENLER))
    if govde != "dunya":
        for f in T.OZELLIKLER:
            out[f"ham_{f}"] = np.asarray(oz[f], np.float32).reshape(len(phi0), -1)
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
    elif asama == "p3b":
        kim = np.load(ARA / f"p3b_{govde}_kimlik.npy")
        p, l = _radyan(df, kim)
        depo = Depo(ARA / f"p3b_{govde}", len(kim), isci=no)
        bloklari_kos(depo, _p3b_fonk(govde, p, l), f"P3B {govde} işçi {no}", isci_no=no, isci_sayi=sayi)
    else:
        kim = _p3_kimlik(govde)
        p, l = _radyan(df, kim)
        depo = Depo(ARA / f"p3_{govde}", len(kim), isci=no)
        bloklari_kos(depo, lambda a, z: p3_blok(govde, p[a:z], l[a:z]), f"P3 {govde} işçi {no}", isci_no=no, isci_sayi=sayi)


def _p3b_fonk(govde, p, l):
    """Katman B hedef tarafı: bir blok = p3_blok + aynı bloğun diyagram dosyası (ara\\diyagram_<govde>). Diyagram
    dosyası blok 'bitti' işaretinden önce yazılır; kesilirse blok yeniden yapılır (aynı sonuç)."""
    kl = ARA / f"diyagram_{govde}"

    def f(a, z):
        dgl = []
        out = p3_blok(govde, p[a:z], l[a:z], diy=dgl)
        assert len(dgl) == z - a
        _diy_blok_yaz(a // BLOK, dgl, np.asarray(out["z"])[:, 4:6], kl=kl, govde=govde)
        return out
    return f


def katmanb_ozellik(isci_sayi, govdeler=("ay", "mars")):
    """P3 (Katman B, belge 3.2): Ay ve Mars'ın BÜTÜN ızgara pencerelerinin özellikleri + diyagramları, paralel.
    Kaldığı yerden devam. İlk blok yazıldıktan sonra disk yeri denetlenir (yetmezse durur)."""
    import shutil
    for g in govdeler:
        t0 = time.time()
        df = izgara(g)
        n = len(df)
        kim = np.arange(n, dtype=np.int64)
        kp = ARA / f"p3b_{g}_kimlik.npy"
        if kp.exists():
            assert np.array_equal(np.load(kp), kim)
        else:
            np.save(kp, kim)
        (ARA / f"diyagram_{g}").mkdir(parents=True, exist_ok=True)
        p, l = _radyan(df, kim)
        fonk = _p3b_fonk(g, p, l)
        depo = Depo(ARA / f"p3b_{g}", n)
        if not depo.bitti_hepsi().any():
            depo.yaz(0, fonk(0, min(n, BLOK)))
        kalan_blok = int((~Depo(ARA / f"p3b_{g}", n).bitti_hepsi()).sum())
        gerek = _bayt(Depo(ARA / f"p3b_{g}", n)) * n * 1.15 * kalan_blok / depo.nb
        bos = shutil.disk_usage(ARA).free
        print(f"   {g}: {n} pencere; disk gereken ≈ {gerek / 1e9:.1f} GB, boş {bos / 1e9:.1f} GB", flush=True)
        assert bos > gerek, f"disk yetmiyor ({g}): {gerek / 1e9:.1f} GB gerekli, {bos / 1e9:.1f} GB boş"
        s = paralel("p3b", g, ARA / f"p3b_{g}", n, isci_sayi, fonk)
        nb = (n + BLOK - 1) // BLOK
        assert len(list((ARA / f"diyagram_{g}").glob("blok_?????.npz"))) == nb, "diyagram dosyası eksik"
        sure_yaz("P3B", govde=g, pencere=n, sure_s=round(time.time() - t0, 1), isci=isci_sayi)
        print(f"   bitti: {g} ({(time.time() - t0) / 60:.1f} dk)", flush=True)


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
    ap.add_argument("asama", choices=["p0", "p1", "p2", "p3", "d5", "dunya", "isci", "d6", "diyagram", "diyagram_isci", "d7", "v5", "katmanb_ozellik"])
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
    if a.asama == "diyagram_isci":
        diyagram_isci(a.isci_no, a.isci_sayi)
        return
    if a.asama == "diyagram":
        diyagram(a.isci)
        print(f"bitti: diyagram ({(time.time() - t) / 60:.1f} dk)")
        return
    if a.asama == "dunya":
        dunya(a.isci)
    elif a.asama == "katmanb_ozellik":
        katmanb_ozellik(a.isci)
    elif a.asama == "d7":
        d7()
    elif a.asama == "v5":
        v5()
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
HEDEF_MERKEZ = "koordinat"   # Q-17 (karar, madde 63): liste hedefinin penceresi hedef koordinatına ortalanır


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


_DIY = None


def dunya_diyagram(D, idx):
    """E′ indeksleri için diyagramlar: önbellekte (kos.py diyagram) varsa oradan, yoksa DEM'den (aynı hesap)."""
    import ozellik_topoloji as TP
    global _DIY
    idx = np.asarray(idx, int)
    if all((DIY_KL / f"blok_{int(i) // BLOK:05d}.npz").exists() for i in idx):
        _DIY = _DIY or DiyagramDeposu()
        return [_DIY[i] for i in idx]
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


def _konum(n, R):
    """E′ satırı → R içindeki sırası (R'de değilse −1)."""
    k = np.full(n, -1, np.int64)
    k[np.asarray(R, np.int64)] = np.arange(len(R))
    return k


def skor_topolojisiz(D, Dk, j, idx, d1c, d1r, R1, R28, KT):
    """Belge 5.4: idx adayları için s_k, ζ_k, d_k (kategori 1, 3–8; 2 boş) ve uygunluk (7.2; topoloji 'DEM tamsa
    hesaplanabilir'). Katman A (puanla) ve V5 aynı fonksiyonu kullanır (Q-5: iki taraf aynı puan).
    R(1) = 2000, R(3..7) = bütün E′, R(8) = R(2) = 200. Aday kendi referans kümesinden çıkar (ref_konum)."""
    import kapi
    import puan as Pn
    idx = np.asarray(idx, np.int64)
    n = len(idx)
    S = np.full((n, 8), np.nan); Zt = np.full((n, 8), np.nan); Dm = np.full((n, 8), np.nan)
    if KT[0]:
        rk1 = _konum(D.n, R1)[idx]
        S[:, 0], Zt[:, 0], Dm[:, 0] = Pn.s_k(d1c, d1r, rk1), Pn.zeta_k(d1c, d1r, rk1), d1c
    for k in (3, 4, 5, 6, 7):
        d = Dk[k][:, j]
        S[:, k - 1], Zt[:, k - 1], Dm[:, k - 1] = Pn.s_k(d[idx], d, idx), Pn.zeta_k(d[idx], d, idx), d[idx]
    rk8 = _konum(D.n, R28)[idx]
    d8 = Dk[8][:, j]
    S[:, 7], Zt[:, 7], Dm[:, 7] = Pn.s_k(d8[idx], d8[R28], rk8), Pn.zeta_k(d8[idx], d8[R28], rk8), d8[idx]
    KE = np.isfinite(S); KE[:, 1] = np.asarray(D.dem_tam)[idx] & KT[1]
    return S, Zt, Dm, kapi.uygun(KE, KT)


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
    d1c = T.d1(D.Q1(idx), D.lnR[idx], hz["Q1"], float(hz["lnR"]), hz["iqr"])
    d1r = T.d1(D.Q1(R1), D.lnR[R1], hz["Q1"], float(hz["lnR"]), hz["iqr"])
    S, Zt, Dm, uyg = skor_topolojisiz(D, Dk, j, idx, d1c, d1r, R1, R28, KT)
    w = Pn.gorev_agirligi(gorev)
    P0, Q0 = Pn.P_Q(S, Zt, w, uyg)
    sira0 = Pn.sirala(P0, Q0, D.kim[idx])
    ilk30 = np.array([i for i in sira0 if uyg[i]][:Pn.TOPOLOJI_ADAY], int)
    # kategori 2: ilk 30'da (R(2) = 200)
    if KT[1] and len(ilk30):
        dgc = dunya_diyagram(D, idx[ilk30])
        d2c = np.array([np.nan if x is None else TP.d2(x, hz["dg"]) for x in dgc])
        d2r = np.array([np.nan if x is None else TP.d2(x, hz["dg"]) for x in diy28])
        rk2 = _konum(D.n, R28)[idx[ilk30]]
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


# ------------------------------------------------------------------ D7 kimlik testi (belge 17.5): Dünya–Dünya
def d7_kontrol(D, hz, e, o, Dk, j, R1, R28, diy28):
    """Hedef = E′ penceresi e. Şart: e listede ilk; hesaplanabilen her k'da d_k(e, T) = 0 ve s_k(e) belge 5.4
    tanımıyla birebir: s = (#{d_ref > 0} + ½ #{d_ref = 0}) / |R_k|. Eşit (d = 0) referans yoksa bu s_k = 1 demektir;
    varsa ½ eşitlik kuralı s_k'yi 1'in altına indirir (madde 71). Dönüş (geçti, ayrıntı)."""
    import ozellik_topo as T
    import ozellik_topoloji as TP
    KT = hedef_kategorileri(hz)
    ke = int(D.kim[e])
    satir = next((r for r in o["ilk10"] if r["kimlik"] == ke), None)
    ilk = bool(o["ilk10"] and o["ilk10"][0]["kimlik"] == ke)
    if satir is None:
        return False, {"ilk": False, "neden": "hedef penceresi ilk 10'da yok"}
    ref = {1: T.d1(D.Q1(R1), D.lnR[R1], hz["Q1"], float(hz["lnR"]), hz["iqr"]),
           2: np.array([np.nan if x is None else TP.d2(x, hz["dg"]) for x in diy28], float)}
    ref[1][np.asarray(R1) == e] = np.nan
    ref[2][np.asarray(R28) == e] = np.nan
    for k in (3, 4, 5, 6, 7):
        d = np.array(Dk[k][:, j], float); d[e] = np.nan; ref[k] = d
    d8 = np.array(Dk[8][np.asarray(R28), j], float); d8[np.asarray(R28) == e] = np.nan; ref[8] = d8
    kat, hepsi = [], ilk
    for k in range(1, 9):
        s, de = satir["s"][k - 1], satir["d"][k - 1]
        if not KT[k - 1]:
            kat.append({"k": k, "durum": "hedefte yok (null)", "s": s}); hepsi &= s is None
            continue
        if s is None or de is None:
            kat.append({"k": k, "durum": "HATA: hesaplanabilir ama null"}); hepsi = False
            continue
        dr = ref[k][np.isfinite(ref[k])]
        n0 = int(np.sum(dr == de))
        bek = (np.sum(dr > de) + 0.5 * n0) / len(dr)
        olcek_ = float(np.median(dr)) if len(dr) else 1.0
        ok = abs(de) <= 1e-6 * max(olcek_, 1e-12) and abs(s - bek) <= 1e-12
        kat.append({"k": k, "d_e": de, "s": s, "s_beklenen": float(bek), "esit_ref": n0, "n_ref": int(len(dr)),
                    "s_bir": bool(s == 1.0), "gecti": bool(ok)})
        hepsi &= ok
    return bool(hepsi), {"ilk": ilk, "kategoriler": kat}


D7_ALANLAR = ("Q1", "lnR", "R", "Omega_1", "Omega_4", "z", "q3", "x4_gecerli", "Q4", "Q6", "Q7", "Q8", "mob")


def _d7_saklanan(D, e, ad):
    tablo = {"Q1": lambda: D.Q1([e])[0], "lnR": lambda: D.lnR[e], "R": lambda: D.R[e], "Omega_1": lambda: D.Om1[e],
             "Omega_4": lambda: D.Om4[e], "z": lambda: D.z[e], "q3": lambda: D.q3[e], "x4_gecerli": lambda: D.x4g[e],
             "mob": lambda: D.mob[e]}
    return np.asarray(tablo[ad]() if ad in tablo else D.Q(ad)[e], float)


def d7():
    """Belge 17.5 D7: V1'in 8 farklı Dünya sahasının E′ penceresi hedef olarak verilir (görev: genel, Kön = 800).
    Önce hedef özellikleri DEM'den yeniden hesaplanır ve P2/P3 kaydıyla karşılaştırılır (hat tutarlılığı);
    sonra d7_kontrol. Çıktı sonuc\\dogrulama\\D7.json."""
    import pandas as pd
    import onele
    import ozellik_diger as OD
    t0 = time.time()
    D = Dunya()
    olcek = onele.Olcek(D.z)
    R1, R28 = referans_kumeleri(D.n)
    diy28 = ref_diyagramlari(D, R28)
    c = pd.read_csv(KOD / "dogrulama_ciftleri.csv", encoding="utf-8-sig")
    v1 = c[c["tur"] == "V1"].drop_duplicates("dunya_saha")
    H = Z.Halka("dunya")
    hzs, es, tutarlilik = [], [], {}
    for _, s in v1.iterrows():
        k = int(H.tikla(float(s["enlem"]), float(s["boylam"])))
        assert k in D.konum, f"V1 sahası E′ dışında: {s['dunya_saha']}"
        e = D.konum[k]
        hz = hedef_hazirla({"kimlik": f"D7-{int(s['cift_no'])}", "ad": s["dunya_saha"], "cisim": "dunya",
                            "enlem": float(D.lat[e]), "boylam": float(D.lon[e]), "kaynak": "D7"})
        fark = {}
        alanlar = list(D7_ALANLAR) + [f"Q5_{f}" for f in OD.termal_ozellikleri("dunya", 0.0)]
        for ad in alanlar:
            a, b = np.asarray(hz[ad], float), _d7_saklanan(D, e, ad)
            assert a.shape == b.shape, (ad, a.shape, b.shape)
            assert np.array_equal(np.isnan(a), np.isnan(b)), f"{s['dunya_saha']} {ad}: NaN deseni farklı"
            m = np.isfinite(a)
            fark[ad] = float(np.max(np.abs(a[m] - b[m]))) if m.any() else 0.0
            assert np.allclose(a[m], b[m], rtol=1e-5, atol=1e-6), f"{s['dunya_saha']} {ad}: yeniden hesap ≠ kayıt ({fark[ad]})"
        tutarlilik[s["dunya_saha"]] = fark
        hzs.append(hz); es.append(e)
        print(f"   D7 hedef hazır: {s['dunya_saha']} (en büyük fark {max(fark.values()):.2e})", flush=True)
    Dk, eK = dunya_uzakliklari(D, hzs)
    Kon = max(onele.K_ON_ADAYLARI)
    sonuc, gecti = {}, True
    for j, (hz, e) in enumerate(zip(hzs, es)):
        o = puanla(D, hz, Dk, eK, j, olcek, R1, R28, diy28, "genel", Kon, 0.0, [])
        g, ay = d7_kontrol(D, hz, e, o, Dk, j, R1, R28, diy28)
        sonuc[hz["ad"]] = {"gecti": g, **ay, "en_buyuk_fark": max(tutarlilik[hz["ad"]].values())}
        gecti &= g
        print(f"   D7 {hz['ad']}: {'PASS' if g else 'FAIL'}  ilk={ay['ilk']}  "
              f"s=1 olan: {sum(1 for x in ay.get('kategoriler', []) if x.get('s_bir'))}/"
              f"{sum(1 for x in ay.get('kategoriler', []) if 's_bir' in x)}", flush=True)
    kl = SONUC / "dogrulama"; kl.mkdir(parents=True, exist_ok=True)
    out = {"gecti": bool(gecti), "K_on": Kon, "gorev": "genel", "sahalar": sonuc, "tutarlilik": tutarlilik,
           "sure_dk": round((time.time() - t0) / 60, 1)}
    (kl / "D7.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    sure_yaz("D7", gecti=bool(gecti), sure_s=round(time.time() - t0, 1))
    print("D7:", "PASS" if gecti else "FAIL", "→ sonuc\\dogrulama\\D7.json", flush=True)
    return gecti


# ------------------------------------------------------------------ V5 (belge 8.3): ön elemenin kaybı, Kön seçimi
def d1_tum(D, hedefler, parca=2048):
    """Kategori 1 uzaklığı bütün E′ × hedefler (belge 6.1); Q1 bir kez okunur."""
    import ozellik_topo as T
    out = np.empty((D.n, len(hedefler)))
    for a in range(0, D.n, parca):
        z = min(D.n, a + parca)
        Q = np.asarray(D.Q1(np.arange(a, z)), float)
        for j, h in enumerate(hedefler):
            out[a:z, j] = T.d1(Q, D.lnR[a:z], h["Q1"], float(h["lnR"]), h["iqr"])
    return out


def v5_hedef(D, hz, Dk, j, d1t, R1, R28, agac, Klar):
    """Q-5: topolojisiz, görev genel. Top-3_{E′}: bütün E′'nin tam sıralamasından 7.4 kuralıyla (100 km) ilk 3.
    E_K: z uzayında en yakın K (görev seçilmemiş → E′_g = E′). recall = |Top-3 ∩ E_K| / 3."""
    import dogrula as DG
    import puan as Pn
    KT = hedef_kategorileri(hz)
    ar = np.arange(D.n)
    S, Zt, _, uyg = skor_topolojisiz(D, Dk, j, ar, d1t, d1t[np.asarray(R1)], R1, R28, KT)
    P0, Q0 = Pn.P_Q(S, Zt, Pn.gorev_agirligi("genel"), uyg)
    sira = Pn.sirala(P0, Q0, D.kim)
    top3 = Pn.aralikli_liste(sira, D.lat, D.lon, 3, gecer=uyg)
    assert len(top3) == 3, "tam sıralamada 3 uygun aday yok"
    satir, _, _ = agac.sorgu(hz["z"], max(Klar))
    satir = np.asarray(satir)
    return {"top3": [int(D.kim[i]) for i in top3], "top3_P": [float(P0[i]) for i in top3], "uygun": int(uyg.sum()),
            "recall": {str(K): DG.recall(top3, satir[:K]) for K in Klar}}


V5_KL = ARA / "v5"


def v5(grup=50):
    """Belge 8.3 V5 + Q-4, Q-9, Q-10: 100 Ay + 100 Mars rastgele ızgara penceresi (alt tohum V5). Her hedef bitince
    ara\\v5\\ altına yazılır (kesilirse aynı komutla devam). Çıktı sonuc\\dogrulama\\V5.json (Kön, r̄, GA)."""
    import pickle
    import onele
    import dogrula as DG
    t0 = time.time()
    V5_KL.mkdir(parents=True, exist_ok=True)
    D = Dunya()
    olcek = onele.Olcek(D.z)
    agac = onele.Agac(olcek, D.z, None, kimlik=D.kim)
    R1, R28 = referans_kumeleri(D.n)
    Klar = tuple(onele.K_ON_ADAYLARI)
    satirlar = []
    secim = DG.rastgele_hedefler(len(izgara("ay")), len(izgara("mars")), "V5")
    for g, ids in zip(("ay", "mars"), secim):
        df = izgara(g)
        la, lo = df["enlem"].to_numpy(), df["boylam"].to_numpy()
        for i in ids:
            satirlar.append({"kimlik": f"V5-{g}-{int(i)}", "ad": f"V5 {g} {int(i)}", "cisim": g,
                             "enlem": float(la[i]), "boylam": float(lo[i]), "kaynak": "V5 (alt tohum V5)"})
    assert len(satirlar) == 200
    # 1) hedef pencereleri (önbellekli)
    hz = {}
    for q, s in enumerate(satirlar):
        p = V5_KL / f"{s['kimlik']}.pkl"
        if p.exists():
            hz[s["kimlik"]] = pickle.loads(p.read_bytes())
        else:
            h = hedef_hazirla(s)
            gecici = p.with_suffix(".tmp"); gecici.write_bytes(pickle.dumps(h)); gecici.replace(p)
            hz[s["kimlik"]] = h
        if (q + 1) % 10 == 0:
            gec = (time.time() - t0) / 60
            print(f"   V5 hedef: {q + 1}/200  geçen {gec:.0f} dk", flush=True)
    # 2) gruplar halinde Dünya uzaklıkları + tam sıralama
    kalan = [s["kimlik"] for s in satirlar if not (V5_KL / f"{s['kimlik']}.json").exists()]
    for a in range(0, len(kalan), grup):
        ks = kalan[a:a + grup]
        hg = [hz[k] for k in ks]
        Dk, _ = dunya_uzakliklari(D, hg)
        d1t = d1_tum(D, hg)
        for j, k in enumerate(ks):
            r = v5_hedef(D, hz[k], Dk, j, d1t[:, j], R1, R28, agac, Klar)
            (V5_KL / f"{k}.json").write_text(json.dumps(r), encoding="utf-8")
        del Dk, d1t
        print(f"   V5 sıralama: {min(a + grup, len(kalan))}/{len(kalan)}  geçen {(time.time() - t0) / 60:.0f} dk", flush=True)
    # 3) özet
    sonuc = {s["kimlik"]: json.loads((V5_KL / f"{s['kimlik']}.json").read_text(encoding="utf-8")) for s in satirlar}
    ort, ga = {}, {}
    for K in Klar:
        m, alt, ust = onele.recall_ozet([sonuc[k]["recall"][str(K)] for k in sonuc])
        ort[K], ga[K] = m, (alt, ust)
    Kon, saglandi = onele.kon_sec(ort)
    out = {"hedef_sayisi": len(sonuc), "alt_tohum": "V5", "recall_ort": {str(K): ort[K] for K in Klar},
           "recall_GA95": {str(K): list(ga[K]) for K in Klar}, "K_on": int(Kon), "esik_saglandi": bool(saglandi),
           "esik": float(onele.RECALL_ESIGI), "hedefler": sonuc, "sure_dk": round((time.time() - t0) / 60, 1)}
    kl = SONUC / "dogrulama"; kl.mkdir(parents=True, exist_ok=True)
    (kl / "V5.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    sure_yaz("V5", K_on=int(Kon), esik_saglandi=bool(saglandi), sure_s=round(time.time() - t0, 1))
    for K in Klar:
        print(f"   Kön={K}: r̄ = {ort[K]:.3f}  (%95 GA {ga[K][0]:.3f}–{ga[K][1]:.3f})", flush=True)
    print(f"V5: Kön = {Kon} ({'eşik sağlandı' if saglandi else 'eşik sağlanmadı → 800 (Q-9)'}) → sonuc\\dogrulama\\V5.json")
    return Kon, saglandi


def kon_oku():
    """Uzun koşunun Kön'ü: sonuc\\dogrulama\\V5.json (yoksa durur)."""
    p = SONUC / "dogrulama" / "V5.json"
    assert p.exists(), "V5 henüz koşmadı: python kos.py v5"
    v = json.loads(p.read_text(encoding="utf-8"))
    assert v["hedef_sayisi"] == 200
    return int(v["K_on"])


# ------------------------------------------------------------------ Dünya diyagram önbelleği (belge 7.1: "Dünya tarafı sabit
# olduğu için bütün Dünya özellikleri, diyagramları ve sıraları önceden hesaplanıp saklanır")
DIY_KL = ARA / "diyagram_dunya"


def _diy_blok_yaz(b, dglar, z_beklenen, kl=None, govde="dunya"):
    """Blok: her pencere için Dgm↓, Dgm↑ (float64 (n, 2)) ve R_top; tek npz (önce geçici ad, sonra yeniden adlandırma).
    Denetim: n↓, n↑ P3'te z'ye yazılanla birebir aynı olmalı."""
    import ozellik_topoloji as TP
    na, nu, Rt, A_, U_ = [], [], [], [], []
    for i, d in enumerate(dglar):
        if d is None:
            na.append(0); nu.append(0); Rt.append(np.nan)
            continue
        A_.append(d[0]); U_.append(d[1]); na.append(len(d[0])); nu.append(len(d[1])); Rt.append(d[2])
        n2 = TP.n_onemli(d, govde)
        assert (n2[0], n2[1]) == (int(z_beklenen[i, 0]), int(z_beklenen[i, 1])), ("diyagram P3 ile tutmuyor", b, i)
    kl = DIY_KL if kl is None else kl
    tmp = kl / f"blok_{b:05d}.tmp.npz"
    np.savez(tmp, na=np.array(na), nu=np.array(nu), Rt=np.array(Rt),
             A=np.concatenate(A_) if A_ else np.zeros((0, 2)), U=np.concatenate(U_) if U_ else np.zeros((0, 2)))
    tmp.replace(kl / f"blok_{b:05d}.npz")


def diyagram_isci(no, sayi, blok=BLOK):
    import ozellik_topoloji as TP
    kim = np.load(ARA / "p3_dunya_kimlik.npy")
    df = izgara("dunya")
    p, l = _radyan(df, kim)
    z = np.asarray(Depo(ARA / "p3_dunya", len(kim)).oku("z"))[:, 4:6]
    nb = (len(kim) + blok - 1) // blok
    t0 = time.time(); say = 0
    for b in range(no, nb, sayi):
        if (DIY_KL / f"blok_{b:05d}.npz").exists():
            continue
        a, e = b * blok, min(len(kim), (b + 1) * blok)
        h, _, _ = K.hucreye(K.ac("etopo"), p[a:e], l[a:e], _r("dunya"))
        _diy_blok_yaz(b, [TP.diyagramlar(h[w], "dunya") for w in range(e - a)], z[a:e])
        say += 1
        if say % 20 == 0:
            print(f"   diyagram işçi {no}: {say} blok, {(time.time() - t0) / 60:.1f} dk", flush=True)


def diyagram(isci_sayi):
    """Bütün E′ için H₀ diyagramları (Katman A ilk 30 ve Katman B için). Paralel, kaldığı yerden devam."""
    import os
    import subprocess
    DIY_KL.mkdir(parents=True, exist_ok=True)
    kim = np.load(ARA / "p3_dunya_kimlik.npy")
    nb = (len(kim) + BLOK - 1) // BLOK
    ortam = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", PYTHONIOENCODING="utf-8")
    kl = KAYIT / "isci"; kl.mkdir(exist_ok=True)
    t0 = time.time()
    ps = []
    for i in range(isci_sayi):
        log = open(kl / f"diyagram_{i}.txt", "a", encoding="utf-8")
        ps.append((subprocess.Popen([sys.executable, "-u", str(KOD / "kos.py"), "diyagram_isci", "--isci-no", str(i),
                                     "--isci-sayi", str(isci_sayi)], cwd=KOD, env=ortam, stdout=log, stderr=subprocess.STDOUT), log))
    b0 = len(list(DIY_KL.glob("blok_?????.npz")))
    while any(p.poll() is None for p, _ in ps):
        time.sleep(60)
        b = len(list(DIY_KL.glob("blok_?????.npz")))
        hiz = (b - b0) / max(time.time() - t0, 1)
        print(f"   diyagram: {b}/{nb} blok  geçen {(time.time() - t0) / 60:.0f} dk  kalan ≈ "
              f"{(nb - b) / hiz / 60 if hiz > 0 else float('nan'):.0f} dk", flush=True)
    for p, log in ps:
        log.close()
    assert all(p.returncode == 0 for p, _ in ps), "işçi hatası → kayit\\isci\\diyagram_<i>.txt"
    assert len(list(DIY_KL.glob("blok_?????.npz"))) == nb, "eksik blok; aynı komutla yeniden başlat"
    sure_yaz("diyagram_dunya", pencere=len(kim), sure_s=round(time.time() - t0, 1), isci=isci_sayi)


class DiyagramDeposu:
    """Önbellekten pencerenin diyagramı: (Dgm↓, Dgm↑, R_top) ya da None. kl: Dünya (E′ sırası) ya da
    ara\\diyagram_<govde> (Katman B, ızgara sırası)."""

    def __init__(self, blok=BLOK, kl=None):
        self.blok = blok
        self.kl = DIY_KL if kl is None else kl
        self._b = {}

    def _yukle(self, b):
        if b not in self._b:
            z = np.load(self.kl / f"blok_{b:05d}.npz")
            na, nu = z["na"], z["nu"]
            self._b[b] = (z["A"], z["U"], z["Rt"], np.r_[0, np.cumsum(na)], np.r_[0, np.cumsum(nu)])
        return self._b[b]

    def __getitem__(self, i):
        b, k = divmod(int(i), self.blok)
        A_, U_, Rt, oa, ou = self._yukle(b)
        if not np.isfinite(Rt[k]):
            return None
        return A_[oa[k]:oa[k + 1]], U_[ou[k]:ou[k + 1]], float(Rt[k])


if __name__ == "__main__":
    main()
''', encoding="utf-8")
(KOD / "testler" / "test_kos_v5_d7.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""D7 (kimlik testi) ve V5 (ön elemenin kaybı) mantığı: sentetik Dünya ile (gerçek veri yok)."""
import numpy as np
import pytest

import kos
import onele
import ozellik_topo as T
import ozellik_topoloji as TP
from test_kos_puanla import RNG, _hedef, _sahte, nE


@pytest.fixture(scope="module")
def ortam():
    D = _sahte()
    x = np.arange(40) * 500.0
    diy = [TP.diyagramlar(150 * np.sin(x[None, :] / (2000 + 10 * i)) * np.cos(x[:, None] / 2600), "dunya", yontem="union_find")
           for i in range(200)]
    f = lambda i: diy[(int(i) * 7919) % 200]
    kos.dunya_diyagram = lambda D_, idx: [f(i) for i in idx]
    R = np.random.default_rng(9).permutation(nE)
    return D, onele.Olcek(D.z), R[:2000], R[:200], [f(i) for i in R[:200]], f


def test_skor_aday_kumesinden_bagimsiz(ortam):
    """Q-5 dayanağı: bir pencerenin s_k, ζ_k, uygunluğu aday kümesine bağlı değil (V5 tam sıralama = Katman A puanı)."""
    D, ol, R1, R28, diy, f = ortam
    hz = _hedef(True)
    Dk, _ = kos.dunya_uzakliklari(D, [hz], parca=700)
    KT = kos.hedef_kategorileri(hz)
    d1t = kos.d1_tum(D, [hz], parca=333)[:, 0]
    assert np.allclose(d1t, T.d1(D.Q1(np.arange(nE)), D.lnR, hz["Q1"], hz["lnR"], hz["iqr"]))
    St, Zt, Dt, ut = kos.skor_topolojisiz(D, Dk, 0, np.arange(nE), d1t, d1t[R1], R1, R28, KT)
    idx = np.sort(RNG.choice(nE, 300, replace=False))
    d1c = T.d1(D.Q1(idx), D.lnR[idx], hz["Q1"], hz["lnR"], hz["iqr"])
    d1r = T.d1(D.Q1(R1), D.lnR[R1], hz["Q1"], hz["lnR"], hz["iqr"])
    Sa, Za, Da, ua = kos.skor_topolojisiz(D, Dk, 0, idx, d1c, d1r, R1, R28, KT)
    assert np.allclose(St[idx], Sa, equal_nan=True, rtol=0, atol=1e-12)
    assert np.allclose(Zt[idx], Za, equal_nan=True, rtol=0, atol=1e-12)
    assert np.array_equal(ut[idx], ua) and np.isnan(St[:, 1]).all()


def test_v5_recall(ortam):
    D, ol, R1, R28, diy, f = ortam
    hz = [_hedef(True), _hedef(False)]
    Dk, _ = kos.dunya_uzakliklari(D, hz, parca=700)
    d1t = kos.d1_tum(D, hz)
    agac = onele.Agac(ol, D.z, None, kimlik=D.kim)
    Klar = (100, 200, 400, 800, nE)
    for j in range(2):
        r = kos.v5_hedef(D, hz[j], Dk, j, d1t[:, j], R1, R28, agac, Klar)
        rc = [r["recall"][str(K)] for K in Klar]
        assert all(0 <= x <= 1 for x in rc) and all(a <= b for a, b in zip(rc, rc[1:]))   # E_K iç içe → artan
        assert rc[-1] == 1.0                                                            # E_K = E′ → recall 1
        assert len(set(r["top3"])) == 3 and r["top3_P"] == sorted(r["top3_P"], reverse=True)
        # Top-3 elle: bütün E′ üzerinde P₀ en büyük (100 km kuralıyla)
        import puan as Pn
        KT = kos.hedef_kategorileri(hz[j])
        S, Z_, _, u = kos.skor_topolojisiz(D, Dk, j, np.arange(nE), d1t[:, j], d1t[R1, j], R1, R28, KT)
        P0, _ = Pn.P_Q(S, Z_, Pn.gorev_agirligi("genel"), u)
        assert r["top3_P"][0] == pytest.approx(np.nanmax(P0))


def test_d7_kimlik(ortam):
    """Hedef = sentetik Dünya penceresi e: e ilk sırada, d_k(e,T) = 0, s_k belge 5.4 tanımıyla (½ eşitlik dahil)."""
    D, ol, R1, R28, diy, f = ortam
    for e in (1234, 2500):
        hz = {"kimlik": "D7", "ad": f"w{e}", "govde": "dunya", "enlem": float(D.lat[e]), "boylam": float(D.lon[e]),
              "kaynak": "", "iqr": np.full(6, 0.5), "dg": f(e), "pi_arti": np.nan, "islak": False,
              "F5": ["tmax", "tort", "tgece", "iarti"], "Q1": D.Q1([e])[0], "lnR": float(D.lnR[e]), "R": float(D.R[e]),
              "Omega_1": float(D.Om1[e]), "Omega_4": float(D.Om4[e]), "q3": D.q3[e], "Q4": D.Q("Q4")[e],
              "x4_gecerli": float(D.x4g[e]), "Q6": D.Q("Q6")[e], "Q7": D.Q("Q7")[e], "Q8": D.Q("Q8")[e], "z": D.z[e]}
        for x in hz["F5"]:
            hz[f"Q5_{x}"] = D.Q(f"Q5_{x}")[e]
        Dk, eK = kos.dunya_uzakliklari(D, [hz], parca=700)
        o = kos.puanla(D, hz, Dk, eK, 0, ol, R1, R28, diy, "genel", 200, 0.0, [])
        g, ay = kos.d7_kontrol(D, hz, e, o, Dk, 0, R1, R28, diy)
        assert g and ay["ilk"], ay
        kat = {x["k"]: x for x in ay["kategoriler"]}
        assert kat[6]["durum"].startswith("hedefte yok")                   # kuru hedef: su/buz null (belge 6.6)
        assert all(kat[k]["d_e"] == 0 for k in (1, 3, 4, 5, 7, 8))
        assert kat[2]["esit_ref"] >= 0 and kat[1]["s_bir"]                  # sürekli dağılım: eşit referans yok → s = 1
    # bozuk durum: hedefin bir özelliği değişirse test FAIL vermeli
    e = 1234
    hz["Q4"] = D.Q("Q4")[e] + 0.5
    hz["kimlik"] = "D7b"
    Dk, eK = kos.dunya_uzakliklari(D, [hz], parca=700)
    o = kos.puanla(D, hz, Dk, eK, 0, ol, R1, R28, diy, "genel", 200, 0.0, [])
    g, ay = kos.d7_kontrol(D, hz, 2500, o, Dk, 0, R1, R28, diy)
    assert not g
''', encoding="utf-8")
(KOD / "testler" / "test_kos_katmanb.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Katman B hedef tarafı (P3B): ham topografya alanları (IQR_T için) ve diyagram dosyaları; sentetik DEM ile."""
import numpy as np

import kos
import ozellik_diger as OD
import ozellik_topo as T
import ozellik_topoloji as TP


def _dem(n, tohum=3):
    rng = np.random.default_rng(tohum)
    x = np.arange(56) * 500.0
    return np.stack([300 * np.sin(x[None, :] / (2500 + 97 * i)) * np.cos(x[:, None] / (3100 + 41 * i))
                     + rng.normal(0, 5, (56, 56)) for i in range(n)])


def _yamala(monkeypatch, h):
    monkeypatch.setattr(kos.K, "ac", lambda ad: ad)
    monkeypatch.setattr(kos.K, "hucreye", lambda kaynak, p, l, r, genisletme=0: (h[: len(p)], None, None))
    monkeypatch.setattr(OD, "pencere_temsili", lambda g, p, l: {"pi_arti": np.zeros(len(p))})
    monkeypatch.setattr(TP, "h0_gudhi", TP.h0_union_find)   # aynı sonuç (MAKALEYİ ETKİLER 5. bölüm); test GUDHI'siz de koşar


def test_p3_blok_ham_ve_diyagram(monkeypatch):
    n = 5
    h = _dem(n)
    _yamala(monkeypatch, h)
    dgl = []
    out = kos.p3_blok("ay", np.radians(np.linspace(-80, 80, n)), np.zeros(n), diy=dgl)
    oz = T.ozellikler(h, "ay")
    for f in T.OZELLIKLER:
        assert out[f"ham_{f}"].shape == (n, np.asarray(oz[f][0]).size)
        assert np.array_equal(out[f"ham_{f}"][2], np.asarray(oz[f][2], np.float32).ravel())
    assert len(dgl) == n
    assert all(TP.n_onemli(d, "ay") == tuple(int(v) for v in out["z"][i, 4:6]) for i, d in enumerate(dgl))
    # IQR_T ham alanlardan = belge 6.1'deki gibi pencere sözlüklerinden
    a = T.iqr_hedef([{f: out[f"ham_{f}"][i] for f in T.OZELLIKLER} for i in range(n)])
    b = T.iqr_hedef([{f: np.asarray(oz[f][i], np.float32) for f in T.OZELLIKLER} for i in range(n)])
    assert np.allclose(a, b)
    # Dünya bloğunda ham alan yok (Dünya kaydı değişmez)
    monkeypatch.setattr(kos, "kara_hucreleri", lambda p, l: np.ones((len(p), 40, 40)))
    import kapi
    monkeypatch.setattr(kapi, "degiskenler", lambda kara, egim_rad: {"mob": np.zeros(len(kara))})
    od = kos.p3_blok("dunya", np.zeros(2), np.zeros(2))
    assert not any(k.startswith("ham_") for k in od)


def test_p3b_fonk_diyagram_dosyasi(monkeypatch, tmp_path):
    n = 7
    h = _dem(n, 4)
    _yamala(monkeypatch, h)
    monkeypatch.setattr(kos, "ARA", tmp_path)
    (tmp_path / "diyagram_mars").mkdir()
    p, l = np.radians(np.linspace(-60, 60, n)), np.zeros(n)
    out = kos._p3b_fonk("mars", p, l)(0, n)
    dd = kos.DiyagramDeposu(kl=tmp_path / "diyagram_mars")
    W = h[:, T.GEN:-T.GEN, T.GEN:-T.GEN]
    for i in range(n):
        a, b = dd[i], TP.diyagramlar(W[i], "mars")
        assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1]) and a[2] == b[2]
    assert out["ham_theta_1"].shape == (n, 1600)
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
| 56 | **K1 — karar (İrem, 14:19, proje sahibi):** Katman B (tıklama haritası, 3D küre) **Ay ve Mars'ın ikisinde de** yapılır; K1'in "yalnız Ay" seçeneği uygulanmaz. Katman A (bütün Ay ve Mars hedefleri, 8 kategori), V1 analog doğrulaması ve analog saha yorumları zaten hiçbir koşulda düşmez (17.5). D5 tek süreç ölçümü (özellik kısmı 12,1 sa) paralel işçilerle (4–6) karşılanır; sonuç tek süreçliyle aynı. Belge 11 K1'den sapma olduğu için makalede Implementation'da tek cümle: "Layer B was computed for both bodies using parallel workers (results identical to a single-process run)." | 3.2, 11 K1, 17.5 | Yalnız koşu düzeni | karar verildi; Emir/Sude bilgilendirilir |
| 57 | İç iş: P2/P3 paralel işçilerle (blok mod K); aynı fonksiyon, aynı bloklar, sonuç tek süreçliyle birebir aynı (testle) | 17.5 | Hayır | — |

## 16. Dünya özellikleri (P2–P3, 15:45) ve site metinleri

P2 + P3 Dünya bitti (5 işçi; P2 5 dk, P3 66 dk; toplam 73,3 dk). |E′| = 346 064 (Dünya 1 275 482 pencerenin %27,1'i). Kategori kapsaması (E′ içinde, 1000 noktanın hepsi dolu): topografya, termal (4 özellik), aydınlanma %100; jeoloji %99,99; mineraloji %99,96; su/buz %90,2 (kar/buz ≥ 0,5 buz tabakası hücreleri hesap dışı, belge 6.6); toz %90,3 (SoilGrids Antarktika'yı kapsamaz, belge 6.7). Bütün pencerelerde DEM tam. z bileşenlerinin hiçbirinde MAD = 0 çıkmadı (Q-1 tetiklenmedi): n↓ ortanca 2 (MAD 2), n↑ ortanca 5 (MAD 5). Kesin sayılar kayit\P3_dunya_ozet.json → ozet.json.

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 58 | **Ad kuralı:** makalede "Overall", "Ice & Resources", "dust and surface" geçiyor; belge 2.3'e göre adlar her yerde metin.json'daki gibi: General, Mobility test, Geology, Ice & resources, Astrobiology; Topography … Dust, Illumination | 2.3 | Hayır | Sude/Emir makaleyi metin.json adlarına çevirir |
| 59 | **Artemis etiketi:** makalede "Artemis candidate landing regions"; v1.2.1 madde 1'e göre etiket "Artemis III candidate regions (Oct 2024) — first landing now planned as Artemis IV" (makalede ilk geçişte bu, sonra "Artemis III candidate regions") | v1.2.1, 9.1 | Hayır | Sude/Emir |
| 60 | **Use of AI:** belge 2.3 beyan cümlesi üç parça ister: kod ve metin düzenlemesi Claude yardımıyla; problem yorumu, yöntem, eşik ve kararlar ekibe ait; çıktılar testlerle doğrulandı. Site, makale ve form aynı cümle | 2.3 | Hayır | Emir (metin.json about.use_of_ai) |
| 61 | Kapı durumlarında "requirement" kelimesi (Emir): sitede kapı başlığı "Mission requirement (gate)"; durum adları belgedeki gibi sabit | 2.3, 7.2 | Hayır | onaylı (İrem) |
| 62 | V1 kontrolü (Sude, 15:42): 11 çiftin kaynakları açıldı; tarih, ekip ve hedef belgeyle tutuyor, değişiklik gerekmiyor | 9.3, 15.1 | Hayır | kapandı |

## 17. kos.py 2. parça (P4–P6, D6 pilot) — 16:30

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 63 | **Q-17 (Claude kararı, 17:20; İrem'in 16:14 talimatıyla):** Liste hedefinin penceresi T **hedef koordinatına ortalanır**; N(T) = T + en yakın 20 ızgara penceresi. Dayanak: belge 9 hedefleri kaynaklı koordinatlarla verir (ör. Artemis: aday iniş noktalarının ortalaması, Wueller ve ark. 2026); ızgara penceresine kaydırmak hedefi 10–15 km yerinden oynatır (Malapert: 14 km) ve kaynaklı koordinatı bozar. Lambert pencere tanımı (4.3) merkezi serbest bırakır, yani koordinata ortalamak formülü değiştirmez. Katman B'de (tıklama) T zaten ızgara penceresidir | 4.2, 4.3, 9 | Evet (kos.HEDEF_MERKEZ = "koordinat") | karara bağlandı; makalede 4.2'ye bir cümle |
| 64 | Okuma: Genel görevde kapı yok (G ≡ 1, belge 7.2 kural 4); sitede kapı durumu "not applicable" | 7.2 | Hayır | kayda yazıldı |
| 65 | Okuma: R(1) = 2000, R(2) = R(8) = 200 tek permütasyondan (alt tohum R_orneklem): R(2) ve R(8) aynı örnek (belge 5.4 "aydınlanma aynı örneği kullanır"), R(1)'in ilk 200'ü | 5.4 | Hayır | kayda yazıldı |
| 66 | Pilot (D6) Kön = 800 (adayların en büyüğü; V5 henüz koşmadı). Uzun koşu V5'in seçtiği Kön ile | 7.1, 17.5 | Hayır | — |
| 67 | Teorem uygulaması: Ψ₁ ve Ψ₂'de ℓ ve ℓ^top her pencerenin kendi cisminin σv'siyle (Dünya penceresi 7,17 m; Ay hedefi 10 m; Mars 1 m). Belge 8.1 tek σv yazıyor; iki cisimli çiftte her pencere kendi R tabanını kendi σv'siyle aldığı için (6.1, 6.2) ℓ de öyle | 8.1 | Hayır (formül aynı) | Emir'e bilgi: ispattaki ℓ_A, ℓ_B tanımı pencere başına |

## 18. D6 pilot (16:28) — Jezero, Apollo 15, A3-03 Malapert

Pilot uçtan uca çalıştı (2,5 dk; hedef başına 5 görev 13–15 s). JSON alanları belge 17.6 şemasıyla uyumlu; her kategori sayı ya da nedenli null (Jezero'da su/buz null, neden "hedef": π⁺ = 0, kuru hedef → Ice "not applicable", belge 6.6).

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 68 | **K7 tetiklendi: X = 0.** V1 Geology çiftlerinden üçünde (2 Ries→Apollo 14, 9 Rio Grande Gorge→Apollo 16, 10 Lunar Crater VF→Apollo 17) Dünya sahasında hedefin baskın kayaç grubunun payı 0 (paylar: çift 1 0,526; 2 0; 3 0,226; 4 0,226; 8 0,613; 9 0; 10 0). Önceden yazılmış kural: "X = 0 çıkarsa kayaç payı koşulu fiilen kapalıdır ve bu yazılır" (belge 7.2, 11.1 K7). Geology kapısı bitki örtüsü ve kar/buz koşullarıyla çalışır | 7.2, 11.1 K7 | Hayır (kural) | Makale ve site Geology kapı metni: "rock-share condition effectively disabled (X = 0, pre-registered rule K7)"; sayılar ozet.json |
| 69 | **ε* bulgusu (madde 34 doğrulandı):** pilotta ilk 10'daki bütün adaylarda ε*₁ ve ε*₂ < 0,01 m ("hassasiyetten küçük"). Neden: Ψ₁'deki eğrilik terimi Λ_H,s'nin sabit kısmı 9/(2δ_s²), IQR_T(H) çok küçük olduğu için (500 m'de ortalama eğrilik dağılımı dar) ε başına çok büyür; referans uzaklıkları arasındaki boşluklar (~1/2000) bundan küçük kalır. Teorem doğru (testler geçti), ama verdiği sınır bu veride pratikte bilgi vermiyor; belge 8.1 sınır (i) bunu ε*₂ için zaten söylüyor, ε*₁ için de geçerli. **Yöntem değişmez.** Makalede "güvenli hata yarıçapı" sonucu dürüstçe "ε* < 1 cm for all top-10 candidates; the worst-case bound is uninformative at DEM noise level, robustness is shown empirically by V7" diye yazılır; 13.1'deki "matematiksel garanti" güçlü yanı bu cümleyle yumuşatılır | 8.1, 13.1 | Hayır | **Emir/Sude için önemli**: teorem bölümü ve güçlü yanlar cümlesi buna göre; F15 (ε*₁ dağılımı) yine üretilir |
| 70 | İç iş: bütün E′ için H₀ diyagramları önbelleğe alınır (belge 7.1 "diyagramlar önceden hesaplanıp saklanır"); her diyagramın n↓, n↑ sayısı P3'teki z ile birebir assert edilir | 7.1 | Hayır | — |

## 19. D7 kimlik testi ve V5 (17:30)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 71 | **D7 okuması (matematik aynı):** belge 17.5 "her s_k = 1" der. s_k tanımı (5.4) eşit uzaklıktaki referansa ½ sayar; hedefe uzaklığı tam 0 olan başka bir referans varsa (ör. iki pencerede de kayaç dağılımı %100 aynı grup → TV = 0) s_k = 1 − ½·n₀/|R_k| olur, 1 değil. D7 bu yüzden şunu sınar: pencere ilk sırada; hesaplanabilen her k'da d_k(T, T) = 0; s_k tanımla birebir. n₀ > 0 olan kategoriler D7.json'a yazılır. Tanımı değiştirmeden testin amacını (hat kendi penceresini tanıyor mu) tam karşılar | 5.4, 17.5 | Hayır | kayda yazıldı |
| 72 | D7 hedefleri: V1'in 8 farklı Dünya sahasının E′ penceresi (yeni tohum gerekmez), görev genel, Kön = 800. Ek kontrol: hedef özellikleri DEM'den yeniden hesaplanır ve P2/P3 kaydıyla karşılaştırılır (rtol 1e-5). Dünya penceresi için π⁺ tanımlı değil (6.6 Ay/Mars içindir) → su/buz kategorisi hedefte null; D7 bunu "hedefte yok" diye bekler | 6.6, 17.5 | Hayır | kayda yazıldı |
| 73 | **V5 okuması:** "Top-3_{E′}(T)" belge 7.4'teki Top-3 tanımıyla (sıralama + 100 km aralık kuralı, Q-12) bütün E′ üzerinde; görev genel (7.1 "görev seçilmemişse E′_g = E′"); Q-5 gereği topolojisiz, iki taraf aynı puan. Tam sıralama ve Katman A aynı puan fonksiyonunu kullanır (kos.skor_topolojisiz); bir pencerenin s_k'si aday kümesinden bağımsız olduğu testle gösterildi. E_K'lar iç içe olduğu için 4 Kön değeri tek sorguyla ölçülür | 7.1, 7.4, 8.3 | Hayır | kayda yazıldı; ozet.json: r̄, GA, Kön, eşik bayrağı |

## 20. Katman B hedef tarafı (17:55)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 74 | D7 sonucu (17:45): 8 sahanın 8'i PASS; her sahada pencere ilk sırada, yeniden hesaplanan özellikler kayıtla birebir aynı (en büyük fark 0). 7 hesaplanabilir kategoriden 6'sında s = 1 (sahaların ikisinde 7/7); kalanı madde 71'deki ½ eşitlik kuralı (sayılar sonuc\dogrulama\D7.json) | 17.5 | Hayır | PASS |
| 75 | İç iş: Ay ve Mars'ın bütün ızgara pencerelerinin özellikleri (P3B) Katman A'daki hedef hesabıyla aynı fonksiyonla (p3_blok) hesaplanır; IQR_T için 6 topografya alanının ham değerleri ve topoloji için diyagramlar da saklanır, böylece Katman B'de IQR_T ve d₂ Katman A ile aynı formülle (yaklaşıksız) bulunur | 3.2, 6.1, 6.2 | Hayır | — |
''', encoding="utf-8")
r = subprocess.run([sys.executable, str(KOD / "kos.py"), "--help"], cwd=KOD, capture_output=True, text=True)
assert r.returncode == 0 and "katmanb_ozellik" in r.stdout, r.stderr
with open(KAYIT / "degisiklik.md", "a", encoding="utf-8") as f:
    f.write("- 2026-11-14 | D7 PASS (8/8); kos.py katmanb_ozellik: Ay+Mars bütün pencereler (P3B) + diyagramlar + ham topografya alanları | etkisi: MAKALEYİ ETKİLER 74–75\n")
if str(KOD) not in sys.path: sys.path.insert(0, str(KOD))
import test_kos; importlib.reload(test_kos)
test_kos.calistir("D4_test_kos_katmanb", ["testler/test_kos_hatti.py", "testler/test_kos_puanla.py",
                                         "testler/test_kos_v5_d7.py", "testler/test_kos_katmanb.py"])
# bilgisayar: bellek ve disk (Katman B puanlama planı için)
try:
    import psutil
    print(f"RAM toplam: {psutil.virtual_memory().total / 2**30:.1f} GB, şu an boş: {psutil.virtual_memory().available / 2**30:.1f} GB")
except ImportError:
    import ctypes
    class M(ctypes.Structure):
        _fields_ = [("l", ctypes.c_ulong), ("y", ctypes.c_ulong), ("t", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong),
                    ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong)]
    m = M(); m.l = ctypes.sizeof(M); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    print(f"RAM toplam: {m.t / 2**30:.1f} GB, şu an boş: {m.a / 2**30:.1f} GB")
print(f"Disk boş: {shutil.disk_usage(ARA).free / 1e9:.1f} GB")
