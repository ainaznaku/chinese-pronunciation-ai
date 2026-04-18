import tempfile
import streamlit as st
import speech_recognition as sr
from pypinyin import pinyin, Style

st.title("🎤 汉语语音纠错智能体")

standard = st.text_input("标准句子", "你好")

audio_file = st.file_uploader(
    "Загрузите аудио (.wav)", type=["wav"]
)

def get_pinyin(txt):
    return [x[0] for x in pinyin(txt, style=Style.TONE3)]

if audio_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(audio_file.read())
        path = f.name

    st.audio(path)

    if st.button("分析"):
        r = sr.Recognizer()

        with sr.AudioFile(path) as source:
            audio = r.record(source)

        text = r.recognize_google(audio, language="zh-CN")

        st.write("你说的是：", text)

        std_py = get_pinyin(standard)
        stu_py = get_pinyin(text)

        st.write("标准拼音：", std_py)
        st.write("你的拼音：", stu_py)

        for i in range(min(len(std_py), len(stu_py))):
            if std_py[i] == stu_py[i]:
                st.success(f"{std_py[i]} 正确")
            else:
                st.error(f"应该读 {std_py[i]}，你读成了 {stu_py[i]}")
