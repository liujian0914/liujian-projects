// 交付前全面检查：跑真实的 exe 服务（http://127.0.0.1:8766），走完整流程，
// 抓 JS 报错、未捕获异常、弹窗、布局溢出。
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const EXE = "D:\\题库系统\\题库系统.exe";
const PORT = 9350;
const URL = "http://127.0.0.1:8766/index.html";
const PROFILE = "D:/AndroidBuild/auditprof";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const fails = [];
const warns = [];
const ok = (n, c, e) => {
  if (!c) { fails.push(n); console.log("FAIL  " + n + (e !== undefined ? "  -> " + e : "")); }
  else console.log("PASS  " + n);
};
const warn = (n) => { warns.push(n); console.log("WARN  " + n); };

async function main() {
  // 1) 启动 exe（真实交付物）
  const exe = spawn(EXE, [], { detached: true, stdio: "ignore" });
  exe.unref();
  let up = false;
  for (let i = 0; i < 40; i++) {
    try {
      const r = await fetch("http://127.0.0.1:8766/index.html", { method: "HEAD" });
      if (r.ok) { up = true; break; }
    } catch (e) {}
    await sleep(300);
  }
  ok("exe 启动并监听 8766", up);

  // 2) 受控 Edge + CDP
  if (fs.existsSync(PROFILE)) fs.rmSync(PROFILE, { recursive: true, force: true });
  const edge = spawn(EDGE, ["--headless=new", "--disable-gpu", "--remote-debugging-port=" + PORT,
    "--user-data-dir=" + PROFILE, "--window-size=1280,900", "about:blank"], { stdio: "ignore" });

  let t = null;
  for (let i = 0; i < 60; i++) {
    try { const r = await fetch(`http://127.0.0.1:${PORT}/json/list`); t = await r.json(); if (t.length) break; } catch (e) {}
    await sleep(250);
  }
  const ws = new WebSocket(t.find((x) => x.type === "page").webSocketDebuggerUrl);
  let id = 0; const pd = new Map();
  const consoleErrors = [], pageErrors = [], dialogs = [];
  await new Promise((r) => (ws.onopen = r));
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pd.has(m.id)) { pd.get(m.id)(m.result); pd.delete(m.id); return; }
    if (m.method === "Runtime.exceptionThrown") {
      const d = m.params.exceptionDetails;
      pageErrors.push((d.exception && (d.exception.description || d.exception.value)) || d.text);
    }
    if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") {
      consoleErrors.push(m.params.args.map((a) => a.value || a.description || a.type).join(" "));
    }
    if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
      consoleErrors.push(m.params.entry.text);
    }
    if (m.method === "Page.javascriptDialogOpening") {
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

  await send("Page.enable"); await send("Runtime.enable"); await send("Log.enable");
  await send("Page.navigate", { url: URL }); await sleep(1500);

  // 3) 首屏
  ok("页面经 exe 服务正常加载", (await ev("!!document.querySelector('#vBanks')")) === true);
  ok("内置题库已就位", (await ev("document.querySelectorAll('#vBanks .bank').length")) >= 1);
  ok("service worker 已注册（http 环境）", (await ev("navigator.serviceWorker.getRegistrations().then(r=>r.length)")) !== 0);

  // 4) 各宽度布局溢出
  for (const w of [320, 360, 390, 414, 768, 1024, 1280]) {
    await send("Emulation.setDeviceMetricsOverride", { width: w, height: 800, deviceScaleFactor: 1, mobile: w < 700 });
    await sleep(250);
    const of1 = await ev("document.documentElement.scrollWidth - window.innerWidth");
    await ev("document.querySelectorAll('#vBanks .bank')[0].click()"); await sleep(400);
    const of2 = await ev("document.documentElement.scrollWidth - window.innerWidth");
    const of3 = await ev("(function(){var m=document.querySelector('main');return m.scrollWidth-m.clientWidth})()");
    ok(`宽度 ${w}px 无横向溢出`, of1 <= 1 && of2 <= 1 && of3 <= 1, `首页${of1} 题库${of2} main${of3}`);
    await ev("document.querySelector('#btnOverview').click()"); await sleep(300);
    const of4 = await ev("document.documentElement.scrollWidth - window.innerWidth");
    ok(`宽度 ${w}px 总览页无溢出`, of4 <= 1, of4);
    await ev("document.querySelector('#btnHome').click()"); await sleep(250);
    await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  }
  await send("Emulation.clearDeviceMetricsOverride"); await sleep(300);

  // 5) 进入题库、答题、设置、总览
  await ev("document.querySelectorAll('#vBanks .bank')[0].click()"); await sleep(500);
  ok("进入题库首页", (await ev("document.querySelector('#vHome').classList.contains('hide')")) === false);
  await ev("document.querySelectorAll('#chList [data-ch]')[0].click()"); await sleep(400);
  ok("进入答题页", (await ev("document.querySelector('#vQuiz').classList.contains('hide')")) === false);

  const before = await ev("document.querySelector('#navPos').textContent");
  await ev("document.querySelectorAll('#qOpts .opt')[0].click()"); await sleep(350);
  const after = await ev("document.querySelector('#navPos').textContent");
  ok("作答后位置不变（未开自动翻页）", before === after, before + " -> " + after);
  ok("作答后有判分反馈", (await ev("document.querySelectorAll('#qFb .fb').length")) === 1);

  // 设置面板
  await ev("document.querySelector('#btnSettings').click()"); await sleep(300);
  ok("设置面板可打开", (await ev("!!document.querySelector('#shAutoNext')")) === true);
  ok("间隔滑杆存在且值合理", (await ev("+document.querySelector('#shDelay').value")) >= 200);
  await ev("document.querySelector('#shClose').click()"); await sleep(200);

  // 总览跳题
  await ev("document.querySelector('#btnSettings').click()"); await sleep(200);
  await ev("document.querySelector('#shClose').click()"); await sleep(200);
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('#btnOverview').click()"); await sleep(400);
  ok("总览列出题号", (await ev("document.querySelectorAll('#ovBody [data-qid]').length")) > 100,
     await ev("document.querySelectorAll('#ovBody [data-qid]').length"));
  await ev("document.querySelectorAll('#ovBody [data-qid]')[5].click()"); await sleep(400);
  ok("总览跳题成功", (await ev("document.querySelector('#vQuiz').classList.contains('hide')")) === false);

  // 6) 兜底逻辑：空答案题库不应崩溃
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);
  await ev("document.querySelector('#btnHome').click()"); await sleep(400);
  await ev(`(()=>{
    const b={format:"qbank",version:"1.0",meta:{id:"bad-bank",title:"坏题库"},
      chapters:[],questions:[{id:"x1",type:"single",stem:"无答案题",options:[{key:"A",text:"a"},{key:"B",text:"b"}],answer:[]}]};
    const blob=new Blob([JSON.stringify(b)],{type:"application/json"});
    const f=new File([blob],"bad.json",{type:"application/json"});
    const dt=new DataTransfer();dt.items.add(f);
    const inp=document.querySelector('#fileBank');inp.files=dt.files;
    inp.dispatchEvent(new Event("change",{bubbles:true}));
  })()`);
  await sleep(900);
  ok("缺答案的题库能导入且给出警告", dialogs.some((d) => d.indexOf("没有答案") >= 0 || d.indexOf("处问题") >= 0),
     dialogs.slice(-2).join(" | "));
  ok("导入后列表变多", (await ev("document.querySelectorAll('#vBanks .bank').length")) >= 2);

  // 坏 JSON 不崩
  await ev(`(()=>{
    const f=new File(["{不是json"],"x.json",{type:"application/json"});
    const dt=new DataTransfer();dt.items.add(f);
    const inp=document.querySelector('#fileBank');inp.files=dt.files;
    inp.dispatchEvent(new Event("change",{bubbles:true}));
  })()`);
  await sleep(700);
  ok("坏 JSON 有提示且不崩溃", dialogs.some((d) => d.indexOf("不是有效的 JSON") >= 0), dialogs.slice(-1)[0]);
  ok("坏 JSON 后页面仍可用", (await ev("document.querySelectorAll('#vBanks .bank').length")) >= 2);

  // 7) 导出四件套（选有做题记录的那套，避免落到刚导入的空题库上）
  await ev("document.querySelector('.bank[data-id=\"maogai-2026-10\"]').click()"); await sleep(600);
  for (const [btn, key, label] of [["#btnExpRec", ".qrec.json", "记录"], ["#btnExpMd", ".md", "Markdown"],
                                   ["#btnExpHtml", ".html", "复习版"], ["#btnExpAi", ".json", "AI 请求包"]]) {
    await ev(`document.querySelector('${btn}').click()`); await sleep(700);
    const r = await ev("(function(){var e=window.__lastExport||{};return {n:e.name||'',t:(e.text||'').length}})()");
    ok("导出" + label + "成功", r.n.indexOf(key) >= 0 && r.t > 100, JSON.stringify(r));
  }

  // 8) 自检页
  await ev("document.querySelector('#btnCheck').click()"); await sleep(500);
  ok("自检页可打开", (await ev("document.querySelector('#vCheck').classList.contains('hide')")) === false);
  ok("自检页有内容", (await ev("document.querySelector('#checkBody').innerText")).length > 20);
  await ev("document.querySelector('#btnHome').click()"); await sleep(300);

  // 9) 记录落盘 & 刷新续接
  await ev("document.querySelectorAll('#chList [data-ch]')[0].click()"); await sleep(400);
  await ev("document.querySelectorAll('#qOpts .opt')[0].click()"); await sleep(400);
  const posBefore = await ev("document.querySelector('#navPos').textContent");
  await send("Page.navigate", { url: URL }); await sleep(1500);
  const resumed = await ev("document.querySelector('#vQuiz').classList.contains('hide')");
  ok("刷新后回到上次位置", resumed === false, "vQuiz隐藏=" + resumed + " 位置=" + posBefore);

  // 10) 收尾：报错汇总
  ok("无未捕获 JS 异常", pageErrors.length === 0, pageErrors.slice(0, 3).join(" | "));
  ok("无 console.error", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" | "));

  console.log("\n===== 汇总 =====");
  console.log("失败 " + fails.length + " 项，警告 " + warns.length + " 项");
  fails.forEach((f) => console.log("  ✗ " + f));
  if (dialogs.length) console.log("弹窗记录 " + dialogs.length + " 条（含预期提示）");

  ws.close();
  try { edge.kill(); } catch (e) {}
  process.exit(fails.length ? 1 : 0);
}
main().catch((e) => { console.error("审计脚本异常:", e); process.exit(2); });
