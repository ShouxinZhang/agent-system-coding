# DeepSeek-Math-V2 Inference as an Agent System

如果从 `agent system` 的角度理解这套 `inference` 代码，它不是一个“多个长期记忆 Agent 持续对话协作”的系统，而是一个“主控编排 + 多角色任务模板 + 外部化记忆池”的流水线系统。

## 1. 这套系统里的 Agent 设计是什么

业务上，这套系统可以拆成 5 个角色：

1. `Orchestrator`
   - 由 `main.py` 承担。
   - 负责分轮次推进任务，控制生成、评分、复核、精修和最终输出。
   - 它是系统总控，不直接“思考”题目，而是把题目和历史结果分发给其他角色。

2. `Prover Agent`
   - 用 `proof_generation` 模板生成题目的证明或答案。
   - 首轮直接看题目；后续轮次则看“题目 + 历史证明 + 历史评分摘要”。

3. `Verifier Agent`
   - 用 `proof_verification` 模板审核 `Prover` 的证明。
   - 它的业务职责是给证明打分，判断结论是否完整、严谨、可接受。

4. `Meta-Verifier Agent`
   - 用 `meta_verification` 模板审核 `Verifier` 的评分是否合理。
   - 它不是解决原题，而是审查“审稿结果”本身。

5. `Refinement Agent`
   - 用 `proof_refinement` 模板把历史高分 proof 和评语重新组织成下一轮输入。
   - 它的业务职责不是独立持久记忆，而是消费已有记忆并产出更好的候选证明。

从这个角度看，这套系统更像一个 `role-based multi-stage agent pipeline`，而不是多个自治 Agent 长时间共享同一上下文窗口。

## 2. 记忆模块是如何管理的

这套系统最重要的点是：记忆主要不在 Agent 进程内部，而在外部文件和重组后的 prompt 中。

### 2.1 短期记忆：单次请求上下文

每次模型调用实际只看到当前样本的 `messages`。

- 在 `generate.py` 中，worker 取到任务后只读取该样本自带的 `messages`，然后发起一次模型请求。
- 这说明单个 worker 没有自动继承别的 worker 的上下文，也不会共享“上一题的思考历史”。

业务含义：
- 每个角色的短期记忆都被压缩在当前 prompt 里。
- 记忆输入是显式传递的，不是隐式共享的。

### 2.2 进程级临时记忆：并行 worker 本地状态

`generate.py` 用 `multiprocessing.Process` 启动多个 worker，并在每个进程内用 `asyncio.gather(...)` 并发请求模型。

这意味着：

- 不同 worker 之间是隔离内存空间。
- worker 和主控之间不共享运行时对象。
- 同一 worker 进程里虽然复用一个客户端实例，但并不会形成跨样本的长期任务记忆。

业务含义：
- 这里的“subagent”更像并行执行单元，而不是共享脑内记忆的协作智能体。
- 并行提升的是吞吐量，不是共享认知能力。

### 2.3 长期记忆：外部持久化记忆池

真正跨轮保留的信息主要有 3 类。

1. `proof_pool`
   - 按题目保存历史 proof、均分、评分细节、自评分数、proof_id 和依赖关系。
   - 它是系统最接近“长期记忆库”的部分。

2. 每轮 `jsonl` 输入输出文件
   - 如 `proof_gen_R*`、`proof_verification_R*`、`meta_verification_R*`。
   - 它们记录每一轮生成结果和审核结果，为下一轮提供可回放的中间状态。

3. `.meta` 断点信息
   - `generate.py` 会为输出文件维护 `.meta`，记录已完成批次。
   - 这更像执行层的“恢复记忆”，确保中断后能续跑，而不是推理层知识记忆。

业务含义：
- 系统的长期记忆不保存在模型上下文窗口里，而保存在外部文件系统中。
- 这样做的优势是可扩展、可并行、可恢复、可审计。
- 代价是每一轮都必须显式把历史信息重新整理后再喂回模型。

## 3. 记忆是如何从存储层回流到 Agent 的

这套系统不是“Agent 自己记住”，而是“主控把记忆重新拼装给 Agent”。

主要过程如下：

1. `main.py` 收集历史 proof、评分、自评和依赖关系。
2. 从 `proof_pool` 里筛选高质量候选证明。
3. 把多个 proof 及其评语整理成文本摘要。
4. 用 `proof_refinement` 模板把这些历史内容重新写入新一轮 `messages`。
5. 新一轮 `Prover/Refinement Agent` 再基于这个新 prompt 继续生成。

所以它的记忆读写链路是：

`Agent output -> files / proof_pool -> orchestrator aggregation -> rebuilt messages -> next Agent call`

而不是：

`Agent output -> shared internal memory -> next Agent directly reads`

## 4. 这套设计的本质判断

如果站在我们这个仓库的 `agent system coding` 视角，这套 DeepSeek 参考实现的本质可以概括为：

- 它有多角色分工，但角色主要由 prompt 模板定义。
- 它有跨轮记忆，但记忆主要外部化到文件和 proof pool。
- 它有并行子执行单元，但这些执行单元不共享内部上下文。
- 它更接近“workflow-driven agent system”，而不是“shared-memory multi-agent system”。

## 5. 对业务的优缺点

优点：

- 易于横向扩展，适合大规模批量评测。
- 中间结果可追踪，适合复盘与审计。
- 记忆和执行分离，能降低单个 Agent 上下文窗口压力。

缺点：

- 没有真正共享的在线工作记忆，跨角色协作依赖主控重组 prompt。
- 历史信息一旦摘要不好，后续 refinement 质量会受影响。
- 角色间协作是“文件驱动”，不是“持续对话驱动”，灵活性较弱。

一句话总结：

`DeepSeek-Math-V2/inference` 的 agent system 设计，本质上是“多角色模板 + 主控编排 + 外部化记忆池”，而不是“多个共享长期上下文记忆的自治 Agent”。 

## 6. 实跑证据：一次 OpenRouter smoke test 看到的记忆链路

为了验证上面的判断，我在 `MyRead/runtime-smoke` 下做了一次最小运行复现，输出目录如下：

- `docs/ref_code/deepseek-math-v2/MyRead/runtime-smoke/output/proof_gen_R1/input.jsonl`
- `docs/ref_code/deepseek-math-v2/MyRead/runtime-smoke/output/proof_gen_R1/output.jsonl`
- `docs/ref_code/deepseek-math-v2/MyRead/runtime-smoke/output/proof_verification_R1/output.jsonl`
- `docs/ref_code/deepseek-math-v2/MyRead/runtime-smoke/output/proof_pool/runtime_smoke/demo-even-sum.jsonl`
- `docs/ref_code/deepseek-math-v2/MyRead/runtime-smoke/output/proof_gen_R2/input.jsonl`

这次样例题是：

- `Prove that the sum of two even integers is even.`

运行中发生的关键事实是：

1. 第一轮 `proof_gen_R1/output.jsonl` 里，模型生成的证明被 `max_tokens=256` 截断。
   - 这说明单次 Agent 调用的“短期记忆”只存在于当次输出里，一旦输出不完整，后续角色不会自动知道缺失的部分。

2. `proof_verification_R1/output.jsonl` 读取这份截断证明后，Verifier 明确给出 `score = 0.0`。
   - 这里没有共享脑内记忆，Verifier 只依据主控给它拼装的 `messages` 做判断。

3. `proof_pool/runtime_smoke/demo-even-sum.jsonl` 把第一轮的 proof、评分结果、自评信息、`proof_id=1` 和 `dep_proof_ids=[]` 写入磁盘。
   - 这就是长期记忆第一次被固化。

4. `proof_gen_R2/input.jsonl` 不再只包含原题，而是把上一轮 proof 和对应评语直接拼进了 `Candidate Solution(s) to Refine`。
   - 同时写入了 `dep_proof_ids: [1]`，说明第二轮输入显式依赖第一轮 proof pool 中的那条记录。

5. 第二轮 `proof_gen_R2/output.jsonl` 的改稿并不是因为 subagent 共享了内部上下文，而是因为主控把外部记忆重新注入了新的 prompt。

因此，这次实跑可以非常直接地证明：

- 记忆不是藏在 worker 或 subagent 的私有上下文里持续共享。
- 记忆先被写成外部文件，再由主控重组后回灌进下一轮 Agent 输入。
- `proof_pool + round outputs + rebuilt messages` 才是这套系统真正的 memory module。
