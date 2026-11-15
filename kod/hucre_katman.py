# Developed with assistance from Claude (Anthropic).
# 17.4 sıra 3: kod\\katman.py + testler (belge 4.4; 8.3 veri testleri). Okuyucular kayit\\temiz_envanter.json'a göre.
import json, sys, subprocess, datetime
from pathlib import Path

KOK = Path.home() / "orbitrary"
KOD, KAYIT = KOK / "kod", KOK / "kayit"

KATMAN_PY = r'''# Developed with assistance from Claude (Anthropic).
"""Belge 4.4: temiz\\ okuyucuları ve hücreye aktarma (ortalama / coarse / sınıf payı).

Konum kuralları (her biri dosyadan okunur ve assert edilir):
- Coğrafi ızgara: x0 = batı kenarı, dx; y0 = kuzey kenarı, dy (derece). Dosya transform'u beklenen
  ppd değerine 1e-9 içinde değilse durur; tam kesir kullanılır.
- LOLA (M1), SWIM (R7): dosya metre cinsinden basit silindirik; yarıçap transform'dan çıkarılır,
  beklenen yarıçapla assert edilir, dereceye çevrilir.
- MOLA (R1): transform kullanılmaz; satır = ⌊(90 − φ)·128⌋, sütun = ⌊(λ + 180)·128⌋ (belge 4.1, 10.3).
- PGDA (M7): x = ρ sin λ, y = ρ cos λ, ρ = 2R tan(kolat/2), 240 m, satır = ⌊(yarım − y)/240⌋,
  sütun = ⌊(x + yarım)/240⌋ (belge 6.8, 10.2; dosya CRS'i kullanılmaz).
- E7, E8, E10: pyproj ile dosyanın CRS'ine; transform dosyadan.
- Tablolar: GCP (0,5° hücre, gece 18:00–06:00 ortalaması), PRP (en yakın üçgen merkezi),
  LP GRS (2° eş-alanlı piksel sınırları), LP hidrojen (0,5° tablo).

Hücreye aktarma (belge 4.4): pencere hücresinin büyük piksel kenarı δv < δ ise hücre içinde
s × s alt nokta (s = ⌈k·δ / küçük kenar⌉, k = katman.piksel_basina_ornek, en az 2, en fazla
katman.alt_ornek_en_fazla) örneklenir
ve ortalanır (alan ağırlıklı piksel ortalaması); δv ≥ δ ise hücre merkezinin pikseli alınır (coarse = 1).
"""
import json
import math
import warnings
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

import ayar as A
import izgara as Z

TEMIZ = A.KLASOR["temiz"]
ARA = A.KLASOR["ara"]
BLOK_SINIRI_BAYT = 768 * 1024 * 1024  # tam genişlik bant okumada en fazla bellek (proje kararı, 34 GB RAM)


def _json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _yakin(a, b, tol, ne):
    assert abs(a - b) <= tol, f"{ne}: {a} ≠ {b} (tolerans {tol})"


# ---------------------------------------------------------------- ızgara okuyucuları
class _Blok:
    """Dosyadan okunan dikdörtgen parçanın önbelleği (tek blok)."""

    def __init__(self):
        self.r0 = self.r1 = self.c0 = self.c1 = -1
        self.veri = None

    def icinde(self, r0, r1, c0, c1):
        return self.veri is not None and r0 >= self.r0 and r1 <= self.r1 and c0 >= self.c0 and c1 <= self.c1


class Izgara:
    """Ortak satır/sütun okuma. Alt sınıflar satir_sutun(lat, lon) → (satır, sütun, geçerli) verir."""

    tur = "izgara"

    def __init__(self, ad, kaynak, nrow, ncol, birim, kuresel=False):
        self.ad, self.kaynak, self.nrow, self.ncol, self.birim = ad, kaynak, int(nrow), int(ncol), birim
        self.kuresel = kuresel
        self._blok = _Blok()
        if isinstance(kaynak, np.ndarray):
            assert kaynak.shape[-2:] == (self.nrow, self.ncol), (ad, kaynak.shape, (nrow, ncol))
        else:  # rasterio veri seti; referans nesnede tutulur
            assert (kaynak.height, kaynak.width) == (self.nrow, self.ncol), (ad, (kaynak.height, kaynak.width), (nrow, ncol))

    def _dosyadan(self, r0, r1, c0, c1):
        if isinstance(self.kaynak, np.ndarray):
            return np.asarray(self.kaynak[r0:r1, c0:c1], dtype=np.float32)
        from rasterio.windows import Window
        return self.kaynak.read(1, window=Window(c0, r0, c1 - c0, r1 - r0)).astype(np.float32)

    def _oku(self, rmin, rmax, cmin, cmax, tam_genislik):
        r1, c1 = rmax + 1, cmax + 1
        if tam_genislik:
            cmin, c1 = 0, self.ncol
        if not self._blok.icinde(rmin, r1, cmin, c1):
            pay = max(16, (r1 - rmin) // 4)
            r0n, r1n = max(0, rmin - pay), min(self.nrow, r1 + pay)
            if (r1n - r0n) * self.ncol * 4 <= BLOK_SINIRI_BAYT:
                c0n, c1n = 0, self.ncol
            else:
                cp = max(16, (c1 - cmin) // 4)
                c0n, c1n = max(0, cmin - cp), min(self.ncol, c1 + cp)
            self._blok.veri = self._dosyadan(r0n, r1n, c0n, c1n)
            self._blok.r0, self._blok.r1, self._blok.c0, self._blok.c1 = r0n, r1n, c0n, c1n
        return self._blok

    def _tekil(self, rg, cg):
        """Seyrek noktalar: numpy kaynağında doğrudan indeks; rasterio'da piksel başına 1 × 1 okuma
        ya da satır dilimleri (blok sınırı aşılmadan)."""
        if isinstance(self.kaynak, np.ndarray):
            return np.asarray(self.kaynak[rg, cg], dtype=np.float32)
        out = np.empty(rg.size, np.float32)
        if rg.size <= 20000:
            from rasterio.windows import Window
            for k in range(rg.size):
                out[k] = self.kaynak.read(1, window=Window(int(cg[k]), int(rg[k]), 1, 1))[0, 0]
            return out
        h = max(1, BLOK_SINIRI_BAYT // (self.ncol * 4))
        for r0 in range(int(rg.min()), int(rg.max()) + 1, h):
            m = (rg >= r0) & (rg < r0 + h)
            if m.any():
                b = self._oku(int(rg[m].min()), int(rg[m].max()), 0, self.ncol - 1, True)
                out[m] = b.veri[rg[m] - b.r0, cg[m] - b.c0]
        return out

    def ornekle(self, lat, lon):
        """Noktaların piksel değerleri (noktanın düştüğü piksel); kapsam dışı NaN."""
        lat = np.asarray(lat, dtype=float)
        lon = np.asarray(lon, dtype=float)
        sekil = np.broadcast(lat, lon).shape
        lat, lon = np.broadcast_to(lat, sekil).ravel(), np.broadcast_to(lon, sekil).ravel()
        cikti = np.full(lat.size, np.nan, dtype=np.float32)
        r, c, g = self.satir_sutun(lat, lon)
        if g.any():
            rg, cg = r[g], c[g]
            tam = self.kuresel and (cg.max() - cg.min() + 1) > self.ncol // 2
            genislik = self.ncol if tam else int(cg.max() - cg.min() + 1)
            if (int(rg.max() - rg.min()) + 1) * genislik * 4 > BLOK_SINIRI_BAYT:
                cikti[g] = self._tekil(rg, cg)
            else:
                b = self._oku(int(rg.min()), int(rg.max()), int(cg.min()), int(cg.max()), tam)
                cikti[g] = b.veri[rg - b.r0, cg - b.c0]
        return cikti.reshape(sekil)

    def cozunurluk_km(self, lat, r):
        raise NotImplementedError


class Cografi(Izgara):
    """Düzenli enlem-boylam ızgarası (derece)."""

    tur = "cografi"

    def __init__(self, ad, kaynak, x0, dx, y0, dy, nrow, ncol, birim):
        kuresel = abs(ncol * dx - 360.0) < 1e-6
        super().__init__(ad, kaynak, nrow, ncol, birim, kuresel)
        self.x0, self.dx, self.y0, self.dy = float(x0), float(dx), float(y0), float(dy)
        assert self.dx > 0 and self.dy > 0

    def satir_sutun(self, lat, lon):
        g = np.isfinite(lat) & np.isfinite(lon)
        if self.kuresel:
            lon = self.x0 + np.mod(lon - self.x0, 360.0)
        with np.errstate(invalid="ignore"):
            c = np.floor((lon - self.x0) / self.dx)
            r = np.floor((self.y0 - lat) / self.dy)
        if self.kuresel:
            c = np.where(c >= self.ncol, c - self.ncol, c)
        # alt kenar tam üstünde (ör. güney kutbu −90°): son satır
        r = np.where(np.isclose(lat, self.y0 - self.nrow * self.dy, rtol=0, atol=1e-12), self.nrow - 1, r)
        g &= (r >= 0) & (r < self.nrow) & (c >= 0) & (c < self.ncol)
        return np.where(g, r, 0).astype(np.int64), np.where(g, c, 0).astype(np.int64), g

    def cozunurluk_km(self, lat, r):
        """(büyük kenar, küçük kenar) km, verilen enlemde."""
        dy = self.dy * math.pi * r / 180.0
        dx = self.dx * math.pi * r / 180.0 * max(math.cos(math.radians(lat)), 1e-6)
        return max(dx, dy), min(dx, dy)


class Projeksiyon(Izgara):
    """Projeksiyonlu ızgara; donustur(lat, lon) → (x, y) metre; transform dosyadan."""

    tur = "projeksiyon"

    def __init__(self, ad, kaynak, donustur, x0, px, y0, py, nrow, ncol, birim):
        super().__init__(ad, kaynak, nrow, ncol, birim, kuresel=False)
        self.donustur = donustur
        self.x0, self.px, self.y0, self.py = float(x0), float(px), float(y0), float(py)
        assert self.px > 0 and self.py > 0

    def satir_sutun(self, lat, lon):
        g = np.isfinite(lat) & np.isfinite(lon)
        x, y = self.donustur(np.where(g, lat, 0.0), np.where(g, lon, 0.0))
        g &= np.isfinite(x) & np.isfinite(y)
        with np.errstate(invalid="ignore"):
            c = np.floor((x - self.x0) / self.px)
            r = np.floor((self.y0 - y) / self.py)
        g &= (r >= 0) & (r < self.nrow) & (c >= 0) & (c < self.ncol)
        return np.where(g, r, 0).astype(np.int64), np.where(g, c, 0).astype(np.int64), g

    def cozunurluk_km(self, lat, r):
        return max(self.px, self.py) / 1000.0, min(self.px, self.py) / 1000.0


def pgda_xy(lat, lon, kutup, R_m):
    """Belge 6.8 / 10.2: x = ρ sin λ, y = ρ cos λ, ρ = 2R tan(kolat/2). Diğer yarıküre NaN."""
    lat = np.asarray(lat, float)
    lon = np.asarray(lon, float)
    kolat = np.radians(90.0 - lat) if kutup == "n" else np.radians(90.0 + lat)
    dogru = (lat > 0) if kutup == "n" else (lat < 0)
    rho = 2.0 * R_m * np.tan(kolat / 2.0)
    lam = np.radians(lon)
    x = np.where(dogru, rho * np.sin(lam), np.nan)
    y = np.where(dogru, rho * np.cos(lam), np.nan)
    return x, y


# ---------------------------------------------------------------- tablo okuyucuları
class Ucgen:
    """Diviner PRP: en yakın üçgen merkezi. Eşik = ucgen_esik_carpani × ortanca komşu aralığı (proje kararı)."""

    tur = "ucgen"

    def __init__(self, ad, lat, lon, deger, r, birim):
        lat, lon, deger = (np.asarray(v, dtype=float).ravel() for v in (lat, lon, deger))
        assert lat.shape == lon.shape == deger.shape
        assert np.isfinite(lat).all() and np.isfinite(lon).all()
        self.ad, self.r, self.birim = ad, float(r), birim
        self.deger = deger.astype(np.float32)
        self.agac = cKDTree(Z.birim_vektor(np.radians(lat), np.radians(lon)))
        g = np.random.default_rng(0)
        k = g.choice(lat.size, min(20000, lat.size), replace=False)
        d, _ = self.agac.query(Z.birim_vektor(np.radians(lat[k]), np.radians(lon[k])), k=2)
        self.aralik_km = float(np.median(2 * self.r * np.arcsin(d[:, 1] / 2)))
        self.esik_km = float(A.ayar("katman.ucgen_esik_carpani")) * self.aralik_km
        self.kapsama_min_abs_enlem = float(np.min(np.abs(lat)))

    def ornekle(self, lat, lon):
        lat = np.asarray(lat, float)
        lon = np.asarray(lon, float)
        sekil = np.broadcast(lat, lon).shape
        v = Z.birim_vektor(np.radians(np.broadcast_to(lat, sekil).ravel()), np.radians(np.broadcast_to(lon, sekil).ravel()))
        d, i = self.agac.query(v, k=1)
        dk = 2 * self.r * np.arcsin(np.clip(d / 2, 0, 1))
        out = np.where(dk <= self.esik_km, self.deger[i], np.nan).astype(np.float32)
        return out.reshape(sekil)

    def cozunurluk_km(self, lat, r):
        return self.aralik_km, self.aralik_km


class EsAlan:
    """LP GRS 2° eş-alanlı pikseller: satır = enlem bandı, bant içinde boylam aralığı."""

    tur = "esalan"

    def __init__(self, ad, min_lat, max_lat, min_lon, max_lon, deger, birim):
        self.ad, self.birim = ad, birim
        min_lat, max_lat, min_lon, max_lon, deger = (np.asarray(v, float) for v in (min_lat, max_lat, min_lon, max_lon, deger))
        self.lon_360 = bool(min_lon.min() >= 0 and max_lon.max() > 180)
        bantlar = np.unique(np.stack([min_lat, max_lat], 1), axis=0)
        bantlar = bantlar[np.argsort(bantlar[:, 0])]
        assert abs(bantlar[0, 0] + 90) < 1e-9 and abs(bantlar[-1, 1] - 90) < 1e-9, "enlem kapsamı −90…90 değil"
        assert np.allclose(bantlar[1:, 0], bantlar[:-1, 1]), "enlem bantları bitişik değil"
        self.bant_ust = bantlar[:, 1]
        self.bant_lon0, self.bant_deger = [], []
        for lo, hi in bantlar:
            m = (min_lat == lo) & (max_lat == hi)
            o = np.argsort(min_lon[m])
            a, b = min_lon[m][o], max_lon[m][o]
            assert np.allclose(a[1:], b[:-1]), f"{ad}: {lo}…{hi} bandında boylam aralıkları bitişik değil"
            assert abs((b[-1] - a[0]) - 360.0) < 1e-6, f"{ad}: {lo}…{hi} bandı 360° kapsamıyor"
            self.bant_lon0.append(a)
            self.bant_deger.append(deger[m][o].astype(np.float32))
        self.lon_bas = np.array([a[0] for a in self.bant_lon0])

    def ornekle(self, lat, lon):
        lat = np.asarray(lat, float)
        lon = np.asarray(lon, float)
        sekil = np.broadcast(lat, lon).shape
        lat, lon = np.broadcast_to(lat, sekil).ravel(), np.broadcast_to(lon, sekil).ravel()
        out = np.full(lat.size, np.nan, np.float32)
        bi = np.minimum(np.searchsorted(self.bant_ust, lat, side="right"), len(self.bant_ust) - 1)
        for b in np.unique(bi):
            m = bi == b
            a0 = self.bant_lon0[b]
            L = a0[0] + np.mod(lon[m] - a0[0], 360.0)
            k = np.clip(np.searchsorted(a0, L, side="right") - 1, 0, len(a0) - 1)
            out[m] = self.bant_deger[b][k]
        return out.reshape(sekil)

    def cozunurluk_km(self, lat, r):
        return 2.0 * math.pi * r / 180.0, 2.0 * math.pi * r / 180.0


def hidrojen_izgara(tablo):
    """M6: (enlem_g, enlem_k, boylam_b, boylam_d, H_ppm) → 360 × 720 dizi, x0 = −180, y0 = 90, 0,5°."""
    g_, k_, b_, d_, h_ = (tablo[:, i] for i in range(5))
    assert np.allclose(k_ - g_, 0.5), "hidrojen: enlem aralığı 0,5° değil"
    gen = np.mod(d_ - b_, 360.0)
    assert np.allclose(gen, 0.5), "hidrojen: boylam aralığı 0,5° değil"
    lat_c = (g_ + k_) / 2.0
    lon_c = np.mod(b_ + gen / 2.0 + 180.0, 360.0) - 180.0
    r = np.floor((90.0 - lat_c) / 0.5).astype(np.int64)
    c = np.floor((lon_c + 180.0) / 0.5).astype(np.int64)
    assert r.min() == 0 and r.max() == 359 and c.min() == 0 and c.max() == 719
    dizi = np.full((360, 720), np.nan, np.float32)
    say = np.zeros((360, 720), np.int64)
    np.add.at(say, (r, c), 1)
    assert (say == 1).all(), "hidrojen: her 0,5° hücre tam bir kez olmalı"
    dizi[r, c] = h_
    return dizi


def gcp_gece_izgara(bantlar, kutup):
    """M4 GCP: bantlar = [(clat, clon, ltim, tbol), ...] → 40 × 720 gece ortalaması (yerel saat 18:00–06:00).
    Kuzey: y0 = 90 (90 → 70); güney: y0 = −70 (−70 → −90). x0 = −180, 0,5°."""
    bas, bit = (float(v) for v in A.ayar("termal.ay_gcp_yerel_saat"))
    y0 = 90.0 if kutup == "n" else -70.0
    top = np.zeros((40, 720))
    say = np.zeros((40, 720), np.int64)
    satir_say = np.zeros((40, 720), np.int64)
    for clat, clon, ltim, tbol in bantlar:
        assert np.isfinite(clat).all() and np.isfinite(clon).all() and np.isfinite(ltim).all()
        assert ltim.min() >= 0 and ltim.max() <= 24, "GCP ltim 0–24 saat değil"
        assert len(np.unique(ltim)) == 96, f"GCP: {len(np.unique(ltim))} farklı yerel saat (96 bekleniyor)"
        assert np.allclose(np.mod(clat * 4, 2), 1), "GCP clat 0,25 / 0,75 merkezlerinde değil"
        r = np.floor((y0 - clat) / 0.5).astype(np.int64)
        lon = np.mod(clon + 180.0, 360.0) - 180.0
        c = np.floor((lon + 180.0) / 0.5).astype(np.int64)
        assert r.min() >= 0 and r.max() < 40 and c.min() >= 0 and c.max() < 720
        gece = (ltim >= bas) | (ltim < bit)
        np.add.at(satir_say, (r[gece], c[gece]), 1)
        gg = gece & np.isfinite(tbol)
        np.add.at(top, (r[gg], c[gg]), tbol[gg])
        np.add.at(say, (r[gg], c[gg]), 1)
    assert (satir_say == 48).all(), f"GCP: hücre başına gece satırı {np.unique(satir_say)} (48 bekleniyor)"
    with np.errstate(invalid="ignore", divide="ignore"):
        dizi = np.where(say > 0, top / np.maximum(say, 1), np.nan).astype(np.float32)
    return dizi, y0


# ---------------------------------------------------------------- vektör (sınıf)
class Vektor:
    """Poligon katmanı; sinif(lat, lon) → birim kodu (−1: poligon yok). Belge 4.4: hücre başına 5 × 5 nokta."""

    tur = "vektor"

    def __init__(self, ad, geometriler, birimler, crs_wkt):
        import shapely
        from pyproj import CRS, Transformer
        self.ad = ad
        self.geom = np.asarray(geometriler)
        birimler = np.asarray(birimler).astype(str)
        self.siniflar, self.kod = np.unique(birimler, return_inverse=True)
        self.agac = shapely.STRtree(self.geom)
        crs = CRS.from_user_input(crs_wkt)
        self.cografi = crs.is_geographic
        self._tr = None if self.cografi else Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
        xmin, ymin, xmax, ymax = shapely.total_bounds(self.geom)
        self.lon_360 = bool(self.cografi and xmin >= 0 and xmax > 180)
        self.gecersiz_sayisi = int((~shapely.is_valid(self.geom)).sum())

    @classmethod
    def gpkg(cls, ad, yol, katman):
        import pyogrio
        import shapely
        meta, _, wkb, alanlar = pyogrio.raw.read(yol, layer=katman, columns=["birim"], return_fids=False)
        geom = shapely.from_wkb(wkb)
        v = cls(ad, geom, alanlar[0], meta["crs"])
        v.gecersiz_sayisi = int((~shapely.is_valid(geom)).sum())
        return v

    def _xy(self, lat, lon):
        if self.cografi:
            return (np.mod(lon, 360.0) if self.lon_360 else lon), lat
        return self._tr.transform(lon, lat)

    def sinif(self, lat, lon):
        import shapely
        lat = np.asarray(lat, float)
        lon = np.asarray(lon, float)
        sekil = np.broadcast(lat, lon).shape
        x, y = self._xy(np.broadcast_to(lat, sekil).ravel(), np.broadcast_to(lon, sekil).ravel())
        x, y = np.asarray(x, float), np.asarray(y, float)
        out = np.full(x.size, -1, np.int64)
        g = np.isfinite(x) & np.isfinite(y)
        if not g.any():
            return out.reshape(sekil)
        aday = self.agac.query(shapely.box(x[g].min(), y[g].min(), x[g].max(), y[g].max()))
        for k in aday:
            p = self.geom[k]
            x0, y0, x1, y1 = shapely.bounds(p)
            m = g & (out < 0) & (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
            if not m.any():
                continue
            shapely.prepare(p)
            ic = shapely.contains_xy(p, x[m], y[m])
            shapely.destroy_prepared(p)
            idx = np.flatnonzero(m)[ic]
            out[idx] = self.kod[k]
        return out.reshape(sekil)


# ---------------------------------------------------------------- hücreye aktarma
def _alt_noktalar(phi0, lam0, r, genisletme, s):
    """Pencereler × hücreler × s × s alt noktanın (enlem, boylam) dereceleri. Biçim (nw, n, n, s, s): [w, j, i, b, a].
    Alt nokta: x = x_i + δ((a + ½)/s − ½), y = y_j + δ((b + ½)/s − ½)."""
    c = Z.hucre_merkezleri(genisletme)
    n = len(c)
    d = float(A.ayar("izgara.delta_m")) / 1000.0
    o = d * ((np.arange(s) + 0.5) / s - 0.5)
    k = c[:, None] + o[None, :]                                  # [i, a] ya da [j, b]
    X = np.broadcast_to(k[None, :, None, :], (n, n, s, s))       # [j, i, b, a] ← x_i + o_a
    Y = np.broadcast_to(k[:, None, :, None], (n, n, s, s))       # [j, i, b, a] ← y_j + o_b
    phi0 = np.asarray(phi0, float)[:, None, None, None, None]
    lam0 = np.asarray(lam0, float)[:, None, None, None, None]
    phi, lam = Z.lambert_geri(X[None], Y[None], phi0, lam0, r)
    lon = np.degrees(lam)
    return np.degrees(phi), np.where(lon >= 180.0, lon - 360.0, lon)


def alt_ornek_sayisi(katman, lat0_der, r):
    """Belge 4.4: δv < δ → ortalama (s ≥ 2), δv ≥ δ → coarse (s = 1)."""
    d = float(A.ayar("izgara.delta_m")) / 1000.0
    buyuk, kucuk = katman.cozunurluk_km(lat0_der, r)
    if buyuk >= d:
        return 1
    k = float(A.ayar("katman.piksel_basina_ornek"))
    return int(min(int(A.ayar("katman.alt_ornek_en_fazla")), max(2, math.ceil(k * d / kucuk))))


def hucreye(katman, phi0, lam0, r, genisletme=0, alt=False, s=None):
    """Belge 4.4 sürekli katman. phi0, lam0: pencere merkezleri (radyan, dizi).
    Dönüş: (değer [nw, n, n] ya da alt=True ise [nw, n, n, s·s], coarse [nw] bool, s [nw])."""
    phi0 = np.atleast_1d(np.asarray(phi0, float))
    lam0 = np.atleast_1d(np.asarray(lam0, float))
    n = int(A.ayar("izgara.N")) + 2 * genisletme
    ss = np.array([s if s is not None else alt_ornek_sayisi(katman, math.degrees(p), r) for p in phi0])
    smax = int(ss.max())
    deger = np.full((len(phi0), n, n, smax * smax) if alt else (len(phi0), n, n), np.nan, np.float32)
    for sv in np.unique(ss):
        idx = np.flatnonzero(ss == sv)
        parca = max(1, int(4_000_000 // (n * n * sv * sv)))
        for k in range(0, len(idx), parca):
            w = idx[k:k + parca]
            lat, lon = _alt_noktalar(phi0[w], lam0[w], r, genisletme, int(sv))
            v = katman.ornekle(lat, lon).reshape(len(w), n, n, int(sv) * int(sv))
            if alt:
                deger[w, :, :, : sv * sv] = v
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    deger[w] = np.nanmean(v, axis=3)
    return deger, ss == 1, ss


def hucreye_sinif(vektor, phi0, lam0, r, genisletme=0, s=None):
    """Belge 4.4 kategorik (vektör): hücre başına s × s nokta (ayar katman.vektor_alt_ornek), sınıf payları.
    Dönüş: pay [nw, n, n, C] (geçerli nokta yoksa NaN), geçerli nokta sayısı [nw, n, n]."""
    s = int(A.ayar("katman.vektor_alt_ornek")) if s is None else int(s)
    phi0 = np.atleast_1d(np.asarray(phi0, float))
    lam0 = np.atleast_1d(np.asarray(lam0, float))
    n = int(A.ayar("izgara.N")) + 2 * genisletme
    C = len(vektor.siniflar)
    pay = np.full((len(phi0), n, n, C), np.nan, np.float32)
    gecerli = np.zeros((len(phi0), n, n), np.int16)
    for w in range(len(phi0)):
        lat, lon = _alt_noktalar(phi0[w:w + 1], lam0[w:w + 1], r, genisletme, s)
        kod = vektor.sinif(lat, lon).reshape(n, n, s * s)
        say = np.zeros((n, n, C), np.int32)
        jj, ii, kk = np.nonzero(kod >= 0)
        np.add.at(say, (jj, ii, kod[jj, ii, kk]), 1)
        toplam = say.sum(axis=2)
        gecerli[w] = toplam
        with np.errstate(invalid="ignore", divide="ignore"):
            pay[w] = np.where(toplam[..., None] > 0, say / np.maximum(toplam[..., None], 1), np.nan)
    return pay, gecerli


# ---------------------------------------------------------------- temiz\ katmanları
def _npy_cografi(ad, yol_npy, beklenen_ppd=None):
    j = _json(Path(yol_npy).with_suffix(".json"))
    gt = j["geotransform"]
    assert gt[2] == 0 and gt[4] == 0, f"{ad}: döndürülmüş geotransform"
    a = np.load(yol_npy, mmap_mode="r")
    assert list(a.shape) == list(j["sekil"]), (ad, a.shape, j["sekil"])
    dx, dy = gt[1], -gt[5]
    if beklenen_ppd is not None:
        _yakin(dx, 1.0 / beklenen_ppd, 1e-9, f"{ad} dx")
        _yakin(dy, 1.0 / beklenen_ppd, 1e-9, f"{ad} dy")
        dx = dy = 1.0 / beklenen_ppd
    return Cografi(ad, a, gt[0], dx, gt[3], dy, a.shape[0], a.shape[1], j.get("birim", ""))


def _tif_cografi(ad, yol, ppd, x0, y0, birim):
    import rasterio
    ds = rasterio.open(yol)
    t = ds.transform
    assert t.b == 0 and t.d == 0, f"{ad}: döndürülmüş transform"
    _yakin(t.a, 1.0 / ppd, 1e-9, f"{ad} dx")
    _yakin(-t.e, 1.0 / ppd, 1e-9, f"{ad} dy")
    _yakin(t.c, x0, 1e-6, f"{ad} x0")
    _yakin(t.f, y0, 1e-6, f"{ad} y0")
    return Cografi(ad, ds, x0, 1.0 / ppd, y0, 1.0 / ppd, ds.height, ds.width, birim)


def _tif_metre_silindirik(ad, yol, R_beklenen_m, ppd, y0_der, birim):
    """LOLA, SWIM: metre cinsinden basit silindirik → derece (yarıçap transform'dan, assert)."""
    import rasterio
    ds = rasterio.open(yol)
    t = ds.transform
    assert t.b == 0 and t.d == 0
    R = -t.c / math.pi
    _yakin(R, R_beklenen_m, 1.0, f"{ad} yarıçap (transform'dan)")
    _yakin(t.a, 2 * math.pi * R / (360 * ppd), 1e-3, f"{ad} piksel (m)")
    _yakin(t.f, y0_der * math.pi * R / 180.0, 1.0, f"{ad} y0 (m)")
    return Cografi(ad, ds, -180.0, 1.0 / ppd, y0_der, 1.0 / ppd, ds.height, ds.width, birim)


def _tif_proj(ad, yol, birim):
    import rasterio
    from pyproj import Transformer
    ds = rasterio.open(yol)
    t = ds.transform
    assert t.b == 0 and t.d == 0
    tr = Transformer.from_crs("EPSG:4326", ds.crs.to_wkt(), always_xy=True)

    def donustur(lat, lon):
        x, y = tr.transform(lon, lat)
        return np.asarray(x, float), np.asarray(y, float)

    return Projeksiyon(ad, ds, donustur, t.c, t.a, t.f, -t.e, ds.height, ds.width, birim)


def _etopo_vrt():
    """E1: 288 karo → ara\\etopo_e1.vrt. Her karonun transform'u adındaki üst-sol köşeyle assert edilir."""
    import re
    import rasterio
    kl = TEMIZ / "dunya" / "E1_etopo"
    karolar = sorted(kl.glob("ETOPO_2022_v1_15s_*_surface.tif"))
    assert len(karolar) == 288, len(karolar)
    for p in karolar:
        m = re.search(r"_([NS])(\d\d)([EW])(\d\d\d)_", p.name)
        lat = (1 if m[1] == "N" else -1) * int(m[2])
        lon = (1 if m[3] == "E" else -1) * int(m[4])
        with rasterio.open(p) as ds:
            _yakin(ds.transform.c, lon, 1e-9, f"{p.name} x0")
            _yakin(ds.transform.f, lat, 1e-9, f"{p.name} y0")
            _yakin(ds.transform.a, 1 / 240, 1e-12, f"{p.name} dx")
            assert (ds.height, ds.width) == (3600, 3600)
    vrt = ARA / "etopo_e1.vrt"
    if not vrt.exists():
        from osgeo import gdal
        gdal.UseExceptions()
        v = gdal.BuildVRT(str(vrt), [str(p) for p in karolar])
        v.FlushCache()
        v = None
    return vrt


_ONBELLEK = {}


def ac(ad):
    """Katman adından okuyucu (bir kez açılır, tutulur). Adlar FONKSIYONLAR.md'de."""
    if ad in _ONBELLEK:
        return _ONBELLEK[ad]
    k = _ac(ad)
    _ONBELLEK[ad] = k
    return k


def aylik(kod, onek):
    """Dünya aylık katman adları: aylik("E4", "yayinim_b12") → ["yayinim_b12_2015001", …] (dosyalardan)."""
    import re
    kl = _kl("dunya", kod)
    adlar = sorted(p.stem for p in kl.glob(f"{onek}_*.npy") if re.fullmatch(rf"{re.escape(onek)}_\d{{7}}", p.stem))
    assert len(adlar) == 12, (kod, onek, len(adlar))
    return adlar


def _kl(govde, kod):
    k = sorted((TEMIZ / govde).glob(f"{kod}_*"))
    assert len(k) == 1, (govde, kod, k)
    return k[0]


def _ac(ad):
    R = {g: float(A.ayar("cisim.yaricap_km")[g]) for g in ("dunya", "ay", "mars")}
    # ---- Dünya
    if ad == "etopo":
        import rasterio
        ds = rasterio.open(_etopo_vrt())
        t = ds.transform
        _yakin(t.c, -180, 1e-9, "etopo x0"); _yakin(t.f, 90, 1e-9, "etopo y0")
        _yakin(t.a, 1 / 240, 1e-12, "etopo dx")
        assert (ds.height, ds.width) == (43200, 86400)
        return Cografi(ad, ds, -180.0, 1 / 240, 90.0, 1 / 240, 43200, 86400, "m")
    if ad.startswith("mcd12c1_"):
        return _npy_cografi(ad, _kl("dunya", "E2") / f"sinif_{ad[-2:]}_yuzde.npy", 20)
    for onek, kod in (("yayinim_b", "E4"), ("ndvi_bayrak_", "E4"), ("ndvi_", "E4"),
                      ("lst_gunduz_", "E5"), ("lst_gece_", "E5"), ("albedo_wsa_", "E6")):
        if ad.startswith(onek):
            return _npy_cografi(ad, _kl("dunya", kod) / f"{ad}.npy", 20)
    if ad == "perm_kuzey":
        return _tif_proj(ad, _kl("dunya", "E7") / "perprob_kuzey.tif", "olasılık")
    if ad == "perm_antarktika":
        return _tif_proj(ad, _kl("dunya", "E8") / "perprob_antarktika.tif", "olasılık")
    if ad in ("ai", "ai_bayrak"):
        m = _json(_kl("dunya", "E9") / "meta.json")
        _yakin(float(m["olcek"]), 1e-4, 0, "E9 ölçek (AI = ham / 10 000)")
        return _tif_cografi(ad, _kl("dunya", "E9") / f"{ad}.tif", 120, -180.0, 90.0, "AI")
    if ad in ("kil", "silt"):
        return _tif_proj(ad, _kl("dunya", "E10") / f"{ad}_0-5cm.tif", "‰")
    # ---- Ay
    if ad == "lola":
        return _tif_metre_silindirik(ad, _kl("ay", "M1") / "lola_m.tif", R["ay"] * 1000, 256, 90.0, "m")
    if ad in ("ra", "tbol"):
        dosya = "ra_sam.tif" if ad == "ra" else "tbol_sam_K.tif"
        return _tif_cografi(ad, _kl("ay", "M3") / dosya, 128, -180.0, 70.0, "" if ad == "ra" else "K")
    if ad.startswith("avgvisib_") or ad.startswith("lpsr_"):
        import rasterio
        kutup = ad[-1]
        ds = rasterio.open(_kl("ay", "M7") / f"{ad}.tif")
        t = ds.transform
        assert (ds.height, ds.width) == (6420, 6420) and t.a == 240 and t.e == -240
        yarim = 6420 * 240 / 2
        _yakin(t.c, -yarim, 1e-6, f"{ad} x0"); _yakin(t.f, yarim, 1e-6, f"{ad} y0")
        Rm = R["ay"] * 1000

        def donustur(lat, lon, kutup=kutup):
            return pgda_xy(lat, lon, kutup, Rm)

        return Projeksiyon(ad, ds, donustur, -yarim, 240.0, yarim, 240.0, 6420, 6420, "oran")
    if ad == "gcp_gece_n" or ad == "gcp_gece_s":
        kl = _kl("ay", "M4")
        kutup = ad[-1]
        bant_adlari = ["70n80n", "80n90n"] if kutup == "n" else ["80s70s", "90s80s"]
        bantlar = [tuple(np.load(kl / f"gcp_{b}_{s}.npy") for s in ("clat", "clon", "ltim", "tbol")) for b in bant_adlari]
        dizi, y0 = gcp_gece_izgara(bantlar, kutup)
        return Cografi(ad, dizi, -180.0, 0.5, y0, 0.5, 40, 720, "K")
    if ad.startswith("prp_"):  # prp_<temp_avg|temp_max|ice_depth_m|ice_depth_bayrak>, iki kutup birlikte
        kl = _kl("ay", "M4")
        alan = ad[4:]
        lat = np.concatenate([np.load(kl / f"prp_{k}_tri_clat.npy") for k in ("north", "south")])
        lon = np.concatenate([np.load(kl / f"prp_{k}_tri_clon.npy") for k in ("north", "south")])
        v = np.concatenate([np.load(kl / f"prp_{k}_{alan}.npy") for k in ("north", "south")])
        return Ucgen(ad, lat, lon, v, R["ay"], alan)
    if ad.startswith("lpgrs_"):
        kl = _kl("ay", "M5")
        t = np.load(kl / "lpgrs_tablo.npy")
        sut = _json(kl / "lpgrs_tablo.json")["sutun_adlari"]
        i = {s: sut.index(s) for s in ("min_lat", "max_lat", "min_lon", "max_lon", ad[6:])}
        return EsAlan(ad, t[:, i["min_lat"]], t[:, i["max_lat"]], t[:, i["min_lon"]], t[:, i["max_lon"]], t[:, i[ad[6:]]], ad[6:])
    if ad == "hidrojen":
        kl = _kl("ay", "M6")
        sut = _json(kl / "hidrojen_tablo.json")["sutunlar"]
        assert sut == ["enlem_g", "enlem_k", "boylam_b", "boylam_d", "H_ppm"], sut
        return Cografi(ad, hidrojen_izgara(np.load(kl / "hidrojen_tablo.npy")), -180.0, 0.5, 90.0, 0.5, 360, 720, "ppm")
    # ---- Mars
    if ad == "mola":
        import rasterio
        ds = rasterio.open(_kl("mars", "R1") / "mola_m.tif")
        assert (ds.height, ds.width) == (23040, 46080)
        return Cografi(ad, ds, -180.0, 1 / 128, 90.0, 1 / 128, 23040, 46080, "m")  # belge 4.1: transform kullanılmaz
    if ad.startswith("tes_"):
        kl = _kl("mars", "R3")
        p = sorted(kl.glob(f"b??_{ad[4:]}.npy"))
        assert len(p) == 1, (ad, p)
        return _npy_cografi(ad, p[0], 4)
    if ad == "ti":
        return _npy_cografi(ad, _kl("mars", "R4") / "ti.npy", 20)
    if ad == "albedo_mars":
        return _npy_cografi(ad, _kl("mars", "R4") / "albedo.npy", 8)
    if ad == "dci":
        return _npy_cografi(ad, _kl("mars", "R5") / "dci.npy", 16)
    if ad == "swim":
        return _tif_metre_silindirik(ad, _kl("mars", "R7") / "swim4mim_ci_0_1.tif", 3396190.0, 20, 60.0, "CI")
    # ---- vektör
    if ad == "glim":
        return Vektor.gpkg(ad, _kl("dunya", "E3") / "glim.gpkg", "glim")
    if ad == "ay_jeoloji":
        return Vektor.gpkg(ad, _kl("ay", "M2") / "ay_jeoloji.gpkg", "ay_jeoloji")
    if ad == "sim3292":
        return Vektor.gpkg(ad, _kl("mars", "R2") / "sim3292.gpkg", "sim3292")
    raise KeyError(f"bilinmeyen katman: {ad}")
'''
TEST_KATMAN = r'''# Developed with assistance from Claude (Anthropic).
"""Belge 4.4 hücreye aktarma ve okuyucu çekirdeği: sentetik girdilerle (cevabı bilinen)."""
import math
import numpy as np
import pytest
import ayar as A
import izgara as Z
import katman as K

R_D = 6371.0


def test_cografi_yonelim_ve_sarma():
    a = (np.arange(180)[:, None] * 1000 + np.arange(360)[None, :]).astype(np.float32)
    k = K.Cografi("t", a, -180.0, 1.0, 90.0, 1.0, 180, 360, "")
    v = k.ornekle(np.array([89.5, -89.5, 0.5, 0.5, -90.0, 90.0]), np.array([-179.5, 179.5, 180.0, -180.0, 0.0, 0.0]))
    assert v.tolist() == [0.0, 179359.0, 89000.0, 89000.0, 179180.0, 180.0]


def test_cografi_kapsam_disi_nan():
    a = np.ones((10, 20), np.float32)
    k = K.Cografi("t", a, 0.0, 1.0, 70.0, 1.0, 10, 20, "")   # 60–70°K, 0–20°D, küresel değil
    v = k.ornekle(np.array([65.0, 75.0, 65.0, 59.9]), np.array([5.0, 5.0, 25.0, 5.0]))
    assert v[0] == 1 and np.isnan(v[1:]).all()


def test_alt_noktalar_s1_pencere_ile_ayni():
    phi0, lam0 = math.radians(45.0), math.radians(179.9)
    lat, lon = K._alt_noktalar([phi0], [lam0], R_D, 0, 1)
    p, l = Z.pencere(phi0, lam0, R_D)
    lp = np.degrees(l); lp = np.where(lp >= 180, lp - 360, lp)
    assert np.allclose(lat[0, :, :, 0, 0], np.degrees(p)) and np.allclose(lon[0, :, :, 0, 0], lp)


def test_alt_noktalar_hucre_icinde():
    phi0, lam0 = 0.0, 0.0
    s = 4
    lat, lon = K._alt_noktalar([phi0], [lam0], R_D, 0, s)
    x, y = Z.lambert_ileri(np.radians(lat[0]), np.radians(lon[0]), phi0, lam0, R_D)
    c = Z.hucre_merkezleri()
    # her alt nokta kendi hücresinin içinde (|x − x_i| < δ/2), alt noktaların ortalaması hücre merkezi
    assert np.all(np.abs(x - c[None, :, None, None]) < 0.25) and np.all(np.abs(y - c[:, None, None, None]) < 0.25)
    assert np.allclose(x.mean(axis=(2, 3)), c[None, :], atol=1e-9) and np.allclose(y.mean(axis=(2, 3)), c[:, None], atol=1e-9)


def _ince_katman(deger_fn, dx=0.001):
    n = int(round(2.0 / dx))
    lat_c = 1.0 - (np.arange(n) + 0.5) * dx
    lon_c = -1.0 + (np.arange(n) + 0.5) * dx
    return K.Cografi("ince", deger_fn(lat_c[:, None], lon_c[None, :]).astype(np.float32), -1.0, dx, 1.0, dx, n, n, "")


def test_ince_katman_ortalama():
    # 0,001° ≈ 111 m < 500 m → ortalama (coarse değil). Otomatik s, çok sık örneğe (s = 40: alan ağırlıklı
    # piksel ortalaması) piksel adımının (burada 1,0) en fazla 0,15'i kadar yakın olmalı.
    k = _ince_katman(lambda la, lo: 1000.0 * np.floor(lo / 0.001) * 0.001 + 0.0 * la)
    v, coarse, s = K.hucreye(k, [0.0], [0.0], R_D)
    assert not coarse[0] and s[0] == math.ceil(2 * 0.5 / (0.001 * math.pi * R_D / 180))
    ref, _, _ = K.hucreye(k, [0.0], [0.0], R_D, s=40)
    assert np.max(np.abs(v[0] - ref[0])) < 0.15, float(np.max(np.abs(v[0] - ref[0])))
    # doğrusal alanın alan ağırlıklı ortalaması hücre merkezindeki değere (piksel yarım adım kaymasıyla) eşit
    lat, lon = K._alt_noktalar([0.0], [0.0], R_D, 0, 1)
    # s = 40 → piksel başına ~9 örnek; kalan kuantalama ≤ adım/(2·9) ≈ 0,056
    assert np.max(np.abs(ref[0] - (1000.0 * lon[0, :, :, 0, 0] - 0.5))) < 0.06


def test_ince_katman_alan_agirligi():
    # sütun paritesi 0/1 (dama sütunları): hücre ortalaması ≈ 0,5
    k = _ince_katman(lambda la, lo: (np.floor((lo + 1.0) / 0.001) % 2) + 0.0 * la)
    v, coarse, s = K.hucreye(k, [0.0], [0.0], R_D, s=8)
    assert abs(float(np.mean(v)) - 0.5) < 0.02


def test_kaba_katman_coarse():
    a = (np.arange(3600)[:, None] * 10000 + np.arange(7200)[None, :]).astype(np.float64)
    k = K.Cografi("kaba", a, -180.0, 0.05, 90.0, 0.05, 3600, 7200, "")
    v, coarse, s = K.hucreye(k, [math.radians(30.0)], [math.radians(10.0)], R_D)
    assert coarse[0] and s[0] == 1
    lat, lon = K._alt_noktalar([math.radians(30.0)], [math.radians(10.0)], R_D, 0, 1)
    beklenen = np.floor((90 - lat[0, :, :, 0, 0]) / 0.05) * 10000 + np.floor((lon[0, :, :, 0, 0] + 180) / 0.05)
    assert np.array_equal(v[0].astype(np.float64), beklenen.astype(np.float32).astype(np.float64))


def test_hucreye_nan_kurali():
    k = _ince_katman(lambda la, lo: np.where(lo < 0, np.nan, 1.0) + 0.0 * la)
    v, _, _ = K.hucreye(k, [0.0], [0.0], R_D)
    lat, lon = K._alt_noktalar([0.0], [0.0], R_D, 0, 1)
    sol = lon[0, :, :, 0, 0] < -0.003
    sag = lon[0, :, :, 0, 0] > 0.003
    assert np.isnan(v[0][sol]).all() and (v[0][sag] == 1).all()


def test_hucreye_alt_ornekler():
    k = _ince_katman(lambda la, lo: 1.0 + 0.0 * la + 0.0 * lo)
    v, _, s = K.hucreye(k, [0.0], [0.0], R_D, alt=True)
    assert v.shape == (1, 40, 40, int(s[0]) ** 2) and (v == 1).all()


def test_genisletme():
    k = _ince_katman(lambda la, lo: 1.0 + 0.0 * la + 0.0 * lo)
    v, _, _ = K.hucreye(k, [0.0], [0.0], R_D, genisletme=2)
    assert v.shape == (1, 44, 44)


def test_hidrojen_izgara():
    lat_k = 90.0 - 0.5 * np.repeat(np.arange(360), 720)
    lon_b = np.tile(np.arange(720) * 0.5, 360)  # 0–360 doğu
    h = np.arange(259200, dtype=float)
    t = np.stack([lat_k - 0.5, lat_k, lon_b, np.mod(lon_b + 0.5, 360.0), h], 1)
    d = K.hidrojen_izgara(t)
    k = K.Cografi("h", d, -180.0, 0.5, 90.0, 0.5, 360, 720, "")
    # 0–0,5°D hücresi (tablo sırası 0) → enlem 89,75, boylam 0,25
    assert k.ornekle(np.array([89.75]), np.array([0.25]))[0] == 0
    assert k.ornekle(np.array([89.75]), np.array([-0.25]))[0] == 719  # 359,5–360
    with pytest.raises(AssertionError):
        K.hidrojen_izgara(np.concatenate([t, t[:1]]))


def _gcp_bant(lat_lo, lat_hi, fn):
    clat = np.arange(lat_lo + 0.25, lat_hi, 0.5)
    clon = np.arange(0.25, 360, 0.5)
    ltim = (np.arange(96) + 0.5) * 0.25
    L, O, T = np.meshgrid(clat, clon, ltim, indexing="ij")
    return L.ravel(), O.ravel(), T.ravel(), fn(L.ravel(), T.ravel())


def test_gcp_gece_ortalamasi():
    fn = lambda la, t: 100.0 + la * 0 + np.where((t >= 18) | (t < 6), 0.0, 50.0) + 0.001 * t
    bantlar = [_gcp_bant(70, 80, fn), _gcp_bant(80, 90, fn)]
    d, y0 = K.gcp_gece_izgara(bantlar, "n")
    ltim = (np.arange(96) + 0.5) * 0.25
    gece = (ltim >= 18) | (ltim < 6)
    assert y0 == 90.0 and d.shape == (40, 720)
    assert np.allclose(d, 100.0 + 0.001 * ltim[gece].mean())


def test_esalan():
    satirlar = []
    for lo in range(-90, 90, 2):
        m = max(1, int(round(180 * math.cos(math.radians(lo + 1)))))
        w = 360.0 / m
        for k in range(m):
            satirlar.append((lo, lo + 2, k * w, (k + 1) * w, lo * 1000 + k))
    t = np.array(satirlar, float)
    e = K.EsAlan("t", t[:, 0], t[:, 1], t[:, 2], t[:, 3], t[:, 4], "")
    assert e.ornekle(np.array([0.5]), np.array([0.1]))[0] == 0
    assert e.ornekle(np.array([-89.0]), np.array([-1.0]))[0] == -90000 + (len([r for r in satirlar if r[0] == -90]) - 1)


def test_ucgen_esik():
    g = np.random.default_rng(0)
    lat = np.linspace(80, 90, 200).repeat(200); lon = np.tile(np.linspace(-180, 180, 200, endpoint=False), 200)
    u = K.Ucgen("t", lat, lon, np.arange(lat.size), 1737.4, "")
    v = u.ornekle(np.array([lat[500], 0.0]), np.array([lon[500], 0.0]))
    assert v[0] == 500 and np.isnan(v[1])


def test_pgda_xy():
    R = 1737400.0
    x, y = K.pgda_xy(np.array([90.0, 89.0, -89.0, -89.0]), np.array([0.0, 0.0, 90.0, 0.0]), "n", R)
    rho1 = 2 * R * math.tan(math.radians(1.0) / 2)
    assert abs(x[0]) < 1e-6 and abs(y[0]) < 1e-6 and abs(x[1]) < 1e-6 and abs(y[1] - rho1) < 1e-6
    assert np.isnan(x[2:]).all()
    xs, ys = K.pgda_xy(np.array([-89.0]), np.array([90.0]), "s", R)
    assert abs(xs[0] - rho1) < 1e-6 and abs(ys[0]) < 1e-6


def test_seyrek_noktalar_dogrudan_indeks(monkeypatch):
    a = (np.arange(1000)[:, None] * 10000 + np.arange(2000)[None, :]).astype(np.float32)
    k = K.Cografi("t", a, -180.0, 0.18, 90.0, 0.18, 1000, 2000, "")
    monkeypatch.setattr(K, "BLOK_SINIRI_BAYT", 1000)  # blok sınırını zorla aş
    lat = np.array([89.95, -89.95, 0.05]); lon = np.array([-179.95, 179.95, 0.05])
    v = k.ornekle(lat, lon)
    r = np.floor((90 - lat) / 0.18); c = np.floor((lon + 180) / 0.18)
    assert np.array_equal(v, (r * 10000 + c).astype(np.float32))
'''
TEST_GERCEK = r'''# Developed with assistance from Claude (Anthropic).
"""katman.py gerçek temiz\\ verisiyle: açılış, bağımsız okuma (rasterio) ile aynılık, belge 8.3 veri testleri,
gerçek-yer kontrolleri (koordinatlar belgeden), vektör sınıfları."""
import math
import numpy as np
import pytest
import ayar as A
import izgara as Z
import katman as K

RASTER = ["etopo", "mcd12c1_00", "mcd12c1_15", "perm_kuzey", "perm_antarktika", "ai", "ai_bayrak", "kil", "silt",
          "lola", "ra", "tbol", "avgvisib_n", "avgvisib_s", "lpsr_n", "lpsr_s", "gcp_gece_n", "gcp_gece_s",
          "prp_temp_max", "prp_temp_avg", "prp_ice_depth_m", "prp_ice_depth_bayrak", "lpgrs_w_feo", "lpgrs_w_th",
          "hidrojen", "mola", "tes_plagioclase", "tes_low_ca_pyroxene", "tes_high_ca_pyroxene", "ti", "albedo_mars",
          "dci", "swim"]


@pytest.mark.parametrize("ad", RASTER)
def test_katman_acilir(ad):
    assert K.ac(ad) is not None


@pytest.mark.parametrize("kod,onek", [("E4", "yayinim_b10"), ("E4", "yayinim_b12"), ("E4", "yayinim_b13"),
                                      ("E4", "yayinim_b14"), ("E4", "ndvi"), ("E4", "ndvi_bayrak"),
                                      ("E5", "lst_gunduz"), ("E5", "lst_gece"), ("E6", "albedo_wsa")])
def test_aylik_katmanlar(kod, onek):
    for ad in K.aylik(kod, onek):
        assert K.ac(ad).tur == "cografi"


def _rastgele(g, n, lat0, lat1, lon0=-180.0, lon1=180.0):
    z = g.uniform(math.sin(math.radians(lat0)), math.sin(math.radians(lat1)), n)
    return np.degrees(np.arcsin(z)), g.uniform(lon0, lon1, n)


def _ayni(a, b):
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    assert np.array_equal(np.isnan(a), np.isnan(b)), f"NaN deseni farklı: {np.isnan(a).sum()} / {np.isnan(b).sum()}"
    assert np.array_equal(a[~np.isnan(a)], b[~np.isnan(b)])


@pytest.mark.parametrize("ad,lat0,lat1", [("etopo", -90, 90), ("ai", -60, 90), ("ra", -70, 70), ("tbol", -70, 70)])
def test_cografi_tif_rasterio_ile_ayni(ad, lat0, lat1):
    k = K.ac(ad)
    lat, lon = _rastgele(np.random.default_rng(5), 3000, lat0 + 1e-6, lat1 - 1e-6)
    biz = k.ornekle(lat, lon)
    onlar = np.array([v[0] for v in k.kaynak.sample(zip(lon, lat))])
    _ayni(biz, onlar)


@pytest.mark.parametrize("ad,lat0,lat1", [("perm_kuzey", 25, 90), ("perm_antarktika", -90, -55),
                                          ("kil", -56, 84), ("silt", -56, 84)])
def test_projeksiyon_rasterio_ile_ayni(ad, lat0, lat1):
    from pyproj import Transformer
    k = K.ac(ad)
    ds = k.kaynak
    lat, lon = _rastgele(np.random.default_rng(6), 4000, lat0, lat1)
    x, y = Transformer.from_crs("EPSG:4326", ds.crs.to_wkt(), always_xy=True).transform(lon, lat)
    x, y = np.asarray(x), np.asarray(y)
    b = ds.bounds
    ic = np.isfinite(x) & np.isfinite(y) & (x > b.left) & (x < b.right) & (y > b.bottom) & (y < b.top)
    assert ic.sum() > 1000
    biz = k.ornekle(lat[ic], lon[ic])
    onlar = np.array([v[0] for v in ds.sample(zip(x[ic], y[ic]))])
    _ayni(biz, onlar)


@pytest.mark.parametrize("ad,R,lat0,lat1", [("lola", 1737400.0, -90, 90), ("swim", 3396190.0, -60, 60)])
def test_metre_silindirik_rasterio_ile_ayni(ad, R, lat0, lat1):
    k = K.ac(ad)
    lat, lon = _rastgele(np.random.default_rng(7), 3000, lat0 + 1e-6, lat1 - 1e-6)
    biz = k.ornekle(lat, lon)
    m = math.pi * R / 180.0
    onlar = np.array([v[0] for v in k.kaynak.sample(zip(lon * m, lat * m))])
    _ayni(biz, onlar)


def test_mola_jezero():
    # belge 17.3 D2: Jezero merkezi (18,44, 77,45) yaklaşık −2570 m (PDS MEGDR çapraz ürün)
    v = float(K.ac("mola").ornekle(18.44, 77.45))
    assert abs(v + 2570) < 100, v


def test_pgda_anormal_piksel_nan():
    # belge 10.2: anormal piksel 88,435°K 106,602°D NaN
    for ad in ("lpsr_n", "avgvisib_n"):
        k = K.ac(ad)
        assert np.isnan(k.ornekle(88.435, 106.602)), ad
        assert np.isfinite(k.ornekle(88.435 + 0.05, 106.602)), ad


def test_pgda_en_soguk_ucgenler_guney():
    # D2 testinin katman.py ile tekrarı: |enlem| ≥ 85° güney en soğuk 100 PRP üçgeni (temp_max) → LPSR = 1 oranı ≥ 0,9
    kl = K._kl("ay", "M4")
    lat = np.load(kl / "prp_south_tri_clat.npy"); lon = np.load(kl / "prp_south_tri_clon.npy")
    t = np.load(kl / "prp_south_temp_max.npy")
    m = np.abs(lat) >= 85
    o = np.argsort(t[m])[:100]
    lp = K.ac("lpsr_s").ornekle(lat[m][o], lon[m][o])
    assert np.mean(lp == 1.0) >= 0.9, float(np.mean(lp == 1.0))


@pytest.mark.parametrize("kutup", ["n", "s"])
def test_gcp_ghrm_70_derece(kutup):
    # belge 8.3 "Ay Tgece birleştirme": 70° bandında GCP (gece yarısı) ile GHRM tbol farkı < 1 K
    kl = K._kl("ay", "M4")
    b = "70n80n" if kutup == "n" else "80s70s"
    clat, ltim, tb = (np.load(kl / f"gcp_{b}_{s}.npy") for s in ("clat", "ltim", "tbol"))
    m = (np.abs(clat) < 70.5) & ((ltim < 0.5) | (ltim >= 23.5)) & np.isfinite(tb)
    gcp = float(np.mean(tb[m]))
    ds = K.ac("tbol").kaynak
    from rasterio.windows import Window
    satir = Window(0, 0, ds.width, 64) if kutup == "n" else Window(0, ds.height - 64, ds.width, 64)
    ghrm = float(np.nanmean(ds.read(1, window=satir)))
    assert abs(gcp - ghrm) < 1.0, (gcp, ghrm)


def test_tes_ve_dci_veri_yok_kodu_kalmadi():
    # belge 8.3: TES b6 = −1 → null; DCI = 0,85 → null
    for ad in ("tes_plagioclase", "tes_low_ca_pyroxene", "tes_high_ca_pyroxene"):
        a = np.asarray(K.ac(ad).kaynak)
        assert not (a == -1).any(), ad
    assert not (np.asarray(K.ac("dci").kaynak) == np.float32(0.85)).any()


def test_gcp_gece_kapsami():
    for ad in ("gcp_gece_n", "gcp_gece_s"):
        d = K.ac(ad).kaynak
        assert np.isfinite(d).mean() > 0.99, (ad, float(np.isfinite(d).mean()))


@pytest.mark.parametrize("govde,lat,lon,katman", [("ay", -89.0, 30.0, "lola"),          # belge 9.1 M-SP
                                                  ("mars", 18.44, 77.45, "mola"),        # belge 9.2 R-JEZ
                                                  ("dunya", 35.58223, -111.63182, "etopo")])  # belge 9.3 SP Crater
def test_gercek_pencere_dem(govde, lat, lon, katman):
    r = Z.yaricap(govde)
    v, coarse, s = K.hucreye(K.ac(katman), [math.radians(lat)], [math.radians(lon)], r, genisletme=2)
    assert v.shape == (1, 44, 44) and np.isfinite(v).all() and not coarse[0] and s[0] >= 2


def test_vektor_sentetik():
    import shapely
    v = K.Vektor("t", [shapely.box(-1, -1, 0, 1), shapely.box(0, -1, 1, 1)], ["a", "b"], "EPSG:4326")
    assert v.sinif(np.array([0.5, 0.5, 5.0]), np.array([-0.5, 0.5, 5.0])).tolist() == [0, 1, -1]
    pay, gec = K.hucreye_sinif(v, [0.0], [0.0], 6371.0)
    lat, lon = K._alt_noktalar([0.0], [0.0], 6371.0, 0, 1)
    sol = lon[0, :, :, 0, 0] < -0.003
    sag = lon[0, :, :, 0, 0] > 0.003
    assert (pay[0][sol][:, 0] == 1).all() and (pay[0][sag][:, 1] == 1).all() and (gec[0] == 25).all()


@pytest.fixture(scope="module")
def glim():
    return K.ac("glim")


def test_glim_siniflari(glim):
    belge_6_3 = {"va", "vi", "vb", "py", "pb", "pa", "pi", "su", "ss", "sm", "sc", "ev", "mt", "ig", "wb", "nd"}
    assert set(glim.siniflar) <= belge_6_3, set(glim.siniflar) - belge_6_3


def test_glim_sp_crater(glim):
    pay, gec = K.hucreye_sinif(glim, [math.radians(35.58223)], [math.radians(-111.63182)], 6371.0)
    assert (gec[0] == 25).mean() > 0.9


def test_ay_ve_mars_jeoloji():
    ay = K.ac("ay_jeoloji")
    assert {"Im1", "Im2", "Em", "Imd", "Id", "EIp"} & set(ay.siniflar)
    mars = K.ac("sim3292")
    assert len(mars.siniflar) == 44
    assert (K.hucreye_sinif(mars, [math.radians(18.44)], [math.radians(77.45)], 3389.5)[1] == 25).all()
'''
(KOD / "katman.py").write_text(KATMAN_PY, encoding="utf-8")
(KOD / "testler" / "test_katman.py").write_text(TEST_KATMAN, encoding="utf-8")
(KOD / "testler" / "test_katman_gercek.py").write_text(TEST_GERCEK, encoding="utf-8")

# ayar.json: katman parametreleri (proje kararı / belge 4.4)
ayar_yolu = KOD / "ayar.json"
aj = json.loads(ayar_yolu.read_text(encoding="utf-8"))
aj["parametreler"]["katman"] = {
    "piksel_basina_ornek": {"deger": 2, "kaynak": "proje kararı (hücreden ince katmanda piksel kenarı başına en az 2 alt nokta; alan ağırlıklı ortalama)", "bolum": "4.4"},
    "alt_ornek_en_fazla": {"deger": 10, "kaynak": "proje kararı (kutba yakın coğrafi ızgarada üst sınır)", "bolum": "4.4"},
    "vektor_alt_ornek": {"deger": 5, "kaynak": "belge 4.4 (GLiM hücre başına 5 × 5 nokta; aynı kural Ay ve Mars jeolojisinde)", "bolum": "4.4"},
    "ucgen_esik_carpani": {"deger": 3.0, "kaynak": "proje kararı (PRP: en yakın üçgen merkezi ortanca komşu aralığının 3 katından uzaksa veri yok)", "bolum": "4.4"},
}
ayar_yolu.write_text(json.dumps(aj, ensure_ascii=False, indent=2), encoding="utf-8")

# FONKSIYONLAR.md
yol = KOD / "FONKSIYONLAR.md"
metin = yol.read_text(encoding="utf-8")
bas, son = "<!-- katman.py -->", "<!-- /katman.py -->"
blok = bas + "\n## katman.py\n" + "\n".join("- " + s for s in [
    "4.4 sürekli katman v_ij (ortalama / coarse) → `katman.hucreye(katman, phi0, lam0, r, genisletme)`",
    "4.4 kategorik katman v_ij,c (vektör, 5 × 5 nokta) → `katman.hucreye_sinif(vektor, phi0, lam0, r)`",
    "4.4 δv < δ kuralı → `katman.alt_ornek_sayisi`",
    "temiz\\ okuyucuları → `katman.ac(ad)`; aylık Dünya katmanları → `katman.aylik(kod, onek)`",
    "6.5 / v1.2 D5 Ay Tgece GCP 18:00–06:00 → `katman.gcp_gece_izgara`",
    "6.8 / 10.2 PGDA kutupsal dönüşüm → `katman.pgda_xy`"]) + "\n" + son
if bas in metin:
    metin = metin.split(bas)[0] + blok + metin.split(son)[1]
else:
    metin = metin.rstrip() + "\n\n" + blok + "\n"
yol.write_text(metin, encoding="utf-8")

deg = KAYIT / "degisiklik.md"
satirlar = [
    "- 2026-11-14 | Belge 4.4 hücre ortalaması: hücreden ince katmanda hücre içinde s × s alt nokta (piksel kenarı başına ≥ 2, s ≤ 10) örneklenip ortalanır (alan ağırlıklı piksel ortalaması) | neden: Lambert hücresi ile piksel ızgarası hizalı değil | etkisi: Implementation\n",
    "- 2026-11-14 | Vektör jeoloji (GLiM, Ay, Mars): her pencerede hücre başına 5 × 5 nokta, poligon içi testi (shapely, hazırlanmış poligon) | belge 4.4 aynen | etkisi: Implementation\n",
    "- 2026-11-14 | Diviner PRP hücreye: en yakın üçgen merkezi; ortanca komşu aralığının 3 katından uzaksa veri yok (proje kararı) | etkisi: Implementation\n",
]
d_eski = deg.read_text(encoding="utf-8")
yeni = [s for s in satirlar if s.split(" | ")[1][:30] not in d_eski]
if yeni:
    deg.write_text(d_eski + "".join(yeni), encoding="utf-8")

r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--durations=8", "testler"],
                   cwd=KOD, capture_output=True, text=True)
cikti = r.stdout + r.stderr
(KAYIT / "D4_test_katman.txt").write_text(cikti, encoding="utf-8")
print(cikti[-6000:])
durum = "PASS" if r.returncode == 0 else "FAIL"
with open(KAYIT / "14_kasim_log.txt", "a", encoding="utf-8") as f:
    f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}\tkatman.py+test_katman(+gercek)\t{durum}\n")
print(f"\ntestler: {durum}")
