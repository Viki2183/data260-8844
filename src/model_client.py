from typing import Any

from langchain_ollama import ChatOllama


class ModelClient:
    """Reusable Ollama model adapter with token accounting."""

    def __init__(
        self,
        model: str = "qwen3:8b",
        temperature: float = 0.0,
        base_url: str = "http://localhost:11434",
        json_mode: bool = True,
        reasoning: bool | None = None,
        timeout_s: float | None = None,
        num_predict: int | None = None,
    ) -> None:
        self.model_name = model
        self.temperature = temperature

        ollama_options: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "base_url": base_url,
            "num_ctx": 2048,
            "format": "json" if json_mode else None,
        }
        # Omit these options by default so existing callers retain their
        # original ChatOllama behavior.
        if reasoning is not None:
            ollama_options["reasoning"] = reasoning
        if timeout_s is not None:
            if timeout_s <= 0:
                raise ValueError("timeout_s must be greater than zero")
            ollama_options["client_kwargs"] = {"timeout": float(timeout_s)}
        if num_predict is not None:
            if num_predict <= 0:
                raise ValueError("num_predict must be greater than zero")
            ollama_options["num_predict"] = num_predict

        self.model = ChatOllama(**ollama_options)

        self.turn_count = 0
        self.cumulative_input_tokens = 0
        self.cumulative_output_tokens = 0

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Send messages to Ollama through one stable interface."""

        model = self.model

        if tools:
            model = model.bind_tools(tools)

        response = model.invoke(messages)

        usage = response.usage_metadata or {}
        metadata = response.response_metadata or {}

        input_tokens = int(
            usage.get(
                "input_tokens",
                metadata.get("prompt_eval_count", 0),
            )
        )

        output_tokens = int(
            usage.get(
                "output_tokens",
                metadata.get("eval_count", 0),
            )
        )

        total_tokens = int(
            usage.get(
                "total_tokens",
                input_tokens + output_tokens,
            )
        )

        self.turn_count += 1
        self.cumulative_input_tokens += input_tokens
        self.cumulative_output_tokens += output_tokens

        token_usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

        print(
            "Turn token usage: "
            f"input={input_tokens}, "
            f"output={output_tokens}, "
            f"total={total_tokens}"
        )

        return {
            "content": str(response.content),
            "usage": token_usage,
        }

    def stats(self, history: list[dict[str, str]]) -> dict[str, int]:
        """Return statistics without changing conversation history."""

        return {
            "turn_count": self.turn_count,
            "cumulative_input_tokens":
                self.cumulative_input_tokens,
            "cumulative_output_tokens":
                self.cumulative_output_tokens,
            "cumulative_total_tokens":
                self.cumulative_input_tokens
                + self.cumulative_output_tokens,
            "serialized_history_length":
                len(str(history)),
        }

    def print_final_stats(self) -> None:
        """Print cumulative counts when the program exits."""

        print("\nCumulative model statistics:")
        print(f"Turns: {self.turn_count}")
        print(
            "Input tokens: "
            f"{self.cumulative_input_tokens}"
        )
        print(
            "Output tokens: "
            f"{self.cumulative_output_tokens}"
        )
        print(
            "Total tokens: "
            f"{self.cumulative_input_tokens + self.cumulative_output_tokens}"
        )
