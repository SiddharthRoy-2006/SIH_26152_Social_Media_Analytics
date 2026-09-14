"""
Final Stabilization Tests for SocialIQ Analytics.
Tests:
1. Instagram Connector search & comments via Meta Graph API.
2. AI Chatbot context grounding, question classification, and missing metric handling.
3. Chat route parity (/api/chat and /api/chat/message).
4. YouTube OAuth status and credentials layer mapping.
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app import app
from backend.connectors.meta_connectors import InstagramConnector
from backend.schemas import ChatRequest, ChatResponse
from backend.services.ai_chat_service import process_chat_message


import asyncio
import httpx


class TestInstagramConnectorSearch(unittest.TestCase):
    """Verify Instagram search implementation with Meta Graph API."""

    def setUp(self):
        self.connector = InstagramConnector(
            access_token="test_meta_token_xyz",
            instagram_account_id="17841400000000001",
        )

    def test_search_not_connected(self):
        connector = InstagramConnector(access_token="")
        results = asyncio.run(connector.search("education"))
        self.assertEqual(results, [])

    @patch.object(httpx.AsyncClient, "get")
    def test_search_hashtag_flow(self, mock_get):
        recent_ts = datetime.now(timezone.utc).isoformat()

        # Mock responses for hashtag search -> hashtag recent media
        hashtag_discovery_resp = MagicMock()
        hashtag_discovery_resp.status_code = 200
        hashtag_discovery_resp.json.return_value = {"data": [{"id": "17843790001"}]}

        hashtag_media_resp = MagicMock()
        hashtag_media_resp.status_code = 200
        hashtag_media_resp.json.return_value = {
            "data": [
                {
                    "id": "media_post_101",
                    "caption": "Exciting educational update #NEP2020",
                    "media_type": "IMAGE",
                    "permalink": "https://www.instagram.com/p/B101/",
                    "timestamp": recent_ts,
                    "like_count": 240,
                    "comments_count": 18,
                }
            ]
        }

        # Account media fallback returns empty
        acct_media_resp = MagicMock()
        acct_media_resp.status_code = 200
        acct_media_resp.json.return_value = {"data": []}

        mock_get.side_effect = [
            hashtag_discovery_resp,
            hashtag_media_resp,
            acct_media_resp,
        ]

        records = asyncio.run(self.connector.search("NEP2020", limit=10))
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec.platform, "Instagram")
        self.assertEqual(rec.content_id, "media_post_101")
        self.assertEqual(rec.text, "Exciting educational update #NEP2020")
        self.assertEqual(rec.engagement.get("likes"), 240)
        self.assertEqual(rec.engagement.get("comments"), 18)

    @patch.object(httpx.AsyncClient, "get")
    def test_search_account_media_fallback(self, mock_get):
        recent_ts = datetime.now(timezone.utc).isoformat()

        # Hashtag discovery returns empty -> fall back to account media
        hashtag_empty_resp = MagicMock()
        hashtag_empty_resp.status_code = 200
        hashtag_empty_resp.json.return_value = {"data": []}

        account_media_resp = MagicMock()
        account_media_resp.status_code = 200
        account_media_resp.json.return_value = {
            "data": [
                {
                    "id": "media_acc_202",
                    "caption": "Our campus workshop on higher education guidelines",
                    "media_type": "VIDEO",
                    "permalink": "https://www.instagram.com/p/B202/",
                    "timestamp": recent_ts,
                    "like_count": 510,
                    "comments_count": 35,
                }
            ]
        }

        mock_get.side_effect = [
            hashtag_empty_resp,
            account_media_resp,
        ]

        records = asyncio.run(self.connector.search("education", limit=5))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].content_id, "media_acc_202")
        self.assertEqual(records[0].engagement.get("likes"), 510)


class TestAIChatbotGrounding(unittest.TestCase):
    """Verify chatbot answers strictly from dashboard_context and handles unsupported metrics."""

    def setUp(self):
        self.context = {
            "topic": "Digital India",
            "platform": "YouTube",
            "data_source": "LIVE",
            "metrics": {
                "total_volume": 2840,
                "engagement_rate": "4.2%",
                "reach": 98500,
                "growth_rate": "+15.8%",
                "likes": 3600,
                "comments": 420,
                "shares": 0,
                "shares_supported": False,
                "followers_supported": False,
            },
            "sentiment": {"positive": 68.0, "neutral": 22.0, "negative": 10.0},
            "trends": [
                {"topic": "#DigitalInclusion", "mentions": 840, "growth": 25.5},
                {"topic": "#SmartGovernance", "mentions": 410, "growth": 14.2},
            ],
            "influencers": [
                {"name": "TechGov India", "reach": 45000, "platform": "YouTube"}
            ],
            "insights": [
                {
                    "title": "Adoption Velocity",
                    "summary": "Rural connectivity content is generating twice the normal comments.",
                    "evidence": "+112% comment ratio",
                    "recommendation": "Produce regional language tutorials",
                }
            ],
        }

    def test_engagement_rate_grounded(self):
        req = ChatRequest(
            message="What is the current engagement rate?",
            dashboard_context=self.context,
        )
        res = process_chat_message(req)
        self.assertIn("4.2%", res.answer)
        self.assertIn("98,500", res.answer)
        self.assertIn("YouTube", res.answer)
        self.assertEqual(res.tool_used, "get_metrics")
        self.assertTrue(res.grounded)

    def test_topic_identification(self):
        req = ChatRequest(
            message="Which topic did I search?",
            dashboard_context=self.context,
        )
        res = process_chat_message(req)
        self.assertIn("Digital India", res.answer)
        self.assertIn("YouTube", res.answer)
        self.assertEqual(res.tool_used, "get_active_topic")

    def test_unsupported_metrics_truthful_denial(self):
        # Followers
        req_fol = ChatRequest(
            message="How many followers do they have?",
            dashboard_context=self.context,
        )
        res_fol = process_chat_message(req_fol)
        self.assertIn("That metric is not available from the current data", res_fol.answer)

        # Shares
        req_shares = ChatRequest(
            message="How many shares did this get?",
            dashboard_context=self.context,
        )
        res_shares = process_chat_message(req_shares)
        self.assertIn("That metric is not available from the current data", res_shares.answer)

    def test_ai_insights_card_retrieval(self):
        req = ChatRequest(
            message="Show AI insights for this topic",
            dashboard_context=self.context,
        )
        res = process_chat_message(req)
        self.assertIn("Adoption Velocity", res.answer)
        self.assertIn("Rural connectivity content", res.answer)
        self.assertEqual(res.tool_used, "get_ai_insights")

    def test_trending_topics_filtering(self):
        req = ChatRequest(
            message="What are the trending topics?",
            dashboard_context=self.context,
        )
        res = process_chat_message(req)
        self.assertIn("#DigitalInclusion", res.answer)
        self.assertIn("#SmartGovernance", res.answer)
        # Ensure generic buzzwords like "funny" or "viral" are not fabricated
        self.assertNotIn("funny", res.answer.lower())


class TestChatEndpointParity(unittest.TestCase):
    """Verify both /api/chat and /api/chat/message work with identical behavior."""

    def setUp(self):
        self.client = TestClient(app)

    def test_chat_message_endpoint(self):
        resp = self.client.post(
            "/api/chat/message",
            json={"message": "What is the engagement rate formula?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("answer", data)
        self.assertTrue(data.get("grounded"))

    def test_chat_root_endpoint(self):
        resp = self.client.post(
            "/api/chat",
            json={"message": "What is the engagement rate formula?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("answer", data)
        self.assertTrue(data.get("grounded"))


class TestChatbotConversationalAndContext(unittest.TestCase):
    """Verify period, platform, greetings, creator, CS concepts, and general knowledge."""

    def setUp(self):
        self.context = {
            "topic": "Renewable Energy",
            "platform": "YouTube",
            "period": "Last 7 Days (7d)",
            "chart_period": "7d",
            "data_source": "LIVE",
            "metrics": {
                "total_volume": 1200,
                "reach": 50000,
                "engagement_rate": 3.8,
            },
        }

    def test_period_identification(self):
        req = ChatRequest(
            message="What period am I analyzing?",
            dashboard_context=self.context,
        )
        res = process_chat_message(req)
        self.assertIn("Last 7 Days (7d)", res.answer)
        self.assertEqual(res.tool_used, "get_active_period")

    def test_platform_identification(self):
        req = ChatRequest(
            message="What platform am I using?",
            dashboard_context=self.context,
        )
        res = process_chat_message(req)
        self.assertIn("YouTube", res.answer)
        self.assertEqual(res.tool_used, "get_active_platform")

    def test_conversational_greeting(self):
        req = ChatRequest(message="Hello")
        res = process_chat_message(req)
        self.assertIn("SocialIQ AI Intelligence Assistant", res.answer)
        self.assertEqual(res.tool_used, "greeting")

    def test_creator_inquiry(self):
        req = ChatRequest(message="Who created you?")
        res = process_chat_message(req)
        self.assertIn("Team NEXORA", res.answer)
        self.assertIn("SIH 26152", res.answer)
        self.assertEqual(res.tool_used, "explain_creator")

    def test_cs_concepts(self):
        for term, title_snippet in [
            ("What is Python?", "Python Programming Language"),
            ("What is FastAPI?", "FastAPI Web Framework"),
            ("What is PostgreSQL?", "PostgreSQL & Supabase"),
            ("What is OAuth?", "OAuth 2.0"),
            ("What is degree centrality?", "Degree Centrality"),
        ]:
            req = ChatRequest(message=term)
            res = process_chat_message(req)
            self.assertIn(title_snippet, res.answer)
            self.assertEqual(res.tool_used, "explain_metric")

    def test_general_knowledge_paris(self):
        req = ChatRequest(message="What is the capital of France?")
        res = process_chat_message(req)
        self.assertIn("Paris", res.answer)
        self.assertEqual(res.tool_used, "general_knowledge")


class TestYouTubeLayersTruthfulProbes(unittest.TestCase):
    """Verify Layer 2 (Analytics) and Layer 3 (Reporting) truthful probe classifications."""

    def setUp(self):
        from datetime import timedelta
        from backend.services.oauth_service import oauth_service, OAuthTokens
        self.oauth_service = oauth_service
        # Inject valid mock token into oauth_service memory
        self.oauth_service._tokens["youtube"] = OAuthTokens(
            access_token="ya29.test_valid_probe_token",
            refresh_token="1//0_refresh_test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            token_type="Bearer",
            scopes=["https://www.googleapis.com/auth/yt-analytics.readonly"],
        )
        self.oauth_service._probe_cache.clear()

    @patch.object(httpx.Client, "get")
    def test_probe_analytics_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"rows": [["2026-09-01", 1500, 320]]}
        mock_get.return_value = mock_resp

        res = self.oauth_service.probe_analytics_layer("youtube", force=True)
        self.assertEqual(res["status"], "CONNECTED")
        self.assertIn("active", res.get("reason", "").lower())

    @patch.object(httpx.Client, "get")
    def test_probe_analytics_api_not_enabled(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {
            "error": {
                "code": 403,
                "message": "YouTube Analytics API has not been used in project 12345 or it is disabled.",
                "errors": [{"reason": "accessNotConfigured"}]
            }
        }
        mock_get.return_value = mock_resp

        res = self.oauth_service.probe_analytics_layer("youtube", force=True)
        self.assertEqual(res["status"], "API_NOT_ENABLED")
        self.assertIn("Google Cloud Console", res.get("reason", ""))

    @patch.object(httpx.Client, "get")
    def test_probe_analytics_no_channel(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {
            "error": {
                "code": 404,
                "message": "The authenticated user does not have a YouTube channel.",
                "errors": [{"reason": "channelNotFound"}]
            }
        }
        mock_get.return_value = mock_resp

        res = self.oauth_service.probe_analytics_layer("youtube", force=True)
        self.assertEqual(res["status"], "NO_CHANNEL_ASSOCIATED")
        self.assertIn("channel", res.get("reason", "").lower())

    @patch.object(httpx.Client, "get")
    def test_probe_reporting_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "jobs": [
                {"id": "job_101", "reportTypeId": "channel_basic_a2", "name": "Basic Daily"}
            ]
        }
        mock_get.return_value = mock_resp

        res = self.oauth_service.probe_reporting_layer("youtube", force=True)
        self.assertEqual(res["status"], "CONNECTED")
        self.assertEqual(res.get("jobs_count"), 1)

    @patch.object(httpx.Client, "get")
    def test_probe_reporting_jobs_not_configured(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}  # Empty jobs list
        mock_get.return_value = mock_resp

        res = self.oauth_service.probe_reporting_layer("youtube", force=True)
        self.assertEqual(res["status"], "REPORTING_JOB_NOT_CONFIGURED")
        self.assertIn("reporting jobs", res.get("reason", "").lower())


if __name__ == "__main__":
    unittest.main()

