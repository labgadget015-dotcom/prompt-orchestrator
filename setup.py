"""Setup for prompt-orchestrator."""

from setuptools import setup, find_packages

setup(
    name="prompt-orchestrator",
    version="0.1.0",
    description="Prompt orchestration layer with agent implementations for the labgadget015-dotcom ecosystem",
    author="labgadget015-dotcom",
    python_requires=">=3.9",
    packages=find_packages(exclude=["tests*"]),
    package_data={
        "orchestrator": [],
        "": ["prompts/**/*.md"],
    },
    install_requires=[
        "requests>=2.31.0",
    ],
    extras_require={
        "llm": [
            "anthropic>=0.20.0",
        ],
        "core": [
            # Install manually: pip install git+https://github.com/labgadget015-dotcom/ai-analyze-think-act-core.git@main
            "ai-analyze-think-act-core",
        ],
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "gh-orchestrate=orchestrator.cli:main",
        ],
    },
)
