"""实验入口 — 完整实验 + 消融实验 + RL 对比实验 + 自动出图"""
import json
import sys
from pathlib import Path
from typing import Dict

# 将项目根目录加入 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from framework.rag import DocumentParser, SemanticChunker, Retriever
from framework.multi_agent import Coordinator, CaseCreator
from experiments.evaluation import Evaluator
from config import REQUIREMENTS_DIR, RESULTS_DIR, GROUND_TRUTH_FILE, \
    EXPERIMENT_MODULES


def experiment_full():
    """完整实验：RAG + 多智能体博弈（RL 模式）"""
    print("=" * 60)
    print("  实验: 完整流程 (RAG + 多智能体博弈 + RL-AGS)")
    print("=" * 60)

    # 1. RAG
    print("\n[1/4] 构建 RAG 检索索引...")
    parser = DocumentParser()
    chunker = SemanticChunker(parser)
    chunks = chunker.create_chunks(str(REQUIREMENTS_DIR))
    print(f"  语义切片: {len(chunks)} 个")

    retriever = Retriever()
    retriever.build_index(chunks)

    stats = chunker.chunk_stats(chunks)
    print(f"  切片统计: {stats}")

    # 2. 多智能体博弈（RL 模式）
    print("\n[2/4] 多智能体博弈用例生成 (RL-AGS)...")
    all_cases = []

    for module in EXPERIMENT_MODULES:
        print(f"\n--- 模块: {module} ---")
        req_chunks = retriever.retrieve_by_module(module)
        if not req_chunks:
            print(f"  [跳过] 未找到 {module} 的需求切片")
            continue

        coordinator = Coordinator(use_rl=True)
        result = coordinator.run(req_chunks, module)
        coordinator.print_summary(result)
        all_cases.extend(result["cases"])

    # 3. 评价
    print("\n[3/4] 计算评价指标...")
    evaluator = Evaluator(str(GROUND_TRUTH_FILE))
    all_chunks = [c.to_dict() if hasattr(c, 'to_dict') else c for c in chunks]

    results = {
        "coverage": evaluator.requirement_coverage(all_cases),
        "hallucination": evaluator.hallucination_rate(all_cases, all_chunks),
        "healing": {"total_attempts": 0, "successful": 0, "success_rate_pct": 0},
    }

    evaluator.print_report(results)

    # 4. 保存结果
    print("\n[4/4] 保存实验结果...")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "experiment_full.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  结果保存至: {output_path}")

    return results


def experiment_ablation():
    """消融实验（含 5 组对比）"""
    print("\n" + "=" * 60)
    print("  消融实验")
    print("=" * 60)

    parser = DocumentParser()
    chunks = SemanticChunker(parser).create_chunks(str(REQUIREMENTS_DIR))
    retriever = Retriever()
    retriever.build_index(chunks)

    evaluator = Evaluator(str(GROUND_TRUTH_FILE))
    all_chunks = [c.to_dict() if hasattr(c, 'to_dict') else c for c in chunks]

    # ---- 实验 A: 有 Auditor ----
    print("\n[实验 A] 有 Auditor 博弈")
    all_cases_a = []
    iterations_a = 0
    for module in EXPERIMENT_MODULES:
        req_chunks = retriever.retrieve_by_module(module)
        if req_chunks:
            coordinator_a = Coordinator(use_rl=False)
            result = coordinator_a.run(req_chunks, module)
            iterations_a += result.get("total_iterations", 0)
            all_cases_a.extend(result["cases"])
    coverage_a = evaluator.requirement_coverage(all_cases_a)
    hallucination_a = evaluator.hallucination_rate(all_cases_a, all_chunks)

    # ---- 实验 B: 无 Auditor ----
    print("\n[实验 B] 无 Auditor（直接生成）")
    creator = CaseCreator()
    all_cases_b = []
    for module in EXPERIMENT_MODULES:
        req_chunks = retriever.retrieve_by_module(module)
        if req_chunks:
            cases = creator.generate(req_chunks, module)
            all_cases_b.extend(cases)
    coverage_b = evaluator.requirement_coverage(all_cases_b)
    hallucination_b = evaluator.hallucination_rate(all_cases_b, all_chunks)

    # ---- 实验 C: RL-AGS 模式 ----
    print("\n[实验 C] RL-AGS 自适应博弈")
    all_cases_c = []
    iterations_c = 0
    for module in ["login", "search"]:
        req_chunks = retriever.retrieve_by_module(module)
        if req_chunks:
            coordinator_c = Coordinator(use_rl=True)
            result = coordinator_c.run(req_chunks, module)
            iterations_c += result.get("total_iterations", 0)
            all_cases_c.extend(result["cases"])
    coverage_c = evaluator.requirement_coverage(all_cases_c)
    hallucination_c = evaluator.hallucination_rate(all_cases_c, all_chunks)

    # 计算对比
    ablation = evaluator.compare_ablation(
        coverage_a, coverage_b, "with_auditor", "without_auditor"
    )

    rl_comparison = evaluator.compare_strategies(
        {"coverage_pct": coverage_a["coverage_pct"],
         "hallucination_pct": hallucination_a["hallucination_pct"],
         "total_iterations": iterations_a},
        {"coverage_pct": coverage_c["coverage_pct"],
         "hallucination_pct": hallucination_c["hallucination_pct"],
         "total_iterations": iterations_c},
    )

    print(f"\n=== 消融实验结论 ===")
    print(f"  有 Auditor vs 无 Auditor:")
    print(f"    覆盖率提升: {ablation['improvement']['coverage_improvement']}%")
    print(f"    幻觉率降幅: {ablation['improvement']['hallucination_reduction']}%")
    print(f"  RL-AGS vs 固定轮次:")
    print(f"    覆盖率: RL={coverage_c['coverage_pct']}% vs 固定={coverage_a['coverage_pct']}%")

    result = {
        "with_auditor": {"coverage": coverage_a, "hallucination": hallucination_a},
        "without_auditor": {"coverage": coverage_b, "hallucination": hallucination_b},
        "rl_ags": {"coverage": coverage_c, "hallucination": hallucination_c},
        "ablation": ablation,
        "rl_comparison": rl_comparison,
    }

    # 保存结果
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "experiment_ablation.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n消融实验结果保存至: {output_path}")

    # 生成对比图表
    _plot_ablation(result, str(RESULTS_DIR / "ablation_chart.png"))

    return result


def experiment_rl_comparison():
    """RL 对比实验：固定轮次 vs RL-AGS（带训练曲线）"""
    print("\n" + "=" * 60)
    print("  RL 对比实验")
    print("=" * 60)

    # 1. 训练 RL-AGS 模型
    print("\n[1/3] 训练 RL-AGS 模型...")
    from framework.rl import AGSTrainer
    trainer = AGSTrainer()
    trainer.train(total_timesteps=5000)
    model_path = trainer.save()
    print(f"  模型训练完成: {model_path}")

    # 2. 对比固定轮次 vs RL
    print("\n[2/3] 运行对比实验...")
    parser = DocumentParser()
    chunks = SemanticChunker(parser).create_chunks(str(REQUIREMENTS_DIR))
    retriever = Retriever()
    retriever.build_index(chunks)
    evaluator = Evaluator(str(GROUND_TRUTH_FILE))

    fixed_results = {}
    rl_results = {}

    for module in ["login", "search"]:
        req_chunks = retriever.retrieve_by_module(module)

        # 固定 3 轮
        coord_fixed = Coordinator(use_rl=False)
        r_fixed = coord_fixed.run(req_chunks, module)
        fixed_results[module] = {
            "iterations": r_fixed["total_iterations"],
            "num_cases": len(r_fixed["cases"]),
        }

        # RL-AGS
        coord_rl = Coordinator(use_rl=True)
        r_rl = coord_rl.run(req_chunks, module)
        rl_results[module] = {
            "iterations": r_rl["total_iterations"],
            "num_cases": len(r_rl["cases"]),
        }

        print(f"\n  {module}: 固定={r_fixed['total_iterations']}轮 "
              f"vs RL={r_rl['total_iterations']}轮")

    # 3. 生成报告
    print("\n[3/3] 生成实验结果...")
    comparison = {
        "fixed": fixed_results,
        "rl_ags": rl_results,
        "summary": {
            "fixed_total_iterations": sum(r["iterations"] for r in fixed_results.values()),
            "rl_total_iterations": sum(r["iterations"] for r in rl_results.values()),
        }
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "experiment_rl.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
    print(f"  RL 实验结果保存至: {output_path}")

    # 画对比图
    _plot_rl_comparison(comparison, str(RESULTS_DIR / "rl_comparison_chart.png"))

    return comparison


def experiment_healing_demo():
    """自愈实验：构造 strict-mode 定位器失败并验证自动修复。"""
    print("\n" + "=" * 60)
    print("  自愈实验: Playwright strict-mode locator")
    print("=" * 60)

    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/run_healing_demo.py"],
        cwd=Path(__file__).parent.parent,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("自愈实验失败")

    output_path = RESULTS_DIR / "healing_demo.json"
    with open(output_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _plot_ablation(data: Dict, save_path: str):
    """绘制消融实验对比柱状图"""
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        matplotlib.rcParams['axes.unicode_minus'] = False

        labels = ['有 Auditor', '无 Auditor', 'RL-AGS']
        coverage = [
            data.get("with_auditor", {}).get("coverage", {}).get("coverage_pct", 0),
            data.get("without_auditor", {}).get("coverage", {}).get("coverage_pct", 0),
            data.get("rl_ags", {}).get("coverage", {}).get("coverage_pct", 0),
        ]
        hallucination = [
            data.get("with_auditor", {}).get("hallucination", {}).get("hallucination_pct", 0),
            data.get("without_auditor", {}).get("hallucination", {}).get("hallucination_pct", 0),
            data.get("rl_ags", {}).get("hallucination", {}).get("hallucination_pct", 0),
        ]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        x = range(len(labels))

        ax1.bar(x, coverage, color=['#2ecc71', '#95a5a6', '#3498db'], width=0.5)
        ax1.set_xticks(list(x))
        ax1.set_xticklabels(labels)
        ax1.set_ylabel('覆盖率 (%)')
        ax1.set_title('需求覆盖率对比')
        for i, v in enumerate(coverage):
            ax1.text(i, v + 1, f'{v:.1f}%', ha='center')

        ax2.bar(x, hallucination, color=['#e74c3c', '#f39c12', '#9b59b6'], width=0.5)
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(labels)
        ax2.set_ylabel('幻觉率 (%)')
        ax2.set_title('幻觉率对比')
        for i, v in enumerate(hallucination):
            ax2.text(i, v + 1, f'{v:.1f}%', ha='center')

        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        print(f"  消融实验对比图: {save_path}")
        plt.close()

    except ImportError as e:
        print(f"  [跳过出图] matplotlib 不可用: {e}")


def _plot_rl_comparison(data: Dict, save_path: str):
    """绘制 RL 对比图"""
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        matplotlib.rcParams['axes.unicode_minus'] = False

        modules = list(data.get("fixed", {}).keys())
        fixed_iters = [data["fixed"][m]["iterations"] for m in modules]
        rl_iters = [data["rl_ags"][m]["iterations"] for m in modules]

        fig, ax = plt.subplots(figsize=(8, 5))
        x = range(len(modules))
        width = 0.35

        ax.bar([i - width/2 for i in x], fixed_iters, width,
               label='固定轮次', color='#95a5a6')
        ax.bar([i + width/2 for i in x], rl_iters, width,
               label='RL-AGS', color='#3498db')

        ax.set_xticks(list(x))
        ax.set_xticklabels(modules)
        ax.set_ylabel('迭代轮次')
        ax.set_title('固定轮次 vs RL-AGS 迭代次数对比')
        ax.legend()

        for i, (f, r) in enumerate(zip(fixed_iters, rl_iters)):
            ax.text(i - width/2, f + 0.1, str(f), ha='center', va='bottom')
            ax.text(i + width/2, r + 0.1, str(r), ha='center', va='bottom')

        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        print(f"  RL 对比图: {save_path}")
        plt.close()

    except ImportError as e:
        print(f"  [跳过出图] matplotlib 不可用: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="实验运行器")
    parser.add_argument("--type", choices=["full", "ablation", "rl", "healing", "all"],
                        default="all", help="实验类型")
    args = parser.parse_args()

    if args.type in ("full", "all"):
        experiment_full()
    if args.type in ("ablation", "all"):
        experiment_ablation()
    if args.type in ("rl", "all"):
        experiment_rl_comparison()
    if args.type in ("healing", "all"):
        experiment_healing_demo()
