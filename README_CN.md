# 🌿 Beautiful Oops

> *因为每一个错误，都值得被温柔对待。*

**Beautiful Oops** 是一个轻量级的、以“冒险（Adventure）”为隐喻的错误监督与恢复框架。  
它让错误的处理过程更像故事：每个阶段（Moment）都可以失败、重来、留下痕迹（StoryBook），  
最终让程序从 “Oops” 中变得更坚韧。

## ✨ 特性 Highlights
- 🪄 **@oops_moment**：自动重试、超时、回滚
- 🧙‍♀️ **Elf / Hero**：策略决策者，让错误被“劝导”
- 📖 **StoryBook 插件**：记录成功与失败，像写冒险日记
- 🔁 **Backoff 策略**：内置指数退避
- ⚙️ **插件体系**：支持日志、监控、熔断、降级
- 🧩 **同步与异步双兼容**

## 🚀 快速上手
```python
from beautiful_oops import oops_moment, Adventure, StorybookPlugin, StoryBook

@oops_moment(chapter="Chapter I", stage="decode_scroll")
def decode_scroll():
    return "ancient wisdom"

adv = Adventure(name="demo", plugins=[StorybookPlugin(StoryBook("my-book"))])
print("Scroll:", decode_scroll())
```

## 🧠 设计哲学
> ⚡ 程序的韧性，不在于避免错误，而在于能否优雅地面对错误。

**Adventure** 构建故事，**Elf** 提供建议，**Hero** 做出决策，**StoryBook** 记录这一切。

## 🌌 路线图 Roadmap
### 🧩 短期（v0.2.x）
- [ ] Fallback Plugin  
- [ ] Circuit Breaker Plugin  
- [ ] Sink System（Console/File/Prometheus）

### 🤖 中期（v0.3–0.5）
- [ ] Agent-based Error Decision（基于历史自动决策 Retry / Fallback）

### 🕊️ 长期（v1.0）
- [ ] 可视化仪表板（Adventure Timeline）  
- [ ] 插件生态仓库  

## 🧪 测试
```bash
pytest -q
ruff check .
mypy beautiful_oops
```
or
```bash
uv run --extra dev pytest
```

MIT License © 2025 Sean Liu
