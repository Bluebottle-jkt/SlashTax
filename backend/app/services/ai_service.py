from anthropic import Anthropic
from openai import OpenAI
from typing import Optional
import logging
import base64
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered analysis using Anthropic and OpenAI APIs."""

    def __init__(self):
        self._anthropic: Optional[Anthropic] = None
        self._openai: Optional[OpenAI] = None

    @property
    def anthropic(self) -> Anthropic:
        if self._anthropic is None:
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            self._anthropic = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._anthropic

    @property
    def openai(self) -> OpenAI:
        if self._openai is None:
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not configured")
            self._openai = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai

    def analyze_caption(self, caption: str) -> dict:
        """Analyze a caption to extract entities, sentiment, and topics."""
        if not caption:
            return {
                "entities": [],
                "sentiment": "neutral",
                "topics": [],
                "summary": "",
            }

        prompt = f"""Analyze the following Instagram caption and extract:
1. Named entities (people, places, organizations, brands)
2. Sentiment (positive, negative, neutral)
3. Main topics or themes
4. A brief one-sentence summary

Caption: {caption}

Respond in JSON format:
{{
    "entities": [{{ "name": "...", "type": "person|place|organization|brand" }}],
    "sentiment": "positive|negative|neutral",
    "topics": ["topic1", "topic2"],
    "summary": "..."
}}"""

        try:
            response = self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            import json
            content = response.content[0].text
            # Extract JSON from response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])

        except Exception as e:
            logger.error(f"Failed to analyze caption: {e}")

        return {
            "entities": [],
            "sentiment": "neutral",
            "topics": [],
            "summary": "",
        }

    def analyze_image(self, image_path: str | Path) -> dict:
        """Analyze an image to describe content, detect objects, and identify context."""
        try:
            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            # Determine media type
            suffix = Path(image_path).suffix.lower()
            media_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            media_type = media_types.get(suffix, "image/jpeg")

            response = self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": """Analyze this image and provide:
1. A description of the scene
2. Number of people visible (approximate)
3. Identifiable location clues (landmarks, signs, etc.)
4. Time of day estimate (if determinable)
5. Notable objects or items
6. Apparent activity or context

Respond in JSON format:
{
    "description": "...",
    "people_count": 0,
    "location_clues": ["clue1", "clue2"],
    "time_of_day": "morning|afternoon|evening|night|unknown",
    "objects": ["object1", "object2"],
    "activity": "...",
    "confidence": 0.0-1.0
}""",
                            },
                        ],
                    }
                ],
            )

            import json
            content = response.content[0].text
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])

        except Exception as e:
            logger.error(f"Failed to analyze image: {e}")

        return {
            "description": "Unable to analyze image",
            "people_count": 0,
            "location_clues": [],
            "time_of_day": "unknown",
            "objects": [],
            "activity": "unknown",
            "confidence": 0.0,
        }

    def generate_person_profile(self, person_data: dict) -> str:
        """Generate a narrative profile for a person based on their graph data."""
        prompt = f"""Based on the following data about a person extracted from social media,
write a brief profile summary (2-3 sentences). Be factual and objective.

Data:
- Name: {person_data.get('name', 'Unknown')}
- Appearances in posts: {person_data.get('post_count', 0)}
- Locations visited: {', '.join(person_data.get('locations', [])[:5]) or 'Unknown'}
- Frequently appears with: {', '.join(person_data.get('co_appearances', [])[:5]) or 'No one identified'}
- Common hashtags: {', '.join(person_data.get('hashtags', [])[:5]) or 'None'}

Write a brief, factual profile:"""

        try:
            response = self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Failed to generate profile: {e}")
            return f"Profile for {person_data.get('name', 'Unknown')}"

    def suggest_connections(self, graph_context: str) -> list[dict]:
        """Suggest potential connections or patterns in the graph."""
        prompt = f"""Based on the following graph data context, suggest potential connections,
patterns, or insights that might be worth investigating.

Context:
{graph_context}

Provide 3-5 suggestions in JSON format:
[
    {{
        "type": "connection|pattern|anomaly",
        "description": "...",
        "confidence": 0.0-1.0,
        "nodes_involved": ["node1", "node2"]
    }}
]"""

        try:
            response = self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )

            import json
            content = response.content[0].text
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])

        except Exception as e:
            logger.error(f"Failed to suggest connections: {e}")

        return []

    def extract_location_from_text(self, text: str) -> Optional[dict]:
        """Extract location information from text using AI."""
        prompt = f"""Extract any location information from the following text.
Return null if no location is found.

Text: {text}

If a location is found, respond in JSON:
{{
    "name": "location name",
    "type": "city|country|venue|landmark|address",
    "confidence": 0.0-1.0
}}

If no location found, respond: null"""

        try:
            response = self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )

            import json
            content = response.content[0].text.strip()
            if content.lower() == "null":
                return None

            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])

        except Exception as e:
            logger.error(f"Failed to extract location: {e}")

        return None

    def generate_embeddings(self, text: str) -> list[float]:
        """Generate text embeddings using OpenAI."""
        try:
            response = self.openai.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return []


ai_service = AIService()
