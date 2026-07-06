# ペダルボード・プランナー

Pedaltrain の Pedalboard Planner のような、仮想エフェクターボードを実寸スケールで組めるWebアプリ。
本家に少ない**国産エフェクター**(BOSS / Ibanez / Maxon / One Control / Free The Tone / Vemuram / Providence / Leqtique / Limetone Audio / Ovaltone / Effects Bakery / Bananana Effects / Sobbat など)を中心に約120種を収録。

## URL

https://nino-msip.github.io/gita-shiban/pedal-board-planner/

## 機能

- **ボード選択**: Pedaltrain 主要11サイズ + すのこ風 + カスタムサイズ(mm指定)
- **実寸配置**: ペダルは実寸(mm)スケールで描画。ドラッグ移動 / 90°回転 / 複製 / 削除
- **ペダルライブラリ**: ブランド絞り込み + 検索。カスタムペダル(名前・寸法・色・消費電流)も追加可能
- **サマリー表示**: 台数 / 合計消費電流(mA・パワーサプライ選びの目安) / ボード占有率
- **保存**: localStorage に自動保存 + 名前付き保存(30件)
- **共有**: レイアウトをURLに埋め込んで共有
- **書き出し**: PNG画像 / JSONファイル(読み込みも対応)
- スマホ・タッチ操作対応

## データについて

寸法(W×D mm)・消費電流(mA)はカタログ値等をもとにした**概算値**です。
ペダルの追加は `index.html` 内の `PEDALS` 配列に1行足すだけ:

```js
// [ブランド, 名前, タイプ, 幅mm, 奥行mm, 消費電流mA, 色]
['BOSS','SD-1 Super OverDrive','OD',73,129,5,'#e8c020'],
```

タイプ一覧は同ファイルの `TYPE_LABEL` を参照。

## 構成

依存ライブラリなしの単一HTMLファイル (`index.html`)。ビルド不要。
