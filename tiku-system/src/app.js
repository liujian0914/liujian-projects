(function(){
"use strict";

var $ = function(s){ return document.querySelector(s); };

/* ================= 存储结构 =================
   qbank.banks.v2   { bankId: 题库JSON }
   qbank.records.v2 { bankId: { qid: 记录 } }
   qbank.cur.v2     当前题库 id
   （兼容旧版单题库：qbank.bank.v1 / qbank.rec.v1）
*/
var K_BANKS = "qbank.banks.v2";
var K_RECS  = "qbank.records.v2";
var K_CUR   = "qbank.cur.v2";
var K_SET   = "qbank.settings.v1";
var K_POS   = "qbank.pos.v2";

var SET = { autoNext:false, sound:true, delay:600 };   // delay 自动翻页间隔（毫秒）

var actx = null;
function tone(freq, delay, dur, gain, type){
  if(!SET.sound) return;
  try {
    if(!actx){
      var AC = window.AudioContext || window.webkitAudioContext;
      if(!AC) return;
      actx = new AC();
    }
    if(actx.state === "suspended") actx.resume();
    var o = actx.createOscillator(), g = actx.createGain();
    o.type = type || "sine";
    o.frequency.value = freq;
    var t0 = actx.currentTime + delay;
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(gain || 0.07, t0 + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g); g.connect(actx.destination);
    o.start(t0); o.stop(t0 + dur + 0.03);
  } catch(e){}
}
function sndCorrect(){ tone(880, 0, 0.09); tone(1320, 0.085, 0.13, 0.055); }
function sndWrong(){ tone(233, 0, 0.15, 0.07); tone(175, 0.13, 0.22, 0.055); }
function sndTap(){ tone(1500, 0, 0.045, 0.035, "triangle"); }
function sndStar(){ tone(1046, 0, 0.07); tone(1568, 0.07, 0.11, 0.05); }

var banks = {};          // id -> 题库原始 JSON
var recs  = {};          // id -> { qid: rec }
var curId = "";

var BANK = null;         // 当前题库（规范化后）
var QS = [], CH = {}, BYID = {};
var state = { q:{} };    // 指向 recs[curId]
var cur = { list:[], i:0, mode:"seq", title:"" };
var noteTimer = null, savedTimer = null, importMode = "merge";
var view = "vBanks";

function lsGet(k){ try{ return localStorage.getItem(k); }catch(e){ return null; } }
function lsSet(k,v){ try{ localStorage.setItem(k,v); return true; }catch(e){ return false; } }
function pad(n){ return (n<10?"0":"") + n; }
function today(){ var d=new Date(); return d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate()); }
function stamp(){ var d=new Date(); return today()+"_"+pad(d.getHours())+pad(d.getMinutes()); }
function isoNow(){
  var d=new Date(), off=-d.getTimezoneOffset(), s=off>=0?"+":"-", o=Math.abs(off);
  return d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate())+"T"+
         pad(d.getHours())+":"+pad(d.getMinutes())+":"+pad(d.getSeconds())+
         s+pad(Math.floor(o/60))+":"+pad(o%60);
}
function esc(s){
  return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

/* ================= 题库规范 v1.0 ================= */
function normalizeBank(raw){
  if(!raw || typeof raw!=="object") throw new Error("不是有效的 JSON 对象");
  if(raw.format && raw.format!=="qbank") throw new Error("这不是题库文件（format="+raw.format+"）");
  if(!Array.isArray(raw.questions)) throw new Error("缺少 questions 数组");

  var chapters = [];
  if(Array.isArray(raw.chapters)){
    raw.chapters.forEach(function(c,i){
      if(!c) return;
      if(typeof c === "string") chapters.push({ id:"ch"+(i+1), name:c, order:i+1 });
      else chapters.push({ id:String(c.id), name:c.name||String(c.id), order:(c.order||i+1) });
    });
  }
  var CHM = {};
  chapters.forEach(function(c){ CHM[c.id]=c.name; });

  var questions = raw.questions.map(function(q, idx){
    if(!q || typeof q!=="object") return null;
    var opts = {}, keys = [];
    if(Array.isArray(q.options)){
      q.options.forEach(function(o){
        if(!o) return;
        var k = String(o.key||"").toUpperCase();
        if(!k) return;
        opts[k] = String(o.text==null?"":o.text);
        keys.push(k);
      });
    } else if(q.options && typeof q.options==="object"){
      Object.keys(q.options).forEach(function(k){
        var kk = String(k).toUpperCase();
        opts[kk] = String(q.options[k]);
        keys.push(kk);
      });
    }
    keys.sort();
    var ans = Array.isArray(q.answer)
      ? q.answer.map(function(x){ return String(x).toUpperCase(); }).sort()
      : (typeof q.answer === "string"
          ? q.answer.toUpperCase().split("").filter(function(c){ return "ABCDEFGH".indexOf(c)>=0; })
          : []);
    var chId = (q.chapter != null) ? String(q.chapter) : (q.ch != null ? String(q.ch) : null);
    if(chId === "null" || chId === "undefined" || chId === "") chId = null;
    var type = q.type === "multi" ? "multi" : (q.type === "indefinite" ? "indefinite" : (q.type === "judge" ? "judge" : "single"));
    if(type === "judge" && !keys.length){ opts = {A:"正确",B:"错误"}; keys = ["A","B"]; }
    return {
      id: String(q.id || ("q-"+idx)),
      type: type, ch: chId,
      chName: (chId && CHM[chId]) ? CHM[chId] : "未分章",
      no: q.number || q.no || 0,
      stem: String(q.stem||"").replace(/\r/g,""),
      options: opts, keys: keys, answer: ans,
      analysis: q.analysis || "",
      tags: Array.isArray(q.tags) ? q.tags : []
    };
  }).filter(Boolean);

  var ord = { single:0, multi:1, indefinite:2, judge:3 };
  var orderOf = {};
  chapters.forEach(function(c){ orderOf[c.id] = c.order; });
  questions.sort(function(a,b){
    var ao = a.ch && orderOf[a.ch] ? orderOf[a.ch] : 999;
    var bo = b.ch && orderOf[b.ch] ? orderOf[b.ch] : 999;
    if(ao !== bo) return ao-bo;
    if(a.ch !== b.ch) return String(a.ch).localeCompare(String(b.ch));
    if(ord[a.type] !== ord[b.type]) return ord[a.type]-ord[b.type];
    return (a.no||0)-(b.no||0);
  });

  return {
    format:"qbank", version:"1.0",
    meta: raw.meta || { id:"bank", title:"题库" },
    chapters: chapters.slice().sort(function(a,b){ return (a.order||0)-(b.order||0); }),
    questions: questions
  };
}

function validateBank(bank){
  var issues = [], ids = {}, chapIds = {};
  (bank.chapters||[]).forEach(function(c){ chapIds[c.id]=1; });
  bank.questions.forEach(function(q){
    if(ids[q.id]) issues.push("题目 id 重复：" + q.id);
    ids[q.id] = 1;
    if(!q.stem.trim()) issues.push(q.id + "：题干为空");
    if(!q.keys.length) issues.push(q.id + "：没有选项");
    var expect = [];
    for(var i=0;i<q.keys.length;i++) expect.push(String.fromCharCode(65+i));
    if(q.keys.join("") !== expect.join("")) issues.push(q.id + "：选项字母不连续（" + q.keys.join("") + "）");
    if(!q.answer.length) issues.push(q.id + "：没有答案");
    q.answer.forEach(function(a){ if(q.keys.indexOf(a)<0) issues.push(q.id + "：" + a + " 不在选项里"); });
    if(q.type==="multi" && q.answer.length>0 && q.answer.length<2) issues.push(q.id + "：多选只有 1 个答案");
    if(q.type==="indefinite" && q.answer.length<1) issues.push(q.id + "：不定项没有答案");
    if((q.type==="single"||q.type==="judge") && q.answer.length>1) issues.push(q.id + "：单选/判断有多个答案");
    if(q.ch && !chapIds[q.ch]) issues.push(q.id + "：章节 " + q.ch + " 不存在");
    q.keys.forEach(function(k){ if(!String(q.options[k]).trim()) issues.push(q.id + "：选项 " + k + " 为空"); });
  });
  return issues;
}

function bankToSpecJson(bank){
  return {
    format:"qbank", version:"1.0",
    meta: bank.meta, chapters: bank.chapters,
    questions: bank.questions.map(function(q){
      var o = { id:q.id, type:q.type, chapter:q.ch, number:q.no, stem:q.stem,
                options: q.keys.map(function(k){ return { key:k, text:q.options[k] }; }),
                answer: q.answer, analysis: q.analysis };
      if(q.tags && q.tags.length) o.tags = q.tags;
      return o;
    })
  };
}

/* ================= 载入 / 保存 ================= */
function saveBanks(){ lsSet(K_BANKS, JSON.stringify(banks)); }
function saveRecs(){ lsSet(K_RECS, JSON.stringify(recs)); }

function loadSettings(){
  var raw = lsGet(K_SET);
  if(!raw) return;
  try {
    var o = JSON.parse(raw);
    if(o && typeof o === "object"){
      SET.autoNext = !!o.autoNext;
      SET.sound = (o.sound === undefined) ? true : !!o.sound;
      var d = parseInt(o.delay, 10);
      SET.delay = (isNaN(d) || d < 150 || d > 3000) ? 600 : d;
    }
  } catch(e){}
}
function saveSettings(){ lsSet(K_SET, JSON.stringify(SET)); }

/* 上次看到哪一题 */
function loadPos(){
  var raw = lsGet(K_POS);
  if(!raw) return {};
  try { var o = JSON.parse(raw); return (o && typeof o === "object") ? o : {}; } catch(e){ return {}; }
}
function savePos(qid){
  if(!curId || !qid) return;
  var all = loadPos();
  all[curId] = { qid: qid, at: Date.now() };
  lsSet(K_POS, JSON.stringify(all));
}
function getPos(){
  var all = loadPos();
  return curId ? (all[curId] || null) : null;
}

function seedFromEmbedded(){
  var el = $("#bank");
  if(!el || !el.textContent) return false;
  var raw;
  try { raw = JSON.parse(el.textContent); } catch(e){ return false; }
  if(!raw || !raw.questions || !raw.questions.length) return false;
  var id = (raw.meta && raw.meta.id) || "builtin";
  banks[id] = raw;
  saveBanks();
  return true;
}

function loadAll(){
  var rawB = lsGet(K_BANKS);
  if(rawB){ try { banks = JSON.parse(rawB) || {}; } catch(e){ banks = {}; } }
  var rawR = lsGet(K_RECS);
  if(rawR){ try { recs = JSON.parse(rawR) || {}; } catch(e){ recs = {}; } }

  // 落盘用的是规范格式（history/wrongOptions/flagged/starred），读回来要转成内部格式
  Object.keys(recs).forEach(function(bid){
    var m = recs[bid];
    if(!m || typeof m !== "object"){ delete recs[bid]; return; }
    Object.keys(m).forEach(function(qid){
      var r = m[qid];
      if(!r || typeof r !== "object"){ delete m[qid]; return; }
      if(r.history !== undefined || r.starred !== undefined || r.flagged !== undefined){
        m[qid] = specToRec(r);
      } else {
        if(r.star === undefined) r.star = 0;
        if(r.wo === undefined) r.wo = {};
        if(r.h === undefined) r.h = [];
      }
    });
  });

  // 迁移旧版单题库
  var oldBank = lsGet("qbank.bank.v1");
  if(oldBank){
    try {
      var b = JSON.parse(oldBank);
      var id = (b.meta && b.meta.id) || "migrated";
      if(!banks[id]){ banks[id] = b; saveBanks(); }
      var oldRec = lsGet("qbank.rec.v1");
      if(oldRec){
        try {
          var o = JSON.parse(oldRec);
          var rs = (o && (o.records || o.q)) || {};
          if(!recs[id]){ recs[id] = {}; }
          Object.keys(rs).forEach(function(qid){
            if(!recs[id][qid]) recs[id][qid] = specToRec(compat(rs[qid]));
          });
          saveRecs();
        } catch(e){}
      }
    } catch(e){}
  }

  if(!Object.keys(banks).length) seedFromEmbedded();

  // 清理没有对应题库的孤儿记录不删除（题库可能稍后再导入），只在统计时忽略
}

function chapterList(chId){
  if(!chId || !CH[chId]) return QS.filter(function(q){ return !q.ch || !CH[q.ch]; });
  return QS.filter(function(q){ return q.ch === chId; });
}

/* 回到上次那一题 */
function resumeLast(){
  var p = getPos();
  if(!p || !p.qid){ return false; }
  var q = BYID[p.qid];
  if(!q){ return false; }
  var list = chapterList(q.ch);
  var idx = -1;
  for(var i=0;i<list.length;i++){ if(list[i].id === q.id){ idx = i; break; } }
  if(idx < 0) return false;
  cur.list = list; cur.i = idx; cur.mode = "seq"; cur.title = q.chName;
  show("vQuiz"); renderQ();
  var tip = $("#resumeTip");
  if(tip) tip.style.display = "flex";
  return true;
}

/* 题目总览：按章列全部题号，点一下直接跳过去 */
function renderOverview(){
  var box = $("#ovBody");
  if(!QS.length){ box.innerHTML = '<div class="card muted">题库里没有题目。</div>'; return; }
  var html = '<div class="legend">' +
    '<span><i style="background:var(--ok-soft);border:1px solid rgba(26,127,75,.35)"></i>最近答对</span>' +
    '<span><i style="background:var(--bad-soft);border:1px solid rgba(192,42,42,.35)"></i>最近答错</span>' +
    '<span><i style="background:var(--card);border:1px solid var(--line)"></i>未做</span>' +
    '<span><i style="background:var(--warn);border-radius:50%"></i>右上角小点＝已标记</span>' +
    '<span>金框＝已收藏</span></div>';

  var blocks = BANK.chapters.map(function(c){ return { id:c.id, name:c.name }; });
  if(QS.some(function(q){ return !q.ch || !CH[q.ch]; })) blocks.push({ id:null, name:"未分章" });

  blocks.forEach(function(b){
    var list = b.id ? QS.filter(function(q){ return q.ch === b.id; })
                    : QS.filter(function(q){ return !q.ch || !CH[q.ch]; });
    if(!list.length) return;
    var done = 0;
    list.forEach(function(q){ var r = state.q[q.id]; if(r && r.attempts > 0) done++; });
    html += '<div class="ov-ch"><div class="ov-h"><b>' + esc(b.name) + '</b>' +
            '<span>' + done + ' / ' + list.length + ' 已做</span></div>';
    groupByType(list).forEach(function(g){
      html += '<div class="ov-t">' + esc(g.name) + ' · ' + g.items.length + ' 题</div><div class="qgrid">';
      g.items.forEach(function(q){
        var r = state.q[q.id] || {};
        var cls = "";
        if(r.lastCorrect === 1) cls += " ok";
        else if(r.lastCorrect === 0) cls += " bad";
        if(r.flag) cls += " fl";
        if(r.star) cls += " st";
        var label = q.no ? q.no : (list.indexOf(q) + 1);
        html += '<button class="' + cls + '" data-qid="' + esc(q.id) + '">' + label + '</button>';
      });
      html += '</div>';
    });
    html += '</div>';
  });
  box.innerHTML = html;

  Array.prototype.forEach.call(box.querySelectorAll("[data-qid]"), function(btn){
    btn.addEventListener("click", function(){ jumpToQ(btn.getAttribute("data-qid")); });
  });
}

function jumpToQ(qid){
  var q = BYID[qid];
  if(!q){ return; }
  var list = chapterList(q.ch);
  var idx = -1;
  for(var i=0;i<list.length;i++){ if(list[i].id === qid){ idx = i; break; } }
  if(idx < 0){ return; }
  cur.list = list; cur.i = idx; cur.mode = "seq"; cur.title = q.chName;
  show("vQuiz"); renderQ();
}

function bankList(){
  return Object.keys(banks).map(function(id){
    var b = banks[id];
    var n = (b.questions && b.questions.length) || 0;
    var chs = (b.chapters && b.chapters.length) || 0;
    var r = recs[id] || {};
    var done = 0, wrong = 0;
    Object.keys(r).forEach(function(qid){
      var x = r[qid];
      if(!x) return;
      if(x.attempts > 0){ done++; if(x.lastCorrect !== 1) wrong++; }
    });
    return {
      id: id,
      title: (b.meta && b.meta.title) || id,
      subject: (b.meta && b.meta.subject) || "",
      edition: (b.meta && b.meta.edition) || "",
      count: n, chapters: chs, done: done, wrong: wrong,
      total: n
    };
  }).sort(function(a,b){ return a.title.localeCompare(b.title, "zh"); });
}

function renderBanks(){
  var list = bankList();
  var box = $("#bankList");
  if(!list.length){
    box.innerHTML = '<div class="card"><div class="empty"><b>还没有题库</b>导入一个 .qbank.json 就能开始</div></div>';
    return;
  }
  var html = "";
  list.forEach(function(b){
    var pct = b.total ? Math.round(b.done/b.total*100) : 0;
    var col = pct>=80 ? "var(--ok)" : (pct>0 ? "var(--accent)" : "var(--sub)");
    html += '<div class="card bank" data-id="' + esc(b.id) + '">' +
      '<div class="bk-main">' +
        '<div class="bk-t">' + esc(b.title) + '</div>' +
        '<div class="bk-s">' + b.count + ' 题 · ' + b.chapters + ' 章' +
          (b.edition ? ' · ' + esc(b.edition) : '') + '</div>' +
        '<div class="bk-p">已做 ' + b.done + ' / ' + b.total +
          (b.wrong ? ' · <span style="color:var(--bad)">错 ' + b.wrong + '</span>' : '') + '</div>' +
      '</div>' +
      '<div class="bk-right">' +
        '<div class="ring" style="background:conic-gradient(' + col + ' ' + (pct*3.6) + 'deg, var(--line) 0)">' +
          '<span style="background:var(--card);width:40px;height:40px;border-radius:50%;display:grid;place-items:center;font-size:11px;font-weight:700">' + pct + '%</span>' +
        '</div>' +
        '<button class="del" data-del="' + esc(b.id) + '" title="删除题库">删除</button>' +
      '</div></div>';
  });
  box.innerHTML = html;

  Array.prototype.forEach.call(box.querySelectorAll("[data-del]"), function(btn){
    btn.addEventListener("click", function(e){
      e.stopPropagation();
      deleteBank(btn.getAttribute("data-del"));
    });
  });
  Array.prototype.forEach.call(box.querySelectorAll(".bank"), function(card){
    card.addEventListener("click", function(){ enterBank(card.getAttribute("data-id")); });
  });
}

function deleteBank(id){
  var b = banks[id];
  if(!b) return;
  var n = (b.questions && b.questions.length) || 0;
  if(!confirm("删除题库「" + ((b.meta && b.meta.title) || id) + "」？\n（共 " + n + " 题）")) return;
  var delRec = false;
  if(recs[id] && Object.keys(recs[id]).length){
    delRec = confirm("这个题库有做题记录。\n确定＝连记录一起删掉\n取消＝保留记录（以后重新导入同一题库还能接上）");
  }
  delete banks[id];
  if(delRec) delete recs[id];
  saveBanks(); saveRecs();
  if(curId === id){ curId = ""; show("vBanks"); }
  renderBanks();
}

function enterBank(id, opts){
  if(!banks[id]) return;
  var norm;
  try { norm = normalizeBank(banks[id]); }
  catch(e){ alert("这个题库读不出来：" + e.message); return; }

  curId = id;
  lsSet(K_CUR, id);
  BANK = norm;
  CH = {};
  BANK.chapters.forEach(function(c){ CH[c.id] = c; });
  QS = BANK.questions;
  BYID = {};
  QS.forEach(function(q){ BYID[q.id] = q; });
  if(!recs[id]) recs[id] = {};
  state.q = recs[id];

  $("#bankTitle").textContent = (BANK.meta && BANK.meta.title) || "题库";
  var sub = (BANK.meta && (BANK.meta.subject || BANK.meta.edition)) || "";
  $("#bankSub").textContent = QS.length + " 道题 · " + BANK.chapters.length + " 章" + (sub ? " · " + sub : "");
  $("#verLine").textContent = "题库版本 " + ((BANK.meta && BANK.meta.edition) || "—") + " · 记录仅存本机";

  var info = $("#bankInfo");
  info.innerHTML =
    '<span>题库名</span><span>' + esc(BANK.meta.title||"") + '</span>' +
    '<span>题库 ID</span><span>' + esc(BANK.meta.id||"") + '</span>' +
    '<span>题量</span><span>' + QS.length + ' 题 / ' + BANK.chapters.length + ' 章</span>' +
    '<span>来源</span><span>' + esc(BANK.meta.source||"（未填）") + '</span>' +
    '<span>版本</span><span>' + esc(BANK.meta.edition||"（未填）") + '</span>';

  refreshHomeStats();
  var s = stats();
  $("#btnContinue").textContent = s.done ? "继续练习（还剩 " + (s.total-s.done) + " 题）" : "开始练习";
  $("#btnContinue").disabled = !QS.length;
  $("#btnRandom").disabled = !QS.length;

  show("vHome");
  $("#hdTitle").textContent = (BANK.meta && BANK.meta.title) || "题库";

  if(opts && opts.resume){
    if(!resumeLast()){ /* 没有上次位置就停在首页 */ }
  }
}

/* ================= 记录 ================= */
function blankRec(){
  return { attempts:0, correct:0, wrong:0, lastPicked:[], lastCorrect:null, h:[], wo:{}, note:"", flag:0, star:0, ai:"", t:0 };
}
function getRec(id){ return state.q[id] || null; }
function recAcc(r){ return (r && r.attempts) ? Math.round(r.correct / r.attempts * 10000)/10000 : 0; }

function setRec(id, patch){
  var r = state.q[id] || blankRec();
  for(var k in patch){ if(Object.prototype.hasOwnProperty.call(patch,k)) r[k] = patch[k]; }
  r.t = Date.now();
  state.q[id] = r;
  persistRec();
  return r;
}

function persistRec(){
  if(!curId && BANK && BANK.meta && BANK.meta.id) curId = BANK.meta.id;   // 兜底，避免静默丢写
  if(!curId) return;
  recs[curId] = state.q;
  saveRecs();
  refreshHomeStats();
}

function recToSpec(r){
  return {
    attempts: r.attempts || 0,
    correct: r.correct || 0,
    wrong: r.wrong || 0,
    accuracy: recAcc(r),
    wrongOptions: r.wo || {},
    lastPicked: (r.lastPicked||[]).slice().sort(),
    lastCorrect: (r.lastCorrect===null) ? null : !!r.lastCorrect,
    history: (r.h||[]).map(function(x){
      return { at: x.at || "", picked: (x.p||[]).slice().sort(), correct: !!x.ok, answer: x.a || "" };
    }),
    note: r.note || "",
    flagged: !!r.flag,
    starred: !!r.star,
    aiAnalysis: r.ai || "",
    updatedAt: new Date(r.t||0).toISOString()
  };
}

function specToRec(s){
  var h = (Array.isArray(s.history) ? s.history : []).map(function(x){
    return { at: (x && x.at) || "", p: ((x && x.picked) || []).map(String), ok: (x && x.correct) ? 1 : 0,
             a: (x && x.answer) || "", t: Date.parse((x && x.at) || "") || 0 };
  }).slice(-50);

  // 数量归一：attempts 不能小于明细条数，correct/wrong 不能超过 attempts
  var att = Math.max(parseInt(s.attempts, 10) || 0, h.length);
  var cor = parseInt(s.correct, 10) || 0;
  if(cor < 0) cor = 0;
  if(cor > att) cor = att;
  var wr = att - cor;

  // 错选统计只保留 A–H 且非负整数
  var wo = {};
  if(s.wrongOptions && typeof s.wrongOptions === "object"){
    Object.keys(s.wrongOptions).forEach(function(k){
      var kk = String(k).toUpperCase();
      var v = parseInt(s.wrongOptions[k], 10);
      if(/^[A-H]$/.test(kk) && v > 0) wo[kk] = v;
    });
  }

  return {
    attempts: att,
    correct: cor,
    wrong: wr,
    lastPicked: (Array.isArray(s.lastPicked) ? s.lastPicked : []).map(String),
    lastCorrect: (s.lastCorrect === true) ? 1 : ((s.lastCorrect === false) ? 0 : null),
    h: h,
    wo: wo,
    note: typeof s.note === "string" ? s.note : "",
    flag: s.flagged ? 1 : 0,
    star: s.starred ? 1 : 0,
    ai: typeof s.aiAnalysis === "string" ? s.aiAnalysis : "",
    t: Date.parse(s.updatedAt || "") || Date.now()
  };
}

/* ================= 统计 ================= */
function stats(){
  var done=0, right=0, wrong=0, flag=0, star=0;
  var wrongIds=[], flagIds=[], everIds=[], heavyIds=[], starIds=[];
  QS.forEach(function(q){
    var r = state.q[q.id];
    if(!r) return;
    if(r.flag){ flag++; flagIds.push(q.id); }
    if(r.star){ star++; starIds.push(q.id); }
    if(r.wrong > 0){
      everIds.push(q.id);
      if(r.wrong >= 2) heavyIds.push(q.id);
    }
    if(r.attempts > 0){
      done++;
      if(r.lastCorrect === 1) right++; else { wrong++; wrongIds.push(q.id); }
    }
  });
  return { done:done, right:right, wrong:wrong, flag:flag, star:star, total:QS.length,
           wrongIds:wrongIds, flagIds:flagIds, everIds:everIds, heavyIds:heavyIds, starIds:starIds,
           acc: done ? Math.round(right/done*100) : null };
}

function buildWrongList(ids){
  return ids.map(function(id){ return BYID[id]; }).filter(Boolean).sort(function(a,b){
    var ra = state.q[a.id] || {}, rb = state.q[b.id] || {};
    var aa = ra.attempts ? ra.wrong/ra.attempts : 0;
    var ab = rb.attempts ? rb.wrong/rb.attempts : 0;
    if(ab !== aa) return ab - aa;
    if((rb.wrong||0) !== (ra.wrong||0)) return (rb.wrong||0)-(ra.wrong||0);
    return (a.no||0)-(b.no||0);
  });
}

function summaryOf(){
  var att=0, okAll=0, noted=0, s = stats();
  QS.forEach(function(q){
    var r = state.q[q.id];
    if(!r) return;
    att += r.attempts||0;
    okAll += r.correct||0;
    if(r.note) noted++;
  });
  return {
    totalQuestions: QS.length, attempted: s.done, correct: s.right, wrong: s.wrong,
    accuracy: s.acc===null ? 0 : Math.round(s.acc)/100,
    totalAttempts: att, noted: noted, flagged: s.flag,
    overallAccuracy: att ? Math.round(okAll/att*10000)/10000 : 0
  };
}

function refreshHomeStats(){
  if(!QS.length) return;
  var s = stats(), sum = summaryOf();
  $("#stDone").textContent = s.done + " / " + s.total;
  $("#stFill").style.width = (s.total ? s.done/s.total*100 : 0) + "%";
  $("#stAcc").textContent = s.acc===null ? "—" : s.acc + "%";
  $("#stFill2").style.width = (s.acc||0) + "%";
  $("#stWrong").textContent = s.wrong;
  $("#stFill3").style.width = (s.total ? s.wrong/s.total*100 : 0) + "%";
  $("#stTries").textContent = sum.totalAttempts;
  $("#stFill4").style.width = (s.total ? Math.min(100, sum.totalAttempts/s.total*100) : 0) + "%";
  $("#hdProg").textContent = s.done + "/" + s.total;
  $("#wrongRing").textContent = s.wrong;
  $("#flagRing").textContent = s.flag;
  $("#heavyRing").textContent = s.heavyIds.length;
  $("#wrongSub").textContent = s.everIds.length
    ? ("当前仍错 " + s.wrong + " 道 · 曾错 " + s.everIds.length + " 道（按错误率排）")
    : "还没有错题";
  $("#heavySub").textContent = s.heavyIds.length ? (s.heavyIds.length + " 道反复错") : "还没有";
  $("#flagSub").textContent = s.flag ? (s.flag + " 道已标记") : "还没有标记";
  $("#starRing").textContent = s.star;
  $("#starSub").textContent = s.star ? (s.star + " 道已收藏") : "还没有收藏";
  var chk = $("#chkAutoNext");
  if(chk) chk.checked = !!SET.autoNext;
  var chkS = $("#chkSound");
  if(chkS) chkS.checked = !!SET.sound;
  renderChapters();
}

function renderChapters(){
  var box = $("#chList");
  if(!QS.length){ box.innerHTML = ""; return; }
  var groups = BANK.chapters.map(function(c){ return { id:c.id, name:c.name }; });
  if(QS.some(function(q){ return !q.ch || !CH[q.ch]; })) groups.push({ id:"__none", name:"未分章" });
  var html = "";
  groups.forEach(function(c){
    var list = (c.id==="__none") ? QS.filter(function(q){ return !q.ch || !CH[q.ch]; })
                                 : QS.filter(function(q){ return q.ch === c.id; });
    if(!list.length) return;
    var done=0, right=0;
    list.forEach(function(q){ var r=state.q[q.id]; if(r&&r.attempts>0){ done++; if(r.lastCorrect===1) right++; } });
    var pct = Math.round(done/list.length*100);
    var col = pct>=80 ? "var(--ok)" : (pct>0 ? "var(--accent)" : "var(--sub)");
    html += '<div class="card ch" data-ch="' + esc(c.id) + '">' +
      '<div class="nm"><b>' + esc(c.name) + '</b><i>' + done + '/' + list.length + ' 题 · 对 ' + right + '</i></div>' +
      '<div class="ring" style="background:conic-gradient(' + col + ' ' + (pct*3.6) + 'deg, var(--line) 0)">' +
      '<span style="background:var(--card);width:36px;height:36px;border-radius:50%;display:grid;place-items:center">' + pct + '%</span></div></div>';
  });
  box.innerHTML = html || '<div class="card muted">题库里没有题目。</div>';
  Array.prototype.forEach.call(box.querySelectorAll("[data-ch]"), function(el){
    el.addEventListener("click", function(){
      var id = el.getAttribute("data-ch");
      var list = (id==="__none") ? QS.filter(function(q){ return !q.ch || !CH[q.ch]; })
                                 : QS.filter(function(q){ return q.ch === id; });
      var nm = (id==="__none") ? "未分章" : (CH[id] ? CH[id].name : id);
      startQuiz(list, "seq", nm);
    });
  });
}

/* ================= 判分 ================= */
function sameSet(a,b){
  if(a.length!==b.length) return false;
  return a.slice().sort().join("") === b.slice().sort().join("");
}
function isCorrect(q, picked){
  if(!picked || !picked.length) return false;
  return sameSet(picked.map(function(s){ return String(s).toUpperCase(); }), q.answer);
}
function isMulti(q){ return q.type==="multi" || q.type==="indefinite"; }
var TYPE_ORDER = ["single","multi","indefinite","judge"];
function groupByType(list){
  var out = [];
  TYPE_ORDER.forEach(function(t){
    var arr = list.filter(function(q){ return q.type === t; });
    if(arr.length) out.push({ type:t, name:typeName({type:t}), items:arr });
  });
  return out;
}
function typeName(q){
  if(q.type==="multi") return "多选题";
  if(q.type==="indefinite") return "不定项选择题";
  if(q.type==="judge") return "判断题";
  return "单选题";
}

/* ================= 视图 ================= */
function show(v){
  view = v;
  ["vBanks","vHome","vQuiz","vCheck","vOverview"].forEach(function(id){
    var el = $("#"+id); if(el) el.classList.add("hide");
  });
  $("#"+v).classList.remove("hide");
  $("#navBar").style.display = (v==="vQuiz") ? "flex" : "none";
  var back = $("#btnHome"), gear = $("#btnSettings");
  if(v === "vBanks"){
    back.style.display = "none";
    if(gear) gear.style.display = "none";
    $("#hdTitle").textContent = "题库系统"; $("#hdProg").textContent = "";
  } else {
    back.style.display = "inline-flex";
    if(gear) gear.style.display = "inline-flex";
  }
  document.querySelector("main").scrollTop = 0;
  if(v === "vBanks") renderBanks();
}

function goBack(){
  flushNote();
  if(view === "vQuiz" || view === "vCheck" || view === "vOverview"){
    show("vHome");
    $("#hdTitle").textContent = (BANK.meta && BANK.meta.title) || "题库";
    refreshHomeStats();
  } else {
    curId = "";
    lsSet(K_CUR, "");
    show("vBanks");
  }
}

function startQuiz(list, mode, title){
  if(!list.length){ alert("这一组没有题目。"); return; }
  cur.list = list; cur.i = 0; cur.mode = mode; cur.title = title || "练习";
  show("vQuiz"); renderQ();
}

function renderQ(){
  var q = cur.list[cur.i];
  if(!q) return;
  var r = getRec(q.id) || blankRec();
  var locked = (r.lastCorrect === 1 || r.lastCorrect === 0);
  var picked = r.lastPicked || [];
  var tagCls = r.lastCorrect===1 ? "ok" : (r.lastCorrect===0 ? "bad" : "");
  var tags = (q.tags||[]).map(function(t){
    return '<span class="tag" style="background:#eceff3;color:var(--sub)">' + esc(t) + '</span>';
  }).join("");

  $("#qHead").innerHTML =
    '<span class="tag">' + esc(q.chName) + '</span>' +
    '<span class="tag ' + tagCls + '">' + typeName(q) + (q.no ? " 第 " + q.no + " 题" : "") + '</span>' +
    (r.flag ? '<span class="tag" style="background:#fff4e0;color:var(--warn)">已标记</span>' : '') +
    (r.star ? '<span class="tag" style="background:#fff8e1;color:#a86a00">★ 收藏</span>' : '') +
    (r.attempts ? '<span style="font-size:12px">做 ' + r.attempts + ' 次 · 错 ' + r.wrong + ' 次 · 错误率 ' +
      Math.round((r.attempts - r.correct)/r.attempts*100) + '%</span>' : '') + tags;

  $("#qStem").textContent = q.stem;

  var html = "";
  q.keys.forEach(function(k){
    var sel = picked.indexOf(k) >= 0;
    var cls = "opt";
    if(locked){
      cls += " locked";
      if(q.answer.indexOf(k)>=0) cls += " correct";
      else if(sel) cls += " wrong";
    } else if(sel) cls += " sel";
    html += '<button class="' + cls + '" data-k="' + k + '"><span class="k">' + k + '</span><span class="tx">' + esc(q.options[k]) + '</span></button>';
  });
  $("#qOpts").innerHTML = html;
  Array.prototype.forEach.call($("#qOpts").querySelectorAll(".opt"), function(b){
    b.addEventListener("click", function(){ pickOpt(b.getAttribute("data-k")); });
  });

  ["#qStem", "#qOpts"].forEach(function(sel){
    var el = $(sel);
    if(!el) return;
    el.classList.remove("qwrap-in");
    void el.offsetWidth;
    el.classList.add("qwrap-in");
  });

  var fb = $("#qFb");
  fb.innerHTML = "";
  if(locked){
    if(r.lastCorrect===1){
      fb.innerHTML = '<div class="fb ok"><b>答对了</b>' + (q.analysis ? '<span class="an">解析：' + esc(q.analysis) + '</span>' : '') + '</div>';
    } else {
      fb.innerHTML = '<div class="fb bad"><b>答错了</b> · 正确答案 <b>' + q.answer.join("") + '</b>' +
        (q.analysis ? '<span class="an">解析：' + esc(q.analysis) + '</span>' : '') + '</div>';
    }
  }

  if(r.attempts){
    var acc = Math.round(r.correct / r.attempts * 100);
    var wos = r.wo || {}, wk = Object.keys(wos).sort();
    var woHtml = wk.length ? wk.map(function(k){ return '<span class="wo">' + esc(k) + ' × ' + wos[k] + '</span>'; }).join("")
                           : '<span>还没有选错过的选项</span>';
    var detail = "";
    if(r.h && r.h.length){
      detail = '<details style="margin-top:8px"><summary style="cursor:pointer;font-size:13px;color:var(--sub);list-style:none">' +
        '▸ 逐次明细（最近 ' + r.h.length + ' 次）</summary><div style="margin-top:6px">' +
        r.h.slice().reverse().map(function(it, i){
          var d = new Date(it.t||0);
          var when = it.t ? ((d.getMonth()+1)+"-"+pad(d.getDate())+" "+pad(d.getHours())+":"+pad(d.getMinutes())) : "";
          var pk = (it.p||[]).slice().sort().join("") || "（空）";
          return '<div class="hi"><b>第' + (r.h.length-i) + '次</b><span class="' + (it.ok?"c":"w") + '">' +
                 (it.ok?"对":"错") + '</span><span>选 ' + pk + '</span>' +
                 (!it.ok && it.a ? '<span class="muted" style="font-size:12px">应选 ' + it.a + '</span>' : '') +
                 '<span class="muted" style="margin-left:auto;font-size:12px">' + when + '</span></div>';
        }).join("") + '</div></details>';
    }
    fb.innerHTML += '<div class="hist">' +
      '<div class="statline"><span>作答 <b>' + r.attempts + '</b> 次</span>' +
      '<span>对 <b>' + r.correct + '</b></span><span>错 <b>' + r.wrong + '</b></span>' +
      '<span>错误率 <b>' + (100-acc) + '%</b></span><span>正确率 <b>' + acc + '%</b></span></div>' +
      '<div class="wopts">错的选项：' + woHtml + '</div>' + detail + '</div>';
  }

  if(r.ai) fb.innerHTML += '<div class="aiBox"><div class="aiT">AI 分析</div><div class="aiBody">' + esc(r.ai) + '</div></div>';

  var sub = $("#btnSubmit");
  if(isMulti(q) && !locked){
    sub.style.display = "flex";
    sub.disabled = picked.length === 0;
    sub.textContent = "提交答案" + (picked.length ? "（已选 " + picked.slice().sort().join("") + "）" : "");
  } else { sub.style.display = "none"; }

  $("#qNote").value = r.note || "";
  $("#noteSaved").textContent = r.note ? "已保存" : "";
  $("#btnFlag").textContent = r.flag ? "取消标记" : "标记为有疑问";
  $("#btnStar").textContent = r.star ? "★ 已收藏" : "☆ 收藏";
  $("#btnStar").style.color = r.star ? "var(--warn)" : "";

  $("#navPos").textContent = (cur.i+1) + " / " + cur.list.length;
  $("#btnPrev").disabled = cur.i === 0;
  $("#btnNext").disabled = cur.i >= cur.list.length-1;
  $("#hdTitle").textContent = cur.title;
  if(cur.mode === "seq") savePos(q.id);
  document.querySelector("main").scrollTop = 0;
}

function pickOpt(k){
  var q = cur.list[cur.i];
  var r = getRec(q.id) || blankRec();
  if(r.lastCorrect === 1 || r.lastCorrect === 0) return;
  var p = (r.lastPicked||[]).slice();
  if(isMulti(q)){
    var at = p.indexOf(k);
    if(at>=0) p.splice(at,1); else p.push(k);
    setRec(q.id, { lastPicked:p });
    renderQ();
  } else {
    setRec(q.id, { lastPicked:[k] });
    grade(q);
  }
}

function grade(q){
  var r = getRec(q.id) || blankRec();
  var p = r.lastPicked || [];
  if(!p.length) return;
  var ok = isCorrect(q, p);
  var h = (r.h||[]).slice(-49);
  h.push({ t: Date.now(), at: isoNow(), p: p.slice().sort(), ok: ok?1:0, a: q.answer.join("") });
  var wo = {};
  Object.keys(r.wo||{}).forEach(function(k){ wo[k] = r.wo[k]; });
  if(!ok){ p.forEach(function(k){ if(q.answer.indexOf(k)<0) wo[k] = (wo[k]||0)+1; }); }
  setRec(q.id, {
    attempts: (r.attempts||0)+1,
    correct: (r.correct||0) + (ok?1:0),
    wrong: (r.wrong||0) + (ok?0:1),
    lastCorrect: ok?1:0, h: h, wo: wo
  });
  renderQ();

  if(ok) sndCorrect(); else sndWrong();

  if(ok && SET.autoNext && cur.i < cur.list.length - 1){
    var from = cur.i, qid = q.id;
    setTimeout(function(){
      if(view !== "vQuiz") return;
      if(cur.i !== from) return;                     // 用户已经自己跳了
      var rr = getRec(qid);
      if(!rr || rr.lastCorrect !== 1) return;        // 已经重做就别跳了
      go(1);
    }, SET.delay);
  }
}

function go(d){
  var n = cur.i + d;
  if(n<0 || n>=cur.list.length) return;
  flushNote(); cur.i = n; renderQ();
}
function jump(i){ flushNote(); cur.i = i; renderQ(); }

function flushNote(){
  if(!cur.list.length) return;
  var q = cur.list[cur.i], v = $("#qNote").value, r = getRec(q.id);
  if(r && r.note === v) return;
  if(!r && !v) return;
  setRec(q.id, { note:v });
}
function onNoteInput(){
  var q = cur.list[cur.i];
  clearTimeout(noteTimer);
  noteTimer = setTimeout(function(){
    setRec(q.id, { note: $("#qNote").value });
    $("#noteSaved").textContent = "已保存";
    clearTimeout(savedTimer);
    savedTimer = setTimeout(function(){ $("#noteSaved").textContent = ""; }, 1800);
  }, 500);
}

function openSheet(){
  var html = '<h3>' + esc(cur.title) + ' · 共 ' + cur.list.length + ' 题</h3>';
  groupByType(cur.list).forEach(function(g){
    html += '<div class="sheet-t">' + esc(g.name) + ' · ' + g.items.length + ' 题</div><div class="qgrid">';
    g.items.forEach(function(q){
      var i = cur.list.indexOf(q);
      var r = state.q[q.id], cls = "";
      if(r && r.lastCorrect===1) cls += " ok";
      else if(r && r.lastCorrect===0) cls += " bad";
      if(r && r.flag) cls += " fl";
      if(r && r.star) cls += " st";
      if(i===cur.i) cls += " cur";
      html += '<button class="' + cls + '" data-i="' + i + '">' + (q.no ? q.no : (i+1)) + '</button>';
    });
    html += '</div>';
  });
  var mask = document.createElement("div");
  mask.className = "sheet";
  mask.innerHTML = '<div class="inner">' + html + '</div>';
  mask.addEventListener("click", function(e){
    if(e.target===mask){ mask.remove(); return; }
    var b = e.target.closest("[data-i]");
    if(b){ var i = parseInt(b.getAttribute("data-i"),10); mask.remove(); jump(i); }
  });
  document.body.appendChild(mask);
}

/* ================= 导出 ================= */
function nativeSave(name, text, mime){
  try {
    if(window.AndroidApp && window.AndroidApp.saveFile){ window.AndroidApp.saveFile(name, mime||"text/plain", text); return true; }
  } catch(e){}
  return false;
}
function download(name, text, mime){
  if(nativeSave(name, text, mime)) return;
  try {
    window.__lastExport = { name:name, mime:mime, text:text };
    var blob = new Blob([text], { type:(mime||"text/plain")+";charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = name; a.style.display = "none";
    document.body.appendChild(a); a.click();
    setTimeout(function(){ URL.revokeObjectURL(url); a.remove(); }, 1500);
  } catch(e){ alert("导出失败：" + e.message); }
}

function buildRecordObject(){
  var sum = summaryOf(), out = {};
  QS.forEach(function(q){
    var r = state.q[q.id];
    if(!r) return;
    if(!r.attempts && !r.note && !r.flag && !r.star && !r.ai) return;
    out[q.id] = recToSpec(r);
  });
  return {
    format:"qbank-record", version:"1.0",
    bankId: (BANK.meta && BANK.meta.id) || "",
    bankTitle: (BANK.meta && BANK.meta.title) || "",
    exportedAt: isoNow(), summary: sum, records: out
  };
}

function exportRec(){
  flushNote();
  var obj = buildRecordObject();
  if(!Object.keys(obj.records).length){ alert("这个题库还没有任何记录。"); return; }
  download("做题记录_" + ((BANK.meta&&BANK.meta.id)||"题库") + "_" + stamp() + ".qrec.json",
           JSON.stringify(obj, null, 1), "application/json");
}

function mergeHist(a, b){
  var map = {}, arr = [];
  (a||[]).concat(b||[]).forEach(function(x){
    if(!x) return;
    var k = (x.t||0) + "|" + (x.p||[]).slice().sort().join("") + "|" + (x.ok?1:0);
    if(!map[k]){ map[k] = x; arr.push(x); }
  });
  arr.sort(function(m,n){ return (m.t||0)-(n.t||0); });
  return arr.slice(-50);
}

function compat(s){
  if(s && s.history) return s;
  if(s && (s.p || s.n !== undefined)){
    var h = (s.h||[]).map(function(x){ return { at:x.at||"", picked:x.p||[], correct:!!x.ok, answer:x.a||"" }; });
    return {
      attempts: s.n || h.length, correct: h.filter(function(x){return x.correct;}).length,
      wrong: h.filter(function(x){return !x.correct;}).length, accuracy: 0, wrongOptions: {},
      lastPicked: Array.isArray(s.p) ? s.p : [],
      lastCorrect: (s.ok===1||s.ok===true) ? true : ((s.ok===0||s.ok===false) ? false : null),
      history: h, note: s.note||"", flagged: !!s.flag, aiAnalysis: s.ai||"",
      updatedAt: s.t ? new Date(s.t).toISOString() : new Date().toISOString()
    };
  }
  return s;
}

function mapId(id){ return id.replace(/^c(\d+)-/, "ch$1-"); }

/* 记录文件严格校验：返回问题列表，空数组表示可以导入 */
function validateRecordFile(o){
  var errs = [];
  if(!o || typeof o !== "object" || Array.isArray(o)) return ["文件内容不是 JSON 对象"];

  if(o.format !== "qbank-record") errs.push("format 必须是 qbank-record（实际：" + o.format + "）");
  if(String(o.version) !== "1.0") errs.push("version 必须是 1.0（实际：" + o.version + "）");

  var bid = (BANK.meta && BANK.meta.id) || "";
  if(!o.bankId) errs.push("缺少 bankId：记录文件必须写明属于哪个题库");
  else if(o.bankId !== bid) errs.push("bankId 不匹配：文件属于「" + o.bankId + "」，当前题库是「" + bid + "」");

  var rs = o.records;
  if(!rs || typeof rs !== "object" || Array.isArray(rs)){ errs.push("records 必须是对象"); return errs; }

  var ids = Object.keys(rs);
  if(!ids.length) errs.push("records 是空的");

  var miss = [], bad = [];
  ids.forEach(function(id){
    if(!BYID[id]){ miss.push(id); return; }
    var r = rs[id];
    if(!r || typeof r !== "object"){ bad.push(id + " 不是对象"); return; }
    if(r.attempts !== undefined && (!(r.attempts >= 0) || Math.floor(r.attempts) !== r.attempts))
      bad.push(id + " 的 attempts 必须是非负整数");
    if(r.correct !== undefined && (!(r.correct >= 0) || r.correct > (r.attempts || 0)))
      bad.push(id + " 的 correct 超过 attempts");
    if(r.history !== undefined && !Array.isArray(r.history)) bad.push(id + " 的 history 必须是数组");
    if(Array.isArray(r.history) && r.history.length > 50) bad.push(id + " 的 history 超过 50 条上限");
    if(r.wrongOptions !== undefined && (typeof r.wrongOptions !== "object" || Array.isArray(r.wrongOptions)))
      bad.push(id + " 的 wrongOptions 必须是对象");
    if(r.flagged !== undefined && typeof r.flagged !== "boolean") bad.push(id + " 的 flagged 必须是布尔");
    if(r.starred !== undefined && typeof r.starred !== "boolean") bad.push(id + " 的 starred 必须是布尔");
    if(r.note !== undefined && typeof r.note !== "string") bad.push(id + " 的 note 必须是字符串");
  });

  if(miss.length) errs.push("有 " + miss.length + " 个题号在当前题库里找不到：" + miss.slice(0, 6).join("、") + (miss.length > 6 ? " 等" : ""));
  if(bad.length) errs.push("字段不合法：" + bad.slice(0, 6).join("；") + (bad.length > 6 ? " 等" : ""));
  return errs;
}

function importRec(file, mode){
  var fr = new FileReader();
  fr.onload = function(){
    var parsed;
    try { parsed = parseLooseJson(String(fr.result)); }
    catch(e){ alert("不是有效的 JSON：\n" + e.message); return; }
    var o = parsed.data;

    var errs = validateRecordFile(o);
    if(errs.length){
      alert("这份记录不能导入，已取消，什么都没改。\n\n" + errs.slice(0, 6).join("\n") +
            (errs.length > 6 ? "\n……" : "") +
            "\n\n要求：format=qbank-record、version=1.0、bankId 与当前题库一致、题号必须存在于本题库。");
      return;
    }

    var recsIn = o.records;
    var added = 0, updated = 0, kept = 0, histAdd = 0;

    if(mode === "over"){
      var fresh = {};
      Object.keys(recsIn).forEach(function(id){
        fresh[id] = specToRec(compat(recsIn[id]));
        added++;
      });
      state.q = fresh;
    } else {
      Object.keys(recsIn).forEach(function(id){
        var nr = specToRec(compat(recsIn[id]));
        var local = state.q[id];
        if(!local){ state.q[id] = nr; added++; return; }
        var merged = mergeHist(local.h, nr.h);
        if(merged.length > (local.h || []).length) histAdd++;
        if((nr.t || 0) > (local.t || 0)){
          nr.h = merged;
          if(!nr.note && local.note) nr.note = local.note;
          if(!nr.ai && local.ai) nr.ai = local.ai;
          var wo = {};
          Object.keys(local.wo || {}).forEach(function(k){ wo[k] = local.wo[k]; });
          Object.keys(nr.wo || {}).forEach(function(k){ wo[k] = (wo[k] || 0) + nr.wo[k]; });
          nr.wo = wo;
          state.q[id] = nr;
          updated++;
        } else {
          local.h = merged;
          var wo2 = local.wo || {};
          Object.keys(nr.wo || {}).forEach(function(k){ wo2[k] = (wo2[k] || 0) + nr.wo[k]; });
          local.wo = wo2;
          kept++;
        }
      });
    }

    // 写入前再归一一次，保证落盘自洽
    Object.keys(state.q).forEach(function(id){ state.q[id] = specToRec(recToSpec(state.q[id])); });
    persistRec();
    alert((mode === "over" ? "已覆盖。" : "已合并。") + "\n新增 " + added + " 条，更新 " + updated + " 条" +
      (mode === "over" ? "" : "，保留本机较新 " + kept + " 条") +
      (histAdd ? "，补入 " + histAdd + " 题的作答明细" : "") + "。");
  };
  fr.readAsText(file, "utf-8");
}

function collect(){
  flushNote();
  var out = [];
  QS.forEach(function(q){
    var r = state.q[q.id];
    if(!r) return;
    if(!r.attempts && !r.note && !r.flag && !r.star && !r.ai && !(r.h && r.h.length)) return;
    out.push({ q:q, r:r });
  });
  return out;
}

function exportMd(){
  var rows = collect();
  if(!rows.length){ alert("还没有任何记录，先做几道题。"); return; }
  var s = stats(), sum = summaryOf(), L = [];
  L.push("# " + ((BANK.meta && BANK.meta.title) || "题库") + " · 我的做题记录");
  L.push("");
  L.push("- 导出时间：" + today());
  L.push("- 进度：" + s.done + " / " + s.total + " 题，最近一次答对 " + s.right + "，答错 " + s.wrong +
         (s.acc===null ? "" : "，正确率 " + s.acc + "%"));
  L.push("- 总作答次数：" + sum.totalAttempts + "，标记 " + s.flag + " 题");
  L.push("");
  L.push("> 每题给出作答次数、错误率、错选分布、逐次明细、我的笔记与 AI 分析。");
  L.push("");
  var lastCh = null;
  rows.forEach(function(it){
    var q = it.q, r = it.r;
    if(q.chName !== lastCh){ L.push(""); L.push("## " + q.chName); L.push(""); lastCh = q.chName; }
    var acc = Math.round(r.correct / Math.max(1,r.attempts) * 100);
    L.push("### " + (q.no ? "第 " + q.no + " 题" : "题") + "（" + typeName(q) + "）· " +
           (r.lastCorrect===1 ? "答对" : (r.lastCorrect===0 ? "**答错**" : "未作答")) + (r.flag ? " · 已标记" : ""));
    L.push("");
    L.push("*题目 id：" + q.id + "*");
    L.push("");
    L.push(q.stem);
    L.push("");
    q.keys.forEach(function(k){ L.push("- " + k + ". " + q.options[k]); });
    L.push("");
    L.push("- 正确答案：" + q.answer.join(""));
    L.push("- 我的最近作答：" + (((r.lastPicked||[]).slice().sort().join("")) || "（空）"));
    L.push("- 作答 " + (r.attempts||0) + " 次，对 " + (r.correct||0) + "，错 " + (r.wrong||0) +
           "，错误率 " + (r.attempts ? (100-acc) : 0) + "%");
    var wos = r.wo || {}, wk = Object.keys(wos).sort();
    L.push("- 错选的选项：" + (wk.length ? wk.map(function(k){ return k+"×"+wos[k]; }).join("、") : "无"));
    if(q.analysis) L.push("- 题库解析：" + q.analysis);
    if(r.h && r.h.length){
      L.push("- 逐次明细：");
      r.h.forEach(function(x,i){
        var d = new Date(x.t||0);
        var when = x.t ? ((d.getMonth()+1)+"-"+d.getDate()+" "+pad(d.getHours())+":"+pad(d.getMinutes())) : "";
        L.push("    " + (i+1) + ". " + (x.ok?"对":"错") + "　选 " +
               (((x.p||[]).slice().sort().join("")) || "（空）") +
               (!x.ok && x.a ? "　应选 " + x.a : "") + (when ? "　" + when : ""));
      });
    }
    L.push("");
    L.push("我的笔记：");
    L.push("");
    L.push(r.note ? r.note.split("\n").map(function(x){ return "> " + x; }).join("\n") : "> （无）");
    L.push("");
    L.push("【AI 分析】");
    L.push("");
    L.push(r.ai || "（待补充）");
    L.push("");
    L.push("---");
    L.push("");
  });
  download("复习笔记_" + today() + ".md", L.join("\n"), "text/markdown");
}

function exportHtml(){
  var rows = collect();
  if(!rows.length){ alert("还没有任何记录，先做几道题。"); return; }
  var s = stats(), sum = summaryOf();
  var body = "", lastCh = null, idx = 0;
  rows.forEach(function(it){
    idx++;
    var q = it.q, r = it.r;
    if(q.chName !== lastCh){ body += '<h2>' + esc(q.chName) + '</h2>'; lastCh = q.chName; }
    var acc = Math.round(r.correct / Math.max(1,r.attempts) * 100);
    var cls = r.lastCorrect===1 ? "ok" : (r.lastCorrect===0 ? "bad" : "");
    var mark = r.lastCorrect===1 ? "答对" : (r.lastCorrect===0 ? "答错" : "未作答");
    body += '<div class="item"><div class="ih"><span class="n">' + idx + '</span><span class="ty">' +
            esc(q.chName) + ' · ' + typeName(q) + (q.no ? ' 第 ' + q.no + ' 题' : '') + '</span>' +
            '<span class="flag ' + cls + '">' + mark + '</span>' +
            (r.flag ? '<span class="flag mark">已标记</span>' : '') + '</div>';
    body += '<div class="stem">' + esc(q.stem) + '</div><div class="opts">';
    q.keys.forEach(function(k){
      var c = q.answer.indexOf(k)>=0 ? " right" : (((r.lastPicked||[]).indexOf(k)>=0) ? " picked" : "");
      body += '<div class="op' + c + '"><b>' + k + '</b>. ' + esc(q.options[k]) + '</div>';
    });
    body += '</div>';
    body += '<div class="ans"><span>我的最近作答：<b>' +
            ((((r.lastPicked||[]).slice().sort().join(""))) || "（空）") + '</b></span>' +
            '<span>正确答案：<b class="rt">' + q.answer.join("") + '</b></span></div>';
    body += '<div class="hs"><b>作答 ' + (r.attempts||0) + ' 次 ｜ 对 ' + (r.correct||0) + ' ｜ 错 ' + (r.wrong||0) +
            ' ｜ 错误率 ' + (r.attempts ? (100-acc) : 0) + '%</b>';
    var wos = r.wo || {}, wk = Object.keys(wos).sort();
    if(wk.length) body += '<div class="wo">错的选项：' + wk.map(function(k){ return k + '×' + wos[k]; }).join('、') + '</div>';
    if(r.h && r.h.length){
      body += '<div class="wo">' + r.h.map(function(x,i){
        return '<span class="' + (x.ok?"hc":"hw") + '">' + (i+1) + "." + (x.ok?"对":"错") + " " +
               (((x.p||[]).slice().sort().join("")) || "空") + "</span>";
      }).join("　") + '</div>';
    }
    body += '</div>';
    if(q.analysis) body += '<div class="an">题库解析：' + esc(q.analysis) + '</div>';
    body += '<div class="nt"><div class="ntl">我的笔记 / 疑问</div><div class="ntb">' +
            (r.note ? esc(r.note).replace(/\n/g,"<br>") : '<span class="ph">（无）</span>') + '</div></div>';
    body += '<div class="ai"><div class="ntl">AI 分析</div><div class="ntb' + (r.ai?'':' ph') + '">' +
            (r.ai ? esc(r.ai).replace(/\n/g,"<br>") : '（待补充）') + '</div></div></div>';
  });

  var page = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">' +
  '<meta name="viewport" content="width=device-width,initial-scale=1"><title>' +
  esc((BANK.meta && BANK.meta.title) || "题库") + ' 复习版</title><style>' +
  'body{font:15px/1.75 -apple-system,"PingFang SC","Microsoft YaHei",serif;max-width:860px;margin:0 auto;padding:28px 22px;color:#111}' +
  'h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:30px 0 12px;padding-bottom:6px;border-bottom:2px solid #222}' +
  '.meta{color:#666;font-size:13px;margin-bottom:8px}' +
  '.item{border:1px solid #dcdcdc;border-radius:8px;padding:14px 16px;margin:14px 0;page-break-inside:avoid}' +
  '.ih{display:flex;gap:8px;align-items:center;font-size:12px;color:#666;margin-bottom:8px;flex-wrap:wrap}' +
  '.n{background:#333;color:#fff;border-radius:4px;padding:1px 6px;font-weight:700}.ty{flex:1}' +
  '.flag{border:1px solid #bbb;border-radius:10px;padding:0 8px}' +
  '.flag.ok{color:#1a7f4b;border-color:#1a7f4b}.flag.bad{color:#c02a2a;border-color:#c02a2a}.flag.mark{color:#a86a00;border-color:#a86a00}' +
  '.stem{font-size:15.5px;font-weight:600;margin-bottom:10px;white-space:pre-wrap}' +
  '.opts{margin-bottom:10px}.op{padding:2px 0 2px 6px;color:#333}' +
  '.op.right{color:#1a7f4b;font-weight:600}.op.picked{text-decoration:underline}' +
  '.ans{display:flex;gap:22px;font-size:14px;margin:8px 0;flex-wrap:wrap}.ans .rt{color:#1a7f4b}' +
  '.hs{font-size:12.5px;color:#555;margin:8px 0;line-height:1.9;border-left:3px solid #ddd;padding-left:8px}' +
  '.hs .wo{color:#777;font-size:12px}.hs .hc{color:#1a7f4b;margin-right:8px}.hs .hw{color:#c02a2a;margin-right:8px}' +
  '.an{background:#f6f8fa;border-left:3px solid #999;padding:8px 10px;font-size:13.5px;color:#444;margin:8px 0}' +
  '.nt,.ai{margin-top:9px}.ntl{font-size:12px;color:#888;margin-bottom:3px}' +
  '.ntb{min-height:42px;border:1px dashed #ccc;border-radius:6px;padding:8px 10px;font-size:14px;background:#fcfcfc}' +
  '.ai .ntb{min-height:56px;background:#fafafa}.ph{color:#aaa}' +
  '@media print{body{padding:0;max-width:none;font-size:12.5pt}.item{page-break-inside:avoid}.ntb,.ai .ntb{background:#fff}' +
  '.n{-webkit-print-color-adjust:exact;print-color-adjust:exact}@page{margin:16mm 14mm}}' +
  '</style></head><body>';
  page += '<h1>' + esc((BANK.meta && BANK.meta.title) || "题库") + ' · 复习版</h1>';
  page += '<div class="meta">导出时间 ' + today() + ' ｜ 进度 ' + s.done + '/' + s.total +
          ' ｜ 总作答 ' + sum.totalAttempts + ' 次 ｜ 正确率 ' + (s.acc===null ? "—" : s.acc + '%') +
          ' ｜ 标记 ' + s.flag + ' 题</div>' + body +
          '<p style="color:#999;font-size:12px;text-align:center;margin-top:30px">— 浏览器打开后 Ctrl+P 可打印或存 PDF —</p></body></html>';
  download("复习版_" + today() + ".html", page, "text/html");
}

/* ================= AI ================= */
function exportAiPack(){
  flushNote();
  var rows = collect();
  if(!rows.length){ alert("还没有任何记录。先做几道题。"); return; }
  var list = rows.map(function(it){
    var q = it.q, r = it.r;
    return {
      id: q.id, chapter: q.chName, type: q.type, number: q.no,
      stem: q.stem,
      options: q.keys.map(function(k){ return { key:k, text:q.options[k] }; }),
      answer: q.answer.join(""), analysis: q.analysis || "",
      myStats: {
        attempts: r.attempts||0, correct: r.correct||0, wrong: r.wrong||0,
        accuracy: recAcc(r), wrongOptions: r.wo||{},
        lastPicked: (r.lastPicked||[]).slice().sort(), lastCorrect: r.lastCorrect===1
      },
      attempts: (r.h||[]).map(function(x){ return { picked:(x.p||[]).slice().sort(), correct:!!x.ok, at:x.at||"" }; }),
      note: r.note || "", existingAnalysis: r.ai || ""
    };
  });
  var pack = {
    format: "qbank-ai-request", version: "1.0",
    instruction: "请为 questions 里每道题补写分析：先用一两句点出考点，再说明正确项为什么对、易错项为什么错，最后给一条 30 字以内的记忆提示。简体中文，不要编造题库之外的内容。",
    replyFormat: { format: "qbank-ai", version: "1.0", analyses: { "题目id": "分析文本" } },
    generatedAt: isoNow(),
    bank: { id: (BANK.meta && BANK.meta.id) || "", title: (BANK.meta && BANK.meta.title) || "" },
    questions: list
  };
  download("AI分析请求_" + stamp() + ".json", JSON.stringify(pack, null, 1), "application/json");
}

function importAi(file){
  var fr = new FileReader();
  fr.onload = function(){
    var o;
    try { o = parseLooseJson(String(fr.result)).data; } catch(e){ alert("不是有效的 JSON。"); return; }
    var map = o.analyses || o.analysis || null;
    if(!map && o.records){
      map = {};
      Object.keys(o.records).forEach(function(id){
        if(o.records[id] && typeof o.records[id].aiAnalysis === "string") map[id] = o.records[id].aiAnalysis;
      });
    }
    if(!map && typeof o === "object"){
      var ks = Object.keys(o);
      if(ks.length && ks.every(function(k){ return BYID[k]; })) map = o;
    }
    if(!map || typeof map !== "object"){ alert('没找到 analyses。需要形如 {"analyses":{"题目id":"分析"}}。'); return; }
    var n = 0, miss = 0;
    Object.keys(map).forEach(function(id0){
      var id = BYID[id0] ? id0 : mapId(id0);
      if(!BYID[id]){ miss++; return; }
      var txt = map[id0];
      if(txt && typeof txt === "object") txt = txt.text || txt.analysis || "";
      txt = String(txt==null ? "" : txt).trim();
      if(!txt) return;
      var r = state.q[id] || blankRec();
      r.ai = txt; r.t = Date.now();
      state.q[id] = r; n++;
    });
    persistRec();
    alert("已写入 " + n + " 道题的 AI 分析" + (miss ? "，另有 " + miss + " 个题号找不到，已跳过" : "") + "。");
  };
  fr.readAsText(file, "utf-8");
}

/* 宽容解析：AI 回复常带 ``` 围栏或前后说明文字，这里只剥「运输层」外壳。
   数据本身的校验仍走各自的严格逻辑，不会因为外壳宽松就放坏数据进来。 */
function parseLooseJson(text){
  var raw = String(text == null ? "" : text).replace(/^\uFEFF/, "").trim();
  if(!raw) throw new Error("内容是空的");
  try { return { data: JSON.parse(raw), cleaned: false }; } catch(e){}

  // 逐个代码块试，跳过说明文字所在的块
  var re = /```[a-zA-Z0-9_+-]*[ \t]*\r?\n([\s\S]*?)```/g, m;
  while((m = re.exec(raw)) !== null){
    try { return { data: JSON.parse(m[1].trim()), cleaned: true }; } catch(e){}
  }

  // 没有围栏就从文字里抓最外层大括号/中括号，尊重字符串与转义
  var pos = [];
  for(var p = 0; p < raw.length; p++){
    var c0 = raw.charAt(p);
    if(c0 === "{" || c0 === "["){ pos.push(p); if(pos.length >= 12) break; }
  }
  for(var k = 0; k < pos.length; k++){
    var st = pos[k], op = raw.charAt(st), cl = (op === "{") ? "}" : "]";
    var depth = 0, inStr = false, esc = false;
    for(var j = st; j < raw.length; j++){
      var c = raw.charAt(j);
      if(inStr){
        if(esc) esc = false;
        else if(c === "\\") esc = true;
        else if(c === '"') inStr = false;
        continue;
      }
      if(c === '"'){ inStr = true; continue; }
      if(c === op) depth++;
      else if(c === cl){
        depth--;
        if(depth === 0){
          try { return { data: JSON.parse(raw.slice(st, j + 1)), cleaned: true }; } catch(e){}
          break;
        }
      }
    }
  }
  throw new Error("找不到合法的 JSON 对象");
}

/* ================= 题库导入 ================= */
function importBankFile(file){
  var fr = new FileReader();
  fr.onload = function(){
    var parsed;
    try { parsed = parseLooseJson(String(fr.result)); }
    catch(e){ alert("这不是有效的 JSON：" + e.message); return; }
    var raw = parsed.data;
    var bank;
    try { bank = normalizeBank(raw); }
    catch(e){ alert("题库格式不对：" + e.message + "\n\n请按「格式规范与 AI 提示词」生成。"); return; }
    if(!bank.questions.length){ alert("题库里没有题目。"); return; }

    var id = (bank.meta && bank.meta.id) || ("bank-" + Date.now());
    bank.meta = bank.meta || {};
    bank.meta.id = id;
    var exists = !!banks[id];

    var issues = validateBank(bank);
    var msg = (parsed.cleaned ? "（已自动去掉 AI 回复里的代码围栏/说明文字）\n" : "") +
              "题库：" + (bank.meta.title || "（无题名）") + "\n共 " + bank.questions.length +
              " 题，" + bank.chapters.length + " 章。\n\n";
    msg += issues.length
      ? ("发现 " + issues.length + " 处问题（仍可导入，可在「题库自检」里看）：\n" +
         issues.slice(0,8).join("\n") + (issues.length>8 ? "\n……" : "") + "\n\n")
      : "格式校验全部通过。\n\n";
    msg += exists
      ? "检测到同 ID 的题库「" + ((banks[id].meta && banks[id].meta.title) || id) + "」，导入会覆盖它的题目（做题记录按题号尽量保留）。继续？"
      : "将作为一个新题库加入列表。继续？";
    if(!confirm(msg)) return;

    banks[id] = bankToSpecJson(bank);
    saveBanks();
    renderBanks();
    alert(exists ? "已更新题库。" : "已添加题库。");

    if(curId === id){
      enterBank(id);
    }
  };
  fr.readAsText(file, "utf-8");
}

/* ================= 自检 ================= */
function selfCheck(){
  var issues = validateBank(BANK), stat = {};
  QS.forEach(function(q){ stat[q.type] = (stat[q.type]||0)+1; });
  var html = '<h3 style="margin:0 0 10px;font-size:15.5px">题库自检</h3>';
  html += '<div class="muted">' + esc((BANK.meta && BANK.meta.title) || "（无题名）") + ' ｜ ' + QS.length +
          ' 题 ｜ 单选 ' + (stat.single||0) + ' ｜ 多选 ' + (stat.multi||0) +
          ' ｜ 不定项 ' + (stat.indefinite||0) + ' ｜ 判断 ' + (stat.judge||0) +
          ' ｜ ' + BANK.chapters.length + ' 章</div>';
  html += '<div class="muted">题库 ID：' + esc((BANK.meta && BANK.meta.id) || "—") + ' ｜ 版本 ' +
          esc((BANK.meta && BANK.meta.edition) || "—") + '</div><hr class="sep">';
  if(!issues.length){
    html += '<div class="fb ok" style="margin:0"><b>全部通过</b><span class="an">答案都在选项内，题型与答案数量一致，选项字母连续。</span></div>';
  } else {
    html += '<div class="fb bad" style="margin:0 0 10px"><b>发现 ' + issues.length + ' 处问题</b></div>';
    html += '<div class="muted" style="max-height:44vh;overflow:auto">' +
            issues.map(function(x){ return "· " + esc(x); }).join("<br>") + '</div>';
  }
  $("#checkBody").innerHTML = html;
  show("vCheck");
}

/* ================= 设置面板 ================= */
function syncSettings(){
  var a = $("#chkAutoNext"); if(a) a.checked = !!SET.autoNext;
  var b = $("#chkSound"); if(b) b.checked = !!SET.sound;
  var c = $("#shAutoNext"); if(c) c.checked = !!SET.autoNext;
  var d = $("#shSound"); if(d) d.checked = !!SET.sound;
}

function openSettings(){
  var mask = document.createElement("div");
  mask.className = "sheet";
  mask.innerHTML = '<div class="inner"><h3>设置</h3>' +
    '<div class="setrow"><div class="sr-t"><b>答对自动下一题</b>' +
      '<span>答对后约 0.9 秒自动翻页；答错不跳，方便看解析</span></div>' +
      '<label class="sw"><input type="checkbox" id="shAutoNext"' + (SET.autoNext ? ' checked' : '') + '><i></i></label></div>' +
    '<div class="setrow"><div class="sr-t"><b>音效</b><span>答对、答错、收藏时的轻提示音</span></div>' +
      '<label class="sw"><input type="checkbox" id="shSound"' + (SET.sound ? ' checked' : '') + '><i></i></label></div>' +
    '<div class="setrow" style="flex-wrap:wrap">' +
      '<div class="sr-t" style="flex-basis:100%"><b>自动翻页间隔</b>' +
      '<span>答对后等多久翻页，当前 <b id="shDelayVal">' + SET.delay + '</b> 毫秒</span></div>' +
      '<input type="range" id="shDelay" class="rng" min="200" max="2000" step="100" value="' + SET.delay + '">' +
    '</div>' +
    '<div style="margin-top:14px"><button class="btn block ghost" id="shClose">关闭</button></div></div>';
  document.body.appendChild(mask);

  var ca = mask.querySelector("#shAutoNext");
  ca.addEventListener("change", function(){
    SET.autoNext = !!ca.checked;
    saveSettings(); syncSettings();
  });
  var sd = mask.querySelector("#shDelay");
  var sdv = mask.querySelector("#shDelayVal");
  sd.addEventListener("input", function(){
    var v = parseInt(sd.value, 10);
    SET.delay = v;
    if(sdv) sdv.textContent = v;
  });
  sd.addEventListener("change", function(){
    saveSettings();
    sndTap();
  });

  var cs = mask.querySelector("#shSound");
  cs.addEventListener("change", function(){
    SET.sound = !!cs.checked;
    saveSettings(); syncSettings();
    if(SET.sound) sndCorrect();
  });
  mask.addEventListener("click", function(e){
    if(e.target === mask || e.target.id === "shClose") mask.remove();
  });
}

/* ================= 导入方式 ================= */
function askImportMode(){
  var mask = document.createElement("div");
  mask.className = "sheet";
  mask.innerHTML = '<div class="inner"><h3>导入记录（当前题库）</h3><div class="pick">' +
    '<button data-m="merge">合并（推荐）<br><span class="muted" style="font-size:12px">同题以更新的一份为准；两边作答明细全部并进来，错选统计相加</span></button>' +
    '<button data-m="over">覆盖<br><span class="muted" style="font-size:12px">清空当前题库的记录，完全按这个文件来</span></button>' +
    '</div><div style="margin-top:12px"><button class="btn block ghost" data-m="cancel">取消</button></div></div>';
  mask.addEventListener("click", function(e){
    if(e.target===mask){ mask.remove(); return; }
    var b = e.target.closest("[data-m]");
    if(!b) return;
    var m = b.getAttribute("data-m");
    mask.remove();
    if(m==="cancel") return;
    importMode = m;
    $("#fileRec").click();
  });
  document.body.appendChild(mask);
}

/* ================= 规范 ================= */
function specText(){
  var el = $("#specDoc");
  return (el && el.textContent) ? el.textContent : "";
}

function showSpec(){
  var t = specText();
  var mask = document.createElement("div");
  mask.className = "sheet";
  mask.innerHTML = '<div class="inner"><h3>题库格式规范与 AI 提示词</h3>' +
    '<div class="muted" style="max-height:56vh;overflow:auto;white-space:pre-wrap;font-size:12.5px;line-height:1.75">' +
    esc(t) + '</div>' +
    '<div class="row" style="margin-top:14px">' +
    '<button class="btn ghost" style="flex:1" id="spClose">关闭</button>' +
    '<button class="btn primary" style="flex:1" id="spCopy">复制全文</button></div></div>';
  mask.addEventListener("click", function(e){
    if(e.target===mask || e.target.id==="spClose") mask.remove();
    if(e.target.id==="spCopy"){ copySpec(); }
  });
  document.body.appendChild(mask);
}

function copyToClipboard(t){
  var done = false;
  try { if(navigator.clipboard && navigator.clipboard.writeText){ navigator.clipboard.writeText(t); done = true; } } catch(e){}
  if(!done){
    try {
      var ta = document.createElement("textarea");
      ta.value = t; ta.style.position="fixed"; ta.style.top="-9999px";
      document.body.appendChild(ta); ta.focus(); ta.select();
      ta.setSelectionRange(0, t.length);
      done = document.execCommand("copy");
      ta.remove();
    } catch(e){ done = false; }
  }
  return done;
}

function promptText(){
  var t = specText();
  var m = t.match(/# 第三部分[\s\S]*?(?=\n# 第四部分)/);
  if(!m) return t;
  var f = m[0].match(/````\r?\n([\s\S]*?)\r?\n````/);
  return (f ? f[1] : m[0]).trim();
}

function copySpec(){
  var t = specText();
  if(!t.trim()){ alert("规范内容缺失。"); return; }
  var done = copyToClipboard(t);
  alert(done ? "已复制整套规范与提示词，直接粘给任意 AI 即可。" : "复制失败，请用「导出规范」把文件发给 AI。");
}

function copyPrompt(){
  var t = promptText();
  if(!t.trim()){ alert("提示词内容缺失。"); return; }
  var done = copyToClipboard(t);
  alert(done ? "已复制转换提示词。把源文件和它一起发给 AI；回复存成 .qbank.json 就能直接导入。"
             : "复制失败，请用「导出规范」把文件发给 AI。");
}

function exportSpec(){
  var t = specText();
  if(!t.trim()){ alert("规范内容缺失。"); return; }
  download("题库格式规范与AI提示词.md", t, "text/markdown");
}

/* ================= 事件 ================= */
function bind(){
  $("#btnHome").addEventListener("click", goBack);

  $("#btnContinue").addEventListener("click", function(){
    var next = QS.filter(function(q){ var r = state.q[q.id]; return !r || !r.attempts; });
    startQuiz(next.length ? next : QS, "seq", "继续练习");
  });
  $("#btnRandom").addEventListener("click", function(){
    var pool = QS.slice();
    for(var i=pool.length-1;i>0;i--){ var j=Math.floor(Math.random()*(i+1)); var t=pool[i]; pool[i]=pool[j]; pool[j]=t; }
    startQuiz(pool.slice(0, Math.min(20, pool.length)), "rand", "随机练习");
  });
  $("#goWrong").addEventListener("click", function(){
    var s = stats();
    if(!s.everIds.length){ alert("记录里还没有做错过任何题。"); return; }
    startQuiz(buildWrongList(s.everIds), "wrong", "错题重练（按错误率排序）");
  });
  $("#goHeavy").addEventListener("click", function(){
    var s = stats();
    if(!s.heavyIds.length){ alert("还没有错过 2 次以上的题。"); return; }
    startQuiz(buildWrongList(s.heavyIds), "heavy", "顽固错题");
  });
  $("#goFlag").addEventListener("click", function(){
    var s = stats();
    if(!s.flagIds.length){ alert("还没有标记的题。在答题页点「标记为有疑问」。"); return; }
    startQuiz(s.flagIds.map(function(id){ return BYID[id]; }), "flag", "标记 / 有疑问");
  });

  $("#btnSettings").addEventListener("click", openSettings);
  $("#btnOverview").addEventListener("click", function(){
    renderOverview();
    show("vOverview");
    $("#hdTitle").textContent = "题目总览";
  });
  var tipX = $("#resumeTipClose");
  if(tipX) tipX.addEventListener("click", function(){ $("#resumeTip").style.display = "none"; });

  $("#btnPrev").addEventListener("click", function(){ go(-1); });
  $("#btnNext").addEventListener("click", function(){ go(1); });
  $("#btnSheet").addEventListener("click", openSheet);
  $("#btnSubmit").addEventListener("click", function(){ flushNote(); grade(cur.list[cur.i]); });
  $("#btnRedo").addEventListener("click", function(){
    var q = cur.list[cur.i];
    setRec(q.id, { lastPicked:[], lastCorrect:null });
    renderQ();
  });
  $("#btnFlag").addEventListener("click", function(){
    var q = cur.list[cur.i], r = getRec(q.id) || blankRec();
    setRec(q.id, { flag: r.flag ? 0 : 1 });
    renderQ();
  });
  $("#btnStar").addEventListener("click", function(){
    var q = cur.list[cur.i], r = getRec(q.id) || blankRec();
    var on = !r.star;
    setRec(q.id, { star: on ? 1 : 0 });
    if(on) sndStar(); else sndTap();
    renderQ();
    var b = $("#btnStar");
    if(b){ b.classList.remove("pop"); void b.offsetWidth; b.classList.add("pop"); }
  });
  var chkAuto = $("#chkAutoNext");
  if(chkAuto){
    chkAuto.addEventListener("change", function(){
      SET.autoNext = !!chkAuto.checked;
      saveSettings();
      if(SET.autoNext){ sndTap(); }
    });
  }
  var chkSound = $("#chkSound");
  if(chkSound){
    chkSound.addEventListener("change", function(){
      SET.sound = !!chkSound.checked;
      saveSettings();
      if(SET.sound) sndCorrect();
    });
  }
  $("#goStar").addEventListener("click", function(){
    var s = stats();
    if(!s.starIds.length){ alert("还没有收藏的题。在答题页点「☆ 收藏」。"); return; }
    startQuiz(s.starIds.map(function(id){ return BYID[id]; }), "star", "我的收藏");
  });
  $("#qNote").addEventListener("input", onNoteInput);
  $("#qNote").addEventListener("blur", function(){ flushNote(); $("#noteSaved").textContent = "已保存"; });

  $("#btnExpRec").addEventListener("click", exportRec);
  $("#btnExpHtml").addEventListener("click", exportHtml);
  $("#btnExpMd").addEventListener("click", exportMd);
  $("#btnExpAi").addEventListener("click", exportAiPack);
  $("#btnImpAi").addEventListener("click", function(){ $("#fileAi").click(); });
  $("#fileAi").addEventListener("change", function(e){
    var f = e.target.files && e.target.files[0];
    if(f) importAi(f);
    e.target.value = "";
  });
  $("#btnImpRec").addEventListener("click", askImportMode);
  $("#fileRec").addEventListener("change", function(e){
    var f = e.target.files && e.target.files[0];
    if(f) importRec(f, importMode);
    e.target.value = "";
  });

  $("#btnImpBank").addEventListener("click", function(){ $("#fileBank").click(); });
  $("#fileBank").addEventListener("change", function(e){
    var f = e.target.files && e.target.files[0];
    if(f) importBankFile(f);
    e.target.value = "";
  });

  $("#btnBankSpec").addEventListener("click", showSpec);
  $("#btnExpSpec").addEventListener("click", exportSpec);
  $("#btnCopyPrompt").addEventListener("click", copyPrompt);
  $("#btnSpecTop").addEventListener("click", showSpec);
  var top2 = $("#btnSpecTop2"); if(top2) top2.addEventListener("click", showSpec);

  $("#btnCheck").addEventListener("click", selfCheck);
  $("#btnReset").addEventListener("click", function(){
    if(!confirm("清空当前题库的所有记录和笔记？\n（建议先导出备份）")) return;
    if(!confirm("再确认一次：清空后无法撤销。")) return;
    state.q = {};
    persistRec();
    alert("已清空。");
  });

  window.addEventListener("beforeunload", function(){ flushNote(); });
  document.addEventListener("visibilitychange", function(){ if(document.hidden) flushNote(); });
  document.addEventListener("keydown", function(e){
    if(view !== "vQuiz") return;
    if(e.target && e.target.tagName === "TEXTAREA") return;
    if(e.key === "ArrowLeft") go(-1);
    if(e.key === "ArrowRight") go(1);
    if(e.key.length === 1 && "ABCDEFGHabcdefgh".indexOf(e.key) >= 0) pickOpt(e.key.toUpperCase());
  });
}

function storageOk(){
  try {
    localStorage.setItem("__probe__", "1");
    localStorage.removeItem("__probe__");
    return true;
  } catch(e){ return false; }
}

function boot(){
  loadAll();
  loadSettings();
  bind();
  renderBanks();

  var lastBank = lsGet(K_CUR);
  if(lastBank && banks[lastBank]){
    enterBank(lastBank, { resume:true });   // 打开就回到上次那一题
  } else {
    show("vBanks");
  }
  if(!storageOk()){
    alert("提示：本机存储不可用（可能开了无痕/隐私模式），做题记录不会被保存。\n建议做完及时用「导出记录」备份。");
  }
  if("serviceWorker" in navigator && location.protocol.indexOf("http") === 0){
    navigator.serviceWorker.register("sw.js").catch(function(){});
  }
}
if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
})();
