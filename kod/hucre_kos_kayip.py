# Developed with assistance from Claude (Anthropic).
# kos.py: ön elemenin puan kaybı ölçümü (python kos.py kayip). Hiçbir sonucu değiştirmez.
import sys, subprocess, importlib, shutil, time
from pathlib import Path
KOK = Path.home() / "orbitrary"; KOD, KAYIT = KOK / "kod", KOK / "kayit"
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
    elif asama == "katmanb":
        n = len(df)
        depo = Depo(ARA / f"katmanb_{govde}", n, isci=no)
        bloklari_kos(depo, _katmanb_fonk(govde, kon_oku(), X_al()), f"Katman B {govde} işçi {no}", her=2,
                     isci_no=no, isci_sayi=sayi)
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
    ap.add_argument("asama", choices=["p0", "p1", "p2", "p3", "d5", "dunya", "isci", "d6", "diyagram", "diyagram_isci", "d7", "v5", "katmanb_ozellik", "katmanb", "katmanb_kuru", "liste", "kayip"])
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
    elif a.asama == "kayip":
        kayip()
    elif a.asama == "liste":
        liste()
    elif a.asama == "katmanb":
        katmanb(a.isci)
    elif a.asama == "katmanb_kuru":
        katmanb_kuru(a.n if a.n != 500 else 100, a.govde if a.govde != "dunya" else "ay")
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


def skor_topolojisiz(D, Dk, j, idx, d1c, d1r, R1, R28, KT, R37=None):
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
    if R37 is None:                                      # Katman A: R(3..7) = bütün E′
        ref37, rk37 = None, idx
    else:                                                # Katman B: sabit rastgele 2000 (belge 3.2)
        ref37, rk37 = np.asarray(R37, np.int64), _konum(D.n, R37)[idx]
    for k in (3, 4, 5, 6, 7):
        d = Dk[k][:, j]
        dr = d if ref37 is None else d[ref37]
        S[:, k - 1], Zt[:, k - 1], Dm[:, k - 1] = Pn.s_k(d[idx], dr, rk37), Pn.zeta_k(d[idx], dr, rk37), d[idx]
    rk8 = _konum(D.n, R28)[idx]
    d8 = Dk[8][:, j]
    S[:, 7], Zt[:, 7], Dm[:, 7] = Pn.s_k(d8[idx], d8[R28], rk8), Pn.zeta_k(d8[idx], d8[R28], rk8), d8[idx]
    KE = np.isfinite(S); KE[:, 1] = np.asarray(D.dem_tam)[idx] & KT[1]
    return S, Zt, Dm, kapi.uygun(KE, KT)


def d2_referans(hz, diy28):
    import ozellik_topoloji as TP
    return np.array([np.nan if x is None else TP.d2(x, hz["dg"]) for x in diy28])


def topoloji_ve_sira(D, hz, idx, S, Zt, Dm, uyg, w, R28, diy28, d2r=None):
    """Belge 7.4: topolojisiz P, Q ile sırala → uygun ilk 30'da kategori 2 (R(2) = 200) → yeniden P, Q ve sıra.
    S, Zt, Dm yerinde güncellenir. Katman A (puanla) ve Katman B aynı fonksiyonu kullanır."""
    import ozellik_topoloji as TP
    import puan as Pn
    P0, Q0 = Pn.P_Q(S, Zt, w, uyg)
    sira0 = Pn.sirala(P0, Q0, D.kim[idx])
    ilk30 = np.array([i for i in sira0 if uyg[i]][:Pn.TOPOLOJI_ADAY], int)
    if hz["dg"] is not None and len(ilk30):
        dgc = dunya_diyagram(D, idx[ilk30])
        d2c = np.array([np.nan if x is None else TP.d2(x, hz["dg"]) for x in dgc])
        d2r = d2_referans(hz, diy28) if d2r is None else d2r
        rk2 = _konum(D.n, R28)[idx[ilk30]]
        S[ilk30, 1], Zt[ilk30, 1], Dm[ilk30, 1] = Pn.s_k(d2c, d2r, rk2), Pn.zeta_k(d2c, d2r, rk2), d2c
    else:
        d2r = None
    P, Q = Pn.P_Q(S, Zt, w, uyg)
    yeni = Pn.yeniden_sirala(ilk30, P, Q, D.kim[idx])
    return P, Q, ilk30, yeni, d2r


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
    P, Q, ilk30, yeni, d2r = topoloji_ve_sira(D, hz, idx, S, Zt, Dm, uyg, w, R28, diy28)
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


# ------------------------------------------------------------------ Ön elemenin puan kaybı (V5'e ek ölçüm, karar için)
def kapi_dizileri(D, X):
    """Görev → (anahtar → G dizisi). Geology için baskın grup c* başına ayrı (belge 7.2)."""
    import kapi
    G = {"genel": np.ones(D.n, bool), "mobility": kapi.kapi_mobility(D.mob)[0], "astro": kapi.kapi_astro(D.astro)[0],
         "ice": kapi.kapi_buz(D.buz, True)[0]}
    for c in range(6):
        G[f"geology{c}"] = kapi.kapi_jeoloji(D.pv, D.karbuz, D.q3[:, c], X)[0]
    G["geology_na"] = kapi.kapi_jeoloji(D.pv, D.karbuz, np.full(D.n, np.nan), X)[0]
    return G


def kayip_hedef(D, hz, Dk, j, d1t, R1, R28, G, agaclar, Kon):
    """Bir hedef, 5 görev: bütün E′ üzerinde topolojisiz P (Q-5) ile ön elemeli (E_K) en iyi P karşılaştırması.
    P_tum: E′'deki en büyük P; P_on: E_K içindeki en büyük P; Pi_on: E′'nin yüzde kaçı P ≤ P_on (V1'deki Π tanımı)."""
    import puan as Pn
    KT = hedef_kategorileri(hz)
    ar = np.arange(D.n)
    S, Zt, _, uyg = skor_topolojisiz(D, Dk, j, ar, d1t, d1t[np.asarray(R1)], R1, R28, KT)
    q3 = np.asarray(hz["q3"], float)
    cj = f"geology{int(np.nanargmax(q3))}" if np.isfinite(q3).any() else "geology_na"
    out = {}
    for g in GOREVLER:
        if g == "ice" and not hz["islak"]:
            out[g] = None
            continue
        key = cj if g == "geology" else g
        gec = uyg & G[key]
        P, _ = Pn.P_Q(S, Zt, Pn.gorev_agirligi(g), gec)
        P = np.where(np.isfinite(P), P, 0.0)
        idx = np.asarray(agaclar[key].sorgu(hz["z"], Kon)[0], np.int64)
        P_tum, P_on = float(P.max()), float(P[idx].max())
        out[g] = {"P_tum": P_tum, "P_on": P_on, "fark": P_tum - P_on, "Pi_on": float(np.mean(P <= P_on)),
                  "gecen": int(gec.sum())}
    return out


def kayip(n_cisim=25, grup=50):
    """V5'in hedef önbelleğinden (ara\\v5) ilk n_cisim Ay + ilk n_cisim Mars hedefi; Kön = 800 (V5 sonucu).
    Çıktı sonuc\\dogrulama\\V5_kayip.json + özet tablo. Hiçbir sonucu değiştirmez (yalnız ölçüm)."""
    import pickle
    import onele
    t0 = time.time()
    v5 = json.loads((SONUC / "dogrulama" / "V5.json").read_text(encoding="utf-8"))
    kim = sorted(v5["hedefler"])
    sec = [k for k in kim if k.startswith("V5-ay-")][:n_cisim] + [k for k in kim if k.startswith("V5-mars-")][:n_cisim]
    hz = {k: pickle.loads((V5_KL / f"{k}.pkl").read_bytes()) for k in sec}
    D = Dunya()
    olcek = onele.Olcek(D.z)
    R1, R28 = referans_kumeleri(D.n)
    X = X_al(D)
    G = kapi_dizileri(D, X)
    agaclar = {k: onele.Agac(olcek, D.z, g, kimlik=D.kim) for k, g in G.items()}
    Kon = int(v5["K_on"])
    sonuc = {}
    for a in range(0, len(sec), grup):
        ks = sec[a:a + grup]
        Dk, _ = dunya_uzakliklari(D, [hz[k] for k in ks])
        d1t = d1_tum(D, [hz[k] for k in ks])
        for j, k in enumerate(ks):
            sonuc[k] = kayip_hedef(D, hz[k], Dk, j, d1t[:, j], R1, R28, G, agaclar, Kon)
        print(f"   kayıp: {min(a + grup, len(sec))}/{len(sec)}  geçen {(time.time() - t0) / 60:.0f} dk", flush=True)
    ozet = {}
    print(f"\nÖn eleme (Kön = {Kon}) ile bütün E′ karşılaştırması, {len(sec)} rastgele hedef (topolojisiz P):")
    print(f"{'görev':10s} {'n':>4s} {'P_tüm ort':>10s} {'P_ön ort':>9s} {'fark ortanca':>13s} {'fark %95':>9s} "
          f"{'Π_ön ortanca':>13s} {'Π_ön %5':>8s}")
    for g in GOREVLER:
        v = [sonuc[k][g] for k in sec if sonuc[k][g] is not None]
        if not v:
            continue
        f = np.array([x["fark"] for x in v]); pi = np.array([x["Pi_on"] for x in v])
        ozet[g] = {"n": len(v), "P_tum_ort": float(np.mean([x["P_tum"] for x in v])), "P_on_ort": float(np.mean([x["P_on"] for x in v])),
                   "fark_ortanca": float(np.median(f)), "fark_y95": float(np.percentile(f, 95)),
                   "Pi_on_ortanca": float(np.median(pi)), "Pi_on_y5": float(np.percentile(pi, 5))}
        o = ozet[g]
        print(f"{g:10s} {o['n']:4d} {o['P_tum_ort']:10.3f} {o['P_on_ort']:9.3f} {o['fark_ortanca']:13.3f} {o['fark_y95']:9.3f} "
              f"{o['Pi_on_ortanca']:13.5f} {o['Pi_on_y5']:8.5f}")
    kl = SONUC / "dogrulama"; kl.mkdir(parents=True, exist_ok=True)
    (kl / "V5_kayip.json").write_text(json.dumps({"K_on": Kon, "X": X, "ozet": ozet, "hedefler": sonuc}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    sure_yaz("V5_kayip", n=len(sec), sure_s=round(time.time() - t0, 1))
    print("→ sonuc\\dogrulama\\V5_kayip.json", flush=True)


# ------------------------------------------------------------------ V2 çiftleri, D8 sabitleme, Katman A (26 hedef)
V2_SINIF = {"orman": "mcd12c1_02", "tarim": "mcd12c1_12"}


def v2_ciftleri():
    """Belge 9.3 / 8.3 V2 + Q-3: her V1 çifti için bir yağmur ormanı (MCD12C1 sınıf 2 pencere ortalaması ≥ %90) ve bir
    tarım (sınıf 12 ≥ %90) penceresi, alt tohum V2, tekrarsız. dogrulama_ciftleri.csv'ye (tur = V2) D8'den önce yazılır.
    Zaten yazılmışsa dokunmaz (yalnız sayıyı denetler)."""
    import pandas as pd
    import dogrula as DG
    p = KOD / "dogrulama_ciftleri.csv"
    c = pd.read_csv(p, encoding="utf-8-sig")
    v1 = c[c["tur"] == "V1"].sort_values("cift_no")
    if (c["tur"] == "V2").any():
        assert int((c["tur"] == "V2").sum()) == 2 * len(v1), "V2 satır sayısı 2 × V1 değil"
        print("   V2 çiftleri zaten yazılı:", int((c["tur"] == "V2").sum()), flush=True)
        return c[c["tur"] == "V2"]
    D = Dunya()
    r = _r("dunya")
    ph, la = np.radians(D.lat), np.radians(D.lon)
    pay = {}
    for ad, kat in V2_SINIF.items():
        k = K.ac(kat)
        v = np.empty(D.n)
        for a in range(0, D.n, 4096):
            z = min(D.n, a + 4096)
            with np.errstate(invalid="ignore"):
                v[a:z] = np.nanmean(K.hucreye(k, ph[a:z], la[a:z], r)[0], axis=(-2, -1)) / 100.0
        pay[ad] = v
        print(f"   V2 {ad}: pay ≥ 0,9 olan E′ penceresi {int(np.sum(v >= 0.9))}", flush=True)
    o, ta = DG.v2_sec(pay["orman"], pay["tarim"], len(v1))
    satir = []
    for q, (_, s) in enumerate(v1.iterrows()):
        for tur_ad, e in (("yağmur ormanı (MCD12C1 sınıf 2 ≥ %90)", o[q]), ("tarım (MCD12C1 sınıf 12 ≥ %90)", ta[q])):
            satir.append({"tur": "V2", "cift_no": int(s["cift_no"]), "hedef_kimlik": s["hedef_kimlik"],
                          "dunya_saha": f"V2 {tur_ad}, E′ penceresi {int(D.kim[e])}", "enlem": round(float(D.lat[e]), 5),
                          "boylam": round(float(D.lon[e]), 5), "gorev": s["gorev"],
                          "kaynak": "tohum 20261113, alt tohum V2 (belge 8.3 V2, Q-3)", "ilk_cift": "", "kaynak_yeri": "kos.v2_ciftleri",
                          "sude_kontrol": ""})
    yeni = pd.concat([c, pd.DataFrame(satir)[c.columns]], ignore_index=True)
    shutil_kopya = KAYIT / f"dogrulama_ciftleri_V2_oncesi_{time.strftime('%H%M')}.csv"
    c.to_csv(shutil_kopya, index=False, encoding="utf-8-sig")
    yeni.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"   V2: {len(satir)} çift yazıldı → kod\\dogrulama_ciftleri.csv (eski hâli kayit\\{shutil_kopya.name})", flush=True)
    return pd.DataFrame(satir)


SABIT_DOSYALAR = ["kod/ayar.json", "kod/dogrulama_ciftleri.csv", "kod/hedefler.csv", "kod/site_girdi/analog_metin.csv",
                  "kod/site_girdi/mission_prep.csv", "ara/ref_kumeleri.npz", "ara/ref_B.npy", "sonuc/dogrulama/V5.json"]


def _sha(p):
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def d8():
    """Belge 17.5 D8: V1/V2 çiftleri, tohum, ağırlık ve eşikler (ayar.json), hedefler, bilinen analog listeleri,
    referans örnekleri ve Kön → kayit\\sabit.json (SHA-256). Varsa yeniden yazılmaz, yalnız denetlenir."""
    kok = KOD.parent
    p = KAYIT / "sabit.json"
    simdi = {f: _sha(kok / f) for f in SABIT_DOSYALAR}
    if p.exists():
        eski = json.loads(p.read_text(encoding="utf-8"))
        fark = [f for f in SABIT_DOSYALAR if eski["sha256"].get(f) != simdi[f]]
        assert not fark, f"D8 FAIL: kilitten sonra değişen dosya: {fark}"
        print("   D8: kilit zaten var, dosyalar aynı (PASS)", flush=True)
        return eski
    out = {"zaman": datetime.datetime.now().isoformat(timespec="seconds"), "tohum": int(A.ayar("tohum")),
           "K_on": kon_oku(), "sha256": simdi}
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    sure_yaz("D8", K_on=out["K_on"])
    print(f"   D8: kilitlendi → kayit\\sabit.json ({len(simdi)} dosya, Kön = {out['K_on']})", flush=True)
    return out


def d8_kontrol():
    """Koşu sonunda: kilitli dosyaların SHA-256'sı aynı mı (belge 17.5 'koşu sonunda hash aynı')."""
    kok = KOD.parent
    eski = json.loads((KAYIT / "sabit.json").read_text(encoding="utf-8"))
    fark = [f for f in SABIT_DOSYALAR if eski["sha256"][f] != _sha(kok / f)]
    return not fark, fark


def liste():
    """V2 → D8 → Katman A: hedefler.csv'deki bütün hedefler, Kön = V5 (sonuc\\liste\\liste_<kimlik>.json)."""
    import pandas as pd
    v2_ciftleri()
    s = d8()
    hed = pd.read_csv(KOD / "hedefler.csv", encoding="utf-8-sig").dropna(subset=["kimlik"])
    sureler = katman_a(list(hed["kimlik"]), "liste", int(s["K_on"]))
    ok, fark = d8_kontrol()
    assert ok, f"D8 FAIL: {fark}"
    print(f"Katman A: {len(sureler)} hedef → sonuc\\liste\\ ; D8 hash aynı (PASS)", flush=True)


# =====================================================================================================
# Katman B (belge 3.2): Ay ve Mars'ın bütün ızgara pencereleri. Aynı formüller; kategori 3–7 referansı sabit
# rastgele 2000 pencere; çıktı Top-3, sekiz s_k, kapsama, eksik veri tarafı (5 görev).
# =====================================================================================================
EKSIK_KOD = {None: 0, "hedef": 1, "dunya": 2, "iki_taraf": 3}


def referans_B(n):
    """Belge 3.2 / 5.4: Katman B'de kategori 3–7 için sabit rastgele 2000 pencere (E′'den bir kez, alt tohum
    katman_B_R); kategori 1, 2, 8 Katman A ile aynı (R(1), R(2) = R(8))."""
    kb = A.ayar("referans.katman_B")
    ka = A.ayar("referans.katman_A")
    m = int(kb["3"])
    assert m == 2000 and all(int(kb[str(k)]) == m for k in (4, 5, 6, 7)), kb
    assert all(str(kb[str(k)]) == str(ka[str(k)]) for k in (1, 2, 8)), (ka, kb)
    p = ARA / "ref_B.npy"
    if p.exists():
        R = np.load(p)
        assert len(R) == m and R.max() < n
        return R
    R = A.rng(int(A.ayar("alt_tohum")["katman_B_R"])).permutation(n)[:m]
    np.save(p, R)
    return R


def X_al(D=None):
    """Geology kapısı X (belge 7.2, K-5: liste dışı hedeflerde 7 Geology çiftinin hepsiyle). Bir kez hesaplanır,
    ara\\X.json'a yazılır."""
    import pandas as pd
    p = ARA / "X.json"
    if p.exists():
        return float(json.loads(p.read_text(encoding="utf-8"))["X"])
    D = D or Dunya()
    hedefler = pd.read_csv(KOD / "hedefler.csv", encoding="utf-8-sig").dropna(subset=["kimlik"])
    ciftler = pd.read_csv(KOD / "dogrulama_ciftleri.csv", encoding="utf-8-sig")
    gerek = set(ciftler.loc[ciftler["gorev"] == "geology", "hedef_kimlik"])
    hz = {r["kimlik"]: hedef_hazirla(r.to_dict()) for _, r in hedefler[hedefler["kimlik"].isin(gerek)].iterrows()}
    (X, loo), paylar = X_hesapla(D, hz, ciftler)
    p.write_text(json.dumps({"X": X, "paylar": paylar}, ensure_ascii=False), encoding="utf-8")
    return float(X)


def dunya_kat_var(D, rows, F5, esik):
    """Dünya pencerelerinde kategori verisi var mı (8,) — eksik veri tarafı için (dunya_uzakliklari'ndaki eK ile aynı)."""
    rows = np.asarray(rows, np.int64)
    e = np.ones((len(rows), 8), bool)
    if not len(rows):
        return e
    e[:, 0] = np.isfinite(D.lnR[rows])
    e[:, 1] = np.asarray(D.dem_tam)[rows]
    e[:, 2] = np.isfinite(D.q3[rows]).all(axis=1)
    e[:, 3] = np.isfinite(_satirlar(D.Q("Q4"), rows)).all(axis=1) & (D.x4g[rows] >= esik)
    e[:, 4] = np.all([np.isfinite(_satirlar(D.Q(f"Q5_{f}"), rows)).all(axis=1) for f in F5], axis=0)
    for k, ad in ((5, "Q6"), (6, "Q7"), (7, "Q8")):
        e[:, k] = np.isfinite(_satirlar(D.Q(ad), rows)).all(axis=1)
    return e


def _satirlar(mm, rows):
    """memmap'ten satırlar (sıralı okuma, istenen sırayla döner)."""
    rows = np.asarray(rows, np.int64)
    o = np.argsort(rows)
    out = np.empty((len(rows),) + mm.shape[1:], np.float64)
    out[o] = mm[rows[o]]
    return out


class KatmanB:
    """Bir işçide bir kez kurulur: Dünya verisi, referanslar (bellekte), görev kapıları ve KD-ağaçları."""

    def __init__(self, D, Kon, X, olcek=None):
        import kapi
        import onele
        self.D, self.Kon, self.X = D, int(Kon), float(X)
        self.R1, self.R28 = referans_kumeleri(D.n)
        self.RB = referans_B(D.n)
        self.diy28 = ref_diyagramlari(D, self.R28)
        self.esik4 = float(A.ayar("mineraloji.gecerlilik_orani"))
        olcek = olcek or onele.Olcek(D.z)
        G = {"genel": None, "mobility": kapi.kapi_mobility(D.mob)[0], "astro": kapi.kapi_astro(D.astro)[0],
             "ice": kapi.kapi_buz(D.buz, True)[0]}
        for c in range(6):
            G[f"geology{c}"] = kapi.kapi_jeoloji(D.pv, D.karbuz, D.q3[:, c], self.X)[0]
        G["geology_na"] = kapi.kapi_jeoloji(D.pv, D.karbuz, np.full(D.n, np.nan), self.X)[0]
        self.agac = {k: onele.Agac(olcek, D.z, g, kimlik=D.kim) for k, g in G.items()}
        # referans satırları bellekte
        R1, RB, R28 = self.R1, self.RB, self.R28
        self.ref1 = (np.asarray(D.Q1(R1), float), D.lnR[R1])
        self.refB = {"q3": D.q3[RB], "x4g": D.x4g[RB]}
        for ad in ("Q4", "Q6", "Q7", "Q5_tmax", "Q5_tort", "Q5_tgece", "Q5_iarti"):
            self.refB[ad] = _satirlar(D.Q(ad), RB)
        self.ref8 = _satirlar(D.Q("Q8"), R28)

    def _uzaklik(self, hz, U):
        """Kategori 1, 3–8 uzaklıkları: tam boy diziler (NaN), yalnız U ∪ referans satırları dolu (belge 6.1–6.8)."""
        import ozellik_topo as T
        import uzaklik as Uz
        D = self.D
        n = D.n
        d1 = np.full(n, np.nan)
        d1[U] = T.d1(np.asarray(D.Q1(U), float), D.lnR[U], hz["Q1"], float(hz["lnR"]), hz["iqr"])
        d1[self.R1] = T.d1(self.ref1[0], self.ref1[1], hz["Q1"], float(hz["lnR"]), hz["iqr"])
        Dk = {k: np.full((n, 1), np.nan) for k in (3, 4, 5, 6, 7, 8)}
        KT = hedef_kategorileri(hz)
        RB = self.RB
        if KT[2]:
            Dk[3][U, 0] = Uz.tv(D.q3[U], hz["q3"][None, :])
            Dk[3][RB, 0] = Uz.tv(self.refB["q3"], hz["q3"][None, :])
        if KT[3]:
            qU = _satirlar(D.Q("Q4"), U)
            v = Uz.w1_matris(qU, hz["Q4"][None, :])[:, 0]; v[D.x4g[U] < self.esik4] = np.nan; Dk[4][U, 0] = v
            v = Uz.w1_matris(self.refB["Q4"], hz["Q4"][None, :])[:, 0]; v[self.refB["x4g"] < self.esik4] = np.nan
            Dk[4][RB, 0] = v
        if KT[4]:
            F5 = hz["F5"]
            Dk[5][U, 0] = np.mean([Uz.w1_matris(_satirlar(D.Q(f"Q5_{f}"), U), hz[f"Q5_{f}"][None, :])[:, 0] for f in F5], axis=0)
            Dk[5][RB, 0] = np.mean([Uz.w1_matris(self.refB[f"Q5_{f}"], hz[f"Q5_{f}"][None, :])[:, 0] for f in F5], axis=0)
        for k, ad in ((6, "Q6"), (7, "Q7")):
            if KT[k - 1]:
                Dk[k][U, 0] = Uz.w1_matris(_satirlar(D.Q(ad), U), hz[ad][None, :])[:, 0]
                Dk[k][RB, 0] = Uz.w1_matris(self.refB[ad], hz[ad][None, :])[:, 0]
        if KT[7]:
            Dk[8][U, 0] = Uz.w1_matris(_satirlar(D.Q("Q8"), U), hz["Q8"][None, :])[:, 0]
            Dk[8][self.R28, 0] = Uz.w1_matris(self.ref8, hz["Q8"][None, :])[:, 0]
        return d1, Dk, KT

    def hedef(self, hz):
        """Bir Ay/Mars penceresi → 5 görevin Top-3'ü (E′ satırı), P, s (3, 8), eksik taraf kodu, durum."""
        import puan as Pn
        D = self.D
        out = {"top3": np.full((5, 3), -1, np.int64), "P": np.full((5, 3), np.nan, np.float32),
               "s": np.full((5, 3, 8), np.nan, np.float32), "eksik": np.zeros((5, 3, 8), np.int8),
               "durum": np.zeros(5, np.int8), "aday": np.zeros(5, np.int32)}
        q3 = np.asarray(hz["q3"], float)
        cj = f"geology{int(np.nanargmax(q3))}" if np.isfinite(q3).any() else "geology_na"
        idxs = {}
        for gi, g in enumerate(GOREVLER):
            if g == "ice" and not hz["islak"]:
                out["durum"][gi] = 1                     # not applicable (belge 6.6)
                continue
            idxs[g] = np.asarray(self.agac[cj if g == "geology" else g].sorgu(hz["z"], self.Kon)[0], np.int64)
        if not idxs:
            return out
        U = np.unique(np.concatenate(list(idxs.values())))
        d1, Dk, KT = self._uzaklik(hz, U)
        d2r = None
        for gi, g in enumerate(GOREVLER):
            if g not in idxs:
                continue
            idx = idxs[g]
            out["aday"][gi] = len(idx)
            S, Zt, Dm, uyg = skor_topolojisiz(D, Dk, 0, idx, d1[idx], d1[self.R1], self.R1, self.R28, KT, R37=self.RB)
            w = Pn.gorev_agirligi(g)
            P, Q, ilk30, yeni, d2r = topoloji_ve_sira(D, hz, idx, S, Zt, Dm, uyg, w, self.R28, self.diy28, d2r)
            t3 = Pn.aralikli_liste(yeni, D.lat[idx], D.lon[idx], 3, gecer=uyg)
            if not len(t3):
                continue
            eK = dunya_kat_var(D, idx[t3], hz["F5"], self.esik4)
            for q, i in enumerate(t3):
                out["top3"][gi, q] = int(idx[i]); out["P"][gi, q] = P[i]; out["s"][gi, q] = S[i]
                for k in range(8):
                    if np.isfinite(S[i, k]):
                        continue
                    out["eksik"][gi, q, k] = EKSIK_KOD["iki_taraf" if (not KT[k] and not eK[q, k]) else
                                                       "hedef" if not KT[k] else "dunya"]
        return out


def hz_B(govde, depo, ham, i, H, diy):
    """Katman B hedefi: ızgara penceresi i (P3B kaydından). N(T) ve IQR_T Katman A'daki hedef_hazirla ile aynı kural
    (T + en yakın 20 ızgara penceresi; ham alanların birleşimi); diyagram önbellekten."""
    import ozellik_diger as OD
    import ozellik_topo as T
    lat, lon = (float(v) for v in H.merkez_der(i))
    kom, _ = H.komsular(lat, lon)
    pen = np.r_[i, np.asarray(kom, np.int64)]
    iqr = T.iqr_hedef([{f: ham[f][w] for f in T.OZELLIKLER} for w in pen])
    hz = {"govde": govde, "enlem": lat, "boylam": lon, "iqr": iqr, "dg": diy[i], "F5": OD.termal_ozellikleri(govde, lat)}
    for ad in depo.sema:
        if not ad.startswith("ham_"):
            hz[ad] = np.asarray(depo.oku(ad)[i])
    hz["z"] = np.asarray(hz["z"], float)
    pi = float(hz.get("pi_arti", np.nan))
    hz["pi_arti"] = pi
    hz["islak"] = bool(OD.islak_mi(pi))
    return hz


KB_ALAN = ("top3", "P", "s", "eksik", "durum", "aday")


def _katmanb_fonk(govde, Kon, X):
    """Blok fonksiyonu (paralel işçide bir kez kurulur)."""
    D = Dunya()
    kb = KatmanB(D, Kon, X)
    df = izgara(govde)
    depo = Depo(ARA / f"p3b_{govde}", len(df))
    assert depo.tamam(), f"P3B {govde} bitmemiş"
    ham = {f: depo.oku(f"ham_{f}") for f in __import__("ozellik_topo").OZELLIKLER}
    H = Z.Halka(govde)
    diy = DiyagramDeposu(kl=ARA / f"diyagram_{govde}")

    def f(a, z):
        res = [kb.hedef(hz_B(govde, depo, ham, i, H, diy)) for i in range(a, z)]
        return {k: np.stack([r[k] for r in res]) for k in KB_ALAN}
    return f


def katmanb(isci_sayi, govdeler=("ay", "mars")):
    """Katman B puanlama: Kön = V5 (sonuc\\dogrulama\\V5.json), X = ara\\X.json. Paralel, kaldığı yerden devam."""
    Kon = kon_oku()
    X = X_al()
    for g in govdeler:
        t0 = time.time()
        n = len(izgara(g))
        f = None
        dp = Depo(ARA / f"katmanb_{g}", n)
        if not dp.bitti_hepsi().any():
            f = _katmanb_fonk(g, Kon, X)
            t1 = time.time()
            dp.yaz(0, f(0, min(n, BLOK)))
            print(f"   {g}: ilk blok {time.time() - t1:.0f} s ({(time.time() - t1) / min(n, BLOK):.2f} s/pencere)", flush=True)
        s = paralel("katmanb", g, ARA / f"katmanb_{g}", n, isci_sayi, f or _katmanb_fonk(g, Kon, X))
        sure_yaz("katman_B", govde=g, pencere=n, K_on=Kon, X=X, sure_s=round(time.time() - t0, 1), isci=isci_sayi)
        print(f"   bitti: katman B {g} ({(time.time() - t0) / 60:.1f} dk)", flush=True)


def katmanb_kuru(n=100, govde="ay"):
    """Süre ölçümü (D5 gibi): rastgele n pencere (alt tohum D5_kuru), tek süreç; sonuç kaydedilmez."""
    Kon, X = kon_oku(), X_al()
    f0 = time.time()
    D = Dunya(); kb = KatmanB(D, Kon, X)
    kur = time.time() - f0
    depo = Depo(ARA / f"p3b_{govde}", len(izgara(govde)))
    assert depo.tamam(), f"P3B {govde} bitmemiş"
    ham = {f: depo.oku(f"ham_{f}") for f in __import__("ozellik_topo").OZELLIKLER}
    H = Z.Halka(govde); diy = DiyagramDeposu(kl=ARA / f"diyagram_{govde}")
    sec = A.rng(int(A.ayar("alt_tohum")["D5_kuru"])).choice(depo.n, n, replace=False)
    t0 = time.time()
    for q, i in enumerate(sec):
        kb.hedef(hz_B(govde, depo, ham, int(i), H, diy))
    s = (time.time() - t0) / n
    print(f"Katman B kuru ({govde}): kurulum {kur:.0f} s, {s:.2f} s/pencere → tek süreç {s * depo.n / 3600:.1f} sa", flush=True)
    sure_yaz("katmanB_kuru", govde=govde, n=n, s_pencere=round(s, 3), kurulum_s=round(kur, 1))
    return s


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
            if len(self._b) >= 400:                      # bellek sınırı (paralel işçiler)
                self._b.clear()
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


def test_kayip_hedef(ortam):
    """Kön = bütün E′ → fark 0, Π_ön = 1; Kön küçükse fark ≥ 0 ve Π_ön ≤ 1; kuru hedefte Ice yok."""
    D, ol, R1, R28, diy, f = ortam
    G = kos.kapi_dizileri(D, 0.1)
    ag = {k: onele.Agac(ol, D.z, g, kimlik=D.kim) for k, g in G.items()}
    hz = [_hedef(True), _hedef(False)]
    Dk, _ = kos.dunya_uzakliklari(D, hz, parca=700)
    d1t = kos.d1_tum(D, hz)
    tam = kos.kayip_hedef(D, hz[0], Dk, 0, d1t[:, 0], R1, R28, G, ag, nE)
    assert all(v["fark"] == 0 and v["Pi_on"] == 1.0 for v in tam.values())
    kuc = kos.kayip_hedef(D, hz[0], Dk, 0, d1t[:, 0], R1, R28, G, ag, 50)
    assert all(v["fark"] >= 0 and 0 < v["Pi_on"] <= 1 for v in kuc.values())
    assert kos.kayip_hedef(D, hz[1], Dk, 1, d1t[:, 1], R1, R28, G, ag, 50)["ice"] is None
''', encoding="utf-8")
(KOD / "testler" / "test_kos_d8.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""V2 çift seçimi ve D8 kilidi (sentetik; gerçek veri yok)."""
import json
import types

import numpy as np
import pandas as pd
import pytest

import kos


def test_d8_kilit_ve_degisiklik(tmp_path, monkeypatch):
    kok = tmp_path
    for f in kos.SABIT_DOSYALAR:
        (kok / f).parent.mkdir(parents=True, exist_ok=True)
        (kok / f).write_text(f"icerik {f}", encoding="utf-8")
    (kok / "kayit").mkdir()
    monkeypatch.setattr(kos, "KOD", kok / "kod")
    monkeypatch.setattr(kos, "KAYIT", kok / "kayit")
    monkeypatch.setattr(kos, "kon_oku", lambda: 800)
    monkeypatch.setattr(kos, "sure_yaz", lambda *a, **k: None)
    s = kos.d8()
    assert s["K_on"] == 800 and len(s["sha256"]) == len(kos.SABIT_DOSYALAR)
    assert kos.d8_kontrol() == (True, [])
    assert kos.d8()["zaman"] == s["zaman"]                     # ikinci çağrı yeniden yazmaz
    (kok / "kod/ayar.json").write_text("değişti", encoding="utf-8")
    assert kos.d8_kontrol() == (False, ["kod/ayar.json"])
    with pytest.raises(AssertionError):
        kos.d8()


def test_v2_ciftleri(tmp_path, monkeypatch):
    rng = np.random.default_rng(1)
    n = 500
    D = types.SimpleNamespace(n=n, lat=rng.uniform(-50, 50, n), lon=rng.uniform(-180, 180, n), kim=np.arange(n) * 2 + 1)
    orman = np.where(np.arange(n) < 60, 95.0, 10.0); tarim = np.where(np.arange(n) >= 440, 92.0, 5.0)
    monkeypatch.setattr(kos, "Dunya", lambda: D)
    monkeypatch.setattr(kos.K, "ac", lambda ad: ad)
    def sahte(k, p, l, r):
        v = orman if k == "mcd12c1_02" else tarim
        assert len(p) == n
        return np.broadcast_to(v[:, None, None], (n, 40, 40)).copy(), None, None
    monkeypatch.setattr(kos.K, "hucreye", sahte)
    kl = tmp_path / "kod"; kl.mkdir(); (tmp_path / "kayit").mkdir()
    monkeypatch.setattr(kos, "KOD", kl); monkeypatch.setattr(kos, "KAYIT", tmp_path / "kayit")
    sut = ["tur", "cift_no", "hedef_kimlik", "dunya_saha", "enlem", "boylam", "gorev", "kaynak", "ilk_cift", "kaynak_yeri", "sude_kontrol"]
    v1 = pd.DataFrame([{"tur": "V1", "cift_no": i, "hedef_kimlik": f"H{i}", "dunya_saha": f"S{i}", "enlem": 0, "boylam": 0,
                        "gorev": "geology", "kaynak": "k", "ilk_cift": "evet", "kaynak_yeri": "", "sude_kontrol": ""} for i in range(1, 12)])[sut]
    v1.to_csv(kl / "dogrulama_ciftleri.csv", index=False, encoding="utf-8-sig")
    kos.v2_ciftleri()
    c = pd.read_csv(kl / "dogrulama_ciftleri.csv", encoding="utf-8-sig")
    v2 = c[c["tur"] == "V2"]
    assert len(v2) == 22 and list(c.columns) == sut
    sec = [int(s.split()[-1]) for s in v2["dunya_saha"]]
    assert len(set(sec)) == 22                                                   # tekrarsız
    orm = [int(s.split()[-1]) for s in v2["dunya_saha"] if "ormanı" in s]
    tar = [int(s.split()[-1]) for s in v2["dunya_saha"] if "tarım" in s]
    assert all((k - 1) // 2 < 60 for k in orm) and all((k - 1) // 2 >= 440 for k in tar)
    kos.v2_ciftleri()                                                             # ikinci çağrı dokunmaz
    assert len(pd.read_csv(kl / "dogrulama_ciftleri.csv", encoding="utf-8-sig")) == 33
''', encoding="utf-8")
r = subprocess.run([sys.executable, str(KOD / "kos.py"), "--help"], cwd=KOD, capture_output=True, text=True)
assert r.returncode == 0 and "kayip" in r.stdout, r.stderr
if str(KOD) not in sys.path: sys.path.insert(0, str(KOD))
import test_kos; importlib.reload(test_kos)
test_kos.calistir("D4_test_kos_kayip", ["testler/test_kos_hatti.py", "testler/test_kos_puanla.py", "testler/test_kos_v5_d7.py",
                                       "testler/test_kos_katmanb.py", "testler/test_kos_katmanb_puan.py", "testler/test_kos_d8.py"])
