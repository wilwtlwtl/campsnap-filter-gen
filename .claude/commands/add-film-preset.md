# フィルムプリセット追加スキル

引数で指定されたフィルム名のサンプル写真を収集し、スナップ・風景の2プリセットを生成してアプリに追加する。
安定性スコアが低い場合は追加検索・ダウンロードを行い、最大2回までリトライする。

## 引数

`$ARGUMENTS` にフィルム名が入る（例: `Kodak Portra 400`、`Fujifilm Pro 400H`）。

## 定数

- **安定性の閾値**: 40（これを下回るとリトライ対象）
- **最大リトライ回数**: 2回
- **1カテゴリあたりの目標枚数**: 初回3〜5枚、リトライごとに3枚追加（上限12枚）

---

## 手順

### STEP 1 — サンプル写真を検索・ダウンロード（初回）

1. WebSearchで以下の2クエリを**並行**検索する:
   - `{フィルム名} sample photos street snap film photography`
   - `{フィルム名} sample photos landscape nature film photography`

2. 検索結果から画像を多く掲載しているレビューサイト（casualphotophile, thedarkroom, myfavouritelens, lenslurker など）を選び、WebFetchで各ページの画像URL（img src）を収集する。

3. 収集した画像URLから以下のフォルダへダウンロードする:
   - スナップ系: `C:\Users\sakamoto\{フィルム名_snake_case}_samples\snap\`
   - 風景系:     `C:\Users\sakamoto\{フィルム名_snake_case}_samples\landscape\`
   - 各カテゴリ3〜5枚をcurlでダウンロード
   - ダウンロード後にファイルサイズが 10KB 未満のものは削除（ダウンロード失敗と見なす）

---

### STEP 2 — プリセット生成スクリプトを作成して実行

`build_ektar_presets.py` を参考に、今回のフィルム用スクリプト `build_{snake_case}_presets.py` を作成する。

スクリプトの要件:
- `SAMPLE_DIR` を今回のサンプルフォルダに変更
- プリセット名を `{フィルム名}_スナップ` / `{フィルム名}_風景` にする
- 解析は `AdvancedAnalyzer` を使用（画像間クロス比較で平均を取る方式）
- print文に絵文字・特殊文字を使わない（Windows cp932対策）
- スクリプト実行後、各プリセットの安定性スコアをコンソールから読み取る

---

### STEP 3 — 安定性チェック＆リトライ（最大2回）

生成された各プリセットの安定性スコアを確認し、**40未満のカテゴリ**についてリトライを行う。

**リトライの上限は2回。** 2回試みても改善しない場合はリトライを打ち切り、STEP 4へ進む。

#### リトライ時の追加検索クエリ（毎回別のキーワードを使う）

| リトライ回数 | スナップ用クエリ | 風景用クエリ |
|---|---|---|
| 1回目 | `{フィルム名} film review sample images city` | `{フィルム名} film review sample images outdoor` |
| 2回目 | `{フィルム名} shot on film flickr examples` | `{フィルム名} shot on film nature examples` |

#### リトライの手順

1. 上記クエリでWebSearchを実行し、**初回とは別のサイト**からWebFetchで画像URLを収集する
2. 各カテゴリ3枚を追加でダウンロード（既存ファイルとは別名で保存）
3. スクリプトを再実行（フォルダ内の全画像で再解析される）
4. 安定性スコアを再確認

#### 打ち切り判定

2回リトライ後も安定性スコアが40未満の場合：
- そのまま現在の値でプリセットを保存する
- STEP 5の報告で「このフィルムは撮影条件によって色の傾向が大きく異なるため、参考程度に使ってください」と伝える

---

### STEP 4 — default_presets.json を更新

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

---

### STEP 5 — コミット＆プッシュ

```bash
cd /c/Users/sakamoto/campsnap-filter-gen
git add default_presets.json build_{snake_case}_presets.py
git commit -m "{フィルム名}スナップ・風景プリセットを追加"
git push origin main
```

---

### STEP 6 — 結果を報告

以下の情報をまとめてユーザーに報告する:

- 追加したプリセット名
- 各プリセットの主要パラメータ（brightness / contrast / saturation / GammaR/G/B）
- 安定性スコアとその解釈:
  - 70以上: 良好（参考写真の傾向が一致していた）
  - 40〜69: 普通（多少のばらつきあり）
  - 39以下: 低い（写真ごとの差が大きく、平均値のため精度は限定的）
- リトライを行った場合はその回数と改善結果
- Streamlit Community Cloudへの反映には1〜2分かかることを伝える

---

## 注意事項

- サンプル写真は著作権のある画像のため、解析目的のみに使用する
- ダウンロード先フォルダはリポジトリ外（`C:\Users\sakamoto\` 直下）に置く
- `presets.json` はgitignoreされているため触らない。`default_presets.json` のみを更新する
- 安定性スコアが低い根本原因が「フィルム自体の特性」である場合（例: CineStill 800Tは夜景・昼間で色が大きく異なる）は、いくらリトライしても改善しない。2回で打ち切ることで無限ループを防ぐ
