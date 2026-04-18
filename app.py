import streamlit as st
from pypinyin import pinyin, Style

st.set_page_config(page_title="汉语语音纠错智能体")

st.title("汉语语音纠错智能体")

standard = st.text_input("标准文本", "你好")
student = st.text_input("学生读音（直接输入中文）", "你号")

def get_pinyin(text):
    result = pinyin(text, style=Style.TONE3)
    return [x[0] for x in result]

if st.button("开始分析"):
    std_py = get_pinyin(standard)
    stu_py = get_pinyin(student)

    st.write("标准拼音：", std_py)
    st.write("学生拼音：", stu_py)

    for i in range(min(len(std_py), len(stu_py))):
        if std_py[i] == stu_py[i]:
            st.success(f"第{i+1}个音节正确：{std_py[i]}")
        else:
            st.error(
                f"第{i+1}个音节错误：标准 {std_py[i]}，学生 {stu_py[i]}"
            )
