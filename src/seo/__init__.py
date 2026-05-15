from src.seo import analyzer, trends
from src.seo.models import SeoMetadata


def generate_and_enrich(
    script: str,
    topic_hint: str,
    styles: list[str],
    language: str,
) -> SeoMetadata:
    raw = analyzer.generate(script, topic_hint, styles, language)
    return trends.enrich(raw, topic_hint, language)


__all__ = ["generate_and_enrich", "SeoMetadata"]
