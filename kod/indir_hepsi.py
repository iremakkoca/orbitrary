# Developed with assistance from Claude (Anthropic).
# indir_hepsi.py — Orbitrary v1.2, belge Bölüm 17.2 (veri indirme).
# Girdi : kod/indirme_listesi.csv; her açılışta kod/liste_denetim.py ile raporla denetlenir.
# Çıktı : veri/<govde>/<set>_<ad>/...  ham veri (doğrulanınca salt okunur yapılır)
#         kayit/indirme.csv     her dosya: adres, bayt, SHA-256, MD5, süre, deneme, durum, not
#         kayit/indirme_ozet.json, kayit/E1_karolar.csv, kayit/indirme_kuru.csv (--kuru)
# Kullanım (Anaconda Prompt, orbitrary ortamı, proje klasöründe):
#   python kod\indir_hepsi.py --kuru        indirmeden sunucuları, boyutları ve CMR'yi sınar
#   python kod\indir_hepsi.py               hepsini indirir; yeniden çalıştırılırsa kaldığı yerden devam eder
#   python kod\indir_hepsi.py --set E3 R5   yalnız seçilen setler
# Durumlar: PASS    boyut ve/veya sağlama tuttu
#           FAIL    tutmadı ya da inmedi (kayda yazılır, silinmez)
#           KONTROL raporda sağlama/boyut yok ya da yaklaşık (CMR); D1'de içerik testiyle kapanır
import argparse, csv, hashlib, json, os, re, shutil, stat, sys, threading, time, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import requests

KOK = Path.home() / "orbitrary"
VERI = KOK / "veri"
KAYIT = KOK / "kayit"
GECICI = KOK / "ara" / "indirme_gecici"          # Earthdata için geçici klasör (proje içinde)
LISTE = KOK / "kod" / "indirme_listesi.csv"

BEKLEMELER = [5, 15, 45, 120, 300]   # belge 17.2: artan bekleme (s); ilk deneme + 5 tekrar
KURU_BEKLEMELER = [5, 15]            # kuru koşuda kısa tekrar
ESZAMANLI = 4                        # belge 17.2: en fazla 4 eşzamanlı indirme
PARCA = 4 * 1024 * 1024
ZAMAN_ASIMI = (30, 120)              # (bağlantı, okuma) saniye
EN_AZ_BOS_DISK = 45e9                # belge 17.1: ham veri yaklaşık 45 GB (rapor toplamı 36,5 GB)
BASLIK = {"User-Agent": "Orbitrary/1.2 (NASA Space Apps 2026; research data download; python-requests)",
          "Accept-Encoding": "identity"}   # sunucu sıkıştırmasın: boyut ve Range ham bayt üzerinden

KILIT = threading.Lock()
ED_KILIT = threading.Lock()          # earthaccess.download aynı anda tek iş
SONUCLAR = []
_yerel = threading.local()
_indirilen = [0]

LOG_ALANLAR = ["zaman", "set", "hedef", "adres", "bayt", "beklenen_bayt", "sha256", "md5",
               "sure_s", "deneme", "durum", "not"]


class KaliciHata(Exception):
    """Tekrar denemenin anlamsız olduğu hata (ör. HTTP 404); varsa yedek adrese geçilir."""


def say(msg):
    with KILIT:
        print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


def ilerleme(n):
    with KILIT:
        _indirilen[0] += n


def oturum():
    # requests.Session iş parçacıkları arasında paylaşılmaz; her iş parçacığına bir oturum
    if not hasattr(_yerel, "s"):
        s = requests.Session()
        s.headers.update(BASLIK)
        _yerel.s = s
    return _yerel.s


def tekrarla(ad, fonk, beklemeler=BEKLEMELER):
    """fonk()'u çalıştırır; hata olursa artan beklemeyle tekrar dener. (sonuç, deneme sayısı) döner."""
    for i in range(len(beklemeler) + 1):
        try:
            return fonk(), i + 1
        except KaliciHata:
            raise
        except Exception as e:
            if i == len(beklemeler):
                raise
            say(f"   tekrar {i + 1}/{len(beklemeler)} {ad}: {type(e).__name__}: {str(e)[:150]} -> {beklemeler[i]} s bekleniyor")
            time.sleep(beklemeler[i])


def log_yaz(k):
    yol = KAYIT / "indirme.csv"
    with KILIT:
        yeni = not yol.exists()
        with open(yol, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LOG_ALANLAR)
            if yeni:
                w.writeheader()
            w.writerow({a: k.get(a, "") for a in LOG_ALANLAR})
        SONUCLAR.append(k)


def bitir(r, yol, durum, notlar, md5, sha, t0, deneme, adres, beklenen):
    k = {"zaman": datetime.now().isoformat(timespec="seconds"), "set": r["set"], "hedef": r["hedef"],
         "adres": adres, "bayt": yol.stat().st_size if (yol is not None and yol.exists()) else "",
         "beklenen_bayt": beklenen or "", "sha256": sha, "md5": md5,
         "sure_s": round(time.time() - t0, 1), "deneme": deneme, "durum": durum, "not": " | ".join(notlar)}
    log_yaz(k)
    say(f"[{durum}] {r['set']} {r['hedef']} ({k['bayt']} bayt, {k['sure_s']} s) {k['not'][:180]}")
    return durum


# ---------------------------------------------------------------- HTTP indirme (Range ile devam)
def http_indir(url, part, beklenen):
    """belge 17.2: var olan parçada Range: bytes=n- ; 206 ve Content-Range başlangıcı n ise eklenir;
    200 gelirse sıfırdan yazılır; 416 = tamam (doğrulama yine yapılır)."""
    s = oturum()
    n = part.stat().st_size if part.exists() else 0
    if beklenen and n > beklenen:
        part.unlink()
        n = 0
    if beklenen and n == beklenen:
        return "parca zaten tam boyutta"
    h = {"Range": f"bytes={n}-"} if n > 0 else {}
    with s.get(url, headers=h, stream=True, timeout=ZAMAN_ASIMI, allow_redirects=True) as r:
        if r.status_code == 416:
            return "416 (parca tam)"
        if r.status_code >= 500 or r.status_code in (408, 429):
            raise IOError(f"HTTP {r.status_code}")
        if r.status_code >= 400:
            raise KaliciHata(f"HTTP {r.status_code}")
        toplam = None
        cr = r.headers.get("Content-Range", "")
        if r.status_code == 206 and n > 0:
            m = re.match(r"bytes (\d+)-\d+/(\d+|\*)", cr)
            if not m or int(m.group(1)) != n:
                part.unlink()
                raise IOError(f"Content-Range uyusmuyor: {cr!r} (beklenen baslangic {n}); parca silindi")
            kip = "ab"
            if m.group(2) != "*":
                toplam = int(m.group(2))
        else:
            kip, n = "wb", 0                      # 200: sunucu Range'i yok saydı -> sıfırdan
            m = re.match(r"bytes \d+-\d+/(\d+)", cr)
            if m:
                toplam = int(m.group(1))
            elif r.headers.get("Content-Length"):
                toplam = int(r.headers["Content-Length"])
        with open(part, kip) as f:
            for c in r.iter_content(PARCA):
                if c:
                    f.write(c)
                    ilerleme(len(c))
    son = part.stat().st_size
    hedef_boyut = beklenen or toplam
    if hedef_boyut and son < hedef_boyut:
        raise IOError(f"baglanti erken kesildi: {son}/{hedef_boyut} bayt (kaldigi yerden devam edilecek)")
    return "tamam"


# ---------------------------------------------------------------- doğrulama
def ozetle(p):
    m5, s2 = hashlib.md5(), hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(PARCA), b""):
            m5.update(c)
            s2.update(c)
    return m5.hexdigest(), s2.hexdigest()


def uretici_deger(kaynak, anahtar, uzunluk):
    """Üreticinin md5/sha dosyasından anahtarın değerini bulur. Yollar '\\' ya da '/' ile olabilir."""
    for satir in kaynak.read_text(encoding="utf-8", errors="replace").splitlines():
        parcalar = satir.replace("*", " ").split()
        hexler = [p for p in parcalar if re.fullmatch(r"[0-9A-Fa-f]{%d}" % uzunluk, p)]
        if not hexler:
            continue
        for y in parcalar:
            if y in hexler:
                continue
            yn = y.replace("\\", "/")
            while yn.startswith("./") or yn.startswith("/"):
                yn = yn[2:] if yn.startswith("./") else yn[1:]
            if yn == anahtar or yn.endswith("/" + anahtar):
                return hexler[0]
    return None


def dogrula(r, p, beklenen):
    """(durum, notlar, md5, sha256). 'Dosya var' tamam sayılmaz: boyut ve sağlama kontrol edilir."""
    notlar, durum = [], "PASS"
    boyut = p.stat().st_size
    md5, sha = ozetle(p)
    with open(p, "rb") as f:
        bas = f.read(512)
    if boyut == 0:
        return "FAIL", ["0 bayt"], md5, sha
    if bas.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
        return "FAIL", ["HTML sayfasi geldi (ilk baytlar <!DOCTYPE/<html)"], md5, sha
    boyut_tuttu = (not beklenen) or boyut == beklenen
    if beklenen and not boyut_tuttu:
        notlar.append(f"boyut {boyut} != beklenen {beklenen}")
    tur = r["saglama_turu"]
    if tur in ("md5", "sha256"):
        hesap = md5 if tur == "md5" else sha
        ok_rapor = hesap.lower() == r["saglama_degeri"].lower()
        notlar.append(f"{tur} rapor " + ("tuttu" if ok_rapor else "TUTMADI"))
        ok_uretici = True
        if r["saglama_kaynak"]:
            kp = VERI / r["saglama_kaynak"]
            u = uretici_deger(kp, r["saglama_anahtar"], 32 if tur == "md5" else 64) if kp.exists() else None
            ok_uretici = u is not None and u.lower() == hesap.lower()
            notlar.append(f"{tur} uretici dosyasi " + ("tuttu" if ok_uretici else ("YOK" if u is None else "TUTMADI")))
        durum = "PASS" if (ok_rapor and ok_uretici) else "FAIL"
        if durum == "PASS" and not boyut_tuttu:
            notlar.append("saglama tuttugu icin boyut farki raporun boyut yazimindan")
    elif tur in ("zip_crc", "glim_uc_test"):
        if tur == "glim_uc_test" and boyut < 1_000_000_000:
            notlar.append("1 GB'tan kucuk")
            durum = "FAIL"
        if bas[:2] != b"PK":
            notlar.append("ilk baytlar PK degil")
            durum = "FAIL"
        else:
            with zipfile.ZipFile(p) as z:
                bilgi = z.infolist()
                yontemler = sorted({i.compress_type for i in bilgi})
                notlar.append(f"zip: {len(bilgi)} girdi, yontemler {yontemler}")
                if 9 in yontemler:
                    notlar.append("Deflate64 var; CRC D1'de inflate64 ile")
                    if durum == "PASS":
                        durum = "KONTROL"
                else:
                    bozuk = z.testzip()
                    if bozuk:
                        notlar.append(f"CRC bozuk: {bozuk}")
                        durum = "FAIL"
                    else:
                        notlar.append("testzip temiz (CRC)")
                if r["saglama_anahtar"]:
                    es = [i for i in bilgi if i.filename.endswith(r["saglama_anahtar"])]
                    if len(es) == 1 and f"{es[0].CRC:08x}" == r["saglama_degeri"].lower():
                        notlar.append("ana dosya CRC rapor tuttu")
                    else:
                        notlar.append("ana dosya CRC rapor TUTMADI")
                        durum = "FAIL"
        if not boyut_tuttu:
            durum = "FAIL"
    elif tur == "cmr_boyut":
        mb = float(r["cmr_mb"].replace(",", "."))
        fark = min(abs(boyut - mb * 1e6) / (mb * 1e6), abs(boyut - mb * 2 ** 20) / (mb * 2 ** 20))
        notlar.append(f"CMR {r['cmr_mb']} MB ile fark %{fark * 100:.2f}")
        if fark > 0.01:
            durum = "KONTROL"
            notlar.append("CMR boyutu yaklasik olabilir; D1'de HDF acilis testi")
    else:   # 'yok': yalnız boyut
        if beklenen:
            durum = "PASS" if boyut_tuttu else "FAIL"
        else:
            durum = "KONTROL"
            notlar.append("raporda boyut ve saglama yok; D1'de icerik testi")
    return durum, notlar, md5, sha


# ---------------------------------------------------------------- işler
def dosya_isi(r, url, beklenen, yedek=""):
    hedef = VERI / r["hedef"]
    hedef.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if hedef.exists():
        d, n, m5, s2 = dogrula(r, hedef, beklenen)
        return bitir(r, hedef, d, ["zaten vardi, yeniden dogrulandi"] + n, m5, s2, t0, 0, "", beklenen)
    part = hedef.with_name(hedef.name + ".part")
    adresler = [url] + ([yedek] if yedek else [])
    notlar, m5, s2, deneme, kullanilan = [], "", "", 0, ""
    for tur in (1, 2):               # 2. tur: doğrulama geçmezse parça silinip bir kez sıfırdan
        kullanilan, son_hata = None, None
        for a in adresler:
            try:
                _, deneme = tekrarla(f"{r['set']} {hedef.name}", lambda a=a: http_indir(a, part, beklenen))
                kullanilan = a
                break
            except Exception as e:
                son_hata = e
                say(f"   ! {r['set']} {hedef.name}: {a} -> {type(e).__name__}: {str(e)[:200]}")
        if kullanilan is None:
            return bitir(r, part if part.exists() else None, "FAIL", [f"indirilemedi: {son_hata}"],
                         "", "", t0, deneme, " ; ".join(adresler), beklenen)
        d, notlar, m5, s2 = dogrula(r, part, beklenen)
        if d != "FAIL":
            if kullanilan != url:
                notlar.append("YEDEK adresten indi")
            os.replace(part, hedef)
            os.chmod(hedef, stat.S_IREAD)            # veri\ salt okunur (belge 17.2)
            return bitir(r, hedef, d, notlar, m5, s2, t0, deneme, kullanilan, beklenen)
        if tur == 1:
            say(f"   ! {r['set']} {hedef.name} dogrulama gecmedi ({'; '.join(notlar)}); sifirdan bir kez daha")
            part.unlink()
    return bitir(r, part, "FAIL", notlar + ["ikinci indirmede de gecmedi; .part birakildi"],
                 m5, s2, t0, deneme, kullanilan, beklenen)


def earthdata_isi(r, granul):
    import earthaccess
    hedef = VERI / r["hedef"]
    hedef.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if hedef.exists():
        d, n, m5, s2 = dogrula(r, hedef, None)
        return bitir(r, hedef, d, ["zaten vardi, yeniden dogrulandi"] + n, m5, s2, t0, 0, "earthaccess", None)
    g, link = granul
    tmp = GECICI / hedef.stem

    def bir_kez():
        # Earthdata dosyaları belge 17.2'deki gibi earthaccess.download ile iner; Range ile devam yok,
        # bu yüzden her denemede geçici klasör temizlenir, tamamlanan dosya doğrulanınca veri\'ye taşınır.
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        with ED_KILIT:
            yollar = earthaccess.download([g], local_path=str(tmp), threads=1)
        p = tmp / hedef.name
        if not p.exists() or p.stat().st_size == 0:
            raise IOError(f"earthaccess dosyayi indirmedi: {yollar}")
        ilerleme(p.stat().st_size)          # Earthdata dosyalari da sayaca girer
        return p

    try:
        p, deneme = tekrarla(f"{r['set']} {hedef.name}", bir_kez)
    except Exception as e:
        return bitir(r, None, "FAIL", [f"indirilemedi: {e}"], "", "", t0, len(BEKLEMELER) + 1, link, None)
    d, notlar, m5, s2 = dogrula(r, p, None)
    if d != "FAIL":
        os.replace(p, hedef)
        os.chmod(hedef, stat.S_IREAD)
        shutil.rmtree(tmp, ignore_errors=True)
        return bitir(r, hedef, d, notlar, m5, s2, t0, deneme, link, None)
    return bitir(r, p, "FAIL", notlar, m5, s2, t0, deneme, link, None)


# ---------------------------------------------------------------- E1 karoları
class _Href(HTMLParser):
    def __init__(self):
        super().__init__()
        self.h = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.h.append(v)


def e1_karolar(r, beklemeler=BEKLEMELER):
    """Klasör listesinden _surface.tif karolarını okur; sayı 288, HEAD boyutlarının toplamı raporla aynı olmalı."""
    def liste():
        x = oturum().get(r["url"], timeout=ZAMAN_ASIMI)
        x.raise_for_status()
        return x.text
    html, _ = tekrarla("E1 klasor listesi", liste, beklemeler)
    p = _Href()
    p.feed(html)
    adlar = sorted({h.rsplit("/", 1)[-1] for h in p.h
                    if re.fullmatch(r"ETOPO_2022_v1_15s_[NS]\d\d[EW]\d{3}_surface\.tif", h.rsplit("/", 1)[-1])})
    assert len(adlar) == int(r["beklenen_adet"]), f"E1 karo sayisi {len(adlar)}, rapor {r['beklenen_adet']}"

    def boyut(ad):
        def head():
            x = oturum().head(r["url"] + ad, timeout=ZAMAN_ASIMI, allow_redirects=True)
            if x.status_code >= 400:
                raise IOError(f"HTTP {x.status_code}")
            return int(x.headers["Content-Length"])
        return tekrarla(f"E1 HEAD {ad}", head, beklemeler)[0]

    with ThreadPoolExecutor(ESZAMANLI) as ex:
        boyutlar = list(ex.map(boyut, adlar))
    toplam = sum(boyutlar)
    assert toplam == int(r["beklenen_bayt"]), f"E1 toplam {toplam} bayt, rapor {r['beklenen_bayt']}"
    with open(KAYIT / "E1_karolar.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ad", "adres", "bayt_HEAD"])
        for a, b in zip(adlar, boyutlar):
            w.writerow([a, r["url"] + a, b])
    say(f"E1: {len(adlar)} karo, HEAD toplami {toplam} bayt (rapor {r['beklenen_bayt']}) -> kayit/E1_karolar.csv")
    karolar = []
    for a, b in zip(adlar, boyutlar):
        k = dict(r)
        k.update(hedef="dunya/E1_etopo/" + a, url=r["url"] + a, beklenen_bayt=str(b), beklenen_adet="",
                 yontem="https", saglama_turu="yok")
        karolar.append(k)
    return karolar


# ---------------------------------------------------------------- Earthdata arama
def earthdata_hazirla(satirlar, beklemeler=BEKLEMELER):
    import earthaccess
    os.environ.setdefault("NETRC", str(Path.home() / "_netrc"))   # şifre okunmaz, yazılmaz
    auth = earthaccess.login(strategy="netrc")
    assert getattr(auth, "authenticated", False), "Earthdata girisi basarisiz (_netrc)"
    gruplar = {}
    for r in satirlar:
        gruplar.setdefault((r["short_name"], r["version"], r["temporal"]), []).append(r)
    eslesme = {}
    for (sn, v, t), rs in gruplar.items():
        a, b = t.split("|")
        sonuc, _ = tekrarla(f"CMR {sn}", lambda: earthaccess.search_data(short_name=sn, version=v, temporal=(a, b)),
                            beklemeler)
        harita = {}
        for g in sonuc:
            for l in g.data_links():
                harita.setdefault(l.rsplit("/", 1)[-1], (g, l))
        for r in rs:
            ad = r["hedef"].rsplit("/", 1)[-1]
            assert ad in harita, f"{r['set']} {ad} CMR aramasinda bulunamadi"
            eslesme[r["hedef"]] = harita[ad]
        say(f"CMR {sn} v{v} {a}..{b}: {len(sonuc)} granul bulundu, {len(rs)} dosya ada gore eslendi")
    return eslesme


# ---------------------------------------------------------------- kuru koşu
def yokla(url):
    """İlk 16 baytı ister (Range 0-15): HTTP durumu, sunucudaki toplam boyut, ilk baytlar."""
    with oturum().get(url, headers={"Range": "bytes=0-15"}, stream=True, timeout=ZAMAN_ASIMI,
                      allow_redirects=True) as x:
        if x.status_code >= 500 or x.status_code in (408, 429):
            raise IOError(f"HTTP {x.status_code}")
        if x.status_code >= 400:
            raise KaliciHata(f"HTTP {x.status_code}")
        bas = x.raw.read(16)
        m = re.match(r"bytes \d+-\d+/(\d+)", x.headers.get("Content-Range", ""))
        if m:
            toplam = int(m.group(1))
        elif x.status_code == 200 and x.headers.get("Content-Length"):
            toplam = int(x.headers["Content-Length"])
        else:
            toplam = None
        return x.status_code, toplam, bas


def kuru(satirlar):
    say("KURU KOSU: dosya indirilmez; sunucular, boyutlar ve Earthdata aramasi sinanir")
    alanlar = ["set", "hedef", "adres", "http", "sunucu_boyut", "beklenen_bayt", "boyut", "ilk_baytlar", "durum", "hata"]
    cikti = []
    for r in [x for x in satirlar if x["yontem"] == "klasor"]:
        try:
            e1_karolar(r, KURU_BEKLEMELER)
            cikti.append({"set": "E1", "hedef": r["hedef"], "adres": r["url"], "durum": "OK",
                          "boyut": "288 karo ve toplam bayt rapora esit"})
        except Exception as e:
            cikti.append({"set": "E1", "hedef": r["hedef"], "adres": r["url"], "durum": "SORUN", "hata": str(e)})
    ed = [x for x in satirlar if x["yontem"] == "earthaccess"]
    if ed:
        try:
            es = earthdata_hazirla(ed, KURU_BEKLEMELER)
            for r in ed:
                g, link = es[r["hedef"]]
                try:
                    mb = round(float(g.size()), 3)
                except Exception:
                    mb = ""
                cikti.append({"set": r["set"], "hedef": r["hedef"], "adres": link, "sunucu_boyut": f"{mb} MB (CMR)",
                              "beklenen_bayt": r["cmr_mb"] + " MB (rapor)", "durum": "OK"})
        except Exception as e:
            cikti.append({"set": "Earthdata", "durum": "SORUN", "hata": f"{type(e).__name__}: {e}"})
    for r in [x for x in satirlar if x["yontem"] in ("https", "http")]:
        adresler = [r["url"]] + ([yedek_adresi(r)] if r["yedek_url"] else [])
        satir = {"set": r["set"], "hedef": r["hedef"], "beklenen_bayt": r["beklenen_bayt"]}
        for a in adresler:
            try:
                (kod, toplam, bas), _ = tekrarla(f"{r['set']} yokla", lambda a=a: yokla(a), KURU_BEKLEMELER)
                html = bas.lstrip()[:15].lower().startswith((b"<!doctype", b"<html"))
                if r["beklenen_bayt"] and toplam is not None:
                    bd = "ayni" if int(r["beklenen_bayt"]) == toplam else "FARKLI"
                else:
                    bd = "bilinmiyor"
                satir.update(adres=a, http=kod, sunucu_boyut=toplam, ilk_baytlar=bas.hex(" "), boyut=bd,
                             durum="SORUN" if (html or bd == "FARKLI") else ("OK" if a == r["url"] else "OK (yedek)"),
                             hata="HTML geldi" if html else "")
                break
            except Exception as e:
                satir.update(adres=a, durum="ULASILAMADI", hata=f"{type(e).__name__}: {str(e)[:200]}")
        cikti.append(satir)
        say(f"   {satir['durum']:12} {r['set']:4} {r['hedef'].rsplit('/', 1)[-1]:48} "
            f"http={satir.get('http', '')} sunucu={satir.get('sunucu_boyut', '')} beklenen={r['beklenen_bayt']} {satir.get('hata', '')}")
    with open(KAYIT / "indirme_kuru.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=alanlar)
        w.writeheader()
        for c in cikti:
            w.writerow({a: c.get(a, "") for a in alanlar})
    say_ = {}
    for c in cikti:
        say_[c["durum"]] = say_.get(c["durum"], 0) + 1
    say(f"KURU KOSU BITTI: {say_} -> kayit/indirme_kuru.csv")
    for c in cikti:
        if c["durum"] not in ("OK", "OK (yedek)"):
            say(f"   SORUNLU: {c.get('set')} {c.get('hedef', '')} {c.get('adres', '')} {c.get('hata', '')} boyut={c.get('boyut', '')}")


def yedek_adresi(r):
    y = r["yedek_url"]
    if y and "dropbox.com" in y and "dl=" not in y:
        y += "?dl=1"                        # rapor E3: yedek bağlantıya ?dl=1 eklenir
    return y


# ---------------------------------------------------------------- ana akış
def main():
    ap = argparse.ArgumentParser(description="Orbitrary v1.2 veri indirme (belge 17.2)")
    ap.add_argument("--kuru", action="store_true", help="indirmeden sina")
    ap.add_argument("--set", nargs="*", default=None, help="yalniz bu setler (or. E3 R5)")
    a = ap.parse_args()

    sys.path.insert(0, str(KOK / "kod"))
    import liste_denetim
    d = liste_denetim.denetle()
    assert d["durum"] == "PASS", f"liste denetimi gecmedi: {d['hatalar'][:5]}"
    say(f"Liste denetimi PASS: {d['satir']} satir, {d['dosya']} dosya, rapor sha256 {d['rapor_sha256'][:16]}...")

    with open(LISTE, encoding="utf-8", newline="") as f:
        tum = list(csv.DictReader(f))
    satirlar = [r for r in tum if (a.set is None or r["set"] in a.set)]
    assert satirlar, "secilen set yok"
    bos = shutil.disk_usage(KOK).free
    say(f"Bos disk: {bos / 1e9:.1f} GB")
    assert bos >= EN_AZ_BOS_DISK, f"bos disk {bos / 1e9:.1f} GB < {EN_AZ_BOS_DISK / 1e9:.0f} GB"
    VERI.mkdir(exist_ok=True)

    if a.kuru:
        kuru(satirlar)
        return 0

    t_bas = time.time()
    durduruldu = threading.Event()

    def durum_yazici():
        while not durduruldu.wait(60):
            say(f"... bu oturumda indirilen {_indirilen[0] / 1e9:.2f} GB, gecen {(time.time() - t_bas) / 60:.1f} dk")
    threading.Thread(target=durum_yazici, daemon=True).start()

    def guvenli(f, *x):
        try:
            return f(*x)
        except Exception as e:
            r = x[0]
            return bitir(r, None, "FAIL", [f"beklenmeyen hata: {type(e).__name__}: {e}"], "", "", time.time(), 0, "", None)

    # Faz A: üreticinin sağlama dosyaları (diğer dosyaların doğrulaması bunlara bakar)
    gereken = {r["saglama_kaynak"] for r in satirlar if r["saglama_kaynak"]}
    faz_a = [r for r in tum if r["hedef"] in gereken]
    say(f"FAZ A: {len(faz_a)} uretici saglama dosyasi")
    for r in faz_a:
        guvenli(dosya_isi, r, r["url"], int(r["beklenen_bayt"]) if r["beklenen_bayt"] else None)
    a_hedef = {r["hedef"] for r in faz_a}

    # Faz B: grup 1 ve 2, en fazla 4 eşzamanlı, büyük dosyalar önce
    isler = []
    for r in satirlar:
        if r["hedef"] in a_hedef or r["grup"] == "3":
            continue
        if r["yontem"] == "klasor":
            for k in e1_karolar(r):
                isler.append((int(r["grup"]), int(k["beklenen_bayt"]), "http", k))
        elif r["yontem"] == "earthaccess":
            isler.append((int(r["grup"]), float(r["cmr_mb"].replace(",", ".")) * 1e6, "ed", r))
        else:
            isler.append((int(r["grup"]), int(r["beklenen_bayt"] or 0), "http", r))
    eslesme = earthdata_hazirla([x[3] for x in isler if x[2] == "ed"]) if any(x[2] == "ed" for x in isler) else {}
    isler.sort(key=lambda x: (x[0], -x[1]))
    say(f"FAZ B: {len(isler)} dosya, {ESZAMANLI} esanli")
    with ThreadPoolExecutor(ESZAMANLI) as ex:
        fut = []
        for _, _, tur, r in isler:
            if tur == "ed":
                fut.append(ex.submit(guvenli, earthdata_isi, r, eslesme[r["hedef"]]))
            else:
                fut.append(ex.submit(guvenli, dosya_isi, r, r["url"],
                                     int(r["beklenen_bayt"]) if r["beklenen_bayt"] else None, yedek_adresi(r)))
        for _ in as_completed(fut):
            pass

    # Faz C: kararsız sunucular (SWIM, ASU, PSI, Dropbox) tek tek
    faz_c = [r for r in satirlar if r["grup"] == "3" and r["hedef"] not in a_hedef]
    say(f"FAZ C: {len(faz_c)} dosya, tek tek (kararsiz sunucular)")
    for r in faz_c:
        guvenli(dosya_isi, r, r["url"], int(r["beklenen_bayt"]) if r["beklenen_bayt"] else None, yedek_adresi(r))
    durduruldu.set()

    # Özet
    ozet = {"bitis": datetime.now().isoformat(timespec="seconds"),
            "sure_dk": round((time.time() - t_bas) / 60, 1),
            "bu_oturumda_indirilen_gb": round(_indirilen[0] / 1e9, 3),
            "secilen_setler": a.set or "hepsi", "durum_sayilari": {}, "set_basina": {},
            "FAIL": [], "KONTROL": []}
    for k in SONUCLAR:
        ozet["durum_sayilari"][k["durum"]] = ozet["durum_sayilari"].get(k["durum"], 0) + 1
        sb = ozet["set_basina"].setdefault(k["set"], {})
        sb[k["durum"]] = sb.get(k["durum"], 0) + 1
        if k["durum"] in ("FAIL", "KONTROL"):
            ozet[k["durum"]].append({"hedef": k["hedef"], "not": k["not"]})
    (KAYIT / "indirme_ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(KAYIT / "13_kasim_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  2b indirme ({ozet['secilen_setler']}): {ozet['durum_sayilari']}, "
                f"{ozet['sure_dk']} dk, {ozet['bu_oturumda_indirilen_gb']} GB\n")
    say("=" * 60)
    say(f"BITTI: {ozet['durum_sayilari']} | {ozet['sure_dk']} dk | {ozet['bu_oturumda_indirilen_gb']} GB")
    for k in ozet["FAIL"]:
        say(f"   FAIL    {k['hedef']}: {k['not'][:200]}")
    for k in ozet["KONTROL"]:
        say(f"   KONTROL {k['hedef']}: {k['not'][:200]}")
    say("Ayrintilar: kayit/indirme.csv, kayit/indirme_ozet.json")
    return 1 if ozet["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
