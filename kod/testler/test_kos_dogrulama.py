# Developed with assistance from Claude (Anthropic).
"""P8 doğrulama akışı uçtan uca, sentetik Dünya ile (gerçek veri yok): biçim, Π tanımı, V2/V3/V6/V8/V9 alanları."""
import json
import types

import numpy as np
import pandas as pd

import kos
import ozellik_topoloji as TP
from test_kos_puanla import _hedef, _sahte, nE


def test_dogrulama_uctan_uca(tmp_path, monkeypatch):
    D = _sahte()
    x = np.arange(40) * 500.0
    diy = [TP.diyagramlar(150 * np.sin(x[None, :] / (2000 + 10 * i)) * np.cos(x[:, None] / 2600), "dunya", yontem="union_find")
           for i in range(50)]
    monkeypatch.setattr(kos, "dunya_diyagram", lambda D_, idx: [diy[int(i) % 50] for i in idx])
    R = np.random.default_rng(2).permutation(nE)
    monkeypatch.setattr(kos, "Dunya", lambda: D)
    monkeypatch.setattr(kos, "referans_kumeleri", lambda n: (R[:2000], R[:200]))
    hedefler = ["H1", "H2", "H3"]
    monkeypatch.setattr(kos, "hedef_hazirla", lambda s: dict(_hedef(True), kimlik=s["kimlik"], ad=s["kimlik"]))
    monkeypatch.setattr(kos, "X_hesapla", lambda D_, hz, c: ((0.1, {i: 0.1 for i in range(1, 12)}), {}))
    # tıklama: (enlem, boylam) → E′ satırının kimliği
    monkeypatch.setattr(kos.Z, "Halka", lambda g: types.SimpleNamespace(
        tikla=lambda la, lo: int(D.kim[int(np.argmin((D.lat - la) ** 2 + (D.lon - lo) ** 2))])))
    kod, son = tmp_path / "kod", tmp_path / "sonuc"
    (son / "liste").mkdir(parents=True); kod.mkdir()
    monkeypatch.setattr(kos, "KOD", kod); monkeypatch.setattr(kos, "SONUC", son)
    monkeypatch.setattr(kos, "sure_yaz", lambda *a, **k: None)
    pd.DataFrame({"kimlik": hedefler, "ad": hedefler, "cisim": "ay", "enlem": 0, "boylam": 0}).to_csv(kod / "hedefler.csv", index=False)
    rows = []
    for i in range(1, 12):
        e = 100 + i * 37
        rows.append({"tur": "V1", "cift_no": i, "hedef_kimlik": hedefler[i % 3], "dunya_saha": f"S{min(i, 8)}",
                     "enlem": D.lat[e], "boylam": D.lon[e], "gorev": ["geology", "mobility", "genel"][i % 3]})
    for i in range(1, 12):
        for q in (0, 1):
            e = 900 + i * 13 + q
            rows.append({"tur": "V2", "cift_no": i, "hedef_kimlik": hedefler[i % 3], "dunya_saha": f"V2 {q} {i}",
                         "enlem": D.lat[e], "boylam": D.lon[e], "gorev": ["geology", "mobility", "genel"][i % 3]})
    pd.DataFrame(rows).to_csv(kod / "dogrulama_ciftleri.csv", index=False)
    rng = np.random.default_rng(1)
    for h in hedefler:
        ilk = [{"s": list(map(float, rng.random(8)))} for _ in range(10)]
        (son / "liste" / f"liste_{h}.json").write_text(json.dumps({"gorevler": {"genel": {"ilk10": ilk}}}), encoding="utf-8")
    kos.dogrulama()
    o = json.loads((son / "dogrulama" / "dogrulama.json").read_text(encoding="utf-8"))
    assert len(o["V1"]) == 11 and o["V2"]["m"] == 22 and o["V1_ilk8"]["m"] == 8
    assert all(0 <= v["Pi"] <= 1 and len(v["s"]) == 8 and len(v["Pi_k"]) == 8 for v in o["V1"])
    assert all(v["Pi"] == 0 for v in o["V1"] if v["kapidan_kaldi"])
    assert 0 <= o["V3"]["AUC"] <= 1 and o["V3"]["nB"] == 11 * 1000
    assert o["V6"]["n"] == 30 and len(o["V9"]["p_kategori"]) == 8
    assert all(len(v) == 8 for v in o["V8"].values())
