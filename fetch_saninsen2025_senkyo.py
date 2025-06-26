# -*- coding: utf-8 -*-
"""
選挙ドットコム「第27回参議院議員選挙 2025年」から候補者情報を取得し
saninsen2025_candidates.csv を生成するスクリプト。

必要ライブラリ:
    pip install -r requirements.txt

使用例:
    python fetch_saninsen2025_senkyo.py
"""

import re
import csv
import time
import requests
from bs4 import BeautifulSoup
from pykakasi import kakasi

BASE = "https://go2senkyo.com/sangiin/20376"

_kakasi = kakasi()


def to_hiragana(text: str) -> str:
    """Return hiragana reading for given Japanese text."""
    return "".join(d["hira"] for d in _kakasi.convert(text))


def slugify_jp(text: str) -> str:
    """Romanize Japanese text and return a slug suitable for IDs."""
    romaji = "".join(d["hepburn"] for d in _kakasi.convert(text))
    romaji = romaji.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", romaji)
    return slug.strip("-")


def unify_party(name: str) -> str:
    """Normalize party name variations."""
    aliases = {
        "自民党": "自民",
        "立憲民主党": "立憲",
        "日本維新の会": "維新",
        "日本共産党": "共産",
        "れいわ新選組": "れいわ",
        "日本保守党": "日保",
        "無所属連合": "諸派",
        "その他": "諸派",
        "無所属": "無所属",
        "公明党": "公明",
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


def fetch(url: str, retry: int = 3, sleep: int = 2) -> str:
    """Get URL and return HTML text. Return empty string on failure."""
    for _ in range(retry):
        try:
            r = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (CandidateFetcher/1.0)"},
            )
            if r.status_code == 404:
                print(f"  ! {url} returned 404")
                return ""
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except Exception as e:
            print(f"Retrying {url} because {e}")
            time.sleep(sleep)
    print(f"Failed to fetch {url}. Skipping.")
    return ""


def get_list_paths() -> tuple[list[str], list[str]]:
    """Return lists of prefecture and hirei paths from the top page."""
    html = fetch(BASE)
    soup = BeautifulSoup(html, "html.parser")
    pref_paths = sorted({a["href"] for a in soup.find_all("a", href=True) if "/prefecture/" in a["href"]})
    hirei_paths = sorted({a["href"] for a in soup.find_all("a", href=True) if "/hirei_party/" in a["href"]})
    return pref_paths, hirei_paths


def extract_pref_name(html: str) -> str:
    """Return prefecture name from prefecture page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"name": "description"})
    text = meta["content"] if meta else soup.title.string if soup.title else ""
    if "選挙区" in text:
        return text.split("選挙区")[0].strip()
    return text.strip()


def parse_candidates(html: str, senkyoku: str, is_proportional: bool) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for sec in soup.select("section.m_senkyo_result_data"):
        a = sec.select_one("h2.m_senkyo_result_data_ttl a")
        if not a:
            continue
        kanji = a.find(string=True, recursive=False).strip()
        kana_tag = a.select_one("span.m_senkyo_result_data_kana")
        kana = kana_tag.get_text(strip=True) if kana_tag else ""
        yomi = to_hiragana(kana.replace(" ", "")) if kana else to_hiragana(kanji.split()[0])
        party_tag = sec.select_one("p.m_senkyo_result_data_circle")
        party = unify_party(party_tag.get_text(strip=True)) if party_tag else ""
        age_span = sec.select_one("p.m_senkyo_result_data_para span")
        age = ""
        if age_span:
            m = re.search(r"(\d+)", age_span.get_text())
            if m:
                age = m.group(1)
        senk = "比例" if is_proportional else senkyoku
        pref = "" if is_proportional else senkyoku
        cid = f"{slugify_jp(senk or 'proportional')}-{slugify_jp(kanji)}"
        rows.append({
            "id": cid,
            "todoufuken": pref,
            "senkyoku": senk,
            "seitou": party,
            "title": kanji,
            "yomi": yomi,
            "detail": f"{age}歳" if age else "",
            "age": age,
            "tubohantei": "",
            "tubonaiyou": "",
            "tuboURL": "",
            "uraganehantei": "",
            "uraganenaiyou": "",
            "uraganeURL": "",
        })
    return rows


def main() -> None:
    pref_paths, hirei_paths = get_list_paths()
    all_rows: list[dict] = []
    for path in pref_paths:
        url = path if path.startswith("http") else f"https://go2senkyo.com{path}"
        print(f"Scraping {url}")
        html = fetch(url)
        senkyoku = extract_pref_name(html) or path.rstrip("/").split("/")[-1]
        rows = parse_candidates(html, senkyoku, False)
        if not rows:
            print(f"  ! No candidates found for {path}")
        all_rows.extend(rows)
        time.sleep(0.5)
    for path in hirei_paths:
        url = path if path.startswith("http") else f"https://go2senkyo.com{path}"
        party_name = path.rstrip("/").split("/")[-2]  # not used but for slug
        print(f"Scraping {url}")
        html = fetch(url)
        rows = parse_candidates(html, party_name, True)
        if not rows:
            print(f"  ! No candidates found for {path}")
        all_rows.extend(rows)
        time.sleep(0.5)
    if not all_rows:
        print("No data scraped. Aborting.")
        return
    keys = [
        "id",
        "todoufuken",
        "senkyoku",
        "seitou",
        "title",
        "yomi",
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
