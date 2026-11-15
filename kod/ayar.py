# Developed with assistance from Claude (Anthropic).
"""Orbitrary ayarları (belge 8.4): KOK, klasörler, tohum, parametre okuma, görev ağırlıkları."""
import json, hashlib
from pathlib import Path
import numpy as np

KOK = Path.home() / "orbitrary"
KLASOR = {ad: KOK / ad for ad in ("veri", "temiz", "kod", "ara", "sonuc", "docs", "makale", "kayit")}
AYAR_YOLU = KOK / "kod" / "ayar.json"
with open(AYAR_YOLU, encoding="utf-8") as _f:
    _AYAR = json.load(_f)

KATEGORILER = ["topografya", "topoloji", "jeoloji", "mineraloji", "termal", "su_buz", "toz", "aydinlanma"]  # k = 1..8
GOREVLER = ["genel", "mobility", "geology", "ice", "astro"]
CISIMLER = ["dunya", "ay", "mars"]


def _yaprak(anahtar):
    d = _AYAR["parametreler"]
    for p in anahtar.split("."):
        d = d[p]
    if not (isinstance(d, dict) and "deger" in d):
        raise KeyError(f"{anahtar} bir parametre değil")
    return d


def ayar(anahtar):
    """Noktalı anahtarın değeri (ör. 'kapi.buz.ana'). Belirlenmemiş değer okunursa ValueError."""
    d = _yaprak(anahtar)
    if d["deger"] is None:
        raise ValueError(f"{anahtar} henüz belirlenmedi: {d.get('durum')}")
    return d["deger"]


def kaynak(anahtar):
    return _yaprak(anahtar)["kaynak"]


def yapraklar(d=None, yol=""):
    """Bütün parametreler: (anahtar, yaprak sözlüğü)."""
    d = _AYAR["parametreler"] if d is None else d
    for k, v in d.items():
        y = f"{yol}.{k}" if yol else k
        if isinstance(v, dict) and "deger" in v:
            yield y, v
        elif isinstance(v, dict):
            yield from yapraklar(v, y)


TOHUM = ayar("tohum")


def rng(alt=None):
    """alt=None: default_rng(20261113); alt=sayı: aynı tohumdan sabit alt akış (ayar alt_tohum)."""
    if alt is None:
        return np.random.default_rng(TOHUM)
    return np.random.default_rng(np.random.SeedSequence(TOHUM, spawn_key=(int(alt),)))


def agirliklar(gorev, sema="kademeli"):
    """Belge 7.3: w_k(g); k = 1..8 sırasıyla 8 elemanlı dizi."""
    n = len(KATEGORILER)
    if gorev == "genel" or sema == "esit":
        return np.full(n, 1.0 / n)
    A = ayar("agirlik.ana_kategoriler")[gorev]
    m, pay = len(A), ayar("agirlik.ana_pay")
    return np.array([pay / m if k in A else (1 - pay) / (n - m) for k in range(1, n + 1)])


def ayar_sha256():
    return hashlib.sha256(AYAR_YOLU.read_bytes()).hexdigest()
