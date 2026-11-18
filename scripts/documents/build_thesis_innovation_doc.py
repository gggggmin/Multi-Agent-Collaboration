from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


THESIS_TITLE = "基于安全约束PPO和成本敏感LinUCB的多智能体Web自动化测试生成与自愈研究"
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "thesis" / "drafts" / f"{THESIS_TITLE}.docx"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=110, start=120, bottom=110, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
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


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_col_width(cell, width_cm):
    cell.width = Cm(width_cm)
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(int(width_cm * 567)))
    tc_w.set(qn("w:type"), "dxa")


def set_font(run, latin="Times New Roman", east_asia="宋体", size=Pt(11), bold=None):
    run.font.name = latin
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), latin)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), latin)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), east_asia)
    run.font.size = size
    run.font.color.rgb = RGBColor(0, 0, 0)
    if bold is not None:
        run.bold = bold


def configure_styles(doc):
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
    title.paragraph_format.space_after = Pt(18)
    title.paragraph_format.line_spacing = 1.2
    title_ppr = title._element.get_or_add_pPr()
    title_border = title_ppr.find(qn("w:pBdr"))
    if title_border is not None:
        title_ppr.remove(title_border)

    for name, size, before, after, font_name in (
        ("Heading 1", 16, 18, 10, "黑体"),
        ("Heading 2", 14, 14, 8, "黑体"),
        ("Heading 3", 12, 10, 6, "黑体"),
    ):
        style = styles[name]
        style.font.name = font_name
        style._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.first_line_indent = Cm(0)


def add_page_number(section):
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(3)
    run = p.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = " PAGE "
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr_text)
    run._r.append(fld_char2)
    set_font(run, size=Pt(9))


def body(doc, text, bold_lead=None, indent=True, keep=False):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.first_line_indent = Cm(0.74) if indent else Cm(0)
    p.paragraph_format.keep_together = keep
    if bold_lead and text.startswith(bold_lead):
        r1 = p.add_run(bold_lead)
        set_font(r1, east_asia="黑体", bold=True)
        r2 = p.add_run(text[len(bold_lead):])
        set_font(r2)
    else:
        r = p.add_run(text)
        set_font(r)
    return p


def bullet(doc, text, level=0):
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    p.paragraph_format.left_indent = Cm(0.74 + level * 0.55)
    p.paragraph_format.first_line_indent = Cm(-0.35)
    p.paragraph_format.line_spacing = 1.4
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    set_font(r)
    return p


NUMBER_COUNTER = 0


def reset_numbering():
    global NUMBER_COUNTER
    NUMBER_COUNTER = 0


def numbered(doc, text):
    global NUMBER_COUNTER
    NUMBER_COUNTER += 1
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.8)
    p.paragraph_format.first_line_indent = Cm(-0.4)
    p.paragraph_format.line_spacing = 1.4
    p.paragraph_format.space_after = Pt(5)
    r = p.add_run(f"{NUMBER_COUNTER}. {text}")
    set_font(r)
    return p


def equation(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_together = True
    r = p.add_run(text)
    set_font(r, latin="Cambria Math", east_asia="Cambria Math", size=Pt(11))
    r.italic = True
    return p


def add_table(doc, headers, rows, widths):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.style = "Table Grid"
    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    for i, text in enumerate(headers):
        cell = hdr.cells[i]
        set_col_width(cell, widths[i])
        set_cell_shading(cell, "1F4E78")
        set_cell_margins(cell)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(str(text))
        set_font(r, east_asia="黑体", size=Pt(9.5), bold=True)
        r.font.color.rgb = RGBColor(255, 255, 255)
    for row_idx, values in enumerate(rows):
        cells = table.add_row().cells
        for i, value in enumerate(values):
            set_col_width(cells[i], widths[i])
            set_cell_margins(cells[i])
            cells[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            if row_idx % 2 == 1:
                set_cell_shading(cells[i], "F2F6FA")
            p = cells[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if i > 0 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.2
            r = p.add_run(str(value))
            set_font(r, size=Pt(9.2))
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return table


def page_break(doc):
    p = doc.add_paragraph()
    p.add_run().add_break(WD_BREAK.PAGE)


def add_heading(doc, text, level):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.keep_with_next = True
    return p


doc = Document()
section = doc.sections[0]
section.page_width = Cm(21.0)
section.page_height = Cm(29.7)
section.top_margin = Cm(2.5)
section.bottom_margin = Cm(2.3)
section.left_margin = Cm(2.8)
section.right_margin = Cm(2.5)
section.header_distance = Cm(1.2)
section.footer_distance = Cm(1.2)
configure_styles(doc)
add_page_number(section)

# Cover
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(76)
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("硕士毕业论文研究方案")
set_font(r, east_asia="黑体", size=Pt(16), bold=True)

title = doc.add_paragraph(style="Title")
title.add_run(THESIS_TITLE)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(12)
r = p.add_run("两项核心创新详细论述与章节规划")
set_font(r, east_asia="宋体", size=Pt(13))

p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(92)
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("文档性质  论文创新章节写作底稿")
set_font(r, east_asia="宋体", size=Pt(11))
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("形成日期  2026 年 11 月 4 日")
set_font(r, east_asia="宋体", size=Pt(11))

page_break(doc)

add_heading(doc, "文档说明", 1)
body(doc, "本文件用于确定毕业论文的研究主线、两项核心创新的技术内涵、各自可拆分的子创新、实验验证方法以及工程系统章节的边界。建议论文不要把 RAG、多智能体、PPO、LinUCB、Playwright 等现成技术分别包装成创新，而应围绕两个明确的决策问题展开：生成阶段如何在质量与成本之间安全地选择下一步动作，执行失败后如何根据故障上下文选择高收益且成本可控的修复策略。")
body(doc, "核心结论是：论文应以“证据约束的安全自适应测试生成控制方法”和“成本敏感的上下文自愈策略选择方法”为两项主要创新，每项创新分别形成独立方法章节，并拆解为三个相互支撑的子创新。完整工程框架只承担算法承载、数据采集和闭环验证功能，集中写入一章，不与算法贡献抢叙事中心。")

add_heading(doc, "建议论文题目", 2)
body(doc, f"首选题目：{THESIS_TITLE}。")
body(doc, "备选题目一：基于Safe PPO与LinUCB的需求驱动Web测试生成和自愈方法研究。")
body(doc, "备选题目二：基于近端策略优化与上下文多臂老虎机的Web自动化测试生成及修复研究。")
body(doc, "题目中的安全约束PPO对应生成阶段的RL-AGS决策算法，成本敏感LinUCB对应执行失败后的在线修复策略选择算法；多智能体Web自动化测试限定了研究对象，测试生成与自愈概括两项核心任务。")

add_heading(doc, "先用大白话看懂两个创新", 2)
body(doc, "整个系统先根据需求生成测试用例，再把用例转换为可执行脚本，最后用浏览器运行脚本。两个创新并不负责所有环节，而是分别安放在两个最需要做选择的位置：创新一放在“生成—审查”循环里，决定当前结果能不能收、下一轮具体改什么；创新二放在“执行失败—自动修复”流程里，决定当前故障应该用哪种修复策略。")
body(doc, "完整位置可以概括为：需求文档 → 检索需求证据 → Creator生成用例 → Auditor审查 →【创新一：安全约束PPO决策】→ 通过后生成代码 → Playwright执行 → 失败诊断 →【创新二：成本敏感LinUCB选修复策略】→ 隔离修复与回归验证。")

add_heading(doc, "创新一到底用了什么算法", 3)
body(doc, "创新一使用PPO，即近端策略优化算法，并在PPO外增加确定性的安全约束层，因此文中称为安全约束PPO。PPO本质上是一个根据当前状态选择动作的强化学习算法。它不直接写测试用例，而是控制Creator和Auditor要不要继续迭代，以及下一轮采用哪一种修改动作。")
add_table(
    doc,
    ["算法要素", "在本项目中的具体含义"],
    [
        ["输入状态", "当前轮次、需求覆盖率、审查问题数、严重问题数、幻觉率、覆盖提升量、脚本通过率和累计调用成本"],
        ["可选动作", "接受当前用例、针对覆盖遗漏进行修订、针对幻觉或逻辑问题进行修订、刷新需求证据后重新生成"],
        ["奖励信号", "覆盖率和通过率提高获得奖励；严重错误、幻觉、不安全接受、模型调用和重复轮次受到惩罚"],
        ["安全约束", "只要存在严重问题、覆盖率未达阈值或证据不一致，即使PPO选择接受，也强制改为继续修订"],
        ["最终输出", "通过质量闸门的测试用例，以及可追踪的停止或修订决策记录"],
    ],
    [3.0, 12.0],
)
body(doc, "它解决的是固定迭代轮次的笨办法。固定三轮会让简单需求白跑两轮，也可能让复杂需求三轮后仍带着严重错误结束。安全约束PPO根据每轮质量变化动态决策：简单任务可以提前停止，复杂任务继续定向修改，同时禁止不合格结果被提前接受。预期提升包括需求覆盖率、证据一致性和合格用例比例，并降低平均迭代轮次、模型调用次数、Token成本和不安全接受率。")

add_heading(doc, "创新二到底用了什么算法", 3)
body(doc, "创新二使用LinUCB，即线性上置信界上下文多臂老虎机，并把修复成本写入奖励，因此称为成本敏感LinUCB。它也不直接修改所有代码，而是在脚本失败后，根据故障上下文从多个修复策略中选择当前最值得尝试的一种。")
add_table(
    doc,
    ["算法要素", "在本项目中的具体含义"],
    [
        ["输入上下文", "错误类型、定位器类型、DOM变化程度、候选元素数、脚本复杂度、重试次数、历史成功率和预计修复成本"],
        ["候选策略臂", "定位器规则修复、等待条件调整、断言修复、测试数据重置、LLM局部重写和回退或转人工"],
        ["选择原则", "综合当前上下文下的预计成功收益和对未知策略的探索价值，选择LinUCB得分最高的可用策略"],
        ["成本反馈", "目标用例通过和回归通过获得奖励；修复失败、引入回归、耗时、重试和LLM Token形成惩罚"],
        ["安全闭环", "修复先在隔离副本中执行，只有目标故障消失且关联回归未退化才接受，否则回退"],
    ],
    [3.0, 12.0],
)
body(doc, "它解决的是两种极端做法：一种是所有故障都按固定规则修，遇到复杂页面就修不动；另一种是所有故障都交给大模型重写，费用高，还可能把原本正确的断言改坏。成本敏感LinUCB会逐步学习“什么故障适合什么修法”，优先使用低成本且成功率高的策略，必要时才调用LLM。预期提升包括修复成功率、回归通过率和平均奖励，同时降低LLM调用率、平均修复成本、修复时延和错误修改风险。")
body(doc, "现有受控实验中，成本敏感LinUCB的修复成功率为76.23%，高于固定规则的70.94%和全量LLM的70.90%；平均奖励为0.367，高于固定规则的0.341和全量LLM的0.142；相对全量LLM，调用率由100%降至62.84%。但这些结果主要来自受控故障模型，正式论文仍需补充多类真实浏览器故障和统计检验，不能把模拟成绩吹成真实生产结论。")

add_heading(doc, "两项核心创新总览", 2)
add_table(
    doc,
    ["主创新", "解决的问题", "三个子创新", "核心评价指标"],
    [
        ["创新一", "固定轮次和无约束策略无法兼顾生成质量、需求依据与调用成本", "结构化质量状态；细粒度动作与安全投影；质量成本联合奖励和失败隔离", "审计通过率、不安全接受率、覆盖率、幻觉率、迭代轮次、Token 和耗时"],
        ["创新二", "固定修复映射缺少场景适应性，而全量 LLM 修复成本高且可能引入回归", "故障上下文编码；成本敏感 LinUCB 在线选择；隔离修复与回归反馈闭环", "修复成功率、回归通过率、LLM 调用率、平均成本、平均奖励、累计后悔值"],
    ],
    [2.4, 4.2, 6.0, 3.8],
)

structure_heading = add_heading(doc, "推荐章节结构", 2)
structure_heading.paragraph_format.page_break_before = True
add_table(
    doc,
    ["章节", "核心内容", "写作定位"],
    [
        ["第 1 章", "绪论、研究背景、问题定义、研究内容与贡献", "提出两个研究问题，不提前堆实现细节"],
        ["第 2 章", "相关理论与研究现状", "覆盖需求驱动测试、多智能体生成、安全强化学习、自愈测试与上下文 Bandit"],
        ["第 3 章", "证据约束的安全自适应测试生成控制方法", "创新一的完整方法、算法、消融和本章实验"],
        ["第 4 章", "成本敏感的上下文自愈策略选择方法", "创新二的完整方法、算法、消融和本章实验"],
        ["第 5 章", "多智能体自动化测试框架设计与工程实现", "只写架构、模块、数据流、接口与工程闭环"],
        ["第 6 章", "综合实验与系统评估", "跨系统复现、端到端成本、真实浏览器故障和总体有效性"],
        ["第 7 章", "总结与展望", "回答研究问题并如实说明边界"],
    ],
    [2.1, 7.0, 7.3],
)

page_break(doc)

# Innovation 1
add_heading(doc, "第一项核心创新 证据约束的安全自适应测试生成控制方法", 1)

add_heading(doc, "1 研究问题与方法定位", 2)
body(doc, "自然语言需求经过大语言模型转换为测试用例时，输出质量具有明显不确定性。测试用例可能遗漏需求点、缺少边界场景、引入需求外行为，或者在描述上看似完整但无法追溯到有效需求证据。传统固定轮次方法对所有需求采用同样的迭代次数，简单需求会产生不必要调用，复杂需求又可能在质量不足时被迫结束。单纯使用 PPO 等学习策略也不能提供确定性安全保证，因为策略在探索或分布外状态下仍可能错误选择接受。")
body(doc, "本方法研究的不是“如何让 PPO 生成测试文本”，而是“如何控制 Creator 与 Auditor 的多轮协作”。Creator 负责生成或修订用例，Auditor 输出结构化质量反馈，决策层根据当前质量状态选择接受、补覆盖、修一致性、补边界或刷新证据。学习策略负责效率，确定性安全约束负责底线，两者分工明确。")

add_heading(doc, "2 总体方法", 2)
body(doc, "在第 t 轮生成和审计后，将需求证据、测试用例和审计结果转换为质量状态 s_t。策略网络提出候选动作 a_t，安全层根据当前状态计算允许动作集合 A_safe(s_t)。若候选动作不满足安全条件，则将其投影到与当前缺陷最相关的修订动作；执行修订后进入下一轮，直到安全接受或达到最大轮次失败。")
equation(doc, "s_t = [i_t, e_t, w_t, h_t, c_t, Δc_t, q_t, k_t]")
body(doc, "其中，i_t 表示当前轮次，e_t 和 w_t 分别表示严重错误与警告数量，h_t 表示幻觉问题数量，c_t 表示需求覆盖率，Δc_t 表示覆盖率增量，q_t 表示证据一致性，k_t 表示累计调用成本。该状态不是为了追求特征数量，而是要同时回答三个问题：当前结果是否正确，继续修订可能获得多少质量收益，以及继续修订需要付出多少成本。")

add_heading(doc, "3 子创新一 需求证据与审计反馈驱动的结构化质量状态", 2)
body(doc, "第一个子创新是把原本分散在自然语言需求、生成用例和 Auditor 评论中的信息，转换为可计算、可追踪、可用于决策的质量状态。常见多智能体系统只保留对话文本，策略无法稳定判断问题类型。本方法要求 Auditor 输出问题类别、严重程度、对应需求证据、受影响用例和建议修订方向，使决策层能够区分“需求遗漏”“需求外幻觉”“逻辑不一致”“边界不足”和“证据失配”。")

add_table(
    doc,
    ["状态维度", "计算来源", "决策作用"],
    [
        ["严重错误数", "Auditor 的 error 级问题", "存在严重错误时禁止接受"],
        ["幻觉数量", "用例与检索证据的可追溯性检查", "触发一致性修订或证据刷新"],
        ["需求覆盖率", "Ground Truth、需求点或语义映射", "判断是否需要补充用例"],
        ["覆盖率增量", "相邻两轮覆盖率差值", "判断继续迭代是否仍有收益"],
        ["证据一致性", "用例、断言与需求片段的语义匹配", "证据不足时禁止放行"],
        ["累计成本", "Token、调用次数、耗时和重试次数", "约束无效迭代"],
    ],
    [3.0, 6.0, 7.4],
)

body(doc, "这一子创新的研究价值在于建立了从生成文本到控制状态的中间表示。它让生成质量不再停留在“模型觉得不错”的主观描述，而是成为可训练、可比较和可审计的决策输入。论文中应重点说明状态字段的定义、归一化方法、缺失值处理和可追溯关系，而不是只给一张框架图。")

add_heading(doc, "4 子创新二 细粒度修订动作与证据约束的安全动作投影", 2)
body(doc, "第二个子创新是把动作空间从简单的“继续或停止”扩展为问题类型驱动的细粒度动作。二元动作只能决定要不要再来一轮，却不能决定下一轮应该解决什么问题，导致 Creator 可能重复生成、盲目补充或产生新的幻觉。细粒度动作使策略真正具备方向性。")

add_table(
    doc,
    ["动作", "适用状态", "预期效果"],
    [
        ["ACCEPT", "无严重错误、无幻觉、覆盖率和证据一致性达标", "结束生成并进入代码生成"],
        ["REVISE COVERAGE", "需求覆盖不足", "围绕缺失需求点补充用例"],
        ["REVISE CONSISTENCY", "存在错误、幻觉或冲突", "删除或修正无依据用例"],
        ["REVISE BOUNDARY", "主体场景完整但边界不足", "补充边界值、异常和逆向场景"],
        ["REFRESH EVIDENCE", "检索证据为空或一致性较低", "调整检索范围并重新构建上下文"],
    ],
    [4.0, 6.2, 6.2],
)

body(doc, "安全层不直接替代策略网络，而是在策略输出后执行动作约束。设策略提出动作 a_t，安全集合为 A_safe(s_t)。若 a_t 属于安全集合，则保留原动作；若不属于，则根据证据不足、幻觉、覆盖不足或边界不足等主导问题，将其投影到对应修订动作。")
equation(doc, "a'_t = a_t,  if a_t ∈ A_safe(s_t);   otherwise a'_t = Project(a_t, s_t)")
body(doc, "这种设计的核心不是“给 PPO 加一条规则”，而是把学习型效率优化与确定性质量保证分层。PPO 可以学习在安全范围内减少迭代，但无权突破质量底线。即使模型在训练不足、随机探索或分布外状态下提出 ACCEPT，安全层仍能阻止不合格用例进入后续代码生成。")

add_heading(doc, "5 子创新三 质量成本联合奖励与失败隔离机制", 2)
body(doc, "第三个子创新是将质量收益、风险惩罚和资源成本统一到奖励函数中，并把最大轮次耗尽定义为失败而不是默认接受。固定轮次系统最容易犯的错误，就是把“流程结束”偷换成“结果合格”。本方法将两者彻底分开：只有满足安全条件的接受才是成功，达到最大轮次仍不合格则返回 failed max iterations，并阻断代码生成。")
equation(doc, "R_t = λ_q · QualityGain_t - λ_r · Risk_t - λ_c · Cost_t")
body(doc, "质量收益包括覆盖率提升、错误减少、幻觉减少和证据一致性提高；风险惩罚包括不安全接受、严重错误和需求外行为；成本项包括模型调用、Token、耗时及重复轮次。权重需要通过敏感性实验分析，不能凭感觉拍脑袋。论文应报告在不同成本权重和安全阈值下，质量与成本如何变化。")

add_heading(doc, "6 算法流程", 2)
reset_numbering()
numbered(doc, "解析需求并构建可检索的语义证据集合。")
numbered(doc, "Creator 根据当前证据生成测试用例，Auditor 输出结构化问题和覆盖信息。")
numbered(doc, "根据审计结果构建质量状态，并计算允许动作集合。")
numbered(doc, "策略网络提出候选动作；安全层检查并在必要时进行动作投影。")
numbered(doc, "执行接受、定向修订或证据刷新，并记录质量变化与调用成本。")
numbered(doc, "满足安全接受条件时进入代码生成；超过最大轮次仍不合格时失败退出并转人工处理。")

add_heading(doc, "7 实验设计与评价", 2)
body(doc, "本章实验必须围绕“安全性是否提高”和“为安全性付出的成本是否合理”展开。建议基线包括固定 1 轮、固定 3 轮、固定 5 轮、审计阈值规则、原始 PPO、二动作 PPO 和本文方法。所有策略应面对同一组初始质量场景或真实生成轨迹，使用相同模型、提示词预算和终止上限。")
add_table(
    doc,
    ["实验类别", "具体设置", "需要回答的问题"],
    [
        ["主对比实验", "固定轮次、规则、原始 PPO、Safe PPO", "是否降低不安全接受并保持较高通过率"],
        ["状态消融", "去掉证据一致性、覆盖增量或成本字段", "哪些状态特征真正贡献决策能力"],
        ["动作消融", "退化为继续与接受二动作", "细粒度动作是否减少无效修订"],
        ["安全消融", "移除动作投影", "安全层是否提供确定性底线"],
        ["敏感性分析", "改变安全阈值、成本权重和最大轮次", "方法在质量成本权衡下是否稳定"],
        ["外部验证", "跨需求模块和跨被测系统测试", "能否超出单一标靶系统泛化"],
    ],
    [3.0, 7.1, 6.3],
)

add_heading(doc, "8 当前证据与结论边界", 2)
body(doc, "现有受控实验中，原始 PPO 的平均不安全接受率为 2.47%，证据约束 Safe PPO 为 0%；平均奖励由 26.815 提升到 28.766，平均成本由 2.302 降至 2.180。该结果支持安全动作投影在受控环境中有效，也说明学习策略本身不能替代确定性安全约束。")
body(doc, "但是，这些状态转移仍然来自受控环境，不是真实 Creator 与 Auditor 的大规模在线轨迹。因此论文当前可以表述为“验证了策略机制和安全性质”，不能直接表述为“已证明在任意真实需求中显著降低 LLM 成本”。正式论文应补充真实多轮生成轨迹、Token 与耗时记录、跨项目测试，以及与规则策略的显著性检验。")

add_heading(doc, "9 本章建议贡献表述", 2)
body(doc, "本文针对多智能体测试生成中质量状态不可计算、固定轮次缺乏适应性以及学习策略可能不安全接受的问题，提出一种证据约束的安全自适应生成控制方法。该方法构建需求证据与审计反馈驱动的结构化质量状态，设计问题类型驱动的细粒度修订动作，并通过安全动作投影与质量成本联合奖励，在保证不合格用例不进入代码生成的前提下优化生成迭代成本。")

# Innovation 2
chapter_heading = add_heading(doc, "第二项核心创新 成本敏感的上下文自愈策略选择方法", 1)
chapter_heading.paragraph_format.page_break_before = True

add_heading(doc, "1 研究问题与方法定位", 2)
body(doc, "自动化测试脚本会因页面元素变化、异步加载、业务断言变化、测试数据污染、语法或依赖问题而失效。不同故障需要不同修复方法：简单定位器变化适合低成本规则修复，复杂 DOM 重构可能需要 LLM 局部重写，数据污染更适合状态重置。固定的错误类型到策略映射无法区分同一类别中的细粒度上下文，而所有故障都调用 LLM 又会增加成本，并可能改坏原本正确的测试逻辑。")
body(doc, "本方法把自愈建模为带上下文的在线策略选择问题。每次故障发生后，系统提取错误类别、定位器类型、DOM 变化、脚本复杂度、重试次数、历史成功率和预计成本等特征；LinUCB 根据历史反馈估计各修复策略在当前上下文中的期望收益及不确定性；修复在隔离环境中执行，并以目标用例与回归用例的执行结果更新策略。")

add_heading(doc, "2 总体方法", 2)
body(doc, "设故障上下文向量为 x_t，策略集合为 A。每个策略 a 维护参数矩阵 A_a 和向量 b_a。系统根据历史观测估计参数 θ_a，并计算期望收益与探索上界。选择得分最高的策略后，在隔离副本中执行修复和回归测试，再根据成功、回归和成本计算奖励并更新对应策略。")
equation(doc, "score(a) = θ_aᵀ x_t + α √(x_tᵀ A_a⁻¹ x_t)")
body(doc, "第一项表示当前上下文下的预期修复收益，第二项表示对不确定策略的探索奖励，α 控制探索强度。与普通多臂老虎机相比，上下文 Bandit 能够区分“相同错误类别但不同页面变化程度、脚本复杂度和历史表现”的故障。")

add_heading(doc, "3 子创新一 多源故障信息融合的上下文编码", 2)
body(doc, "第一个子创新是设计面向自动化测试故障的上下文表示。仅使用错误类别会丢失关键差异，例如 locator 错误既可能来自元素文本变更，也可能来自多元素匹配、页面未加载或 DOM 大幅重构。上下文编码将离散诊断信息与连续工程特征结合，使算法能够学习“什么场景下哪种策略更合适”。")
page_break(doc)
add_table(
    doc,
    ["特征组", "示例字段", "影响"],
    [
        ["错误诊断", "locator、timeout、assertion、data、syntax、import", "限定候选策略和基础成功概率"],
        ["定位器信息", "CSS、文本、role、XPath、候选元素数量", "区分规则修复与语义重定位需求"],
        ["页面变化", "DOM 差异比例、元素属性变化、页面加载状态", "判断局部规则是否仍然可靠"],
        ["脚本特征", "代码长度、跳转数、断言数、依赖数量", "估计修复复杂度与回归风险"],
        ["历史反馈", "相似故障成功率、失败次数、最近奖励", "支持在线适应系统变化"],
        ["资源估计", "预计 Token、执行时间、重试成本", "避免为了成功率无脑选择高成本策略"],
    ],
    [3.0, 7.0, 6.4],
)
body(doc, "论文中应说明特征如何归一化、类别如何独热编码、缺失信息如何处理，以及哪些特征来自运行日志、DOM 快照和历史策略库。若特征只能在模拟器中生成而真实系统无法采集，就不能算完整落地，因此上下文编码必须和真实诊断器的数据接口保持一致。")

add_heading(doc, "4 子创新二 成本敏感的 LinUCB 在线修复策略选择", 2)
body(doc, "第二个子创新是在 LinUCB 的在线探索利用机制中显式加入修复成本。策略池可以包括定位器规则修复、等待条件调整、断言修复、测试数据重置、LLM 局部重写和回退。算法不追求单一成功率最大化，而是优化修复成功、回归安全与资源成本构成的综合收益。")
equation(doc, "R_t = r_success + r_regression - λ_cost · cost_t - λ_retry · retry_t")
body(doc, "其中，修复后目标用例通过获得主要正奖励，相关回归用例通过获得附加奖励；修复失败、引入回归或超过最大尝试次数受到惩罚；LLM Token、执行时间和重试次数构成成本项。通过调整成本权重，可以得到偏质量、均衡或偏成本的策略。")
body(doc, "这一设计的创新点不在于重新发明 LinUCB，而在于完成测试自愈问题的上下文建模、策略臂设计和可观测成本奖励，使成熟算法能够解决具体的软件测试决策问题。论文必须这样写，不能宣称“提出了 LinUCB 算法”，那属于给祖传菜谱改个盘子就说发明新菜，老师一问出处就露馅。")

add_heading(doc, "5 子创新三 隔离修复 回归验证 在线反馈的安全闭环", 2)
body(doc, "第三个子创新是把策略选择与工程验证组成可恢复的安全闭环。Bandit 选择策略并不意味着代码可以直接覆盖原脚本。修复必须先在隔离副本中完成语法检查和静态检查，再执行原失败用例与关联回归集。只有目标故障消失且回归未退化时，修复结果才被接受，奖励才作为正反馈更新策略。")
reset_numbering()
numbered(doc, "捕获标准输出、错误输出、Traceback、页面快照和运行上下文。")
numbered(doc, "诊断故障类别并构造上下文向量，过滤当前不可用或高风险策略。")
numbered(doc, "LinUCB 计算各策略得分，选择当前期望收益最高的可用策略。")
numbered(doc, "在隔离副本中执行修复，保存补丁、原始代码和修复记录。")
numbered(doc, "运行目标用例、相关回归集以及必要的静态检查。")
numbered(doc, "根据成功、回归、成本和尝试次数计算奖励；成功则提交候选补丁，失败则继续选择或回退。")
body(doc, "连续失败达到阈值时应停止自动修改并转人工处理。对于业务断言修改，必须能够追溯到需求证据，否则系统可能把真实缺陷“修复”成测试通过。这类伪自愈比脚本失败更危险，因为它会静默掩盖产品问题。")

add_heading(doc, "6 实验设计与评价", 2)
body(doc, "本章实验应同时评价修复质量、回归安全和资源成本。故障集至少覆盖定位器、超时、断言、测试数据、语法和导入六类，每类包含多个不同上下文实例。所有策略面对相同故障序列，并使用配对结果或固定随机种子减少实验噪声。")
add_table(
    doc,
    ["实验类别", "对比方法", "评价重点"],
    [
        ["策略主对比", "随机、固定规则、ε greedy、UCB1、全量 LLM、LinUCB、Oracle", "成功率、回归率、成本、奖励和后悔值"],
        ["上下文消融", "去掉 DOM、历史成功率、复杂度或成本特征", "上下文信息是否真正提高选择质量"],
        ["成本敏感性", "改变 LLM、执行时间和重试成本权重", "质量成本权衡是否可控"],
        ["冷启动实验", "无历史数据与少量历史数据", "在线学习初期是否稳定"],
        ["真实故障注入", "六类浏览器或脚本故障，多实例重复运行", "模拟优势能否迁移到真实执行环境"],
        ["跨项目实验", "不同技术栈和页面结构的被测系统", "上下文策略是否具备泛化能力"],
    ],
    [3.0, 7.2, 6.2],
)

add_heading(doc, "7 当前证据与结论边界", 2)
body(doc, "现有受控实验中，成本敏感 LinUCB 的修复成功率为 76.23%，固定规则为 70.94%，全量 LLM 为 70.90%；LinUCB 的平均奖励为 0.367，高于固定规则的 0.341 和全量 LLM 的 0.142。与全量 LLM 相比，LinUCB 将 LLM 调用率从 100% 降至 62.84%。真实浏览器故障注入已经验证一例 locator strict mode 冲突，系统完成了诊断、规则修复和回归复测。")
body(doc, "当前主要限制是受控实验中的策略成功概率由模拟模型定义，真实浏览器实验只有一种故障和一个代表性案例；此外，主流水线当前仍使用旧版 HSS Bandit，成本敏感 LinUCB 尚未成为实际 HealingAgent 的默认策略。正式论文必须完成算法接线，并补充六类真实故障、多次重复、跨系统验证和统计显著性分析。")

add_heading(doc, "8 本章建议贡献表述", 2)
body(doc, "本文针对固定自愈策略缺乏场景适应性以及全量大模型修复成本高、回归风险不可控的问题，提出一种成本敏感的上下文自愈策略选择方法。该方法融合故障诊断、页面变化、脚本复杂度和历史反馈构建上下文表示，利用 LinUCB 在线选择修复策略，并通过隔离修复、回归验证和成本反馈形成可恢复的闭环，在提高修复成功率的同时减少不必要的大模型调用。")

# Engineering chapter
chapter_heading = add_heading(doc, "工程化落地章节 多智能体自动化测试框架设计与实现", 1)
chapter_heading.paragraph_format.page_break_before = True

add_heading(doc, "1 本章定位", 2)
body(doc, "工程章节只负责回答两个问题：两项算法如何嵌入一个可运行系统，以及系统如何完成从需求到执行和自愈的闭环。不要把每一个目录、类和第三方库都写成创新。RAG、Page Object、Playwright、Pytest、向量数据库和命令行接口属于实现手段，写清楚架构取舍、接口和可复现性即可。")

add_heading(doc, "2 总体架构", 2)
add_table(
    doc,
    ["层次", "核心职责", "与创新的关系"],
    [
        ["输入与知识层", "解析需求、语义切片、建立索引和检索证据", "为创新一提供需求证据"],
        ["多智能体层", "Creator 生成、Auditor 审计、Coordinator 协调", "产生质量状态与修订反馈"],
        ["生成决策层", "Safe PPO、动作投影和质量闸门", "承载创新一"],
        ["代码生成与执行层", "生成 Page Object 和 Playwright 测试，沙箱执行", "连接方法与真实运行环境"],
        ["诊断与自愈层", "错误分类、LinUCB 策略选择、修复和回归", "承载创新二"],
        ["评价与实验层", "覆盖、幻觉、修复成功率、成本和实验记录", "提供可复现证据"],
    ],
    [3.0, 7.0, 6.4],
)

add_heading(doc, "3 完整业务流程", 2)
body(doc, "系统接收 Markdown 需求文档后进行语义切片和检索，Creator 根据检索证据生成正向、逆向和边界测试用例，Auditor 检查需求覆盖、幻觉和一致性。创新一根据质量状态决定接受、定向修订或刷新证据，通过质量闸门的用例进入 Page Object 与 Pytest Playwright 代码生成。执行器在隔离子进程中运行测试并采集日志。失败脚本进入诊断与自愈模块，创新二根据上下文选择修复策略，修复结果经过目标用例与回归验证后写入策略反馈。")

add_heading(doc, "4 工程实现重点", 2)
bullet(doc, "质量闸门：审计未通过且达到最大轮次的结果不得进入代码生成。")
bullet(doc, "执行隔离：显式管理工作目录、超时、标准输出、错误输出和 Pytest node id。")
bullet(doc, "可追溯记录：保存每轮生成、审计问题、决策来源、修复补丁、执行结果和实验配置。")
bullet(doc, "确定性降级：语义模型不可用时采用 TF IDF，保证 Windows 环境下可复现。")
bullet(doc, "修复可恢复：保留原脚本和补丁，失败时回退，避免直接覆盖有效代码。")
bullet(doc, "实验可复现：固定随机种子、共享评估场景、保存原始 JSON 结果和图表。")

add_heading(doc, "5 当前集成状态必须如实写", 2)
body(doc, "当前工程骨架已经打通需求解析、Creator Auditor、代码生成、浏览器执行、错误诊断、规则自愈和回归验证，现有单元测试可以验证质量闸门、安全生成环境和上下文 Bandit 的基础行为。但新算法与主流水线仍存在两处关键断点：Coordinator 默认使用旧版二动作 AGS，Safe PPO 主要运行在独立受控环境；HealingAgent 默认使用旧版 HSS Bandit，成本敏感 LinUCB 主要运行在独立基准实验。")
body(doc, "因此，工程章节不应声称两项创新已经全部在线化。论文提交前应完成统一接口、模型加载、上下文采集、奖励回写和持久化，并通过端到端测试证明实际调用链确实经过 Safe PPO 和 LinUCB。这个问题不解决，论文方法和系统实现就像两根平行铁轨，看着都挺直，就是火车开不过去。")

add_heading(doc, "6 工程章节建议目录", 2)
reset_numbering()
numbered(doc, "需求分析与系统目标。")
numbered(doc, "总体架构与关键数据流。")
numbered(doc, "需求知识库与多智能体协作模块。")
numbered(doc, "安全生成控制算法的系统接入。")
numbered(doc, "测试代码生成与隔离执行。")
numbered(doc, "上下文自愈算法的系统接入。")
numbered(doc, "日志、配置、结果存储与可复现性设计。")
numbered(doc, "系统功能验证与本章小结。")

# Writing and defense
chapter_heading = add_heading(doc, "论文写作与答辩口径", 1)
chapter_heading.paragraph_format.page_break_before = True

add_heading(doc, "1 可以明确主张的内容", 2)
bullet(doc, "提出面向测试生成审计反馈的结构化质量状态，而不是提出 RAG 或多智能体本身。")
bullet(doc, "提出细粒度修订动作、安全动作投影和质量成本联合控制机制，而不是提出 PPO 本身。")
bullet(doc, "提出面向测试自愈的上下文建模、策略池和成本敏感奖励，而不是提出 LinUCB 本身。")
bullet(doc, "实现从需求到浏览器执行、自愈和回归验证的系统闭环，作为两项方法的实验载体。")

add_heading(doc, "2 不应夸大的内容", 2)
bullet(doc, "不要把使用 AutoGen、ChromaDB、Playwright 或 Page Object Model 写成理论创新。")
bullet(doc, "不要用受控模拟结果证明真实大模型协作或真实浏览器环境中的普遍泛化。")
bullet(doc, "不要把 Ground Truth test id 命中率直接等同于语义正确率或真实缺陷发现率。")
bullet(doc, "不要把单个 locator 故障修复成功写成多故障类型大规模验证完成。")
bullet(doc, "不要声称 LinUCB 已经控制线上自愈流程，除非完成主流水线集成并保留运行轨迹。")

add_heading(doc, "3 两项创新之间的逻辑关系", 2)
body(doc, "两项创新不是彼此割裂的算法拼盘。创新一解决测试产生阶段的决策问题，目标是避免不合格用例进入代码生成；创新二解决测试执行后的决策问题，目标是在脚本失效时选择合理修复策略。前者控制“生成什么以及何时停止”，后者控制“失败后怎么修以及何时停止”。二者共享质量约束、成本建模、安全回退和在线反馈思想，共同构成需求驱动测试生命周期中的双阶段决策框架。")

add_heading(doc, "4 最小补强任务清单", 2)
add_table(
    doc,
    ["优先级", "任务", "完成标准"],
    [
        ["P0", "将 Safe PPO 接入 Coordinator", "真实运行轨迹记录五类动作、安全投影和终止原因"],
        ["P0", "将 LinUCB 接入 HealingAgent", "真实上下文编码、策略选择、成本奖励和模型持久化全部可追踪"],
        ["P0", "建立六类真实故障注入集", "每类至少 20 个实例并完成重复实验"],
        ["P1", "采集真实 Creator Auditor 多轮轨迹", "记录证据、用例、审计、动作、Token、耗时和质量变化"],
        ["P1", "增强评价指标", "加入语义覆盖、人工一致性、变异得分、APFD 和真实缺陷发现率"],
        ["P1", "增加跨系统验证", "至少两个被测系统达到同等级端到端复现"],
        ["P2", "完成统计分析", "报告多随机种子均值、方差、置信区间和效应量"],
    ],
    [1.7, 7.2, 7.5],
)

add_heading(doc, "结论", 1)
body(doc, "本论文最合理的研究结构，是用两章分别回答生成控制和修复选择两个核心决策问题，再用一章说明工程框架如何承载方法。第一项创新的核心是证据约束、安全动作投影和质量成本联合控制；第二项创新的核心是多源上下文编码、成本敏感在线选择和隔离回归反馈。工程项目不是第三项平级算法创新，而是验证两项方法真实性、可复现性和实际价值的实验平台。")
body(doc, "按这一结构推进，论文叙事会从“我做了很多模块”升级为“我定义了两个清晰问题，提出两套方法，并在统一系统中完成验证”。这才是硕士论文该有的骨架：主线少而硬，证据实而准，工程够用但不抢戏。")

# Global paragraph and table cleanup
for p in doc.paragraphs:
    if p.style.name == "Normal" and not p.text.strip():
        p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.widow_control = True

doc.core_properties.title = THESIS_TITLE
doc.core_properties.subject = "需求驱动 Web 自动化测试的安全生成与自适应修复"
doc.core_properties.keywords = "自动化测试 多智能体 安全强化学习 上下文多臂老虎机 自愈"
doc.core_properties.author = ""
doc.core_properties.last_modified_by = ""

doc.save(OUTPUT)
print(OUTPUT.resolve())
