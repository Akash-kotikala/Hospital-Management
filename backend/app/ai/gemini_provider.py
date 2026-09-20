from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.ai.provider import LLMProvider
from app.ai.fallback_provider import FallbackProvider
from app.core.logging import logger


class GeminiProvider(LLMProvider):
    def __init__(self):
        self.fallback = FallbackProvider()
        self.api_key = settings.GEMINI_API_KEY
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Initialized Google GenAI Gemini client successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI client: {e}. Using FallbackProvider.")

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        system_instruction: str,
        capabilities: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        # If no client or API key is not configured, use the deterministic fallback provider
        if not self.client or not self.api_key:
            return await self.fallback.generate_response(messages, system_instruction, capabilities, context)

        try:
            from google.genai import types

            # Format conversation for Gemini
            contents = []
            for msg in messages:
                role = "user" if msg.get("sender") == "USER" or msg.get("role") == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.get("content", ""))]
                ))

            # Convert capability schemas into Gemini function declarations
            function_declarations = []
            for cap in capabilities:
                schema_dict = cap["schema"].model_json_schema()
                # Clean schema for Gemini parameters
                properties = schema_dict.get("properties", {})
                required = schema_dict.get("required", [])
                function_declarations.append(
                    types.FunctionDeclaration(
                        name=cap["name"],
                        description=cap["description"],
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                k: types.Schema(
                                    type="STRING" if v.get("type") == "string" else "OBJECT",
                                    description=v.get("description", "")
                                )
                                for k, v in properties.items()
                            },
                            required=required,
                        )
                    )
                )

            tool = types.Tool(function_declarations=function_declarations)
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,
                tools=[tool],
            )

            # Call Gemini
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=contents,
                config=config,
            )

            # Extract tool calls if returned
            tool_calls = []
            if response.function_calls:
                for fc in response.function_calls:
                    tool_calls.append({
                        "name": fc.name,
                        "args": dict(fc.args) if fc.args else {},
                    })

            reply_text = response.text or ""
            return {
                "text": reply_text,
                "tool_calls": tool_calls,
            }

        except Exception as exc:
            logger.warning(f"Gemini API call failed ({exc}). Falling back to deterministic fallback provider.")
            return await self.fallback.generate_response(messages, system_instruction, capabilities, context)
