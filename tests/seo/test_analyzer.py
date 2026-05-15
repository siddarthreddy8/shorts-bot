from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.seo.analyzer import generate
from src.seo.models import SeoMetadata

_VALID_JSON = json.dumps({
    "title": "The Shocking Truth About Hyderabad",
    "description": (
        "Hyderabad has a hidden history that most people never hear about. "
        "In this short, we uncover the secrets buried beneath the old city. "
        "Watch the full documentary — link in description."
    ),
    "hashtags": ["#hyderabad", "#history", "#shorts", "#india", "#documentary"],
    "thumbnail_phrases": ["You Won't Believe This", "The Secret Nobody Knows", "History Uncovered"],
    "niche": "history",
})


def _mock_client(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = resp
    return client


def test_generate_returns_seo_metadata():
    with patch("src.seo.analyzer._make_client", return_value=_mock_client(_VALID_JSON)), \
         patch("src.seo.analyzer.env", return_value="anthropic/claude-sonnet-4-6"):
        result = generate("A short script about Hyderabad.", "Hyderabad History", ["documentary"], "english")

    assert isinstance(result, SeoMetadata)
    assert result.title == "The Shocking Truth About Hyderabad"
    assert result.niche == "history"
    assert len(result.hashtags) == 5
    assert len(result.thumbnail_phrases) == 3
    assert result.thumbnail_phrase is None


def test_generate_strips_markdown_code_fences():
    wrapped = f"```json\n{_VALID_JSON}\n```"
    with patch("src.seo.analyzer._make_client", return_value=_mock_client(wrapped)), \
         patch("src.seo.analyzer.env", return_value="anthropic/claude-sonnet-4-6"):
        result = generate("script", "topic", ["comedy"], "english")

    assert result.title == "The Shocking Truth About Hyderabad"


def test_generate_retries_once_on_bad_json():
    bad_choice = MagicMock()
    bad_choice.message.content = "Not JSON at all, sorry."
    bad_resp = MagicMock()
    bad_resp.choices = [bad_choice]

    good_choice = MagicMock()
    good_choice.message.content = _VALID_JSON
    good_resp = MagicMock()
    good_resp.choices = [good_choice]

    client = MagicMock()
    client.chat.completions.create.side_effect = [bad_resp, good_resp]

    with patch("src.seo.analyzer._make_client", return_value=client), \
         patch("src.seo.analyzer.env", return_value="model"):
        result = generate("script", "topic", ["serious"], "hindi")

    assert client.chat.completions.create.call_count == 2
    assert result.niche == "history"


def test_generate_raises_after_two_failures():
    client = _mock_client("still not json")
    with patch("src.seo.analyzer._make_client", return_value=client), \
         patch("src.seo.analyzer.env", return_value="model"):
        with pytest.raises(ValueError, match="SEO analyzer failed after 2 attempts"):
            generate("script", "topic", ["explainer"], "english")
