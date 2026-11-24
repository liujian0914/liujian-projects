# 题库格式规范 v1.0（严格版）· 兼 AI 转换提示词

本文同时是**格式规范**和**可直接发给 AI 的提示词**。软件里内嵌的也是这一份，只有这一个来源。

- 校验哲学：**要么完全合格，要么一点不改**。记录文件只要有一处不合格，程序整体拒绝，不会写进半个字段。
- 所有文件必须 UTF-8、无 BOM、无注释、无尾逗号，字符串里的换行用 `\n`。
- 扩展名建议：题库 `.qbank.json`，记录 `.qrec.json`。

---

# 第一部分　题库文件（.qbank.json）

## 1.1 顶层结构（4 个必填键，缺一不可）

```json
{ "format": "qbank", "version": "1.0", "meta": {}, "chapters": [], "questions": [] }
```

| 键 | 类型 | 必填 | 取值 | 说明 |
|---|---|---|---|---|
| format | string | 是 | 必须是 `"qbank"` | 写成别的，程序直接拒收 |
| version | string | 是 | 必须是 `"1.0"` | |
| meta | object | 是 | 见 1.2 | |
| chapters | array | 是 | 见 1.3，可以是 `[]` | |
| questions | array | 是 | 见 1.4，至少 1 条 | |

多余字段会被忽略，发现即丢弃，不影响导入。

## 1.2 meta

```json
{
  "id": "maogai-2026-10",
  "title": "毛泽东思想和中国特色社会主义理论体系概论 题库",
  "subject": "毛泽东思想和中国特色社会主义理论体系概论",
  "source": "概论课题库（2026.10修订）.docx",
  "edition": "2026.10 修订",
  "createdAt": "2026-11-24T20:00:00+08:00",
  "questionCount": 410,
  "description": "可选说明"
}
```

| 键 | 类型 | 必填 | 约束 |
|---|---|---|---|
| id | string | **是** | 正则 `^[a-z0-9][a-z0-9-]*$`，即小写字母数字与短横线。**这是记录的归属依据，同一套题库永远不要改它** |
| title | string | **是** | 非空 |
| subject / source / edition / description | string | 否 | |
| createdAt | string | 否 | ISO 8601 |
| questionCount | integer | 否 | 与 questions 实际条数不符会被提示，以实际为准 |

## 1.3 chapters

```json
[ { "id": "ch1", "name": "第一章 毛泽东思想及其历史地位", "order": 1 } ]
```

| 键 | 类型 | 必填 | 约束 |
|---|---|---|---|
| id | string | 是 | 题库内唯一；题目用 `chapter` 引用它 |
| name | string | 是 | 非空 |
| order | integer | 否 | 缺省按数组顺序 |

- 不分章的题库：`chapters` 写 `[]`，题目的 `chapter` 写 `null` 或省略，程序归到「未分章」。
- **只支持一层章节**。原文的「第一节」并进章节名，不要建二级。

## 1.4 questions

```json
{
  "id": "ch2-multi-7",
  "type": "multi",
  "chapter": "ch2",
  "number": 7,
  "stem": "新民主主义政治纲领规定的新民主主义国家（　）",
  "options": [
    { "key": "A", "text": "国体是各革命阶级的联合专政" },
    { "key": "B", "text": "政体是民主集中制的人民代表大会制度" },
    { "key": "C", "text": "各革命阶级的联合专政就是工农民主专政" },
    { "key": "D", "text": "人民当家作主是国家制度的核心内容和基本准则" }
  ],
  "answer": ["A", "B", "D"],
  "analysis": "国体与政体是两个层面，C 项混淆了联合专政与工农民主专政。",
  "tags": ["政治纲领", "易错"],
  "difficulty": 2
}
```

| 键 | 类型 | 必填 | 约束 |
|---|---|---|---|
| id | string | **是** | **全库唯一**。建议 `章节-题型-题号`，如 `ch2-multi-7`。**记录靠它对应，改了 id 等于换了一道题，旧记录会对不上** |
| type | string | **是** | 只能是 `single` / `multi` / `judge` / `indefinite` |
| stem | string | **是** | 非空。**不要带「1.」「2、」这类题号**，题号放 number |
| options | array | **是** | 2–8 条，每条 `{key,text}`；key 必须从 A 开始**连续不跳号** |
| answer | array | **是** | 正确字母数组。`single`/`judge` 恰好 1 个；`multi` ≥2；`indefinite` ≥1 |
| chapter | string\|null | 否 | 必须是某个 chapters[].id，或 null |
| number | integer | 否 | 该章该题型的题号，用于显示与排序 |
| analysis | string | 否 | 解析，没有就 `""` |
| tags | string[] | 否 | |
| difficulty | integer | 否 | 1–5 |

### 四种题型的判定规则

| type | 中文 | answer 个数 | 判分方式 |
|---|---|---|---|
| single | 单选题 | 恰好 1 | 点一下即判 |
| multi | 多选题 | ≥ 2 | 勾选后提交，少选/多选/错选都算错 |
| indefinite | 不定项 | ≥ 1 | 同上，但答案可能只有 1 个 |
| judge | 判断题 | 恰好 1 | 选项固定 A=正确、B=错误 |

原文写「不定项」「答案可能一个或多个」→ 用 `indefinite`；只写「多选」→ 一律用 `multi`，不要擅自改。

## 1.5 导入时会执行的校验（不合格的会在提示里逐条列出）

1. `format` 必须是 `qbank`
2. `meta.id`、`meta.title` 非空
3. 题目 `id` 全库唯一
4. `stem` 非空
5. `options` 的 key 从 A 起连续（A、B、C…），无跳号无重复
6. 每个 `answer` 字母都在该题 `options` 里
7. `single`/`judge` 答案恰好 1 个；`multi` ≥2；`indefinite` ≥1
8. `chapter` 非空时必须在 chapters 里存在
9. 选项文本不能为空

校验不通过时：**题库仍可导入，但问题会列出来**，导入后也能随时点「题库自检」复查。题库文件是「只读输入」，坏数据不会污染做题记录。

导入口会自动剥掉 AI 回复里常见的 ` ```json ` 围栏和前后说明文字，只处理外壳，不放宽上面 9 条校验。所以即使 AI 没遵守「裸 JSON」约定，回复照样能存成文件直接导入。

---

# 第二部分　做题记录文件（.qrec.json）

## 2.1 顶层结构

```json
{
  "format": "qbank-record",
  "version": "1.0",
  "bankId": "maogai-2026-10",
  "bankTitle": "毛泽东思想和中国特色社会主义理论体系概论 题库",
  "exportedAt": "2026-11-24T21:30:00+08:00",
  "summary": {},
  "records": { }
}
```

| 键 | 类型 | 必填 | 约束 |
|---|---|---|---|
| format | string | **是** | 必须是 `"qbank-record"` |
| version | string | **是** | 必须是 `"1.0"` |
| bankId | string | **是** | **必须与当前题库的 meta.id 完全一致**，否则整份拒绝 |
| bankTitle | string | 否 | 只作说明 |
| exportedAt | string | 否 | ISO 8601 |
| summary | object | 否 | 程序会重算，写错不影响 |
| records | object | **是** | 键＝题目 id，值＝单题记录，不能是数组 |

## 2.2 单题记录

```json
"ch2-multi-7": {
  "attempts": 4,
  "correct": 2,
  "wrong": 2,
  "accuracy": 0.5,
  "wrongOptions": { "C": 2, "D": 1 },
  "lastPicked": ["A", "B"],
  "lastCorrect": false,
  "history": [
    { "at": "2026-11-24T20:41:00+08:00", "picked": ["A","B"], "correct": false, "answer": "ABD" }
  ],
  "note": "C 项混淆了联合专政和工农民主专政。",
  "flagged": true,
  "starred": true,
  "aiAnalysis": "考点：国体与政体……",
  "updatedAt": "2026-11-24T20:44:00+08:00"
}
```

| 键 | 类型 | 约束 |
|---|---|---|
| attempts | integer | ≥0，且必须 ≥ `history.length` |
| correct | integer | 0 ≤ correct ≤ attempts |
| wrong | integer | 程序按 attempts − correct 重算，填错会被纠正 |
| accuracy | number | 0–1，程序重算 |
| wrongOptions | object | 键只能是 A–H，值必须是正整数；表示**选错的选项**被误选的次数 |
| lastPicked | string[] | 选项字母 |
| lastCorrect | boolean \| null | 最近一次对错，没做过为 null |
| history | array | **最多 50 条**，按时间升序 |
| history[].at | string | ISO 8601 |
| history[].picked | string[] | 本次所选 |
| history[].correct | boolean | 本次对错 |
| history[].answer | string | 本次作答时的正确答案，如 `"ABD"` |
| note | string | 笔记，允许 `\n` |
| flagged | boolean | 是否「标记为有疑问」 |
| starred | boolean | 是否「收藏」 |
| aiAnalysis | string | AI 分析 |
| updatedAt | string | ISO 8601，合并时判断谁更新 |

## 2.3 导入记录的严格规则（不满足就整份拒收）

1. `format` = `qbank-record`
2. `version` = `1.0`
3. `bankId` 必须等于当前题库的 `meta.id`
4. `records` 必须是对象，且非空
5. **每个题号都必须在当前题库里存在**
6. 字段类型必须正确：attempts/correct 为非负整数、history 为数组且 ≤50、wrongOptions 为对象、flagged/starred 为布尔、note 为字符串
7. 只要有一条不合格，**整份不导入，本机数据一个字都不改**

程序在写入前还会做一次归一化：`attempts` 取「原值」与「明细条数」的较大者，`correct` 不超过 `attempts`，`wrong` 重算，`wrongOptions` 只保留合法项。所以落盘数据永远是自洽的。

记录导入同样会自动剥掉代码围栏/说明文字；这只是外壳容错，上面 7 条数据校验一条都不放宽。

## 2.4 合并规则

- 同一题以 `updatedAt` 较新的一份为准；
- `history` 两边按「时间 + 所选 + 对错」去重合并，最多 50 条，不丢任何一次；
- `wrongOptions` 按选项求和；
- 对方 `note` / `aiAnalysis` 为空时，不覆盖本机非空内容；
- 记录按题库（`bankId`）分别存放，切换题库不会串。

## 2.5 常见拒绝原因对照

| 提示 | 原因 | 怎么修 |
|---|---|---|
| format 必须是 qbank-record | 把题库文件当记录导入，或字段写错 | 记录文件顶层写 `"format":"qbank-record"` |
| bankId 不匹配 | 文件属于另一套题库 | 进对应题库再导入；或重新导出 |
| 有 N 个题号在当前题库里找不到 | 题库改过 id，或文件来自别的题库 | 保持 id 稳定；必要时重新生成记录 |
| correct 超过 attempts | 手工改数据 | 让 correct ≤ attempts |
| history 超过 50 条上限 | 拼接过多 | 截到最近 50 条 |

---

# 第三部分　发给 AI 的转换提示词（整段复制）

软件首页的「复制提示词」按钮复制的就是下面这一段，不用复制整份规范。把提示词和源文件一起发给任意 AI，**AI 的回复存成 `.qbank.json` 就能直接导入软件，中间不需要删围栏、不需要删解释**；就算 AI 自作主张加了围栏或说明，导入口也会自动剥掉。

````
你是「题库格式转换器」。我会在下一轮给你源文件（docx / pdf / txt / 表格 / 截图均可）。
把里面的选择题逐题转换成下面这套 JSON。不许编题、不许漏题、不许改答案。

【输出契约 —— 最高优先级，违反任何一条都算失败】
1. 你的回复只能是一个「裸 JSON 对象」。
2. 绝对不要写 ```json 或 ``` 代码块标记，绝对不要写任何解释、标题、前后缀、总结、报告。
3. 回复的第一个字符必须是 {，最后一个字符必须是 }。中间不能有任何 JSON 以外的字符。
4. JSON 必须能被标准 JSON.parse 一次解析成功；字段名必须用英文半角双引号，字符串内容里可以用中文标点。
5. 不要用中文引号当语法符号，不要尾逗号，不要注释，字符串里的换行写成 \n。
6. 这份 JSON 会直接被题库系统导入，所以格式必须一次正确。
7. 你想说明题数或自检结果也不要写在 JSON 外面；确实需要就写进 meta.description。

【唯一合法的顶层格式】
{"format":"qbank","version":"1.0","meta":{...},"chapters":[...],"questions":[...]}

meta 必填两项，其余可选：
  id    正则 ^[a-z0-9][a-z0-9-]*$，例如 "maogai-2026-10"。同一份资料重复转换必须保持一致。
        这是记录归属依据，改了 id 旧记录就对不上。
  title 原文里的科目名 / 书名，非空。
  可选：subject、source、edition、createdAt、questionCount、description。

chapters：原文分章就写 [{"id":"ch1","name":"第一章 ……","order":1}, ...]；
         原文不分章就写 []，题目的 chapter 写 null。
         只支持一层章节，原文的「第一节」并进章节名，不要建二级。

questions 每题字段：
  id       必填，全库唯一，格式「章节-题型-题号」，例如 "ch2-multi-7"；
           不分章用 "q-single-1"。同一份资料重复转换，id 必须完全一样。
  type     必填，只能是 single（单选）/ multi（多选）/ judge（判断）/ indefinite（不定项）。
           原文写「不定项」「答案可能一个或多个」→ indefinite；
           只写「多选」→ multi，不要擅自改。
  stem     必填，题干文字，不要带「1.」「2、」题号前缀。
  options  必填，[{"key":"A","text":"……"}]，2–8 个，key 从 A 起连续不跳号。
           原文里「A.xxx  B.yyy」挤在一行的，要拆成两个 option 对象。
  answer   必填，正确字母数组：single/judge 恰好 1 个；multi ≥2；indefinite ≥1。
  chapter  可选，必须是某个 chapters[].id，或 null。
  number   可选，该章该题型的题号。
  analysis 可选，没有就写空字符串 ""。
  tags     可选，字符串数组。
  difficulty 可选，1–5 的整数。

判断题统一成两个选项：A=正确、B=错误。
原文答案集中在卷末（如「参考答案 1.A 2.B …」）的，必须按题号逐条对应回每题，不要按行拆错。
原文确实没有答案的题：answer 写 []，并在 tags 里加 "缺答案"，绝对不要自己猜一个答案填进去。
不要编造解析，原文没有就写 ""。

【一个最小合法样例，照着这个形状输出】
{"format":"qbank","version":"1.0","meta":{"id":"demo-2026","title":"示例题库"},"chapters":[{"id":"ch1","name":"第一章","order":1}],"questions":[{"id":"ch1-single-1","type":"single","chapter":"ch1","number":1,"stem":"题干","options":[{"key":"A","text":"甲"},{"key":"B","text":"乙"}],"answer":["B"],"analysis":""}]}

【转换流程】
1. 通读源文件：判断有没有章节、有哪几种题型、答案在题干后还是卷末。
2. 统计题数：每章每种题型各多少题，心里有数。
3. 逐题转换：按原文顺序，题号连续。
4. 对答案：卷末答案按题号对回去，对不上的标「缺答案」。
5. 自检三轮（见下），有问题就改，改完重新自检，直到全过。

【三轮自检 —— 每轮都必须真的检查】
第一轮　结构：format/version 一字不差；meta.id 与 meta.title 非空；题目 id 全库无重复。
第二轮　逐题：stem 非空；options 的 key 从 A 起连续；answer 每个字母都在 options 里；
　　　　single/judge 恰好 1 个答案，multi ≥2，indefinite ≥1；chapter 要么 null 要么在 chapters 里。
第三轮　对账：题目总数 = 原文总数（逐章逐题型核对）；随机抽 10 题逐字对照题干、选项、答案；
　　　　没有并题、拆题、漏题、多题。

【输出前最后一步】
把你要输出的内容按「输出契约 1–7 条 + 三轮自检」过一遍。
只要有一条不满足，就重做那部分，不要带着问题输出。
然后只输出裸 JSON，一个字的多余内容都不要。
````

如果你只是想让 AI 顺带报个题数统计，另外单独问它一句，不要在转换提示词里加「报告」要求 —— 那会污染输出，导致存成文件后导不进去。

---

# 第四部分　本地自检工具

```bash
python tools/validate.py 题库.json            # 校验题库文件
python tools/validate.py 记录.qrec.json --record --bank 题库.json   # 校验记录文件并核对题号
```

返回码 0 表示合格，1 表示有问题。AI 给出的 JSON 先过一遍这个脚本，再导入软件最稳。

脚本和软件一样会剥掉代码围栏/说明文字，所以 AI 回复可以直接存盘再校验。

---

# 第五部分　速查清单

- [ ] 顶层四个键齐全，`format`/`version` 一字不差
- [ ] `meta.id` 稳定不变、`meta.title` 非空
- [ ] 每题 `id` 唯一且可复现
- [ ] 选项字母从 A 连续
- [ ] 答案字母都在选项内，题型与答案个数匹配
- [ ] 题数与原文一致，无并题拆题
- [ ] 记录文件 `bankId` 与目标题库一致
- [ ] 记录里每个题号都存在于该题库
