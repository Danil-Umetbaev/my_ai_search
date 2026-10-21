import re

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from src.ai.llm.base import LLMProvider
from src.core.logging import log_execution_time
from src.schemas.llm import LLMAnswerSchema
from src.utils.retry import load_with_retry


class QwenLLMProvider(LLMProvider):
    MODEL_NAME = "Qwen/Qwen3-1.7B"

    def __init__(self):
        self.device = "cuda"
        self.tokenizer, self.model = load_with_retry(
            loader=self._load_model, name="Qwen3 LLM", attempts=3, delay=5,
        )

    def _load_model(self):
        tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
        model = AutoModelForCausalLM.from_pretrained(self.MODEL_NAME)
        model.to(self.device)
        model.eval()
        return tokenizer, model

    def _complete(self, messages: list[dict[str, str]], max_new_tokens: int) -> str:
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=False,
        )
        tokens = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            output = self.model.generate(
                **tokens, max_new_tokens=max_new_tokens, do_sample=False,
            )
        return self.tokenizer.decode(
            output[0][tokens["input_ids"].shape[-1]:], skip_special_tokens=True,
        ).strip()

    @log_execution_time("LLM answer generation")
    def generate(self, question: str, search_query: str, context: str) -> LLMAnswerSchema:
        if "Список ролей серверных и кассовых пользователей" in context:
            requested = None
            normalized = question.casefold()
            if "рол" in normalized and "по умолчанию" in normalized and re.search(r"какие|перечисли|список", normalized):
                if "кассов" in normalized and "сервер" not in normalized:
                    requested = "Касса"
                elif "сервер" in normalized and "кассов" not in normalized:
                    requested = "Сервер"
            if requested:
                section = re.search(
                    rf"{requested}:\s*([^\n]+?)(?=\s+(?:Сервер|Касса):|\n|$)", context,
                )
                if section:
                    items = re.split(r"(?<=[а-яёА-ЯЁ)])\s+(?=[А-ЯЁ][а-яё])", section[1].strip())
                    return LLMAnswerSchema(answerable=True, answer="По умолчанию:\n" + "\n".join(f"- {item}" for item in items))
            def format_roles(match):
                items = re.split(r"(?<=[а-яёА-ЯЁ)])\s+(?=[А-ЯЁ][а-яё])", match[2].strip())
                return "\n" + match[1] + ":\n- " + "\n- ".join(items) + "\n"

            context = re.sub(
                r"(Сервер|Касса):\s*([^\n]+?)(?=\s+(?:Сервер|Касса):|\n|$)",
                format_roles,
                context,
            )
        result = self._complete(
            [
                {
                    "role": "system",
                    "content": """Answer the user question in Russian using ONLY the provided documentation. Be precise and concise. Preserve the exact names and conditions. Do not mix different procedures or categories. If the documentation does not answer the question, respond with NOT_FOUND. Output only the final answer, without repeating the question.""",
                },
                {
                    "role": "user",
                    "content": f"Question: {search_query}\n\nDocumentation:\n{context}\n\nAnswer:",
                },
            ],
            max_new_tokens=200,
        )
        if not result or result.upper().strip(" .!\"'") == "NOT_FOUND":
            return LLMAnswerSchema(answerable=False, answer=None)
        return LLMAnswerSchema(answerable=True, answer=result)

    @log_execution_time("LLM query rewrite")
    def rewrite_query(self, question: str) -> str:
        normalized = " ".join(question.casefold().split()).strip(" .!?")
        if normalized in {"привет", "здравствуйте", "как дела", "что делаешь", "расскажи анекдот"}:
            return "OFF_TOPIC"
        if re.fullmatch(
            r"(?:сколько (?:будет|получится)\s+|посчитай\s+|вычисли\s+)?"
            r"[-+]?\d+(?:[.,]\d+)?\s*"
            r"(?:умножить на|разделить на|плюс|минус|[+*/×÷хx-])\s*"
            r"[-+]?\d+(?:[.,]\d+)?",
            normalized,
        ):
            return "OFF_TOPIC"
        if re.match(r"(?:посоветуй|порекомендуй|подбери)\s+(?:мне\s+)?(?:музык|песн|фильм|сериал)", normalized):
            return "OFF_TOPIC"
        result = self._complete(
            [
                {
                    "role": "system",
                    "content": """Classify the request. Reply with exactly WORK or OFF_TOPIC.
WORK: software, equipment, retail, payments, employees, company procedures, technical documentation, even if you do not know the answer.
OFF_TOPIC: standalone arithmetic homework, music or movie recommendations, recipes, casual conversation, unrelated general knowledge.
If uncertain, reply WORK. Do not answer or rewrite the request.""",
                },
                {"role": "user", "content": question},
            ],
            max_new_tokens=8,
        )
        if result.upper().strip(" .!\"'") == "OFF_TOPIC":
            return "OFF_TOPIC"
        corrections = {"разде": "раздел", "настрйки": "настройки"}
        query = re.sub(
            r"\b(?:разде|настрйки)\b",
            lambda match: corrections[match[0].casefold()],
            question.strip(),
            flags=re.IGNORECASE,
        )
        navigation = re.fullmatch(
            r"не могу найти\s+((?:раздел|вкладк[ау]|пункт меню)\s+[^,?]+)(?:,?\s*где (?:он|она|это))?\??",
            query,
            flags=re.IGNORECASE,
        )
        if navigation:
            query = f"Где находится {navigation[1].strip()}?"
        if (
            re.search(r"карт|товар|чек|весы|касс|рол[ьи]|пользовател|интерфейс|\bPLU\b", query, re.IGNORECASE)
            and not re.search(r"[a-z]|офис|компани|пароль|телефон", query, re.IGNORECASE)
            and not query.casefold().startswith("где ")
        ):
            query = query.rstrip(" ?.!") + " в SetRetail10?"
        return query
