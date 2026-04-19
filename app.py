import os
import base64
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
    font-size: 1.8rem;
    font-weight: 800;
}
.lesson-pinyin {
    text-align: center;
    color: gray;
    font-size: 1.15rem;
    margin-top: 8px;
}
.section-title {
    font-size: 1.2rem;
    font-weight: 700;
    margin-bottom: 0.6rem;
}
audio {
    width: 100%;
    margin-top: 10px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">🎤 汉语语音纠错智能体</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Duolingo Style • Record or Upload • Chinese/English Feedback • Standard Chinese Voice</div>',
    unsafe_allow_html=True
)

LESSONS = [
    "你好",
    "谢谢",
    "不客气",
    "再见",
    "老师好",
    "同学们好",
    "你好吗",
    "我很好",
    "你叫什么名字",
    "我叫安娜",
    "你是哪国人",
    "我是哈萨克斯坦人",
    "你会说汉语吗",
    "我会说一点汉语",
    "请再说一遍",
    "请慢一点",
    "我听不懂",
    "我明白了",
    "今天星期几",
    "今天星期一",
    "现在几点",
    "现在八点半",
    "你去哪儿",
    "我去学校",
    "你喜欢什么",
    "我喜欢学汉语",
    "你喜欢喝茶吗",
    "我喜欢喝咖啡",
    "你家有几口人",
    "我家有四口人",
    "今天天气怎么样",
    "今天天气很好",
    "我想买这个",
    "这个多少钱",
    "太贵了",
    "便宜一点吧",
    "我饿了",
    "我渴了",
    "我要一杯水",
    "请给我菜单",
    "洗手间在哪儿",
    "我可以坐这里吗",
    "欢迎来到中国",
    "祝你生日快乐",
    "新年快乐",
    "一路平安",
    "没关系",
    "对不起",
    "没问题",
    "请进",
    "请坐",
    "你真漂亮",
    "你真帅",
    "我很高兴认识你",
    "明天见",
    "晚安",
    "早上好",
    "中午好",
    "晚上好"
]

INITIALS = [
    "zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l",
    "g", "k", "h", "j", "q", "x", "r", "z", "c", "s", "y", "w"
]

if "current_index" not in st.session_state:
    st.session_state.current_index = 0
if "last_score" not in st.session_state:
    st.session_state.last_score = None
if "last_spoken" not in st.session_state:
    st.session_state.last_spoken = ""
if "last_results" not in st.session_state:
    st.session_state.last_results = []
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False

target = LESSONS[st.session_state.current_index]


def pinyin_marks(text: str):
    return [x[0] for x in pinyin(text, style=Style.TONE, strict=False)]


def pinyin_numbers(text: str):
    return [x[0] for x in pinyin(
        text,
        style=Style.TONE3,
        strict=False,
        neutral_tone_with_five=True
    )]


def split_tone(py: str):
    if py and py[-1].isdigit():
        return py[:-1], py[-1]
    return py, "5"


def split_initial_final(base: str):
    for ini in sorted(INITIALS, key=len, reverse=True):
        if base.startswith(ini):
            return ini, base[len(ini):]
    return "", base


def compare(std_list, user_list, std_marks, user_marks):
    results = []
    score = 100
    max_len = max(len(std_list), len(user_list))

    for i in range(max_len):
        std = std_list[i] if i < len(std_list) else None
        usr = user_list[i] if i < len(user_list) else None
        std_mark = std_marks[i] if i < len(std_marks) else ""
        usr_mark = user_marks[i] if i < len(user_marks) else ""

        if std is None:
            score -= 12
            results.append({
                "ok": False,
                "cn": f"第{i+1}个音节多读了：{usr_mark or usr}",
                "en": f"Syllable {i+1}: extra syllable {usr_mark or usr}"
            })
            continue

        if usr is None:
            score -= 12
            results.append({
                "ok": False,
                "cn": f"第{i+1}个音节漏读了，应该是：{std_mark or std}",
                "en": f"Syllable {i+1}: missing syllable, it should be: {std_mark or std}"
            })
            continue

        std_base, std_tone = split_tone(std)
        usr_base, usr_tone = split_tone(usr)

        std_ini, std_fin = split_initial_final(std_base)
        usr_ini, usr_fin = split_initial_final(usr_base)

        if std == usr:
            results.append({
                "ok": True,
                "cn": f"第{i+1}个音节正确：{std_mark}",
                "en": f"Syllable {i+1} correct: {std_mark}"
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

            if not msg_cn:
                msg_cn.append(f"发音不够准确，标准是 {std_mark}，你读成了 {usr_mark}")
                msg_en.append(f"Pronunciation is not accurate. Target is {std_mark}, but you said {usr_mark}")
                score -= 10

            results.append({
                "ok": False,
                "cn": "；".join(msg_cn),
                "en": "; ".join(msg_en)
            })

    return max(score, 0), results


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


def score_comment(score: int):
    if score >= 90:
        return (
            "你的发音非常好，接近标准汉语。",
            "Your pronunciation is excellent and very close to standard Mandarin."
        )
    if score >= 75:
        return (
            "整体不错，还有一些小问题需要继续练习。",
            "Good overall, but there are still a few points to improve."
        )
    if score >= 60:
        return (
            "基础可以，需要重点练习声调和音节。",
            "The foundation is okay, but you should focus on tones and syllables."
        )
    return (
        "需要继续练习。建议放慢速度，一音节一音节模仿。",
        "More practice is needed. Try slowing down and imitating one syllable at a time."
    )


def reset_result_state():
    st.session_state.last_score = None
    st.session_state.last_spoken = ""
    st.session_state.last_results = []
    st.session_state.analysis_done = False


progress_value = (st.session_state.current_index + 1) / len(LESSONS)
st.progress(progress_value)
st.caption(f"Progress: {st.session_state.current_index + 1} / {len(LESSONS)}")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("⬅️ Previous", use_container_width=True):
        if st.session_state.current_index > 0:
            st.session_state.current_index -= 1
            reset_result_state()
            st.rerun()

with col2:
    if st.button("🔄 Restart", use_container_width=True):
        st.session_state.current_index = 0
        reset_result_state()
        st.rerun()

with col3:
    if st.button("➡️ Next", use_container_width=True):
        if st.session_state.current_index < len(LESSONS) - 1:
            st.session_state.current_index += 1
            reset_result_state()
            st.rerun()

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

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">选择方式 / Choose Method / Выберите способ</div>', unsafe_allow_html=True)

mode = st.radio(
    "选择方式 / Choose method",
    ["🎙️ Record voice", "📁 Upload file"],
    horizontal=True,
    label_visibility="collapsed"
)

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

if st.button("开始分析 / Analyze", use_container_width=True):
    if not audio_path:
        st.warning("请先录音或上传音频 / Please record or upload audio first")
    else:
        try:
            spoken = recognize_audio(audio_path)

            target_nums = pinyin_numbers(target)
            spoken_nums = pinyin_numbers(spoken)

            target_marks = pinyin_marks(target)
            spoken_marks = pinyin_marks(spoken)

            score, results = compare(target_nums, spoken_nums, target_marks, spoken_marks)

            st.session_state.last_score = score
            st.session_state.last_spoken = spoken
            st.session_state.last_results = results
            st.session_state.analysis_done = True

        except sr.UnknownValueError:
            st.error("无法识别语音，请说得更清楚一些。 / Speech could not be recognized. Please speak more clearly.")
        except sr.RequestError:
            st.error("语音识别服务当前不可用。 / Speech recognition service is currently unavailable.")
        except Exception as e:
            st.error(f"Error: {e}")

if st.session_state.analysis_done:
    target_marks = pinyin_marks(target)
    spoken_marks = pinyin_marks(st.session_state.last_spoken)
    cn_comment, en_comment = score_comment(st.session_state.last_score)

    st.markdown(
        f"""
        <div class="card score-box">
            <div class="score">{st.session_state.last_score}/100</div>
            <div>Pronunciation Score / 发音得分</div>
            <div style="margin-top:10px;">中文：{cn_comment}</div>
            <div style="margin-top:6px;">English: {en_comment}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.progress(st.session_state.last_score / 100)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("识别结果 / Recognition")
    st.markdown("### 正确句子 / Correct sentence")
    st.markdown(f"<h2>{target}</h2>", unsafe_allow_html=True)

    st.markdown("### 你说的是 / You said")
    st.markdown(f"<h2>{st.session_state.last_spoken}</h2>", unsafe_allow_html=True)

    st.write(f"**正确拼音 / Correct pinyin:** {' '.join(target_marks)}")
    st.write(f"**你的拼音 / Your pinyin:** {' '.join(spoken_marks)}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("纠错 / Correction")
    for item in st.session_state.last_results:
        if item["ok"]:
            st.success(f"中文：{item['cn']}\n\nEnglish: {item['en']}")
        else:
            st.error(f"中文：{item['cn']}\n\nEnglish: {item['en']}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("正确发音 / Standard Pronunciation")
    st.write(f"**中文:** {target}")
    st.write(f"**拼音:** {' '.join(target_marks)}")

    try:
        voice_bytes = create_standard_audio_bytes(target)
        render_audio_player(voice_bytes)
    except Exception as e:
        st.warning(f"标准发音暂时不可用 / Standard audio unavailable: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.current_index < len(LESSONS) - 1:
        if st.button("✅ 下一题 / Next Question", use_container_width=True):
            st.session_state.current_index += 1
            reset_result_state()
            st.rerun()
    else:
        st.success("🎉 全部完成！ / All lessons completed!")
