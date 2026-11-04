import pytest

from aurora.generator import GeneratorConfig, SyntheticData, generate


@pytest.fixture(scope="session")
def data() -> SyntheticData:
    return generate(GeneratorConfig(seed=42))
