from src.seo.models import SeoMetadata


def test_seo_metadata_defaults_thumbnail_phrase_to_none():
    m = SeoMetadata(
        title="The Truth About Hyderabad",
        description="A detailed description about the historic city.",
        hashtags=["#hyderabad", "#history", "#shorts"],
        thumbnail_phrases=["Secret Revealed", "You Won't Believe", "History Shocked"],
        niche="history",
    )
    assert m.thumbnail_phrase is None


def test_seo_metadata_accepts_chosen_phrase():
    m = SeoMetadata(
        title="T",
        description="D",
        hashtags=["#test"],
        thumbnail_phrases=["p1", "p2", "p3"],
        niche="tech",
        thumbnail_phrase="p2",
    )
    assert m.thumbnail_phrase == "p2"


def test_seo_metadata_stores_all_fields():
    m = SeoMetadata(
        title="Breaking: Hyderabad's Hidden Past",
        description="Discover the secrets of the city.",
        hashtags=["#hyderabad", "#documentary"],
        thumbnail_phrases=["Shocking Truth", "Nobody Knew This", "History Exposed"],
        niche="history",
        thumbnail_phrase="Shocking Truth",
    )
    assert m.title == "Breaking: Hyderabad's Hidden Past"
    assert m.niche == "history"
    assert len(m.hashtags) == 2
    assert len(m.thumbnail_phrases) == 3
