import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
INFERENCE_DIR = ROOT_DIR / "inference"
sys.path.insert(0, str(INFERENCE_DIR))

from math_templates import math_templates  # noqa: E402


def hash_problem_idx(question: str) -> str:
    return hashlib.sha256(question.encode()).hexdigest()


def extract_boxed_answers(text: str) -> list[str]:
    answers = []
    for piece in text.split("boxed{")[1:]:
        depth = 0
        for i, ch in enumerate(piece):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth < 0:
                    answers.append(piece[:i])
                    break
    return answers


def normalize_prover_output(text: str) -> str:
    text = text.strip()
    text = re.sub(r"(^|\n)\s*\*+\s*Solution\s*\*+\s*\n", "\n## Solution\n", text)
    text = re.sub(r"\n\s*\*+\s*Self Evaluation\s*\*+\s*\n", "\n## Self Evaluation\n", text)
    text = re.sub(r"(^|\n)## Solution\s*\n", "\n## Solution\n", text)
    text = re.sub(r"\n## Self Evaluation\s*\n", "\n## Self Evaluation\n", text)
    return text.strip()


def extract_solution(student: str) -> str:
    student = normalize_prover_output(student)
    first_part = re.split(r"\n## Self Evaluation\s*\n", student)[0]
    parts = re.split(r"## Solution\s*\n", first_part)
    if len(parts) < 2:
        raise ValueError("solution section not found")
    return parts[1].strip()


def extract_self_eval(student: str) -> str:
    student = normalize_prover_output(student)
    parts = re.split(r"\n## Self Evaluation\s*\n", student)
    if len(parts) < 2:
        raise ValueError("self evaluation section not found")
    return parts[1].strip()


def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def read_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def call_openrouter(messages: list[dict], *, model: str, max_tokens: int, temperature: float) -> dict:
    api_key = os.environ["OPENROUTER_API_KEY"]
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://local.test",
            "X-Title": "deepseek-math-v2-memory-smoke",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter request failed: {exc.code} {body}") from exc


def normalize_model_output(response: dict) -> tuple[str, str, dict]:
    choice = response["choices"][0]
    message = choice["message"]
    content = message.get("content") or ""
    reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
    if reasoning:
        output = f"<think>\n{reasoning.strip()}\n</think>"
        if content:
            output += f"\n{content.strip()}"
    else:
        output = content.strip()
    return output.strip(), str(choice.get("finish_reason", "stop")).lower(), response.get("usage", {})


def safe_extract_proof_fields(raw_output: str) -> tuple[str, str, float]:
    proof = raw_output
    self_eval = "null"
    self_eval_score = 0.0
    if "</think>" in proof:
        proof = proof.split("</think>", 1)[1].strip()
    try:
        self_eval = extract_self_eval(proof).strip()
        proof = extract_solution(proof).strip()
        scores = [s.strip() for s in extract_boxed_answers(self_eval) if s.strip()]
        if scores:
            self_eval_score = float(scores[-1])
    except Exception:
        proof = proof.strip()
        self_eval = "null"
        self_eval_score = 0.0
    return proof, self_eval, self_eval_score


def extract_rating_score(raw_rating: str) -> float:
    content = raw_rating
    if "</think>" in content:
        content = content.split("</think>", 1)[1].strip()
    scores = [s.strip() for s in extract_boxed_answers(content) if s.strip()]
    if not scores:
        return 0.0
    return float(scores[-1])


def build_refinement_message(question: str, proof: str, rating: str) -> str:
    summary = f"--- Solution 0 ---\n{proof}\n\n=== Evaluation 0 of Solution 0 ===\n{rating}"
    return math_templates["proof_refinement"].format(
        instruction=math_templates["proof_generation"].format(question=question.strip()).strip(),
        proofs_to_refine=summary.strip(),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_json", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model", default="nvidia/nemotron-3-super-120b-a12b:free")
    parser.add_argument("--proof_max_tokens", type=int, default=256)
    parser.add_argument("--verification_max_tokens", type=int, default=256)
    parser.add_argument("--refinement_max_tokens", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--force_refinement_demo", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input_json)
    output_dir = Path(args.output_dir)
    items = read_json(input_path)

    proof_gen_inputs = []
    proof_gen_outputs = []
    verification_inputs = []
    verification_outputs = []
    refinement_inputs = []
    refinement_outputs = []
    report = []

    for item in items:
        question = item["question"].strip()
        source_name = item.get("source_name", input_path.stem)
        problem_idx = str(item.get("problem_idx") or hash_problem_idx(question))

        proof_prompt = math_templates["proof_generation"].format(question=question)
        proof_record = {
            **item,
            "source_name": source_name,
            "problem_idx": problem_idx,
            "messages": [{"role": "user", "content": proof_prompt}],
        }
        proof_gen_inputs.append(proof_record)

        proof_response = call_openrouter(
            proof_record["messages"],
            model=args.model,
            max_tokens=args.proof_max_tokens,
            temperature=args.temperature,
        )
        proof_output, proof_finish_reason, proof_usage = normalize_model_output(proof_response)
        proof, self_eval, self_eval_score = safe_extract_proof_fields(proof_output)
        proof_result = {
            **proof_record,
            "output": proof_output,
            "finish_reason": proof_finish_reason,
            "proof": proof,
            "self_eval": self_eval,
            "self_eval_score": self_eval_score,
            "usage": proof_usage,
        }
        proof_gen_outputs.append(proof_result)

        verification_prompt = math_templates["proof_verification"].format(
            statement=question,
            proof=proof,
        )
        verification_record = {
            **item,
            "source_name": source_name,
            "problem_idx": problem_idx,
            "proof": proof,
            "self_eval": self_eval,
            "self_eval_score": self_eval_score,
            "messages": [{"role": "user", "content": verification_prompt}],
        }
        verification_inputs.append(verification_record)

        verification_response = call_openrouter(
            verification_record["messages"],
            model=args.model,
            max_tokens=args.verification_max_tokens,
            temperature=0,
        )
        verification_output, verification_finish_reason, verification_usage = normalize_model_output(verification_response)
        score = extract_rating_score(verification_output)
        verification_result = {
            **verification_record,
            "output": verification_output,
            "finish_reason": verification_finish_reason,
            "score": score,
            "usage": verification_usage,
        }
        verification_outputs.append(verification_result)

        proof_pool_record = {
            "proof": proof,
            "meanscore": score,
            "score2ratings": {
                str(score): [
                    {
                        "rating": verification_output,
                        "score": score,
                    }
                ]
            },
            "self_eval": {
                "self_eval": self_eval,
                "self_eval_score": self_eval_score,
            },
            "proof_id": 1,
            "dep_proof_ids": [],
            "round_idx": 1,
        }
        proof_pool_path = output_dir / "proof_pool" / source_name / f"{problem_idx}.jsonl"
        write_jsonl(proof_pool_path, [proof_pool_record])

        should_build_refinement = args.force_refinement_demo or score < 1.0
        refinement_result = None
        if should_build_refinement:
            refinement_prompt = build_refinement_message(question, proof, verification_output)
            refinement_record = {
                **item,
                "source_name": source_name,
                "problem_idx": problem_idx,
                "dep_proof_ids": [1],
                "messages": [{"role": "user", "content": refinement_prompt}],
            }
            refinement_inputs.append(refinement_record)
            refinement_response = call_openrouter(
                refinement_record["messages"],
                model=args.model,
                max_tokens=args.refinement_max_tokens,
                temperature=args.temperature,
            )
            refinement_output, refinement_finish_reason, refinement_usage = normalize_model_output(refinement_response)
            refinement_result = {
                **refinement_record,
                "output": refinement_output,
                "finish_reason": refinement_finish_reason,
                "usage": refinement_usage,
            }
            refinement_outputs.append(refinement_result)

        report.append(
            {
                "question": question,
                "problem_idx": problem_idx,
                "proof_pool_path": str(proof_pool_path),
                "score": score,
                "self_eval_score": self_eval_score,
                "forced_refinement_demo": args.force_refinement_demo and score >= 1.0,
                "refinement_generated": refinement_result is not None,
            }
        )

    write_jsonl(output_dir / "proof_gen_R1" / "input.jsonl", proof_gen_inputs)
    write_jsonl(output_dir / "proof_gen_R1" / "output.jsonl", proof_gen_outputs)
    write_jsonl(output_dir / "proof_verification_R1" / "input.jsonl", verification_inputs)
    write_jsonl(output_dir / "proof_verification_R1" / "output.jsonl", verification_outputs)
    if refinement_inputs:
        write_jsonl(output_dir / "proof_gen_R2" / "input.jsonl", refinement_inputs)
    if refinement_outputs:
        write_jsonl(output_dir / "proof_gen_R2" / "output.jsonl", refinement_outputs)

    summary = {
        "model": args.model,
        "input_json": str(input_path),
        "output_dir": str(output_dir),
        "items": report,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
