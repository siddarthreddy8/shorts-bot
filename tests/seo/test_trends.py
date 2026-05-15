from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.seo.models import SeoMetadata
from src.seo.trends import _score_keywords, _youtube_autocomplete, enrich


def _meta(**overrides) -> SeoMetadata:
    defaults = dict(
        title="Hyderabad Secret History",
        description="A description.",
        hashtags=["#low", "#high", "#medium"],
        thumbnail_phrases=["Shocked", "Nobody Knew", "History Exposed"],
        niche="history",
    )
    defaults.update(overrides)
    return SeoMetadata(**defaults)


# --- _score_keywords ---

def test_score_keywords_returns_average_interest():
    mock_pt = MagicMock()
    df = pd.DataFrame({"hyderabad": [60, 70, 80], "history": [20, 30, 25]})
    mock_pt.interest_over_time.return_value = df

    with patch("src.seo.trends.TrendReq", return_value=mock_pt):
        scores = _score_keywords(["hyderabad", "history"])

    assert scores["hyderabad"] == 70
    assert scores["history"] == 25


def test_score_keywords_skips_missing_columns():
    mock_pt = MagicMock()
    df = pd.DataFrame({"known": [50, 50]})
    mock_pt.interest_over_time.return_value = df

    with patch("src.seo.trends.TrendReq", return_value=mock_pt):
        scores = _score_keywords(["known", "unknown"])

    assert "known" in scores
    assert "unknown" not in scores


def test_score_keywords_returns_empty_on_pytrends_failure():
    with patch("src.seo.trends.TrendReq", side_effect=Exception("rate limited")):
        scores = _score_keywords(["any"])

    assert scores == {}


# --- _youtube_autocomplete ---

def test_youtube_autocomplete_returns_suggestion_strings():
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        "hyderabad history",
        [["hyderabad history 2024", {}], ["hyderabad old city", {}]],
    ]
    mock_resp.raise_for_status.return_value = None

    with patch("src.seo.trends.requests.get", return_value=mock_resp):
        results = _youtube_autocomplete("hyderabad history", "english")

    assert results == ["hyderabad history 2024", "hyderabad old city"]


def test_youtube_autocomplete_returns_empty_on_network_failure():
    with patch("src.seo.trends.requests.get", side_effect=Exception("timeout")):
        results = _youtube_autocomplete("anything", "hindi")

    assert results == []


# --- enrich ---

def test_enrich_puts_high_score_hashtag_first():
    # hashtags: #low (score 0), #high (score 85), #medium (score 32)
    base = _meta()

    mock_pt = MagicMock()
    df = pd.DataFrame({"low": [0, 0], "high": [80, 90], "medium": [30, 35]})
    mock_pt.interest_over_time.return_value = df

    mock_resp = MagicMock()
    mock_resp.json.return_value = ["q", []]
    mock_resp.raise_for_status.return_value = None

    with patch("src.seo.trends.TrendReq", return_value=mock_pt), \
         patch("src.seo.trends.requests.get", return_value=mock_resp):
        result = enrich(base, "hyderabad history", "english")

    assert result.hashtags[0] == "#high"
    assert result.hashtags[-1] == "#low"


def test_enrich_injects_autocomplete_tags():
    base = _meta(hashtags=["#hyderabad"])

    mock_pt = MagicMock()
    mock_pt.interest_over_time.return_value = pd.DataFrame()

    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        "q",
        [["brand new term", {}], ["another fresh term", {}]],
    ]
    mock_resp.raise_for_status.return_value = None

    with patch("src.seo.trends.TrendReq", return_value=mock_pt), \
         patch("src.seo.trends.requests.get", return_value=mock_resp):
        result = enrich(base, "topic", "english")

    assert "#brandnewterm" in result.hashtags
    assert "#anotherfreshterm" in result.hashtags


def test_enrich_does_not_duplicate_existing_hashtags():
    base = _meta(hashtags=["#hyderabad"])

    mock_pt = MagicMock()
    mock_pt.interest_over_time.return_value = pd.DataFrame()

    mock_resp = MagicMock()
    # "hyderabad" is already in hashtags → should not be added again
    mock_resp.json.return_value = ["q", [["hyderabad", {}], ["new one", {}]]]
    mock_resp.raise_for_status.return_value = None

    with patch("src.seo.trends.TrendReq", return_value=mock_pt), \
         patch("src.seo.trends.requests.get", return_value=mock_resp):
        result = enrich(base, "topic", "english")

    assert result.hashtags.count("#hyderabad") == 1


def test_enrich_returns_original_on_total_failure():
    base = _meta()

    with patch("src.seo.trends._score_keywords", side_effect=Exception("boom")):
        result = enrich(base, "topic", "english")

    assert result.hashtags == base.hashtags
    assert result.title == base.title
    assert result.niche == base.niche


def test_enrich_passthrough_fields_unchanged():
    base = _meta()

    mock_pt = MagicMock()
    mock_pt.interest_over_time.return_value = pd.DataFrame()

    mock_resp = MagicMock()
    mock_resp.json.return_value = ["q", []]
    mock_resp.raise_for_status.return_value = None

    with patch("src.seo.trends.TrendReq", return_value=mock_pt), \
         patch("src.seo.trends.requests.get", return_value=mock_resp):
        result = enrich(base, "topic", "english")

    assert result.title == base.title
    assert result.description == base.description
    assert result.niche == base.niche
    assert result.thumbnail_phrases == base.thumbnail_phrases
