"""Tests for the Event Classifier."""


from app.intelligence.classifier import EventClassifier
from app.intelligence.ontology import EventCategory


class TestEventClassifier:
    """Tests for keyword-based event classification."""

    def setup_method(self):
        """Create a classifier without FinBERT for testing."""
        self.classifier = EventClassifier(use_finbert=False)

    def test_interest_rate_classification(self):
        cat = self.classifier.classify_category(
            "Fed raises rates by 25 bps",
            "The Federal Reserve raised the federal funds rate by 25 basis points."
        )
        assert cat == EventCategory.INTEREST_RATE_CHANGE

    def test_supply_chain_classification(self):
        cat = self.classifier.classify_category(
            "Major earthquake disrupts TSMC factories",
            "A 7.4 magnitude earthquake caused significant supply chain disruption."
        )
        assert cat == EventCategory.SUPPLY_CHAIN_DISRUPTION

    def test_earnings_surprise_classification(self):
        cat = self.classifier.classify_category(
            "Apple Q4 earnings beat expectations",
            "Apple reported quarterly revenue that exceeded expectations."
        )
        assert cat == EventCategory.EARNINGS_SURPRISE

    def test_merger_classification(self):
        cat = self.classifier.classify_category(
            "Microsoft announces acquisition of Activision",
            "Microsoft to acquire Activision Blizzard in $68.7B deal announced today."
        )
        assert cat == EventCategory.MERGER_ACQUISITION

    def test_natural_disaster_classification(self):
        cat = self.classifier.classify_category(
            "Hurricane approaches Florida",
            "A category 4 hurricane is expected to make landfall."
        )
        assert cat == EventCategory.NATURAL_DISASTER

    def test_geopolitical_classification(self):
        cat = self.classifier.classify_category(
            "US imposes new tariffs on China",
            "The US announced new trade war tariffs on Chinese goods."
        )
        assert cat == EventCategory.TRADE_WAR

    def test_unknown_defaults_to_other(self):
        cat = self.classifier.classify_category(
            "Some random article",
            "This doesn't match any category keywords at all."
        )
        assert cat == EventCategory.OTHER

    def test_cyber_attack_classification(self):
        cat = self.classifier.classify_category(
            "Major data breach at company",
            "Millions of user records exposed in a major data breach."
        )
        assert cat == EventCategory.CYBERSECURITY_BREACH


class TestFallbackSentiment:
    """Tests for the keyword-based sentiment fallback."""

    def setup_method(self):
        self.classifier = EventClassifier(use_finbert=False)

    def test_negative_sentiment(self):
        sentiment = self.classifier.score_sentiment(
            "Stock crash causes massive loss. Bearish outlook with decline expected."
        )
        assert sentiment["negative"] > sentiment["positive"]

    def test_positive_sentiment(self):
        sentiment = self.classifier.score_sentiment(
            "Earnings beat expectations with strong profit growth and bullish rally."
        )
        assert sentiment["positive"] > sentiment["negative"]

    def test_neutral_sentiment(self):
        sentiment = self.classifier.score_sentiment(
            "The company held a regular quarterly board meeting."
        )
        assert sentiment["neutral"] == 1.0

    def test_sentiment_scores_sum_to_one(self):
        sentiment = self.classifier.score_sentiment("Stock crash with strong growth signals.")
        total = sentiment["positive"] + sentiment["negative"] + sentiment["neutral"]
        assert abs(total - 1.0) < 0.01


class TestSeverityEstimation:
    """Tests for the heuristic severity scoring."""

    def setup_method(self):
        self.classifier = EventClassifier(use_finbert=False)

    def test_market_wide_high_severity(self):
        severity = self.classifier.estimate_severity(
            EventCategory.INTEREST_RATE_CHANGE,
            {"positive": 0.0, "negative": 0.9, "neutral": 0.1}
        )
        # Base 0.7 + (0.9 * 0.3) = 0.97 → clamped to 0.97
        assert severity >= 0.9

    def test_single_stock_low_severity(self):
        severity = self.classifier.estimate_severity(
            EventCategory.EARNINGS_SURPRISE,
            {"positive": 0.8, "negative": 0.1, "neutral": 0.1}
        )
        # Base 0.3 + (0.1 * 0.3) = 0.33
        assert severity < 0.5

    def test_severity_never_exceeds_one(self):
        severity = self.classifier.estimate_severity(
            EventCategory.MARKET_CRASH,
            {"positive": 0.0, "negative": 1.0, "neutral": 0.0}
        )
        assert severity <= 1.0
