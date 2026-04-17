# 顧客別納入分析システム

Access（`.accdb`）の納入実績を参照し、検索・集計・年次予測・グラフ表示・Excel 出力までをまとめて扱う Windows 業務アプリです。  
現在の GUI 実装は `tkinter` 版です。配布先 PC でも起動しやすいことを優先しています。

## 主な機能

- 期間・顧客・品番・集計単位による納入実績検索
- 年別・月別推移グラフの表示
- 年次予測の算出
- 予測算出詳細の説明表示
- 一覧および予測結果の Excel 出力
- Access DB の外部指標を使った予測補助

## 技術スタック

- Python 3.10 以上
- GUI: `tkinter`
- DB 接続: `pyodbc`
- 集計・予測: `pandas` / `numpy`
- グラフ: `matplotlib`
- Excel 出力: `openpyxl`
- 日付選択: `tkcalendar`
- 配布: `PyInstaller`

## 起動方法

```powershell
cd <リポジトリのルート>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```

補足:
- `app/main.py` が起動点です。
- `app/tk_app.py` に tkinter 版の画面実装があります。
- Access の保存場所を変える場合は `CDA_ACCESS_DB` 環境変数を設定します。

## 配布用 exe の作成

```powershell
pip install pyinstaller
.\build_exe.ps1
```

既定は `onefile` 配布です。生成されるのは単体の `.exe` です。

## フォルダ構成

```text
customer_delivery_analytics/
├─ app/
│  ├─ main.py
│  ├─ tk_app.py
│  ├─ config/
│  ├─ db/
│  ├─ infrastructure/
│  └─ service/
├─ docs/
├─ requirements.txt
├─ build_exe.ps1
├─ README.md
└─ .gitignore
```

補足:
- `app/ui/` には旧 PySide6 実装が残っていますが、現行の起動経路では使っていません。
- `web_date_picker_demo.py` と `pyi_rth_cda_dateutil.py` は整理済みです。

## 配布先 PC で必要なもの

- Microsoft Access Database Engine または Access 用 ODBC ドライバ
- Access の `.accdb` へ到達できるネットワーク権限
- 外部指標を更新する場合はインターネット接続

## トラブルシュート

| 現象 | 確認事項 |
|---|---|
| Access に接続できない | ODBC の 32/64 bit を確認、`CDA_ACCESS_DB` のパス確認、共有フォルダ権限確認 |
| 画面の表示が崩れる | `pip install -r requirements.txt` の再実行、`matplotlib` / `tkcalendar` の導入確認 |
| exe が起動しない | `.\build_exe.ps1` を再実行して再ビルド |

## ライセンス

利用ライブラリは各パッケージのライセンスに従います。社内配布ルールやデータ取り扱いルールもあわせて確認してください。
