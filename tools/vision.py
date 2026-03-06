"""
Vision LLM — analyze screenshots from phone or desktop.
Uses NVIDIA NIM llama-3.2-vision or Ollama vision model.
"""

from __future__ import annotations
import config
from core.llm import _get_client


def vision_model() -> str:
    if config.LLM_BACKEND == "nvidia":
        return config.NVIDIA_VISION_MODEL
    return config.OLLAMA_VISION_MODEL


async def analyze_image(
    image_base64: str,
    question: str = "Describe this screen in detail. List all visible UI elements, buttons, text, and their approximate positions.",
    screen_width: int = None,
    screen_height: int = None,
) -> str:
    """
    Analyze a base64-encoded image (PNG or JPEG) using the vision LLM.
    Returns a text description or answer to the question.
    """
    client = _get_client()

    context = question
    if screen_width and screen_height:
        context = f"Screen size: {screen_width}x{screen_height}px. {question}"

    # Strip data URI prefix if present
    img_data = image_base64
    if "," in image_base64:
        img_data = image_base64.split(",", 1)[1]

    response = await client.chat.completions.create(
        model=vision_model(),
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_data}"},
                },
                {"type": "text", "text": context},
            ],
        }],
        max_tokens=1024,
    )
    return response.choices[0].message.content
