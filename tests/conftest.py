import os

os.environ["LLM_FAKE"] = "true"
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

import pytest

from app.classifier import Classifier
from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(llm_fake=True)


@pytest.fixture
def classifier(settings: Settings) -> Classifier:
    return Classifier(settings)
