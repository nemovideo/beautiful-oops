from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Dict, List, Optional


class NodeType(str, Enum):
    MOMENT = "moment"
    ATTEMPT = "attempt"


class NodeStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class StoryNode:
    node_id: str
    node_type: NodeType
    chapter: str
    stage: str
    attempt: Optional[int] = None
    parent_id: Optional[str] = None
    status: NodeStatus = NodeStatus.RUNNING
    started_at: float = field(default_factory=time)
    finished_at: Optional[float] = None
    note: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    children: List[str] = field(default_factory=list)

    def close(self, status: NodeStatus, note: Optional[str] = None) -> None:
        if not self.finished_at:
            self.finished_at = time()
        self.status = status
        if note:
            self.note = note

    @property
    def duration(self) -> Optional[float]:
        if self.finished_at is None:
            return None
        return max(0.0, self.finished_at - self.started_at)


@dataclass
class Treasure:
    chapter: str
    stage: str
    value: Any
    at: float = field(default_factory=time)


@dataclass
class Tear:
    chapter: str
    stage: str
    error: str
    at: float = field(default_factory=time)


class StoryBook:
    def __init__(self, title: str):
        self.title = title
        self.nodes: Dict[str, StoryNode] = {}
        self.roots: List[str] = []
        self.treasures: List[Treasure] = []
        self.tears: List[Tear] = []

    @staticmethod
    def build_moment_id(trace_id: str, chapter: str, stage: str) -> str:
        return f"{trace_id}:{chapter}/{stage}"

    @staticmethod
    def build_attempt_id(trace_id: str, chapter: str, stage: str, attempt: int) -> str:
        return f"{trace_id}:{chapter}/{stage}#{attempt}"

    @staticmethod
    def parse_moment_id_from_attempt(attempt_id: str) -> str:
        return attempt_id.split("#", 1)[0]

    def _ensure_node(self, node_id: str, node_type: NodeType, chapter: str, stage: str, attempt: Optional[int] = None,
                     parent_id: Optional[str] = None) -> StoryNode:
        node = self.nodes.get(node_id)
        if node is None:
            node = StoryNode(node_id=node_id, node_type=node_type, chapter=chapter, stage=stage, attempt=attempt,
                             parent_id=parent_id)
            self.nodes[node_id] = node
            if node_type == NodeType.MOMENT:
                if parent_id is None:
                    self.roots.append(node_id)
                elif parent_id in self.nodes:
                    parent = self.nodes[parent_id]
                    if node_id not in parent.children:
                        parent.children.append(node_id)
            elif parent_id and parent_id in self.nodes:
                parent = self.nodes[parent_id]
                if node_id not in parent.children:
                    parent.children.append(node_id)
        return node

    def enter(self, trace_id: str, chapter: str, stage: str, parent_span_id: Optional[str] = None) -> str:
        moment_id = self.build_moment_id(trace_id, chapter, stage)
        parent_id = parent_span_id
        self._ensure_node(moment_id, NodeType.MOMENT, chapter, stage, parent_id=parent_id)
        return moment_id

    def attempt_enter(self, trace_id: str, chapter: str, stage: str, attempt: int, span_id: Optional[str] = None,
                      parent_span_id: Optional[str] = None) -> str:
        attempt_id = span_id or self.build_attempt_id(trace_id, chapter, stage, attempt)
        parent_id = parent_span_id or self.parse_moment_id_from_attempt(attempt_id)
        self._ensure_node(parent_id, NodeType.MOMENT, chapter, stage, parent_id=None)
        self._ensure_node(attempt_id, NodeType.ATTEMPT, chapter, stage, attempt=attempt, parent_id=parent_id)
        return attempt_id

    def attempt_success(self, attempt_id: str, result: Any) -> None:
        node = self.nodes.get(attempt_id)
        if not node:
            return
        node.result = result
        node.close(status=NodeStatus.SUCCESS)
        parent_id = node.parent_id or self.parse_moment_id_from_attempt(attempt_id)
        if parent_id in self.nodes:
            m = self.nodes[parent_id]
            if m.status == NodeStatus.RUNNING:
                m.close(status=NodeStatus.SUCCESS)
        self.treasures.append(Treasure(chapter=node.chapter, stage=node.stage, value=result))

    def attempt_fail(self, attempt_id: str, oops: Optional[Any]) -> None:
        node = self.nodes.get(attempt_id)
        if not node:
            return
        node.error = getattr(oops, "message", str(oops)) if oops else "unknown"
        node.close(status=NodeStatus.FAILED, note=node.error)

    def fail(self, trace_id: str, chapter: str, stage: str, oops: Any) -> None:
        moment_id = self.build_moment_id(trace_id, chapter, stage)
        m = self._ensure_node(moment_id, NodeType.MOMENT, chapter, stage)
        m.error = getattr(oops, "message", str(oops))
        m.close(status=NodeStatus.FAILED, note=m.error)
        self.tears.append(Tear(chapter=chapter, stage=stage, error=m.error))

    def get_roots(self) -> List[StoryNode]:
        return [self.nodes[rid] for rid in self.roots if rid in self.nodes]

    def get_children(self, node_id: str) -> List[StoryNode]:
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.children if cid in self.nodes]

    def render_ascii(self, show_time: bool = True) -> str:
        """
        以树形结构输出：
        - 使用 ┣━━ / ┗━━ 区分是否为同层的最后一个节点
        - 使用 ┃ 维持上层未结束分支的竖线
        - [M] / [A#n] 表示 moment / attempt
        - ✅ / 💀 / ⏳ 表示状态
        - 可选输出耗时
        """
        def mark(n: StoryNode) -> str:
            return "✅" if n.status == NodeStatus.SUCCESS else ("💀" if n.status == NodeStatus.FAILED else "⏳")

        def tag(n: StoryNode) -> str:
            return "[M]" if n.node_type == NodeType.MOMENT else f"[A#{n.attempt}]"

        def dur(n: StoryNode) -> str:
            if not show_time:
                return ""
            if n.duration is None:
                return ""
            return f" ⏱ {n.duration:.2f}s"

        lines: list[str] = []

        # 深度优先递归，携带“前缀”和“是否最后节点”的信息
        def walk(node_id: str, prefix: str, is_last: bool):
            node = self.nodes.get(node_id)
            if not node:
                return
            connector = "┗━━" if is_last else "┣━━"
            lines.append(f"{prefix}{connector} {tag(node)} {node.chapter}/{node.stage} {mark(node)}{dur(node)}")

            children = self.get_children(node_id)
            if not children:
                return

            # 下一层的前缀：若当前不是最后分支，需要延续竖线 ┃ ，否则留空格
            child_prefix = prefix + ("    " if is_last else "┃   ")
            for i, ch in enumerate(children):
                walk(ch.node_id, child_prefix, i == len(children) - 1)

        # 多棵根的情况，逐棵渲染
        for ridx, root_id in enumerate([rid for rid in self.roots if rid in self.nodes]):
            # 顶层没有前缀，仅按是否最后一棵根决定连接符
            walk(root_id, prefix="", is_last=(ridx == len(self.roots) - 1))

        return "\n".join(lines)
