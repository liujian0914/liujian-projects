// 通用题库系统（多题库版）端到端测试
const { spawn } = require("child_process");
const fs = require("fs");
const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const PORT = 9340;
const PROFILE = "D:/AndroidBuild/vprof5";
const URL = "file:///D:/题库系统/index.html";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const res = [];
const ok = (n, c, e) => { res.push([n, !!c]); console.log((c ? "PASS  " : "FAIL  ") + n + (c ? "" : "  -> " + (e === undefined ? "" : e))); };

const Q = (id, type, ch, no, stem, opts, ans) => ({
  id, type, chapter: ch, number: no, stem,
  options: opts.map((t, i) => ({ key: String.fromCharCode(65 + i), text: t })),
  answer: ans,
});

const BANK1 = {
  format: "qbank", version: "1.0",
  meta: { id: "test-bank", title: "测试题库甲", edition: "T1" },
  chapters: [{ id: "ch1", name: "第一章 测试", order: 1 }, { id: "ch2", name: "第二章 测试", order: 2 }],
  questions: [
    Q("ch1-single-1", "single", "ch1", 1, "单选：正确的是？", ["甲", "乙", "丙"], ["B"]),
    Q("ch1-multi-1", "multi", "ch1", 2, "多选：全选对", ["a", "b", "c", "d"], ["A", "B", "D"]),
    Q("ch1-indef-1", "indefinite", "ch1", 3, "不定项：可能一个或多个", ["a", "b", "c", "d"], ["C"]),
    Q("ch1-indef-2", "indefinite", "ch1", 4, "不定项：多个答案", ["a", "b", "c"], ["A", "C"]),
    Q("ch1-judge-1", "judge", "ch1", 5, "判断：这句话对。", ["正确", "错误"], ["A"]),
    Q("ch2-single-1", "single", "ch2", 1, "第二章单选", ["x", "y"], ["A"]),
    Q("ch2-multi-7", "multi", "ch2", 7, "第二章第7题", ["1", "2", "3", "4"], ["A", "B", "D"]),
  ],
};

const BANK2 = {
  format: "qbank", version: "1.0",
  meta: { id: "test-bank-2", title: "测试题库乙", edition: "T2" },
  chapters: [],
  questions: [Q("q-single-1", "single", null, 1, "无章节题", ["对", "错"], ["A"])],
};

const BANK3 = {
  format: "qbank", version: "1.0",
  meta: { id: "third-bank", title: "测试题库丙" },
  chapters: [{ id: "s1", name: "唯一一章" }],
  questions: [Q("s1-indef-1", "indefinite", "s1", 1, "丙题库不定项", ["a", "b", "c"], ["B", "C"])],
};

async function main() {
  if (fs.existsSync(PROFILE)) fs.rmSync(PROFILE, { recursive: true, force: true });
  const child = spawn(EDGE, ["--headless=new", "--disable-gpu", "--remote-debugging-port=" + PORT,
    "--user-data-dir=" + PROFILE, "--window-size=1280,900", "about:blank"], { stdio: "ignore" });

  let t = null;
  for (let i = 0; i < 60; i++) {
    try { const r = await fetch(`http://127.0.0.1:${PORT}/json/list`); t = await r.json(); if (t.length) break; } catch (e) {}
    await sleep(250);
  }
  const ws = new WebSocket(t.find((x) => x.type === "page").webSocketDebuggerUrl);
  let id = 0; const pd = new Map();
  const dialogs = [];
  await new Promise((r) => (ws.onopen = r));
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pd.has(m.id)) { pd.get(m.id)(m.result); pd.delete(m.id); }
    else if (m.method === "Page.javascriptDialogOpening") {
      dialogs.push(m.params.message);
      const i = ++id; pd.set(i, () => {});
      ws.send(JSON.stringify({ id: i, method: "Page.handleJavaScriptDialog", params: { accept: true } }));
    }
  };
  const send = (me, pa) => new Promise((r) => { const i = ++id; pd.set(i, r); ws.send(JSON.stringify({ id: i, method: me, params: pa || {} })); });
  const ev = async (x) => {
    const r = await send("Runtime.evaluate", { expression: x, returnByValue: true });
    if (r.exceptionDetails) return "EXC:" + JSON.stringify(r.exceptionDetails.exception && r.exceptionDetails.exception.description);
    return r.result.value;
  };

  await send("Page.enable"); await send("Runtime.enable");
  await send("Page.navigate", { url: URL }); await sleep(900);
  await ev(`localStorage.setItem('qbank.banks.v2', ${JSON.stringify(JSON.stringify({ "test-bank": BANK1, "test-bank-2": BANK2 }))});
            localStorage.removeItem('qbank.records.v2'); localStorage.removeItem('qbank.cur.v2');`);
  await send("Page.navigate", { url: URL }); await sleep(1100);

  // ---------- 开头界面 ----------
  ok("开头界面显示", (await ev("document.querySelector('#vBanks').classList.contains('hide')")) === false);
  ok("题库列表 2 套", (await ev("document.querySelectorAll('#vBanks .bank').length")) === 2,
     await ev("document.querySelectorAll('#vBanks .bank').length"));
  const listTxt = await ev("document.querySelector('#bankList').innerText");
  ok("两套题库都在列表里", listTxt.indexOf("测试题库甲") >= 0 && listTxt.indexOf("测试题库乙") >= 0);
  ok("未进入题库时练习页隐藏", (await ev("document.querySelector('#vHome').classList.contains('hide')")) === true);
  ok("开头界面不显示返回键", (await ev("document.querySelector('#btnHome').style.display")) === "none");

  // ---------- 进入题库甲 ----------
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(500);
  ok("进入题库甲", (await ev("document.querySelector('#vHome').classList.contains('hide')")) === false);
  ok("题库甲标题正确", (await ev("document.querySelector('#bankTitle').textContent")) === "测试题库甲");
  ok("题库甲 7 题", (await ev("document.querySelector('#stDone').textContent")) === "0 / 7",
     await ev("document.querySelector('#stDone').textContent"));
  ok("章节 2 个", (await ev("document.querySelectorAll('#chList [data-ch]').length")) === 2);

  // ---------- 四种题型 ----------
  await ev("document.querySelectorAll('#chList [data-ch]')[0].click()"); await sleep(350);
  ok("第一章 5 题", (await ev("document.querySelector('#navPos').textContent")) === "1 / 5");
  await ev("document.querySelectorAll('#qOpts .opt')[0].click()"); await sleep(250);
  ok("单选答错判分", (await ev("document.querySelector('#qFb .fb').innerText")).indexOf("答错了") >= 0);
  ok("错选被记下", (await ev("document.querySelector('#qFb .wopts').innerText")).indexOf("A") >= 0);

  await ev("document.querySelector('#btnNext').click()"); await sleep(250);
  await ev("document.querySelectorAll('#qOpts .opt')[0].click()"); await sleep(80);
  await ev("document.querySelectorAll('#qOpts .opt')[1].click()"); await sleep(80);
  await ev("document.querySelector('#btnSubmit').click()"); await sleep(250);
  ok("多选少选判错", (await ev("document.querySelector('#qFb .fb').innerText")).indexOf("答错了") >= 0);
  await ev("document.querySelector('#btnRedo').click()"); await sleep(150);
  await ev("document.querySelectorAll('#qOpts .opt')[0].click()"); await sleep(60);
  await ev("document.querySelectorAll('#qOpts .opt')[1].click()"); await sleep(60);
  await ev("document.querySelectorAll('#qOpts .opt')[3].click()"); await sleep(60);
  await ev("document.querySelector('#btnSubmit').click()"); await sleep(250);
  ok("多选 ABD 判对", (await ev("document.querySelector('#qFb .fb').innerText")).indexOf("答对了") >= 0);

  await ev("document.querySelector('#btnNext').click()"); await sleep(250);
  ok("不定项题型标签", (await ev("document.querySelector('#qHead').innerText")).indexOf("不定项") >= 0);
  await ev("document.querySelectorAll('#qOpts .opt')[2].click()"); await sleep(100);
  await ev("document.querySelector('#btnSubmit').click()"); await sleep(250);
  ok("不定项单答案判对", (await ev("document.querySelector('#qFb .fb').innerText")).indexOf("答对了") >= 0);

  await ev("document.querySelector('#btnNext').click()"); await sleep(250);
  await ev("document.querySelectorAll('#qOpts .opt')[0].click()"); await sleep(80);
  await ev("document.querySelector('#btnSubmit').click()"); await sleep(250);
  ok("不定项漏选判错", (await ev("document.querySelector('#qFb .fb').innerText")).indexOf("答错了") >= 0);
  await ev("document.querySelector('#btnRedo').click()"); await sleep(120);
  await ev("document.querySelectorAll('#qOpts .opt')[0].click()"); await sleep(60);
  await ev("document.querySelectorAll('#qOpts .opt')[2].click()"); await sleep(60);
  await ev("document.querySelector('#btnSubmit').click()"); await sleep(250);
  ok("不定项 AC 判对", (await ev("document.querySelector('#qFb .fb').innerText")).indexOf("答对了") >= 0);

  await ev("document.querySelector('#btnNext').click()"); await sleep(250);
  ok("判断题两个选项", (await ev("document.querySelectorAll('#qOpts .opt').length")) === 2);
  await ev("document.querySelectorAll('#qOpts .opt')[0].click()"); await sleep(250);
  ok("判断题判对", (await ev("document.querySelector('#qFb .fb').innerText")).indexOf("答对了") >= 0);

  await ev(`(()=>{const t=document.querySelector('#qNote');t.value='笔记第一行\\n第二行';t.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await sleep(800);
  await ev("document.querySelector('#btnFlag').click()"); await sleep(200);

  // ---------- 记录结构 ----------
  const recAll = await ev("JSON.parse(localStorage.getItem('qbank.records.v2'))");
  const recA = recAll["test-bank"] || {};
  ok("记录按题库分开存", !!recAll["test-bank"]);
  ok("另一题库暂无记录", !recAll["test-bank-2"] || Object.keys(recAll["test-bank-2"]).length === 0);
  ok("单选错误次数=1", (recA["ch1-single-1"] || {}).wrong === 1);
  ok("错选分布 A×1", JSON.stringify((recA["ch1-single-1"] || {}).wo) === '{"A":1}',
     JSON.stringify((recA["ch1-single-1"] || {}).wo));
  ok("多选历史 2 条", ((recA["ch1-multi-1"] || {}).h || []).length === 2);
  ok("笔记已存", ((recA["ch1-judge-1"] || {}).note || "").indexOf("笔记第一行") >= 0);
  ok("标记已存", (recA["ch1-judge-1"] || {}).flag === 1);

  // ---------- 逐级返回 ----------
  await ev("document.querySelector('#btnHome').click()"); await sleep(450);
  ok("答题页返回题库首页", (await ev("document.querySelector('#vHome').classList.contains('hide')")) === false &&
     (await ev("document.querySelector('#vBanks').classList.contains('hide')")) === true);
  await ev("document.querySelector('#btnHome').click()"); await sleep(450);
  ok("再返回到题库列表", (await ev("document.querySelector('#vBanks').classList.contains('hide')")) === false);
  const cardTxt = await ev("document.querySelector('.bank[data-id=\"test-bank\"]').innerText");
  ok("列表卡片刷新为 5 / 7", cardTxt.indexOf("5 / 7") >= 0, cardTxt.replace(/\n/g, " "));
  ok("列表头部恢复题库系统", (await ev("document.querySelector('#hdTitle').textContent")) === "题库系统");

  // ---------- 题库乙独立 ----------
  await ev("document.querySelector('.bank[data-id=\"test-bank-2\"]').click()"); await sleep(500);
  ok("切到题库乙", (await ev("document.querySelector('#bankTitle').textContent")) === "测试题库乙");
  ok("题库乙 1 题且无进度", (await ev("document.querySelector('#stDone').textContent")) === "0 / 1");
  ok("无章节归入未分章", (await ev("document.querySelector('#chList').innerText")).indexOf("未分章") >= 0);
  await ev("document.querySelectorAll('#chList [data-ch]')[0].click()"); await sleep(300);
  await ev("document.querySelectorAll('#qOpts .opt')[0].click()"); await sleep(250);
  ok("题库乙答题正常", (await ev("document.querySelector('#qFb .fb').innerText")).indexOf("答对了") >= 0);
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('#btnHome').click()"); await sleep(450);
  const t1 = await ev("document.querySelector('.bank[data-id=\"test-bank\"]').innerText");
  const t2 = await ev("document.querySelector('.bank[data-id=\"test-bank-2\"]').innerText");
  ok("两套题库进度互不影响", t1.indexOf("5 / 7") >= 0 && t2.indexOf("1 / 1") >= 0, t1 + " | " + t2);

  // ---------- 导入第三套 ----------
  await ev(`(()=>{
    const b=${JSON.stringify(JSON.stringify(BANK3))};
    const blob=new Blob([b],{type:'application/json'});
    const f=new File([blob],'third.qbank.json',{type:'application/json'});
    const dt=new DataTransfer();dt.items.add(f);
    const inp=document.querySelector('#fileBank');inp.files=dt.files;
    inp.dispatchEvent(new Event('change',{bubbles:true}));
  })()`);
  await sleep(1000);
  ok("导入后变 3 套", (await ev("document.querySelectorAll('#vBanks .bank').length")) === 3,
     await ev("document.querySelectorAll('#vBanks .bank').length"));
  ok("新题库标题出现", (await ev("document.querySelector('#bankList').innerText")).indexOf("测试题库丙") >= 0);

  // ---------- 删除 ----------
  await ev("document.querySelector('.bank[data-id=\"test-bank-2\"] .del').click()"); await sleep(800);
  ok("删除后剩 2 套", (await ev("document.querySelectorAll('#vBanks .bank').length")) === 2,
     await ev("document.querySelectorAll('#vBanks .bank').length"));

  // ---------- 导出记录 ----------
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(500);
  await ev("document.querySelector('#btnExpRec').click()"); await sleep(800);
  const exRec = await ev("(function(){var e=window.__lastExport||{};return {name:e.name||'',text:e.text||''}})()");
  ok("导出记录文件名正确", /\.qrec\.json$/.test(exRec.name), exRec.name);
  const o = JSON.parse(exRec.text || "{}");
  ok("导出 format=qbank-record", o.format === "qbank-record");
  ok("导出带 bankId", o.bankId === "test-bank", o.bankId);
  ok("导出含 5 条记录", Object.keys(o.records || {}).length === 5, String(Object.keys(o.records || {}).length));
  ok("导出含错选分布", !!(o.records["ch1-single-1"] || {}).wrongOptions);
  ok("导出含历史明细", ((o.records["ch1-multi-1"] || {}).history || []).length === 2);

  // ---------- 合并另一台设备的记录 ----------
  await ev("document.querySelector('#btnImpRec').click()"); await sleep(250);
  await ev("document.querySelector('.sheet [data-m=\"merge\"]').click()"); await sleep(250);
  await ev(`(()=>{
    const p={format:'qbank-record',version:'1.0',bankId:'test-bank',records:{
      'ch2-single-1':{attempts:3,correct:2,wrong:1,accuracy:0.6667,wrongOptions:{B:1},
        lastPicked:['A'],lastCorrect:true,history:[
          {at:'2026-11-24T10:00:00+08:00',picked:['B'],correct:false,answer:'A'},
          {at:'2026-11-24T10:01:00+08:00',picked:['A'],correct:true,answer:'A'},
          {at:'2026-11-24T10:02:00+08:00',picked:['A'],correct:true,answer:'A'}],
        note:'另一台设备的笔记',flagged:false,aiAnalysis:'',updatedAt:'2026-11-24T10:02:00+08:00'}
    }};
    const b=new Blob([JSON.stringify(p)],{type:'application/json'});
    const f=new File([b],'r.json',{type:'application/json'});
    const dt=new DataTransfer();dt.items.add(f);
    const inp=document.querySelector('#fileRec');inp.files=dt.files;
    inp.dispatchEvent(new Event('change',{bubbles:true}));
  })()`);
  await sleep(900);
  const rec2 = await ev("JSON.parse(localStorage.getItem('qbank.records.v2'))['test-bank']");
  ok("合并带入对方记录", !!rec2["ch2-single-1"]);
  ok("合并带入历史 3 条", ((rec2["ch2-single-1"] || {}).h || []).length === 3);
  ok("合并带入错选统计", JSON.stringify((rec2["ch2-single-1"] || {}).wo) === '{"B":1}');
  await ev("document.querySelector('#btnHome').click()"); await sleep(450);
  ok("列表进度变为 6 / 7",
     (await ev("document.querySelector('.bank[data-id=\"test-bank\"]').innerText")).indexOf("6 / 7") >= 0,
     await ev("document.querySelector('.bank[data-id=\"test-bank\"]').innerText"));

  // ---------- 收藏 ----------
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(500);
  await ev("document.querySelector('#chList [data-ch=\"ch2\"]').click()"); await sleep(400);
  ok("进入第二章 2 题", (await ev("document.querySelector('#navPos').textContent")) === "1 / 2",
     await ev("document.querySelector('#navPos').textContent"));
  // 这题在合并记录里已有作答，先重做，才能验证「答对自动跳」
  await ev("document.querySelector('#btnRedo').click()"); await sleep(200);
  // 这题在合并记录里已有作答，先重做，才能验证「答对自动跳」
  await ev("document.querySelector('#btnRedo').click()"); await sleep(200);
  await ev("document.querySelector('#btnStar').click()"); await sleep(250);
  ok("收藏按钮变为已收藏", (await ev("document.querySelector('#btnStar').textContent")).indexOf("已收藏") >= 0);
  // 刷新页面，验证收藏真的落盘了（先清当前题库标记，避免冷启动自动续接）
  await ev("localStorage.removeItem('qbank.cur.v2')");
  await send("Page.navigate", { url: URL }); await sleep(1100);
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(500);
  ok("刷新后收藏数仍为 1", (await ev("document.querySelector('#starRing').textContent")) === "1",
     await ev("document.querySelector('#starRing').textContent"));
  await ev("document.querySelector('#chList [data-ch=\"ch2\"]').click()"); await sleep(400);
  ok("刷新后收藏状态保留", (await ev("document.querySelector('#btnStar').textContent")).indexOf("已收藏") >= 0,
     await ev("document.querySelector('#btnStar').textContent"));
  await ev("document.querySelector('#btnRedo').click()"); await sleep(200);

  // ---------- 答对自动下一题 ----------
  ok("开关默认关闭", (await ev("document.querySelector('#chkAutoNext').checked")) === false);
  await ev("(()=>{const c=document.querySelector('#chkAutoNext');c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await sleep(200);
  ok("开关已开启并记住", (await ev("JSON.parse(localStorage.getItem('qbank.settings.v1')).autoNext")) === true);
  await ev("document.querySelectorAll('#qOpts .opt')[0].click()"); await sleep(1400);
  ok("答对后自动跳到下一题", (await ev("document.querySelector('#navPos').textContent")) === "2 / 2",
     await ev("document.querySelector('#navPos').textContent"));

  // 答错不跳
  await ev("document.querySelector('#btnSheet').click()"); await sleep(300);
  await ev("document.querySelector('.sheet [data-i=\"0\"]').click()"); await sleep(300);
  await ev("document.querySelector('#btnRedo').click()"); await sleep(200);
  await ev("document.querySelectorAll('#qOpts .opt')[1].click()"); await sleep(1400);
  ok("答错后不自动跳", (await ev("document.querySelector('#navPos').textContent")) === "1 / 2",
     await ev("document.querySelector('#navPos').textContent"));

  // 关掉开关后答对也不跳
  await ev("(()=>{const c=document.querySelector('#chkAutoNext');c.checked=false;c.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await sleep(200);
  await ev("document.querySelector('#btnRedo').click()"); await sleep(200);
  await ev("document.querySelectorAll('#qOpts .opt')[0].click()"); await sleep(1300);
  ok("关闭开关后不自动跳", (await ev("document.querySelector('#navPos').textContent")) === "1 / 2",
     await ev("document.querySelector('#navPos').textContent"));

  // ---------- 收藏组 ----------
  await ev("document.querySelector('#btnHome').click()"); await sleep(450);
  ok("首页收藏计数为 1", (await ev("document.querySelector('#starRing').textContent")) === "1",
     await ev("document.querySelector('#starRing').textContent"));
  await ev("document.querySelector('#goStar').click()"); await sleep(400);
  ok("收藏组只有 1 题", (await ev("document.querySelector('#navPos').textContent")) === "1 / 1",
     await ev("document.querySelector('#navPos').textContent"));
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('#btnHome').click()"); await sleep(450);

  // ---------- 题型分组 ----------
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(500);
  await ev("document.querySelector('#btnOverview').click()"); await sleep(450);
  ok("总览里有题型分组标题", (await ev("document.querySelectorAll('#ovBody .ov-t').length")) >= 6,
     await ev("document.querySelectorAll('#ovBody .ov-t').length"));
  ok("分组标题写明题型与数量", (await ev("document.querySelector('#ovBody .ov-t').textContent")).indexOf("题") >= 0,
     await ev("document.querySelector('#ovBody .ov-t').textContent"));
  const ovGroups = await ev("Array.from(document.querySelectorAll('#ovBody .ov-t')).map(function(e){return e.textContent})");
  ok("单选/多选/不定项/判断都分开了",
     ovGroups.some(function(x){return x.indexOf("单选题")>=0}) &&
     ovGroups.some(function(x){return x.indexOf("多选题")>=0}) &&
     ovGroups.some(function(x){return x.indexOf("不定项")>=0}) &&
     ovGroups.some(function(x){return x.indexOf("判断题")>=0}), ovGroups.join(" / "));

  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('#chList [data-ch=\"ch1\"]').click()"); await sleep(350);
  await ev("document.querySelector('#btnSheet').click()"); await sleep(300);
  ok("目录弹层也按题型分组", (await ev("document.querySelectorAll('.sheet .sheet-t').length")) >= 3,
     await ev("document.querySelectorAll('.sheet .sheet-t').length"));
  ok("目录分组标题正确", (await ev("Array.from(document.querySelectorAll('.sheet .sheet-t')).map(function(e){return e.textContent}).join(' / ')"))
     .indexOf("单选题") >= 0);
  await ev("document.querySelector('.sheet').remove()"); await sleep(150);
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('#btnHome').click()"); await sleep(400);

  // ---------- 记录导入严格校验 ----------
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(500);
  const recBefore = await ev("Object.keys(JSON.parse(localStorage.getItem('qbank.records.v2'))['test-bank']).length");

  // (a) bankId 不匹配
  await ev("document.querySelector('#btnImpRec').click()"); await sleep(250);
  await ev("document.querySelector('.sheet [data-m=\"merge\"]').click()"); await sleep(250);
  await ev(`(()=>{
    const p={format:'qbank-record',version:'1.0',bankId:'other-bank',records:{
      'ch1-single-1':{attempts:1,correct:1,wrong:0,lastPicked:['A'],lastCorrect:true,history:[]}}};
    const b=new Blob([JSON.stringify(p)],{type:'application/json'});
    const f=new File([b],'x.json',{type:'application/json'});
    const dt=new DataTransfer();dt.items.add(f);
    const inp=document.querySelector('#fileRec');inp.files=dt.files;
    inp.dispatchEvent(new Event('change',{bubbles:true}));
  })()`);
  await sleep(800);
  ok("bankId 不匹配被拒绝", dialogs.some(function(d){return d.indexOf("bankId 不匹配")>=0}), dialogs.slice(-1)[0]);
  const recAfter1 = await ev("Object.keys(JSON.parse(localStorage.getItem('qbank.records.v2'))['test-bank']).length");
  ok("拒绝后本机记录一点没变", recBefore === recAfter1, recBefore + " -> " + recAfter1);

  // (b) 题号不存在
  await ev("document.querySelector('#btnImpRec').click()"); await sleep(250);
  await ev("document.querySelector('.sheet [data-m=\"merge\"]').click()"); await sleep(250);
  await ev(`(()=>{
    const p={format:'qbank-record',version:'1.0',bankId:'test-bank',records:{
      'no-such-question':{attempts:1,correct:1,wrong:0,history:[]}}};
    const b=new Blob([JSON.stringify(p)],{type:'application/json'});
    const f=new File([b],'y.json',{type:'application/json'});
    const dt=new DataTransfer();dt.items.add(f);
    const inp=document.querySelector('#fileRec');inp.files=dt.files;
    inp.dispatchEvent(new Event('change',{bubbles:true}));
  })()`);
  await sleep(800);
  ok("题号不存在被拒绝", dialogs.some(function(d){return d.indexOf("找不到")>=0}), dialogs.slice(-1)[0]);
  const recAfter2 = await ev("Object.keys(JSON.parse(localStorage.getItem('qbank.records.v2'))['test-bank']).length");
  ok("第二次拒绝后记录仍未变", recBefore === recAfter2, recBefore + " -> " + recAfter2);

  // (c) format 不对
  await ev("document.querySelector('#btnImpRec').click()"); await sleep(250);
  await ev("document.querySelector('.sheet [data-m=\"merge\"]').click()"); await sleep(250);
  await ev(`(()=>{
    const p={version:'1.0',bankId:'test-bank',records:{'ch1-single-1':{attempts:1,correct:1}}};
    const b=new Blob([JSON.stringify(p)],{type:'application/json'});
    const f=new File([b],'z.json',{type:'application/json'});
    const dt=new DataTransfer();dt.items.add(f);
    const inp=document.querySelector('#fileRec');inp.files=dt.files;
    inp.dispatchEvent(new Event('change',{bubbles:true}));
  })()`);
  await sleep(800);
  ok("缺 format 被拒绝", dialogs.some(function(d){return d.indexOf("format 必须")>=0}), dialogs.slice(-1)[0]);

  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('#btnHome').click()"); await sleep(400);

  // ---------- 题目总览 ----------
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(500);
  await ev("document.querySelector('#btnOverview').click()"); await sleep(450);
  ok("总览视图打开", (await ev("document.querySelector('#vOverview').classList.contains('hide')")) === false);
  ok("总览按章分组 2 组", (await ev("document.querySelectorAll('#ovBody .ov-ch').length")) === 2,
     await ev("document.querySelectorAll('#ovBody .ov-ch').length"));
  ok("总览列出全部 7 题", (await ev("document.querySelectorAll('#ovBody [data-qid]').length")) === 7,
     await ev("document.querySelectorAll('#ovBody [data-qid]').length"));
  ok("总览里带对错颜色", (await ev("document.querySelectorAll('#ovBody .qgrid button.ok, #ovBody .qgrid button.bad').length")) >= 1);
  ok("总览里标出收藏", (await ev("document.querySelectorAll('#ovBody .qgrid button.st').length")) >= 1);
  await ev("document.querySelector('#ovBody [data-qid=\"ch2-multi-7\"]').click()"); await sleep(450);
  ok("点总览题号直达该题", (await ev("document.querySelector('#navPos').textContent")) === "2 / 2",
     await ev("document.querySelector('#navPos').textContent"));
  ok("直达的是第 7 题", (await ev("document.querySelector('#qHead').innerText")).indexOf("第 7 题") >= 0,
     await ev("document.querySelector('#qHead').innerText").then ? "" : "");

  // ---------- 冷启动回到上次位置 ----------
  await send("Page.navigate", { url: URL }); await sleep(1200);
  ok("冷启动直接回到上次的题", (await ev("document.querySelector('#vQuiz').classList.contains('hide')")) === false &&
     (await ev("document.querySelector('#navPos').textContent")) === "2 / 2",
     await ev("document.querySelector('#navPos').textContent") + " / vQuiz隐藏=" +
     (await ev("document.querySelector('#vQuiz').classList.contains('hide')")));
  ok("出现续接提示条", (await ev("document.querySelector('#resumeTip').style.display")) !== "none");
  await ev("document.querySelector('#resumeTipClose').click()"); await sleep(200);
  ok("可关闭续接提示", (await ev("document.querySelector('#resumeTip').style.display")) === "none");
  await ev("document.querySelector('#btnHome').click()"); await sleep(400);
  ok("续接后返回落到题库首页", (await ev("document.querySelector('#vHome').classList.contains('hide')")) === false);
  await ev("document.querySelector('#btnHome').click()"); await sleep(450);

  // ---------- 答题页里的设置入口 ----------
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(500);
  await ev("document.querySelector('#chList [data-ch=\"ch1\"]').click()"); await sleep(400);
  ok("答题页顶栏有设置按钮", (await ev("document.querySelector('#btnSettings').style.display")) !== "none");
  await ev("document.querySelector('#btnSettings').click()"); await sleep(350);
  ok("设置面板打开", (await ev("!!document.querySelector('#shAutoNext')")) === true);
  ok("设置面板读到当前开关值", (await ev("document.querySelector('#shAutoNext').checked")) === false);
  await ev("(()=>{const c=document.querySelector('#shAutoNext');c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await sleep(250);
  ok("面板里改开关会存下来", (await ev("JSON.parse(localStorage.getItem('qbank.settings.v1')).autoNext")) === true);
  await ev("document.querySelector('#shClose').click()"); await sleep(200);
  ok("设置面板可关闭", (await ev("!!document.querySelector('#shAutoNext')")) === false);
  // 关掉，免得影响后面的用例
  await ev("document.querySelector('#btnSettings').click()"); await sleep(300);
  await ev("(()=>{const c=document.querySelector('#shAutoNext');c.checked=false;c.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await sleep(200);
  await ev("document.querySelector('#shClose').click()"); await sleep(200);
  ok("取消后开关回到关闭", (await ev("JSON.parse(localStorage.getItem('qbank.settings.v1')).autoNext")) === false);
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('#btnHome').click()"); await sleep(400);

  // ---------- 自动翻页间隔可调 ----------
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(500);
  await ev("document.querySelector('#chList [data-ch=\"ch1\"]').click()"); await sleep(400);
  await ev("document.querySelector('#btnSettings').click()"); await sleep(350);
  ok("设置里有间隔滑杆", (await ev("!!document.querySelector('#shDelay')")) === true);
  ok("默认间隔 600 毫秒", (await ev("document.querySelector('#shDelay').value")) === "600",
     await ev("document.querySelector('#shDelay').value"));
  ok("间隔数值有显示", (await ev("document.querySelector('#shDelayVal').textContent")) === "600");
  await ev("(()=>{const r=document.querySelector('#shDelay');r.value='200';r.dispatchEvent(new Event('input',{bubbles:true}));r.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await sleep(250);
  ok("滑杆数值同步显示", (await ev("document.querySelector('#shDelayVal').textContent")) === "200");
  ok("间隔写入设置", (await ev("JSON.parse(localStorage.getItem('qbank.settings.v1')).delay")) === 200,
     String(await ev("JSON.parse(localStorage.getItem('qbank.settings.v1')).delay")));
  await ev("(()=>{const c=document.querySelector('#shAutoNext');c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await sleep(200);
  await ev("document.querySelector('#shClose').click()"); await sleep(250);

  await ev("document.querySelector('#btnSheet').click()"); await sleep(300);
  await ev("document.querySelector('.sheet [data-i=\"0\"]').click()"); await sleep(300);
  await ev("document.querySelector('#btnRedo').click()"); await sleep(200);
  await ev("document.querySelectorAll('#qOpts .opt')[1].click()"); await sleep(480);
  ok("间隔 200ms 时很快翻页", (await ev("document.querySelector('#navPos').textContent")) === "2 / 5",
     await ev("document.querySelector('#navPos').textContent"));

  // 恢复默认，避免影响后续
  await ev("document.querySelector('#btnSettings').click()"); await sleep(300);
  await ev("(()=>{const r=document.querySelector('#shDelay');r.value='600';r.dispatchEvent(new Event('input',{bubbles:true}));r.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await ev("(()=>{const c=document.querySelector('#shAutoNext');c.checked=false;c.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await sleep(250);
  await ev("document.querySelector('#shClose').click()"); await sleep(200);
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('#btnHome').click()"); await sleep(400);

  // ---------- 提示词与宽容导入 ----------
  ok("首页有复制提示词按钮", (await ev("!!document.querySelector('#btnCopyPrompt')")) === true);
  await ev("window.__copied=''; try{Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:function(t){window.__copied=t;return Promise.resolve();}}});}catch(e){}");
  dialogs.length = 0;
  await ev("document.querySelector('#btnCopyPrompt').click()"); await sleep(300);
  ok("复制提示词按钮可用", dialogs.some(function(d){return d.indexOf("已复制转换提示词")>=0}), dialogs.slice(-1)[0]);
  const pt = String(await ev("window.__copied||''"));
  ok("复制的提示词含输出契约", pt.indexOf("输出契约") >= 0 && pt.indexOf("裸 JSON") >= 0, pt.slice(0, 80));
  ok("提示词只含提示词正文", pt.indexOf("# 第四部分") < 0 && pt.indexOf("# 第一部分") < 0, pt.slice(0, 80));
  ok("提示词不含 Markdown 外层围栏", pt.slice(0, 4) !== "````" && pt.indexOf("````") < 0, pt.slice(0, 40));

  // 带代码围栏 + 前后说明文字的题库文件，应能直接导入
  const BANK4 = {
    format: "qbank", version: "1.0",
    meta: { id: "fenced-bank", title: "围栏测试题库" },
    chapters: [],
    questions: [Q("q-single-1", "single", null, 1, "围栏题", ["甲", "乙"], ["A"])]
  };
  const wrappedBank = "这是 AI 的回复：\n```json\n" + JSON.stringify(BANK4) + "\n```\n以上。";
  const nBefore = await ev("document.querySelectorAll('#vBanks .bank').length");
  dialogs.length = 0;
  await ev(`(()=>{
    const t=${JSON.stringify(wrappedBank)};
    const blob=new Blob([t],{type:'application/json'});
    const f=new File([blob],'fenced.qbank.json',{type:'application/json'});
    const dt=new DataTransfer();dt.items.add(f);
    const inp=document.querySelector('#fileBank');inp.files=dt.files;
    inp.dispatchEvent(new Event('change',{bubbles:true}));
  })()`);
  await sleep(1000);
  ok("带围栏的题库能导入", (await ev("document.querySelectorAll('#vBanks .bank').length")) === nBefore + 1,
     nBefore + " -> " + await ev("document.querySelectorAll('#vBanks .bank').length"));
  ok("导入时提示已自动去围栏", dialogs.some(function(d){return d.indexOf("已自动去掉")>=0}), dialogs.slice(-1)[0]);
  ok("围栏题库内容正确", (await ev("document.querySelector('#bankList').innerText")).indexOf("围栏测试题库") >= 0);

  // 带围栏的记录文件也应能导入，但数据严格校验不放宽
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(450);
  const makeRecWrap = (bid) => "AI 回复：\n```json\n" + JSON.stringify({
    format: "qbank-record", version: "1.0", bankId: bid,
    records: { "ch1-single-1": { attempts: 1, correct: 1, wrong: 0,
      lastPicked: ["B"], lastCorrect: true, history: [] } }
  }) + "\n```";
  dialogs.length = 0;
  await ev("document.querySelector('#btnImpRec').click()"); await sleep(250);
  await ev("document.querySelector('.sheet [data-m=\"merge\"]').click()"); await sleep(250);
  await ev(`(()=>{
    const t=${JSON.stringify(makeRecWrap("test-bank"))};
    const blob=new Blob([t],{type:'application/json'});
    const f=new File([blob],'fenced.qrec.json',{type:'application/json'});
    const dt=new DataTransfer();dt.items.add(f);
    const inp=document.querySelector('#fileRec');inp.files=dt.files;
    inp.dispatchEvent(new Event('change',{bubbles:true}));
  })()`);
  await sleep(900);
  ok("带围栏的记录能导入", dialogs.some(function(d){return d.indexOf("已合并")>=0}), dialogs.slice(-1)[0]);

  dialogs.length = 0;
  await ev("document.querySelector('#btnImpRec').click()"); await sleep(250);
  await ev("document.querySelector('.sheet [data-m=\"merge\"]').click()"); await sleep(250);
  await ev(`(()=>{
    const t=${JSON.stringify(makeRecWrap("wrong-bank"))};
    const blob=new Blob([t],{type:'application/json'});
    const f=new File([blob],'bad.qrec.json',{type:'application/json'});
    const dt=new DataTransfer();dt.items.add(f);
    const inp=document.querySelector('#fileRec');inp.files=dt.files;
    inp.dispatchEvent(new Event('change',{bubbles:true}));
  })()`);
  await sleep(900);
  ok("围栏不放宽严格校验", dialogs.some(function(d){return d.indexOf("bankId 不匹配")>=0}), dialogs.slice(-1)[0]);

  await ev("document.querySelector('#btnHome').click()"); await sleep(350);
  if(await ev("!!document.querySelector('.bank[data-id=\"fenced-bank\"] .del')")){
    await ev("document.querySelector('.bank[data-id=\"fenced-bank\"] .del').click()"); await sleep(700);
  }
  await sleep(200);

  // ---------- 会话作答态：进入答题时清掉上一次作答 ----------
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(450);

  // 先做 ch1-single-1（答错），留下记录
  await ev("document.querySelector('#chList [data-ch=\"ch1\"]').click()"); await sleep(350);
  await ev("document.querySelectorAll('#qOpts .opt')[0].click()"); await sleep(250);
  const recAfterAnswer = await ev("JSON.parse(localStorage.getItem('qbank.records.v2'))['test-bank']['ch1-single-1']");
  ok("作答后记录写入次数", recAfterAnswer.attempts >= 1, JSON.stringify(recAfterAnswer).slice(0, 100));
  ok("作答后界面锁定显示反馈", (await ev("!!document.querySelector('#qFb .fb')")) === true);

  // 回到题库首页，再点章节重新进入 ——上一次的作答痕迹应消失
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('#chList [data-ch=\"ch1\"]').click()"); await sleep(350);
  ok("重进后不再显示上次对错反馈", (await ev("!!document.querySelector('#qFb .fb')")) === false,
     await ev("document.querySelector('#qFb').innerText.slice(0,60)"));
  ok("重进后选项不再锁定", (await ev("document.querySelectorAll('#qOpts .opt.locked').length")) === 0,
     await ev("document.querySelectorAll('#qOpts .opt.locked').length"));
  ok("重进后选项不显示正确答案", (await ev("document.querySelectorAll('#qOpts .opt.correct').length")) === 0);
  ok("重进后没有选中项", (await ev("document.querySelectorAll('#qOpts .opt.sel').length")) === 0);
  ok("重进后仍显示历史统计", (await ev("document.querySelector('#qFb .hist')!==null")) === true);
  const recAfterReenter = await ev("JSON.parse(localStorage.getItem('qbank.records.v2'))['test-bank']['ch1-single-1']");
  ok("重进后做题记录没被清掉", recAfterReenter.attempts === recAfterAnswer.attempts &&
     recAfterReenter.h.length === recAfterAnswer.h.length,
     recAfterAnswer.attempts + "/" + recAfterAnswer.h.length + " -> " +
     recAfterReenter.attempts + "/" + recAfterReenter.h.length);

  // 本次会话答对，反馈出现；切到下一题再切回来，本次作答应保留（同一次练习内）
  await ev("document.querySelectorAll('#qOpts .opt')[1].click()"); await sleep(250);
  ok("本次作答后显示答对", (await ev("document.querySelector('#qFb .fb.ok')!==null")) === true);
  await ev("document.querySelector('#btnNext').click()"); await sleep(200);
  await ev("document.querySelector('#btnPrev').click()"); await sleep(200);
  ok("同一次练习内切题回来保留本次作答", (await ev("!!document.querySelector('#qFb .fb')")) === true);

  // 退出题库再进、走错题重做入口，也应清零
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('#btnHome').click()"); await sleep(350);
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(450);
  const recBeforeWrong = await ev("JSON.parse(localStorage.getItem('qbank.records.v2'))['test-bank']['ch1-single-1'].attempts");
  await ev("document.querySelector('#goWrong').click()"); await sleep(400);
  ok("错题重做入口进入后作答清零", (await ev("!!document.querySelector('#qFb .fb')")) === false,
     await ev("document.querySelector('#qFb').innerText.slice(0,60)"));
  ok("错题重做里选项未锁定", (await ev("document.querySelectorAll('#qOpts .opt.locked').length")) === 0);
  const recWrong = await ev("JSON.parse(localStorage.getItem('qbank.records.v2'))['test-bank']['ch1-single-1']");
  ok("错题重做不清历史记录", recWrong.attempts === recBeforeWrong, recBeforeWrong + " -> " + recWrong.attempts);

  // 版本号显示
  ok("版本号已注入页面", (await ev("document.querySelector('#appVer').textContent")).indexOf("v1.1.0") >= 0,
     await ev("document.querySelector('#appVer').textContent"));
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  ok("首页底部显示版本号", (await ev("document.querySelector('#topVer').textContent")).indexOf("v1.1.0") >= 0,
     await ev("document.querySelector('#topVer').textContent"));
  await ev("document.querySelector('#btnHome').click()"); await sleep(400);

  // ---------- 退回题库列表后关掉重开，仍回到上次那题 ----------
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(450);
  await ev("document.querySelector('#chList [data-ch=\"ch2\"]').click()"); await sleep(350);
  await ev("document.querySelector('#btnNext').click()"); await sleep(250);
  const resumeQ = await ev("JSON.parse(localStorage.getItem('qbank.pos.v2'))['test-bank'].qid");
  const resumeText = await ev("document.querySelector('#qStem').textContent");
  ok("答题时记录了位置", !!resumeQ, String(resumeQ));
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);   // 回题库首页
  await ev("document.querySelector('#btnHome').click()"); await sleep(350);   // 回题库列表
  ok("退回列表后仍保留当前题库标记", (await ev("localStorage.getItem('qbank.cur.v2')")) === "test-bank",
     await ev("localStorage.getItem('qbank.cur.v2')"));
  await send("Page.navigate", { url: URL }); await sleep(1600);               // 关掉重开
  ok("重开后直接回到答题页", (await ev("document.querySelector('#vQuiz').classList.contains('hide')")) === false);
  ok("重开后回到上次那道题", (await ev("document.querySelector('#qStem').textContent")) === resumeText,
     (await ev("document.querySelector('#qStem').textContent")).slice(0,40) + " | 应为 " + resumeText.slice(0,40));
  ok("重开后该题作答是干净的", (await ev("!!document.querySelector('#qFb .fb')")) === false);
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('#btnHome').click()"); await sleep(400);

  // ---------- 自检 ----------
  await ev("document.querySelector('.bank[data-id=\"test-bank\"]').click()"); await sleep(450);
  await ev("document.querySelector('#btnCheck').click()"); await sleep(400);
  const chk = await ev("document.querySelector('#checkBody').innerText");
  ok("自检通过", chk.indexOf("全部通过") >= 0, chk.slice(0, 100));
  ok("自检含不定项计数", chk.indexOf("不定项 2") >= 0, chk.slice(0, 170));
  await ev("document.querySelector('#btnHome').click()"); await sleep(250);

  // ---------- 规范 ----------
  ok("内置规范文本存在", (await ev("(document.querySelector('#specDoc')||{}).textContent.length")) > 3000);
  await ev("document.querySelector('#btnBankSpec').click()"); await sleep(400);
  ok("规范弹层出现", (await ev("!!document.querySelector('.sheet')")) === true);
  await ev("document.querySelector('#spClose').click()"); await sleep(250);
  await ev("document.querySelector('#btnHome').click()"); await sleep(450);
  await ev("document.querySelector('#btnExpSpec').click()"); await sleep(800);
  const exSpec = await ev("(function(){var e=window.__lastExport||{};return {name:e.name||'',text:e.text||''}})()");
  ok("导出规范为 .md", /\.md$/.test(exSpec.name), exSpec.name);
  ok("规范含格式与自检要求", exSpec.text.indexOf("qbank") >= 0 && exSpec.text.indexOf("自检") >= 0);

  console.log("\n===== 汇总 =====");
  const bad = res.filter((x) => !x[1]);
  console.log(`通过 ${res.length - bad.length} / ${res.length}`);
  bad.forEach((b) => console.log("  失败：" + b[0]));
  ws.close(); child.kill();
  process.exit(bad.length ? 1 : 0);
}
main().catch((e) => { console.error(e); process.exit(2); });
