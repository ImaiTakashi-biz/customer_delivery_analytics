# 顧客別納入分析システム（customer_delivery_analytics）

営業部向けの納入実績確認・年次予測・Excel 出力用 Windows デスクトップアプリです。
Access（`.accdb`）を **参照専用** で読み取り、**起動時に全件ロードはしません**（検索時に SQL で絞り込み取得します）。

## 仕様書

実装の基準とした仕様書のパスは次のとおりです。

- `docs/specification_updated.md`

## 技術スタック

- Python 3.10+ 推奨
- GUI: PySide6 / DB: pyodbc / 集計: pandas / グラフ: matplotlib / Excel: openpyxl / exe: PyInstaller

## 実行手順（開発時）

```powershell
cd C:\Users\SEIZOU-20\PycharmProjects\customer_delivery_analytics
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```

Access パスを上書きする場合: 環境変数 `CDA_ACCESS_DB` に accdb のフルパスを設定。

## exe 化

```powershell
pip install pyinstaller
.\build_exe.ps1
```

出力: `dist\顧客別納入分析システム\顧客別納入分析システム.exe`

## 補足

- `app/main.py` では、一部環境で PySide6（Shiboken）と pandas の import 順が衝突する場合があるため、**先に pandas を import してから Qt を読み込む**ようにしています。
- 既定の Access パスは `app/config/settings.py` の `DEFAULT_ACCESS_DB_PATH`（仕様どおりの UNC）です。

## フォルダ構成（抜粋）

```
customer_delivery_analytics/
├─ app/（main.py, ui/, db/, service/, utils/, config/）
├─ requirements.txt
├─ build_exe.ps1
├─ README.md
└─ docs/specification_updated.md
```

## 機能

- 実績一覧（期間・顧客・品番・集計単位）、Excel 出力、年別グラフ、メイン画面の年次予測（検索明細ベース・線形トレンド・Excel・グラフ）
