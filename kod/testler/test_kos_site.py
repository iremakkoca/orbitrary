# Developed with assistance from Claude (Anthropic).
"""P9 site verisi: halka dosyalarının bayt düzeni, earth tablosu eşlemesi, analog.json türleri, ozet/meta alanları (sentetik)."""
import json

import numpy as np
import pandas as pd

import kos
import izgara as Zg
from test_kos_puanla import _sahte, nE


def test_site_veri(tmp_path, monkeypatch):
    D = _sahte()
    D.n = nE
    ara, son, kod, kay = tmp_path / "ara", tmp_path / "sonuc", tmp_path / "kod", tmp_path / "kayit"
    for k in (ara, son / "liste", son / "dogrulama", kod / "site_girdi", kay):
        k.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(kos, "ARA", ara); monkeypatch.setattr(kos, "SONUC", son); monkeypatch.setattr(kos, "SITE", son / "site")
    monkeypatch.setattr(kos, "KOD", kod); monkeypatch.setattr(kos, "KAYIT", kay)
    monkeypatch.setattr(kos, "Dunya", lambda: D); monkeypatch.setattr(kos, "sure_yaz", lambda *a, **k: None)
    monkeypatch.setattr(kos, "yakin_ust_km", lambda: 100.0)
    monkeypatch.setattr(kos, "bilinen_analoglar", lambda: [("v-a", 10.0, 20.0), ("m-b", -30.0, 50.0)])
    nA = Zg.Halka("ay").n
    monkeypatch.setattr(kos, "izgara", lambda g: np.zeros({"dunya": 10, "ay": nA, "mars": 5}[g]))
    (kod / "ayar.json").write_text(json.dumps({"parametreler": {"kapi": {}, "agirlik": {}}}), encoding="utf-8")
    pd.DataFrame({"kimlik": ["A3-01", "R-JEZ"], "ad": ["a", "j"], "cisim": ["ay", "mars"], "enlem": [-89, 18], "boylam": [0, 77]}).to_csv(
        kod / "hedefler.csv", index=False)
    rng = np.random.default_rng(0)
    def ilk(k):
        return [{"kimlik": int(D.kim[e]), "enlem": float(D.lat[e]), "boylam": float(D.lon[e]), "P": 0.9, "s": [0.5] * 8,
                 "en_yakin_analog": {"id": "v-a", "km": 150.0 if q == 0 else 5.0}} for q, e in enumerate(rng.choice(nE, 10, replace=False))]
    for k in ("A3-01", "R-JEZ"):
        (son / "liste" / f"liste_{k}.json").write_text(json.dumps({"gorevler": {"genel": {"ilk10": ilk(k)}}}), encoding="utf-8")
    # Katman B: Ay tamam (sahte), Mars yok
    dp = kos.Depo(ara / "katmanb_ay", nA)
    for b in range(dp.nb):
        a, z = b * kos.BLOK, min(nA, (b + 1) * kos.BLOK)
        m = z - a
        t3 = rng.choice(nE, (m, 5, 3)); t3[:, 3, :] = -1
        dp.yaz(b, {"top3": t3.astype(np.int64), "P": rng.random((m, 5, 3)).astype(np.float32),
                   "s": rng.random((m, 5, 3, 8)).astype(np.float32), "eksik": np.zeros((m, 5, 3, 8), np.int8),
                   "durum": np.zeros((m, 5), np.int8), "aday": np.full((m, 5), 800, np.int32)})
    kos.site_veri()
    s = son / "site"
    meta = json.loads((s / "meta.json").read_text(encoding="utf-8"))
    earth = json.loads((s / "earth.json").read_text(encoding="utf-8"))
    H = Zg.Halka("ay")
    assert meta["izgara"]["moon"]["M"] == H.M and len(list((s / "grid" / "moon").glob("*.bin"))) == H.M
    assert not (s / "grid" / "mars").exists()
    for i in (0, 5, H.M // 2):
        m = int(H.m[i]); raw = (s / "grid" / "moon" / f"{i}.bin").read_bytes()
        assert len(raw) == m * (15 * 4 + 15 + 120 + 120 + 5)
        idx = np.frombuffer(raw[: m * 60], "<u4").reshape(m, 5, 3)
        t3 = np.asarray(kos.Depo(ara / "katmanb_ay", nA).oku("top3"))[H.ofset[i]:H.ofset[i + 1]]
        ok = t3 >= 0
        assert (idx[~ok] == 0xFFFFFFFF).all()
        assert all(earth["kimlik"][int(x)] == int(D.kim[r]) for x, r in zip(idx[ok], t3[ok]))
    for t in meta["izgara"]["moon"]["test"]:
        assert H.tikla(t["enlem"], t["boylam"]) == t["kimlik"] and H.i[t["kimlik"]] == t["halka"]
    an = json.loads((s / "analog.json").read_text(encoding="utf-8"))
    assert {x["tur"] for x in an} == {"candidate"} and all(x["en_yakin_bilinen"]["km"] > 100 for x in an)
    hed = json.loads((s / "hedefler.json").read_text(encoding="utf-8"))
    assert hed[0]["etiket"] == kos.ARTEMIS_ETIKET and "etiket" not in hed[1]
    oz = json.loads((son / "ozet.json").read_text(encoding="utf-8"))
    assert oz["E_prime"] == nE and oz["katman_B"]["cisim"]["ay"]["tamam"] and not oz["katman_B"]["cisim"]["mars"]["tamam"]
    assert (kay / "SITE_VERI_NOTU.md").exists()
