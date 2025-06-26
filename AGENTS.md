This repository scrapes candidate data for the 2025 House of Councillors election from go2senkyo.com (選挙ドットコム).

The site provides candidate names in both kanji and kana. The script converts the kana to hiragana using pykakasi to populate the `yomi` column.

Run `python fetch_saninsen2025_senkyo.py` to generate `saninsen2025_candidates.csv`.
