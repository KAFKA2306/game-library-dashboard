# Game Library Dashboard

Static GitHub Pages dashboard for a 48-title game library.

- Live GitHub Pages: https://kafka2306.github.io/game-library-dashboard/
- Data: `data/game-library.json`
- Sources: Steam Store app metadata, Temple Gates Games, Rio Grande Games
- Dashboard: `index.html`

## 因果・証拠オントロジー

上位システムは `GameLibraryCatalogSystem` です。

```text
公式・ストアのメタデータ
→ タイトル／版／プラットフォームの同定
→ 正規化
→ 派生分類
→ 重複・競合判定
→ データセット生成
→ ダッシュボード公開
```

公式ジャンルとプレイモードは、デザインファミリーや派生タグとは別の主張型として保存します。異なる版やプラットフォームを自動統合せず、出典、取得時刻、変換規則が欠ける値は `UNKNOWN` または `flag_conflict` とします。

- [プロジェクト・オントロジー](ontology/project.yaml)
- [共通因果・証拠オントロジー](https://github.com/KAFKA2306/know/blob/main/ontology/causal-evidence-core.yaml)

The detailed ontology groups games by design family, official genres, play modes, and derived tags while preserving provenance and identity boundaries.