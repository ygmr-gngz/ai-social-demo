# agents.py
# Basit AI sosyal demo yardımcıları:
# - weights (yükle/kaydet/auto-update)
# - metin skoru, görsel skoru
# - moderasyon, para dönüşümü, feed sıralama
# - görselden video üretimi (MoviePy; güvenli import + numpy dönüşümü)

import json
import time
from typing import List, Dict
from PIL import Image, ImageStat, ImageFilter


# ---------- WEIGHTS ----------
DEFAULT_WEIGHTS = {
    "alpha_text": 0.6,   # metin skor ağırlığı
    "beta_image": 0.4,   # görsel skor ağırlığı
    "money_coef": 0.12   # puan -> para katsayısı
}

def load_weights(path: str = "weights.json") -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            w = json.load(f)
    except FileNotFoundError:
        w = DEFAULT_WEIGHTS.copy()
        save_weights(w, path)

    # eksik anahtarlar varsa tamamla
    for k, v in DEFAULT_WEIGHTS.items():
        w.setdefault(k, v)
    return w

def save_weights(w: Dict, path: str = "weights.json") -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(w, f, ensure_ascii=False, indent=2)

def auto_update(path: str = "weights.json") -> Dict:
    """
    Dış dosyadaki ağırlıkları küçük oranlarla günceller (auto-update simülasyonu).
    """
    w = load_weights(path)
    # metin ağırlığını %2 artır, görüntüyü dengele (0.2–0.8 aralığını koru)
    w["alpha_text"] = float(max(0.2, min(0.8, w["alpha_text"] * 1.02)))
    w["beta_image"] = round(max(0.2, min(0.8, 1.0 - w["alpha_text"])), 2)
    # para katsayısını %1 artır (örnek)
    w["money_coef"] = float(max(0.05, min(0.5, w["money_coef"] * 1.01)))

    save_weights(w, path)
    return {"version": f"v{int(time.time())}", "weights": w}


# ---------- TEXT SCORE (heuristik) ----------
POS = {"harika", "mükemmel", "süper", "iyi", "güzel", "başarılı", "sevdim", "bayıldım"}
NEG = {"kötü", "berbat", "rezalet", "nefret", "çirkin", "sıkıntı"}

def score_text(txt: str) -> int:
    t = (txt or "").strip().lower()
    if not t:
        return 0

    words = t.split()
    n = len(words)
    uniq = len(set(words)) or 1

    # uzunluk puanı: 10–60 arası optimum
    if n < 10:
        s_len = n / 10
    elif n <= 60:
        s_len = 1.0
    else:
        s_len = max(0.0, 1.0 - (n - 60) / 120)

    s_div = min(1.0, uniq / (n or 1))  # çeşitlilik
    s_sent = max(0.0, min(1.0, (sum(w in POS for w in words) - sum(w in NEG for w in words) + 5) / 10))
    has_meta = 1.0 if ("@" in t or "#" in t) else 0.0

    raw = 0.35 * s_len + 0.35 * s_div + 0.25 * s_sent + 0.05 * has_meta
    return int(max(0.0, min(1.0, raw)) * 100)


# ---------- IMAGE SCORE (çok hafif kalite ölçümü) ----------
def score_image(img: Image.Image) -> int:
    """
    Basit kalite skoru: kontrast + keskinlik + parlaklık.
    0–100 arası skor döner.
    """
    g = img.convert("L")
    contrast = ImageStat.Stat(g).stddev[0] / 64.0     # ~0–4 normalize
    edges = g.filter(ImageFilter.FIND_EDGES)
    sharp = ImageStat.Stat(edges).mean[0] / 128.0     # ~0–2 normalize
    bright = ImageStat.Stat(g).mean[0] / 255.0        # 0–1
    raw = 0.5 * min(1.0, contrast) + 0.3 * min(1.0, sharp) + 0.2 * bright
    return int(max(0.0, min(1.0, raw)) * 100)


# ---------- MODERATION ----------
BAN = {"küfür", "ırkçı", "nefret", "şiddet", "hakaret"}

def moderate(txt: str, img_score: int) -> str:
    t = (txt or "").lower()
    if any(b in t for b in BAN):
        return "review"
    if img_score < 15:  # çok düşük kalite/uygunsuzluk şüphesi
        return "review"
    return "ok"


# ---------- MONEY ----------
def to_money(score: int, coef: float) -> float:
    return round(max(0, score) * float(coef), 2)


# ---------- FEED ----------
def rank_feed(items: List[Dict]) -> List[Dict]:
    safe = [it for it in items if it.get("mod") == "ok"]
    return sorted(safe, key=lambda x: (x.get("score", 0), x.get("ts", 0)), reverse=True)


# ---------- IMAGE -> VIDEO (MoviePy ile; güvenli import) ----------
def image_to_video(img: Image.Image, out_path: str = "demo.mp4", seconds: int = 10) -> str:
    """
    Tek görselden 10 sn'lik basit pan/zoom videosu üretir.
    MoviePy veya NumPy yoksa kullanıcıya yönlendirici mesajla hata verir.
    """
    # MoviePy'yi fonksiyon içinde import et (lazy import)
    try:
        from moviepy.editor import ImageClip
    except Exception as e:
        raise RuntimeError(
            "MoviePy bulunamadı. Kurulum için:\n"
            "  pip install moviepy imageio imageio-ffmpeg"
        ) from e

    # PIL Image -> NumPy array dönüşümü gerekir
    try:
        import numpy as np
    except Exception as e:
        raise RuntimeError(
            "NumPy bulunamadı. Kurulum için:\n"
            "  pip install numpy"
        ) from e

    # 1080x1920 dikey canvas oluştur, görseli ortala
    W, H = 1080, 1920
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    pic = img.convert("RGB")
    pic.thumbnail((W, H))
    x = (W - pic.width) // 2
    y = (H - pic.height) // 2
    canvas.paste(pic, (x, y))

    # MoviePy numpy array ister
    frame = np.array(canvas)
    clip = ImageClip(frame).set_duration(seconds)

    # basit zoom-in (Ken Burns)
    def zoom(t: float) -> float:
        return 1.0 + 0.05 * (t / seconds)

    animated = clip.resize(zoom)
    animated.write_videofile(
        out_path, fps=24, codec="libx264", audio=False, verbose=False, logger=None
    )
    return out_path
