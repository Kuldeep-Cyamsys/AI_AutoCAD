import base64
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app import ai_service
from app.schemas import ChatRequest, ImageAttachment


IMAGE = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()


@pytest.mark.parametrize("url", ["https://example.com/image.png", "data:image/png;base64,!!!", "data:image/png;base64,YWJj", "data:image/svg+xml;base64,YWJj"])
def test_reject_invalid_attachment(url):
    with pytest.raises(ValidationError):
        ImageAttachment(name="reference", data_url=url)


def test_attachment_limits():
    with pytest.raises(ValidationError):
        ChatRequest(message="edit", images=[{"name": "image", "data_url": IMAGE}] * 4)
    with pytest.raises(ValidationError):
        ImageAttachment(name="large", data_url="data:image/png;base64," + base64.b64encode(b"x" * (5 * 1024 * 1024 + 1)).decode())


def test_offline_images_are_not_ignored(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = ai_service.chat(ChatRequest(message="plate", images=[{"name": "image", "data_url": IMAGE}]))
    assert response.status == "clarification"
    assert response.spec is None


def test_images_use_multimodal_content_and_require_approval(monkeypatch):
    spec = ai_service.demo_parse(ChatRequest(message="plate")).spec
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        content = json.dumps({"status": "ready", "message": "Updated", "spec": spec.model_dump()})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "OpenAI", lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    response = ai_service.chat(ChatRequest(message="design", current_spec=spec, images=[{"name": "image", "data_url": IMAGE}]))
    assert response.status == "proposal"
    content = calls[0]["messages"][1]["content"]
    assert content[1]["image_url"]["url"] == IMAGE
    assert IMAGE not in content[0]["text"]
    assert json.loads(content[0]["text"])["current_spec"]["name"] == spec.name
