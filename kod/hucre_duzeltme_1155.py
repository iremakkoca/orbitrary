# Developed with assistance from Claude (Anthropic).
# Düzeltme (11:55): PRP aramasına mesafe sınırı + Ay Tmax/T̄ yalnız |φ| ≥ 76° (belge 6.5 F₅); CMG test aralıkları veriden türetildi;
# test koşucusuna bekçi (10 dk çıktı yoksa durdurur). katman.py PGDA adı + 3 GB önbellek sınırı dahil. I⊕ teşhis sayımı. Sonra bütün testler.
import sys, json, datetime, importlib
from pathlib import Path
import numpy as np

KOK = Path.home() / "orbitrary"
KOD, KAYIT, ARA = KOK / "kod", KOK / "kayit", KOK / "ara"
(KOD / 'katman.py').write_text(r'''# Developed with assistance from Claude (Anthropic).
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
BLOK_SINIRI_BAYT = 768 * 1024 * 1024  # tek okumada en fazla bellek (proje kararı, 34 GB RAM)
TOPLAM_ONBELLEK_BAYT = 3 * 1024 ** 3  # bütün okuyucuların blok önbelleklerinin toplamı (proje kararı); aşılınca en eskiler boşaltılır
_BLOK_SIRASI = []  # (okuyucu kimliği, blok) en eskiden en yeniye


def _onbellek_kaydet(blok):
    """Toplam önbellek sınırı: yeni blok sona eklenir; toplam aşılırsa en eski blokların verisi bırakılır."""
    global _BLOK_SIRASI
    _BLOK_SIRASI = [b for b in _BLOK_SIRASI if b is not blok and b.veri is not None] + [blok]
    toplam = sum(b.veri.nbytes for b in _BLOK_SIRASI)
    while toplam > TOPLAM_ONBELLEK_BAYT and len(_BLOK_SIRASI) > 1:
        eski = _BLOK_SIRASI.pop(0)
        toplam -= eski.veri.nbytes
        eski.veri = None


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
            self._blok.veri = None  # eski bloğu önce bırak (iki blok aynı anda bellekte durmasın)
            self._blok.veri = self._dosyadan(r0n, r1n, c0n, c1n)
            self._blok.r0, self._blok.r1, self._blok.c0, self._blok.c1 = r0n, r1n, c0n, c1n
            _onbellek_kaydet(self._blok)
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
        """En yakın üçgen merkezi; eşikten uzak nokta NaN. Arama eşik uzaklığıyla sınırlı (distance_upper_bound):
        kapsam dışındaki noktalar ağaçta hemen elenir (kapsamdan uzak sorgular aksi halde çok yavaştır)."""
        lat = np.asarray(lat, float)
        lon = np.asarray(lon, float)
        sekil = np.broadcast(lat, lon).shape
        la, lo = np.broadcast_to(lat, sekil).ravel(), np.broadcast_to(lon, sekil).ravel()
        out = np.full(la.size, np.nan, np.float32)
        # kapsam ön elemesi: en düşük kapsam enleminden eşik kadar (derece) beride kalan nokta aranmaz
        pay_der = np.degrees(self.esik_km / self.r)
        aday = np.isfinite(la) & np.isfinite(lo) & (np.abs(la) >= self.kapsama_min_abs_enlem - pay_der)
        if aday.any():
            v = Z.birim_vektor(np.radians(la[aday]), np.radians(lo[aday]))
            kiris = 2 * np.sin(self.esik_km / self.r / 2)             # eşik büyük çember uzaklığının kirişi
            d, i = self.agac.query(v, k=1, distance_upper_bound=kiris * (1 + 1e-12))
            bulundu = np.isfinite(d)
            dk = np.full(d.shape, np.inf)
            dk[bulundu] = 2 * self.r * np.arcsin(np.clip(d[bulundu] / 2, 0, 1))
            ic = bulundu & (dk <= self.esik_km)
            sonuc = np.full(d.shape, np.nan, np.float32)
            sonuc[ic] = self.deger[i[ic]]
            out[aday] = sonuc
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


def _kapat():
    """Çıkışta açık rasterio dosyalarını kapat (yorumlayıcı kapanırken excepthook uyarısını önler)."""
    for k in list(_ONBELLEK.values()):
        ds = getattr(k, "kaynak", None)
        if hasattr(ds, "close"):
            try:
                ds.close()
            except Exception:
                pass


import atexit
atexit.register(_kapat)


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
        dosya = _kl("ay", "M7") / f"{ad[:-2]}_65{kutup}.tif"   # temiz\\ay\\M7_pgda: avgvisib_65n.tif, lpsr_65s.tif …
        assert dosya.is_file(), dosya
        ds = rasterio.open(dosya)
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
''', encoding='utf-8')
(KOD / 'ozellik_diger.py').write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 6.3–6.8: jeoloji (3), mineraloji (4), termal (5), su/buz (6), toz (7), aydınlanma (8).

Formüller (saf fonksiyonlar) → türetilmiş katmanlar (ornekle/cozunurluk_km; katman.hucreye ile hücreye) →
pencere temsilleri (sınıf payları, sıra dağılımlarının 1000 noktalı yüzdelik vektörleri) → d₃ … d₈.

Okuma kararları (14 Kasım; kayit\\degisiklik.md):
- Dünya Tmax = 12 aylık gündüz LST'nin en büyüğü; T̄ = aylık (gündüz + gece)/2'nin yıllık ortalaması;
  Tgece = aylık gece LST'nin yıllık ortalaması.
- I⊕ aylık; C₁ = 0 ya da ΔTg ≤ 0 olan ay ortalamaya girmez. δ⊙: ayın 15'i, düşük duyarlıklı güneş formülü
  (Astronomical Almanac), sin δ = sin ε sin λ.
- ASTER MI: her bandın 12 aylık ortalamasından.
- Ay aydınlanması: |φ| ≥ 65° PGDA, |φ| < 65° Berger; her biri kendi kapsamında sıralanır.
- Sıfır kuralı: kara hücresi = MCD12C1 kara payı ≥ 0,5. Ay π⁺: alt örneklerin ≥ yarısı pozitifse hücre pozitif.
"""
import datetime
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import ayar as A
import izgara as Z
import katman as K
import uzaklik as U

ARA = A.KLASOR["ara"]
GRUPLAR = ["volkanik", "bazik_plutonik", "asidik_ara_plutonik", "tortul", "metamorfik", "buz"]
IZINLI = set(GRUPLAR) | {"yayla_yarim", "hesap_disi"}


# =============================================================== 1. formüller
def gunes_boylami_ve_deklinasyon(tarih):
    """Düşük duyarlıklı güneş konumu (Astronomical Almanac): ekliptik boylam λ (derece) ve
    δ⊙ = asin(sin ε sin λ), ε = ayar cisim.eksen_egikligi_der['dunya'] (belge 6.8 biçimi)."""
    n = (datetime.datetime(tarih.year, tarih.month, tarih.day, 12) - datetime.datetime(2000, 1, 1, 12)).days
    L = 280.460 + 0.9856474 * n
    g = math.radians(357.528 + 0.9856003 * n)
    lam = (L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360.0
    eps = math.radians(float(A.ayar("cisim.eksen_egikligi_der")["dunya"]))
    return lam, math.asin(math.sin(eps) * math.sin(math.radians(lam)))


def _H0(phi, delta):
    """Gün doğumu saat açısı: cos H₀ = −tan φ tan δ; kutup gününde π, kutup gecesinde 0."""
    with np.errstate(invalid="ignore", divide="ignore"):
        c = -np.tan(phi) * np.tan(delta)
    return np.arccos(np.clip(c, -1.0, 1.0))


def C1(phi, delta):
    """Belge 6.5: C₁ = sin φ sin δ sin H₀ + H₀ cos φ cos δ (H₀ = π → π cos φ cos δ; H₀ = 0 → 0)."""
    phi, delta = np.asarray(phi, float), np.asarray(delta, float)
    H = _H0(phi, delta)
    return np.sin(phi) * np.sin(delta) * np.sin(H) + H * np.cos(phi) * np.cos(delta)


def I_arti_ay(c1, albedo, dTg):
    """Belge 6.5: I⊕ = C₁ (1 − α) / ΔTg; C₁ = 0 ya da ΔTg ≤ 0 → NaN (ortalamaya girmez)."""
    c1, albedo, dTg = (np.asarray(v, float) for v in (c1, albedo, dTg))
    with np.errstate(invalid="ignore", divide="ignore"):
        I = c1 * (1.0 - albedo) / dTg
    return np.where((c1 > 0) & (dTg > 0) & np.isfinite(albedo), I, np.nan)


def berger_gunluk(phi, delta):
    """Belge 6.8: Q̄_gün = (1/π)(H₀ sin φ sin δ + cos φ cos δ sin H₀)."""
    phi, delta = np.asarray(phi, float), np.asarray(delta, float)
    H = _H0(phi, delta)
    return (H * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(H)) / math.pi


def berger_yillik(phi, eps_der, n_adim=None):
    """Belge 6.8: f(φ) = (1/2π) ∫ Q̄_gün(φ, δ(L_s)) dL_s, sin δ = sin ε sin L_s; orta nokta kuralı."""
    n_adim = int(A.ayar("aydinlanma.Ls_adim")) if n_adim is None else int(n_adim)
    Ls = (np.arange(n_adim) + 0.5) * 2 * math.pi / n_adim
    d = np.arcsin(math.sin(math.radians(eps_der)) * np.sin(Ls))
    phi = np.atleast_1d(np.asarray(phi, float))
    return np.array([berger_gunluk(p, d).mean() for p in phi])


class BergerTablosu:
    """f(φ) tablosu (0,001° adım) ve doğrusal ara değer (ölçülen en büyük hata 1,2e-9, Ay ε = 1,54°; testte < 1e-8)."""

    def __init__(self, eps_der, adim_der=0.001):
        self.adim = adim_der
        self.lat = np.linspace(-90.0, 90.0, int(round(180 / adim_der)) + 1)
        n_adim = int(A.ayar("aydinlanma.Ls_adim"))
        Ls = (np.arange(n_adim) + 0.5) * 2 * math.pi / n_adim
        d = np.arcsin(math.sin(math.radians(eps_der)) * np.sin(Ls))
        phi = np.radians(self.lat)
        self.f = np.empty_like(phi)
        for k in range(0, phi.size, 2000):
            self.f[k:k + 2000] = berger_gunluk(phi[k:k + 2000, None], d[None, :]).mean(axis=1)

    def __call__(self, lat_der):
        return np.interp(np.asarray(lat_der, float), self.lat, self.f)


def mafik_indeks(e12, e13, e14):
    """Belge 6.4 (Ninomiya ve ark. [134]): MI = ε₁₂ ε₁₄³ / ε₁₃⁴."""
    e12, e13, e14 = (np.asarray(v, float) for v in (e12, e13, e14))
    with np.errstate(invalid="ignore", divide="ignore"):
        return e12 * e14 ** 3 / e13 ** 4


def mars_hcp(b3, b5, b6):
    """Belge 6.4 / v1.2 D11: x = b₆ / (b₃ + b₅ + b₆); paydada 0 ya da veri yok → NaN."""
    b3, b5, b6 = (np.asarray(v, float) for v in (b3, b5, b6))
    s = b3 + b5 + b6
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(s > 0, b6 / s, np.nan)


def sifir_kurali(perm, kar_buz, kara):
    """Belge 6.6 Dünya: kar/buz ≥ 0,5 → hesap dışı (NaN); haritada değer yok ve kara hücresi (kara ≥ 0,5) → 0;
    haritada değer yok ve kara değil → NaN; değer var → değer."""
    perm, kar_buz, kara = (np.asarray(v, float) for v in (perm, kar_buz, kara))
    kb_sinir = float(A.ayar("su_buz.kar_buz_siniri"))
    x = np.where(np.isfinite(perm), perm, np.where(kara >= 0.5, 0.0, np.nan))
    return np.where(np.isfinite(kar_buz) & (kar_buz >= kb_sinir), np.nan, x)


def pi_arti(pozitif, veri_var):
    """Belge 6.6: π⁺(T) = #{pozitif hücre} / #{verisi olan hücre}; veri yoksa NaN."""
    pozitif, veri_var = np.asarray(pozitif, bool), np.asarray(veri_var, bool)
    n = veri_var.sum(axis=(-2, -1))
    p = (pozitif & veri_var).sum(axis=(-2, -1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, p / np.maximum(n, 1), np.nan)


def islak_mi(pi):
    """Belge 6.6: π⁺ ≥ 0,5 → ıslak; NaN (kapsam dışı) → kuru."""
    pi = np.asarray(pi, float)
    return np.where(np.isfinite(pi), pi >= float(A.ayar("su_buz.islak_esigi")), False)


def gecerli_oran(x):
    """Pencerede değeri olan hücre oranı (son iki eksen)."""
    x = np.asarray(x, float)
    return np.isfinite(x).mean(axis=(-2, -1))


# =============================================================== 2. jeoloji sözlüğü
def sozluk_matrisi(govde, siniflar, yol=None):
    """kod\\jeoloji_sozluk.csv → (C, 6) ağırlık matrisi (birim → grup). Verideki her birim sözlükte ve grubu izinli
    olmalı; hesap_disi → 0 satırı; yayla_yarim → ayar jeoloji.mars_yayla."""
    yol = A.KLASOR["kod"] / "jeoloji_sozluk.csv" if yol is None else Path(yol)
    sz = pd.read_csv(yol, dtype=str, encoding="utf-8-sig").fillna("")
    sz = sz[sz["cisim"].str.strip().str.lower() == govde]
    harita = dict(zip(sz["birim_kodu"].str.strip(), sz["grup"].str.strip()))
    eksik = [s for s in siniflar if s not in harita]
    bos = [s for s in siniflar if s in harita and harita[s] == ""]
    yanlis = sorted({harita[s] for s in siniflar if s in harita and harita[s] not in IZINLI and harita[s] != ""})
    assert not eksik, f"jeoloji_sozluk.csv ({govde}): sözlükte olmayan birimler {eksik}"
    assert not bos, f"jeoloji_sozluk.csv ({govde}): grubu boş birimler ({len(bos)}): {bos}"
    assert not yanlis, f"jeoloji_sozluk.csv ({govde}): izinsiz grup değerleri {yanlis}; izinli: {sorted(IZINLI)}"
    yayla = A.ayar("jeoloji.mars_yayla")
    G = np.zeros((len(siniflar), len(GRUPLAR)))
    for i, s in enumerate(siniflar):
        g = harita[s]
        if g == "hesap_disi":
            continue
        if g == "yayla_yarim":
            for ad, w in yayla.items():
                G[i, GRUPLAR.index(ad)] = float(w)
        else:
            G[i, GRUPLAR.index(g)] = 1.0
    return G


def hucre_grup_paylari(pay, G, kar_buz=None):
    """Hücre sınıf payları pay (..., C) → grup payları (..., 6), hesap dışı noktalar düşer ve yeniden
    normalleşir. Dünya: kar/buz payı kb (MCD12C1 sınıf 15) 'buz' grubuna yazılır: (1 − kb)·q + kb·e_buz.
    Geçersiz hücre (veri yok, kb = 0 ya da yok) → NaN."""
    g = np.nan_to_num(np.asarray(pay, float)) @ G
    t = g.sum(axis=-1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        q = np.where(t > 0, g / np.maximum(t, 1e-300), np.nan)
    if kar_buz is not None:
        kb = np.clip(np.nan_to_num(np.asarray(kar_buz, float)), 0, 1)[..., None]
        e = np.zeros(len(GRUPLAR)); e[GRUPLAR.index("buz")] = 1.0
        q = np.where(np.isfinite(q), (1 - kb) * q + kb * e, np.where(kb > 0, e * np.ones_like(kb), np.nan))
    return q


def pencere_jeoloji(qh):
    """Belge 6.3: q_c(W) = W* hücrelerinin ortalaması; (..., n, n, 6) → (..., 6), geçerli hücre oranı."""
    qh = np.asarray(qh, float)
    gec = np.isfinite(qh).all(axis=-1)
    say = gec.sum(axis=(-2, -1))
    top = np.where(gec[..., None], qh, 0.0).sum(axis=(-3, -2))
    with np.errstate(invalid="ignore", divide="ignore"):
        q = np.where(say[..., None] > 0, top / np.maximum(say, 1)[..., None], np.nan)
    return q, gec.mean(axis=(-2, -1))


# =============================================================== 3. türetilmiş katmanlar
class Fonksiyon:
    """f(lat, lon) → değer; çözünürlük fonksiyonu (katman.hucreye için)."""

    tur = "fonksiyon"

    def __init__(self, ad, f, coz):
        self.ad, self.f, self.coz = ad, f, coz

    def ornekle(self, lat, lon):
        lat, lon = np.asarray(lat, float), np.asarray(lon, float)
        return np.asarray(self.f(lat, lon), np.float32)

    def cozunurluk_km(self, lat, r):
        return self.coz(lat, r)


def _kaba(lat, r):
    return 1e9, 1e9  # hücreden kaba → coarse (s = 1)


def _tarih(ad):
    s = ad.split("_")[-1]
    return datetime.date(int(s[:4]), 1, 1) + datetime.timedelta(days=int(s[4:]) - 1)


def dunya_cmg():
    """Dünya 0,05° CMG türetilmiş ızgaraları (bir kez hesaplanır, ara\\cmg_*.npy + .json):
    mi, tmax, tort, tgece, iarti. Girdiler temiz\\ E4, E5, E6 (aynı CMG ızgarası, assert)."""
    adlar = ["mi", "tmax", "tort", "tgece", "iarti"]
    yollar = {a: ARA / f"cmg_{a}.npy" for a in adlar}
    if all(p.exists() for p in yollar.values()):
        return yollar
    gt = [-180.0, 0.05, 0.0, 90.0, 0.0, -0.05]
    bilgi = {}

    def yukle(ad):
        k = K.ac(ad)
        assert k.tur == "cografi" and (k.x0, k.dx, k.y0, k.dy) == (-180.0, 0.05, 90.0, 0.05), ad
        return np.asarray(k.kaynak, dtype=np.float32)

    # MI: her bandın 12 aylık ortalaması
    e = {}
    for b in (12, 13, 14):
        st = np.stack([yukle(a) for a in K.aylik("E4", f"yayinim_b{b}")])
        with np.errstate(invalid="ignore"):
            e[b] = np.nanmean(st, axis=0)
        del st
    mi = mafik_indeks(e[12], e[13], e[14]).astype(np.float32)
    del e
    # LST
    gun = {_tarih(a).month: a for a in K.aylik("E5", "lst_gunduz")}
    gec = {_tarih(a).month: a for a in K.aylik("E5", "lst_gece")}
    alb = {_tarih(a).month: a for a in K.aylik("E6", "albedo_wsa")}
    assert sorted(gun) == sorted(gec) == sorted(alb) == list(range(1, 13))
    lat_c = 90.0 - (np.arange(3600) + 0.5) * 0.05
    tmax = np.full((3600, 7200), -np.inf, np.float32)
    top_ort = np.zeros((3600, 7200), np.float32); n_ort = np.zeros((3600, 7200), np.int16)
    top_gece = np.zeros((3600, 7200), np.float32); n_gece = np.zeros((3600, 7200), np.int16)
    top_i = np.zeros((3600, 7200), np.float64); n_i = np.zeros((3600, 7200), np.int16)
    for ay in range(1, 13):
        D, N, a = yukle(gun[ay]), yukle(gec[ay]), yukle(alb[ay])
        tmax = np.fmax(tmax, D)
        m = np.isfinite(D) & np.isfinite(N)
        top_ort += np.where(m, (D + N) / 2, 0); n_ort += m
        mg = np.isfinite(N)
        top_gece += np.where(mg, N, 0); n_gece += mg
        _, d = gunes_boylami_ve_deklinasyon(datetime.date(2023, ay, 15))
        c1 = C1(np.radians(lat_c), d)[:, None]
        I = I_arti_ay(c1, a, D - N)
        mi_ = np.isfinite(I)
        top_i += np.where(mi_, I, 0); n_i += mi_
        bilgi[f"ay_{ay:02d}"] = {"gunduz": gun[ay], "gece": gec[ay], "albedo": alb[ay],
                                 "deklinasyon_der": round(math.degrees(d), 4), "iarti_gecerli": int(mi_.sum())}
    with np.errstate(invalid="ignore", divide="ignore"):
        ciktilar = {"mi": mi,
                    "tmax": np.where(np.isfinite(tmax), tmax, np.nan).astype(np.float32),
                    "tort": np.where(n_ort > 0, top_ort / np.maximum(n_ort, 1), np.nan).astype(np.float32),
                    "tgece": np.where(n_gece > 0, top_gece / np.maximum(n_gece, 1), np.nan).astype(np.float32),
                    "iarti": np.where(n_i > 0, top_i / np.maximum(n_i, 1), np.nan).astype(np.float32)}
    for ad, v in ciktilar.items():
        np.save(yollar[ad], v)
        Path(yollar[ad]).with_suffix(".json").write_text(json.dumps({
            "geotransform": gt, "sekil": [3600, 7200], "birim": {"mi": "", "tmax": "K", "tort": "K", "tgece": "K", "iarti": "K⁻¹ (göreli)"}[ad],
            "gecerli": int(np.isfinite(v).sum()), "en_kucuk": float(np.nanmin(v)), "en_buyuk": float(np.nanmax(v)),
            "aylar": bilgi if ad == "iarti" else None, "uretim": datetime.datetime.now().isoformat(timespec="seconds")},
            ensure_ascii=False, indent=1), encoding="utf-8")
    return yollar


_OD = {}


def ac(ad):
    """Türetilmiş katmanlar (bu modül) + katman.ac."""
    if ad in _OD:
        return _OD[ad]
    k = _ac(ad)
    _OD[ad] = k
    return k


def _ac(ad):
    R = {g: float(A.ayar("cisim.yaricap_km")[g]) for g in ("dunya", "ay", "mars")}
    if ad.startswith("cmg_"):
        p = dunya_cmg()[ad[4:]]
        return K._npy_cografi(ad, p, 20)
    if ad == "perm_sifir":
        kn, ka, su, kb = K.ac("perm_kuzey"), K.ac("perm_antarktika"), K.ac("mcd12c1_00"), K.ac("mcd12c1_15")

        def f(lat, lon):
            p = np.where(lat >= 0, kn.ornekle(lat, lon), ka.ornekle(lat, lon))
            return sifir_kurali(p, kb.ornekle(lat, lon) / 100.0, 1.0 - su.ornekle(lat, lon) / 100.0)
        return Fonksiyon(ad, f, _kaba)
    if ad == "siltkil":
        kil, silt = K.ac("kil"), K.ac("silt")
        return Fonksiyon(ad, lambda lat, lon: (kil.ornekle(lat, lon) + silt.ornekle(lat, lon)) / 1000.0,
                         lambda lat, r: kil.cozunurluk_km(lat, r))
    if ad == "berger_dunya" or ad == "berger_mars" or ad == "berger_ay":
        g = ad.split("_")[1]
        t = BergerTablosu(float(A.ayar("cisim.eksen_egikligi_der")[g]))
        return Fonksiyon(ad, lambda lat, lon: t(lat) + 0.0 * lon, _kaba)
    if ad == "ay_tgece":  # belge 6.5 / v1.2 D5: |φ| ≥ 70° GCP gece ortalaması, < 70° GHRM tbol
        gn, gs, tb = K.ac("gcp_gece_n"), K.ac("gcp_gece_s"), K.ac("tbol")
        sinir = float(A.ayar("termal.ay_tgece_gcp_sinir_der"))

        def f(lat, lon):
            return np.where(lat >= sinir, gn.ornekle(lat, lon),
                            np.where(lat <= -sinir, gs.ornekle(lat, lon), tb.ornekle(lat, lon)))

        def coz(lat, r):
            return gn.cozunurluk_km(lat, r) if abs(lat) >= sinir else tb.cozunurluk_km(lat, r)
        return Fonksiyon(ad, f, coz)
    if ad == "hidrojen_th":  # belge 6.6: Th ≥ 4,56 ppm hücreler hesap dışı
        h, th = K.ac("hidrojen"), K.ac("lpgrs_w_th")
        esik = float(A.ayar("su_buz.ay_toryum_ppm"))
        return Fonksiyon(ad, lambda lat, lon: np.where(th.ornekle(lat, lon) >= esik, np.nan, h.ornekle(lat, lon)), _kaba)
    if ad == "pgda":  # iki kutup birlikte (|φ| ≥ 65°)
        n_, s_ = K.ac("avgvisib_n"), K.ac("avgvisib_s")
        sinir = float(A.ayar("aydinlanma.ay_pgda_sinir_der"))
        return Fonksiyon(ad, lambda lat, lon: np.where(lat >= sinir, n_.ornekle(lat, lon),
                                                       np.where(lat <= -sinir, s_.ornekle(lat, lon), np.nan)),
                         lambda lat, r: n_.cozunurluk_km(lat, r))
    if ad == "mars_hcp":
        b3, b5, b6 = (np.asarray(K.ac(f"tes_{b}").kaynak) for b in ("plagioclase", "low_ca_pyroxene", "high_ca_pyroxene"))
        k6 = K.ac("tes_high_ca_pyroxene")
        return K.Cografi(ad, mars_hcp(b3, b5, b6).astype(np.float32), k6.x0, k6.dx, k6.y0, k6.dy, k6.nrow, k6.ncol, "")
    return K.ac(ad)


# =============================================================== 4. sıra referansları (P_f,B)
OZELLIK = {  # (gövde, özellik) → (katman, bantlar, sıra türü)
    ("dunya", "mi"): ("cmg_mi", ((-90, 90),), "u"),
    ("dunya", "tmax"): ("cmg_tmax", ((-90, 90),), "u"),
    ("dunya", "tort"): ("cmg_tort", ((-90, 90),), "u"),
    ("dunya", "tgece"): ("cmg_tgece", ((-90, 90),), "u"),
    ("dunya", "iarti"): ("cmg_iarti", ((-90, 90),), "u"),
    ("dunya", "su"): ("perm_sifir", ((-90, 90),), "u+"),
    ("dunya", "toz"): ("siltkil", ((-90, 90),), "u"),
    ("dunya", "isik"): ("berger_dunya", ((-90, 90),), "u"),
    ("ay", "mi"): ("lpgrs_w_feo", ((-90, 90),), "u"),
    ("ay", "tmax"): ("prp_temp_max", ((-90, -75.9), (75.9, 90)), "u"),
    ("ay", "tort"): ("prp_temp_avg", ((-90, -75.9), (75.9, 90)), "u"),
    ("ay", "tgece"): ("ay_tgece", ((-90, 90),), "u"),
    ("ay", "su"): ("hidrojen_th", ((-90, 90),), "u+"),
    ("ay", "toz"): ("ra", ((-70, 70),), "ters"),
    ("ay", "isik_pgda"): ("pgda", ((-90, -65), (65, 90)), "u"),
    ("ay", "isik_berger"): ("berger_ay", ((-65, 65),), "u"),
    ("mars", "mi"): ("mars_hcp", ((-90, 90),), "u"),
    ("mars", "iarti"): ("ti", ((-90, 90),), "u"),
    ("mars", "su"): ("swim", ((-60, 60),), "u+"),
    ("mars", "toz"): ("dci", ((-90, 90),), "ters"),
    ("mars", "isik"): ("berger_mars", ((-90, 90),), "u"),
}
_SIRA = {}


def sira(govde, ozellik, n_en_fazla=None, onbellek=True):
    """P_f,B'den sıra fonksiyonu (Sira / SiraPozitif). Varsayılan: ≤ 10⁶ değer, ara\\ref_<gövde>_<özellik>.npy önbelleği."""
    anahtar = (govde, ozellik, n_en_fazla)
    if anahtar in _SIRA:
        return _SIRA[anahtar]
    kat, bant, tur = OZELLIK[(govde, ozellik)]
    yol = ARA / f"ref_{govde}_{ozellik}.npy"
    if onbellek and n_en_fazla is None and yol.exists():
        v = np.load(yol)
    else:
        v, bilgi = U.referans_orneklem(f"{govde}_{ozellik}", ac(kat).ornekle, bantlar=bant, n_en_fazla=n_en_fazla)
        if onbellek and n_en_fazla is None:
            np.save(yol, v)
            yol.with_suffix(".json").write_text(json.dumps(bilgi, ensure_ascii=False, indent=1), encoding="utf-8")
    s = U.SiraPozitif(v) if tur == "u+" else U.Sira(v)
    s.tur = tur
    _SIRA[anahtar] = s
    return s


def sirala(s, x):
    """Belge 5.2: u, u⁺ ya da ters (1 − u)."""
    return s.ters(x) if getattr(s, "tur", "u") == "ters" else s(x)


# =============================================================== 5. pencere temsilleri
def _hucre(ad, phi0, lam0, r, alt=False):
    v, coarse, s = K.hucreye(ac(ad), phi0, lam0, r, alt=alt)
    return v


def _Q(u):
    u = np.asarray(u, float)
    return U.yuzdelik(u.reshape(*u.shape[:-2], -1)).astype(np.float32)


def termal_ozellikleri(govde, lat0_der):
    """Belge 6.5 F₅ (hedefin cisminde de bulunanlar). Dünya referans tarafı dördünü de tutar."""
    if govde == "mars":
        return ["iarti"]
    if govde == "ay":
        return ["tmax", "tort", "tgece"] if abs(lat0_der) >= float(A.ayar("termal.ay_prp_sinir_der")) else ["tgece"]
    return ["tmax", "tort", "tgece", "iarti"]


def pencere_temsili(govde, phi0, lam0, kategoriler=(3, 4, 5, 6, 7, 8), n_ref=None):
    """Pencereler (radyan dizileri) için kategori 3–8 temsilleri:
    q3 (nw, 6), q3_gecerli; x4_gecerli (nw,), Q4 (nw, M); Q5[f] (nw, M); Q6 (nw, M); Q7; Q8;
    hedef bilgileri: pi_arti (Ay/Mars). n_ref: test için küçük referans (None = 10⁶, önbellekli)."""
    phi0 = np.atleast_1d(np.asarray(phi0, float))
    lam0 = np.atleast_1d(np.asarray(lam0, float))
    r = float(A.ayar("cisim.yaricap_km")[govde])
    T = {}
    if 3 in kategoriler:
        vek = ac({"dunya": "glim", "ay": "ay_jeoloji", "mars": "sim3292"}[govde])
        G = sozluk_matrisi(govde, list(vek.siniflar))
        pay, _ = K.hucreye_sinif(vek, phi0, lam0, r)
        kb = _hucre("mcd12c1_15", phi0, lam0, r) / 100.0 if govde == "dunya" else None
        T["q3"], T["q3_gecerli"] = pencere_jeoloji(hucre_grup_paylari(pay, G, kb))
    if 4 in kategoriler:
        x = _hucre({"dunya": "cmg_mi", "ay": "lpgrs_w_feo", "mars": "mars_hcp"}[govde], phi0, lam0, r)
        T["x4_gecerli"] = gecerli_oran(x)
        T["Q4"] = _Q(sirala(sira(govde, "mi", n_ref), x))
    if 5 in kategoriler:
        adlar = {"dunya": {"tmax": "cmg_tmax", "tort": "cmg_tort", "tgece": "cmg_tgece", "iarti": "cmg_iarti"},
                 "ay": {"tmax": "prp_temp_max", "tort": "prp_temp_avg", "tgece": "ay_tgece"},
                 "mars": {"iarti": "ti"}}[govde]
        # Belge 6.5 F₅: Ay'da Tmax ve T̄ (PRP) yalnız |φ₀| ≥ 76° pencerelerde; diğerlerinde null (hesaplanmaz)
        lat0 = np.degrees(phi0)
        for f, kat in adlar.items():
            gerek = np.array([f in termal_ozellikleri(govde, float(la)) for la in lat0])
            Q = np.full((len(phi0), U.M()), np.nan, np.float32)
            if gerek.any():
                Q[gerek] = _Q(sirala(sira(govde, f, n_ref), _hucre(kat, phi0[gerek], lam0[gerek], r)))
            T[f"Q5_{f}"] = Q
    if 6 in kategoriler:
        x = _hucre({"dunya": "perm_sifir", "ay": "hidrojen_th", "mars": "swim"}[govde], phi0, lam0, r)
        T["Q6"] = _Q(sirala(sira(govde, "su", n_ref), x))
        if govde == "mars":
            T["pi_arti"] = pi_arti(x > 0, np.isfinite(x))
        elif govde == "ay":
            b = _hucre("prp_ice_depth_bayrak", phi0, lam0, r, alt=True)  # (nw, n, n, s²)
            veri = np.isfinite(b)
            poz = veri & (b != 1)
            nv = veri.sum(-1)
            with np.errstate(invalid="ignore", divide="ignore"):
                oran = np.where(nv > 0, poz.sum(-1) / np.maximum(nv, 1), np.nan)
            T["pi_arti"] = pi_arti(np.nan_to_num(oran) >= 0.5, nv > 0)
    if 7 in kategoriler:
        x = _hucre({"dunya": "siltkil", "ay": "ra", "mars": "dci"}[govde], phi0, lam0, r)
        T["Q7"] = _Q(sirala(sira(govde, "toz", n_ref), x))
    if 8 in kategoriler:
        if govde == "ay":
            sinir = float(A.ayar("aydinlanma.ay_pgda_sinir_der"))
            lat, _ = K._alt_noktalar(phi0, lam0, r, 0, 1)
            lat = lat[..., 0, 0]
            up = sirala(sira("ay", "isik_pgda", n_ref), _hucre("pgda", phi0, lam0, r))
            ub = sirala(sira("ay", "isik_berger", n_ref), _hucre("berger_ay", phi0, lam0, r))
            u = np.where(np.abs(lat) >= sinir, up, ub)
        else:
            u = sirala(sira(govde, "isik", n_ref), _hucre(f"berger_{govde}", phi0, lam0, r))
        T["Q8"] = _Q(u)
    return T


# =============================================================== 6. uzaklıklar d₃ … d₈
def d3(qA, qT):
    """Belge 6.3: d₃ = TV(q(A), q(T))."""
    return U.tv(qA, qT)


def d4(QA, gecA, QT, gecT):
    """Belge 6.4: W₁(u[A], u[T]); pencerede değerli hücre oranı < %50 (iki taraftan biri) → null."""
    esik = float(A.ayar("mineraloji.gecerlilik_orani"))
    d = U.w1(QA, QT)
    return np.where((np.asarray(gecA) >= esik) & (float(gecT) >= esik), d, np.nan)


def d5(QA_dict, QT_dict, F5):
    """Belge 6.5: (1/|F₅|) Σ_f W₁; bir F₅ özelliği adayda yoksa null."""
    w = np.stack([U.w1(QA_dict[f], QT_dict[f]) for f in F5], axis=0)
    return np.mean(w, axis=0)  # NaN yayılır → null


def d_dagilim(QA, QT):
    """Belge 6.6–6.8: d = W₁ (u ya da u⁺ dağılımları); değer yoksa null (NaN)."""
    return U.w1(QA, QT)
''', encoding='utf-8')
(KOD / 'test_kos.py').write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Testleri canlı çıktıyla koşturur: her satır hem ekrana hem kayit\\<ad>.txt'ye anında yazılır
(defter bağlantısı kopsa bile ilerleme dosyada kalır). Kullanım: calistir("D4_test_x", "testler")."""
import datetime
import subprocess
import sys
import time
from pathlib import Path

KOK = Path.home() / "orbitrary"
KOD, KAYIT = KOK / "kod", KOK / "kayit"


def calistir(kayit_adi, hedef="testler", ek=(), bekci_dk=10):
    """bekci_dk dakika boyunca tek satır çıktı gelmezse süreci durdurur ve son test adını yazar."""
    import queue
    import threading
    t0 = time.time()
    yol = KAYIT / f"{kayit_adi}.txt"
    hedefler = [hedef] if isinstance(hedef, str) else list(hedef)
    komut = [sys.executable, "-u", "-m", "pytest", "-v", "-p", "no:cacheprovider", "-rf", "--durations=10", "--color=no",
             *hedefler, *ek]
    zaman_asimi = False
    with open(yol, "w", encoding="utf-8") as f:
        p = subprocess.Popen(komut, cwd=KOD, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace", bufsize=1)
        kuyruk = queue.Queue()
        threading.Thread(target=lambda: [kuyruk.put(s) for s in p.stdout] + [kuyruk.put(None)], daemon=True).start()
        son = ""
        while True:
            try:
                satir = kuyruk.get(timeout=bekci_dk * 60)
            except queue.Empty:
                zaman_asimi = True
                mesaj = f"\n!!! BEKÇİ: {bekci_dk} dakikadır çıktı yok, süreç durduruldu. Son biten: {son.strip()} — takılan test bundan SONRAKİ\n"
                f.write(mesaj); f.flush(); print(mesaj, flush=True)
                p.kill()
                break
            if satir is None:
                break
            son = satir
            f.write(satir)
            f.flush()
            print(satir, end="", flush=True)
        kod = p.wait()
    durum = "ZAMAN_ASIMI" if zaman_asimi else ("PASS" if kod == 0 else "FAIL")
    sure = time.time() - t0
    with open(KAYIT / "14_kasim_log.txt", "a", encoding="utf-8") as g:
        g.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}\t{kayit_adi}\t{durum}\t{sure:.0f} s\n")
    print(f"\ntestler: {durum}  ({sure:.0f} s) → kayit\\{kayit_adi}.txt", flush=True)
    return kod
''', encoding='utf-8')
(KOD / 'testler/test_katman.py').write_text(r'''# Developed with assistance from Claude (Anthropic).
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


def test_toplam_onbellek_siniri(monkeypatch):
    monkeypatch.setattr(K, "_BLOK_SIRASI", [])
    kat = [K.Cografi(f"t{i}", np.full((180, 360), i, np.float32), -180.0, 1.0, 90.0, 1.0, 180, 360, "") for i in range(5)]
    blok = 33 * 360 * 4                                                 # 1 satır + 16 satır dolgu her yanda
    monkeypatch.setattr(K, "TOPLAM_ONBELLEK_BAYT", 3 * blok + 100)    # üç blok sığar
    for k in kat:
        assert k.ornekle(np.array([0.5]), np.array([0.5]))[0] == float(k.ad[1:])
    dolu = [k for k in kat if k._blok.veri is not None]
    assert len(dolu) == 3 and dolu == kat[2:]                          # en eski ikisi boşaltıldı
    assert kat[0].ornekle(np.array([0.5]), np.array([0.5]))[0] == 0.0   # boşaltılan yeniden okunur


def test_ucgen_kapsamdan_uzak_sorgu_hizli():
    # Kapsamdan uzak noktalar (ör. Apollo 15 için PRP) eşik sınırlı aramayla hızlı elenir; sonuç NaN
    import time
    g = np.random.default_rng(1)
    n = 400000
    z = g.uniform(np.sin(np.radians(76)), 1, n)
    lat = np.concatenate([np.degrees(np.arcsin(z)), -np.degrees(np.arcsin(z))])
    lon = np.concatenate([g.uniform(-180, 180, n)] * 2)
    u = K.Ucgen("t", lat, lon, np.arange(lat.size, dtype=float), 1737.4, "")
    qlat = 26.0 + g.uniform(-0.2, 0.2, 130000); qlon = 3.6 + g.uniform(-0.2, 0.2, 130000)
    t0 = time.time()
    v = u.ornekle(qlat, qlon)
    assert np.isnan(v).all() and time.time() - t0 < 5.0
    # kapsam kenarına yakın (76° berisinde, eşik içinde) nokta yine bulunur
    v2 = u.ornekle(np.array([lat[0]]), np.array([lon[0]]))
    assert v2[0] == 0
''', encoding='utf-8')
(KOD / 'testler/test_ozellik_diger_gercek.py').write_text(r'''# Developed with assistance from Claude (Anthropic).
"""ozellik_diger gerçek temiz\\ verisiyle: CMG türetilmiş ızgaralar, türetilmiş katmanlar, birim kontrolleri,
referanslar (küçük örnek), gerçek pencere temsilleri. Mars jeoloji sözlüğü Sude doldurana kadar bilerek FAIL verir."""
import math
import json
import numpy as np
import pytest
import ayar as A
import katman as K
import ozellik_diger as O
import uzaklik as U


def test_dunya_cmg_turetilmis():
    yol = O.dunya_cmg()
    # Aralıklar verinin kendi sınırlarından türetilir (14 Kasım; ilk sürümdeki elle konmuş MI ve I⊕ sınırları yanlıştı):
    # MI = ε₁₂ε₁₄³/ε₁₃⁴, ε ∈ [0,604; 1] (D2'de ölçülen) → [0,604⁴; 1/0,604⁴] = [0,133; 7,5]
    # I⊕ = C₁(1 − α)/ΔTg, C₁ ≤ π, ΔTg ≥ 0,02 K (LST ölçeği) → (0; π/0,02 ≈ 157]
    # LST: geçerli aralık 7500–65535 × 0,02 K = 150–1310,7 K (dosya valid_range)
    aralik = {"tmax": (150, 1310.7), "tort": (150, 1310.7), "tgece": (150, 1310.7),
              "mi": (0.604 ** 4, 1 / 0.604 ** 4), "iarti": (0, math.pi / 0.02)}
    for ad, (lo, hi) in aralik.items():
        j = json.loads(yol[ad].with_suffix(".json").read_text(encoding="utf-8"))
        assert j["gecerli"] > 1_000_000, (ad, j["gecerli"])
        assert lo <= j["en_kucuk"] and j["en_buyuk"] <= hi, (ad, j["en_kucuk"], j["en_buyuk"])
    t = json.loads(yol["iarti"].with_suffix(".json").read_text(encoding="utf-8"))["aylar"]
    d = [t[f"ay_{m:02d}"]["deklinasyon_der"] for m in range(1, 13)]
    assert max(d) > 23 and min(d) < -23  # haziran/aralık


@pytest.mark.parametrize("ad", ["cmg_mi", "cmg_tmax", "cmg_tort", "cmg_tgece", "cmg_iarti", "perm_sifir", "siltkil",
                                "berger_dunya", "berger_ay", "berger_mars", "ay_tgece", "hidrojen_th", "pgda", "mars_hcp"])
def test_turetilmis_katman_acilir(ad):
    k = O.ac(ad)
    v = k.ornekle(np.array([-85.0, 0.0, 45.0, 85.0]), np.array([30.0, 10.0, -100.0, 100.0]))
    assert v.shape == (4,)


def test_toryum_birim_ve_esik():
    # belge 6.6: Th ≥ 4,56 ppm = Ay'ın en yüksek toryumlu %10'u → alanca düzgün örnekte pay ≈ 0,10
    th = K.ac("lpgrs_w_th")
    lat, lon = U.kure_noktalari(np.random.default_rng(11), 200000)
    v = th.ornekle(lat, lon)
    assert np.nanmin(v) >= -1 and np.nanmax(v) < 30, (np.nanmin(v), np.nanmax(v))
    pay = float(np.mean(v >= A.ayar("su_buz.ay_toryum_ppm")))
    assert 0.08 <= pay <= 0.12, pay


def test_sifir_kurali_gercek():
    p = O.ac("perm_sifir")
    lat, lon = U.kure_noktalari(np.random.default_rng(12), 200000, -30, 30)
    v = p.ornekle(lat, lon)
    kara = np.isfinite(v)
    assert kara.mean() > 0.15 and np.mean(v[kara] == 0) > 0.99  # tropik karada permafrost yok → 0


@pytest.mark.parametrize("govde,oz", sorted(O.OZELLIK))
def test_referans_kucuk(govde, oz):
    s = O.sira(govde, oz, n_en_fazla=20000, onbellek=False)
    assert s.n > 1000, s.n
    if O.OZELLIK[(govde, oz)][2] == "u+":
        assert 0 <= s.sifir_orani < 1


@pytest.mark.parametrize("govde,lat,lon,kat", [("dunya", 35.58223, -111.63182, (3, 4, 5, 6, 7, 8)),   # 9.3 SP Crater
                                               ("ay", -85.399, 31.180, (3, 4, 5, 6, 7, 8)),         # B5 A3-05
                                               ("ay", 26.13239, 3.63330, (3, 4, 5, 6, 7, 8)),       # 9.1 M-A15
                                               ("mars", 18.44, 77.45, (4, 5, 6, 7, 8))])            # 9.2 R-JEZ
def test_gercek_pencere_temsili(govde, lat, lon, kat):
    T = O.pencere_temsili(govde, [math.radians(lat)], [math.radians(lon)], kategoriler=kat, n_ref=20000)
    if 3 in kat:
        assert abs(np.nansum(T["q3"][0]) - 1) < 1e-6 and T["q3_gecerli"][0] > 0.5
    # Q6: Ay'da toryum maskesi (Th ≥ 4,56 ppm) bütün pencereyi düşürebilir (ör. Imbrium çevresi); orada yalnız
    # "ya tamamen sonlu ya tamamen null" kontrol edilir.
    beklenen = {"Q4": True, "Q8": True, "Q7": not (govde == "ay" and abs(lat) > 70),
                "Q6": True if govde != "ay" else None}
    for k, sonlu in beklenen.items():
        hepsi, hic = np.isfinite(T[k]).all(), (~np.isfinite(T[k])).all()
        assert hepsi or hic, (k, "kısmi null")
        if sonlu is not None:
            assert hepsi == sonlu, (k, govde, lat)
    for f in O.termal_ozellikleri(govde, lat):
        assert np.isfinite(T[f"Q5_{f}"]).all(), f
    if govde != "dunya":
        assert "pi_arti" in T


def test_mars_jeoloji_sozlugu_tam():
    # Sude jeoloji_sozluk.csv'de Mars'ın 44 biriminin grubunu doldurunca geçer (belge 6.3, 15.1)
    G = O.sozluk_matrisi("mars", list(O.ac("sim3292").siniflar))
    assert G.shape == (44, 6)
    T = O.pencere_temsili("mars", [math.radians(18.44)], [math.radians(77.45)], kategoriler=(3,), n_ref=20000)
    assert abs(np.nansum(T["q3"][0]) - 1) < 1e-6
''', encoding='utf-8')

with open(KAYIT / "degisiklik.md", "a", encoding="utf-8") as f:
    f.write("- 2026-11-14 | katman.Ucgen: arama eşik uzaklığıyla sınırlandı (distance_upper_bound) + kapsam ön elemesi | neden: Apollo 15 penceresinde PRP en yakın üçgen araması pratikte bitmiyordu (11:41 koşusu takıldı) | etkisi: yok (sonuç aynı, NaN)\n")
    f.write("- 2026-11-14 | ozellik_diger: Ay Tmax ve T̄ yalnız |φ₀| ≥ 76° pencerelerde hesaplanır (belge 6.5 F₅ kuralı) | etkisi: yok (zaten kullanılmıyordu)\n")
    f.write("- 2026-11-14 | CMG testi aralıkları veriden türetildi: MI [0,604⁴; 1/0,604⁴], I⊕ (0; π/0,02], LST [150; 1310,7] K | ilk sürümdeki elle konmuş MI (0,5–2) ve I⊕ (0–10) sınırları yanlıştı | etkisi: yok (test)\n")

# I⊕ teşhisi (KAYNAK YOK — ekip kararı için sayı): ΔTg < 1 K olan geçerli ayı bulunan piksel sayısı
if str(KOD) not in sys.path: sys.path.insert(0, str(KOD))
import katman as K, ozellik_diger as O
importlib.reload(K); importlib.reload(O)
gun = {O._tarih(a).month: a for a in K.aylik("E5", "lst_gunduz")}
gec = {O._tarih(a).month: a for a in K.aylik("E5", "lst_gece")}
lat_c = 90.0 - (np.arange(3600) + 0.5) * 0.05
kucuk = np.zeros((3600, 7200), bool); gecerli = np.zeros((3600, 7200), bool)
for ay in range(1, 13):
    D = np.asarray(K.ac(gun[ay]).kaynak, np.float32); N = np.asarray(K.ac(gec[ay]).kaynak, np.float32)
    _, d = O.gunes_boylami_ve_deklinasyon(datetime.date(2023, ay, 15))
    c1 = O.C1(np.radians(lat_c), d)[:, None]
    dT = D - N
    g = (c1 > 0) & (dT > 0)
    gecerli |= g; kucuk |= g & (dT < 1.0)
I = np.load(ARA / "cmg_iarti.npy")
bilgi = {"iarti_gecerli_piksel": int(np.isfinite(I).sum()), "dTg_1K_alti_ayi_olan_piksel": int(kucuk.sum()),
         "oran": round(float(kucuk.sum() / max(gecerli.sum(), 1)), 4),
         "iarti_yuzdelikler": {q: round(float(np.nanpercentile(I, q)), 4) for q in (1, 50, 99, 99.9)}}
(KAYIT / "iarti_teshis.json").write_text(json.dumps(bilgi, ensure_ascii=False, indent=1), encoding="utf-8")
print("I⊕ teşhis:", bilgi, flush=True)

import test_kos; importlib.reload(test_kos)
test_kos.calistir("D4_test_ozellik_diger_3", "testler")
