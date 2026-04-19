import os
import base64
import tempfile
import asyncio

import streamlit as st
import speech_recognition as sr
import edge_tts
from pypinyin import pinyin, Style

st.set_page_config(page_title="汉语语音纠错智能体", page_icon="🎤", layout="centered")

st.markdown("""
<style>
.block-container {max-width: 900px; padding-top: 1rem;}
.card {
    background:white;
    border-radius:20px;
    padding:18px;
    margin-bottom:16px;
    border:1px solid #eee;
    box-shadow:0 4px 12px rgba(0,0,0,0.06);
}
.score-box {
    text-align:center;
    background:#f4fff0;
    border:2px solid #d8f3c8;
}
.score {
    font-size:3rem;
    font-weight:900;
    color:#58cc02;
}
audio { width:100%; margin-top:10px; }
</style>
""", unsafe_allow_html=True)

st.title("🎤 汉语语音纠错智能体")
st.caption("Введите любую фразу, затем произнесите её")

INITIALS = [
    "zh","ch","sh","b","p","m","f","d","t","n","l",
    "g","k","h","j","q","x","r","z","c","s","y","w"
]

def pinyin_marks(text):
    return [x[0] for x in pinyin(text, style=Style.TONE, strict=False)]

def pinyin_numbers(text):
    return [x[0] for x in pinyin(
        text,
        style=Style.TONE3,
        strict=False,
        neutral_tone_with_five=True
    )]

def split_tone(py):
    if py and py[-1].isdigit():
        return py[:-1], py[-1]
    return py, "5"

def split_initial_final(base):
    for ini in sorted(INITIALS, key=len, reverse=True):
        if base.startswith(ini):
            return ini, base[len(ini):]
    return "", base

def compare(std_list, usr_list, std_marks, usr_marks):
    score = 100
    results = []

    max_len = max(len(std_list), len(usr_list))

    for i in range(max_len):
        std = std_list[i] if i < len(std_list) else None
        usr = usr_list[i] if i < len(usr_list) else None

        std_mark = std_marks[i] if i < len(std_marks) else ""
        usr_mark = usr_marks[i] if i < len(usr_marks) else ""

        if std is None:
            score -= 10
            results.append(("❌", f"多读了: {usr_mark}"))
            continue

        if usr is None:
            score -= 10
            results.append(("❌", f"漏读了: {std_mark}"))
            continue

        if std == usr:
            results.append(("✅", f"{std_mark} 正确"))
            continue

        std_base, std_tone = split_tone(std)
        usr_base, usr_tone = split_tone(usr)

        std_ini, std_fin = split_initial_final(std_base)
        usr_ini, usr_fin = split_initial_final(usr_base)

        msg = []

        if std_ini != usr_ini:
            score -= 20
            msg.append(f"声母应为 {std_ini}")

        if std_fin != usr_fin:
            score -= 20
            msg.append(f"韵母应为 {std_fin}")

        if std_tone != usr_tone:
            score -= 15
            msg.append(f"声调应为第{std_tone}声")

        results.append(("❌", f"{std_mark}: {'；'.join(msg)}"))

    return max(score, 0), results

def recognize_audio(path):
    r = sr.Recognizer()
    with sr.AudioFile(path) as source:
        audio = r.record(source)
    return r.recognize_google(audio, language="zh-CN")

async def generate_voice(text, path):
    communicate = edge_tts.Communicate(
        text=text,
        voice="zh-CN-YunxiNeural"
    )
    await communicate.save(path)

def create_audio_bytes(text):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    asyncio.run(generate_voice(text, tmp.name))
    with open(tmp.name, "rb") as f:
        return f.read()

def render_audio(audio_bytes):
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(
        f"""
        <audio controls>
            <source src="data:audio/mp3;base64,{b64}" type="audio/mpeg">
        </audio>
        """,
        unsafe_allow_html=True
    )

def save_audio(file):
    suffix = ".wav"
    if hasattr(file, "name") and "." in file.name:
        suffix = os.path.splitext(file.name)[1]

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.read())
        return tmp.name

target = st.text_input(
    "请输入要练习的词语或句子 / Enter a Chinese word or sentence",
    "你好"
)

if target:
    st.markdown(
        f"""
        <div class="card">
            <h2 style="text-align:center;">{target}</h2>
            <p style="text-align:center;color:gray;">
                {' '.join(pinyin_marks(target))}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

mode = st.radio(
    "选择方式 / Choose method",
    ["🎙️ Record voice", "📁 Upload file"],
    horizontal=True
)

audio_path = None

if mode == "🎙️ Record voice":
    audio_data = st.audio_input("点击录音 / Record")
    if audio_data:
        audio_path = save_audio(audio_data)
else:
    uploaded = st.file_uploader("Upload", type=["wav","mp3","m4a","ogg"])
    if uploaded:
        audio_path = save_audio(uploaded)

if st.button("开始分析 / Analyze", use_container_width=True):
    if not target:
        st.warning("请输入中文")
    elif not audio_path:
        st.warning("请先录音")
    else:
        try:
            spoken = recognize_audio(audio_path)

            std_num = pinyin_numbers(target)
            usr_num = pinyin_numbers(spoken)

            std_mark = pinyin_marks(target)
            usr_mark = pinyin_marks(spoken)

            score, results = compare(std_num, usr_num, std_mark, usr_mark)

            st.markdown(
                f"""
                <div class="card score-box">
                    <div class="score">{score}/100</div>
                    <div>Pronunciation Score</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.progress(score / 100)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("识别结果 / Recognition")
            st.write(f"正确句子: {target}")
            st.write(f"你说的是: {spoken}")
            st.write(f"正确拼音: {' '.join(std_mark)}")
            st.write(f"你的拼音: {' '.join(usr_mark)}")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("分析 / Analysis")
            for icon, text in results:
                if icon == "✅":
                    st.success(text)
                else:
                    st.error(text)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("正确发音 / Standard Pronunciation")
            voice_bytes = create_audio_bytes(target)
            render_audio(voice_bytes)
            st.markdown('</div>', unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Error: {e}")
