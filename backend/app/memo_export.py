"""分析备忘录 Markdown 导出（纯函数，便于单测）。

输出结构：
  - 标题：单行安全化（换行压平、行首 # 转义、反引号 / 竖线 / 反斜杠转义），
    用户输入无法生成或打断标题；
  - 正文：逐字保留，用「自适应长度」反引号围栏代码块包裹，内部任何
    Markdown 语法（标题、围栏、表格竖线等）都不被解析；
  - 证据：逐条列出关联时保存的编码名、区间、摘录快照与当前状态
    （当前有效 / 已变化 / 已删除）；已变化时同时列出当前编码、区间与
    摘录；已删除时仅保留快照，不丢失原内容。
"""

from __future__ import annotations

STATE_LABELS = {
    "current": "当前有效",
    "changed": "已变化",
    "missing": "已删除",
}


def _flatten(text) -> str:
    """压平为单行（标题、列表项等不允许出现物理换行的位置）。"""
    return str(text).replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def escape_inline(text) -> str:
    """转义行内用户内容，避免破坏标题 / 列表 / 表格 / 代码结构。

    反斜杠最先转义（否则后加的转义符会被二次解释）；反引号（代码围栏与
    行内代码）与竖线（表格分隔）始终转义；行首 # 转义以防被解析为标题。
    """
    s = _flatten(text)
    s = s.replace("\\", "\\\\").replace("`", "\\`").replace("|", "\\|")
    if s.startswith("#"):
        s = "\\" + s
    return s


def _max_backtick_run(text: str) -> int:
    """文本中最长的连续反引号串长度（含带前导空格的行，防止提前闭合围栏）。"""
    longest = 0
    run = 0
    for ch in text:
        if ch == "`":
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return longest


def fenced_block(text) -> list[str]:
    """把用户文本包进自适应长度反引号围栏，内容逐字保留。

    围栏长度取「内容最长反引号串 + 1」且不少于 3，保证内容中任何一行
    反引号都无法提前闭合围栏；波浪线围栏不能闭合反引号围栏，无需处理。
    """
    fence = "`" * max(3, _max_backtick_run(text) + 1)
    return [fence, text, fence]


def _excerpt_lines(excerpt) -> list[str]:
    if excerpt is None:
        return ["（区间已超出当前正文范围，无法截取摘录）"]
    return fenced_block(str(excerpt))


def build_memo_markdown(memo: dict, document: dict) -> str:
    """把 serialize_memo() 的结果渲染为 Markdown 文档字符串。"""
    evidences = memo.get("evidences", [])
    counts = {"current": 0, "changed": 0, "missing": 0}
    for ev in evidences:
        state = ev.get("state", "current")
        counts[state] = counts.get(state, 0) + 1

    lines: list[str] = []
    lines.append(f"# 分析备忘录：{escape_inline(memo['title'])}")
    lines.append("")
    lines.append(f"- 所属文档：{escape_inline(document['title'])}（ID {document['id']}）")
    lines.append(f"- 备忘录 ID：{memo['id']}")
    lines.append(f"- 状态：{'已归档' if memo.get('status') == 'archived' else '在办'}")
    lines.append(f"- 创建时间（UTC）：{memo['created_at']}")
    lines.append(f"- 更新时间（UTC）：{memo['updated_at']}")
    if memo.get("archived_at"):
        lines.append(f"- 归档时间（UTC）：{memo['archived_at']}")
    lines.append(
        f"- 证据：共 {len(evidences)} 条 — 当前有效 {counts['current']} 条、"
        f"已变化 {counts['changed']} 条、已删除 {counts['missing']} 条"
    )
    lines.append("")

    lines.append("## 正文")
    lines.append("")
    body = memo.get("body") or ""
    if body.strip():
        lines.extend(fenced_block(body))
    else:
        lines.append("（无正文）")
    lines.append("")

    lines.append(f"## 关联证据（{len(evidences)} 条）")
    if not evidences:
        lines.append("")
        lines.append("（未关联证据）")

    for i, ev in enumerate(evidences, 1):
        state = ev.get("state", "current")
        label = STATE_LABELS.get(state, state)
        lines.append("")
        lines.append(f"### 证据 {i}（{label}）")
        lines.append("")
        lines.append(f"- 关联时编码：{escape_inline(ev['code_name'])}")
        lines.append(f"- 关联时区间：[{ev['start']}, {ev['end']})")
        lines.append(f"- 关联时间（UTC）：{ev['created_at']}")
        lines.append("")
        lines.append("关联时摘录（快照）：")
        lines.append("")
        lines.extend(_excerpt_lines(ev.get("excerpt")))

        cur = ev.get("current")
        if state == "changed" and cur is not None:
            lines.append("")
            lines.append("当前标注信息（已变化）：")
            lines.append("")
            lines.append(f"- 当前编码：{escape_inline(cur['code_name'])}")
            lines.append(f"- 当前区间：[{cur['start']}, {cur['end']})")
            lines.append("")
            lines.append("当前摘录：")
            lines.append("")
            lines.extend(_excerpt_lines(cur.get("excerpt")))
        elif state == "missing":
            lines.append("")
            lines.append("> 原标注已删除；以上为关联时保存的编码、区间与原文摘录快照，未随删除丢失。")

    lines.append("")
    return "\n".join(lines)
