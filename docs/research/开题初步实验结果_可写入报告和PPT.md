# 开题初步实验结果（Preliminary Results）

> 说明：以下结果用于开题阶段展示“系统链路已跑通”和“实验指标体系可计算”。当前实验基于现有 login/search/cart/checkout 四模块需求集，LLM 使用 mock/fallback 输出，Embedding 因 HuggingFace 本地缓存权限问题降级为 TF-IDF 检索。正式论文实验将迁移到 Spree Commerce 固定版本本地部署后重新运行。

## 1. RAG 需求检索实验

- 解析需求文档：4 个模块。
- 语义切片总数：40 个。
- 模块分布：cart 9、checkout 11、login 11、search 9。
- 类型分布：正向 18、逆向 8、边界值 14。
- 平均切片长度：118.2 字符。
- 查询样例：`购物车`。
- Top-3 检索结果：查看购物车、空购物车页面、结算时不填写收货地址。
- 结论：RAG 检索能够召回与购物车/结算流程相关的需求片段，说明需求切片和检索链路已跑通。

## 2. 完整流程初步实验

实验配置：RAG + Creator-Auditor + RL-AGS，mock/fallback LLM。

| 指标 | 结果 |
|---|---:|
| 需求总数 | 26 |
| 覆盖需求数 | 16 |
| 需求覆盖率 | 61.54% |
| 生成测试用例数 | 14 |
| 幻觉判定用例数 | 8 |
| 启发式幻觉率 | 57.14% |
| 平均迭代轮次 | 1 轮/模块 |
| 自愈实验次数 | 0 |

说明：当前幻觉率偏高，主要原因是 fallback 用例与需求文本关键词不完全一致，且幻觉率采用严格启发式文本匹配。该指标暴露了后续必须接入真实 LLM、Spree 需求文档和更稳健审计规则的必要性。

## 3. RL-AGS PPO 初步训练

- 算法：PPO。
- 训练环境：AGSEnvironment 模拟 Creator-Auditor 迭代决策。
- 训练步数：5000 steps。
- 模型保存路径：`.cache/rl_models/ags_ppo.zip`。
- 训练趋势：rollout 平均 episode length 从约 1.83 降至 1.00；rollout 平均奖励从约 -1.13 提升至 0.00。
- 结论：PPO 训练链路已跑通，模型能够学习在简单状态下提前停止，后续需要在真实 Spree 测试任务上验证质量-成本权衡效果。

## 4. RL 对比初步结果

| 模块 | 固定策略迭代轮次 | RL-AGS 迭代轮次 |
|---|---:|---:|
| login | 1 | 1 |
| search | 1 | 1 |
| 合计 | 2 | 2 |

说明：由于 mock/fallback 用例在 login 和 search 模块第一轮即通过规则审计，因此 RL-AGS 与固定策略没有拉开差距。该结果不能证明 RL 优于固定策略，只能证明 PPO 训练、加载和推理链路可运行。正式实验需要构造更复杂的 Spree 任务，使固定轮次与动态决策产生可比较差异。

## 5. 已生成实验文件

- `experiments/results/experiment_full.json`
- `experiments/results/experiment_ablation.json`
- `experiments/results/experiment_rl.json`
- `experiments/results/ablation_chart.png`
- `experiments/results/rl_comparison_chart.png`
- `.cache/rl_models/ags_ppo.zip`

## 6. 开题报告可写结论

目前已完成原型系统的初步链路验证：RAG 需求切片与检索、多智能体生成与审计、PPO-based RL-AGS 训练与推理均已跑通。初步实验覆盖 4 个业务模块、40 个需求切片和 26 个标注需求点，完整流程生成 14 条测试用例，覆盖 16 个需求点，覆盖率为 61.54%。由于当前实验采用 mock/fallback LLM 和 TF-IDF 降级检索，结果仅作为开题阶段可行性验证，后续将基于 Spree Commerce 固定版本本地部署重新开展正式对比实验和消融实验。
