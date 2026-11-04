MCM C AGENT

产品需求文档（PRD）

版本：v1.0 | 状态：Baseline / M0 开发基线 | 日期：2026-11-03

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