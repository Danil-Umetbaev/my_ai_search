import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from src.ai.llm.base import LLMProvider

class QwenLLMProvider(LLMProvider):
    MODEL_NAME = "Qwen/Qwen3-1.7B"

    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
        self.model = AutoModelForCausalLM.from_pretrained(self.MODEL_NAME)
        if torch.cuda.is_available():
            self.device = 'cuda'
        else:
            self.device = 'cpu'
        self.model.to(self.device)
        self.model.eval()



    def generate(self, question: str, search_query: str, context: str) -> str:
        messages = [
            {
                'role': 'system',
                'content': """Ты — корпоративный помощник по документации SetRetail10.

    Твоя задача — ответить на ОРИГИНАЛЬНЫЙ вопрос пользователя, используя только предоставленный контекст.

    Правила:
    - главным является оригинальный вопрос пользователя;
    - поисковый запрос дан только как дополнительное уточнение терминов;
    - если поисковый запрос меняет или искажает смысл оригинального вопроса — игнорируй его;
    - используй только факты из контекста;
    - не придумывай информацию;
    - если в контексте есть информация, позволяющая ответить на вопрос, обязательно дай ответ;
    - ответ может быть сформулирован своими словами;
    - если нужная информация распределена между несколькими фрагментами контекста, объедини её;
    - если информации действительно недостаточно для ответа, напиши только: "Информация недостаточна.";
    - отвечай именно на то, что спросил пользователь;
    - ответ должен быть кратким и конкретным."""
            },
            {
                'role': 'user',
                'content': f"""Контекст:
    {context}

    Оригинальный вопрос пользователя:
    {question}

    Уточнённый поисковый запрос:
    {search_query}

    Ответ:"""
            }
        ]

        result = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False
        )

        tokens = self.tokenizer(result, return_tensors='pt').to(self.device)

        with torch.inference_mode():
            answer_llm = self.model.generate(
                **tokens,
                max_new_tokens=200,
                do_sample=False
            )

        tokens_prompt_len = tokens['input_ids'].shape[-1]

        return self.tokenizer.decode(
            answer_llm[0][tokens_prompt_len:],
            skip_special_tokens=True
        ).strip()

    def rewrite_query(self, question: str) -> str:
        messages = [
            {
                'role': 'system',
                'content': """Ты преобразуешь вопрос пользователя в короткий точный поисковый запрос для поиска по документации SetRetail10.

    Твоя задача — улучшить формулировку для поиска, НЕ изменяя смысл вопроса.

    Строгие правила:
    - не отвечай на вопрос;
    - верни только один поисковый запрос без пояснений;
    - не добавляй фактов, которых нет в вопросе;
    - исправляй очевидные опечатки;
    - убирай лишние разговорные слова;
    - сохраняй исходное намерение пользователя;
    - сохраняй тип вопроса;
    - если пользователь спрашивает "что", поисковый запрос тоже должен спрашивать "что";
    - если пользователь спрашивает "где", поисковый запрос тоже должен спрашивать "где";
    - если пользователь спрашивает "как", поисковый запрос тоже должен спрашивать "как";
    - если пользователь спрашивает "можно ли", не превращай вопрос в "как";
    - если речь идёт о разделе интерфейса, явно используй слово "раздел";
    - названия разделов и сущностей формулируй максимально явно;
    - при необходимости добавляй "SetRetail10" для уточнения контекста;
    - если исходный вопрос уже точный и понятный, не меняй его смысл и только минимально уточни формулировку.

    Примеры:

    Вопрос: Что находится в разделе "Справочники"?
    Запрос: Что находится в разделе «Справочники» в SetRetail10?

    Вопрос: Не могу найти раздел карты, где он находится?
    Запрос: Где находится раздел «Карты» в SetRetail10?

    Вопрос: где там справочники вообще
    Запрос: Где находится раздел «Справочники» в SetRetail10?

    Вопрос: как отменить оплату после печати чека
    Запрос: Как отменить оплату после печати чека в SetRetail10?

    Вопрос: какие ограничения у общепита
    Запрос: Какие ограничения есть при работе кассы в режиме общепита в SetRetail10?

    Вопрос: можно ли вернуть весовой товар
    Запрос: Можно ли вернуть весовой товар в SetRetail10?

    Вопрос: как выбрать язык интерфейса
    Запрос: Как выбрать язык интерфейса в SetRetail10?"""
            },
            {
                'role': 'user',
                'content': f"""Вопрос:
    {question}

    Поисковый запрос:"""
            }
        ]

        result = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False
        )

        tokens = self.tokenizer(result, return_tensors='pt').to(self.device)

        with torch.inference_mode():
            answer_llm = self.model.generate(
                **tokens,
                max_new_tokens=64,
                do_sample=False
            )

        tokens_prompt_len = tokens['input_ids'].shape[-1]

        return self.tokenizer.decode(
            answer_llm[0][tokens_prompt_len:],
            skip_special_tokens=True
        ).strip()