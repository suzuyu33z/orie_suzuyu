import os
import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import folium_static
import hashlib

# セッション状態の初期化
if 'show_all' not in st.session_state:
    st.session_state['show_all'] = False
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""
if 'favorite_properties' not in st.session_state:
    st.session_state['favorite_properties'] = []
if 'search_clicked' not in st.session_state:
    st.session_state['search_clicked'] = False

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
    df['家賃'] = pd.to_numeric(df['家賃'], errors='coerce')
    df = df.dropna(subset=['家賃'])
    return df

def make_clickable(url, name):
    return f'<a target="_blank" href="{url}">{name}</a>'

# 地図を作成し、マーカーを追加する関数
def create_map(filtered_df):
    map_center = [filtered_df['緯度'].mean(), filtered_df['経度'].mean()]
    m = folium.Map(location=map_center, zoom_start=12)
    for idx, row in filtered_df.iterrows():
        if pd.notnull(row['緯度']) and pd.notnull(row['経度']):
            popup_html = f"""
            <b>名称:</b> {row['名称']}<br>
            <b>アドレス:</b> {row['アドレス']}<br>
            <b>家賃:</b> {row['家賃']}万円<br>
            <b>間取り:</b> {row['間取り']}<br>
            <a href="{row['物件詳細URL']}" target="_blank">物件詳細</a>
            """
            popup = folium.Popup(popup_html, max_width=400)
            folium.Marker(
                [row['緯度'], row['経度']],
                popup=popup
            ).add_to(m)
    return m

# 検索結果を表示する関数
def display_search_results(filtered_df):
    for idx, row in filtered_df.iterrows():
        col1, col2 = st.columns([2, 1])
        with col1:
            st.write(f"### 物件番号: {idx+1}")
            st.write(f"**名称:** {row['名称']}")
            st.write(f"**アドレス:** {row['アドレス']}")
            st.write(f"**階数:** {row['階数']}")
            st.write(f"**家賃:** {row['家賃']}万円")
            st.write(f"**間取り:** {row['間取り']}")
            st.write(f"**物件詳細URL:** {make_clickable(row['物件詳細URL'], '詳細情報はこちらをクリック')}", unsafe_allow_html=True)
            if st.button(f"お気に入り登録", key=f"favorite_{idx}"):
                save_favorite_property(st.session_state['username'], idx)
                st.success(f"{row['名称']}をお気に入りに追加しました")
        with col2:
            st.image(row['物件画像URL'], use_column_width=True)
        st.write("---")

# パスワードをハッシュ化
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return hashed_text
    return False

# ユーザー登録、ユーザー追加、ログイン機能実装
def create_user():
    conn = sqlite3.connect('password.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS userstable(username TEXT, password TEXT)')
    conn.commit()
    conn.close()

def add_user(username, password):
    conn = sqlite3.connect('password.db')
    c = conn.cursor()
    c.execute('INSERT INTO userstable(username, password) VALUES (?, ?)', (username, password))
    conn.commit()
    conn.close()

def login_user(username, password):
    conn = sqlite3.connect('password.db')
    c = conn.cursor()
    c.execute('SELECT * FROM userstable WHERE username =? AND password = ?', (username, password))
    data = c.fetchall()
    conn.close()
    return data

# お気に入り物件を保存する関数
def save_favorite_property(username, property_id):
    conn = sqlite3.connect('password.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS favorite_properties(username TEXT, property_id INTEGER)')
    c.execute('INSERT INTO favorite_properties(username, property_id) VALUES (?, ?)', (username, property_id))
    conn.commit()
    conn.close()

# お気に入り物件を取得する関数
def get_favorite_properties(username):
    conn = sqlite3.connect('password.db')
    c = conn.cursor()
    c.execute('SELECT property_id FROM favorite_properties WHERE username = ?', (username,))
    data = c.fetchall()
    conn.close()
    return [item[0] for item in data]

# お気に入り物件を削除する関数
def remove_favorite_property(username, property_id):
    conn = sqlite3.connect('password.db')
    c = conn.cursor()
    c.execute('DELETE FROM favorite_properties WHERE username = ? AND property_id = ?', (username, property_id))
    conn.commit()
    conn.close()

# メインのアプリケーション
def main():
    db_path = "chintai.db"
    table_name = "properties"  # テーブル名をここに入力

    df = load_data_from_sqlite(db_path, table_name)
    df = preprocess_dataframe(df)

    # StreamlitのUI要素（スライダー、ボタンなど）の各表示設定
    st.title('賃貸物件情報の可視化')

    menu = ["ログイン", "物件を探す","物件を決める"]
    choice = st.sidebar.radio("", menu)

    if choice == "ログイン":
        st.subheader("ログインしてください")
        st.markdown("<a href='#サインアップ' style='font-size: 0.8em; color: #ff6347;'>ユーザー登録がまだの方は新規ユーザー登録（左より登録可能）をお願いします</a>", unsafe_allow_html=True)
        username = st.text_input("ユーザー名を入力してください")
        password = st.text_input("パスワードを入力してください", type='password')
        if st.button("ログインする"):
            create_user()
            hashed_pswd = make_hashes(password)
            result = login_user(username, check_hashes(password, hashed_pswd))
            if result:
                st.success(f"{username}さんでログインしました")
                st.info("物件を探してお気に入り登録できるようになりました")
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
            else:
                st.warning("ユーザー名かパスワードが間違っています")
        #サインアップ
        st.sidebar.markdown("<hr>", unsafe_allow_html=True)
        st.sidebar.subheader("新規ユーザー登録")
        new_user = st.sidebar.text_input("新しいユーザー名を入力してください")
        new_password = st.sidebar.text_input("新しいパスワードを入力してください", type='password')
        if st.sidebar.button("登録する"):
            create_user()
            add_user(new_user, make_hashes(new_password))
            st.sidebar.success("アカウントの作成に成功しました")
            st.sidebar.info("ログインしてください")

    elif choice == "物件を探す":
        st.subheader("物件を探してお気に入り登録しよう！")
        if st.session_state['logged_in']:
            st.write(f"こんにちは、{st.session_state['username']} さん")

        else:
            st.warning("ログインしてください")

    elif choice == "物件を決める":
        st.subheader("物件を決めよう！")
        if st.session_state['logged_in']:
            favorite_properties = get_favorite_properties(st.session_state['username'])
            if favorite_properties:
                st.write("お気に入り物件:")
                for property_id in favorite_properties:
                    property_data = df[df.index == property_id]
                    if not property_data.empty:
                        st.write(property_data[['名称', 'アドレス', '家賃', '間取り']])
                        if st.button(f"お気に入り解除 {property_data.iloc[0]['名称']}", key=f"remove_{property_id}"):
                            remove_favorite_property(st.session_state['username'], property_id)
                            st.success(f"{property_data.iloc[0]['名称']}をお気に入りから解除しました")
        else:
            st.warning("ログインしてください")

    if st.session_state['logged_in'] and choice == "物件を探す":
        col1, col2 = st.columns([1, 2])
        with col1:
            area = st.multiselect('■ エリア選択', df['区'].unique(), default=[])
        with col2:
            price_min = st.number_input(
                '■ 家賃下限 (万円)',
                min_value=int(1),
                max_value=int(df['家賃'].max()),
                value=int(df['家賃'].min()),
                step=1
            )
            price_max = st.number_input(
                '■ 家賃上限 (万円)',
                min_value=int(1),
                max_value=int(df['家賃'].max()),
                value=int(df['家賃'].max()),
                step=1
            )
        with col2:
            type_options = st.multiselect('■ 間取り選択', df['間取り'].unique(), default=['2LDK', '3LDK'])

        filtered_df = df[(df['区'].isin(area)) & (df['間取り'].isin(type_options))]
        filtered_df = filtered_df[(filtered_df['家賃'] >= price_min) & (filtered_df['家賃'] <= price_max)]
        filtered_count = len(filtered_df)

        filtered_df['緯度'] = pd.to_numeric(filtered_df['緯度'], errors='coerce')
        filtered_df['経度'] = pd.to_numeric(filtered_df['経度'], errors='coerce')
        filtered_df2 = filtered_df.dropna(subset=['緯度', '経度'])
        filtered_df['物件詳細URL'] = filtered_df['物件詳細URL'].apply(lambda x: make_clickable(x, "リンク"))

        col2_1, col2_2 = st.columns([1, 2])
        with col2_2:
            st.write(f"物件検索数: {filtered_count}件 / 全{len(df)}件")
        if col2_1.button('検索＆更新', key='search_button'):
            st.session_state['filtered_df'] = filtered_df
            st.session_state['filtered_df2'] = filtered_df2
            st.session_state['search_clicked'] = True
        if st.session_state.get('search_clicked', False):
            m = create_map(st.session_state.get('filtered_df2', filtered_df2))
            folium_static(m)
        
        show_all_option = st.radio(
        "表示オプションを選択してください:",
        ('地図上の検索物件のみ', 'すべての検索物件'),
        index=0 if not st.session_state.get('show_all', False) else 1,
        key='show_all_option'
        )
        st.session_state['show_all'] = (show_all_option == 'すべての検索物件')
        if st.session_state.get('search_clicked', False):
            if st.session_state['show_all']:
                display_search_results(st.session_state.get('filtered_df', filtered_df))
            else:
                display_search_results(st.session_state.get('filtered_df2', filtered_df2))

# アプリケーションの実行
if __name__ == "__main__":
    main()
