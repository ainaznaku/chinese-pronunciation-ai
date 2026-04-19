import os
import base64
import tempfile
import asyncio

import streamlit as st
import speech_recognition as sr
import edge_tts
from pypinyin import pinyin, Style

st.set_page_config(
    page_title="汉语语音识别与示范",
    page_icon="🎤",
    layout="centered"
)

st.markdown("""
<style>
.block-container {
    max-width: 900px;
    padding-top: 1rem;
    padding-bottom: 2rem;
}
.title {
    text-align: center;
    font-size: 2.4rem;
    font-weight: 800;
    margin-bottom: 0.3rem;
}
.subtitle {
    text-align: center;
    color: #666;
    margin-bottom: 1.2rem;
}
.card {
    background: white;
    border-radius: 20px;
    padding: 18px;
    margin-bottom: 16px;
    border: 1px solid #eee;
    box-shadow: 0 4px 12px rgba(0,0,0,0.06);
}
.section-title {
    font-size: 1.2rem;
    font-weight: 700;
    margin-bottom: 0.6rem;
}
.big-text {
    text-align: center;
    font-size: 1.8rem;
    font-weight: 800;
}
.pinyin-text {
    text-align: center;
    color: gray;
    font-size: 1.15rem;
    margin-top: 8px;
}
audio {
    width: 100%;
    margin-top: 10px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">🎤 汉语语音识别与示范</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Free Speaking Mode • Speak any Chinese word or sentence</div>',
    unsafe_allow_html=True
)

if "recognized_text" not in st.session_state:
    st.session_state.recognized_text = ""
if "recognized_pinyin" not in st.session_state:
    st.session_state.recognized_pinyin = []
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False


def pinyin_marks(text: str):
    return [x[0] for x in pinyin(text, style=Style.TONE, strict=False)]


def recognize_audio(path: str):
    recognizer = sr.Recognizer()
    with sr.AudioFile(path) as source:
        audio = recognizer.record(source)
    return recognizer.recognize_google(audio, language="zh-CN")


async def generate_voice(text: str, path: str):
    communicate = edge_tts.Communicate(
        text=text,
        voice="zh-CN-YunxiNeural"
    )
    await communicate.save(path)


def create_standard_audio_bytes(text: str):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp.close()
    asyncio.run(generate_voice(text, temp.name))
    with open(temp.name, "rb") as f:
        data = f.read()
    return data


def render_audio_player(audio_bytes: bytes):
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
    audio_html = f"""
        <audio controls>
            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mpeg">
            Your browser does not support audio playback.
        </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)


def save_audio(file):
    suffix = ".wav"
    if hasattr(file, "name") and "." in file.name:
        suffix = os.path.splitext(file.name)[1].lower() or ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.read())
        return tmp.name


def reset_state():
    st.session_state.recognized_text = ""
    st.session_state.recognized_pinyin = []
    st.session_state.analysis_done = False


col1, col2 = st.columns(2)

with col1:
    if st.button("🔄 Clear", use_container_width=True):
        reset_state()
        st.rerun()

with col2:
    mode = st.selectbox(
        "Input Mode",
        ["🎙️ Record voice", "📁 Upload file"]
    )

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">请说任意汉语词语或句子 / Say any Chinese word or sentence</div>', unsafe_allow_html=True)

audio_path = None

if mode == "🎙️ Record voice":
    audio_data = st.audio_input("点击录音 / Record your pronunciation")
    if audio_data:
        audio_path = save_audio(audio_data)
else:
    uploaded = st.file_uploader(
        "Upload audio file",
        type=["wav", "mp3", "m4a", "ogg"]
    )
    if uploaded:
        audio_path = save_audio(uploaded)

st.markdown('</div>', unsafe_allow_html=True)

if st.button("开始识别 / Start Recognition", use_container_width=True):
    if not audio_path:
        st.warning("请先录音或上传音频 / Please record or upload audio first")
    else:
        try:
            spoken = recognize_audio(audio_path)
            spoken_pinyin = pinyin_marks(spoken)

            st.session_state.recognized_text = spoken
            st.session_state.recognized_pinyin = spoken_pinyin
            st.session_state.analysis_done = True

        except sr.UnknownValueError:
            st.error("无法识别语音，请说得更清楚一些。 / Speech could not be recognized. Please speak more clearly.")
        except sr.RequestError:
            st.error("语音识别服务当前不可用。 / Speech recognition service is currently unavailable.")
        except Exception as e:
            st.error(f"Error: {e}")

if st.session_state.analysis_done:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("识别结果 / Recognition Result")
    st.markdown("### 你说的是 / You said")
    st.markdown(f"<div class='big-text'>{st.session_state.recognized_text}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='pinyin-text'>{' '.join(st.session_state.recognized_pinyin)}</div>",
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("正确发音示范 / Standard Pronunciation Demo")
    st.write(f"**中文:** {st.session_state.recognized_text}")
    st.write(f"**拼音:** {' '.join(st.session_state.recognized_pinyin)}")

    try:
        voice_bytes = create_standard_audio_bytes(st.session_state.recognized_text)
        render_audio_player(voice_bytes)
    except Exception as e:
        st.warning(f"标准发音暂时不可用 / Standard audio unavailable: {e}")

    st.markdown('</div>', unsafe_allow_html=True)
