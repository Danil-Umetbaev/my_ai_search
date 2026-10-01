from src.ai.llm.qwen import QwenLLMProvider

llm = QwenLLMProvider()

question = "Что находилось вдали за горизонтом?"

context = (
    "Вдали, за горизонтом, виднелись величественные горы, "
    "чьи вершины терялись в облаках."
)

result = llm.generate(question, context)

print(result)