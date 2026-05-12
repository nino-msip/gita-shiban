#!/usr/bin/env node
/**
 * Life OS → Notion 同期スクリプト
 * 使い方: node notion-sync.js [notion-queue.json のパス]
 *
 * Notionデータベースに必要なプロパティ:
 *   タスクDB    : Name(title) / Category(select) / Due(date) / Status(select) / Notes(rich_text)
 *   ギターログDB: Name(title) / Date(date) / Minutes(number) / Type(select) / Notes(rich_text)
 *   体重ログDB  : Name(title) / Date(date) / Weight(number) / Notes(rich_text)
 *   家計DB      : Name(title) / Date(date) / Amount(number) / Type(select) / Category(select)
 */

const https = require('https');
const fs    = require('fs');
const path  = require('path');

const queueFile = process.argv[2] || path.join(__dirname, 'notion-queue.json');

if (!fs.existsSync(queueFile)) {
  console.error(`❌ ファイルが見つかりません: ${queueFile}`);
  console.error('   Life OS アプリの設定 → 「同期キューを出力」でファイルを生成してください');
  process.exit(1);
}

const queue = JSON.parse(fs.readFileSync(queueFile, 'utf8'));
const TOKEN = process.env.NOTION_TOKEN || queue.token;

if (!TOKEN) {
  console.error('❌ Notion Token が設定されていません');
  console.error('   環境変数: NOTION_TOKEN=secret_xxx node notion-sync.js');
  console.error('   または Life OS 設定に token を入力して再度エクスポートしてください');
  process.exit(1);
}

function notionRequest(method, endpoint, body) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const req = https.request({
      hostname: 'api.notion.com',
      path: `/v1/${endpoint}`,
      method,
      headers: {
        'Authorization': `Bearer ${TOKEN}`,
        'Content-Type': 'application/json',
        'Notion-Version': '2022-06-28',
        ...(data ? { 'Content-Length': Buffer.byteLength(data) } : {})
      }
    }, res => {
      let raw = '';
      res.on('data', c => raw += c);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(raw) }); }
        catch { resolve({ status: res.statusCode, body: raw }); }
      });
    });
    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

async function createPage(dbId, properties) {
  if (!dbId) return null;
  const res = await notionRequest('POST', 'pages', {
    parent: { database_id: dbId },
    properties
  });
  if (res.status !== 200) {
    console.warn(`  ⚠️  Notion API エラー ${res.status}:`, JSON.stringify(res.body).slice(0, 120));
  }
  return res;
}

function title(text)   { return { title:     [{ text: { content: String(text) } }] }; }
function richText(t)   { return { rich_text: [{ text: { content: String(t || '') } }] }; }
function select(name)  { return { select: { name: String(name) } }; }
function date(d)       { return d ? { date: { start: d } } : undefined; }
function number(n)     { return n != null ? { number: Number(n) } : undefined; }

async function syncTasks() {
  const dbId = queue.tasksDb;
  if (!dbId || !queue.tasks?.length) { console.log('  タスクDB未設定またはデータなし — スキップ'); return; }
  console.log(`  📝 タスク: ${queue.tasks.length}件`);
  for (const t of queue.tasks) {
    const props = {
      Name:     title(t.name),
      Category: select(t.cat || 'general'),
      Status:   select(t.done ? '完了' : '未完了'),
    };
    if (t.date) props.Due   = date(t.date);
    if (t.note) props.Notes = richText(t.note);
    const r = await createPage(dbId, props);
    if (r?.status === 200) process.stdout.write('.');
  }
  console.log(' ✅');
}

async function syncGuitarLogs() {
  const dbId = queue.guitarDb;
  if (!dbId || !queue.guitarLogs?.length) { console.log('  ギターログDB未設定またはデータなし — スキップ'); return; }
  console.log(`  🎸 ギター練習ログ: ${queue.guitarLogs.length}件`);
  const typeLabel = { scale:'スケール', chord:'コード', song:'曲', theory:'音楽理論', improv:'アドリブ', tech:'テクニック', live:'ライブ', other:'その他' };
  for (const l of queue.guitarLogs) {
    const label = typeLabel[l.type] || l.type || 'その他';
    const props = {
      Name:    title(`${l.date} — ${l.minutes}分 ${label}`),
      Date:    date(l.date),
      Minutes: number(l.minutes),
      Type:    select(label),
    };
    if (l.note) props.Notes = richText(l.note);
    const r = await createPage(dbId, props);
    if (r?.status === 200) process.stdout.write('.');
  }
  console.log(' ✅');
}

async function syncDietLogs() {
  const dbId = queue.dietDb;
  if (!dbId || !queue.dietLogs?.length) { console.log('  体重ログDB未設定またはデータなし — スキップ'); return; }
  console.log(`  💪 体重ログ: ${queue.dietLogs.length}件`);
  for (const l of queue.dietLogs) {
    const props = {
      Name:   title(`${l.date} — ${l.weight}kg`),
      Date:   date(l.date),
      Weight: number(l.weight),
    };
    if (l.note) props.Notes = richText(l.note);
    const r = await createPage(dbId, props);
    if (r?.status === 200) process.stdout.write('.');
  }
  console.log(' ✅');
}

async function syncBudget() {
  const dbId = queue.budgetDb;
  if (!dbId || !queue.budgetEntries?.length) { console.log('  家計DB未設定またはデータなし — スキップ'); return; }
  console.log(`  💰 家計: ${queue.budgetEntries.length}件`);
  for (const e of queue.budgetEntries) {
    const sign = e.type === 'income' ? '+' : '-';
    const props = {
      Name:     title(`${e.date} ${e.cat} ${sign}¥${Number(e.amount).toLocaleString()}`),
      Date:     date(e.date),
      Amount:   number(e.amount),
      Type:     select(e.type === 'income' ? '収入' : '支出'),
      Category: select(e.cat || 'その他'),
    };
    if (e.note) props.Notes = richText(e.note);
    const r = await createPage(dbId, props);
    if (r?.status === 200) process.stdout.write('.');
  }
  console.log(' ✅');
}

(async () => {
  console.log('\n🔄 Life OS → Notion 同期開始');
  console.log(`   エクスポート日時: ${queue.exportedAt || '不明'}\n`);
  await syncTasks();
  await syncGuitarLogs();
  await syncDietLogs();
  await syncBudget();
  console.log('\n✅ 同期完了\n');
})().catch(e => { console.error('❌ エラー:', e.message); process.exit(1); });
