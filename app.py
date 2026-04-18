import os
import tempfile
from io import BytesIO

import streamlit as st
import speech_recognition as sr
from pypinyin import pinyin, Style
from gtts import gTTS


st.set_page_config(
    page_title="汉语语音纠错智能体",
    page_icon="🎤",
    layout="centered"
)

# -----------------------------
# Style: Duolingo-like
# -----------------------------
st.markdown("""
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 820px;
}
.main-title {
    text-align: center;
    font-size: 2.1rem;
    font-weight: 800;
    margin-bottom: 0.3rem;
}
.sub-title {
    text-align: center;
    font-size: 1rem;
    color: #666;
    margin-bottom: 1.2rem;
}
.duo-card {
    background: white;
    border-radius: 18px;
    padding: 18px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.08);
    margin-bottom: 16px;
    border: 1px solid #f0f0f0;
}
.score-box {
    text-align: center;
    padding: 20px;
    border-radius: 20px;
    background: #f7fff2;
    border: 2px solid #d8f3c8;
}
.score-number {
    font-size: 3rem;
    font-weight: 900;
    color: #58cc02;
}
.small-label {
    font-size: 0.95rem;
    color: #666;
}
.good-chip {
    display: inline-block;
    background: #e9fbe0;
    color: #247a00;
    padding: 6px 12px;
    border-radius: 999px;
    font-weight: 700;
    margin-top: 8px;
}
.bad-chip {
    display: inline-block;
    background: #ffe8e8;
    color: #b42318;
    padding: 6px 12px;
    border-radius: 999px;
    font-weight: 700;
    margin-top: 8px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🎤 汉语语音纠错智能体</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Russian + Chinese + English interface | Pinyin with tone marks | Score out of 100</div>',
    unsafe_allow_html=True
)

INITIALS = [
    "zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l",
    "g", "k", "h", "j", "q", "x", "r", "z", "c", "s", "y", "w"
]


def chinese_to_pinyin_marks(text: str):
    result = pinyin(text, style=Style.TONE, strict=False)
    return [item[0] for item in result]


def chinese_to_pinyin_numbers(text: str):
    result = pinyin(text, style=Style.TONE3, strict=False, neutral_tone_with_five=True)
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
                "cn": f"学生多读了一个音节：{usr_py}",
                "en": f"The student added an extra syllable: {usr_py}",
                "deduction": 12
            })
            continue

        if usr_py is None:
            results.append({
                "index": i + 1,
                "status": "missing",
                "cn": f"学生漏读了一个音节，标准应为：{std_py}",
                "en": f"The student missed a syllable. The correct one is: {std_py}",
                "deduction": 12
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
                "en": f"Syllable {i+1} is correct: {std_py}",
                "deduction": 0
            })
            continue

        details_cn = []
        details_en = []
        deduction = 0

        if std_ini != usr_ini:
            details_cn.append(f"声母错误：应为“{std_ini}”，实际更接近“{usr_ini}”")
            details_en.append(f"Initial error: expected “{std_ini}”, but heard something closer to “{usr_ini}”")
            deduction += 20

        if std_fin != usr_fin:
            details_cn.append(f"韵母错误：应为“{std_fin}”，实际更接近“{usr_fin}”")
            details_en.append(f"Final error: expected “{std_fin}”, but heard something closer to “{usr_fin}”")
            deduction += 20

        if std_tone != usr_tone:
            details_cn.append(f"声调错误：应为第{std_tone}声，实际更接近第{usr_tone}声")
            details_en.append(f"Tone error: expected tone {std_tone}, but it sounds closer to tone {usr_tone}")
            deduction += 15

        if not details_cn:
            details_cn.append(f"发音有偏差：标准“{std_py}”，学生“{usr_py}”")
            details_en.append(f"Pronunciation deviation: target “{std_py}”, student produced “{usr_py}”")
            deduction += 15

        results.append({
            "index": i + 1,
            "status": "incorrect",
            "target": std_py,
            "user": usr_py,
            "cn": "；".join(details_cn),
            "en": "; ".join(details_en),
            "deduction": deduction
        })

    return results


def calculate_score(results):
    score = 100
    for r in results:
        score -= r.get("deduction", 0)
    return max(0, min(100, score))


def score_comment(score):
    if score >= 90:
        return (
            "发音非常好，接近标准。",
            "Excellent pronunciation, very close to the standard."
        )
    if score >= 75:
        return (
            "整体不错，还有一些小问题需要练习。",
            "Good overall, but there are still some points to improve."
        )
    if score >= 60:
        return (
            "基础可以，需要重点练习声调和音节。",
            "The foundation is okay, but tones and syllables need more practice."
        )
    return (
        "需要继续练习。建议放慢速度，一音节一音节模仿。",
        "More practice is needed. Try slowing down and imitating one syllable at a time."
    )


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
    return recognizer.recognize_google(audio, language="zh-CN")


def save_audio_to_temp(uploaded_file):
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
with st.container():
    st.markdown('<div class="duo-card">', unsafe_allow_html=True)
    standard_text = st.text_input(
        "标准句子 / Target sentence / Эталонная фраза",
        value="你好"
    )

    mode = st.radio(
        "选择方式 / Choose method / Выберите способ",
        ["🎙️ 直接录音 Record now", "📁 上传音频 Upload audio"],
        horizontal=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

audio_path = None

with st.container():
    st.markdown('<div class="duo-card">', unsafe_allow_html=True)
    if mode == "🎙️ 直接录音 Record now":
        audio_rec = st.audio_input("点击录音 / Click to record / Нажмите для записи")
        if audio_rec is not None:
            audio_path = save_audio_to_temp(audio_rec)
            st.audio(audio_path)
    else:
        uploaded = st.file_uploader(
            "上传音频 / Upload audio / Загрузите аудио",
            type=["wav", "mp3", "m4a", "ogg"]
        )
        if uploaded is not None:
            audio_path = save_audio_to_temp(uploaded)
            st.audio(audio_path)
    st.markdown('</div>', unsafe_allow_html=True)

if st.button("开始分析 / Start analysis / Начать анализ", use_container_width=True):
    if not standard_text.strip():
        st.warning("请输入标准句子 / Please enter the target sentence / Введите эталонную фразу")
    elif not audio_path:
        st.warning("请先录音或上传音频 / Please record or upload audio first / Сначала запишите или загрузите аудио")
    else:
        try:
            recognized_text = recognize_audio_file(audio_path)

            std_pinyin_marks = chinese_to_pinyin_marks(standard_text)
            usr_pinyin_marks = chinese_to_pinyin_marks(recognized_text)

            std_pinyin_nums = chinese_to_pinyin_numbers(standard_text)
            usr_pinyin_nums = chinese_to_pinyin_numbers(recognized_text)

            results = compare_pinyin(std_pinyin_nums, usr_pinyin_nums)
            score = calculate_score(results)
            cn_comment, en_comment = score_comment(score)

            st.markdown('<div class="duo-card score-box">', unsafe_allow_html=True)
            st.markdown(f'<div class="score-number">{score}/100</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="small-label">中文：{cn_comment}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="small-label">English: {en_comment}</div>', unsafe_allow_html=True)
            st.progress(score / 100)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="duo-card">', unsafe_allow_html=True)
            st.subheader("识别结果 / Recognition / Что сказано")
            st.write(f"**中文 Chinese:** {recognized_text}")
            st.write(f"**标准拼音 Target pinyin:** {' '.join(std_pinyin_marks)}")
            st.write(f"**你的拼音 Your pinyin:** {' '.join(usr_pinyin_marks)}")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="duo-card">', unsafe_allow_html=True)
            st.subheader("逐项纠错 / Corrections / Исправления")
            for r in results:
                if r["status"] == "correct":
                    st.markdown(
                        f"""
                        <div class="good-chip">Correct</div>
                        """,
                        unsafe_allow_html=True
                    )
                    st.success(f"中文：{r['cn']}\n\nEnglish: {r['en']}")
                else:
                    st.markdown(
                        f"""
                        <div class="bad-chip">Needs practice</div>
                        """,
                        unsafe_allow_html=True
                    )
                    st.error(f"中文：{r['cn']}\n\nEnglish: {r['en']}")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="duo-card">', unsafe_allow_html=True)
            st.subheader("正确答案 / Correct answer / Правильный ответ")
            st.write(f"**中文 Chinese:** {standard_text}")
            st.write(f"**拼音 Pinyin:** {' '.join(std_pinyin_marks)}")
            tts_audio = synthesize_standard_audio(standard_text)
            if tts_audio is not None:
                st.audio(tts_audio, format="audio/mp3")
            else:
                st.info("标准发音暂时无法生成 / Standard audio is unavailable right now")
            st.markdown('</div>', unsafe_allow_html=True)

        except sr.UnknownValueError:
            st.error("无法识别语音。请说得更清楚一些。 / Speech could not be recognized. Please speak more clearly.")
        except sr.RequestError:
            st.error("语音识别服务当前不可用。 / Speech recognition service is currently unavailable.")
        except Exception as e:
            st.error(f"发生错误 / Error: {e}")
