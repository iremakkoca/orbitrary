# Developed with assistance from Claude (Anthropic).
"""V2 çift seçimi ve D8 kilidi (sentetik; gerçek veri yok)."""
import json
import types

import numpy as np
import pandas as pd
import pytest

import kos


def test_d8_kilit_ve_degisiklik(tmp_path, monkeypatch):
    kok = tmp_path
    for f in kos.SABIT_DOSYALAR:
        (kok / f).parent.mkdir(parents=True, exist_ok=True)
        (kok / f).write_text(f"icerik {f}", encoding="utf-8")
    (kok / "kayit").mkdir()
    monkeypatch.setattr(kos, "KOD", kok / "kod")
    monkeypatch.setattr(kos, "KAYIT", kok / "kayit")
    monkeypatch.setattr(kos, "kon_oku", lambda: 800)
    monkeypatch.setattr(kos, "sure_yaz", lambda *a, **k: None)
    s = kos.d8()
    assert s["K_on"] == 800 and len(s["sha256"]) == len(kos.SABIT_DOSYALAR)
    assert kos.d8_kontrol() == (True, [])
    assert kos.d8()["zaman"] == s["zaman"]                     # ikinci çağrı yeniden yazmaz
    (kok / "kod/ayar.json").write_text("değişti", encoding="utf-8")
    assert kos.d8_kontrol() == (False, ["kod/ayar.json"])
    with pytest.raises(AssertionError):
        kos.d8()


def test_v2_ciftleri(tmp_path, monkeypatch):
    rng = np.random.default_rng(1)
    n = 500
    D = types.SimpleNamespace(n=n, lat=rng.uniform(-50, 50, n), lon=rng.uniform(-180, 180, n), kim=np.arange(n) * 2 + 1)
    orman = np.where(np.arange(n) < 60, 95.0, 10.0); tarim = np.where(np.arange(n) >= 440, 92.0, 5.0)
    monkeypatch.setattr(kos, "Dunya", lambda: D)
    monkeypatch.setattr(kos.K, "ac", lambda ad: ad)
    def sahte(k, p, l, r):
        v = orman if k == "mcd12c1_02" else tarim
        assert len(p) == n
        return np.broadcast_to(v[:, None, None], (n, 40, 40)).copy(), None, None
    monkeypatch.setattr(kos.K, "hucreye", sahte)
    kl = tmp_path / "kod"; kl.mkdir(); (tmp_path / "kayit").mkdir()
    monkeypatch.setattr(kos, "KOD", kl); monkeypatch.setattr(kos, "KAYIT", tmp_path / "kayit")
    sut = ["tur", "cift_no", "hedef_kimlik", "dunya_saha", "enlem", "boylam", "gorev", "kaynak", "ilk_cift", "kaynak_yeri", "sude_kontrol"]
    v1 = pd.DataFrame([{"tur": "V1", "cift_no": i, "hedef_kimlik": f"H{i}", "dunya_saha": f"S{i}", "enlem": 0, "boylam": 0,
                        "gorev": "geology", "kaynak": "k", "ilk_cift": "evet", "kaynak_yeri": "", "sude_kontrol": ""} for i in range(1, 12)])[sut]
    v1.to_csv(kl / "dogrulama_ciftleri.csv", index=False, encoding="utf-8-sig")
    kos.v2_ciftleri()
    c = pd.read_csv(kl / "dogrulama_ciftleri.csv", encoding="utf-8-sig")
    v2 = c[c["tur"] == "V2"]
    assert len(v2) == 22 and list(c.columns) == sut
    sec = [int(s.split()[-1]) for s in v2["dunya_saha"]]
    assert len(set(sec)) == 22                                                   # tekrarsız
    orm = [int(s.split()[-1]) for s in v2["dunya_saha"] if "ormanı" in s]
    tar = [int(s.split()[-1]) for s in v2["dunya_saha"] if "tarım" in s]
    assert all((k - 1) // 2 < 60 for k in orm) and all((k - 1) // 2 >= 440 for k in tar)
    kos.v2_ciftleri()                                                             # ikinci çağrı dokunmaz
    assert len(pd.read_csv(kl / "dogrulama_ciftleri.csv", encoding="utf-8-sig")) == 33
