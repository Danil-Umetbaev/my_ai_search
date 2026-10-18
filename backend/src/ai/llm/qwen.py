import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from src.ai.llm.base import LLMProvider
from src.schemas.llm import LLMAnswerSchema
from src.core.logging import log_execution_time
from src.utils.retry import load_with_retry

class QwenLLMProvider(LLMProvider):
    MODEL_NAME = "Qwen/Qwen3-1.7B"

    def __init__(self):
        self.device = "cuda"

        self.tokenizer, self.model = load_with_retry(
            loader=self._load_model,
            name="Qwen3 LLM",
            attempts=3,
            delay=5,
        )

    def _load_model(self):
        tokenizer = AutoTokenizer.from_pretrained(
            self.MODEL_NAME
        )

        model = AutoModelForCausalLM.from_pretrained(
            self.MODEL_NAME
        )

        model.to(self.device)
        model.eval()

        return tokenizer, model


    @log_execution_time("LLM answer generation")
    def generate(
        self,
        question: str,
        search_query: str,
        context: str,
    ) -> LLMAnswerSchema:

        messages = [
            {
                "role": "system",
                "content": """
    Ты отвечаешь на вопросы по документации SetRetail10.

    Используй только предоставленный контекст.

    Твоя задача — НАЙТИ в контексте информацию,
    которая отвечает на вопрос пользователя,
    и кратко передать её пользователю.

    ВАЖНО:

    Если в контексте есть определение, правило,
    назначение функции, настройка, условие,
    инструкция или другой факт,
    который отвечает на вопрос,
    ОБЯЗАТЕЛЬНО дай ответ.

    Не требуй, чтобы формулировка вопроса
    дословно совпадала с текстом документации.

    Если ответ содержится в одном или нескольких
    предложениях контекста — используй их.

    NOT_FOUND возвращай ТОЛЬКО если
    в контексте действительно нет информации,
    позволяющей ответить на вопрос.

    Не используй собственные знания.
    Не придумывай отсутствующие факты.

    Следуй типу вопроса:

    - "Что такое..." → дай определение.
    - "Для чего..." → укажи назначение.
    - "Где..." → укажи место настройки или раздел.
    - "Когда..." → укажи условие или момент.
    - "Как..." → опиши действие или последовательность.
    - "Какие..." → перечисли только то, о чём спросили.
    - "Можно ли..." → ответь да/нет и кратко поясни.

    Если спрашивают о серверных пользователях —
    не добавляй кассовых пользователей.

    Если спрашивают о кассовых пользователях —
    не добавляй серверных пользователей.

    Не отвечай только "да" или "нет",
    если вопрос не начинается с "можно ли".

    Не повторяй вопрос пользователя.

    Не пиши:
    "Ответ:"
    "Вопрос:"
    "Для ответа на вопрос:"

    Если информации нет, верни строго:

    NOT_FOUND
    """
            },
            {
                "role": "user",
                "content": f"""
    КОНТЕКСТ:

    {context}

    ВОПРОС:

    {question}

    Дай ответ только на вопрос пользователя.
    """
            }
        ]

        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )

        tokens = self.tokenizer(
            prompt,
            return_tensors="pt",
        ).to(self.device)

        with torch.inference_mode():

            answer_llm = self.model.generate(
                **tokens,
                max_new_tokens=200,
                do_sample=False,
            )

        tokens_prompt_len = (
            tokens["input_ids"].shape[-1]
        )

        result = self.tokenizer.decode(
            answer_llm[0][tokens_prompt_len:],
            skip_special_tokens=True,
        ).strip()

        if not result:
            return LLMAnswerSchema(
                answerable=False,
                answer=None,
            )

        normalized = (
            result
            .upper()
            .strip()
            .strip(" .!\"'")
        )

        if normalized == "NOT_FOUND":
            return LLMAnswerSchema(
                answerable=False,
                answer=None,
            )

        return LLMAnswerSchema(
            answerable=True,
            answer=result,
        )

    @log_execution_time("LLM query rewrite")
    def rewrite_query(self, question: str) -> str:
        normalized = " ".join(
            question.strip().lower().split()
        )

        # То, что мы можем определить без LLM наверняка.
        obvious_off_topic = {
            "как дела",
            "как дела?",
            "что делаешь",
            "что делаешь?",
            "привет",
            "привет!",
            "здарова",
            "здравствуйте",
            "ае",
            "ае?",
            "ахах",
            "ахахах",
            "ахахахах",
            "расскажи анекдот",
            "расскажи анекдот.",
            "посоветуй фильм на вечер",
            "посоветуй фильм на вечер.",
            "как приготовить борщ",
            "как приготовить борщ?",
            "почему небо голубое",
            "почему небо голубое?",
        }

        if normalized in obvious_off_topic:
            return "OFF_TOPIC"

        messages = [
            {
                "role": "system",
                "content": """
    Ты преобразуешь вопрос пользователя
    в поисковый запрос для корпоративной базы знаний.

    ТВОЯ ГЛАВНАЯ ЗАДАЧА:
    НЕ отвечать на вопрос,
    а подготовить хороший поисковый запрос.

    OFF_TOPIC используй ТОЛЬКО тогда,
    когда сообщение ОДНОЗНАЧНО не связано
    ни с работой, ни с корпоративными процессами,
    ни с программным обеспечением,
    ни с технической документацией.

    ВАЖНО:

    НЕ проверяй, есть ли ответ в базе знаний.

    Отсутствие ответа в документации
    НЕ означает OFF_TOPIC.

    Если вопрос выглядит рабочим,
    техническим или корпоративным,
    он НЕ является OFF_TOPIC,
    даже если ты не знаешь термин.

    Если сомневаешься —
    НЕ используй OFF_TOPIC.

    Любые вопросы про:
    - SetRetail10;
    - SetCentrum;
    - POS;
    - SetTouch;
    - кассы;
    - товары;
    - чеки;
    - оплаты;
    - возвраты;
    - пользователей;
    - роли;
    - привилегии;
    - справочники;
    - алкоголь;
    - ЕГАИС;
    - весы;
    - PLU;
    - штрихкоды;
    - обновления;
    - МУК;
    - настройки;
    - интерфейс;
    - магазины;
    - торговую сеть;
    - Active Directory;
    - оборудование;
    - действия сотрудников;
    - внутренние процессы компании

    считай потенциально рабочими
    и НЕ помечай OFF_TOPIC.

    Также НЕ являются OFF_TOPIC
    рабочие вопросы, ответа на которые
    может не быть в документации.

    Например:

    Вопрос:
    Как оформить отпуск сотруднику?
    Результат:
    Как оформить отпуск сотруднику?

    Вопрос:
    Как настроить Wi-Fi в офисе?
    Результат:
    Как настроить Wi-Fi в офисе?

    Вопрос:
    Какая зарплата у директора?
    Результат:
    Какая зарплата у директора?

    Эти запросы потом сможет отклонить
    сама система поиска, если ответа нет.

    OFF_TOPIC:

    Вопрос:
    Как дела?
    Результат:
    OFF_TOPIC

    Вопрос:
    Расскажи анекдот
    Результат:
    OFF_TOPIC

    Вопрос:
    Как приготовить борщ?
    Результат:
    OFF_TOPIC

    Вопрос:
    Почему небо голубое?
    Результат:
    OFF_TOPIC

    Вопрос:
    Абракадабра шмяк 123 крокодил
    Результат:
    OFF_TOPIC


    Если запрос рабочий,
    верни ОДИН короткий поисковый запрос.

    Правила переписывания:

    - сохраняй исходный смысл;
    - не отвечай на вопрос;
    - не придумывай новые факты;
    - исправляй очевидные опечатки;
    - убирай разговорный мусор;
    - сохраняй технические термины;
    - если вопрос уже сформулирован хорошо,
    меняй его минимально;
    - если пользователь спрашивает "что",
    сохрани "что";
    - если спрашивает "где",
    сохрани "где";
    - если спрашивает "как",
    сохрани "как";
    - если спрашивает "можно ли",
    сохрани "можно ли".

    Примеры:

    Вопрос:
    Что такое штучный товар в SetRetail10?
    Результат:
    Что такое штучный товар в SetRetail10?

    Вопрос:
    Какие роли кассовых пользователей создаются по умолчанию?
    Результат:
    Какие роли кассовых пользователей создаются по умолчанию в SetRetail10?

    Вопрос:
    Можно ли использовать Active Directory для авторизации пользователей?
    Результат:
    Можно ли использовать Active Directory для авторизации пользователей SetRetail10?

    Вопрос:
    Какой порядок обновления SetCentrum, SetRetail и POS?
    Результат:
    Порядок обновления SetCentrum, SetRetail и POS

    Вопрос:
    Для чего нужен весовой модуль SetRetail10?
    Результат:
    Назначение весового модуля SetRetail10

    Вопрос:
    Можно ли формировать PLU на основе штрихкода?
    Результат:
    Можно ли формировать PLU на основе штрихкода в SetRetail10?

    Вопрос:
    Для чего нужна клавиша ОПЛАТЫ на клавиатурной кассе?
    Результат:
    Назначение клавиши ОПЛАТЫ на клавиатурной кассе SetRetail10
    """
            },
            {
                "role": "user",
                "content": f"""Вопрос:
    {question}

    Результат:"""
            }
        ]

        result = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False
        )

        tokens = self.tokenizer(
            result,
            return_tensors="pt"
        ).to(self.device)

        with torch.inference_mode():
            answer_llm = self.model.generate(
                **tokens,
                max_new_tokens=64,
                do_sample=False
            )

        tokens_prompt_len = tokens["input_ids"].shape[-1]

        answer = self.tokenizer.decode(
            answer_llm[0][tokens_prompt_len:],
            skip_special_tokens=True
        ).strip()

        if not answer:
            return question.strip()

        normalized_answer = (
            answer
            .upper()
            .strip()
            .strip(" .!\"'")
        )

        # Только ТОЧНОЕ совпадение.
        if normalized_answer == "OFF_TOPIC":
            return "OFF_TOPIC"

        return answer