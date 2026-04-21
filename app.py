"""
app.py
Streamlit web app for visualizing CWA 7-day weather forecasts on a Folium map.
Run with: streamlit run app.py
"""

import os
import subprocess
import sys

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

# ── Page configuration ──────────────────────────────────────────────
st.set_page_config(
    page_title="台灣氣溫預報 Web App",
    page_icon="🌤️",
    layout="wide",
)

# ── Region coordinates (approximate centre of each area) ────────────
REGION_COORDS = {
    "北部": (25.05, 121.50),
    "中部": (24.15, 120.67),
    "南部": (22.63, 120.30),
    "東北部": (24.77, 121.75),
    "東部": (23.97, 121.60),
    "東南部": (22.75, 121.15),
}

CSV_FILE = "weather_data.csv"


# ── Helper: colour by average temperature ───────────────────────────
def temp_color(avg_temp: float) -> str:
    if avg_temp < 20:
        return "blue"
    elif avg_temp < 25:
        return "green"
    elif avg_temp < 30:
        return "orange"      # yellow is hard to see on a map
    else:
        return "red"


def temp_color_hex(avg_temp: float) -> str:
    """Return a hex colour for the CircleMarker fill."""
    if avg_temp < 20:
        return "#3b82f6"     # blue
    elif avg_temp < 25:
        return "#22c55e"     # green
    elif avg_temp < 30:
        return "#eab308"     # yellow / amber
    else:
        return "#ef4444"     # red


# ── Ensure CSV exists ───────────────────────────────────────────────
def ensure_data():
    if not os.path.exists(CSV_FILE):
        st.info("首次啟動：正在從 CWA API 下載氣象資料 …")
        subprocess.run([sys.executable, "fetch_weather.py"], check=True)
        st.rerun()


# ── Main app ────────────────────────────────────────────────────────
def main():
    ensure_data()

    # Load data
    try:
        df = pd.read_csv(CSV_FILE)
    except Exception as e:
        st.error(f"無法讀取 {CSV_FILE}: {e}")
        st.stop()

    if df.empty:
        st.warning("CSV 資料為空，請確認 CWA API 是否正常回傳資料。")
        st.stop()

    # ── Title ───────────────────────────────────────────────────────
    st.markdown(
        "<h1 style='text-align:center;'>🌤️ 台灣氣溫預報 Web App</h1>"
        "<p style='text-align:center;color:gray;'>"
        "資料來源：中央氣象署 CWA — F-A0010-001 一週農業氣象預報</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Date selector ───────────────────────────────────────────────
    dates = sorted(df["date"].unique())
    selected_date = st.selectbox("📅 選擇日期", dates, index=0)

    day_df = df[df["date"] == selected_date].copy()

    # ── Two-column layout ───────────────────────────────────────────
    col_map, col_table = st.columns([1, 1], gap="large")

    # ── Left: Folium map ────────────────────────────────────────────
    with col_map:
        st.subheader("🗺️ 台灣區域氣溫地圖")

        m = folium.Map(
            location=[23.7, 121.0],
            zoom_start=7,
            tiles="CartoDB positron",
        )

        for _, row in day_df.iterrows():
            region = row["region"]
            coords = REGION_COORDS.get(region)
            if coords is None:
                continue

            avg = row["avg_temp"]
            color = temp_color(avg)
            hex_color = temp_color_hex(avg)

            popup_html = (
                f"<div style='min-width:140px'>"
                f"<b>{region}</b><br>"
                f"📅 {row['date']}<br>"
                f"🌡️ 最低 {row['min_temp']}°C<br>"
                f"🌡️ 最高 {row['max_temp']}°C<br>"
                f"📊 平均 {avg}°C"
                f"</div>"
            )

            folium.CircleMarker(
                location=coords,
                radius=18,
                color=hex_color,
                fill=True,
                fill_color=hex_color,
                fill_opacity=0.7,
                popup=folium.Popup(popup_html, max_width=200),
                tooltip=f"{region}：{avg}°C",
            ).add_to(m)

        st_folium(m, width=600, height=500, returned_objects=[])

        # Legend
        st.markdown(
            """
            **圖例：**
            🔵 < 20°C &nbsp;&nbsp;
            🟢 20–25°C &nbsp;&nbsp;
            🟡 25–30°C &nbsp;&nbsp;
            🔴 > 30°C
            """
        )

    # ── Right: data table ───────────────────────────────────────────
    with col_table:
        st.subheader(f"📋 {selected_date} 各區域氣溫")

        display_df = day_df[["region", "min_temp", "max_temp", "avg_temp"]].rename(
            columns={
                "region": "區域",
                "min_temp": "最低溫 (°C)",
                "max_temp": "最高溫 (°C)",
                "avg_temp": "平均溫 (°C)",
            }
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # ── Quick stats ─────────────────────────────────────────────
        st.markdown("---")
        st.subheader("📊 當日統計")
        c1, c2, c3 = st.columns(3)
        c1.metric("最低溫", f"{day_df['min_temp'].min()}°C")
        c2.metric("最高溫", f"{day_df['max_temp'].max()}°C")
        c3.metric("平均溫", f"{day_df['avg_temp'].mean():.1f}°C")

    # ── Refresh button ──────────────────────────────────────────────
    st.markdown("---")
    if st.button("🔄 重新抓取最新資料"):
        subprocess.run([sys.executable, "fetch_weather.py"], check=True)
        st.rerun()


if __name__ == "__main__":
    main()
