import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="食物碳水與胰島素系統", layout="wide")

# === 授權 Google Sheets API ===
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    gc = gspread.authorize(credentials)
    st.success("✅ 成功授權 Google Sheets API")
except Exception as e:
    st.error("❌ 無法授權 Google Sheets API")
    st.exception(e)
    st.stop()

# === 設定 Sheet ID ===
FOOD_SHEET_ID = "你的食物資料表 ID"
RECORD_SHEET_ID = "你的紀錄資料表 ID"

# === 連接 Google Sheets ===
try:
    sheet_food = gc.open_by_key(FOOD_SHEET_ID).worksheet("食物資料")
    st.success("✅ 已連接食物資料")
except Exception as e:
    st.error("❌ 無法連接食物資料")
    st.exception(e)
    st.stop()

try:
    sheet_food_records = gc.open_by_key(RECORD_SHEET_ID).worksheet("食物記錄")
    sheet_insulin = gc.open_by_key(RECORD_SHEET_ID).worksheet("血糖與胰島素紀錄表")
    st.success("✅ 已連接紀錄表格")
except Exception as e:
    st.error("❌ 無法連接紀錄工作表")
    st.exception(e)
    st.stop()

# === Session state ===
if "calc_results" not in st.session_state:
    st.session_state.calc_results = []

# === 分頁介面 ===
tabs = st.tabs(["🍱 食物管理", "📊 碳水計算", "💉 胰島素紀錄"])

# === 食物管理 ===
with tabs[0]:
    st.header("🍱 食物管理")
    with st.form("add_food_form"):
        name = st.text_input("食物名稱")
        unit = st.selectbox("單位", ["克(g)", "毫升(ml)"])
        carb = st.text_input("每單位碳水 (g)")
        note = st.text_input("備註")
        if st.form_submit_button("✅ 新增 / 更新"):
            try:
                carb_val = float(carb)
                rows = sheet_food.get_all_values()
                updated = False
                for i, row in enumerate(rows[1:], start=2):
                    if row[0] == name:
                        sheet_food.update(f"A{i}:D{i}", [[name, unit, carb_val, note]])
                        updated = True
                        break
                if not updated:
                    sheet_food.append_row([name, unit, carb_val, note])
                st.success("✅ 已新增或更新")
            except:
                st.error("❌ 碳水請輸入數字")

    st.subheader("🔍 查詢食物")
    keyword = st.text_input("查詢關鍵字")
    if keyword:
        data = sheet_food.get_all_values()[1:]
        results = [row for row in data if keyword in row[0]]
        if results:
            df = pd.DataFrame(results, columns=["食物名稱", "單位", "碳水化合物", "備註"])
            st.dataframe(df)
        else:
            st.info("查無資料")

# === 碳水計算 ===
with tabs[1]:
    st.header("📊 碳水計算")
    keyword = st.text_input("輸入食物名稱")
    data = sheet_food.get_all_values()[1:]
    results = [row for row in data if keyword in row[0]] if keyword else []
    if results:
        selected = st.selectbox("選擇食物", results)
        amount = st.number_input("攝取量", min_value=0.0)
        if st.button("✅ 加入計算"):
            carb = round(float(selected[2]) * amount, 2)
            st.session_state.calc_results.append({
                "name": selected[0], "amount": amount, "unit": selected[1], "carb": carb
            })
            st.success(f"已加入：{selected[0]}，碳水：{carb}g")

    if st.session_state.calc_results:
        st.subheader("📋 計算結果")
        df = pd.DataFrame(st.session_state.calc_results)
        st.dataframe(df)
        total = sum([r["carb"] for r in st.session_state.calc_results])
        st.metric("總碳水量", f"{round(total, 2)} g")
        if st.button("🗑 清除"):
            st.session_state.calc_results.clear()

# === 胰島素紀錄 ===
with tabs[2]:
    st.header("💉 胰島素紀錄")
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("日期", value=datetime.today())
        meal = st.selectbox("餐別", ["早餐", "午餐", "晚餐", "宵夜"])
        current = st.number_input("目前血糖", 0)
        target = st.number_input("目標血糖", value=100)
    with col2:
        ci = st.number_input("C/I 值", 0.1)
        isf = st.number_input("ISF 值", 0.1)

    if st.button("🧮 計算與儲存"):
        total_carb = round(sum([r["carb"] for r in st.session_state.calc_results]), 2)
        insulin_carb = round(total_carb / ci, 1)
        insulin_corr = round((current - target) / isf, 1)
        total = round(insulin_carb + insulin_corr, 1)

        st.success(f"碳水：{insulin_carb}U，矯正：{insulin_corr}U，總量：{total}U")

        for item in st.session_state.calc_results:
            sheet_food_records.append_row([
                str(date), meal, item["name"], item["amount"], item["unit"], item["carb"]
            ])
        sheet_insulin.append_row([
            str(date), meal, total_carb, current, target, ci, isf, insulin_carb, insulin_corr, total
        ])

        st.session_state.calc_results.clear()
        st.success("✅ 已儲存至 Google Sheets")
