import hashlib
import json
import regex

def hash_problem_idx(question):
    return hashlib.sha256(question.encode()).hexdigest()

def read_data(path):
    items = []
    if path.endswith(".jsonl"):
        with open(path, "r") as file:
            for line in file:
                item = json.loads(line)
                items.append(item)
    else:
        items = json.load(open(path, "r"))
    return items

def extract_boxed_answers(text):
    answers = []
    for piece in text.split('boxed{')[1:]:
        n = 0
        for i in range(len(piece)):
            if piece[i] == '{':
                n += 1
            elif piece[i] == '}':
                n -= 1
                if n < 0:
                    if i + 1 < len(piece) and piece[i + 1] == '%':
                        answers.append(piece[: i + 1])
                    else:
                        answers.append(piece[:i])
                    break
    return answers

def _normalize_prover_output(text):
    text = text.strip()
    text = regex.sub(r"(^|\n)\s*\*+\s*Solution\s*\*+\s*\n", "\n## Solution\n", text)
    text = regex.sub(r"\n\s*\*+\s*Self Evaluation\s*\*+\s*\n", "\n## Self Evaluation\n", text)
    text = regex.sub(r"(^|\n)## Solution\s*\n", "\n## Solution\n", text)
    text = regex.sub(r"\n## Self Evaluation\s*\n", "\n## Self Evaluation\n", text)
    return text.strip()

def extract_solution(student):
    student = _normalize_prover_output(student)
    return regex.split(r"## Solution\s*\n", regex.split(r"\n## Self Evaluation\s*\n", student)[0])[1].strip()

def extract_self_eval(student):
    student = _normalize_prover_output(student)
    return regex.split(r"\n## Self Evaluation\s*\n", student)[1].strip()
