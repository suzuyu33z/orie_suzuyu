import os
import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import folium_static

# show_allというセッション変数が存在しない場合、それを初期化して設定する役割を果たしています。
if 'show_all' not in st.session_state:
    st.session_state['show_all'] = False 


# 地図上以外の物件も表示するボタンの状態を切り替える関数
def toggle_show_all():
    st.session_state['show_all'] = not st.session_state['show_all']


# SQLiteデータベースからデータを読み込む関数
def load_data_from_sqlite(db_path, table_name):
    conn = sqlite3.connect(db_path)
    query = f"SELECT * FROM {table_name}"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def preprocess_dataframe(df):
    # '家賃' 列を浮動小数点数に変換し、NaN値を取り除く
    df['家賃'] = pd.to_numeric(df['家賃'], errors='coerce')
    df = df.dropna(subset=['家賃'])
    return df


def make_clickable(url, name):
    return f'<a target="_blank" href="{url}">{name}</a>'


# 地図を作成し、マーカーを追加する関数
def create_map(filtered_df):
    # 地図の初期設定
    map_center = [filtered_df['緯度'].mean(), filtered_df['経度'].mean()]
    m = folium.Map(location=map_center, zoom_start=12)

    # マーカーを追加
    for idx, row in filtered_df.iterrows():
        if pd.notnull(row['緯度']) and pd.notnull(row['経度']):
            # ポップアップに表示するHTMLコンテンツを作成
            popup_html = f"""
            <b>名称:</b> {row['名称']}<br>
            <b>アドレス:</b> {row['アドレス']}<br>
            <b>家賃:</b> {row['家賃']}万円<br>
            <b>間取り:</b> {row['間取り']}<br>
            <a href="{row['物件詳細URL']}" target="_blank">物件詳細</a>
            """
            # HTMLをポップアップに設定
            popup = folium.Popup(popup_html, max_width=400)
            folium.Marker(
                [row['緯度'], row['経度']],
                popup=popup
            ).add_to(m)

    return m


# 検索結果を表示する関数
def display_search_results(filtered_df):
    # 物件番号を含む新しい列を作成
    filtered_df['物件番号'] = range(1, len(filtered_df) + 1)
    filtered_df['物件詳細URL'] = filtered_df['物件詳細URL'].apply(lambda x: make_clickable(x, "リンク"))
    display_columns = ['物件番号', '名称', 'アドレス', '階数', '家賃', '間取り', '物件詳細URL']
    filtered_df_display = filtered_df[display_columns]
    st.markdown(filtered_df_display.to_html(escape=False, index=False), unsafe_allow_html=True)


# メインのアプリケーション
def main():
    db_path = "chintai.db"
    table_name = "properties"  # テーブル名をここに入力

    df = load_data_from_sqlite(db_path, table_name)
    df = preprocess_dataframe(df)

    # StreamlitのUI要素（スライダー、ボタンなど）の各表示設定
    st.title('賃貸物件情報の可視化')

    # エリアと家賃フィルタバーを1:2の割合で分割
    col1, col2 = st.columns([1, 2])

    with col1:
        # エリア選択
        area = st.radio('■ エリア選択', df['区'].unique())


    with col2:
        # 家賃範囲選択のスライダーをfloat型で設定し、小数点第一位まで表示
        price_min, price_max = st.slider(
            '■ 家賃範囲 (万円)', 
            min_value=float(1), 
            max_value=float(df['家賃'].max()),
            value=(float(df['家賃'].min()), float(df['家賃'].max())),
            step=0.1,  # ステップサイズを0.1に設定
            format='%.1f'
        )

    with col2:
    # 間取り選択のデフォルト値をすべてに設定
        type_options = st.multiselect('■ 間取り選択', df['間取り'].unique(), default=df['間取り'].unique())


    # フィルタリング/ フィルタリングされたデータフレームの件数を取得
    filtered_df = df[(df['区'].isin([area])) & (df['間取り'].isin(type_options))]
    filtered_df = filtered_df[(filtered_df['家賃'] >= price_min) & (filtered_df['家賃'] <= price_max)]
    filtered_count = len(filtered_df)

    # '緯度' と '経度' 列を数値型に変換し、NaN値を含む行を削除
    filtered_df['緯度'] = pd.to_numeric(filtered_df['緯度'], errors='coerce')
    filtered_df['経度'] = pd.to_numeric(filtered_df['経度'], errors='coerce')
    filtered_df2 = filtered_df.dropna(subset=['緯度', '経度'])
    filtered_df['物件詳細URL'] = filtered_df['物件詳細URL'].apply(lambda x: make_clickable(x, "リンク"))


    # 検索ボタン / # フィルタリングされたデータフレームの件数を表示
    col2_1, col2_2 = st.columns([1, 2])

    with col2_2:
        st.write(f"物件検索数: {filtered_count}件 / 全{len(df)}件")

    # 検索ボタン
    if col2_1.button('検索＆更新', key='search_button'):
        # 検索ボタンが押された場合、セッションステートに結果を保存
        st.session_state['filtered_df'] = filtered_df
        st.session_state['filtered_df2'] = filtered_df2
        st.session_state['search_clicked'] = True

    # Streamlitに地図を表示
    if st.session_state.get('search_clicked', False):
        m = create_map(st.session_state.get('filtered_df2', filtered_df2))
        folium_static(m)

    # 地図の下にラジオボタンを配置し、選択したオプションに応じて表示を切り替える
    show_all_option = st.radio(
        "表示オプションを選択してください:",
        ('地図上の検索物件のみ', 'すべての検索物件'),
        index=0 if not st.session_state.get('show_all', False) else 1,
        key='show_all_option'
    )

    # ラジオボタンの選択に応じてセッションステートを更新
    st.session_state['show_all'] = (show_all_option == 'すべての検索物件')

    # 検索結果の表示
    if st.session_state.get('search_clicked', False):
        if st.session_state['show_all']:
            display_search_results(st.session_state.get('filtered_df', filtered_df))  # 全データ
        else:
            display_search_results(st.session_state.get('filtered_df2', filtered_df2))  # 地図上の物件のみ


# アプリケーションの実行
if __name__ == "__main__":
    if 'search_clicked' not in st.session_state:
        st.session_state['search_clicked'] = False
    if 'show_all' not in st.session_state:
        st.session_state['show_all'] = False
    main()
