# 🌿 Beautiful Oops

> *Because every error deserves a graceful story.*

**Beautiful Oops** is a lightweight adventure-style supervision and recovery framework for Python.  
It turns error handling into storytelling — each **Moment** can fail, retry, or succeed,  
and all outcomes are recorded in a **StoryBook**.

## ✨ Features
- 🪄 **@oops_moment** decorator for automatic retry / timeout / rollback  
- 🧙‍♀️ **Elf & Hero** – pluggable decision-makers for handling Oops  
- 📖 **StoryBook Plugin** – records every success and failure  
- 🔁 **Backoff Policy** – exponential with jitter  
- ⚙️ **Plugin Architecture** – easy to extend (logging, monitoring, circuit-breaker)  
- 🧩 Works in both **sync** and **async** modes

## 🚀 Quickstart
```python
from beautiful_oops import oops_moment, Adventure, StorybookPlugin

@oops_moment(chapter="Chapter I", stage="decode_scroll")
def decode_scroll():
    return "ancient wisdom"

adv = Adventure(name="demo", plugins=[StorybookPlugin()])
with Adventure.auto(adv):
    print("Scroll:", decode_scroll())
```

## 🧠 Philosophy
> ⚡ Resilience is not about avoiding errors, but about facing them gracefully.

**Adventure** builds the story, **Elf** gives advice, **Hero** decides, **StoryBook** remembers.

## 🌌 Roadmap
### 🧩 Short-term (v0.2.x)
- [ ] Fallback Plugin  
- [ ] Circuit Breaker Plugin  
- [ ] Sink System (Console / File / Prometheus / Loki)

### 🤖 Mid-term (v0.3–0.5)
- [ ] Agent-based Error Decision Engine  
  – let an intelligent agent decide whether to retry, ignore, or fallback

### 🕊️ Long-term (v1.0)
- [ ] Visual Dashboard (Adventure Timeline)  
- [ ] Community Plugin Ecosystem  

## 🧪 Testing & CI
```bash
pip install -e .[dev]
pytest -q
ruff check .
mypy beautiful_oops
```
or
```bash
uv run --extra dev pytest
```

MIT License © 2025 Sean Liu
