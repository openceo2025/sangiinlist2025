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
from pykakasi import kakasi

# ベース URL（B01〜B47 が各選挙区、C01 が比例区）
BASE = "https://www.asahi.com/senkyo/saninsen/koho/"

# 動的取得に失敗した際に用いるフォールバックのコード一覧
FALLBACK_CODES = [f"B{n:02d}" for n in range(1, 48)]
FALLBACK_CODES.remove("B32")  # 鳥取単独ページは存在しない
FALLBACK_CODES.append("C01")


_kakasi = kakasi()


def slugify_jp(text: str) -> str:
    """Romanize Japanese text and return a slug suitable for IDs."""
    romaji = "".join(d["hepburn"] for d in _kakasi.convert(text))
    romaji = romaji.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", romaji)
    return slug.strip("-")


def unify_party(name: str) -> str:
    """Normalize party name variations."""
    aliases = {
        "自": "自民",
        "自民党": "自民",
        "立": "立憲",
        "立憲民主党": "立憲",
        "維": "維新",
        "日本維新の会": "維新",
        "共": "共産",
        "共産党": "共産",
        "れ": "れいわ",
        "れいわ新選組": "れいわ",
        "保": "日保",
        "日本保守党": "日保",
        "諸": "諸派",
        "無所属連合": "諸派",
        "その他": "諸派",
        "無": "無所属",
        "公": "公明",
        "公明党": "公明",
        "社": "社民",
        "社民党": "社民",
        "国民民主党": "国民",
        "参政党": "参政",
        "みんなでつくる党": "みんつく",
        "NHK党": "N国",
        "再生の道": "再道",
        "チームみらい": "みらい",
        "日本改革党": "日改",
    }
    return aliases.get(name, name)


def get_district_codes() -> list[str]:
    """候補者一覧トップページから選挙区コードを抽出して返す。"""

    html = fetch(BASE)
    if not html:
        return FALLBACK_CODES

    soup = BeautifulSoup(html, "html.parser")
    codes: set[str] = set()
    for a in soup.find_all("a", href=True):
        m = re.search(r"/koho/([A-Z]\d{2})\.html", a["href"])
        if m:
            codes.add(m.group(1))

    if not codes:
        return FALLBACK_CODES

    return sorted(codes)

def fetch(url: str, retry: int = 3, sleep: int = 2) -> str:
    """指定 URL を取得して HTML 文字列を返す。失敗時は空文字を返す。"""

    for _ in range(retry):
        try:
            r = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (CandidateFetcher/1.0)"},
            )
            if r.status_code == 404:
                # ページが存在しない場合はスキップ
                print(f"  ! {url} returned 404")
                return ""
            r.raise_for_status()
            # 朝日新聞のページは UTF-8 で提供されているが、
            # requests が誤判定する場合があるため明示的に指定する
            r.encoding = "utf-8"
            return r.text
        except Exception as e:
            print(f"Retrying {url} because {e}")
            time.sleep(sleep)

    print(f"Failed to fetch {url}. Skipping.")
    return ""

def parse_candidates(html: str, default_district: str) -> list[dict]:
    """Return candidate info list for one page in csv2giin.py compatible format."""
    soup = BeautifulSoup(html, "html.parser")

    # ページタイトルから選挙区名を補足（例: "参院選東京 候補者一覧"）
    h1 = soup.select_one(".PageTitle .Title h1") or soup.find("h1")
    district = default_district
    if h1:
        m = re.search(r"参院選\s*(.+?)候補者一覧", h1.get_text(strip=True))
        if m:
            district = m.group(1).split("選挙区")[0].strip()

    # 新サイト構造： <div class="snkKohoInfoBox" data-type="yoteisha"> 内の li
    containers = soup.find_all("div", class_="snkKohoInfoBox", attrs={"data-type": "yoteisha"})
    tags: list[tuple[BeautifulSoup, str]] = []
    if containers:
        for c in containers:
            h3 = c.select_one(".snkTitle h3")
            container_party = h3.get_text(strip=True) if h3 else ""
            for li in c.find_all("li"):
                tags.append((li, container_party))
    else:
        # 旧構造にフォールバック
        section = soup.find("h2", string=lambda x: x and "立候補予定者一覧" in x)
        if not section:
            return []
        for tag in section.find_all_next(["li", "p"], limit=200):
            text = tag.get_text(" ", strip=True)
            if (not text) or text.startswith("＊") or "顔ぶれの見方" in text:
                break
            tags.append((tag, ""))

    candidates: list[dict] = []
    for tag, container_party in tags:
        text = tag.get_text(" ", strip=True).lstrip("●*◇・")
        parts = re.split(r"\s+", text)

        # 年齢の位置を特定（数字のみのトークン）
        age_idx = next((i for i, p in enumerate(parts) if p.isdigit()), -1)
        if age_idx == -1 or age_idx + 1 >= len(parts):
            continue
        name = "".join(parts[:age_idx])
        age = parts[age_idx]
        party_status = parts[age_idx + 1]

        if container_party:
            party = container_party
        else:
            # "自現①"->"自" etc. Extract first party code.
            m = re.match(r"([^\d現新前元]+)", party_status)
            party = m.group(1) if m else party_status
        party = unify_party(party)

        is_proportional = "比例" in district or default_district.startswith("C")
        senkyoku = "比例" if is_proportional else district
        todoufuken = "" if is_proportional else district

        candidate_id = f"{slugify_jp(senkyoku or 'proportional')}-{slugify_jp(name)}"

        candidates.append({
            "id": candidate_id,
            "todoufuken": todoufuken,
            "senkyoku": senkyoku,
            "seitou": party,
            "title": name,
            "detail": f"{age}歳",
            "age": age,
            "tubohantei": "",
            "tubonaiyou": "",
            "tuboURL": "",
            "uraganehantei": "",
            "uraganenaiyou": "",
            "uraganeURL": "",
        })

    return candidates

def main() -> None:
    all_rows: list[dict] = []

    district_codes = get_district_codes()
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

    # CSV 出力 (csv2giin.py 互換フォーマット)
    keys = [
        "id",
        "todoufuken",
        "senkyoku",
        "seitou",
        "title",
        "detail",
        "age",
        "tubohantei",
        "tubonaiyou",
        "tuboURL",
        "uraganehantei",
        "uraganenaiyou",
        "uraganeURL",
    ]
    with open("saninsen2025_candidates.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Saved saninsen2025_candidates.csv with {len(all_rows)} records.")

if __name__ == "__main__":
    main()
