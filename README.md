# DCF Valuation App

企業価値評価（DCF法）を簡単に行えるWebアプリケーションです。

## 機能

- **EDINET CSV対応**: 上場企業の有価証券報告書CSVから自動データ抽出
- **Excelテンプレート**: 非上場企業向けの手動入力にも対応
- **株価自動取得**: Yahoo Finance APIから現在株価を取得
- **複数バリュエーション手法**:
  - DCF法（永久成長率法・Exit Multiple法）
  - マルチプル法（EV/EBITDA、PER）
- **感応度分析**: WACCと成長率の変動による株価変化を可視化
- **シナリオ比較**: Bull/Base/Bear 3シナリオ同時表示
- **Excel/PDF出力**: 分析結果のエクスポート

## 使い方

1. サイドバーからEDINET CSVまたはExcelテンプレートをアップロード
2. WACC構成要素・成長率などのパラメータを調整
3. 「データを適用」ボタンをクリック
4. 結果を確認し、必要に応じてExcel/PDFでダウンロード

## 技術スタック

- Python 3.9+
- Streamlit
- Pandas
- Plotly
- ReportLab (PDF生成)

## ライセンス

MIT License

## 作者

Kei | MBA | 元銀行員
