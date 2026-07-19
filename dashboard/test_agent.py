"""
Test rapide de l'agent chatbot en ligne de commande, avant intégration
dans le dashboard Gradio — permet de valider le tool-calling et le
routage SQL/RAG indépendamment de l'interface.

Usage: docker compose exec dashboard uv run python test_agent.py
"""

from chatbot_agent import build_agent

TEST_QUESTIONS = [
    "How many active events are there right now?",
    "What is the most disrupted roadway?",
    "Are there any incidents mentioning a collision?",
]


def main() -> None:
    agent = build_agent()
    for question in TEST_QUESTIONS:
        print(f"\n{'='*60}")
        print(f"Q: {question}")
        print("=" * 60)
        result = agent.invoke({"input": question})
        print(f"\nA: {result['output']}")


if __name__ == "__main__":
    main()