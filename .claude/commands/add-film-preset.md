# フィルムプリセット追加スキル

引数で指定されたフィルム名のサンプル写真を収集し、Ektar100と同じ手順でスナップ・風景の2プリセットを生成してアプリに追加する。

## 引数

`$ARGUMENTS` にフィルム名が入る（例: `Kodak Portra 400`、`Fujifilm Pro 400H`）。

## 手順

### STEP 1 — サンプル写真を検索・ダウンロード

1. WebSearchで以下の2クエリを並行検索する:
   - `{フィルム名} sample photos street snap film photography`
   - `{フィルム名} sample photos landscape nature film photography`

2. 検索結果から画像を多く掲載しているレビューサイト（casualphotophile, thedarkroom, myfavouritelens, lenslurker など）を選び、WebFetchで各ページの画像URL（img src）を収集する。

3. 収集した画像URLから以下のフォルダへダウンロードする:
   - スナップ系: `C:\Users\sakamoto\{フィルム名_snake_case}_samples\snap\`
   - 風景系:     `C:\Users\sakamoto\{フィルム名_snake_case}_samples\landscape\`
   - 各カテゴリ最低3枚（最大5枚）をcurlでダウンロード
   - ダウンロード後にファイルサイズが 10KB 未満のものは削除（ダウンロード失敗と見なす）

### STEP 2 — プリセット生成スクリプトを作成して実行

`build_ektar_presets.py` を参考に、今回のフィルム用スクリプト `build_{snake_case}_presets.py` を作成する。

スクリプトの要件:
- `SAMPLE_DIR` を今回のサンプルフォルダに変更
- プリセット名を `{フィルム名}_スナップ` / `{フィルム名}_風景` にする
- 解析は `AdvancedAnalyzer` を使用（画像間クロス比較で平均を取る方式）
- print文に絵文字・特殊文字を使わない（Windows cp932対策）

スクリプトを実行し、生成されたパラメータをコンソールで確認する。

### STEP 3 — default_presets.json を更新

スクリプト実行後、`default_presets.json` に新しい2プリセットが追加されていることを確認する。
追加されていない場合は手動でJSONを編集して追記する。

JSONの形式:
```json
"{フィルム名}_スナップ": {
  "params": {"Brightness": X, "Contrast": X, "Saturation": X, "Hue": 0,
             "GammaR": X, "GammaG": X, "GammaB": X},
  "meta": {"n_images": N, "stability": N,
           "description": "{フィルム名} / 街・スナップ写真から生成"}
},
"{フィルム名}_風景": {
  "params": {"Brightness": X, "Contrast": X, "Saturation": X, "Hue": 0,
             "GammaR": X, "GammaG": X, "GammaB": X},
  "meta": {"n_images": N, "stability": N,
           "description": "{フィルム名} / 風景写真から生成"}
}
```

### STEP 4 — コミット＆プッシュ

```bash
cd /c/Users/sakamoto/campsnap-filter-gen
git add default_presets.json build_{snake_case}_presets.py
git commit -m "{フィルム名}スナップ・風景プリセットを追加"
git push origin main
```

### STEP 5 — 結果を報告

以下の情報をまとめてユーザーに報告する:
- 追加したプリセット名
- 各プリセットの主要パラメータ（brightness / contrast / saturation / GammaR/G/B）
- 安定性スコアとその解釈（70以上=良好、40〜69=普通、39以下=画像のばらつきが大きい）
- Streamlit Community Cloudへの反映には1〜2分かかることを伝える

## 注意事項

- サンプル写真は著作権のある画像のため、解析目的のみに使用する
- ダウンロード先フォルダはリポジトリ外（`C:\Users\sakamoto\` 直下）に置く
- `presets.json` はgitignoreされているため触らない。`default_presets.json` のみを更新する
- 風景写真は撮影条件のばらつきが大きく安定性スコアが低くなりやすい。スコアが30を下回る場合はその旨をユーザーに伝える
