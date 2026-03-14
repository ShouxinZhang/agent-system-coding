# DeepSeek-Math-V2 Inference Algorithm

这套代码的业务目标不是训练模型，而是批量评估模型在高难数学题上的证明能力，并通过多轮生成与校验持续提升证明质量。

```mermaid
flowchart TD
    A[Input problem sets<br/>JSON or JSONL files] --> B[Load problems<br/>read_data]
    B --> C[Round starts]
    C --> D[Build proof-generation prompts<br/>proof_generation template]
    D --> E[Call model in parallel<br/>generate.py<br/>multiprocess + asyncio]
    E --> F[Collect candidate proofs<br/>with self-evaluation]
    F --> G[Prepare verification tasks<br/>proof_verification template]
    G --> H[Call verifier model in parallel<br/>generate.py<br/>multiprocess + asyncio]
    H --> I[Score each proof<br/>0 / 0.5 / 1]
    I --> J{Skip meta verification?}
    J -- No --> K[Check whether ratings are reasonable<br/>meta_verification template<br/>parallel verifier calls]
    J -- Yes --> L[Aggregate proof quality]
    K --> L[Aggregate proof quality]
    L --> M[Update proof pool<br/>store best proofs per problem<br/>parallel aggregation workers]
    M --> N{Any proof near full score<br/>or max rounds reached?}
    N -- Yes --> O[Write final outputs]
    N -- No --> P[Sample best proofs and feedback]
    P --> Q[Build proof-refinement prompts<br/>proof_refinement template]
    Q --> E
```

关键脚本对应关系：

- `main.py`：编排整条多轮评测与精修流程。
- `generate.py`：并发调用模型接口，产出证明或评分结果。
- `math_templates.py`：定义生成、验证、复核、精修四类提示词模板。
- `utils.py`：负责题目读取、答案抽取、证明与自评拆分。
- `run.sh`：给出一套批量运行参数示例。

从结果上看，这是一条“生成证明 -> 自动审稿 -> 汇总高质量样本 -> 继续精修”的闭环流水线。

并行执行说明：

- `generate.py` 不是单线程调用，而是用多进程分发批次，再在每个进程内用 `asyncio.gather(...)` 并发请求模型接口。
- `main.py` 在 proof refinement 阶段还会用 `multiprocessing.Pool(...)` 并行准备 proof aggregation 任务。
