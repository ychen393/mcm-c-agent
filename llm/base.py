from abc import ABC, abstractmethod
from dataclasses import dataclass
@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    usage: dict | None = None
class BaseLLM(ABC):
    @abstractmethod
    def invoke(self, messages: list[dict[str, str]]) -> LLMResponse: raise NotImplementedError
