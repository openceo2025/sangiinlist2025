This repository scrapes Asahi Shimbun's '参院選2025 立候補予定者一覧' to build CSV data.

Known limitations of source data:
- The pages listing 2025 candidates currently show only kanji names, ages, and party status. They do **not** provide official name readings (ふりがな).
- Past election result blocks on the same pages include readings, but they correspond to previous elections.

Because official readings are missing, `fetch_saninsen2025_asahi.py` generates the `yomi` column using automatic kanji-to-hiragana conversion via pykakasi. If accurate readings become available, update the scraper accordingly.
