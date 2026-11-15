# Developed with assistance from Claude (Anthropic).
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
