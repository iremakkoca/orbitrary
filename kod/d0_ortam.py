# Developed with assistance from Claude (Anthropic).
# D0 ortam testi — Orbitrary v1.2 belge Bölüm 17.1 madde 4.
# Ne yapar: paket sürümleri, GDAL sürücüleri (HDF4, HDF5, netCDF, GTiff, GPKG,
# ESRI Shapefile, OpenFileGDB), küçük yaz/oku denemeleri, GUDHI CubicalComplex
# (cevabı bilinen örnek), earthaccess login(strategy="netrc") ve bir CMR araması.
# Çıktı: kayit\ortam.json. Bir test geçmezse silinmez; FAIL olarak yazılır.
import sys, os, json, platform, shutil, subprocess, ctypes
from pathlib import Path
from datetime import datetime
from importlib.metadata import version, PackageNotFoundError
import numpy as np

KOK = Path.home() / "orbitrary"
KAYIT = KOK / "kayit"
GECICI = KOK / "ara" / "d0_gecici"
shutil.rmtree(GECICI, ignore_errors=True)
GECICI.mkdir(parents=True)

sonuc = {"adim": "D0", "tarih": datetime.now().isoformat(timespec="seconds"), "testler": {}}
T = sonuc["testler"]

def kaydet(ad, gecti, detay=""):
    T[ad] = {"durum": "PASS" if gecti else "FAIL", "detay": str(detay)}
    print(("[PASS] " if gecti else "[FAIL] ") + ad + ": " + str(detay))

def dene(ad, fonk):
    # Test hata verirse FAIL olarak kaydedilir, diğer testler devam eder
    try:
        gecti, detay = fonk()
        kaydet(ad, gecti, detay)
    except Exception as e:
        kaydet(ad, False, type(e).__name__ + ": " + str(e))

# ---------- 0) Doğru ortam ----------
exe = Path(sys.executable)
kaydet("ortam_python", ("envs" in exe.parts and "orbitrary" in exe.parts and sys.version_info[:2] == (3, 12)),
       str(exe) + " | Python " + sys.version.split()[0])

# ---------- 1) Makine bilgisi (makale Implementation, t11_sure için) ----------
def ram_gb():
    try:
        class M(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = M(); m.dwLength = ctypes.sizeof(M)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return round(m.ullTotalPhys / 1e9, 1)
    except Exception:
        return None

conda_surum = None
if os.environ.get("CONDA_EXE"):
    try:
        conda_surum = subprocess.run([os.environ["CONDA_EXE"], "--version"], capture_output=True,
                                     text=True, timeout=60).stdout.strip()
    except Exception:
        pass
disk = shutil.disk_usage(KOK)
sonuc["makine"] = {"platform": platform.platform(), "islemci": platform.processor(),
                   "cekirdek": os.cpu_count(), "ram_gb": ram_gb(),
                   "disk_bos_gb": round(disk.free / 1e9, 1), "conda": conda_surum,
                   "python": sys.version, "python_yolu": str(exe)}
print("Makine:", sonuc["makine"])

# ---------- 2) Paket sürümleri ----------
# pip/metadata adı -> içe aktarma adı (metadata yoksa modülün __version__'ı okunur)
paketler = {"numpy": "numpy", "scipy": "scipy", "pandas": "pandas", "pyarrow": "pyarrow",
            "GDAL": "osgeo.gdal", "rasterio": "rasterio", "pyproj": "pyproj", "geopandas": "geopandas",
            "pyogrio": "pyogrio", "shapely": "shapely", "xarray": "xarray", "netCDF4": "netCDF4",
            "h5py": "h5py", "earthaccess": "earthaccess", "gudhi": "gudhi", "matplotlib": "matplotlib",
            "jupyterlab": "jupyterlab", "pytest": "pytest", "tqdm": "tqdm", "inflate64": "inflate64"}
surumler = {}
for ad, modul in paketler.items():
    try:
        surumler[ad] = version(ad)
    except PackageNotFoundError:
        try:
            m = __import__(modul, fromlist=["x"])
            surumler[ad] = getattr(m, "__version__", "bilinmiyor")
        except Exception as e:
            surumler[ad] = None
    # Paket gerçekten içe aktarılabiliyor mu
    try:
        __import__(modul, fromlist=["x"])
        aktarildi = True
    except Exception as e:
        aktarildi = False
    kaydet("paket_" + ad, surumler[ad] is not None and aktarildi, surumler[ad])
sonuc["paket_surumleri"] = surumler

# Conda paketleri (GDAL eklentileri pip'te görünmez; conda-meta'dan okunur)
meta = {}
for f in (Path(sys.prefix) / "conda-meta").glob("*.json"):
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        meta[d["name"]] = d["version"]
    except Exception:
        pass
conda_p = {a: meta.get(a) for a in ["python", "gdal", "libgdal-core", "libgdal-hdf4", "libgdal-hdf5", "libgdal-netcdf"]}
sonuc["conda_paketleri"] = conda_p
for a in ["libgdal-hdf4", "libgdal-hdf5", "libgdal-netcdf"]:
    kaydet("conda_" + a, conda_p[a] is not None, conda_p[a])

# ---------- 3) GDAL: tek sürüm ve sürücüler ----------
from osgeo import gdal
gdal.UseExceptions()
import rasterio, pyogrio

def tek_gdal():
    gv = gdal.__version__
    rv = rasterio.__gdal_version__
    pv = pyogrio.__gdal_version_string__
    kisa = lambda s: ".".join(str(s).split(".")[:3])
    return kisa(gv) == kisa(rv) == kisa(pv), "osgeo " + gv + " | rasterio " + rv + " | pyogrio " + pv
dene("gdal_tek_surum", tek_gdal)
sonuc["gdal_driver_path"] = os.environ.get("GDAL_DRIVER_PATH")

suruculer = ["HDF4", "HDF4Image", "HDF5", "HDF5Image", "netCDF", "GTiff", "GPKG", "ESRI Shapefile", "OpenFileGDB"]
for d in suruculer:
    drv = gdal.GetDriverByName(d)
    kaydet("surucu_" + d, drv is not None, drv.LongName if drv is not None else "yok")

ogr_list = pyogrio.list_drivers()
for d in ["GPKG", "ESRI Shapefile", "OpenFileGDB"]:
    kaydet("pyogrio_surucu_" + d, d in ogr_list, ogr_list.get(d, "yok"))

# ---------- 4) Küçük yaz/oku denemeleri ----------
from rasterio.transform import from_origin

def t_gtiff():
    a = np.arange(16, dtype="float32").reshape(4, 4); a[0, 0] = np.nan
    p = GECICI / "t.tif"
    with rasterio.open(p, "w", driver="GTiff", height=4, width=4, count=1, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(0, 4, 1, 1), nodata=np.nan) as ds:
        ds.write(a, 1)
    with rasterio.open(p) as ds:
        b = ds.read(1)
    return np.array_equal(a, b, equal_nan=True), "4x4 float32, NaN veri-yok geri okundu"
dene("yazoku_GTiff", t_gtiff)

def t_bigtiff():
    # LOLA ve PGDA dosyaları BigTIFF (rapor M1, M7: ilk baytlar 49 49 2B 00)
    a = np.arange(16, dtype="int16").reshape(4, 4)
    p = GECICI / "t_big.tif"
    with rasterio.open(p, "w", driver="GTiff", height=4, width=4, count=1, dtype="int16",
                       crs="EPSG:4326", transform=from_origin(0, 4, 1, 1), BIGTIFF="YES") as ds:
        ds.write(a, 1)
    bas = p.read_bytes()[:4]
    with rasterio.open(p) as ds:
        b = ds.read(1)
    return bas == bytes([0x49, 0x49, 0x2B, 0x00]) and np.array_equal(a, b), "ilk baytlar " + bas.hex(" ")
dene("yazoku_BigTIFF", t_bigtiff)

import geopandas as gpd
from shapely.geometry import box

def vektor_testi(surucu, uzanti):
    def f():
        g = gpd.GeoDataFrame({"birim": ["a"]}, geometry=[box(0, 0, 2, 1)], crs="EPSG:4326")
        p = GECICI / ("t" + uzanti)
        g.to_file(p, driver=surucu, engine="pyogrio")
        g2 = gpd.read_file(p, engine="pyogrio")
        ok = len(g2) == 1 and g2["birim"].iloc[0] == "a" and abs(g2.geometry.iloc[0].area - 2.0) < 1e-12
        return ok, "1 poligon yazıldı/okundu, alan " + str(g2.geometry.iloc[0].area)
    return f
dene("yazoku_GPKG", vektor_testi("GPKG", ".gpkg"))
dene("yazoku_ESRI_Shapefile", vektor_testi("ESRI Shapefile", ".shp"))
dene("yazoku_OpenFileGDB", vektor_testi("OpenFileGDB", ".gdb"))

import h5py
def t_hdf5():
    # ASTER GED gibi: boşluklu öznitelik adı "Scale Factor" (rapor E4)
    a = np.arange(12, dtype="uint8").reshape(3, 4)
    p = GECICI / "t.h5"
    with h5py.File(p, "w") as f:
        ds = f.create_dataset("Emissivity", data=a)
        ds.attrs["Scale Factor"] = 0.002
    with h5py.File(p, "r") as f:
        sf = float(f["Emissivity"].attrs["Scale Factor"])
    g = gdal.Open(str(p))
    alt = g.GetSubDatasets()
    src = gdal.Open(alt[0][0]) if alt else g
    b = src.ReadAsArray()
    src = None; g = None
    return np.array_equal(a, b) and sf == 0.002, "GDAL HDF5 ile okundu; 'Scale Factor' = " + str(sf)
dene("yazoku_HDF5", t_hdf5)

import netCDF4
def t_netcdf():
    a = np.arange(12, dtype="float32").reshape(3, 4)
    p = GECICI / "t.nc"
    with netCDF4.Dataset(p, "w") as n:
        n.createDimension("y", 3); n.createDimension("x", 4)
        v = n.createVariable("z", "f4", ("y", "x")); v[:] = a
    src = gdal.Open('NETCDF:"' + p.as_posix() + '":z')
    b = src.ReadAsArray()
    src = None
    if np.array_equal(a, b):
        return True, "aynı yönde okundu"
    if np.array_equal(a, np.flipud(b)):
        return True, "GDAL satırları ters çevirerek okudu (koordinatsız netCDF'te beklenen; kayda geçti)"
    return False, "değerler tutmuyor"
dene("yazoku_netCDF", t_netcdf)
# HDF4: Python'da HDF4 yazıcısı yok; gerçek okuma testi D2'de MCD12C1 dosyasıyla yapılır.
T["yazoku_HDF4"] = {"durum": "SONRA", "detay": "yalnız sürücü kontrol edildi; okuma testi D2'de MCD12C1 ile"}
print("[SONRA] yazoku_HDF4: okuma testi D2'de MCD12C1 ile")

# ---------- 5) GUDHI CubicalComplex, cevabı bilinen örnek ----------
import gudhi
def t_gudhi():
    # Dört köşe hücre 0, 1, 2, 3; aralar 5. Alt-seviye filtrasyonunda dört ayrı çukur
    # doğar ve hepsi 5'te birleşir. Beklenen H0: (0, sonsuz), (1, 5), (2, 5), (3, 5).
    hucre = np.array([[0, 5, 1], [5, 5, 5], [2, 5, 3]], dtype=float)
    cc = gudhi.CubicalComplex(top_dimensional_cells=hucre)
    p = cc.persistence()
    h0 = sorted((float(b), float(d)) for dim, (b, d) in p if dim == 0)
    beklenen = [(0.0, float("inf")), (1.0, 5.0), (2.0, 5.0), (3.0, 5.0)]
    return h0 == beklenen, "H0 = " + str(h0)
dene("gudhi_CubicalComplex", t_gudhi)

# ---------- 6) Earthdata: netrc ile giriş ve CMR araması ----------
NETRC = Path.home() / "_netrc"
kaydet("netrc_dosyasi", NETRC.is_file(), str(NETRC) + " (içerik okunmaz, yazılmaz)")
os.environ.setdefault("NETRC", str(NETRC))   # earthaccess/requests Windows'ta _netrc'yi bulsun
import earthaccess
def t_login():
    auth = earthaccess.login(strategy="netrc")
    return bool(getattr(auth, "authenticated", False)), "authenticated = " + str(getattr(auth, "authenticated", None))
dene("earthaccess_login_netrc", t_login)

def t_arama():
    # Rapor E2: CMR'de 13 Kasım'da hits = 1
    s = earthaccess.search_data(short_name="MCD12C1", version="061", temporal=("2023-01-01", "2023-12-31"))
    return len(s) == 1, str(len(s)) + " granül (rapor: 1)"
dene("earthaccess_arama_MCD12C1", t_arama)

# ---------- 7) Kayıt ----------
shutil.rmtree(GECICI, ignore_errors=True)
gecmeyen = [k for k, v in T.items() if v["durum"] == "FAIL"]
sonuc["ozet"] = {"toplam": len(T), "PASS": sum(v["durum"] == "PASS" for v in T.values()),
                 "FAIL": len(gecmeyen), "gecmeyenler": gecmeyen}
(KAYIT / "ortam.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8")
with open(KAYIT / "13_kasim_log.txt", "a", encoding="utf-8") as f:
    f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "  D0 ortam testi: "
            + str(sonuc["ozet"]["PASS"]) + " PASS, " + str(len(gecmeyen)) + " FAIL " + str(gecmeyen) + "\n")
print("=" * 50)
print("Yazıldı:", KAYIT / "ortam.json")
print("Özet:", sonuc["ozet"])
assert not gecmeyen, "Geçmeyen testler var: " + str(gecmeyen)
print("D0 TAMAM")
