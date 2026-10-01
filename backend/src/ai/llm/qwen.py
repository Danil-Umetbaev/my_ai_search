import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from src.ai.llm.base import LLMProvider

class QwenLLMProvider(LLMProvider):
    MODEL_NAME = "Qwen/Qwen3-0.6B"

    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
        self.model = AutoModelForCausalLM.from_pretrained(self.MODEL_NAME)
        if torch.cuda.is_available():
            self.device = 'cuda'
        else:
            self.device = 'cpu'
        self.model.to(self.device)
        self.model.eval()



    def generate(self, question: str, context: str) -> str:
        messages = [{'role': 'system', 'content': """Ты корпоративный AI-помощник.
                        Отвечай только на основании предоставленного контекста.
                        Если в контексте нет ответа, сообщи, что информации недостаточно.
                        Не придумывай факты."""},
                    {'role': 'user', 'content': f'Контекст: {context}, вопрос: {question}'}]

        result = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        tokens = self.tokenizer(result, return_tensors='pt')
        tokens = tokens.to(self.device)
        with torch.inference_mode():
            answer_llm = self.model.generate(**tokens, max_new_tokens=200)

        tokens_prompt_len = tokens['input_ids'].shape[-1]

        return self.tokenizer.decode(answer_llm[0][tokens_prompt_len:], skip_special_tokens=True).strip()
