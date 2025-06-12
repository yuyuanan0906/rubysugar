# Streamlit Web App for Food Carb & Insulin Record System (Google Sheets版)
# ✅ 使用 gspread + Google Sheets API

import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

# === 初始化 Google Sheets 連線 ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    st.secrets["gcp_service_account"], scope
)
gc = gspread.authorize(credentials)

# === Google Sheets 連結 ===
FOOD_SHEET_ID = "1vD-vEszbCPVeVKjKEd0VGBvLak4a12gbiowNvnB0Ik8"
RECORD_SHEET_ID = "1vIL-n9ARfJy7GkBc7EWC3XDizgJU6e3BYes7N6AJWU0"

sheet_food = gc.open_by_key(FOOD_SHEET_ID).worksheet("食物資料")
sheet_food_records = gc.open_by_key(RECORD_SHEET_ID).worksheet("食物記錄")
sheet_insulin = gc.open_by_key(RECORD_SHEET_ID).worksheet("血糖與胰島素紀錄表")

st.set_page_config(page_title="食物碳水與胰島素系統", layout="wide")

# === Session State 初始化 ===
if "calc_results" not in st.session_state:
    st.session_state.calc_results = []

# === 查詢相似食物 ===
def find_similar_foods(keyword):
    data = sheet_food.get_all_values()[1:]
    return [row for row in data if keyword in row[0]]

# === 分頁設定 ===
tabs = st.tabs(["🍱 食物管理", "📊 碳水計算", "💉 胰島素紀錄"])

# === 食物管理 ===
with tabs[0]:
    st.header("🍱 食物管理")
    with st.form("add_food_form"):
        name = st.text_input("食物名稱")
        unit = st.selectbox("單位", ["克(g)", "毫升(ml)"])
        carb = st.text_input("每單位碳水化合物含量 (g)")
        note = st.text_input("備註")
        submitted = st.form_submit_button("✅ 新增 / 覆蓋")
        if submitted:
            if not name or not unit or not carb:
                st.warning("請填寫完整資訊")
            else:
                try:
                    carb_val = float(carb.replace(",", "."))
                    data = sheet_food.get_all_values()
                    updated = False
                    for i, row in enumerate(data[1:], start=2):
                        if row[0] == name:
                            sheet_food.update(f"A{i}:D{i}", [[name, unit, carb_val, note]])
                            updated = True
                            break
                    if not updated:
                        sheet_food.append_row([name, unit, carb_val, note])
                    st.success(f"✅ {'覆蓋' if updated else '新增'}成功：{name}")
                except:
                    st.error("碳水值請輸入數字")

    st.divider()
    keyword = st.text_input("🔍 查詢關鍵字")
    if keyword:
        results = find_similar_foods(keyword)
        if results:
            df = pd.DataFrame(results, columns=["食物名稱", "單位", "碳水化合物", "備註"])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("查無資料")

# === 碳水計算 ===
with tabs[1]:
    st.header("📊 碳水計算")
    keyword = st.text_input("輸入食物名稱以查詢")
    if keyword:
        matches = find_similar_foods(keyword)
        if matches:
            selected = st.selectbox("選擇項目", [f"{r[0]}｜每{r[1]} 含 {r[2]}g" for r in matches])
            amount = st.number_input("攝取量 (g/ml)", min_value=0.0, step=1.0)
            if st.button("✅ 加入計算"):
                idx = [f"{r[0]}｜每{r[1]} 含 {r[2]}g" for r in matches].index(selected)
                row = matches[idx]
                carb = round(float(row[2]) * amount, 2)
                st.session_state.calc_results.append({"name": row[0], "amount": amount, "unit": row[1], "carb": carb})
                st.success(f"已加入：{row[0]}｜{amount}{row[1]}｜碳水: {carb}g")

    st.divider()
    if st.session_state.calc_results:
        df = pd.DataFrame(st.session_state.calc_results)
        st.dataframe(df, use_container_width=True)
        total = sum([r["carb"] for r in st.session_state.calc_results])
        st.metric("總碳水量 (g)", f"{round(total, 2)}")
        if st.button("🗑️ 清除所有項目"):
            st.session_state.calc_results.clear()
            st.success("已清除")

# === 胰島素紀錄 ===
with tabs[2]:
    st.header("💉 胰島素劑量與記錄")
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("📅 日期", value=datetime.today())
        meal = st.selectbox("🍽️ 餐別", ["早餐", "午餐", "晚餐", "宵夜"])
        current_glucose = st.number_input("🩸 目前血糖值", min_value=0, step=1)
        target_glucose = st.number_input("🎯 期望血糖值", min_value=0, value=100)
    with col2:
        ci = st.number_input("C/I 值", min_value=0.1, step=0.1)
        isf = st.number_input("ISF 值", min_value=0.1, step=0.1)

    if st.button("🧮 計算與儲存"):
        total_carb = round(sum([r["carb"] for r in st.session_state.calc_results]), 2)
        insulin_carb = round(total_carb / ci, 1)
        insulin_correction = round((current_glucose - target_glucose) / isf, 1)
        total_insulin = round(insulin_carb + insulin_correction, 1)

        st.success(f"碳水劑量：{insulin_carb}U，矯正劑量：{insulin_correction}U，總劑量：{total_insulin}U")

        for item in st.session_state.calc_results:
            sheet_food_records.append_row([
                str(date), meal, item["name"], item["amount"], item["unit"], item["carb"]
            ])
        sheet_food_records.append_row(["", "", "", "", "總碳水", total_carb])

        sheet_insulin.append_row([
            str(date), meal, total_carb, current_glucose, target_glucose,
            ci, isf, insulin_carb, insulin_correction, total_insulin
        ])

        st.success("✅ 資料已儲存至 Google Sheets")
        st.session_state.calc_results.clear()
