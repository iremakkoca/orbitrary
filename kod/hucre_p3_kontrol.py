# Developed with assistance from Claude (Anthropic).
# P3 Dünya çıktısının denetimi: her alanda dolu oran, kategori kapsaması, z dağılımı → kayit\P3_dunya_ozet.json
import json, sys
from pathlib import Path
import numpy as np
KOK = Path.home() / "orbitrary"; KOD, KAYIT, ARA = KOK / "kod", KOK / "kayit", KOK / "ara"
if str(KOD) not in sys.path: sys.path.insert(0, str(KOD))
import kos
kim = np.load(ARA / "p3_dunya_kimlik.npy")
d = kos.Depo(ARA / "p3_dunya", len(kim))
assert d.tamam(), "P3 Dünya eksik blok var"
print("pencere:", len(kim))
oz = {"pencere": int(len(kim)), "alan": {}}
for ad, (kuyruk, dt) in sorted(d.sema.items()):
    a = d.oku(ad)
    if np.dtype(dt).kind == "f":
        dolu = np.isfinite(a.reshape(len(kim), -1)).all(axis=1) if a.ndim > 1 else np.isfinite(a)
        oz["alan"][ad] = {"bicim": kuyruk, "dolu_orani": round(float(dolu.mean()), 4)}
    else:
        oz["alan"][ad] = {"bicim": kuyruk, "ortalama": round(float(np.asarray(a).mean()), 4)}
    print(f"  {ad:14s} {str(kuyruk):12s} {oz['alan'][ad]}")
z = d.oku("z")
bil = ["theta_ort", "theta_09", "vrm_ort", "lnR", "n_asagi", "n_yukari"]
oz["z"] = {b: {"ortanca": float(np.nanmedian(z[:, i])), "yuzde1": float(np.nanpercentile(z[:, i], 1)),
               "yuzde99": float(np.nanpercentile(z[:, i], 99)),
               "MAD": float(np.nanmedian(np.abs(z[:, i] - np.nanmedian(z[:, i]))))} for i, b in enumerate(bil)}
print("z:"); [print("  ", b, v) for b, v in oz["z"].items()]
(KAYIT / "P3_dunya_ozet.json").write_text(json.dumps(oz, ensure_ascii=False, indent=1), encoding="utf-8")
print("→ kayit\\P3_dunya_ozet.json")
