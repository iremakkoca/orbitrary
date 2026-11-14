# Developed with assistance from Claude (Anthropic).
# Liste denetimi (belge 17.2 girdisi): kod\indirme_listesi.csv'deki her adres, boyut,
# sağlama değeri, granül adı ve CMR boyutu kod\indirme_raporu3.md içinde geçiyor mu?
# indir_hepsi.py her başlangıçta bunu çalıştırır; tek bir hata varsa indirme başlamaz.
import csv, json, re, hashlib
from pathlib import Path
from datetime import datetime

KOK = Path.home() / "orbitrary"
RAPOR = KOK / "kod" / "indirme_raporu3.md"
LISTE = KOK / "kod" / "indirme_listesi.csv"
BEKLENEN_DOSYA = 409                 # rapor, Ek bölüm 2 "Toplam" tablosu
SETLER = [f"E{i}" for i in range(1, 11)] + [f"M{i}" for i in range(1, 8)] + [f"R{i}" for i in range(1, 8)]

def _genislet(s):
    # "a.{tab,lbl}" -> ["a.tab", "a.lbl"]; iç içe olmayan, virgüllü süslü parantezler
    m = re.search(r"\{([^{}]*,[^{}]*)\}", s)
    if not m:
        return [s]
    out = []
    for p in m.group(1).split(","):
        out += _genislet(s[:m.start()] + p.strip() + s[m.end():])
    return out

def denetle():
    ham = RAPOR.read_bytes()
    R = ham.decode("utf-8")
    # Boşluklu sayılar birleştirilir: "604 800 210" -> "604800210"
    RN = R
    for _ in range(6):
        RN = re.sub(r"(?<=\d)[ \u00a0\u202f\u2009](?=\d{3}(?!\d))", "", RN)
    GEN = set()
    for tok in re.findall(r"[^\s`'\"()<>\u00b7]*\{[^{}\s]+\}[^\s`'\"()<>\u00b7]*", R):
        for g in _genislet(tok):
            GEN.add(g)
            GEN.add(g.split("://", 1)[-1])

    def adres(u):
        if u in R:
            return "tam"
        if u in GEN:
            return "genisletilmis"
        d, ad = u.rsplit("/", 1)
        if (ad in R or ad in GEN) and d.split("://", 1)[-1] in R:
            return "klasor+ad"
        return None

    def sayi_var(n):
        return re.search(r"(?<![\d.,])" + re.escape(str(n)) + r"(?!\d)", RN) is not None

    with open(LISTE, encoding="utf-8", newline="") as f:
        satirlar = list(csv.DictReader(f))
    hatalar, kurallar = [], {}
    for i, r in enumerate(satirlar, start=2):           # 1. satır başlık
        etiket = f"satir {i} {r['set']} {r['hedef']}"
        def hata(m):
            hatalar.append(etiket + ": " + m)
        if r["set"] not in SETLER:
            hata("bilinmeyen set")
        if r["url"]:
            k = adres(r["url"])
            if k is None:
                hata("adres raporda yok: " + r["url"])
            kurallar[k] = kurallar.get(k, 0) + 1
        if r["yedek_url"] and adres(r["yedek_url"]) is None:
            hata("yedek adres raporda yok: " + r["yedek_url"])
        if r["beklenen_bayt"] and not sayi_var(r["beklenen_bayt"]):
            hata("boyut raporda yok: " + r["beklenen_bayt"])
        if r["beklenen_adet"] and not sayi_var(r["beklenen_adet"]):
            hata("adet raporda yok: " + r["beklenen_adet"])
        if r["saglama_degeri"] and r["saglama_degeri"] not in R:
            hata("saglama degeri raporda yok: " + r["saglama_degeri"])
        if r["yontem"] == "klasor" and "ETOPO_2022_v1_15s_{N|S}{YY}{E|W}{XXX}_surface.tif" not in R:
            hata("E1 ad kalibi raporda yok")
        if r["yontem"] == "earthaccess":
            if f'short_name="{r["short_name"]}", version="{r["version"]}"' not in R:
                hata("short_name/version raporda yok")
            a, b = r["temporal"].split("|")
            if f'temporal=("{a}","{b}")' not in R:
                hata("temporal raporda yok")
            if r["set"] == "E4":
                if "ASTER_GEDv4.1_A2015{DDD}.h5" not in R or \
                   "001, 032, 060, 091, 121, 152, 182, 213, 244, 274, 305, 335" not in R:
                    hata("E4 ad kalibi ya da DDD listesi raporda yok")
                if r["cmr_mb"] not in R:
                    hata("CMR boyutu raporda yok")
            elif r["set"] == "E2":
                if r["granul"] not in R or r["cmr_mb"] not in R:
                    hata("granul adi ya da CMR boyutu raporda yok")
            else:
                if f"`{r['granul']}` {r['cmr_mb']}" not in R:
                    hata("granul adi + CMR boyutu cifti raporda yok")
    hedefler = [r["hedef"] for r in satirlar]
    if len(set(hedefler)) != len(hedefler):
        hatalar.append("ayni hedef yolu birden fazla satirda")
    if not all(h.split("/")[0] in ("dunya", "ay", "mars") for h in hedefler):
        hatalar.append("hedef dunya/ay/mars disinda")
    eksik_set = [s for s in SETLER if s not in {r["set"] for r in satirlar}]
    if eksik_set:
        hatalar.append("listede olmayan set: " + str(eksik_set))
    dosya_sayisi = sum(int(r["beklenen_adet"]) if r["beklenen_adet"] else 1 for r in satirlar)
    if dosya_sayisi != BEKLENEN_DOSYA:
        hatalar.append(f"dosya sayisi {dosya_sayisi}, rapor {BEKLENEN_DOSYA}")
    set_sayim = {}
    for r in satirlar:
        set_sayim[r["set"]] = set_sayim.get(r["set"], 0) + (int(r["beklenen_adet"]) if r["beklenen_adet"] else 1)
    return {"tarih": datetime.now().isoformat(timespec="seconds"),
            "rapor": str(RAPOR), "rapor_sha256": hashlib.sha256(ham).hexdigest(),
            "liste": str(LISTE), "liste_sha256": hashlib.sha256(LISTE.read_bytes()).hexdigest(),
            "satir": len(satirlar), "dosya": dosya_sayisi, "set_basina_dosya": set_sayim,
            "adres_kurali": kurallar, "hatalar": hatalar, "durum": "PASS" if not hatalar else "FAIL"}

if __name__ == "__main__":
    s = denetle()
    (KOK / "kayit" / "liste_denetim.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    (KOK / "kayit" / "rapor_sha256.txt").write_text(s["rapor_sha256"] + "  kod/indirme_raporu3.md\n", encoding="utf-8")
    with open(KOK / "kayit" / "13_kasim_log.txt", "a", encoding="utf-8") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + f"  2a liste denetimi {s['durum']}: "
                f"{s['satir']} satir, {s['dosya']} dosya, {len(s['hatalar'])} hata\n")
    print("Rapor SHA-256:", s["rapor_sha256"])
    print("Satır:", s["satir"], "| Dosya:", s["dosya"], "(rapor: 409)")
    print("Set başına dosya:", s["set_basina_dosya"])
    print("Adres kuralı:", s["adres_kurali"])
    for h in s["hatalar"]:
        print("HATA:", h)
    print("Durum:", s["durum"])
    assert not s["hatalar"], f"{len(s['hatalar'])} hata var; indirme başlamaz"
