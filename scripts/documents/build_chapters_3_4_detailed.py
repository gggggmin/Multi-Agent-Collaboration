from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


TITLE = "基于安全约束PPO和成本敏感LinUCB的多智能体Web自动化测试生成与自愈研究"
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "thesis" / "drafts" / "毕业论文第三章第四章详细正文初稿.docx"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def set_font(run, east="宋体", latin="Times New Roman", size=Pt(11), bold=None, italic=None):
    run.font.name = latin
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), latin)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), latin)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), east)
    run.font.size = size
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=110, start=130, bottom=110, end=130):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for tag, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_width(cell, width_cm):
    cell.width = Cm(width_cm)
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(int(Cm(width_cm).emu / 635)))
    tc_w.set(qn("w:type"), "dxa")


def repeat_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def add_page_number(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, end])
    set_font(run, size=Pt(9))


def configure(doc):
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(11)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.first_line_indent = Cm(0.74)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    title = styles["Title"]
    title.font.name = "黑体"
    title._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
    title.font.size = Pt(20)
    title.font.bold = True
    title.font.color.rgb = RGBColor(0, 0, 0)
    title.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.line_spacing = 1.25
    title.paragraph_format.space_after = Pt(18)
    title_ppr = title._element.get_or_add_pPr()
    title_border = title_ppr.find(qn("w:pBdr"))
    if title_border is not None:
        title_ppr.remove(title_border)

    for name, size, before, after in (
        ("Heading 1", 16, 18, 12),
        ("Heading 2", 14, 14, 8),
        ("Heading 3", 12, 10, 6),
    ):
        s = styles[name]
        s.font.name = "黑体"
        s._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
        s.font.size = Pt(size)
        s.font.bold = True
        s.font.color.rgb = RGBColor(0, 0, 0)
        s.paragraph_format.space_before = Pt(before)
        s.paragraph_format.space_after = Pt(after)
        s.paragraph_format.keep_with_next = True
        s.paragraph_format.first_line_indent = Cm(0)


def heading(doc, text, level):
    return doc.add_heading(text, level=level)


def body(doc, text, bold_lead=None):
    p = doc.add_paragraph()
    if bold_lead and text.startswith(bold_lead):
        r1 = p.add_run(bold_lead)
        set_font(r1, bold=True)
        r2 = p.add_run(text[len(bold_lead):])
        set_font(r2)
    else:
        r = p.add_run(text)
        set_font(r)
    return p


def bullet(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.8)
    p.paragraph_format.first_line_indent = Cm(-0.35)
    p.paragraph_format.line_spacing = 1.4
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("• " + text)
    set_font(r)
    return p


def numbered(doc, items):
    for idx, text in enumerate(items, 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.8)
        p.paragraph_format.first_line_indent = Cm(-0.45)
        p.paragraph_format.line_spacing = 1.4
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(f"{idx}. {text}")
        set_font(r)


def equation(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_together = True
    r = p.add_run(text)
    set_font(r, east="Cambria Math", latin="Cambria Math", size=Pt(11), italic=True)
    return p


def table(doc, headers, rows, widths):
    tbl = doc.add_table(rows=1, cols=len(headers))
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    repeat_header(tbl.rows[0])
    for idx, text in enumerate(headers):
        cell = tbl.rows[0].cells[idx]
        set_cell_width(cell, widths[idx])
        set_cell_shading(cell, "1F4E78")
        set_cell_margins(cell)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(str(text))
        set_font(r, east="黑体", size=Pt(9.5), bold=True)
        r.font.color.rgb = RGBColor(255, 255, 255)
    for ridx, values in enumerate(rows):
        cells = tbl.add_row().cells
        for idx, value in enumerate(values):
            cell = cells[idx]
            set_cell_width(cell, widths[idx])
            set_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            if ridx % 2 == 1:
                set_cell_shading(cell, "F2F6FA")
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if idx == 0 else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.2
            r = p.add_run(str(value))
            set_font(r, size=Pt(9.5))
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(2)
    return tbl


def page_break(doc):
    p = doc.add_paragraph()
    p.add_run().add_break(WD_BREAK.PAGE)


doc = Document()
section = doc.sections[0]
section.page_width = Cm(21)
section.page_height = Cm(29.7)
section.top_margin = Cm(2.5)
section.bottom_margin = Cm(2.3)
section.left_margin = Cm(2.8)
section.right_margin = Cm(2.5)
section.header_distance = Cm(1.2)
section.footer_distance = Cm(1.2)
configure(doc)
add_page_number(section)

# Cover
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(76)
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("硕士毕业论文核心方法章节正文初稿")
set_font(r, east="黑体", size=Pt(16), bold=True)

t = doc.add_paragraph(style="Title")
t.add_run(TITLE)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(14)
r = p.add_run("第三章与第四章")
set_font(r, east="宋体", size=Pt(14))

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(80)
r = p.add_run("形成日期  2026 年 11 月 5 日")
set_font(r, size=Pt(11))

page_break(doc)

# Chapter 3
heading(doc, "第3章 基于安全约束PPO的多智能体Web测试生成控制方法", 1)
body(doc, "本章针对多智能体测试生成采用固定迭代轮次、审查反馈难以计算以及学习策略可能提前接受不合格结果的问题，提出一种基于安全约束PPO的生成控制方法。该方法首先将需求证据、生成用例与审查结果转换为结构化质量状态，再由PPO策略网络根据当前状态选择接受、定向修订或刷新证据等动作，最后通过确定性安全动作投影阻止违反质量底线的接受行为。方法目标不是让PPO直接生成测试文本，而是使其成为Creator与Auditor协作过程中的决策控制器，在保证质量约束的前提下减少无效迭代和模型调用成本。")

heading(doc, "3.1 研究问题与方法定位", 2)
heading(doc, "3.1.1 固定轮次生成的局限", 3)
body(doc, "需求驱动的测试生成通常由大语言模型根据需求文档产生测试用例，再通过独立审查角色检查覆盖、逻辑一致性和需求外行为。为了改善初始结果，系统往往预先规定两轮或三轮生成与审查。该机制实现简单，但默认不同需求具有相同难度：简单需求即使首轮已经合格也要继续调用模型，复杂需求则可能在固定轮次结束时仍存在严重遗漏。固定轮次因此同时存在资源浪费和质量不足两种风险。")
body(doc, "仅把固定轮次替换为普通PPO也不能自动获得安全性。PPO通过经验回报优化策略，在探索、训练不足或分布外状态下可能给出错误的接受动作。如果该动作直接控制后续代码生成，存在严重问题或证据不足的用例仍可能进入执行阶段。由此，本章需要同时回答两个问题：如何学习质量与成本之间的动态迭代策略，以及如何保证学习策略无权突破明确的质量底线。")

heading(doc, "3.1.2 研究目标与约束", 3)
body(doc, "设一份需求经过第t轮生成和审查后得到质量状态s_t，决策器选择动作a_t并产生下一状态s_(t+1)。本章目标是在有限轮次内最大化累计质量收益并最小化模型调用成本，同时满足严重错误、需求覆盖和证据一致性等硬约束。该目标可以表示为带约束的序列决策问题。")
equation(doc, "max_π  E_π[Σ_(t=0)^(T-1) γ^t R(s_t,a_t)]    s.t.    g_j(s_t,a_t) ≤ 0,  j=1,…,m")
body(doc, "其中，π表示生成控制策略，T表示最大迭代轮次，γ为折扣因子，R表示质量与成本联合奖励，g_j表示第j项安全约束。约束并不依赖策略网络自行学习，而由安全层在推理阶段确定性执行，从而将效率优化与质量底线分离。")

heading(doc, "3.2 总体架构", 2)
body(doc, "所提方法由需求证据层、多智能体生成审查层、策略决策层和安全控制层组成。需求证据层解析原始需求并构建可检索的语义证据；Creator依据证据生成或修订测试用例；Auditor对用例进行结构化审查；策略决策层将审查结果编码为状态并由PPO提出候选动作；安全控制层计算当前允许动作集合，对不安全候选动作进行投影。")
table(doc, ["组成部分", "输入", "主要处理", "输出"], [
    ["需求证据层", "需求文档与检索查询", "语义切片、证据检索、需求点映射", "需求证据集合"],
    ["Creator", "证据、历史用例和修订指令", "生成正向、逆向和边界测试用例", "当前测试用例集"],
    ["Auditor", "需求证据与测试用例", "检查遗漏、幻觉、冲突、边界和可追溯性", "结构化审查结果"],
    ["PPO决策器", "质量状态与成本状态", "估计动作概率和状态价值", "候选控制动作"],
    ["安全控制层", "候选动作和硬约束", "计算安全集合并执行动作投影", "最终可执行动作"],
], [2.7, 3.3, 5.0, 4.0])
body(doc, "该架构强调控制层与生成层解耦。大语言模型负责文本生成和语义审查，PPO负责控制下一步行为，安全层负责强制质量约束。这样既避免将大语言模型的主观评分直接当作最终决策，也避免将全部安全责任交给需要通过数据学习的策略网络。")

heading(doc, "3.3 生成控制过程的马尔可夫决策建模", 2)
heading(doc, "3.3.1 状态空间", 3)
body(doc, "为使策略网络能够稳定判断当前结果是否值得继续修订，需要将自然语言需求、测试用例和审查评论转换为数值状态。本章将第t轮状态表示为：")
equation(doc, "s_t=[i_t,e_t,w_t,h_t,c_t,Δc_t,q_t,k_t,u_t]")
table(doc, ["符号", "状态维度", "计算来源", "决策含义"], [
    ["i_t", "当前轮次", "协调器运行记录", "反映剩余迭代预算"],
    ["e_t", "严重错误数", "Auditor的error级问题", "存在严重错误时禁止接受"],
    ["w_t", "警告问题数", "Auditor的warning级问题", "衡量仍需优化的缺陷规模"],
    ["h_t", "幻觉率", "无需求证据用例数与总用例数之比", "衡量需求外行为风险"],
    ["c_t", "需求覆盖率", "需求点与测试用例映射", "判断用例是否覆盖核心需求"],
    ["Δc_t", "覆盖增量", "相邻两轮覆盖率差值", "衡量继续迭代的边际收益"],
    ["q_t", "证据一致性", "用例、断言与需求片段的匹配结果", "判断用例能否追溯到有效证据"],
    ["k_t", "累计成本", "Token、调用次数和耗时归一化值", "约束无效迭代"],
    ["u_t", "执行或静态可用性", "可选的代码预检查或历史通过信息", "补充文本审查之外的可执行性证据"],
], [1.5, 3.0, 5.0, 5.5])
body(doc, "离散计数特征按照任务规模归一化，比例特征限制在0到1之间，成本特征按照预设预算截断。缺失状态不直接填零，而是增加可用性标记或采用训练集统计量填充，避免策略将“未计算”误判为“没有问题”。所有状态字段均保存其需求证据、审查问题和用例标识之间的映射，以支持结果复核。")

heading(doc, "3.3.2 动作空间", 3)
body(doc, "传统二动作策略只能决定继续或接受，无法告知Creator下一轮应该处理什么问题。为提高迭代方向性，本章设计五类控制动作。")
table(doc, ["动作", "触发场景", "执行内容", "预期作用"], [
    ["ACCEPT", "无严重错误且各项质量阈值达标", "结束迭代并进入代码生成", "避免无收益调用"],
    ["覆盖修订", "需求覆盖不足", "针对未覆盖需求点补充用例", "提升覆盖率"],
    ["一致性修订", "存在错误、幻觉或冲突", "删除无依据用例并修正逻辑", "降低需求外行为"],
    ["边界修订", "主体流程完整但边界不足", "补充异常、边界和逆向场景", "提高测试充分性"],
    ["刷新证据", "证据为空或一致性偏低", "调整检索查询并重建生成上下文", "修复证据失配"],
], [3.2, 4.0, 5.0, 3.8])
body(doc, "动作执行后，Creator收到明确的问题类别、对应需求证据和受影响用例，而不是笼统的“请继续优化”。这种设计把策略决策转化为可执行的修订指令，使状态、动作与质量变化之间形成可解释的因果链。")

heading(doc, "3.3.3 状态转移与终止条件", 3)
body(doc, "动作执行后，Creator生成新的用例集合，Auditor重新计算审查结果和质量指标，系统由s_t转移到s_(t+1)。由于大语言模型输出具有随机性，状态转移并非完全确定；训练阶段需要固定随机种子、保存生成轨迹，并在相同初始任务上重复运行，以区分策略效果与模型采样噪声。")
body(doc, "正常终止发生在安全接受条件全部满足且最终动作是ACCEPT时。失败终止发生在达到最大轮次、累计成本超过预算或连续多轮质量无提升时。失败终止不能等价于默认接受，而应返回明确的failed_max_iterations状态并阻止后续代码生成，必要时转人工审查。")

heading(doc, "3.4 质量成本联合奖励", 2)
body(doc, "奖励函数需要同时反映质量收益、风险损失和资源成本。若只奖励覆盖率，策略可能通过生成大量重复或无效用例刷高指标；若只惩罚调用次数，策略可能过早接受。因此，本章采用质量、风险和成本三部分构成的联合奖励。")
equation(doc, "R_t=λ_q·QualityGain_t−λ_r·Risk_t−λ_c·Cost_t+λ_b·TerminalBonus_t")
body(doc, "质量收益由覆盖率增量、证据一致性增量、严重错误减少量和可执行性改善组成；风险项由不安全接受、严重错误残留和需求外行为组成；成本项由模型调用次数、Token、耗时和重复修订组成；终止奖励仅在安全接受时给予。")
equation(doc, "QualityGain_t=α_1Δc_t+α_2Δq_t+α_3(e_(t−1)−e_t)+α_4Δu_t")
equation(doc, "Risk_t=β_1·I_unsafe_accept+β_2e_t+β_3h_t")
equation(doc, "Cost_t=η_1Token_t+η_2Latency_t+η_3Retry_t")
body(doc, "各项指标在进入奖励函数前进行归一化，权重通过验证集和敏感性实验确定。安全接受惩罚应明显大于一次普通调用成本，使策略无法通过少量成本节省抵消质量底线。同时，安全层仍需独立存在，因为有限惩罚不能提供确定性的零违规保证。")

heading(doc, "3.5 PPO策略优化", 2)
heading(doc, "3.5.1 Actor Critic网络", 3)
body(doc, "本章使用基于Actor-Critic结构的PPO。Actor接收状态向量并输出五类动作的概率分布，Critic估计当前状态价值。对于本研究规模，采用多层感知机即可表达状态特征之间的非线性关系，无需引入更重的Transformer结构。策略网络的作用是学习不同质量状态下的控制偏好，而不是学习测试文本本身。")
body(doc, "PPO通过限制新旧策略概率比的变化幅度提高训练稳定性。其裁剪目标为：")
equation(doc, "L_clip(θ)=E_t[min(r_t(θ)Â_t, clip(r_t(θ),1−ε,1+ε)Â_t)]")
body(doc, "其中，r_t(θ)为新旧策略对已执行动作的概率比，Â_t为优势函数估计，ε为裁剪系数。总损失还包括价值函数误差和策略熵正则项，用于提高价值估计精度并维持适度探索。")
equation(doc, "L(θ)=L_clip(θ)−c_vL_value(θ)+c_eH(π_θ)")

heading(doc, "3.5.2 训练数据与训练过程", 3)
body(doc, "训练轨迹由需求任务、每轮生成结果、审查问题、动作、下一状态、奖励和终止原因组成。为避免策略只适应少量固定需求，训练集应覆盖不同模块数量、需求长度、边界复杂度和初始缺陷类型。受控训练环境可以系统生成遗漏、幻觉、冲突和边界不足等状态，但最终评价必须使用真实Creator与Auditor多轮轨迹。")
numbered(doc, [
    "从训练任务集中采样需求，并生成初始测试用例和审查结果。",
    "构建归一化质量状态，由Actor采样候选动作。",
    "安全层根据当前硬约束生成最终动作并记录是否发生投影。",
    "执行修订或接受动作，获得下一状态和质量成本奖励。",
    "收集固定长度轨迹，计算优势函数与回报。",
    "按多个epoch更新Actor和Critic，并监控策略熵、价值损失和安全投影比例。",
    "在独立验证集上选择兼顾安全、质量和成本的模型检查点。",
])

heading(doc, "3.6 安全约束与动作投影", 2)
heading(doc, "3.6.1 安全接受条件", 3)
body(doc, "对状态s_t定义安全接受谓词SafeAccept(s_t)。只有严重错误为零、覆盖率达到阈值、幻觉率不超过上限、证据一致性达到阈值且必要场景完整时，该谓词才为真。")
equation(doc, "SafeAccept(s_t)=I[e_t=0 ∧ c_t≥τ_c ∧ h_t≤τ_h ∧ q_t≥τ_q ∧ b_t=1]")
body(doc, "其中，b_t表示必要边界与异常场景是否满足。阈值应根据任务类别分别标定，不能用一个覆盖率阈值粗暴处理所有需求。对于业务断言和安全相关需求，还应增加人工确认或证据强一致性条件。")

heading(doc, "3.6.2 安全动作集合与投影规则", 3)
body(doc, "安全层根据问题类型计算当前允许动作集合A_safe(s_t)。若PPO提出的动作属于安全集合，则原样执行；若不属于，则投影为与主要缺陷最相关的修订动作。")
equation(doc, "a'_t=a_t, if a_t∈A_safe(s_t); otherwise a'_t=Project(a_t,s_t)")
table(doc, ["检测条件", "禁止动作", "投影动作"], [
    ["e_t>0或h_t>τ_h", "ACCEPT", "REVISE_CONSISTENCY"],
    ["c_t<τ_c", "ACCEPT", "REVISE_COVERAGE"],
    ["必要边界场景缺失", "ACCEPT", "REVISE_BOUNDARY"],
    ["q_t<τ_q或证据为空", "ACCEPT", "REFRESH_EVIDENCE"],
    ["达到成本或轮次上限仍不合格", "ACCEPT及继续自动修改", "失败退出并转人工"],
], [5.0, 4.0, 6.0])
body(doc, "投影动作不是简单地把所有违规情况都改成继续，而是依据缺陷严重程度、需求覆盖缺口和证据问题进行确定性排序。这样既维持安全底线，也保留细粒度动作带来的效率优势。")

page_break(doc)
heading(doc, "3.7 算法流程与复杂度分析", 2)
heading(doc, "3.7.1 完整算法流程", 3)
table(doc, ["步骤", "处理内容", "关键输出"], [
    ["1", "解析需求并构建可追溯证据集合", "需求点与证据映射"],
    ["2", "Creator生成初始测试用例", "用例集合C_0"],
    ["3", "Auditor执行结构化审查并计算质量指标", "状态s_t"],
    ["4", "PPO根据s_t产生候选动作a_t", "动作概率与价值估计"],
    ["5", "安全层计算A_safe并执行动作投影", "最终动作a'_t"],
    ["6", "执行接受、定向修订或证据刷新", "下一轮用例集合"],
    ["7", "计算质量、风险和成本奖励并记录轨迹", "转移样本"],
    ["8", "安全接受则进入代码生成，否则继续或失败退出", "终止状态与原因"],
], [1.5, 9.5, 4.0])

heading(doc, "3.7.2 时间与空间复杂度", 3)
body(doc, "设状态维度为d_s，动作数为|A|，策略网络参数量为P，最大迭代轮次为T。单次策略推理复杂度约为O(P)，安全条件检查和动作投影复杂度为O(d_s+|A|)。算法控制部分总复杂度约为O(T(P+d_s+|A|))。实际耗时主要来自大语言模型生成和审查，而不是PPO前向计算。轨迹存储空间与训练步数N和状态维度成正比，约为O(N(d_s+|A|))。")

heading(doc, "3.8 实验设计与阶段性结果", 2)
heading(doc, "3.8.1 研究问题与对比方法", 3)
body(doc, "实验围绕安全性、质量、效率和方法组成四类问题展开：RQ1检验安全约束能否降低不安全接受；RQ2检验细粒度动作能否提高修订效率；RQ3检验成本奖励能否减少无效调用；RQ4检验状态、动作和安全层的独立贡献。")
table(doc, ["类别", "对比方法", "比较目的"], [
    ["固定策略", "固定1轮、固定3轮、固定5轮", "评价动态迭代必要性"],
    ["规则策略", "基于覆盖和错误阈值的决策", "比较学习策略与人工规则"],
    ["学习策略", "原始PPO、二动作PPO", "评价细粒度动作和安全层"],
    ["本文方法", "结构化状态、五动作PPO和安全投影", "综合评价安全与成本权衡"],
], [2.5, 6.0, 6.5])

heading(doc, "3.8.2 评价指标与消融实验", 3)
body(doc, "质量指标包括需求覆盖率、严重错误率、幻觉率、证据一致性和审查通过率；安全指标包括不安全接受率和失败后默认放行率；效率指标包括平均迭代轮次、模型调用次数、Token、耗时和归一化成本；学习指标包括平均奖励、策略熵和安全投影比例。")
body(doc, "消融实验分别去除证据一致性与覆盖增量状态、将五动作退化为继续和接受、移除安全投影、移除成本惩罚，并改变安全阈值和奖励权重。所有方法应在相同需求、初始生成轨迹、模型配置和最大轮次下比较，使用多个随机种子报告均值、标准差、置信区间和效应量。")

heading(doc, "3.8.3 阶段性证据与有效性边界", 3)
body(doc, "现有受控状态迁移实验中，原始PPO的平均不安全接受率为2.47%，加入证据约束安全投影后降为0%；平均奖励由26.815提高到28.766，平均归一化成本由2.302下降到2.180。该结果说明安全动作投影能够在受控环境中阻止违规接受，并未以明显增加成本为代价。")
body(doc, "上述结果仍不能直接证明方法在任意真实需求和大语言模型协作场景中均有效。当前状态转移主要来自受控环境，真实Creator与Auditor多轮轨迹、跨项目需求和模型版本变化尚需补充；主流程还需要确保实际Coordinator调用训练后的Safe PPO并记录动作投影与终止原因。正式结论应建立在真实端到端轨迹和统计检验之上。")

heading(doc, "3.9 本章小结", 2)
body(doc, "本章提出了基于安全约束PPO的多智能体测试生成控制方法。该方法以需求证据和审查反馈构建结构化质量状态，以五类细粒度动作控制接受、定向修订和证据刷新，以质量风险成本联合奖励学习迭代策略，并通过确定性安全动作投影阻止不合格用例进入代码生成。方法将学习型效率优化与质量底线控制分离，为下一阶段生成可执行测试脚本提供可靠输入。")

page_break(doc)

# Chapter 4
heading(doc, "第4章 基于成本敏感LinUCB的Web测试自愈方法", 1)
body(doc, "本章针对Web自动化测试脚本因页面变化、异步加载、业务断言变化和测试数据污染等原因失效后，固定修复规则缺少场景适应性、全量大模型修复成本高且存在回归风险的问题，提出一种基于成本敏感LinUCB的上下文自愈策略选择方法。该方法融合故障诊断、页面变化、脚本复杂度、历史反馈和资源估计构建上下文向量，在可用策略集合中在线选择预期综合收益最高的修复方式，并通过隔离修复、目标用例复测、关联回归和失败回退形成安全闭环。")

heading(doc, "4.1 研究问题与方法定位", 2)
heading(doc, "4.1.1 Web测试脚本失效特点", 3)
body(doc, "Web测试脚本具有明显的环境依赖性。页面元素文本或层级变化会造成定位器失败，网络波动和异步渲染会导致等待超时，业务规则变化会造成断言不匹配，测试数据残留会破坏后续用例前置条件，依赖和语法错误则可能使脚本无法启动。即使错误日志属于同一类别，其最合适的修复方式也可能随DOM变化程度、脚本复杂度和历史表现而改变。")
body(doc, "固定的错误类型到修复策略映射无法表达这种上下文差异。例如，locator错误既可能只是按钮文本变化，也可能来自页面未加载、多元素匹配或DOM结构重构。另一方面，将所有故障都交给大语言模型重写不仅增加Token和等待成本，还可能修改正确断言、扩大补丁范围并引入新的回归。")

heading(doc, "4.1.2 上下文在线决策建模", 3)
body(doc, "本章将每次故障后的策略选择建模为上下文多臂老虎机问题。系统在时刻t观察故障上下文x_t，从可用修复策略集合A_t中选择策略a_t，执行修复和验证后获得奖励r_t，并利用该反馈更新策略参数。与第三章的多轮序列控制不同，本章主要关注单次故障下的在线选择，因此采用样本效率更高、解释性更强的LinUCB，而不继续堆叠PPO。")
equation(doc, "a_t=arg max_(a∈A_t) E[r_t | x_t,a]")
body(doc, "目标不是单纯最大化修复成功率，而是在目标用例恢复、关联回归安全、资源成本和重试风险之间获得更高综合收益。")

heading(doc, "4.2 故障上下文编码", 2)
heading(doc, "4.2.1 多源故障特征", 3)
body(doc, "单独使用错误类别会丢失决定策略效果的关键信息。本章从错误输出、页面状态、脚本结构、历史表现和资源估计五类来源构造上下文向量。")
table(doc, ["特征组", "示例字段", "数据来源", "决策作用"], [
    ["错误诊断", "locator、timeout、assertion、data、syntax、import", "异常类型、标准错误和Traceback", "确定候选策略范围"],
    ["定位器信息", "CSS、XPath、文本、role、候选元素数", "失败步骤和页面快照", "区分规则替换与语义重定位"],
    ["页面变化", "DOM差异、属性变化、加载状态和可见性", "当前DOM与历史快照", "估计局部规则修复是否可靠"],
    ["脚本结构", "代码长度、跳转数、断言数和依赖数量", "测试脚本静态分析", "估计修复复杂度和回归风险"],
    ["历史反馈", "相似故障成功率、失败次数和最近奖励", "策略历史库", "支持在线适应"],
    ["资源估计", "预计Token、执行时间、回归范围和重试成本", "调用与执行统计", "避免无脑选择高成本策略"],
], [2.5, 4.5, 4.2, 3.8])
body(doc, "离散特征采用独热编码，连续特征进行标准化或区间缩放，缺失特征增加显式缺失标记。最终上下文表示为x_t∈R^d。用于训练和推理的编码器必须共享字段顺序、归一化参数和类别字典，否则策略参数与线上输入将失去对应关系。")

heading(doc, "4.2.2 故障诊断与策略可用性", 3)
body(doc, "诊断器首先将原始异常归类，并提取页面和脚本特征。随后根据故障类型、权限和证据条件生成可用动作掩码m_t。不可用或高风险策略不进入LinUCB排序。例如，数据污染故障不应选择定位器修复；没有需求证据时不得自动修改业务断言；依赖缺失时无需调用DOM语义重定位。")
equation(doc, "A_t={a∈A | m_t(a)=1}")
body(doc, "可用性掩码既减少无效探索，也承担第一层安全控制。若诊断置信度过低或故障涉及关键业务断言，系统应限制自动修复范围并转人工确认，而不是让在线算法在高风险动作中试错。")

heading(doc, "4.3 修复策略池设计", 2)
table(doc, ["策略臂", "适用故障", "主要操作", "成本与风险"], [
    ["定位器规则修复", "局部定位器变化或多元素匹配", "根据候选元素、role和稳定属性替换定位器", "成本低，复杂DOM下成功率有限"],
    ["等待条件调整", "加载超时和异步渲染", "替换固定等待并增加条件等待", "成本低，可能掩盖性能问题"],
    ["断言修复", "有证据支持的断言变化", "依据需求证据局部修改断言", "风险较高，必须可追溯"],
    ["测试数据重置", "状态污染和前置数据失效", "重置测试数据或重建前置条件", "执行成本中等"],
    ["依赖修复", "语法、导入和依赖问题", "修复导入、版本或语法错误", "通常不需要页面语义"],
    ["LLM局部重写", "复杂DOM重构或组合故障", "限制上下文和补丁范围进行局部重写", "Token和回归成本高"],
    ["回退或转人工", "多次失败或高风险业务变化", "回退原脚本并转人工", "停止自动修改，避免扩大损失"],
], [3.7, 4.0, 4.7, 3.0])
body(doc, "策略池中的每个动作必须具有统一接口，包括适用条件、输入字段、补丁生成方式、静态检查、最大执行时间和回退方法。这样LinUCB输出的策略标识才能被工程执行层稳定调用，策略反馈也能按统一口径记录。")

heading(doc, "4.4 成本敏感LinUCB策略", 2)
heading(doc, "4.4.1 LinUCB参数估计与选择", 3)
body(doc, "对每个修复策略a维护参数矩阵A_a∈R^(d×d)和向量b_a∈R^d。初始化时A_a为单位矩阵，b_a为零向量。根据历史样本计算线性收益参数估计：")
equation(doc, "θ_a=A_a^(−1)b_a")
body(doc, "对当前上下文x_t，计算策略a的上置信界得分：")
equation(doc, "p_(t,a)=θ_a^T x_t+α√(x_t^T A_a^(−1)x_t)")
body(doc, "第一项表示当前上下文下的预计综合收益，第二项表示参数不确定性带来的探索奖励，α控制探索强度。系统仅在可用策略集合A_t中选择得分最高的策略。历史数据充分时，预计收益占主导；冷启动或新场景下，不确定性项推动适度探索。")
equation(doc, "a_t=arg max_(a∈A_t) p_(t,a)")

heading(doc, "4.4.2 成本敏感奖励", 3)
body(doc, "普通LinUCB只学习观测奖励，是否体现成本取决于奖励定义。本章将修复成功、回归安全、资源消耗和重试风险统一编码为成本敏感奖励。")
equation(doc, "r_t=ω_sS_t+ω_gG_t−λ_lC_(llm,t)−λ_eC_(exec,t)−λ_rN_(retry,t)−λ_fF_t")
table(doc, ["项", "含义", "推荐计算方式"], [
    ["S_t", "目标失败用例是否恢复", "通过为1，失败为0"],
    ["G_t", "关联回归是否安全", "回归通过比例或关键回归通过标记"],
    ["C_llm,t", "大模型调用成本", "归一化Token、调用次数和费用估计"],
    ["C_exec,t", "执行与验证成本", "修复耗时、目标复测与回归耗时"],
    ["N_retry,t", "当前故障重试次数", "按最大重试次数归一化"],
    ["F_t", "失败或引入回归的风险", "失败、扩大补丁或关键回归失败给予高惩罚"],
], [2.5, 5.0, 7.5])
body(doc, "当修复完成并获得奖励后，只更新被选择策略的参数：")
equation(doc, "A_(a_t)←A_(a_t)+x_t x_t^T")
equation(doc, "b_(a_t)←b_(a_t)+r_t x_t")
body(doc, "通过调整成本权重，可以形成偏质量、均衡或偏成本的策略配置。论文实验应报告不同权重下的成功率、回归率和成本变化，而不能只给出一组拍脑袋参数。")

heading(doc, "4.4.3 冷启动与模型持久化", 3)
body(doc, "新策略或新项目缺少历史数据时，LinUCB的不确定性较高。系统可利用受控故障注入样本完成初始预热，也可为低风险规则策略设置弱先验，但不应使用模拟成功率替代真实反馈长期运行。参数矩阵、向量、特征字典和归一化统计量需要作为同一模型版本持久化，并记录每次更新的故障、策略、奖励和成本来源。")

heading(doc, "4.5 隔离修复与回归反馈闭环", 2)
heading(doc, "4.5.1 隔离补丁生成", 3)
body(doc, "策略选择结果不能直接覆盖原始脚本。执行器首先创建隔离副本，保存原始版本、候选补丁、策略标识和上下文快照。规则策略只能修改限定字段，LLM策略应限制输入上下文、目标函数和补丁范围，禁止无关文件的大规模重写。补丁生成后先执行语法检查、导入检查和静态规则检查，未通过则立即判定本次尝试失败。")

heading(doc, "4.5.2 目标复测与关联回归", 3)
body(doc, "静态检查通过后，系统先运行原失败用例，确认目标故障是否消失；随后根据页面、需求点、公共Page Object和被修改模块选择关联回归集。只有目标用例通过且关键回归未退化时，候选补丁才可被接受。对于断言修改，还必须验证新断言能够追溯到需求证据，防止系统通过降低断言强度掩盖真实产品缺陷。")

heading(doc, "4.5.3 回退与停止条件", 3)
body(doc, "修复失败时恢复原始脚本，并将失败、耗时和成本反馈给策略。达到最大重试次数、连续选择高成本策略失败、诊断置信度过低或关键回归失败时，系统停止自动修改并转人工处理。失败退出是安全机制的一部分，不能为了提高表面修复率而无限重试。")
table(doc, ["阶段", "通过条件", "失败处理"], [
    ["补丁生成", "候选补丁产生且修改范围符合限制", "放弃补丁并记录策略失败"],
    ["静态检查", "语法、导入和规则检查全部通过", "回退并更新负奖励"],
    ["目标复测", "原失败用例恢复", "选择下一策略或停止"],
    ["关联回归", "关键回归全部通过且总体无显著退化", "拒绝补丁并回退"],
    ["证据检查", "断言修改可追溯到需求证据", "转人工确认"],
    ["提交更新", "补丁、结果和成本记录完整", "不得覆盖主脚本"],
], [2.7, 7.0, 5.3])

heading(doc, "4.6 算法流程与复杂度分析", 2)
heading(doc, "4.6.1 完整算法流程", 3)
numbered(doc, [
    "捕获标准输出、错误输出、Traceback、失败步骤、页面快照和DOM状态。",
    "诊断故障类别，提取定位器、页面变化、脚本结构、历史反馈和成本特征。",
    "按照统一编码器构造上下文向量x_t，并生成策略可用性掩码。",
    "计算各可用策略的LinUCB得分，选择得分最高的策略a_t。",
    "在隔离副本中执行修复，保存原代码、补丁、策略版本和上下文。",
    "依次执行静态检查、目标用例复测、关联回归和需求证据检查。",
    "根据成功、回归、Token、耗时和重试计算奖励并更新A_(a_t)与b_(a_t)。",
    "验证通过则提交候选补丁；否则回退并选择下一策略，达到阈值后转人工。",
])

heading(doc, "4.6.2 时间与空间复杂度", 3)
body(doc, "设上下文维度为d，修复策略数为K。独立臂LinUCB若直接计算矩阵逆，每次选择的复杂度约为O(Kd^3)；通过缓存逆矩阵并采用Sherman-Morrison更新，可将单次更新降低到O(d^2)，选择阶段约为O(Kd^2)。模型存储复杂度为O(Kd^2)。在实际系统中，修复执行和回归测试耗时通常远大于Bandit计算，因此优化重点应是减少无效策略尝试和控制回归范围。")

heading(doc, "4.7 实验设计与阶段性结果", 2)
heading(doc, "4.7.1 故障集与对比方法", 3)
body(doc, "实验应构建同时包含受控故障和真实浏览器故障的测试集。受控故障用于覆盖定位器、超时、断言、测试数据、语法和依赖六类问题，并控制上下文难度；真实故障通过修改页面结构、属性、加载方式和测试数据产生，保留执行日志、DOM快照和原始补丁。每类故障至少包含多个上下文实例，避免算法只记住错误标签。")
table(doc, ["对比策略", "特点", "比较目的"], [
    ["随机策略", "在可用策略中随机选择", "提供下界"],
    ["固定规则", "错误类型映射到固定策略", "评价上下文建模价值"],
    ["ε greedy", "主要利用历史均值并随机探索", "比较简单在线学习"],
    ["UCB1", "无上下文的上置信界", "评价上下文信息贡献"],
    ["全量LLM", "所有故障均调用LLM局部重写", "评价成本和回归风险"],
    ["普通LinUCB", "使用上下文但不惩罚资源成本", "评价成本敏感奖励"],
    ["本文方法", "上下文、成本奖励、可用掩码和隔离回归", "综合评价"],
    ["Oracle", "预先知道每个实例的最佳策略", "提供可达上界"],
], [3.0, 7.0, 5.0])

heading(doc, "4.7.2 评价指标与消融实验", 3)
body(doc, "核心指标包括修复成功率、目标复测通过率、关联回归通过率、错误修改率、LLM调用率、平均Token、平均修复时间、平均尝试次数、平均奖励和累计后悔值。若只报告修复成功率，就可能掩盖全量LLM通过高成本重试获得成功的事实，也可能忽略修复引入的回归。")
body(doc, "消融实验分别移除DOM变化、脚本复杂度、历史反馈和成本估计特征，移除策略可用性掩码、成本惩罚或关联回归，并改变探索系数α。冷启动实验使用无历史、少量历史和完整历史三种设置，跨项目实验检验从一个被测系统学习的参数能否迁移到另一系统。所有策略面对相同故障序列并使用配对统计检验。")

heading(doc, "4.7.3 阶段性证据与有效性边界", 3)
body(doc, "现有受控实验中，成本敏感LinUCB的修复成功率为76.23%，固定规则为70.94%，全量LLM为70.90%；平均奖励分别为0.367、0.341和0.142。相较全量LLM，LinUCB将LLM调用率由100%降低到62.84%。真实浏览器故障注入已经完成一例locator strict mode冲突的诊断、规则修复和回归复测。")
body(doc, "阶段性结果说明上下文与成本反馈具有进一步验证价值，但当前受控实验中的部分策略成功概率由模拟模型定义，真实浏览器验证的故障类型和样本数量仍不足；主流水线中的HealingAgent尚需确保使用成本敏感LinUCB替换旧版HSS Bandit，并持久化真实上下文、策略选择和奖励。正式论文必须补充六类真实故障、多随机种子重复、跨系统验证和统计显著性分析。")

heading(doc, "4.8 本章小结", 2)
body(doc, "本章提出了基于成本敏感LinUCB的Web测试脚本自愈策略选择方法。该方法融合故障诊断、页面变化、脚本结构、历史反馈和成本估计构建上下文表示，在可用策略集合中平衡预期收益与探索价值，并通过修复成功、回归安全和资源成本构成的奖励在线更新策略。隔离补丁、目标复测、关联回归、证据检查和失败回退共同保证算法选择不会直接转化为不可控的代码覆盖。")

heading(doc, "两章之间的衔接关系", 1)
body(doc, "第三章和第四章分别作用于测试生命周期的两个决策阶段。第三章位于测试用例生成到代码生成之间，控制“当前结果能否进入后续环节以及下一轮修改什么”；第四章位于脚本执行失败到补丁提交之间，控制“当前故障应该采用什么修复策略以及修复结果能否被接受”。前者采用深度强化学习处理多轮序列控制，后者采用上下文Bandit处理在线单步选择，两者共享质量约束、成本建模、失败退出和可追溯反馈思想。")
body(doc, "两章的工程接口也应保持一致：状态与上下文均来自可观测运行数据，策略输出均经过安全层约束，执行结果均回写为可复现轨迹。这样，论文贡献不再是若干技术组件的并列堆叠，而是围绕生成控制和修复选择两个研究问题形成完整方法链。")

for p in doc.paragraphs:
    p.paragraph_format.widow_control = True

doc.core_properties.title = "毕业论文第三章第四章详细正文初稿"
doc.core_properties.subject = TITLE
doc.core_properties.keywords = "安全约束PPO LinUCB 多智能体 Web自动化测试 自愈"
doc.core_properties.author = ""
doc.core_properties.last_modified_by = ""

doc.save(OUTPUT)
print(OUTPUT.resolve())
