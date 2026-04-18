import os
import tempfile
import asyncio

import streamlit as st
import speech_recognition as sr
import edge_tts
from pypinyin import pinyin, Style

st.set_page_config(
    page_title="汉语语音纠错智能体",
    page_icon="🎤",
    layout="centered"
)

# ---------- Style ----------
st.markdown("""
<style>
.block-container {
    max-width: 850px;
    padding-top: 1rem;
}
.title {
    text-align: center;
    font-size: 2.3rem;
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
.score-box {
    text-align: center;
    background: #f4fff0;
    border: 2px solid #d8f3c8;
}
.score {
    font-size: 3rem;
    font-weight: 900;
    color: #58cc02;
}
.lesson-title {
    text-align: center;
    font-size: 1.5rem;
    font-weight: 800;
}
.lesson-pinyin {
    text-align: center;
    color: gray;
    font-size: 1.1rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">🎤 汉语语音纠错智能体</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Chinese Pronunciation Coach • Duolingo Style • HSK Voice</div>',
    unsafe_allow_html=True
)

# ---------- Lesson List ----------
LESSONS = [
    "你好",
    "谢谢",
    "老师好",
    "我叫安娜",
    "你好吗",
    "我喜欢学汉语",
    "今天星期几",
    "请再说一遍"
]

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

target = LESSONS[st.session_state.current_index]

# ---------- Helpers ----------
INITIALS = [
    "zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l",
    "g", "k", "h", "j", "q", "x", "r", "z", "c", "s", "y", "w"
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


def compare(std_list, user_list):
    results = []
    score = 100

    max_len = max(len(std_list), len(user_list))

    for i in range(max_len):
        std = std_list[i] if i < len(std_list) else None
        usr = user_list[i] if i < len(user_list) else None

        if std is None or usr is None:
            score -= 12
            results.append({
                "ok": False,
                "cn": f"第{i+1}个音节有缺失或多余。",
                "en": f"Syllable {i+1} is missing or extra."
            })
            continue

        std_base, std_tone = split_tone(std)
        usr_base, usr_tone = split_tone(usr)

        std_ini, std_fin = split_initial_final(std_base)
        usr_ini, usr_fin = split_initial_final(usr_base)

        if std == usr:
            results.append({
                "ok": True,
                "cn": f"第{i+1}个音节正确：{std}",
                "en": f"Syllable {i+1} correct: {std}"
            })
        else:
            msg_cn = []
            msg_en = []

            if std_ini != usr_ini:
                msg_cn.append(f"声母应为 {std_ini}，你读成了 {usr_ini}")
                msg_en.append(f"Initial should be {std_ini}, but you said {usr_ini}")
                score -= 20

            if std_fin != usr_fin:
                msg_cn.append(f"韵母应为 {std_fin}，你读成了 {usr_fin}")
                msg_en.append(f"Final should be {std_fin}, but you said {usr_fin}")
                score -= 20

            if std_tone != usr_tone:
                msg_cn.append(f"声调应为第{std_tone}声，你读成了第{usr_tone}声")
                msg_en.append(f"Tone should be {std_tone}, but you pronounced tone {usr_tone}")
                score -= 15

            results.append({
                "ok": False,
                "cn": "；".join(msg_cn),
                "en": "; ".join(msg_en)
            })

    return max(score, 0), results


def recognize_audio(path):
    recognizer = sr.Recognizer()
    with sr.AudioFile(path) as source:
        audio = recognizer.record(source)
    return recognizer.recognize_google(audio, language="zh-CN")


async def generate_voice(text, path):
    communicate = edge_tts.Communicate(
        text=text,
        voice="zh-CN-XiaoxiaoNeural"
    )
    await communicate.save(path)


def create_standard_audio(text):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp.close()
    asyncio.run(generate_voice(text, temp.name))
    return temp.name


def save_audio(file):
    suffix = ".wav"
    if hasattr(file, "name") and "." in file.name:
        suffix = os.path.splitext(file.name)[1]

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.read())
        return tmp.name


# ---------- Task Card ----------
st.markdown(
    f"""
    <div class="card">
        <div class="lesson-title">
            第 {st.session_state.current_index + 1} 题 / Question {st.session_state.current_index + 1}
        </div>
        <br>
        <div class="lesson-title">{target}</div>
        <div class="lesson-pinyin">{' '.join(pinyin_marks(target))}</div>
    </div>
    """,
    unsafe_allow_html=True
)

# ---------- Audio Input ----------
st.markdown('<div class="card">', unsafe_allow_html=True)

mode = st.radio(
    "选择方式 / Choose method",
    ["🎙️ Record voice", "📁 Upload file"],
    horizontal=True
)

audio_path = None

if mode == "🎙️ Record voice":
    audio_data = st.audio_input("点击录音 / Record your pronunciation")
    if audio_data:
        audio_path = save_audio(audio_data)
        st.audio(audio_path)

else:
    uploaded = st.file_uploader(
        "Upload audio file",
        type=["wav", "mp3", "m4a", "ogg"]
    )
    if uploaded:
        audio_path = save_audio(uploaded)
        st.audio(audio_path)

st.markdown('</div>', unsafe_allow_html=True)

# ---------- Analyze ----------
if st.button("开始分析 / Analyze", use_container_width=True):
    if not audio_path:
        st.warning("请先录音或上传音频 / Please record or upload audio first")
    else:
        try:
            spoken = recognize_audio(audio_path)

            target_marks = pinyin_marks(target)
            spoken_marks = pinyin_marks(spoken)

            target_nums = pinyin_numbers(target)
            spoken_nums = pinyin_numbers(spoken)

            score, results = compare(target_nums, spoken_nums)

            st.markdown(
                f"""
                <div class="card score-box">
                    <div class="score">{score}/100</div>
                    <div>Pronunciation Score / 发音得分</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.progress(score / 100)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("识别结果 / Recognition")
            st.write(f"**你说的是 / You said:** {spoken}")
            st.write(f"**正确拼音 / Correct pinyin:** {' '.join(target_marks)}")
            st.write(f"**你的拼音 / Your pinyin:** {' '.join(spoken_marks)}")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("纠错 / Correction")

            for item in results:
                if item["ok"]:
                    st.success(f"中文：{item['cn']}\n\nEnglish: {item['en']}")
                else:
                    st.error(f"中文：{item['cn']}\n\nEnglish: {item['en']}")

            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("标准发音 / Standard Pronunciation")
            st.write(f"**中文:** {target}")
            st.write(f"**拼音:** {' '.join(target_marks)}")

            voice_file = create_standard_audio(target)
            st.audio(voice_file, format="audio/mp3")

            st.markdown('</div>', unsafe_allow_html=True)

            # ---------- Next Lesson ----------
            if st.session_state.current_index < len(LESSONS) - 1:
                if st.button("➡️ 下一题 / Next Question", use_container_width=True):
                    st.session_state.current_index += 1
                    st.rerun()
            else:
                st.success("🎉 全部完成！ / All lessons completed!")

        except Exception as e:
            st.error(f"Error: {e}")
