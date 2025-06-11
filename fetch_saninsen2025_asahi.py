# -*- coding: utf-8 -*-
"""
朝日新聞「参院選2025 立候補予定者一覧」全ページをスクレイピングして
saninsen2025_candidates.csv を生成するスクリプト。

必要ライブラリ:
    pip install requests beautifulsoup4

使用例 (PowerShell):
    python fetch_saninsen2025_asahi.py
"""

import re
import csv
import time
import requests
from bs4 import BeautifulSoup

# ベース URL（B01〜B47 が各選挙区、C01 が比例区）
BASE = "https://www.asahi.com/senkyo/saninsen/koho/"

# 47 都道府県用のコード B01〜B47（ただし B32=鳥取は島根と合区なので飛ばす）
district_codes = [f"B{n:02d}" for n in range(1, 48)]
district_codes.remove("B32")   # 鳥取単独ページは存在しない
# 比例区
district_codes.append("C01")

def fetch(url: str, retry: int = 3, sleep: int = 2) -> str:
    """
    指定 URL を取得して HTML 文字列を返す。失敗時はリトライ。
    """
    for _ in range(retry):
        try:
            r = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (CandidateFetcher/1.0)"})
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"Retrying {url} because {e}")
            time.sleep(sleep)
    raise RuntimeError(f"Failed to fetch {url}")

def parse_candidates(html: str, default_district: str) -> list[dict]:
    """
    HTML を解析して候補者情報を抽出し、
    [{'選挙区', '氏名', '年齢', '党派'}, ...] のリストで返す。
    """
    soup = BeautifulSoup(html, "html.parser")

    # ページタイトルから選挙区名を補足（例: "参院選東京 候補者一覧"）
    h1 = soup.find("h1")
    district = default_district
    if h1 and "参院選" in h1.text:
        district = h1.text.split("参院選")[-1].split("候補者一覧")[0].strip()

    # 「立候補予定者一覧」の見出し直後にリストがある
    section = soup.find("h2", string=lambda x: x and "立候補予定者一覧" in x)
    if not section:
        return []

    candidates: list[dict] = []
    for tag in section.find_all_next(["li", "p"], limit=200):
        text = tag.get_text(" ", strip=True)
        # 空行・注釈・見出しの終端などで終了
        if (not text) or text.startswith("＊") or "顔ぶれの見方" in text:
            break
        # 候補者行は「名前 年齢 党派現新…」という形
        parts = re.split(r"\s+", text.lstrip("●*◇・"))
        if len(parts) < 3 or not parts[1].isdigit():
            continue

        name = parts[0]
        age = parts[1]
        party_status = parts[2]
        # 「自現①」→「自」／「立新」→「立」など、先頭の党派だけを抽出
        m = re.match(r"([^\d現新前元]+)", party_status)
        party = m.group(1) if m else party_status

        candidates.append({
            "選挙区": district,
            "氏名": name,
            "年齢": age,
            "党派": party
        })

    return candidates

def main() -> None:
    all_rows: list[dict] = []

    for code in district_codes:
        url = f"{BASE}{code}.html"
        print(f"Scraping {url}")
        html = fetch(url)
        rows = parse_candidates(html, code)
        if not rows:
            print(f"  ! No candidates found for {code}")
        all_rows.extend(rows)
        time.sleep(0.5)  # サーバー負荷軽減

    if not all_rows:
        print("No data scraped. Aborting.")
        return

    # CSV 書き出し
    keys = ["選挙区", "氏名", "年齢", "党派"]
    with open("saninsen2025_candidates.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Saved saninsen2025_candidates.csv with {len(all_rows)} records.")

if __name__ == "__main__":
    main()
