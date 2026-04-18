import os
import re
import tempfile
from io import BytesIO

import streamlit as st
import speech_recognition as sr
from pypinyin import pinyin, Style
from gtts import gTTS


st.set_page_config(page_title="汉语语音纠错智能体", page_icon="🎤", layout="centered")

st.title("🎤 汉语语音纠错智能体 / Chinese Pronunciation Correction Assistant")
st.write("支持两种方式：直接录音 / 上传音频文件")
st.write("Supports two methods: record directly or upload an audio file")

# -----------------------------
# Helpers
# -----------------------------
INITIALS = [
    "zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l",
    "g", "k", "h", "j", "q", "x", "r", "z", "c", "s", "y", "w"
]


def chinese_to_pinyin_with_tone(text: str):
    result = pinyin(
        text,
        style=Style.TONE3,
        strict=False,
        neutral_tone_with_five=True
    )
    return [item[0] for item in result]


def split_tone(py: str):
    if py and py[-1].isdigit():
        return py[:-1], py[-1]
    return py, "5"


def split_initial_final(base: str):
    for ini in sorted(INITIALS, key=len, reverse=True):
        if base.startswith(ini):
            return ini, base[len(ini):]
    return "", base


def compare_pinyin(std_list, user_list):
    results = []
    max_len = max(len(std_list), len(user_list))

    for i in range(max_len):
        std_py = std_list[i] if i < len(std_list) else None
        usr_py = user_list[i] if i < len(user_list) else None

        if std_py is None:
            results.append({
                "index": i + 1,
                "status": "extra",
                "cn": f"第{i+1}个音节：学生多读了“{usr_py}”。",
                "en": f"Syllable {i+1}: the student added an extra syllable “{usr_py}”."
            })
            continue

        if usr_py is None:
            results.append({
                "index": i + 1,
                "status": "missing",
                "cn": f"第{i+1}个音节：学生漏读了，标准应为“{std_py}”。",
                "en": f"Syllable {i+1}: the student missed a syllable. The correct one should be “{std_py}”."
            })
            continue

        std_base, std_tone = split_tone(std_py)
        usr_base, usr_tone = split_tone(usr_py)

        std_ini, std_fin = split_initial_final(std_base)
        usr_ini, usr_fin = split_initial_final(usr_base)

        if std_py == usr_py:
            results.append({
                "index": i + 1,
                "status": "correct",
                "cn": f"第{i+1}个音节正确：{std_py}",
                "en": f"Syllable {i+1} is correct: {std_py}"
            })
            continue

        details_cn = []
        details_en = []

        if std_ini != usr_ini:
            details_cn.append(f"声母错误：应为“{std_ini}”，实际更接近“{usr_ini}”")
            details_en.append(f"Initial consonant error: expected “{std_ini}”, but got something closer to “{usr_ini}”")

        if std_fin != usr_fin:
            details_cn.append(f"韵母错误：应为“{std_fin}”，实际更接近“{usr_fin}”")
            details_en.append(f"Final error: expected “{std_fin}”, but got something closer to “{usr_fin}”")

        if std_tone != usr_tone:
            details_cn.append(f"声调错误：应为第{std_tone}声，实际更接近第{usr_tone}声")
            details_en.append(f"Tone error: expected tone {std_tone}, but it sounds closer to tone {usr_tone}")

        if not details_cn:
            details_cn.append(f"发音有偏差：标准“{std_py}”，学生“{usr_py}”")
            details_en.append(f"Pronunciation deviation: target “{std_py}”, student produced “{usr_py}”")

        results.append({
            "index": i + 1,
            "status": "incorrect",
            "target": std_py,
            "user": usr_py,
            "cn": f"第{i+1}个音节有误。标准：{std_py}；学生：{usr_py}。\n" + "；".join(details_cn),
            "en": f"Syllable {i+1} is incorrect. Target: {std_py}; Student: {usr_py}.\n" + "; ".join(details_en)
        })

    return results


def build_general_feedback(results):
    tone_err = 0
    initial_err = 0
    final_err = 0
    other_err = 0

    for r in results:
        if r["status"] != "incorrect":
            continue
        cn = r["cn"]
        if "声调错误" in cn:
            tone_err += 1
        if "声母错误" in cn:
            initial_err += 1
        if "韵母错误" in cn:
            final_err += 1
        if all(key not in cn for key in ["声调错误", "声母错误", "韵母错误"]):
            other_err += 1

    if tone_err == 0 and initial_err == 0 and final_err == 0 and other_err == 0:
        return {
            "cn": "整体发音很好。可以继续练习更长的句子，并注意语流自然度。",
            "en": "Overall pronunciation is good. You can move on to longer sentences and work on natural fluency."
        }

    parts_cn = []
    parts_en = []

    if tone_err:
        parts_cn.append("请重点练习声调，尤其注意升降变化。")
        parts_en.append("Please focus on tones, especially the rising and falling contour.")
    if initial_err:
        parts_cn.append("请注意声母发音部位，例如舌尖音、舌面音和送气对比。")
        parts_en.append("Please pay attention to initials, such as tongue position and aspirated vs. unaspirated sounds.")
    if final_err:
        parts_cn.append("请注意韵母口型和收音位置。")
        parts_en.append("Please pay attention to finals, including mouth shape and ending position.")
    if other_err:
        parts_cn.append("建议慢速跟读，一音节一音节地纠正。")
        parts_en.append("It is recommended to shadow slowly and correct pronunciation syllable by syllable.")

    return {
        "cn": " ".join(parts_cn),
        "en": " ".join(parts_en)
    }


def synthesize_standard_audio(text: str):
    try:
        tts = gTTS(text=text, lang="zh-CN")
        buffer = BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        return buffer
    except Exception:
        return None


def recognize_audio_file(path: str):
    recognizer = sr.Recognizer()
    with sr.AudioFile(path) as source:
        audio = recognizer.record(source)
    text = recognizer.recognize_google(audio, language="zh-CN")
    return text


def save_uploaded_or_recorded_audio_to_temp(uploaded_file):
    suffix = ".wav"
    file_name = getattr(uploaded_file, "name", "")
    if "." in file_name:
        suffix = os.path.splitext(file_name)[1].lower() or ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        return tmp.name


# -----------------------------
# UI
# -----------------------------
standard_text = st.text_input(
    "标准句子 / Target sentence",
    value="你好"
)

st.markdown("### 选择输入方式 / Choose input method")
mode = st.radio(
    "方式 / Method",
    ["🎙️ 直接录音 Record now", "📁 上传音频 Upload audio"],
    label_visibility="collapsed"
)

audio_path = None

if mode == "🎙️ 直接录音 Record now":
    audio_rec = st.audio_input("点击录音 / Click to record")
    if audio_rec is not None:
        audio_path = save_uploaded_or_recorded_audio_to_temp(audio_rec)
        st.audio(audio_path)

else:
    uploaded = st.file_uploader(
        "上传音频文件 / Upload an audio file",
        type=["wav", "mp3", "m4a", "ogg"]
    )
    if uploaded is not None:
        audio_path = save_uploaded_or_recorded_audio_to_temp(uploaded)
        st.audio(audio_path)

if st.button("开始分析 / Start analysis"):
    if not standard_text.strip():
        st.warning("请输入标准句子 / Please enter the target sentence.")
    elif not audio_path:
        st.warning("请先录音或上传音频 / Please record or upload audio first.")
    else:
        try:
            recognized_text = recognize_audio_file(audio_path)

            st.markdown("## 识别结果 / Recognition result")
            st.write(f"**中文 Chinese:** {recognized_text}")

            std_pinyin = chinese_to_pinyin_with_tone(standard_text)
            usr_pinyin = chinese_to_pinyin_with_tone(recognized_text)

            st.markdown("## 对比结果 / Comparison")
            st.write(f"**标准拼音 Target pinyin:** {std_pinyin}")
            st.write(f"**学生拼音 Student pinyin:** {usr_pinyin}")

            results = compare_pinyin(std_pinyin, usr_pinyin)

            st.markdown("## 纠错说明 / Correction details")
            for r in results:
                if r["status"] == "correct":
                    st.success(f"中文：{r['cn']}\n\nEnglish: {r['en']}")
                else:
                    st.error(f"中文：{r['cn']}\n\nEnglish: {r['en']}")

            feedback = build_general_feedback(results)

            st.markdown("## 总结建议 / Overall feedback")
            st.info(f"中文：{feedback['cn']}\n\nEnglish: {feedback['en']}")

            st.markdown("## 正确答案 / Correct answer")
            st.write(f"**中文 Chinese:** {standard_text}")
            st.write(f"**拼音 Pinyin:** {' '.join(std_pinyin)}")

            st.markdown("## 标准发音 / Standard pronunciation")
            tts_audio = synthesize_standard_audio(standard_text)
            if tts_audio is not None:
                st.audio(tts_audio, format="audio/mp3")
            else:
                st.warning("标准语音暂时无法生成，但文字和拼音已经显示。 / Standard audio could not be generated right now, but the text and pinyin are shown.")

        except sr.UnknownValueError:
            st.error("无法识别语音。请说得更清楚一些。 / Speech could not be recognized. Please speak more clearly.")
        except sr.RequestError:
            st.error("语音识别服务当前不可用。 / Speech recognition service is currently unavailable.")
        except Exception as e:
            st.error(f"发生错误 / Error: {e}")
