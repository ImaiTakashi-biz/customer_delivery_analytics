# 顧客別納入分析システム（customer_delivery_analytics）

営業・実務向けの **Windows デスクトップアプリ** です。Access（`.accdb`）の納入実績を **参照専用** で検索・集計し、**年次予測**・**グラフ**・**Excel 出力**まで一画面で扱えます。

- **起動時に全件ロードはしません**（検索時に SQL で絞り込み取得）。
- **exe は単一ファイル配布**可能（PyInstaller onefile）。同梱リソースは実行時に一時展開されます。

## 仕様書

- `docs/specification_updated.md`

## 主な機能

| 区分 | 内容 |
|------|------|
| 実績 | 期間・顧客・品番・集計単位での一覧表示 |
| グラフ | 年別・月別推移（matplotlib）、予測結果のグラフ |
| Excel | 一覧・年次予測結果の出力（openpyxl） |
| 年次予測 | 検索で取得した明細を年次集計し、**直線延長（最小二乗）**・**重み付き回帰（直近重視）**・**外部要因予測（IIP・景気動向指数 CI）** の 3 系統を算出 |
| 外部指標 | IIP / CI を公式ソースから取得し、SQLite（`%LOCALAPPDATA%\顧客別納入分析システム\`）にキャッシュ |
| UI | PySide6。Web 風テーブル・日付入力・予測算出の説明・詳細ダイアログ |

## 技術スタック

- **Python** 3.10 以上推奨（開発・ビルドは 3.12 で確認）
- **GUI**: PySide6  
- **DB 接続**: pyodbc（Access ODBC 必須）  
- **集計・予測**: pandas / scikit-learn（線形回帰）  
- **グラフ**: matplotlib（Qt バックエンド）  
- **Excel**: openpyxl  
- **パッケージング**: PyInstaller 6 系（`--paths` / onefile）

## 実行手順（開発時）

```powershell
cd <リポジトリのルートパス>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller
python -m app.main
```

- **Access のパス**を変える場合: 環境変数 `CDA_ACCESS_DB` に `.accdb` のフルパスを設定。
- 既定パスは `app/config/settings.py` の `DEFAULT_ACCESS_DB_PATH`（UNC）。社内環境に合わせて変更してください。

## exe 化・配布

```powershell
pip install pyinstaller
.\build_exe.ps1
```

| 項目 | 説明 |
|------|------|
| 出力 | `dist\顧客別納入分析システム.exe`（**単一 exe**。横に DLL 等は不要） |
| フォルダ版 | デバッグ用: `$env:CDA_FOLDER = "1"; .\build_exe.ps1` |
| スクリプト文字コード | `build_exe.ps1` は **UTF-8（BOM 付き）** 推奨（日本語 exe 名の文字化け防止） |
| ランタイムフック | リポジトリ直下の `pyi_rth_cda_dateutil.py` を `--runtime-hook` で同梱（pandas / dateutil / six と PySide6 の frozen 時衝突回避） |

### 配布先 PC で必要なもの

- **Microsoft Access Database Engine 等**、**Access 用 ODBC ドライバ**（64 位 exe なら 64 位ドライバ）。
- 既定の accdb へ **ネットワークで到達できること**、または各 PC で `CDA_ACCESS_DB` を設定。
- 外部指標の取得には **インターネット**（初回・月次更新時）。失敗時はキャッシュ利用を試みます。

## 補足（import 順・frozen）

- `app/main.py` では、PySide6（Shiboken）と **pandas / matplotlib → python-dateutil → six** の import が frozen 時に衝突しやすいため、**pandas と matplotlib の日付系を Qt より先に import** しています。
- exe ではさらに **`pyi_rth_cda_dateutil.py`** で `dateutil` 関連を先行ロードします。

## フォルダ構成（抜粋）

```
customer_delivery_analytics/
├─ app/
│   ├─ main.py              # エントリポイント
│   ├─ config/settings.py  # 定数・パス解決（frozen 時は _MEIPASS 対応）
│   ├─ db/                  # Access 接続
│   ├─ infrastructure/      # AppData パス・外部指標 SQLite
│   ├─ service/             # 集計・予測・Excel・外部指標取得
│   ├─ ui/                  # メイン画面・テーマ・ワーカー等
│   └─ utils/
├─ docs/                    # 仕様書・アイコン（icon.png / icon.ico）
├─ requirements.txt
├─ build_exe.ps1
├─ pyi_rth_cda_dateutil.py  # PyInstaller 用ランタイムフック（削除しないこと）
├─ web_date_picker_demo.py  # 日付 UI 検証用スクリプト（任意）
└─ README.md
```

ビルド中間物は `build\`、成果物は `dist\` に出力されます（`.gitignore` 対象）。

## トラブルシュート

| 現象 | 確認事項 |
|------|----------|
| exe 起動直後に `_SixMetaPathImporter` 等 | `build_exe.ps1` が `pyi_rth_cda_dateutil.py` を参照しているか、再ビルドしたか |
| Access に接続できない | ODBC インストール、64/32 位の一致、`CDA_ACCESS_DB`・ファイアウォール・UNC 権限 |
| ビルドした exe 名が文字化け | `build_exe.ps1` を UTF-8 BOM で保存してから再実行 |

## ライセンス・第三者素材

利用ライブラリは各パッケージのライセンスに従います。アイコン・仕様書の権利は社内ルールに従ってください。
