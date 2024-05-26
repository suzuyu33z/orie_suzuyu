import requests
import re
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import sqlite3
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time

# homesからのスクレイピング（港区の物件のみ）
base_url = "https://www.homes.co.jp/chintai/tokyo/minato-city/list/?page={}"
max_page = 5
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

all_data = []

for page in range(1, max_page + 1):
    url = base_url.format(page)
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'lxml')
    items = soup.findAll("div", {"class": "mod-mergeBuilding--rent--photo"})

    for item in items:
        base_data = {}
        base_data["名称"] = item.find(class_="bukkenName").get_text(strip=True) if item.find(class_="bukkenName") else None
        base_data["アドレス"] = next((td.find_next_sibling('td').get_text(strip=True) for td in item.find_all('th') if td.get_text(strip=True) == '所在地'), None)
        base_data["アクセス"] = item.find("td", class_="traffic").get_text(strip=True) if item.find("td", class_="traffic") else ', '.join(span.get_text(strip=True) for span in item.find_all("span", class_="prg-stationText"))
        module_body = item.find('div', class_='moduleBody')
        if module_body:
            construction_th = module_body.find('th', string='築年数/階数')
            if construction_th:
                base_data["築年数"] = construction_th.find_next_sibling('td').get_text(strip=True).split(' ')[0]
                base_data["構造"] = construction_th.find_next_sibling('td').get_text(strip=True).split(' ')[2]

        rooms = item.find_all(class_="unitListBody prg-unitListBody")
        for room in rooms:
            data = base_data.copy()
            floor_number_td = room.find(class_="roomKaisuu")
            data["階数"] = floor_number_td.get_text(strip=True) if floor_number_td else None

            rent_price_label = room.select_one("span.priceLabel")
            rent_price = rent_price_label.get_text(strip=True) if rent_price_label else None
            rent_admin = rent_price_label.next_sibling.strip().replace("/", "").replace(",", "") if rent_price_label else None
            data["家賃"] = rent_price
            data["管理費"] = rent_admin

            price = room.select_one("td.price")
            br_tag = price.find('br').next_sibling.strip()
            depo = br_tag.split("/")[0]
            key = br_tag.split("/")[1]
            data["敷金"] = depo
            data["礼金"] = key

            layout = room.select_one("td.layout")
            room_type = layout.contents[0].strip() if layout.contents else None
            room_area = layout.find('br').next_sibling.strip().replace('m²', 'm2') if layout.find('br') else None
            data["間取り"] = room_type
            data["面積"] = room_area

            property_image_element = item.select_one(".bukkenPhoto .photo img")
            data["物件画像URL"] = property_image_element["data-original"] if property_image_element else None

            floor_plan_image_element = item.select_one(".floarPlanPic img")
            data["間取画像URL"] = floor_plan_image_element["data-original"] if floor_plan_image_element else None

            property_link_element = item.select_one("a[href*='/chintai/room']")
            data["物件詳細URL"] = property_link_element['href'] if property_link_element else None
            
            all_data.append(data)

df = pd.DataFrame(all_data)

# データフレームの内容を確認
print(df.head())
print(df.columns)

# アドレスの標準化関数
def standardize_address(address):
    address = re.sub(r'1', '１', address)
    address = re.sub(r'2', '２', address)
    address = re.sub(r'3', '３', address)
    address = re.sub(r'4', '４', address)
    address = re.sub(r'5', '５', address)
    address = re.sub(r'6', '６', address)
    address = re.sub(r'7', '７', address)
    address = re.sub(r'8', '８', address)
    address = re.sub(r'9', '９', address)
    address = re.sub(r'0', '０', address)
    address = re.sub(r'丁目.*', '', address)
    address = re.sub(r'-.*', '', address)
    return address

# 標準化した住所を新しいカラムに追加
df['アドレス'] = df['アドレス'].apply(standardize_address)

# 数字を除去した住所をアドレス_数字除去に格納
def remove_numbers(address):
    address_no_numbers = re.sub(r'[0-9０-９]', '', address)
    return address_no_numbers

df['アドレス_数字除去'] = df['アドレス'].apply(remove_numbers)

# スーモからの情報取得
base_url = "https://suumo.jp/chintai/tokyo/sc_minato/?page={}"
max_page = 5

all_data = []

for page in range(1, max_page + 1):
    url = base_url.format(page)
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'lxml')
    items = soup.findAll("div", {"class": "cassetteitem"})

    print("page", page, "items", len(items))

    for item in items:
        base_data = {}
        base_data["名称"] = item.find("div", {"class": "cassetteitem_content-title"}).get_text(strip=True) if item.find("div", {"class": "cassetteitem_content-title"}) else None
        base_data["カテゴリ"] = item.find("div", {"class": "cassetteitem_content-label"}).span.get_text(strip=True) if item.find("div", {"class": "cassetteitem_content-label"}) else None
        base_data["アドレス"] = item.find("li", {"class": "cassetteitem_detail-col1"}).get_text(strip=True) if item.find("li", {"class": "cassetteitem_detail-col1"}) else None
        base_data["アクセス"] = ", ".join([station.get_text(strip=True) for station in item.findAll("div", {"class": "cassetteitem_detail-text"})])

        construction_info = item.find("li", {"class": "cassetteitem_detail-col3"}).find_all("div") if item.find("li", {"class": "cassetteitem_detail-col3"}) else None
        base_data["築年数"] = construction_info[0].get_text(strip=True) if construction_info and len(construction_info) > 0 else None
        base_data["構造"] = construction_info[1].get_text(strip=True) if construction_info and len(construction_info) > 1 else None

        tbodys = item.find("table", {"class": "cassetteitem_other"}).findAll("tbody")

        for tbody in tbodys:
            data = base_data.copy()
            floor_info = tbody.find_all("td")[2].get_text(strip=True) if len(tbody.find_all("td")) > 2 else None
            data["階数"] = floor_info
            data["家賃"] = tbody.select_one(".cassetteitem_price--rent").get_text(strip=True) if tbody.select_one(".cassetteitem_price--rent") else None
            data["管理費"] = tbody.select_one(".cassetteitem_price--administration").get_text(strip=True) if tbody.select_one(".cassetteitem_price--administration") else None
            data["敷金"] = tbody.select_one(".cassetteitem_price--deposit").get_text(strip=True) if tbody.select_one(".cassetteitem_price--deposit") else None
            data["礼金"] = tbody.select_one(".cassetteitem_price--gratuity").get_text(strip=True) if tbody.select_one(".cassetteitem_price--gratuity") else None
            data["間取り"] = tbody.select_one(".cassetteitem_madori").get_text(strip=True) if tbody.select_one(".cassetteitem_madori") else None
            data["面積"] = tbody.select_one(".cassetteitem_menseki").get_text(strip=True) if tbody.select_one(".cassetteitem_menseki") else None

            property_image_element = item.find(class_="cassetteitem_object-item")
            data["物件画像URL"] = property_image_element.img["rel"] if property_image_element and property_image_element.img else None

            floor_plan_image_element = item.find(class_="casssetteitem_other-thumbnail")
            data["間取画像URL"] = floor_plan_image_element.img["rel"] if floor_plan_image_element and floor_plan_image_element.img else None

            property_link_element = item.select_one("a[href*='/chintai/jnc_']")
            data["物件詳細URL"] = "https://suumo.jp" + property_link_element['href'] if property_link_element else None

            all_data.append(data)

df2 = pd.DataFrame(all_data)

# 数字を除去した住所をアドレス_数字除去に格納
df2['アドレス_数字除去'] = df2['アドレス'].apply(remove_numbers)

# カテゴリはホームズにないので消す
df2_cleaned = df2.drop(columns=['カテゴリ'])

# スーモとホームズを合体
df_merged = pd.concat([df, df2_cleaned], ignore_index=True)

# 重複物件を削除する
df_deduplicated = df_merged.drop_duplicates(subset=['築年数', '構造', '階数', '家賃', '面積', 'アドレス_数字除去'])

# 削除前後の行数を比較
original_count = len(df_merged)
deduplicated_count = len(df_deduplicated)
duplicates_removed = original_count - deduplicated_count

# df_deduplicatedから「アドレス_数字除去」を削除する
df_deduplicated = df_deduplicated.drop(columns=['アドレス_数字除去'])

# SQLiteに格納する処理
conn = sqlite3.connect('chintai.db')

# データフレームをSQLiteに格納
df_deduplicated.to_sql('properties', conn, if_exists='replace', index=False)

# 接続を閉じる
conn.close()

# データベースからデータを取り込む
conn = sqlite3.connect('chintai.db')
df = pd.read_sql_query('SELECT * FROM properties', conn)

# 新築であれば築年数を0にする
def extract_years(x):
    if x == '新築':
        return 0
    match = re.search(r'(\d+)', x)
    if match:
        return int(match.group(1))
    return None

df['築年数'] = df["築年数"].apply(extract_years)

# 構造を変更。「階建」を消す。
def get_most_floor(x):
    if '階建' not in x:
        return np.nan
    else:
        list = re.findall(r'(\d+)階建', str(x))
        if list:
            list = map(int, list)
            min_value = min(list)
            return min_value
        return np.nan

df['構造'] = df['構造'].apply(get_most_floor)

# 階数を編集する。「5階」→5
def get_floor(x):
    if isinstance(x, float) and np.isnan(x):
        return 0
    x = str(x)
    if '階' not in x:
        return 0
    elif 'B' not in x:
        floors = re.findall(r'(\d+)階', x)
        floors = list(map(int, floors))
        min_value = min(floors)
        return int(min_value)
    else:
        floors = re.findall(r'(\d+)階', x)
        floors = list(map(int, floors))
        min_value = -1 * min(floors)
        return int(min_value)

df['階数'] = df['階数'].apply(get_floor)

# 家賃を数字に変える
def change_fee(x):
    if '万円' not in x:
        return np.nan
    else:
        return float(x.split('万円')[0])

df['家賃'] = df['家賃'].apply(change_fee)

# 敷金、礼金の変換関数
def convert_fee(value):
    if isinstance(value, float) and pd.isna(value):
        return 0
    value = str(value)
    if '無' in value:
        return 0
    match = re.match(r'(\d+)ヶ月', value)
    if match:
        return int(match.group(1))
    return 0

df['敷金'] = df['敷金'].apply(convert_fee)
df['礼金'] = df['礼金'].apply(convert_fee)

df['敷金'] = df['敷金'] * df['家賃']
df['礼金'] = df['礼金'] * df['家賃']

def change_fee2(x):
    if '円' not in x:
        return np.nan
    else:
        return float(x.split('円')[0])

df['管理費'] = df['管理費'].apply(change_fee2)

df['面積'] = df['面積'].apply(lambda x: float(x[:-2]))

df['区'] = df["アドレス"].apply(lambda x: x[x.find("都") + 1:x.find("区") + 1])

df['市町'] = df["アドレス"].apply(lambda x: x[x.find("区") + 1:-1])

# 「西武新宿線/鷺ノ宮駅 歩9分」「西武新宿線 鷺ノ宮駅 徒歩9分」どちらの表記であっても上手く分割できるように書き換える
def split_access(row):
    accesses = row['アクセス'].split(', ')
    results = {}

    for i, access in enumerate(accesses, start=1):
        if i > 3:
            break

        parts = re.split(r'[ /]', access, maxsplit=1)
        if len(parts) == 2:
            line_station, walk = parts
            line_station = line_station.strip()
            walk = walk.strip()

            walk_min_match = re.search(r'(徒歩|歩)(\d+)分', walk)
            if walk_min_match:
                station = re.split(r'(駅)', line_station, maxsplit=1)[0].strip() + '駅'
                walk_min = int(walk_min_match.group(2))
            else:
                station = None
                walk_min = None
        else:
            line_station = access.strip()
            station = walk_min = None

        results[f'アクセス{i}線路名'] = line_station
        results[f'アクセス{i}駅名'] = station
        results[f'アクセス{i}徒歩(分)'] = walk_min

    return pd.Series(results)

df = df.join(df.apply(split_access, axis=1))

# ジオコーダーの初期化
geolocator = Nominatim(user_agent="your_app_name", timeout=10)

current_count = 0
total_count = len(df['アドレス'])

def get_lat_lon(address, retries=3):
    global current_count
    current_count += 1
    
    for attempt in range(retries):
        try:
            location = geolocator.geocode(address)
            if location:
                print(f"{current_count}/{total_count} 件目実施中 結果: {location.latitude}, {location.longitude}")
                return location.latitude, location.longitude
            else:
                print(f"{current_count}/{total_count} 件目実施中 結果: 住所が見つかりません")
                return None, None
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Error retrieving location for address {address}: {e}. Retrying ({attempt + 1}/{retries})...")
            time.sleep(1)

    print(f"Failed to retrieve location for address {address} after {retries} retries")
    return None, None

df['緯度'], df['経度'] = zip(*df['アドレス'].apply(get_lat_lon))

# SQLiteに格納
conn = sqlite3.connect('chintai.db')
df.to_sql('properties', conn, if_exists='replace', index=False)
conn.close()
