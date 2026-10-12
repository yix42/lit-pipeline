/* L2 阅读卡 —— quote 全部逐字取自入库正文。
   note 里写的是与我自身课题（AF 消融、血清蛋白组学、左房标测 VTH）的关联。
   先跑 dryRun 确认锚定命中率，再决定是否落盘。 */
const BASE = "http://127.0.0.1:8787";

const CARDS = [
  {
    type: "KT",
    quote: "However, our findings indicate that the RA proteome exhibits the hallmark characteristics of persAF at comparable levels to LA, reflecting a global atrial unification and reinforcing the view that persAF is a biatrial disease.",
    note: "【知识主题】全文的核心命题：持续性房颤不是左房单侧疾病，而是双心房疾病。\n\n对我课题的意义：我一直把分析重心放在左房（LVA 双极电压标测、VTH 阈值、肺静脉隔离）。如果 persAF 是真的双心房疾病，那么「只标左房、只打肺静脉」在 persAF 里就是系统性欠治疗。这直接关系到我 af0916 队列的分析口径 —— 是否该把 RA 也纳入。",
    comment: "要追问：作者说的是「proteome 层面 comparable」，这不等于「电生理层面 equally arrhythmogenic」。蛋白组相似 ≠ 致心律失常性相同。别直接把结论外推到消融策略。",
    tags: ["双心房疾病", "persAF", "核心命题"],
    star: true,
    pinned: true,
  },
  {
    type: "KC",
    quote: "Although significant proteomic differences were observed between the RA and LA from SR patients, a comparison of RA and LA proteomes in persAF patients revealed proteome homogenization between the two atrial chambers.",
    note: "【核心概念：心房蛋白质组均一化 homogenization】窦律下左右房蛋白组显著不同，persAF 下趋同。\n\n机制是双向的：RA 丢失 RA 特异标志物（HCN4/CACNA2D2/NTM/RGS6），同时获得 LA 特异标志物（线粒体、脂肪酸代谢相关）。左房基本不变，是右房在向左房靠。\n\n记住这个方向性 —— 「LA 稳定、RA 迁移」，不是两边各走一半。",
    comment: "注意这里说的是 RA→LA 单向迁移为主。我在写讨论时不能说成「双向趋同」。",
    tags: ["蛋白质组均一化", "左右房", "方向性"],
    star: true,
  },
  {
    type: "KM",
    quote: "A spectral library representing 13 539 human proteins was generated from five anatomical regions of five independent donor hearts.",
    note: "【方法要点：自建光谱库 + DIA-MS】用 5 个供体心脏的 5 个解剖区域建参考谱图库（13 539 蛋白），再用 diaPASEF 做 DIA 定量。\n\n对我有用的地方：\n1. DIA 相比 DDA 的优势是重现性和跨批次可比性 —— 我这边的血清样本分多批跑，如果换 DIA 能缓解批次效应；\n2. 谱图库思路可以直接抄：先用代表性样本建库，再批量定量。\n\n但我做的是血清，不是组织，蛋白动态范围和复杂度差一个量级，别照搬。",
    comment: "待办：查一下我们平台（timsTOF 还是 Orbitrap）能否上 diaPASEF。",
    tags: ["DIA-MS", "光谱库", "方法可借鉴"],
    star: true,
  },
  {
    type: "KM",
    quote: "Discovery thresholds and correction were unchanged (FDR < 0.05 together with |log2FC| > 0.58).",
    note: "【方法要点：统计口径】GEE 模型（geepack）+ BH 校正，阈值 FDR<0.05 且 |log2FC|>0.58。\n\n对照我自己的口径：我用的是 limma + 经验贝叶斯，阈值 |logFC|>0.25。这里的 0.58 相当于 1.5 倍变化，比我的 0.25（约 1.19 倍）严得多。\n\n这是个值得写进讨论的差异点：我的阈值更宽松，所以差异蛋白比例会更高，不能直接跟这篇的 21/658 比。",
    comment: "⚠️ 我原以为 0.25 是通用阈值。这篇用 0.58。我的 Sci Rep 稿件里如果引用「与文献一致的阈值」这种说法，要谨慎。",
    tags: ["统计阈值", "log2FC", "limma", "GEE"],
    star: true,
  },
  {
    type: "KM",
    quote: "To summarize medication burden, we constructed Drugs-PC1 as the first principal component of eight binary drug-use indicators (Digitalis, ACE inhibitors, AT1 blockers, beta-blockers, dihydropyridines, diuretics, nitrates, lipid-lowering drugs) after centering and scaling.",
    note: "【方法要点：混杂控制】把 8 类药物的二分类用药指标做 PCA 取第一主成分（Drugs-PC1），作为一个综合协变量纳入模型，而不是把 8 个变量分别塞进去。\n\n这个做法我很想用：我的队列里用药种类多、样本量有限，逐个纳入会吃自由度。降维成一个协变量既控制混杂又不炸模型。\n\n而且他们做了敏感性分析对比：Drugs-PC1 校正后 R²=0.969、RMSE=0.034，全校正模型 r=0.917 —— 效应估计几乎不动，说明药物负担不是主要混杂。这种「主动展示敏感性分析」的写法值得学。",
    comment: "我的稿子如果要回应审稿人关于围术期用药的质疑，这种 Drugs-PC1 + 敏感性分析的做法可以直接参照。",
    tags: ["混杂控制", "PCA降维", "敏感性分析"],
    star: false,
  },
  {
    type: "KR",
    quote: "In persAF, the number of DEPs in RA was reduced by 85%, while LA showed a 50% reduction.",
    note: "【关键结果：均一化的量化证据】persAF 下 RA 的差异蛋白减少 85%，LA 减少 50%。\n\n这个不对称数字是全文最有力的证据：RA 丢失了绝大部分「身份特征」，LA 只丢一半。配合前面的方向性结论（LA 稳定、RA 迁移），逻辑链是完整的。",
    comment: "85% 和 50% 的分母要小心 —— 是相对 SR 状态下各自的 DEP 数。引用时别写成「RA 减少 85% 的差异蛋白」这种含糊说法。",
    tags: ["DEPs", "85%", "50%", "量化证据"],
    star: true,
  },
  {
    type: "KV",
    quote: "Our analysis identified 21 differentially expressed proteins [FDR < 0.05 and |log2(FC)| > 0.58] in RA-persAF samples, of which 17 were up-regulated and 4 were down-regulated.",
    note: "【证据数据】RA-persAF vs RA-SR：21 个差异蛋白，17 上调 4 下调。n=15(SR) vs 16(persAF)。\n\n注意 17:4 这个上调占绝对优势的比例 —— 作者在讨论里解释为 ECM 大量产生 + 蛋白合成区室（ER、Golgi）增加，而肌原纤维蛋白降解。上调为主的模式跟「纤维化+肌溶解」的组织学表型是自洽的。",
    comment: "样本量只有 15 vs 16，21 个差异蛋白不多。别拿这个数字当强证据。",
    tags: ["21 DEPs", "n=15 vs 16", "样本量"],
    star: false,
  },
  {
    type: "KV",
    quote: "In RA-persAF, 61% of most abundant RA-SR proteins relative to LA-SR, including HCN4, CACNA2D2, NTM and RGS6, were down-regulated.",
    note: "【证据数据：RA 标志物丢失】RA 特异标志物 61% 下调，同时 LA 特异标志物 47% 上调。\n\nCACNA2D2 和 RGS6 还做了免疫印迹验证（独立队列），两个心房在 persAF 下丰度相当 —— 这是全篇少数有独立验证的结论。\n\nHCN4 是起搏电流相关，CACNA2D2 是钙通道辅助亚基 —— 这两个下调可能直接对应电生理改变，比 ECM 蛋白更接近机制。",
    comment: "待查：HCN4/CACNA2D2 下调是否已在功能层面被证实（电流密度测定）。这篇只做到蛋白丰度。",
    tags: ["RA标志物", "HCN4", "CACNA2D2", "RGS6", "61%"],
    star: true,
  },
  {
    type: "KR",
    quote: "Furthermore, a marked decrease in cardiac contractile proteins was observed, including TNNC1, CRYAB, TPM1, TPM2, MYLK, MYH11, MYH14, MYL2, and TNNT2.",
    note: "【关键结果：肌溶解 myolysis】心肌收缩蛋白广泛下降：肌钙蛋白、原肌球蛋白、肌球蛋白轻/重链、MLCK。\n\n作者把它跟「肌原纤维降解 + 溶酶体增多」联系起来，并指出肌钙蛋白 C 降解会损害收缩功能、削弱胞质 Ca2+ 缓冲，进一步促 AF —— 这是从结构到电生理的桥接。\n\n对我的意义：我做的 LVA（低电压区）标测，其组织学基础通常被认为是纤维化。这篇提示肌溶解也是平行机制，且可能在纤维化之前发生。",
    comment: "⚠️ 重要：如果肌溶解先于纤维化，那 LVA 电压阈值捕捉的可能只是「晚期」表型。这对 VTH 阈值的时间窗解释有影响。",
    tags: ["肌溶解", "收缩蛋白", "LVA病理基础"],
    star: true,
  },
  {
    type: "KV",
    quote: "After covariate adjustment, the direction of the effect was preserved, though statistical significance was not reached, likely reflecting the limited sample size and variance imbalance (13 vs. 6, F-test = 0.049).",
    note: "【证据数据：纤维化量化的软肋】组织学纤维化队列只有 13(SR) vs 6(persAF)，校正后效应方向保留但不再显著，且方差不齐（F-test=0.049）。\n\n这是全篇最弱的一环：6 例 persAF 做纤维化定量，样本量太小。作者自己承认了。\n\n我特别留意这种「方向对但不显著」的处理方式 —— 作者如实报告并给出原因，没有硬吹。",
    comment: "F-test = 0.049 说明两组方差不齐，用了 Welch 检验。这种细节我在自己的稿件里也该交代。",
    tags: ["纤维化", "样本量不足", "方差不齐", "13 vs 6"],
    star: false,
  },
  {
    type: "KR",
    quote: "It is important to highlight that the persAF patient cohort in this study had preserved left ventricular ejection fraction, supporting the notion that HF-associated features in the atria develop independently of ventricular dysfunction.",
    note: "【关键结果：心房的心衰样特征独立于心室功能障碍】persAF 患者 LVEF 正常，但心房蛋白组已经出现心衰样特征（NPPA/NPPB 上调、纤维化、缺氧、肌溶解、能量代谢、细胞骨架相关蛋白富集）。\n\n这个排除很关键 —— 排除了「心房变化是心室功能不全的继发表现」这个替代解释。\n\n另外注意：作者说这是「stress-related adaptive processes」，不是胎型代谢重编程（没有脂肪酸氧化→糖酵解的转变）。这个区分很重要，别笼统说「心衰表型」。",
    comment: "这个「LVEF 正常但仍出现心衰样心房重构」的论点，跟我关心的「心房基质改变是否独立于心室」直接相关。",
    tags: ["LVEF正常", "心衰样特征", "替代解释排除"],
    star: true,
  },
  {
    type: "KS",
    quote: "On the other hand, a comparable proteome between the two atrial chambers in persAF potentially suggests that both chambers may serve as equally vulnerable substrates promoting AF progression in the presence of widespread AF triggers.",
    note: "【可证伪问题】作者的推论：两个心房在 persAF 下是同样易感的基质。\n\n我要把它变成可检验的预测：\n\n若 persAF 确为双心房疾病，则在仅接受肺静脉隔离（不处理 RA 非肺静脉灶）的 persAF 患者中，复发灶应显著富集于右房来源位点（上腔静脉、冠状窦）；若我们的 af0916 队列里复发患者的 RA 标测异常比例与 LA 相当甚至更高，则支持该推论；若 RA 与 LA 无显著差异、复发灶仍以肺静脉传导恢复为主，则该推论在我们的队列中不成立。\n\n判定标准：复发患者中 RA 来源非肺静脉灶占比是否显著高于「LA 肺静脉传导恢复」以外的其他机制。需要在 ≥100 例、随访 ≥12 个月的队列中检验。",
    comment: "作者用的是「potentially suggests」，很克制。我改成可证伪句式时要保留这个克制 —— 给出明确的判定标准和推翻条件，而不是说「有待更多研究」。",
    tags: ["可证伪预测", "非肺静脉灶", "af0916", "双心房基质"],
    star: true,
    pinned: true,
  },
  {
    type: "KM",
    quote: "Consistently, NT-proANP and NT-proBNP were also significantly up-regulated in plasma samples from persAF patients compared with SR patients.",
    note: "【方法对照：组织→血浆的唯一桥接】全篇唯一把组织发现外推到血浆的证据：NT-proANP（校正后仍显著）、NT-proBNP（校正后仅趋势，不显著）。\n\n对照我的研究：我做的是血清蛋白组学，这篇做的是心房组织。这个对比是我最该在讨论里点明的 ——\n\n组织蛋白组能直接看基质重构，但不可重复采样；血清能重复采样（术前/术后 30 天），但稀释效应和高丰度蛋白掩盖问题严重。\n\n注意 NT-proBNP 校正后不显著的细节：年龄、性别、CAD、瓣膜病、利尿剂一校正就掉了。这正是血清标志物的通病 —— 混杂太强。",
    comment: "⚠️ 我的 Sci Rep 稿件如果被问「血清发现能否反映心房组织改变」，这篇就是最好的对照文献。",
    tags: ["血清vs组织", "NT-proANP", "NT-proBNP", "对照文献"],
    star: true,
  },
  {
    type: "KC",
    quote: "Transcription factor paired-like homeodomain 2 (PITX2) has been suggested to play a significant role in the left-right asymmetry by modulating gene expression, ensuring the proper development and functional differentiation of the LA.",
    note: "【核心概念：PITX2 与左右不对称】PITX2 活性左房更高，是左右房身份差异的上游调控者。RA 富集的标志物（CACNA2D2、HCN4、RGS6、NTM、BMP10）都跟「低 PITX2 活性」相关。\n\n这给了均一化一个分子层面的解释框架：不是随机漂移，而是 PITX2 驱动的左右身份程序在疾病状态下被抹平。",
    comment: "作者在 limitation 里说整体组织裂解会掩盖 PITX2（转录因子丰度低）—— 所以 PITX2 本身在蛋白层面没直接测到，是推断。引用时要标明这一点。",
    tags: ["PITX2", "左右不对称", "上游调控"],
    star: false,
  },
  {
    type: "NT",
    quote: "In addition, the number of paired RA and LA samples in this study is limited.",
    note: "【随手批注：最大软肋】配对 RA/LA 样本只有 6 例 persAF、8 例 SR。全文最重要的结论（均一化）就建立在这 6 对上。\n\n作者自己也说「obtaining paired samples is exceptionally challenging」。\n\n另外两个局限要记：\n1. 用的是心耳（appendage），可能不代表整个心房；\n2. 整体组织裂解，缺乏细胞类型特异信息，低丰度蛋白（转录因子、离子通道）被掩盖。\n\n第 2 条对我特别重要 —— 我做血清的，低丰度掩盖问题更严重。",
    comment: "读这类样本量小的机制研究，结论要按「hypothesis-generating」对待，不能当定论。",
    tags: ["局限性", "配对样本", "n=6", "细胞类型"],
    star: false,
  },
];

async function call(name, args) {
  const r = await fetch(BASE + "/api/call", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, args }),
  });
  const j = await r.json();
  return JSON.parse(j.result.content[0].text);
}

(async () => {
  const pid = process.argv[2];
  if (!pid) { console.error("用法: node cards_run.js <paperId> [--dry]"); process.exit(1); }
  const dry = process.argv.includes("--dry");

  const res = await call("folio_import_cards", { paperId: pid, cards: CARDS, dryRun: dry });
  console.log(dry ? "=== dryRun 试算 ===" : "=== 已导入 ===");
  console.log("  请求卡片 :", res.requested);
  console.log("  成功锚定 :", res.anchored);
  console.log("  未命中   :", res.unanchored);
  // dryRun 会返回全部明细（便于逐条核对），正式导入只返回未命中的
  if (dry) {
    console.log("\n  逐条命中情况：");
    res.items.forEach((it, i) => {
      const mark = it.anchored ? "OK  " : "MISS";
      console.log("    " + mark + " [" + it.type + "] p" + it.paraIdx + " " + it.quote.slice(0, 62) + "…");
    });
  } else if (res.items && res.items.length) {
    console.log("\n  未命中明细（这些卡建了但没有锚点，" + "「定位原文」按钮不会出现）：");
    res.items.forEach((it) => console.log("    [" + it.type + "] " + it.quote.slice(0, 70) + "…"));
  } else {
    console.log("\n  全部 quote 均在原文中命中 —— 每张卡都能用「定位原文」跳回去。");
  }
  if (!dry) {
    const st = await call("folio_status", {});
    console.log("\n  当前数据：文献 " + st.papers + " 篇 / 卡片 " + st.cards + " 张");
  }
})();
