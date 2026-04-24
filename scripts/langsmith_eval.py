"""离线评估脚本：批量调用 /chat/reply，并可选上传 LangSmith 数据集。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from observability import TraceSanitizer, get_langsmith_service


def load_cases(path: Path) -> list[dict[str, Any]]:
    """load_cases 方法。
    
    目的：执行load_cases 方法相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    cases: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


def score_case(case: dict[str, Any], payload: dict[str, Any]) -> dict[str, float]:
    """score_case 方法。
    
    目的：执行score_case 方法相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    reply = str(payload.get("reply", ""))
    trace = payload.get("trace", {}) if isinstance(payload.get("trace"), dict) else {}
    safety_level = str(trace.get("safety_level", "low"))

    scores = {
        "reply_non_empty": 1.0 if reply.strip() else 0.0,
        "safety_match": 1.0 if not case.get("expected_risk_level") or case["expected_risk_level"] == safety_level else 0.0,
        "contains_expected_phrase": 1.0,
    }
    expected_phrases = case.get("expected_contains") or []
    if expected_phrases:
        scores["contains_expected_phrase"] = 1.0 if any(phrase in reply for phrase in expected_phrases) else 0.0
    return scores


def upload_to_langsmith(dataset_name: str, results: list[dict[str, Any]]) -> None:
    """upload_to_langsmith 方法。
    
    目的：执行upload_to_langsmith 方法相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    service = get_langsmith_service()
    client = service.get_client()
    if client is None:
        print("LangSmith 未配置或当前环境不可用，跳过上传。")
        return

    dataset = None
    try:
        for item in client.list_datasets(dataset_name=dataset_name):
            dataset = item
            break
    except Exception:
        dataset = None

    if dataset is None:
        dataset = client.create_dataset(dataset_name=dataset_name, description="AI Love 离线评估集")

    examples = []
    for result in results:
        examples.append({
            "inputs": TraceSanitizer.sanitize_payload(result["request"]),
            "outputs": TraceSanitizer.sanitize_payload(result["response"]),
            "metadata": {
                "scores": result["scores"],
                "case_id": result["case"].get("case_id", ""),
            },
        })

    try:
        client.create_examples(dataset_id=dataset.id, examples=examples)
        print(f"已上传 {len(examples)} 条评估样本到 LangSmith 数据集：{dataset_name}")
    except Exception as exc:
        print(f"LangSmith 数据集上传失败：{exc}")


def main() -> None:
    """main 方法。
    
    目的：执行main 方法相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    parser = argparse.ArgumentParser(description="批量执行 AI Love 聊天评估")
    parser.add_argument("--input", required=True, help="JSONL 测试集路径")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="后端服务地址")
    parser.add_argument("--dataset-name", default="ai-love-chat-eval", help="LangSmith 数据集名称")
    parser.add_argument("--upload", action="store_true", help="是否上传结果到 LangSmith")
    args = parser.parse_args()

    cases = load_cases(Path(args.input))
    results: list[dict[str, Any]] = []

    with httpx.Client(base_url=args.base_url, timeout=60.0) as client:
        for index, case in enumerate(cases, start=1):
            request_payload = {
                "session_id": case.get("session_id", f"eval-session-{index}"),
                "user_id": case.get("user_id", f"eval-user-{index}"),
                "message": case["message"],
                "mode": case.get("mode", "companion"),
            }
            response = client.post("/chat/reply", json=request_payload)
            response.raise_for_status()
            body = response.json()
            scores = score_case(case, body)
            results.append({
                "case": case,
                "request": request_payload,
                "response": body,
                "scores": scores,
            })
            print(json.dumps({"case_id": case.get("case_id", index), "scores": scores}, ensure_ascii=False))

    if args.upload:
        upload_to_langsmith(args.dataset_name, results)


if __name__ == "__main__":
    main()
