/* 给「Deep-learning-enabled brain hemodynamic mapping using resting-state fMRI」
   （npj Digital Medicine 2023;6:116）建 L2 阅读卡并导入 Folio。

   为什么用脚本而不是直接调 folio_import_cards：
     quote 必须**逐字**存在于 Folio 正文才能锚定。手工敲 quote 极易差一个字符
     （弯引号、连字符、上下标），所以这里用「起始片段 → 句末」的定位方式从
     入库后的正文里**程序化截取**，从根本上消除抄写风险。

   跑法：node tools/_cards_pdf.js <paperId> [--dry]
*/
"use strict";
const BASE = "http://127.0.0.1:8787";
const PAPER = process.argv[2];
const DRY = process.argv.includes("--dry");
if (!PAPER) { console.error("用法: node tools/_cards_pdf.js <paperId> [--dry]"); process.exit(1); }

const SRC = "npj Digital Medicine 2023;6:116 · DOI 10.1038/s41746-023-00859-y";

async function call(name, args) {
  const r = await fetch(BASE + "/api/call", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, args }),
  });
  const j = await r.json();
  if (!j.result) throw new Error(JSON.stringify(j).slice(0, 300));
  if (j.result.isError) throw new Error(j.result.content[0].text);
  return JSON.parse(j.result.content[0].text);
}

async function getParas(paperId) {
  const out = [];
  for (let off = 0; ; off += 100) {
    const r = await call("folio_get_text", { paperId, offset: off, limit: 100 });
    (r.paragraphs || []).forEach((p) => out.push(p));
    if (out.length >= (r.total || 0) || !(r.paragraphs || []).length) break;
  }
  return out;
}

/* ---------------- 卡片定义 ----------------
   find：句中一段**唯一的起始片段**（用来定位）
   end ：可选，跨句引用的结束片段；不给则截到第一个句末 ". " */
const DEFS = [
  /* KC 核心概念 */
  { t: "KC", find: "Cerebrovascular reactivity (CVR) and bolus arrival time (BAT), which denote",
    n: "CVR = 脑血管的扩张能力；BAT = 血流动力学延迟。两者是脑血管功能的两大标志物，在脑血管病中已有明确效用。" },
  { t: "KC", find: "This presents an opportunity to use resting-state CO2 change as an intrinsic marker",
    n: "静息态下动脉 CO2 随逐次呼吸自然波动，因此可把 rs-fMRI 的 CO2 波动当作「内在对比剂」来估计 CVR/BAT，无需外源给气。（注：该处 PDF 文本层把 `concentration` 与 `fluctuates` 之间的空格丢了，正文里是 `concentrationfluctuates`）" },

  /* KT 知识主题 */
  { t: "KT", find: "Currently, CVR and BAT mappings are carried out using the administration of CO2 enriched gas",
    n: "现状：CVR/BAT 测量依赖外源 CO2 吸入、血管活性药物或对比剂 → 额外操作与设备。这正是本工作想绕开的负担。" },
  { t: "KT", find: "these techniques generally suffers from low signal-to-noise ratio",
    n: "既往 rs-fMRI 类方法的通病：信噪比低、图像质量在患者间波动大；根因是静息态 CO2 自然变异幅度有限。（原文语法如此：suffers）" },

  /* KM 方法要点 */
  { t: "KM", find: "Participants were recruited from two sites:",
    n: "两中心招募：UTSW（Dallas）与 JHU（Baltimore）。跨中心利于外部效度；但训练/验证数据的中心分布未见分层报告。" },
  { t: "KM", find: "In a subset of 8 participants, the resting-state scan was performed at 3 spatial resolutions",
    n: "空间分辨率依赖性测试：8 例在 3 种分辨率（2×2×2 / 2.4×2.4×2.4 / 3×3×3 mm）各扫一次。样本很小，结论只能算提示性。" },
  { t: "KM", find: "we used Statistical Parametric Mapping (SPM12",
    n: "预处理链：SPM12 + 全局回归（GRRS）。GRRS 图既作 DL 输入，也作对比基线。" },
  { t: "KM", find: "For GRRS BAT map, the BOLD time course of each voxel within the brain was extracted and then shifted",
    n: "GRRS BAT：逐体素 BOLD 时间序列在 ±9 s 内以 0.1 s 步长平移，与参考信号做 GLM 取最优延迟；±9 s 取自既往文献。" },
  { t: "KM", find: "the residual BOLD signal after global regression was parcellated into 133 regions-of-interest",
    n: "补充编码器的输入：全局回归后的残差 BOLD 按 Neuromorphometrics 图谱分成 133 个 ROI —— 这是「补充信息」的来源。" },
  { t: "KM", find: "The deep-learning network was trained using GRRS CVR β, GRRS CVR β, GRRS BAT, and cross-correlation maps as input images",
    n: "训练设置：输入 = GRRS 图 + 互相关图；**标签 = 高碳酸血症（HC）CVR/BAT**。即用金标准方法的结果，教网络从静息态反推。" },
  { t: "KM", find: "We conducted an ablation study to demonstrate the efficacy of the proposed network architecture",
    n: "消融实验：验证主编码器与补充编码器各自必要 —— 这是「架构不是为了堆料」的证据。" },
  { t: "KM", find: "The HC BAT was quantified as the time delay between the synchronized",
    n: "HC BAT 定义：同步的 EtCO2 时间曲线与体素 BOLD 曲线之间的时间延迟。" },

  /* KR 关键结果 */
  { t: "KR", find: "In summary, our study shows that cerebrovascular reactivity (CVR) and bolus arrival time (BAT) mappings using deep-learning model from resting-state functional MRI provide a task-free approach",
    n: "全文主结论：rs-fMRI + 深度学习可实现**免任务**的 CVR/BAT 成像。" },
  { t: "KR", find: "We found that there was not a significant difference in CVR or BAT between HC and DLRS method",
    n: "DLRS 与金标准 HC 无显著差异 —— 「可替代」的核心论据。⚠️ 但「无显著差异」不等于等效：本文未预设非劣界值，属阴性检验而非等效检验。" },
  { t: "KR", find: "We found that most regional CVR from our model tended to decrease while regional BAT increased with age",
    n: "增龄效应：区域 CVR 随年龄下降、BAT 延长。" },
  { t: "KR", find: "In Moyamoya patients, the DLRS CVR/BAT metrics in those who underwent revascularization surgery were significantly improved",
    n: "烟雾病中，行血运重建者的 DLRS 指标显著优于未手术者 —— 提示可用于疗效评估。⚠️ 但属横断比较而非同一患者的前后随访，存在选择偏倚。" },
  { t: "KR", find: "The sensitivity of DLRS CVR and DLRS BAT images to brain pathologies was examined in three patient cohorts",
    n: "疾病敏感性在三类队列检验：烟雾病、卒中、脑肿瘤。" },

  /* KV 证据数据 */
  { t: "KV", find: "The ICCs of our DLRS CVR and DLRS BAT were 0.874",
    n: "重测信度：DLRS CVR ICC 0.874（95% CI 0.867–0.881）、BAT 0.857（0.848–0.865）。⚠️ 这是测试-重测的组内相关，不等于个体水平的临床可重复性。" },
  { t: "KV", find: "The Dice coefficients between DLRS CVR and HC CVR were 0.78",
    n: "与金标准 HC 的空间重叠：DLRS CVR Dice = 0.78，而传统全局回归法仅 0.08 —— 数量级差距是本文最有力的单项证据。" },
  { t: "KV", find: "using a bootstrap method (N = 10,000)",
    n: "统计细节：用 bootstrap（N = 10,000）估计 R 值方差。属可复现性信息。" },

  /* NT 批注 / 局限 */
  { t: "NT", find: "the performance of the DLRS method in patients, in particular in Moyamoya disease, was not as good as that in healthy controls",
    n: "⚠️ 关键不对称：模型在患者中（尤其烟雾病）表现不如健康对照。作者归因于病理血管的复杂改变。这对「能否泛化到重症患者」是直接警示。" },
  { t: "NT", find: "the CVR and BAT obtained from our deep-learning model were in relative units",
    n: "⚠️ 局限①：输出是**相对单位**而非绝对生理量 → 不能跨受试者/跨中心直接比大小，也无法设定通用阈值。" },
  { t: "NT", find: "the current deep-learning results pre-sented in stroke patients have not been validated with the ground-truth hypercapnic method",
    n: "⚠️ 局限②：卒中患者的结果**未与金标准 HC 方法验证**（实际操作困难）。即卒中这条线缺独立验证。（原文含断词 pre-sented）" },

  /* KS 可证伪问题 */
  { t: "KS", find: "We also provided some early evidence that the deep-learning derived hemodynamic maps may be useful in patient triaging or",
    n: "可证伪问题：在**前瞻性**队列中，用 DLRS CVR/BAT 做分诊或疗效评估，能否改变临床决策或改善结局？本文只给「早期证据」（横断、回顾），未做决策性验证 —— 一旦前瞻试验显示无增益，本命题即被否证。" },
];

/* 从正文里按 find/end 截取 quote（保证逐字） */
function pick(paras, def) {
  for (const p of paras) {
    const i = p.text.indexOf(def.find);
    if (i < 0) continue;
    let end;
    if (def.end) {
      const j = p.text.indexOf(def.end, i + def.find.length);
      if (j < 0) continue;
      end = j + def.end.length;
    } else {
      const j = p.text.indexOf(". ", i + def.find.length);
      end = j < 0 ? p.text.length : j + 1;
    }
    return { quote: p.text.slice(i, end), paraIdx: p.paraIdx };
  }
  return null;
}

(async () => {
  const paras = await getParas(PAPER);
  console.log("正文段落数：" + paras.length + "\n");

  const cards = [];
  const failed = [];
  DEFS.forEach((d, k) => {
    const hit = pick(paras, d);
    if (!hit) { failed.push("[定义" + k + "] find 未命中：" + d.find.slice(0, 60)); return; }
    cards.push({
      type: d.t,
      quote: hit.quote,
      note: d.n + "\n\n—— 来源：" + SRC,
      tags: ["PDF导入", "rs-fMRI", "CVR/BAT", "深度学习"],
      star: d.t === "NT" || d.t === "KS",
    });
  });

  const byType = {};
  cards.forEach((c) => { byType[c.type] = (byType[c.type] || 0) + 1; });
  console.log("卡片 " + cards.length + " 张 → " + JSON.stringify(byType));
  if (failed.length) { console.log("\n未能定位的卡片："); failed.forEach((f) => console.log("  ✗ " + f)); }
  console.log("\n逐卡 quote 预览（前 100 字）：");
  cards.forEach((c, i) => console.log("  " + String(i + 1).padStart(2) + " [" + c.type + "] " + c.quote.slice(0, 100)));

  const r = await call("folio_import_cards", { paperId: PAPER, cards, dryRun: DRY });
  console.log("\n" + (DRY ? "【试算】" : "【已写入】") + " 请求 " + r.requested +
    " · 锚定 " + r.anchored + " · 未命中 " + r.unanchored);
  if (r.unanchored) { console.log("未命中明细："); (r.items || []).slice(0, 12).forEach((x) => console.log("  ✗ " + String(x.quote).slice(0, 96))); }
  process.exit(0);
})().catch((e) => { console.error("失败：" + e.message); process.exit(1); });
