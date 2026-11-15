# Developed with assistance from Claude (Anthropic).
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
