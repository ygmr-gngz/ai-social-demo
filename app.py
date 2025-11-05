import time
import streamlit as st 
from PIL import Image
# --- Pillow 10+ uyumluluk yamasi (moviepy icin) ---
# Image.ANTIALIAS kaldirildi; moviepy gibi kutuphaneler hala bunu kullanabiliyor.
if not hasattr(Image, "Resampling"):
    # Eski Pillow icin Resampling takma adi
    Image.Resampling = Image
# ANTIALIAS sabitini LANCZOS'a esitle
Image.ANTIALIAS = Image.Resampling.LANCZOS
# ---------------------------------------------------
from agents import (
    load_weights, auto_update, score_text, score_image,
    moderate, to_money, rank_feed, image_to_video
)

st.set_page_config(page_title="AI Social MVP", layout="wide")
st.title("AI Social – Basit Demo")
st.caption("Skor • Moderasyon • Auto-Update • Görselden Video")

# state
if "items" not in st.session_state:
    st.session_state["items"] = []
if "version" not in st.session_state:
    st.session_state.version = "v0.1"

w = load_weights()
st.sidebar.markdown(f"**Versiyon:** {st.session_state.version}")
with st.sidebar.expander("Ağırlıklar", expanded=False):
    st.json(w)

# inputlar
txt = st.text_area("Metin paylaş", height=120, placeholder="Bir gönderi yazın…")
img_file = st.file_uploader("Görsel yükle (opsiyonel)", type=["png","jpg","jpeg"])

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    if st.button("Analiz Et", use_container_width=True):
        s_text = score_text(txt)
        s_img = 0
        pil_img = None
        if img_file:
            pil_img = Image.open(img_file)
            s_img = score_image(pil_img)

        final_score = int(w["alpha_text"] * s_text + w["beta_image"] * s_img)
        mod = moderate(txt, s_img)
        money = to_money(final_score, w["money_coef"])

        st.success(f"AI Score: {final_score}  |  ₺ {money}  |  Moderasyon: {mod.upper()}")
        st.caption(f"(Text:{s_text} • Image:{s_img} • α={w['alpha_text']} • β={w['beta_image']})")

        st.session_state["items"].append({
            "text": txt or "",
            "score": final_score,
            "mod": mod,
            "ts": time.time(),
            "img": pil_img
        })

with col2:
    if st.button("Sistemi Güncelle (Auto-Update)", use_container_width=True):
        info = auto_update()
        st.session_state.version = info["version"]
        st.info(f"Yeni versiyon: {info['version']}")
        st.json(info["weights"], expanded=False)

with col3:
    if st.button("Görselden Video Üret", use_container_width=True):
        if not img_file:
            st.warning("Önce bir görsel yükleyin.")
        else:
            try:
                out = image_to_video(Image.open(img_file), out_path="demo.mp4", seconds=10)
                with open(out, "rb") as f:
                    st.download_button("Videoyu indir (MP4)", data=f,
                                       file_name="demo.mp4", mime="video/mp4")
            except RuntimeError as e:
                st.error(str(e))


st.divider()
st.subheader("Sonuçlar")
if st.session_state["items"]:
    st.dataframe([{
        "score": it["score"],
        "mod": it["mod"],
        "text": (it["text"][:80] + "...") if len(it["text"]) > 80 else it["text"]
    } 
    for it in reversed(st.session_state["items"][-50:])], use_container_width=True)
else:
    st.write("Henüz içerik yok.")

st.subheader("Benim Akışım (Feed)")
for it in rank_feed(st.session_state["items"])[:10]:
    st.write(f"**{it['score']}** — {it['text'][:100]}{'...' if len(it['text'])>100 else ''}")
