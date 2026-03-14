# DeepSeek-Math-V2 Inference Algorithm (ASCII)

这份版本面向纯文本阅读，强调这套流程不是单线程串行，而是包含多进程和异步并发请求的多轮评测闭环。

```text
+---------------------------+
| Input problem sets        |
| JSON / JSONL files        |
+---------------------------+
             |
             v
+---------------------------+
| Load problems             |
| read_data                 |
+---------------------------+
             |
             v
+---------------------------+
| Round starts              |
+---------------------------+
             |
             v
+---------------------------+
| Build generation prompts  |
| proof_generation          |
+---------------------------+
             |
             v
+--------------------------------------------------+
| Parallel proof generation                        |
| generate.py                                      |
| - multiprocessing.Process workers                |
| - asyncio.gather inside each worker              |
+--------------------------------------------------+
             |
             v
+---------------------------+
| Candidate proofs          |
| + self-evaluation         |
+---------------------------+
             |
             v
+---------------------------+
| Build verification tasks  |
| proof_verification        |
+---------------------------+
             |
             v
+--------------------------------------------------+
| Parallel proof verification                      |
| generate.py                                      |
| - multiprocess request dispatch                  |
| - async API calls per worker                     |
+--------------------------------------------------+
             |
             v
+---------------------------+
| Score each proof          |
| 0 / 0.5 / 1               |
+---------------------------+
             |
             v
        +-----------+
        | Skip meta |
        | verify?   |
        +-----------+
          |       |
       No |       | Yes
          v       v
+---------------------------+     +---------------------------+
| Meta verification         |     | Aggregate proof quality   |
| Check rating reasonableness|    | directly                  |
+---------------------------+     +---------------------------+
          |                           ^
          v                           |
+--------------------------------------------------+
| Parallel proof aggregation / refinement prep     |
| main.py                                          |
| - multiprocessing.Pool(cpu_count)                |
| - merge ratings, proof pool, dependency ids      |
+--------------------------------------------------+
             |
             v
+---------------------------+
| Update proof pool         |
| store best proofs         |
+---------------------------+
             |
             v
    +------------------------------+
    | Any proof near full score    |
    | or max rounds reached?       |
    +------------------------------+
          |                    |
       Yes|                    |No
          v                    v
+-------------------+   +---------------------------+
| Write final output|   | Sample best proofs        |
+-------------------+   | and feedback              |
                        +---------------------------+
                                     |
                                     v
                        +---------------------------+
                        | Build refinement prompts  |
                        | proof_refinement          |
                        +---------------------------+
                                     |
                                     v
                        back to parallel proof generation
```

关键并行点：

- 证明生成：多进程 worker + 每个 worker 内的异步模型请求。
- 证明评分：沿用同样的多进程与异步调用模式。
- 证明聚合与精修准备：`main.py` 用进程池并行处理题目级聚合任务。
