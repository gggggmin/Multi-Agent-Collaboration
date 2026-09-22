#!/usr/bin/env python3
"""基于多智能体协同的需求驱动自动化测试生成与自愈方法研究 — 主入口"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from framework.rag import DocumentParser, SemanticChunker, Retriever
from framework.multi_agent import Coordinator, CaseCreator, AgentPipeline
from framework.code_gen import PageAgent, TestAgent
from framework.self_healing import SandboxExecutor, ErrorDiagnoser, HealingAgent
from experiments.evaluation import Evaluator
from config import REQUIREMENTS_DIR, GROUND_TRUTH_FILE, MAX_ITERATIONS


def cmd_rag(args):
    """RAG 模块：解析需求、构建索引"""
    print("=" * 50)
    print("  RAG 知识检索模块")
    print("=" * 50)

    parser = DocumentParser()
    chunker = SemanticChunker(parser)
    chunks = chunker.create_chunks(str(REQUIREMENTS_DIR))

    print(f"\n解析到 {len(chunks)} 个语义切片:")
    stats = chunker.chunk_stats(chunks)
    for module, count in stats["by_module"].items():
        print(f"  {module}: {count} 个切片")
    print(f"  类型分布: {stats['by_type']}")
    print(f"  平均切片长度: {stats['avg_chunk_length']} 字符")

    retriever = Retriever()
    retriever.build_index(chunks)

    if args.query:
        print(f"\n检索测试: query='{args.query}'")
        results = retriever.retrieve(args.query)
        for r in results:
            print(f"  [{r['metadata']['module']}] {r['metadata']['func_name']} (dist={r['distance']:.4f})")
            print(f"    {r['content'][:100]}...")

    return chunks


def cmd_generate(args):
    """多智能体博弈生成测试用例"""
    print("=" * 50)
    print("  多智能体博弈用例生成")
    print("=" * 50)

    # 先构建 RAG
    parser = DocumentParser()
    chunks = SemanticChunker(parser).create_chunks(str(REQUIREMENTS_DIR))
    retriever = Retriever()
    retriever.build_index(chunks)

    module = args.module or "login"
    req_chunks = retriever.retrieve_by_module(module)

    # 使用 RL-AGS 决策或固定轮次
    use_rl = not args.no_rl  # 默认使用 RL
    mode_name = "RL-AGS 自适应决策" if use_rl else "固定轮次"

    if args.no_auditor:
        print(f"[模式] 无 Auditor（直接生成）")
        creator = CaseCreator()
        cases = creator.generate(req_chunks, module)
        for c in cases:
            print(f"  [{c.get('type','?')}] {c.get('test_id','')}: {c.get('title','')}")
    else:
        print(f"[模式] Creator-Auditor 博弈 ({mode_name})")
        coordinator = Coordinator(use_rl=use_rl)
        result = coordinator.run(req_chunks, module)
        coordinator.print_summary(result)


def cmd_codegen(args):
    """生成测试脚本"""
    print("=" * 50)
    print("  测试脚本生成")
    print("=" * 50)

    page_agent = PageAgent()
    test_agent = TestAgent()

    sample_cases = [
        {"test_id": "TC-LOGIN-001", "module": "login", "title": "正确用户名密码登录",
         "steps": ["访问登录页", "输入用户名 testuser", "输入密码 password123", "点击登录"],
         "expected": "登录成功", "type": "正向"},
    ]

    pages = page_agent.generate(sample_cases, args.output)
    tests = test_agent.generate(sample_cases, pages, args.output)
    print(f"\n生成完成: {len(pages)} 个 Page Object, {len(tests)} 个测试文件")


def cmd_heal(args):
    """自愈测试"""
    print("=" * 50)
    print("  执行自愈模块（含 RL-HSS 策略选择）")
    print("=" * 50)

    executor = SandboxExecutor(args.dir)
    diagnoser = ErrorDiagnoser()
    healer = HealingAgent()

    exec_result = executor.run_script(args.script)
    print(f"执行结果: {'成功' if exec_result.get('success') else '失败'}")

    if not exec_result.get("success"):
        diagnosis = diagnoser.diagnose(exec_result)
        print(f"错误类型: {diagnosis['category']}")
        print(f"Traceback: {diagnosis['traceback'][:200]}")

        if args.fix:
            script_content = Path(args.script).read_text(encoding="utf-8")
            heal_result = healer.heal(script_content, diagnosis)
            if heal_result.get("fixed_code"):
                fix_path = args.script.replace(".py", "_fixed.py")
                Path(fix_path).write_text(heal_result["fixed_code"], encoding="utf-8")
                verify_result = executor.run_script(fix_path)
                heal_result["success"] = verify_result.get("success", False)
                healer.record_strategy_result(
                    heal_result.get("strategy", "unknown"),
                    heal_result.get("error_category", "unknown"),
                    heal_result["success"],
                )
                print(f"修复完成，策略: {heal_result.get('strategy', 'unknown')}")
                print(f"保存至: {fix_path}")
                print(f"二次验证: {'通过' if verify_result.get('success') else '失败'}")
            else:
                print("修复失败，所有策略均无效")


def cmd_pipeline(args):
    """运行完整智能体流水线"""
    print("=" * 50)
    print("  智能体实验流水线")
    print("=" * 50)

    pipeline = AgentPipeline(
        modules=args.module or None,
        use_rl=not args.no_rl,
        output_dir=args.output,
        execute_tests=args.execute,
        heal_failures=args.heal,
    )
    result = pipeline.run()

    metrics = result.get("metrics", {})
    coverage = metrics.get("coverage", {})
    hallucination = metrics.get("hallucination", {})
    healing = metrics.get("healing", {})

    print("\n流水线完成")
    print(f"  用例数: {result.get('num_cases', 0)}")
    print(f"  覆盖率: {coverage.get('coverage_pct', 'N/A')}%")
    print(f"  幻觉率: {hallucination.get('hallucination_pct', 'N/A')}%")
    print(f"  自愈成功率: {healing.get('success_rate_pct', 'N/A')}%")
    print(f"  结果文件: {result.get('result_path')}")

def cmd_train_rl(args):
    """训练 RL-AGS 模型"""
    print("=" * 50)
    print("  RL-AGS: 训练自适应博弈终止策略")
    print("=" * 50)

    from framework.rl import AGSTrainer

    trainer = AGSTrainer()
    result = trainer.train(total_timesteps=args.timesteps)
    trainer.save()
    print(f"\n训练完成！模型已保存至: {result['model_save_dir']}")


def cmd_experiment(args):
    """运行实验"""
    print("=" * 50)
    print("  实验运行")
    print("=" * 50)

    if args.type in ("full", "all"):
        from experiments.run_experiments import experiment_full
        experiment_full()

    if args.type in ("ablation", "all"):
        from experiments.run_experiments import experiment_ablation
        experiment_ablation()

    if args.type in ("rl", "all"):
        from experiments.run_experiments import experiment_rl_comparison
        experiment_rl_comparison()

    if args.type in ("healing", "all"):
        from experiments.run_experiments import experiment_healing_demo
        experiment_healing_demo()


def main():
    parser = argparse.ArgumentParser(
        description="基于多智能体协同的需求驱动自动化测试生成与自愈方法研究")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # RAG
    p_rag = subparsers.add_parser("rag", help="RAG 知识检索")
    p_rag.add_argument("--query", "-q", default="", help="检索查询")

    # 生成（支持 RL）
    p_gen = subparsers.add_parser("generate", help="多智能体博弈生成用例")
    p_gen.add_argument("--module", "-m", default="login", help="模块名")
    p_gen.add_argument("--no-auditor", action="store_true", help="无 Auditor")
    p_gen.add_argument("--no-rl", action="store_true", help="禁用 RL-AGS，使用固定轮次")

    # 代码生成
    p_code = subparsers.add_parser("codegen", help="生成测试脚本")
    p_code.add_argument("--output", "-o", default="output", help="输出目录")

    # 自愈
    p_heal = subparsers.add_parser("heal", help="执行自愈")
    p_heal.add_argument("script", help="测试脚本路径")
    p_heal.add_argument("--dir", default=".", help="工作目录")
    p_heal.add_argument("--fix", action="store_true", help="启用自动修复")

    # 智能体流水线
    p_pipeline = subparsers.add_parser("pipeline", help="运行完整智能体流水线")
    p_pipeline.add_argument("--module", "-m", action="append", help="模块名，可重复传入")
    p_pipeline.add_argument("--output", "-o", default="output", help="输出目录")
    p_pipeline.add_argument("--no-rl", action="store_true", help="禁用 RL-AGS")
    p_pipeline.add_argument("--execute", action="store_true", help="执行生成的测试脚本")
    p_pipeline.add_argument("--heal", action="store_true", help="对失败脚本启用自愈")

    # RL 训练
    p_rl = subparsers.add_parser("train-rl", help="训练 RL-AGS 模型")
    p_rl.add_argument("--timesteps", type=int, default=10000,
                      help="PPO 训练总步数")

    # 实验
    p_exp = subparsers.add_parser("experiment", help="运行实验")
    p_exp.add_argument("--type",
                       choices=["full", "ablation", "rl", "healing", "all"],
                       default="all",
                       help="实验类型 (full=完整, ablation=消融, rl=RL对比, healing=自愈, all=全部)")

    args = parser.parse_args()

    cmds = {
        "rag": cmd_rag,
        "generate": cmd_generate,
        "codegen": cmd_codegen,
        "heal": cmd_heal,
        "pipeline": cmd_pipeline,
        "train-rl": cmd_train_rl,
        "experiment": cmd_experiment,
    }

    cmd = cmds.get(args.command)
    if cmd:
        cmd(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
