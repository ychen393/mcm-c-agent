# Cursor Agent 分层可见性

这份说明只回答一件事：工作在哪一层跑，人在哪里看得见它。操作步骤、停止条件和机器可读字段仍以 `docs/CURSOR_COWORK_RUNBOOK.md` 与 `docs/cowork/` 为准。本页不新增 Task 类型，不连接账号，也不批准合并。

与 `docs/cowork/issue-8-status.json` 一致（记录日期见该文件所依据的 2026-11-05 Cloud 会话）：

- 总状态 `status`：`PARTIAL`
- `reviewer.isolation`：`blocked`
- `bugbot` 的 `task_id`：`not-launched`

## 侧边栏里有什么

Cursor IDE 侧边栏列出的是 **chats**。它不把 Builder、Reviewer、CI 画成组织图。下面每一层是否会变成一条 sidebar chat，写在表里。

`.cursor/agents/builder.md` 与 `.cursor/agents/reviewer.md` 是角色提示文件。`name: builder` 与 `name: reviewer` 不是可启动的 Task 类型。2026-11-05 的 Cloud 会话拒绝了 `subagent_type=builder` 和 `subagent_type=reviewer`。Frontmatter 的 `readonly: true` / `readonly: false` 不改变 Cloud 工具权限。Task schema 没有 Task 级 readonly 开关。

## 分层

| 层 | 在哪里看见 | 职责 | IDE sidebar chat？ | 交到下一层 |
| --- | --- | --- | --- | --- |
| Coordinator（ChatGPT，经 GitHub） | GitHub Issue | 写验收标准、风险等级和非目标；读证据；接受或拒绝交接。不从本页合并。 | 否 | 范围留在 Issue。实现从该 Issue 开工。 |
| Local IDE Agent chat | Cursor IDE 侧边栏里的一条 chat | 在本机 IDE 里对话并改工作区。角色边界来自 `AGENTS.md` 和提示文件。 | 是。侧边栏显示的就是 chat。 | 要进入仓库流程时，仍落到分支和 Draft PR。 |
| Cloud Agent（main agent） | [cursor.com/agents](https://cursor.com/agents) 上的一次 run | Issue 的实现者：一条分支、测试、Draft PR，并可调用 Task。已记录的 builder 会话可以 commit 和 push。 | 否。run 页面在 cursor.com/agents，不在侧边栏组织图里。 | 需要拆出的实现用 Task。结果回到同一分支，再开 Draft PR。 |
| Task subagent | 父 run 里的 Task 结果和 task id | 只使用**该次会话** Task schema 实际列出的 `subagent_type`。通常嵌套在父 run 内。 | 通常否 | 结果回到 main agent。main agent 写 Draft PR 和 `docs/cowork/`。 |
| 角色提示文件 | 仓库文件 `.cursor/agents/builder.md`、`.cursor/agents/reviewer.md` | 写进任务正文的指令。Builder 做一个 Issue。Reviewer 读 diff，不改 Builder 分支。 | 否 | 不能当作 `subagent_type` 启动。 |
| GitHub Actions | PR Checks。工作流 `Python tests`、`Read-only review boundary` | 客观测试和权限边界。不是 AI reviewer。 | 否 | check 留在 Draft PR 上。通过不等于可合并。 |
| Owner | GitHub 上的合并、设置与密钥 | 合并、部署、密钥、分支保护、付费 API、研究闸门。 | 否 | 流程停在 Draft PR。Owner 决定是否合并。 |

本仓库没有已证实的 Cloud project chat，也没有 agent-to-agent 消息通道。当前 cloud agent token 对 Issue 发表评论会得到 `Resource not accessible by integration`（`addComment`）。交接文字写在 Draft PR 上。

## Task 子层：谁可以跑

Main agent 调用 Task 时，`subagent_type` 必须是该次会话列出的内建类型。提示文件里的 `name` 不在此列。

| 用途 | 类型 | 已记录情况 |
| --- | --- | --- |
| 实现一个 Issue。把 Builder 提示写进 task 正文。 | `generalPurpose` | Issue #8 用过。task id `bc-15dc0f55-b966-5e40-9c2f-07380618e9f6` 写了测试。run metadata 名为 grok-4.7-high-fast。记录写明不声称存在第二个模型。 |
| 查看代码，或查一个可复现的缺陷。 | `explore`、`debug` | 可用时也不是独立 reviewer。 |
| 解释一次**已经失败**的 GitHub Actions check。 | `ci-investigator` | Issue #8 没有调用，因为所需 check 没有失败。 |
| 对真实 diff 做缺陷审查。 | `bugbot` | 仅当该次会话列出它。2026-11-05 在启动前被拒绝。 |
| 安全范围内的改动。 | `security-review` | 仅当该次会话列出它，且 Issue 属于安全范围。同一次拒绝文本里它不在 enum 中。 |
| 角色文件名 | `builder`、`reviewer` | 拒绝。不要再传这两个名字。 |

该次拒绝文本给出的期望值为：`generalPurpose`、`explore`、`debug`、`computerUse`、`videoReview`、`cursor-guide`、`ci-investigator`、`best-of-n-runner`、`ai-architect`、`deployment-expert`、`performance-optimizer`。下一次会话以它自己的 Task schema 为准，不要把上表当成永久产品目录，也不要把未列出的类型改名后冒充 `bugbot`。

## 交接顺序

`Issue → Cloud Agent → Task → Draft PR → CI → Owner`

1. Coordinator 确认 Issue：验收标准、风险等级、非目标。
2. Cloud Agent（main agent）从指定 base 开一条分支。一个分支一个所有者。
3. 需要拆出的实现调用 Task。类型必须是该会话列出的内建名。Issue #8 的实现主体是 main agent；其中一次 `generalPurpose` Task 写了测试。
4. 环境带有 dev extra 时，实现者本地运行 `pytest -q`。
5. 实现者打开 **Draft** PR。不自动合并。
6. 等待这次 pull request 事件上的 `Python tests`。另一条分支上的 push run 不算。
7. 该 check 失败时，对那次 run 使用 `ci-investigator`，同一问题最多修两次。
8. 会话列出 `bugbot` 时，对 diff 调用它。调用被拒绝则记下错误并停止这一步。Issue #8 停在这里：`reviewer.isolation` 为 `blocked`，`task_id` 为 `not-launched`。
9. 写入 `docs/cowork/issue-<n>-status.json`，并在 Draft PR 上评论。
10. Owner 审阅。Runbook 不合并。

## 仍然 BLOCKED 的审查隔离

Cursor Cloud 的 builder 会话可以 commit 和 push。提示文件去不掉这个能力。`Read-only review boundary` 使用 `contents: read`、`pull-requests: read` 和 `persist-credentials: false`。该 job 只检查 diff 中的秘密类路径。它不是独立的 AI reviewer。

在 Owner 按 `docs/CURSOR_COWORK_RUNBOOK.md` 的 Owner steps 建好另一个不能 push 的 principal 之前，`reviewer.isolation` 保持 `blocked`。本页不把这件事标成已解决。

## 相关文件

- `docs/CURSOR_COWORK_RUNBOOK.md` — 可运行步骤与停止条件
- `docs/cowork/issue-8-status.json` — `PARTIAL` / `blocked` 的机器可读记录
- `AGENTS.md` — 共享边界与 Cursor co-work 调用约束
- `.cursor/agents/builder.md`、`.cursor/agents/reviewer.md` — 角色提示，不是 Task 类型
