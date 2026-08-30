import argparse
import json
import re
import time
from collections import Counter
from typing import Any

from src.model_client import ModelClient


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for",
    "from", "has", "have", "in", "is", "it", "of", "on", "or",
    "that", "the", "this", "to", "was", "were", "will", "with",
}


def clean_text(value: Any) -> str:
    """Remove markdown artifacts and normalize whitespace."""

    text = str(value or "")
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "").replace("`", "")
    return " ".join(text.split())


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract and parse the first JSON object in model output."""

    cleaned = clean_text(text)

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")

    if start == -1:
        return {}

    depth = 0
    in_string = False
    escaped = False

    for position in range(start, len(cleaned)):
        character = cleaned[position]

        if escaped:
            escaped = False
            continue

        if character == "\\":
            escaped = True
            continue

        if character == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1

            if depth == 0:
                candidate = cleaned[start:position + 1]

                try:
                    parsed = json.loads(candidate)
                    return parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError:
                    return {}

    return {}


def tokenize(text: str) -> list[str]:
    """Convert text into lowercase topical words."""

    words = re.findall(r"[a-zA-Z][a-zA-Z0-9.+_-]*", text.lower())

    return [
        word
        for word in words
        if word not in STOP_WORDS and len(word) > 1
    ]


def phrase_candidates(
    title: str,
    content: str,
    limit: int = 12,
) -> list[str]:
    """Create tag candidates using only the supplied input."""

    title_words = tokenize(title)
    all_words = tokenize(f"{title} {content}")

    phrases: list[str] = []

    for words in (title_words, all_words):
        for size in (3, 2):
            for index in range(len(words) - size + 1):
                phrase = " ".join(words[index:index + size])

                if phrase not in phrases:
                    phrases.append(phrase)

    frequencies = Counter(all_words)

    for word, _ in frequencies.most_common():
        if word not in phrases:
            phrases.append(word)

    return phrases[:limit]


def normalize_tag(tag: Any) -> str:
    return " ".join(tokenize(clean_text(tag)))[:60]


def tag_is_topical(tag: str, source_words: set[str]) -> bool:
    words = tokenize(tag)
    return bool(words) and all(word in source_words for word in words)


def limit_words(text: str, maximum: int) -> str:
    words = clean_text(text).split()
    return " ".join(words[:maximum])


def make_fallback_summary(title: str, content: str) -> str:
    source = clean_text(content) or clean_text(title)
    summary = limit_words(source, 25).rstrip(".!?")

    if not summary:
        summary = "The submitted content was reviewed"

    return summary + "."


def coerce_result(
    raw: Any,
    title: str,
    content: str,
    strict: bool,
) -> dict[str, Any]:
    """Force arbitrary model output into the required schema."""

    obj = raw if isinstance(raw, dict) else {}
    data = obj.get("data", {})

    if not isinstance(data, dict):
        data = {}

    possible_tags = data.get("tags", obj.get("tags", []))

    if not isinstance(possible_tags, list):
        possible_tags = []

    source_words = set(tokenize(f"{title} {content}"))
    candidates = phrase_candidates(title, content)

    tags: list[str] = []

    for possible_tag in possible_tags:
        tag = normalize_tag(possible_tag)

        if (
            tag
            and tag_is_topical(tag, source_words)
            and tag not in tags
        ):
            tags.append(tag)

    for candidate in candidates:
        if len(tags) == 3:
            break

        if candidate not in tags:
            tags.append(candidate)

    while len(tags) < 3:
        tags.append(f"topic {len(tags) + 1}")

    tags = tags[:3]

    if strict:
        multiword_count = sum(
            1 for tag in tags if len(tag.split()) >= 2
        )

        if multiword_count < 2:
            replacements = [
                candidate
                for candidate in candidates
                if len(candidate.split()) >= 2
                and candidate not in tags
            ]

            for replacement in replacements:
                for index, tag in enumerate(tags):
                    if len(tag.split()) == 1:
                        tags[index] = replacement
                        break

                multiword_count = sum(
                    1 for tag in tags if len(tag.split()) >= 2
                )

                if multiword_count >= 2:
                    break

    summary = clean_text(
        data.get("summary", obj.get("summary", ""))
    )

    summary = summary.replace("...", "")
    summary = limit_words(summary, 25).rstrip(".!?")

    if not summary:
        summary = make_fallback_summary(title, content).rstrip(".")

    summary += "."

    message = limit_words(
        obj.get("message", "Tags and summary prepared."),
        60,
    )

    if not message:
        message = "Tags and summary prepared."

    thought = clean_text(obj.get("thought", ""))

    issues = data.get("issues", obj.get("issues", []))

    if not isinstance(issues, list):
        issues = [clean_text(issues)]

    return {
        "thought": thought,
        "message": message,
        "data": {
            "tags": tags,
            "summary": summary,
            "issues": [
                clean_text(issue)
                for issue in issues
                if clean_text(issue)
            ],
        },
    }


def call_agent(
    client: ModelClient,
    name: str,
    system_prompt: str,
    task: str,
    title: str,
    content: str,
    context: list[dict[str, Any]],
    strict: bool,
) -> tuple[dict[str, Any], float]:
    """Call one agent through the shared model adapter."""

    user_prompt = {
        "task": task,
        "title": title,
        "content": content,
        "previous_agent_outputs": context,
        "required_output": {
            "thought": "string",
            "message": "non-empty string of at most 60 words",
            "data": {
                "tags": "exactly three topical tags",
                "summary": "one sentence of at most 25 words",
                "issues": "array",
            },
        },
    }

    messages = [
        {
            "role": "system",
            "content": (
                system_prompt
                + " Return only one valid JSON object. "
                + "Do not use markdown or code fences."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(user_prompt),
        },
    ]

    started = time.perf_counter()
    response = client.complete(messages)
    latency_ms = (time.perf_counter() - started) * 1000

    parsed = extract_json_object(response["content"])
    result = coerce_result(
        parsed,
        title,
        content,
        strict,
    )

    print(f"\n--- {name} ({latency_ms:.0f} ms) ---")
    print(json.dumps(result, indent=2))

    return result, latency_ms


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--title", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--strict", action="store_true")

    args = parser.parse_args()

    client = ModelClient(
        model=args.model,
        temperature=args.temperature,
    )

    task = (
        "Derive exactly three topical tags and a one-sentence "
        "summary from the supplied title and content. "
        "Do not use fixed domain keywords."
    )

    transcript: list[dict[str, Any]] = []

    planner, planner_latency = call_agent(
        client=client,
        name="Planner",
        system_prompt=(
            "You are the Planner. Propose exactly three distinct "
            "topical tags and a summary of at most 25 words."
        ),
        task=task,
        title=args.title,
        content=args.content,
        context=[],
        strict=args.strict,
    )

    transcript.append({
        "agent": "Planner",
        "output": planner,
        "latency_ms": round(planner_latency, 2),
    })

    reviewer, reviewer_latency = call_agent(
        client=client,
        name="Reviewer",
        system_prompt=(
            "You are the Reviewer. Check whether the Planner's "
            "tags come from the input, whether there are exactly "
            "three tags, and whether the summary has at most "
            "25 words. Correct problems and list detected issues."
        ),
        task=task,
        title=args.title,
        content=args.content,
        context=transcript,
        strict=args.strict,
    )

    transcript.append({
        "agent": "Reviewer",
        "output": reviewer,
        "latency_ms": round(reviewer_latency, 2),
    })

    finalizer, finalizer_latency = call_agent(
        client=client,
        name="Finalizer",
        system_prompt=(
            "Perform the finalization step using the Planner and "
            "Reviewer outputs. Return exactly three tags, a summary "
            "of at most 25 words, and an empty issues array."
        ),
        task=task,
        title=args.title,
        content=args.content,
        context=transcript,
        strict=args.strict,
    )

    finalizer["data"]["issues"] = []

    print("\n--- Finalized Output ---")
    print(json.dumps(finalizer, indent=2))

    publish_package = {
        "title": args.title,
        "email": args.email,
        "content": args.content,
        "agents": {
            "transcript": transcript,
            "final": finalizer["data"],
        },
        "submissionDate": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        ),
        "temperature": args.temperature,
        "model": args.model,
        "finalization_latency_ms": round(
            finalizer_latency,
            2,
        ),
    }

    print("\n--- Publish Package ---")
    print(json.dumps(publish_package, indent=2))

    client.print_final_stats()


if __name__ == "__main__":
    main()