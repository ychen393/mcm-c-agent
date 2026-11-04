MCM C AGENT

产品需求文档（PRD）

版本：v1.1 | 状态：Approved Baseline | 日期：2026-11-04

文档用途

本文件是 MCM C Agent 项目的产品需求与架构基线（Single Source of Truth）。后续需求、架构、工作流、验收标准发生变化时，更新本文件的版本记录和对应章节。未经用户确认的建议不得直接视为已批准需求。

1. 项目概述

1.1 产品定位

MCM C Agent 是一个面向 demo 场景的半自主、多智能体数学建模竞赛研究系统，首要目标是辅助完成 Mathematical Contest in Modeling（MCM）Problem C 的完整研究流程：从题目理解、数据探索、文献与优秀论文参考、研究思路整合、模型构建与验证，到最终生成结构完整、证据可追溯的 LaTeX 论文。

产品不是简单的论文代写器，也不是多个 Agent 的自由聊天窗口。它应当把研究过程拆解为可执行、可审查、可复现的阶段，并在关键决策点由用户审核。

1.2 项目目标

- 将题目、数据、历史优秀论文和外部研究资料组织为统一研究上下文。

- 让数据分析与文献/思路研究并行开展，减少单一模型视角带来的偏差。

- 通过结构化交叉审查和研究决策机制整合不同 Agent 的发现。

- 支持可复现的数据处理、建模、实验、敏感性分析和结果验证。

- 自动组织论文内容并输出 LaTeX 源码、参考文献及可编译 PDF。

- 保留 AI 使用记录，支持用户检查研究过程和最终产物。

1.3 非目标（当前 Demo 阶段）

- 不承诺无人监督地完成真实竞赛级研究或保证获奖。

- 不允许 Agent 在没有证据的情况下编造数据、论文、引用、模型结果或实验结论。

- 不实现无限制的 Agent 自我修改或任意执行宿主机代码。

- 暂不建设面向大规模团队的 SaaS、多租户权限系统或生产级分布式基础设施。

- 不将历史获奖论文直接复制进最终论文；其用途是学习结构、方法和表达方式，并须尊重版权与学术诚信。

2. 已确认的产品决策

| 决策项 | 已确认选择 |

| 使用场景 | Demo |

| 知识库范围 | Mixed：历史 MCM 优秀论文、题目相关数据/资料、外部学术与可信来源 |

| 自主程度 | Semi-autonomous：Agent 执行研究任务，用户在关键 Gate 审批 |

| 论文输出 | LaTeX，目标产物包含 .tex、.bib、PDF 及研究附件 |

| 开发语言 | Python |

| 起始里程碑 | M0 |

| LLM 策略 | Multi-provider / Multi-LLM，可配置不同模型 |

| 数据库 | Local-first，本地数据库与本地文件存储优先 |

| Repository | 新建 GitHub Repository：ychen393/mcm-c-agent |

| 主分支 | main |

2.1 当前技术基线

- 应用形态：模块化单体（Modular Monolith），避免 Demo 阶段过早拆分微服务。

- UI：Streamlit。

- Agent 编排：LangGraph。

- LLM 接入：统一 Provider Adapter；支持 OpenAI-compatible 接口（例如 DeepSeek）及 Anthropic，后续按需扩展。

- 结构化数据：PostgreSQL；向量检索：pgvector。

- 数据分析：Pandas、NumPy；按需要增加 SciPy、scikit-learn、statsmodels。

- 测试：Pytest。

- 论文：LaTeX + BibTeX。

- 本地运行：Docker Compose 管理 PostgreSQL/pgvector；原始上传文件与生成物保存在本地目录，不提交 Git。

3. 用户与核心使用场景

3.1 目标用户

主要用户为 MCM C 参赛者/研究小组成员，需要在有限时间内完成数据驱动的问题分析、建模、验证与论文写作。Demo 首先服务单人研究工作流，同时保留未来团队协作扩展空间。

3.2 核心场景

用户创建项目并输入 MCM C 题目，上传题目附件和数据文件。系统解析题意与数据结构，启动 EDA Agent 和 Research Agent 并行工作；两条研究线产出结构化报告后，由 Debate/Review 机制比较假设、方法和证据，形成研究方案。用户审核研究方案后，系统开展建模、实验与验证；用户审核模型结果后，系统生成论文大纲和 LaTeX 初稿，经 Reviewer 检查和用户最终批准后，导出完整交付物。

4. 产品工作流

4.1 总体流程

Project Intake

→ Problem Understanding

→ Parallel Research（EDA + Literature/Method Research）

→ Cross-Agent Discussion & Synthesis

→ Human Approval Gate H1

→ Modeling & Experimentation

→ Validation & Sensitivity Analysis

→ Human Approval Gate H2

→ Paper Planning & LaTeX Drafting

→ Paper Review & Revision

→ Human Approval Gate H3

→ Export & Archive

4.2 阶段说明

A. 题目输入与项目初始化

- 输入：题目文本、PDF/文档附件、数据文件、用户补充说明。

- 系统识别题目要求、子问题、交付要求、数据文件与潜在约束。

- 输出：项目元数据、题目解析初稿、待确认事项。

B. 数据探索（EDA）

- 自动识别文件类型、数据表、字段、数据类型、样本量、缺失值、重复值、异常值及基本统计分布。

- 根据题目子问题提出可检验的数据发现和可视化方案。

- 输出：数据字典、清洗记录、EDA 图表、发现与局限性、可复用分析代码。

- 所有统计结论必须能够追溯到输入数据和执行代码。

C. 文献与优秀论文研究

- 从混合知识库检索相关 MCM 优秀论文、题目相关研究、方法论文和可信公开资料。

- 提取研究问题、模型选择、变量设计、假设、验证方式、论文结构和可借鉴之处。

- 记录来源、作者/机构、年份、链接或文件位置、页码/章节（可获得时）。

- 优秀论文仅作为研究参考，不得将其文本或结论伪装成当前项目原创成果。

D. 交叉讨论与方案整合

- 比较 EDA 发现与文献/方法研究是否一致。

- 检查模型假设是否有数据支持，指出证据冲突、信息缺口和潜在偏差。

- 输出多个候选方案、优缺点、数据需求、验证策略及推荐方案。

- Debate Agent 不应简单投票；必须给出可审查的理由和证据。

E. 模型构建与实验

- 将研究方案转化为模型定义、变量、参数、目标函数/约束、算法和执行计划。

- 使用受控工具执行 Python 分析代码；记录代码版本、参数、随机种子、环境和输出。

- 支持基准模型、候选模型对比、参数估计、预测/分类/优化（按题目需求选择）。

- 产出模型说明、运行日志、结果表格、图表和中间数据。

F. 验证与敏感性分析

- 检查模型假设、拟合/预测表现、残差或误差、稳健性和边界条件。

- 根据题目场景采用交叉验证、留出验证、回测、对照分析或其他合理方法。

- 开展关键参数敏感性分析、情景分析和局限性评估。

- 不得把单次运行结果包装成普遍有效结论。

G. 论文生成与审查

- 先形成论文大纲和章节证据映射，再生成 LaTeX。

- 论文中的数字、图表、模型公式、结论和引用应链接到研究产物或可信来源。

- Reviewer 检查逻辑连贯性、数学符号、公式定义、图表引用、引用真实性、章节完整性和题目覆盖度。

- 生成 .tex、.bib、图表文件、代码/数据附件及 PDF（PDF 编译环境可用时）。

5. Agent 角色设计

系统采用职责明确、输入输出结构化的 Agent。各 Agent 共享 ResearchState，但不应共享无边界的自由文本上下文。

1) Orchestrator / Project Manager Agent

负责项目状态、任务拆分、依赖管理、并行任务调度、阶段状态更新、异常处理和审批 Gate。它不替代领域 Agent 做专业结论。

2) Problem Analyst Agent

负责理解题目，拆分子问题，识别输入输出、限制条件、评价目标、隐含要求和需要用户澄清的问题。输出结构化 Problem Specification。

3) Data Analyst / EDA Agent

负责数据文件识别、数据质量检查、统计分析、可视化和初步发现。所有发现均应附数据依据和可复现代码。

4) Literature & Reference Agent

负责检索、筛选和总结历史优秀论文及外部资料，提取方法与写作结构，并维护来源元数据和引用证据。

5) Research Strategy Agent

结合题目要求、EDA 结果和文献发现，提出候选研究路线、变量设计、假设、模型选择与验证计划。

6) Debate / Critic Agent

独立审查候选方案，发现矛盾、薄弱假设、证据缺口和替代解释，要求提出反证或验证方法。

7) Modeling & Experiment Agent

负责将获批方案转化为可执行模型与实验，调用受控 Python 工具，保存代码、参数、结果和运行记录。

8) Validation & Paper Reviewer Agent

验证模型结果与论文质量；检查统计/数学错误、引用、证据、结构和题目覆盖度，并生成可操作的修改意见。

Paper Planner / LaTeX Writer 可作为论文阶段的专门工作节点或 Agent 实现；M0 不要求一次性实现全部 Agent，先固定状态与接口，再逐步交付。

6. 人工审核机制（Human-in-the-loop）

H1 — Research Plan Approval

触发时机：EDA 与文献研究完成、交叉讨论形成方案后。

用户审核：问题理解、研究问题、关键假设、候选模型、推荐方案、所需数据及验证计划。

未批准：返回方案修订；不得进入正式建模。

H2 — Modeling Results Approval

触发时机：模型运行和验证完成后。

用户审核：模型表现、实验结果、敏感性分析、局限性、关键图表与结论。

未批准：允许调整模型或重跑实验；不得将未批准结果作为最终论文结论。

H3 — Final Paper Approval

触发时机：论文生成和 Reviewer 检查完成后。

用户审核：完整论文、引用、公式、图表、AI 使用披露及导出内容。

未批准：进入修订循环；不得标记为最终交付。

所有 Gate 必须记录审批人、时间、所审版本、决策、意见和后续动作。

7. 论文结构与固定要求

论文采用 LaTeX 模板，章节根据具体题目调整，但必须覆盖以下固定内容：

- Summary Sheet / Executive Summary：概述问题、方法、核心结果与结论。

- Introduction：背景、问题目标、整体研究路线。

- Problem Restatement：用清晰、准确的语言重述问题。

- Assumptions and Justifications：列出关键假设及其理由。

- Notations：定义主要变量、参数和符号。

- Data Processing / Exploratory Analysis：数据来源、清洗、探索与关键发现（适用时）。

- Model Development：模型建立、公式、变量解释、求解方法。

- Results and Analysis：结果、图表、解释及子问题回答。

- Model Validation：验证、稳健性、敏感性和误差分析。

- Strengths and Weaknesses：模型优点、局限与改进方向。

- Conclusion：总结主要发现和对题目问题的回答。

- References：真实、可追溯的参考文献。

- AI Use Report / AI Use Statement：按照当届竞赛官方规则和实际 AI 使用情况披露；若官方要求独立报告或指定格式，优先遵守官方要求。

可根据 Problem C 题目增加专属章节，例如优化策略、影响评估、情景分析、管理建议或决策信。章节顺序和标题应服从当届官方格式要求。

8. 知识库与检索要求

知识库范围为 Mixed：

- 历史 MCM 优秀论文及其元数据。

- 当前题目及其附件、数据字典和研究过程资料。

- 相关学术论文、官方数据源、政府/机构报告和可信公开资料。

- 项目内部生成的分析报告、模型记录和已批准决策。

检索要求：

- 区分原始来源、二手总结和模型生成内容。

- 记录来源标识、标题、作者/机构、年份、URL/文件路径、页码/章节及访问时间（可获取时）。

- 检索结果需支持按题目、方法、领域、年份和关键词筛选。

- 向量相似度不能替代来源核验；引用必须能够回到原始来源。

- 不确定或无法验证的来源必须标记，不得生成看似真实的参考文献。

9. 数据、状态与可追溯性

核心 ResearchState 至少覆盖：

- project_id、project_name、project_status、current_stage

- problem_text、problem_specification、uploaded_files

- dataset_metadata、eda_report

- research_proposal、disagreement_log、decision_report

- model_artifacts、experiment_logs、validation_report

- paper_outline、latex_source、citations、review_report

- approval_status、ai_usage_logs、errors

每次重要节点运行应记录：

- run_id、agent_name、输入摘要、输出结构、模型 Provider/Model、提示词版本

- 开始/结束时间、状态、错误信息和必要的用量/成本信息

- 数据/代码/参数版本及产物存储位置

- 关联的项目版本与审批记录

10. 功能需求与优先级

P0 — Demo 核心必需

- 创建项目、录入题目、上传数据/资料。

- 题目解析与子问题拆解。

- 数据文件读取、基础 EDA 和可视化。

- 历史论文/外部资料检索与来源记录。

- EDA 与文献研究并行执行。

- 研究方案整合、交叉审查与 H1 审批。

- 模型运行、结果保存和 H2 审批。

- 论文大纲、LaTeX 初稿和 H3 审批。

- 引用核验、AI 使用记录和项目运行历史。

- 导出 LaTeX 源码、BibTeX、PDF（在编译条件具备时）及研究附件。

P1 — 提升质量

- 多模型路由与模型任务分配。

- 论文结构/方法案例对比。

- 更丰富的敏感性分析、模型对比与 Reviewer 规则。

- 项目版本比较、失败恢复和断点续跑。

- 更完善的成本、耗时和 Token 统计。

P2 — 后续扩展

- 多人协作、角色权限、云端部署。

- 更复杂的知识库管理和增量索引。

- 竞赛题型扩展至其他 MCM 题目。

- 更完整的自动化评测与历史题目回归测试。

11. 非功能需求

- 可追溯：论文中的关键数字、图表和引用应能追溯至数据、代码、实验或原始来源。

- 可复现：保存代码、输入数据版本、参数、随机种子和运行环境信息。

- 可靠性：节点失败时保存状态和错误，支持从可恢复节点继续。

- 安全性：密钥仅从环境变量/安全配置读取；不得提交 Git；不执行未经隔离的 Agent 生成代码。

- 可维护性：模块边界清晰，Agent 使用 Pydantic 等结构化契约。

- 可扩展性：LLM Provider、Agent、工具和论文模板可独立替换。

- 学术诚信：不得伪造引用、数据、实验或将参考论文内容冒充原创。

- 可解释性：关键模型选择和研究决策须给出理由、证据与不确定性。

12. 技术架构

采用 Python 模块化单体，逻辑分层如下：

Presentation Layer

- Streamlit 页面：项目创建、文件上传、工作流状态、报告审阅、审批、论文预览与导出。

Orchestration Layer

- LangGraph StateGraph：节点编排、并行分支、条件路由、人工中断/恢复和状态管理。

Agent Layer

- Problem Analyst、EDA、Literature、Research Strategy、Debate、Modeling、Validation、Paper Review 等领域职责。

Service / Tool Layer

- File Parser、Data Profiler、Python Analysis Runner、Knowledge Retriever、Citation Verifier、LaTeX Compiler 等确定性工具。

LLM Adapter Layer

- Provider Factory、模型配置、结构化输出、重试/超时与统一响应结构。

Persistence Layer

- PostgreSQL + pgvector：项目元数据、研究状态、检索索引和运行记录。

- Local filesystem：上传文件、原始数据、代码、图表、LaTeX、PDF 和运行产物。

Security Boundary

- 后续模型执行工具必须使用隔离环境、资源限制和文件访问白名单；不能直接在 Streamlit 主进程执行任意生成代码。

13. 里程碑与交付计划

M0 — Project Foundation（当前起点）

- 初始化 GitHub Repository 和 Python 项目结构。

- 建立配置管理、Multi-LLM Adapter、ResearchState、基础 LangGraph。

- 建立 PostgreSQL + pgvector 本地服务配置。

- 建立 Streamlit 初始 UI。

- 建立 Pytest 基础测试与项目文档。

- 验收：环境配置可加载、图可编译运行、状态结构符合约定、关键单元测试通过；本地 Docker/数据库/API 联调需实际执行验证。

M1 — Knowledge & Data Foundation

- 文件上传和解析。

- 数据集元信息、数据字典与基础 EDA。

- 历史论文/外部来源摄取、元数据和检索。

- 引用与来源追溯。

- 验收：能够对样例题目及附件生成可追溯的数据报告和文献检索报告。

M2 — Multi-Agent Research Workflow

- Problem Analyst、EDA、Literature、Research Strategy、Debate 节点。

- EDA 与文献分支并行。

- 结构化报告合并、冲突记录和 H1 审批。

- 验收：两条分支独立完成任务，整合报告列明共识、冲突、证据缺口和推荐方案。

M3 — Modeling & Validation

- 受控 Python 执行工具。

- 模型构建、实验记录、模型比较。

- 验证、敏感性分析和 H2 审批。

- 验收：模型结果可复现，结论与实验产物关联，错误和局限有记录。

M4 — Paper Generation

- 论文大纲和章节证据映射。

- LaTeX 模板、BibTeX、图表和公式生成。

- AI 使用报告、论文审查与 H3 审批。

- 验收：LaTeX 可编译，固定章节覆盖，引用可追溯，导出产物齐全。

M5 — End-to-End Demo & Evaluation

- 选择历史 MCM C 题目开展端到端演示。

- 评估流程稳定性、证据质量、模型正确性、论文完整性和可复现性。

- 修复高优先级缺陷并形成演示脚本。

- 验收：完成从题目输入到论文导出的完整流程；所有关键决策经过 Gate；无虚构来源、数字或实验结果。

14. Demo 验收标准

核心质量门槛：

1. Traceability：论文关键数字、图表、模型结论和引用均有来源或运行产物映射；目标 100% 可追溯。

2. Reproducibility：关键实验可由保存的代码、数据版本和参数重新执行；目标 100% 覆盖核心实验。

3. Required Section Coverage：论文固定章节完整覆盖；目标 100%。

4. Unsupported Claims：不得存在未标记、无证据支撑的关键数字、引用或实验结果；目标为 0。

5. Major Mathematical Errors：不得遗留已识别的重大公式、变量定义或计算错误。

6. Human Approval：H1、H2、H3 均有明确审批记录。

7. Export Integrity：LaTeX、BibTeX、图表与 PDF（若编译环境可用）内容一致。

15. 风险与应对

- 历史获奖论文质量/版权/可用性不一：建立来源元数据与使用边界，优先提取方法和结构，不直接复制文本。

- LLM 幻觉与错误引用：要求引用回链和核验；未核实内容标记为待验证。

- 多 Agent 观点冲突：结构化记录证据、假设与反例，交由用户审批。

- 数据质量不足：先生成数据质量报告，明确缺失和局限，不自动补造数据。

- 生成代码存在安全风险：采用隔离执行环境、超时和资源限制。

- LaTeX 编译失败：保留源码和日志，定位错误后修复；不得声称 PDF 已成功生成。

- 多模型行为不一致：统一输出 Schema、记录 Provider/Model/Prompt 版本并执行回归测试。

16. 当前 Repository 与 M0 状态

GitHub Repository：https://github.com/ychen393/mcm-c-agent

Branch：main

当前代码基线：M0 scaffold

已建立的模块方向：app、core、llm、agents、database、schemas、tools、knowledge、modeling、paper、tests、docs。

已建立的基础内容包括：配置管理、ResearchState、基础 LangGraph、LLM Provider Adapter、Streamlit 起始页面、PostgreSQL/pgvector Docker 配置、Pytest 测试骨架和项目文档。

状态说明：Repository 已完成初始文件推送，但不能据此宣称本地环境、Docker 数据库、真实 LLM API 或完整端到端测试已经通过。相关项目验收必须在实际开发环境执行并记录结果。

17. 变更管理与文档维护规则

本 PRD 是项目需求基线。后续每次开发迭代按以下规则维护：

- 先识别变更类型：需求新增/修改、架构调整、Agent 职责调整、数据结构变化、验收标准变化或 Bug 修复。

- 先更新本文件对应章节，并增加版本记录；重大变更先向用户说明影响并取得确认。

- 同步更新相关技术文档、任务清单、接口 Schema、测试和 README。

- 完成代码变更后，记录 Git Commit、测试结果、未完成事项和风险。

- 不得把“计划实现”写成“已实现”，不得把“代码已提交”写成“测试已通过”。

- 若用户提出的临时想法尚未确认，应放入 Open Questions / Proposed Changes，而非直接覆盖已批准基线。

- 每次用户要求继续 MCM C Agent 项目时，应优先读取此 Google Doc 与 GitHub 当前状态，核对两者差异，再继续开发。

18. 版本记录

v1.0 — 2026-11-03

- 汇总已确认的产品方向、技术决策、Agent 工作流、人工审核 Gate、论文结构、技术架构、里程碑和 Demo 验收要求。

- 标记当前 M0 Repository scaffold 状态及尚未完成的本地集成验收。

- 本版本作为后续开发的 PRD Baseline；后续变化通过新版本记录维护。

19. Open Questions（后续需要在开发中确认）

- 最终支持的输入文件类型、单文件大小与批量上传限制。

- 首批纳入知识库的获奖论文年份、数量、来源和版权使用策略。

- 多模型路由规则：哪些任务使用何种模型，以及成本/质量权衡。

- PostgreSQL 持久化与 LangGraph checkpoint 的具体接入阶段。

- Python 沙箱采用独立容器、受限子进程还是其他隔离执行方案。

- LaTeX 模板是否采用当届官方模板，以及 AI Use 报告的最终格式。

- 首个端到端 Demo 采用哪一届、哪一道 MCM C 历史题目。

==============================
PRD v1.1 CHANGE PROPOSAL
状态：Approved Change Set — 已获用户批准
提案日期：2026-11-04
本提案不覆盖 v1.0 已批准基线；用户批准后，合并为 PRD v1.1 正式基线。
==============================

20. 变更摘要与优先级

本次提案将五项改进纳入下一版本：
C1. 将验收标准转化为可自动化或按清单核验的指标。
C2. 采用垂直切片（Vertical Slice）交付，并在 M1/M2 开发前建立评估集。
C3. 在 M1 知识库摄取前完成论文版权、来源许可和当届竞赛合规检查。
C4. 在 M2 Agent Workflow 设计冻结前确定持久化 Checkpoint 与 Python Sandbox 方案；断点续跑由 P1 提升至 P0。
C5. 新增建模质量策略，明确题型方法库、模型选择规则和 Debate 价值验证方法。

拟议优先级：
- P0：项目状态持久化、断点续跑、运行幂等性、基础评估集、版权/合规 Gate、可验证的核心质量指标。
- P1：题型方法库扩展、自动模型比较、Debate 消融评估、复杂评估仪表盘。
- P2：跨题型泛化、大规模论文库治理和更复杂的协作评测。

21. 可执行验收标准（Testable Acceptance Criteria）

所有验收项必须有唯一 ID、测试方法、测试数据、预期结果、实际结果、执行日期和证据位置。状态只允许：Not Run / Pass / Fail / Blocked。未执行的测试不得标记 Pass。

AC-01 项目初始化
- 输入有效项目名称与题目文本，项目创建成功并生成唯一 project_id。
- 缺少必填字段或名称不合法时，返回明确校验错误，不创建半成品项目。
- 自动化：pytest API/service tests。

AC-02 文件上传与数据读取
- 支持的文件类型必须由 allowlist 明确列出；首期建议 CSV、XLSX、JSON、PDF。
- 对每个成功上传文件记录文件名、MIME/扩展名、字节大小、SHA-256、上传时间和项目归属。
- 对不支持、损坏、超限文件返回可理解错误；不得静默丢弃或误读。
- 自动化：每种支持格式至少 2 个 fixture（正常与异常），覆盖率 100%。

AC-03 EDA 正确性
- 对固定 fixture 自动检查行列数、字段类型、缺失值、重复值和关键统计量。
- 确定性统计项与人工核对基准一致；数值容差默认 absolute tolerance 1e-6，特殊算法另行声明。
- 所有图表与发现必须记录输入文件 hash、数据处理步骤和生成代码/配置版本。
- 自动化：golden dataset tests + output schema validation。

AC-04 知识检索与引用
- 每条检索结果必须有 source_id、标题、来源 URL/文件路径和来源类型。
- 引用 URL 可访问性/文件定位状态必须明确标注；不能验证的引用不得标记为 verified。
- 在评估集的引用核验样本中，虚构引用数必须为 0；来源字段完整率目标 100%。
- 自动化：metadata schema tests + citation verification tests；人工抽查原文。

AC-05 Agent 结构化输出
- 每个 Agent 输出必须通过对应 Pydantic Schema 校验。
- Schema 校验失败时执行有限次数修复/重试；超过上限后将节点标记为 failed，并保留错误。
- 不允许把自由文本解析失败静默转换为成功状态。
- 自动化：schema contract tests + malformed-output fixtures。

AC-06 并行研究与整合
- EDA 与 Literature/Method Research 在同一研究阶段启动为独立分支。
- 任一分支失败时保留另一分支结果；整合节点必须标注缺失分支和不确定性。
- 两个分支均成功时，整合报告必须包含共识、冲突、证据缺口、候选方案和推荐理由。
- 自动化：graph integration tests，检查分支状态与输出字段。

AC-07 Checkpoint 与断点续跑（P0）
- 在每个关键节点完成后持久化状态；运行中断后可从最近成功节点恢复，不重复执行已成功且非幂等的外部副作用。
- 进程被强制终止并重启后，能够按 project_id/thread_id 找回运行状态和 artifact references。
- 至少通过 3 类故障注入：进程中断、LLM 超时、工具执行失败。
- 自动化：integration tests；必须包含 kill/restart resume test。
- 验收目标：恢复后状态完整率 100%；已完成节点重复副作用次数为 0。

AC-08 Sandbox 安全边界
- Agent 生成的 Python 代码只能在独立隔离执行环境运行，不得在 Streamlit 或 Orchestrator 进程内执行。
- 默认禁止网络访问；只挂载当前任务所需的只读输入与专用输出目录。
- 设置 CPU、内存、进程数、运行时长、磁盘/输出大小限制。
- 执行容器以非 root 用户运行，根文件系统只读，使用固定版本镜像。
- 自动化：security integration tests，验证网络隔离、路径越权、超时、内存/CPU 限制和清理行为。

AC-09 模型验证
- 每个正式候选模型至少包含一个 baseline 对照。
- 记录训练/验证/测试切分或其他适用验证设计，防止数据泄漏。
- 结果报告至少包含适用的误差/拟合指标、验证方式、关键假设和局限性。
- 自动化：固定合成数据集上的数值测试；人工审核方法是否适合题目。

AC-10 论文完整性
- LaTeX 构建成功时必须保存编译日志、源文件版本和 PDF。
- 论文中的数字、图表、公式、结论和引用应建立 evidence/artifact mapping。
- AI 使用报告须记录工具/模型、用途和使用环节。
- 自动化：latex build test、required-section checker、citation key checker、artifact reference checker。
- 验收目标：必需章节覆盖率 100%；引用键未解析数 0；关键主张无来源映射数 0（未核实主张必须显式标记）。

AC-11 人工审批
- H1、H2、H3 必须有审批状态、版本、时间、决策和意见。
- 未批准 Gate 不得进入下游正式阶段。
- 自动化：workflow routing tests。

AC-12 可观测性与运行记录
- 每个节点记录 run_id、agent、provider/model、prompt version、开始/结束时间、状态、错误和产物引用。
- 密钥不得进入日志。
- 自动化：log schema tests + secret redaction tests。

21.2 评估集与评分规则

在 M1/M2 开发前建立第一版固定评估集，避免系统完成后才补做质量评估。

建议最小规模：
- 3 道不同年份的历史 MCM Problem C 题目作为端到端 benchmark。
- 至少 15 个 task-level evaluation cases，覆盖题目拆解、数据理解、EDA、来源检索、方法选择、Debate、验证设计和论文结构。
- 至少 5 个确定性数据分析 fixture，覆盖缺失值、异常值、时间趋势、类别变量和多表关联。
- 至少 10 个引用核验样本，包含有效来源、元数据不全来源和不可验证来源。
- 每个 LLM 评估 case 保存输入、参考要点、评分 Rubric、禁止错误和期望输出 Schema。

评估集分层：
- Dev Set：允许用于 Prompt、Schema 和工作流调试。
- Holdout Set：只用于阶段验收，不允许反复用于提示词调优；若被用于调优，应重新建立 Holdout。
- Regression Set：保存已发现的失败案例，代码或 Prompt 变更后自动回归。

评分维度（建议统一为 0–4 分）：
- Task Coverage：是否覆盖题目要求。
- Evidence Grounding：是否有数据或来源支撑。
- Mathematical Soundness：变量、假设、公式和推理是否成立。
- Reproducibility：是否能够复现结果。
- Communication：结构、图表与表达是否清楚。
- Compliance：是否满足竞赛披露、引用和格式要求。

评估报告必须同时呈现分项分数、失败案例、严重错误数和人工评审意见；不得只用单一 LLM Judge 分数代表系统质量。关键数学与引用问题必须进行人工抽查。建议至少 20% 的 LLM 评估样本由人工复核。

22. 垂直切片交付路线（Vertical Slices）

每个切片都必须形成可运行、可演示、可测试的端到端薄功能，而不是只完成孤立 Agent。

VS-0 Foundation Smoke Slice（M0）
- 创建项目 → 保存项目 → 读取项目 → 基础 LangGraph 运行 → UI 展示状态。
- 交付：本地可运行应用、数据库连通性、基础测试、环境说明。
- Gate：新环境按 README 可启动；核心测试通过。

VS-1 Data-to-EDA Slice（M1-A）
- 上传一个 CSV/XLSX → 文件校验 → 数据预览 → 数据字典 → 基础 EDA → 图表/报告 → 保存报告。
- 交付：至少一个完整样例项目及可追溯 EDA 产物。
- Gate：AC-02、AC-03 通过。

VS-2 Knowledge-to-Evidence Slice（M1-B）
- 输入题目/研究问题 → 检索获准来源 → 返回证据卡片 → 用户打开原始来源 → 生成带来源标记的研究摘要。
- 交付：首批知识库、来源登记表、检索评估集和引用核验报告。
- Gate：版权/竞赛合规 Gate 通过，AC-04 通过。

VS-3 Parallel Research-to-Decision Slice（M2）
- Problem Analyst → EDA 与 Literature 并行 → Research Strategy → Debate/Critic → 方案整合 → H1 审批 → Checkpoint 恢复。
- 交付：可恢复的研究流程、结构化报告、冲突日志、审批记录。
- Gate：AC-05、AC-06、AC-07、AC-11 通过；评估集完成首轮基线测试。

VS-4 Approved Plan-to-Validated Model Slice（M3）
- 获批研究方案 → Sandbox 执行 → baseline/candidate 对比 → 验证与敏感性分析 → H2 审批。
- 交付：可复现模型、运行环境/参数记录、验证报告。
- Gate：AC-08、AC-09 通过。

VS-5 Evidence-to-LaTeX Submission Slice（M4）
- 已批准研究产物 → 论文大纲 → 章节证据映射 → LaTeX/BibTeX → 编译 PDF → Reviewer → AI Use Report → H3 审批。
- 交付：完整 LaTeX 项目、PDF、BibTeX、图表和 AI 使用报告。
- Gate：AC-10、AC-11 通过；按当届规则检查页数与格式。

VS-6 Full Historical Problem Demo（M5）
- 从历史题目输入开始，完整走通 VS-1 至 VS-5。
- 交付：录屏/演示脚本、评估报告、已知限制和回归测试结果。
- Gate：全部 P0 验收项通过；关键失败均有记录，无虚构引用或实验结果。

23. 知识库版权与竞赛合规 Gate（M1 前置条件）

23.1 版权与来源策略
在任何批量论文下载或索引前，先建立 Corpus Registry（知识库来源登记表），至少记录：
- source_id、标题、作者/机构、年份、原始 URL、获取日期。
- 发布方、许可类型/版权声明、使用条款链接。
- 文件来源（官方公开、作者授权、用户提供、机构订阅或其他）。
- 允许的操作：仅链接、元数据索引、内部全文检索、摘要、片段引用、是否允许再分发。
- 审核状态、审核人和审核日期。

默认原则：
- 公开可访问不等于 Public Domain，也不自动意味着可批量下载、复制、再分发或向第三方模型上传。
- 优先使用 COMAP 官方公开资料、明确开放许可资料、作者授权资料和用户有权使用的材料。
- 对权利不明确的获奖论文，默认只保存必要元数据与原始链接；在权利确认前不建立可对外分发的全文语料库。
- 知识库生成的方法卡片应以抽象总结为主，不复制论文大段原文、图表或独创表达。
- 用户上传文件不自动代表用户拥有再分发或训练使用权；上传前应提示用户确认使用权限。
- 不向外部 LLM Provider 发送超出完成任务所需的受版权保护全文；Provider 数据处理条款和保留政策需纳入评估。
- 为每份来源保留删除/下架机制；来源失效或许可变更时可禁用检索并移除本地副本。

23.2 2027 MCM/ICM 竞赛合规基线（需在比赛前再次核验）
截至 2026-11-04，COMAP 官方 2027 规则明确：
- AI 工具允许作为辅助工具使用，但团队必须诚实、清晰地披露 AI 使用情况。
- 报告中需指出使用的 AI 工具/模型及用途，并按官方要求在正文中引用、在参考文献中列出；若使用 AI，需在 25 页 solution 后附 Report on Use of AI，该报告不计入 25 页 solution 限额。
- 团队必须核验 AI 生成内容及引用的准确性、有效性和适当性，并防范抄袭。
- COMAP 特别提醒谨慎使用 AI 进行模型选择与构建、代码生成、数据/模型结果解释和科学结论推导；团队对最终分析与提交内容负责。
- 2027 Solution 主体总页数上限为 25 页，包含 Summary Sheet、Solution、目录、参考文献、附录等；AI Use Report 按官方说明另附。
- 比赛期间不得向团队外部人员寻求解题帮助；工具设计必须服务于团队自主分析，不能引入外部人员代做或代答。

系统必须实现：
- AI Usage Ledger：记录 Provider、模型标识、用途、调用阶段、时间和人工核验状态。
- AI Use Report Export：按官方要求生成可编辑的披露草稿，最终由参赛团队核实。
- Citation & Claim Review：要求用户核对 AI 输出的事实、公式、引用和结论。
- Competition Mode Checklist：比赛前锁定当届官方规则版本、规则 URL、核验日期、页数/字体/匿名要求和 AI 披露要求。
- 不得将任何往届格式假设硬编码为永久规则；以当届官方规则为准。

官方依据：
COMAP 2027 MCM/ICM Contest Rules and Instructions：
https://contest.comap.com/undergraduate/contests/mcm/instructions.php
COMAP 2027 AI Tools Guidance（包含于官方规则页面）：
https://www.contest.comap.com/undergraduate/contests/mcm/instructions.php

23.3 M1 Knowledge Ingestion Release Gate
在以下事项全部完成前，不得启动批量历史论文摄取：
- 首批来源清单经用户审核。
- 每个来源的许可/使用条款字段完整，或明确标记为“仅链接/不存全文”。
- 版权不明材料采用保守处理方式。
- 已确认不会把知识库设计成论文全文再分发服务。
- 用户确认首批 Corpus Registry 和检索用途边界。

24. Checkpoint 持久化与 Sandbox 技术决策（M2 前冻结）

24.1 Checkpoint 推荐方案
- LangGraph 使用 PostgreSQL Checkpointer（优先采用官方 PostgresSaver 实现）。
- 每个研究项目映射稳定 thread_id；每次运行有独立 run_id。
- 在重要节点边界保存 checkpoint；H1/H2/H3 等人工审批中断必须可持久化恢复。
- ResearchState 中保存结构化状态与 artifact references；大文件、数据集、图表、PDF 不直接塞入 checkpoint，而存文件系统并保存 URI、hash、版本。
- 对节点定义幂等策略；外部副作用（文件写入、远程 API、导出）使用 idempotency key 或先检查产物是否已存在。
- 记录 checkpoint schema version；升级时提供兼容/迁移策略。
- 定义保留策略、备份方式和项目删除行为。

24.2 Sandbox 推荐方案
首选 rootless Docker container-per-run：
- 每次 Agent 代码执行创建独立容器或隔离任务。
- 默认 network=none；如需联网，必须由明确授权的受控数据获取工具完成，不允许任意代码直接访问网络。
- 非 root 用户、只读根文件系统、drop capabilities、禁止 privileged。
- 输入数据只读挂载；输出目录单独挂载并限制路径。
- CPU、内存、PID、运行时长和输出文件大小均设硬限制。
- 固定并扫描基础镜像；执行后清理容器与临时目录。
- 记录代码 hash、镜像 digest、依赖版本、参数、随机种子、stdout/stderr 和退出码。
- Sandbox 不应拥有数据库管理员凭证、LLM API Key 或宿主机敏感目录访问权限。

24.3 设计冻结前验证
M2 设计开始前必须提交 Architecture Decision Record（ADR），明确：
- Checkpointer 选型、依赖版本、连接池、迁移和恢复策略。
- thread_id/run_id 规则与 artifact storage contract。
- Sandbox 运行时、资源限制、网络策略、镜像和清理策略。
- 本地开发环境如何启动和测试。
- 故障注入测试方案。
用户审核 ADR 后，才冻结 M2 工作流实现方案。

25. 建模质量策略（Modeling Quality Strategy）

25.1 题型方法库（Problem-Type Method Library）
建立可检索、可解释的方法卡片库，而不是直接按题目关键词调用固定模型。首批方法族建议包括：
- 描述统计与探索性分析：分布、分组比较、相关性、异常检测。
- 时间序列与预测：趋势/季节性基线、指数平滑、ARIMA 类模型及适用的机器学习模型。
- 回归与解释分析：线性/广义线性回归、正则化、非线性关系和诊断。
- 分类与评分：逻辑回归、树模型、分类指标、校准与阈值选择。
- 聚类与分群：K-means、层次聚类、密度聚类及聚类稳定性。
- 降维与综合指标：PCA、标准化指标、权重敏感性。
- 优化与资源分配：线性/整数规划、约束优化、启发式算法。
- 仿真与不确定性：Monte Carlo、离散事件/Agent-based simulation（按题目需要）。
- 网络与空间分析：图指标、网络结构、空间相关与地理可视化。
每张方法卡片记录：适用问题、数据要求、核心假设、公式/算法、参数、优缺点、验证指标、常见失败模式、参考来源和可运行示例。

25.2 模型选择规则
- 先把题目子问题转化为明确的任务类型、目标变量、决策变量和评价标准。
- 先建立简单、可解释的 baseline，再考虑复杂模型；复杂度必须由可验证收益支撑。
- 每个候选模型必须声明假设、数据需求、适用条件、评价指标和失败风险。
- 至少比较 baseline 与一个有理由的候选模型；若题目不适合比较，需说明原因。
- 预测任务使用与时间/数据结构相符的验证切分；时间序列不得随机打乱造成未来信息泄漏。
- 分类任务同时考虑类别不平衡、Precision/Recall/F1、ROC-AUC/PR-AUC 与校准（按场景选取）。
- 回归任务按场景选择 MAE、RMSE、R²、残差诊断和外推风险；不能只凭 R² 判定优劣。
- 聚类任务结合内部指标、稳定性和业务/题意可解释性，不能只看单一 Silhouette Score。
- 优化/仿真任务需验证约束可行性、边界情况、随机种子稳定性、情景敏感性和基准策略对比。
- 模型选择必须考虑解释性、计算成本、数据质量和题目叙事，而不只是模型分数。
- 禁止在测试集上反复调参；所有数据切分与指标须记录。

25.3 Debate 机制与价值验证
Debate 的目标不是让多个 Agent 互相赞同或增加文字，而是提高研究决策质量。每次 Debate 必须围绕具体决策对象进行：
- 主张：当前推荐方案/模型是什么？
- 证据：来自数据、文献、数学推导或实验的哪些证据？
- 假设：依赖哪些可检验前提？
- 反例：什么观察会推翻该主张？
- 替代方案：至少一个合理备选及其代价。
- 验证动作：下一步用什么数据/实验区分候选方案？
- 决策记录：采纳/拒绝/保留意见及理由。

Debate 不能以 Agent 数量、发言轮数或输出长度作为质量指标。必须通过消融实验评估：
- Baseline A：Research Strategy 单 Agent，不启用 Debate。
- Baseline B：Research Strategy + Debate/Critic。
- 对同一 Holdout 题目、相同输入和可比模型预算进行评估。
- 由盲评者按方案适配度、证据充分性、数学合理性、风险识别和可验证性评分。
- 记录 Debate 新发现的实质性问题数、被数据/原文核实的问题数、误报数、方案修订前后评分变化、额外耗时/成本。
- 只有当 Debate 带来可重复的质量提升或发现并验证了实质性风险，且收益与额外成本相称时，才保留该阶段；否则简化为单轮 Critic 或规则化审查。

26. PRD v1.1 Proposed Decision Log

PD-01：断点续跑由 P1 提升至 P0。已批准。
PD-02：M1/M2 前建立固定 Dev/Holdout/Regression 评估集。已批准。
PD-03：M1 批量知识库摄取必须经过版权与竞赛合规 Gate。已批准。
PD-04：M2 前冻结 PostgreSQL Checkpointer + Docker Sandbox ADR。已批准；rootless 优先在支持的 Linux 环境验证。
PD-05：引入垂直切片交付和建模质量策略。已批准。

版本记录补充：
v1.1 Approved — 2026-11-04
- 新增可执行验收标准、评估集方案、垂直切片路线、版权与 2027 竞赛合规 Gate、Checkpoint/Sandbox 技术决策建议、建模质量策略。
- 用户于 2026-11-04 批准五项变更；本版本成为正式 PRD v1.1 基线。


## 32. PRD v1.2 — Visual EDA & Chart Intelligence (Approved 2026-11-04)

**Decision:** User approved the proposed Visual EDA Agent architecture on 2026-11-04. This section is the approved v1.2 product direction, not evidence that every phase is implemented.

### 32.1 User value
Given a dataset and MCM C problem statement, choose charts for their analytical purpose rather than generating histograms for every numeric column. Each chart must include clear labels, a figure reference, caption, the question it answers, data-supported findings, insights, limitations, and next-step implications.

### 32.2 Architecture
Dataset Loader → Deterministic EDA Profiler → Visual EDA Agent (chart planner) → Chart Plan Validator → Python Chart Executor → Insight Analyst → EDA Reviewer → EDA Report.

LLM plans and interprets; Python computes actual values and renders charts. Do not run arbitrary LLM-authored Python as part of chart planning. Any quantitative claims must be supported by actual computed metrics and provenance. No invented data, figures or causal inferences.

### 32.3 ChartSpec contract
A chart specification includes: chart_id, chart_type, title, figure_label (LaTeX-compatible identifier), x/y source columns, axis labels and optional units, legend, caption, analytical_question, rationale, priority, caveats, transform and aggregation where supported. Execution results include plotted row counts, dataset hash, input fields, chart path and computed metrics.

Insight objects (Phase C) must distinguish observation, numeric finding, research insight, limitation, next step and evidence_refs. Insights are not valid without data evidence.

### 32.4 Chart selection
Support common table, categorical, time-series, comparative and domain-specific charts through a typed catalog. Financial return, volatility, drawdown and normalized asset comparisons are optional specialized capabilities, not universal defaults. The planner must select charts with clear value, reject redundant/unsuitable charts, and explain when a chart should not be generated.

When the problem statement is absent or the LLM is unavailable, deterministic fallback EDA must still work and be labeled as generic rather than problem-aware analysis.

### 32.5 Chart presentation and paper reuse
UI and exported Markdown/JSON must bind a plot to its Figure Label, title, axes with units, caption, analytical question, actual metrics and later Insight. LaTeX paper generation will reuse the figure label, image path, caption and evidence references. Full label coverage and zero unsupported quantitative findings are release requirements.

### 32.6 Phased implementation
- **Phase A (first):** structured ChartSpec, Chart Catalog, validator, deterministic Python executor, labels, computed metrics and provenance. Preserve legacy chart output as fallback.
- **Phase B:** connect Visual EDA Agent through existing Multi-LLM Adapter; plan and rank charts using the question and dataset profile.
- **Phase C:** connect Insight Analyst and Reviewer to produce and verify evidence-grounded findings, insights, limitations and proposed follow-up analysis.
- **Phase D:** refine Streamlit report cards, LaTeX export hooks and evaluation cases for relevance, nonredundancy, grounding and reproducibility.

### 32.7 Progress
Phase A code authored on `feature/m1a-data-eda` on 2026-11-04; isolated local chart-runtime tests passed (4/4). Whole-project CI, Streamlit UX acceptance and the user's approval remain pending. Phases B–D have not been implemented.

### 32.8 Change log
v1.2 Approved — 2026-11-04: user confirmed Visual EDA Agent + image labels + evidence-grounded findings/insights architecture; implementation gated by phased review.
