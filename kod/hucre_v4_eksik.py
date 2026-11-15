# Developed with assistance from Claude (Anthropic).
# V4: 112 beklenen hedef x gorev durumundan hangisi V4.json'a girmedi ve neden?
import os, sys, json
from pathlib import Path
import numpy as np

KOD = Path(r"C:\Users\USER\orbitrary\kod")
os.chdir(KOD); sys.path.insert(0, str(KOD))
import kos as K
import izgara as Z

GOREV = K.GOREVLER
v4 = json.loads((K.SONUC / "dogrulama" / "V4.json").read_text(encoding="utf-8"))["satirlar"]
v4_set = {(r["hedef"], r["gorev"]) for r in v4}
print("V4.json satir sayisi:", len(v4))

A = {}
for p in sorted((K.SONUC / "liste").glob("liste_*.json")):
    A[p.stem.replace("liste_", "")] = json.loads(p.read_text(encoding="utf-8"))
assert len(A) == 26, f"26 liste dosyasi bekleniyordu, {len(A)} bulundu"

hesap = [(k, g) for k, o in A.items() for g in GOREV
         if (o["gorevler"].get(g) or {}).get("durum") == "computed" and (o["gorevler"].get(g) or {}).get("ilk10")]
print("Katman A'da hesaplanan hedef x gorev:", len(hesap))

eksik = [x for x in hesap if x not in v4_set]
print("V4'e girmeyen:", eksik)

for k, g in eksik:
    h = A[k]["hedef"]
    cisim = "ay" if k.startswith(("A3-", "M-")) else "mars"
    H = Z.Halka(cisim)
    dp = K.Depo(K.ARA / f"katmanb_{cisim}", H.n)
    t3 = np.asarray(dp.oku("top3"))
    c = int(H.tikla(h["enlem"], h["boylam"]))
    gi = GOREV.index(g)
    print(f"\n{k} / {g}: Katman B hucresi {c}, top3 = {t3[c, gi].tolist()}")
    print("  -> Katman B'de bu hucrede bu gorev icin aday yok." if (t3[c, gi] < 0).all()
          else "  -> Katman B'de aday var; baska bir neden, ciktiyi Claude'a at.")