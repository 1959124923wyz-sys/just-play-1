import json
import sys
from pathlib import Path


def load_story(path: str):
    story_path = Path(path)
    if not story_path.exists():
        raise FileNotFoundError(f"故事文件不存在：{path}")
    try:
        with story_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"故事文件解析失败：{exc}") from exc


def validate_story(story: dict):
    if not isinstance(story, dict):
        raise ValueError("故事结构错误：根节点必须是对象")
    title = story.get("title")
    start = story.get("start")
    nodes = story.get("nodes")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("故事结构错误：缺少标题")
    if not isinstance(start, str) or not start.strip():
        raise ValueError("故事结构错误：缺少起始节点")
    if not isinstance(nodes, dict) or not nodes:
        raise ValueError("故事结构错误：缺少节点列表")
    if start not in nodes:
        raise ValueError("故事结构错误：起始节点不存在")

    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            raise ValueError(f"故事结构错误：节点 {node_id} 必须是对象")
        text = node.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"故事结构错误：节点 {node_id} 缺少文本")
        choices = node.get("choices", [])
        ending = node.get("ending", False)
        if ending:
            if choices:
                raise ValueError(f"故事结构错误：结局节点 {node_id} 不应包含选项")
            continue
        if not isinstance(choices, list) or not choices:
            raise ValueError(f"故事结构错误：节点 {node_id} 缺少选项")
        for choice in choices:
            if not isinstance(choice, dict):
                raise ValueError(f"故事结构错误：节点 {node_id} 选项必须是对象")
            choice_text = choice.get("text")
            next_id = choice.get("next")
            if not isinstance(choice_text, str) or not choice_text.strip():
                raise ValueError(f"故事结构错误：节点 {node_id} 选项缺少文本")
            if not isinstance(next_id, str) or not next_id.strip():
                raise ValueError(f"故事结构错误：节点 {node_id} 选项缺少跳转")
            if next_id not in nodes:
                raise ValueError(
                    f"故事结构错误：节点 {node_id} 选项跳转不存在：{next_id}"
                )
    return True


def get_choices(story: dict, node_id: str):
    node = story["nodes"][node_id]
    return node.get("choices", [])


def apply_choice(story: dict, node_id: str, choice_index: int):
    choices = get_choices(story, node_id)
    if choice_index < 1 or choice_index > len(choices):
        raise IndexError("选项索引超出范围")
    return choices[choice_index - 1]["next"]


def _render_normal(story: dict, node_id: str):
    node = story["nodes"][node_id]
    lines = [node["text"], "请选择："]
    for index, choice in enumerate(get_choices(story, node_id), start=1):
        lines.append(f"{index}. {choice['text']}")
    lines.append("输入 0 查看帮助，9 退出，# 后退。")
    return lines


def _render_ending(story: dict, node_id: str):
    node = story["nodes"][node_id]
    return [node["text"], "结局：输入 1 重开，9 退出。"]


def step(state: dict, user_input: str, story: dict):
    output_lines = []
    trimmed = user_input.strip()

    if trimmed == "":
        if state["mode"] == "ending":
            output_lines.extend(_render_ending(story, state["node_id"]))
        else:
            output_lines.extend(_render_normal(story, state["node_id"]))
        return state, output_lines, False

    if state["mode"] == "ending":
        if trimmed == "1":
            new_state = {"node_id": story["start"], "history_stack": [], "mode": "normal"}
            output_lines.extend(_render_normal(story, new_state["node_id"]))
            return new_state, output_lines, False
        if trimmed == "9":
            output_lines.append("已退出游戏。")
            return state, output_lines, True
        output_lines.append("无效输入")
        output_lines.extend(_render_ending(story, state["node_id"]))
        return state, output_lines, False

    if trimmed == "0":
        output_lines.append("帮助：输入 1..N 选择，# 后退，9 退出。")
        output_lines.extend(_render_normal(story, state["node_id"]))
        return state, output_lines, False

    if trimmed == "9":
        output_lines.append("已退出游戏。")
        return state, output_lines, True

    if trimmed == "#":
        if state["history_stack"]:
            new_node_id = state["history_stack"].pop()
            state = {"node_id": new_node_id, "history_stack": state["history_stack"], "mode": "normal"}
        else:
            output_lines.append("无法后退，已经在起点。")
        output_lines.extend(_render_normal(story, state["node_id"]))
        return state, output_lines, False

    if trimmed.isdigit():
        choice_index = int(trimmed)
        choices = get_choices(story, state["node_id"])
        if 1 <= choice_index <= len(choices):
            next_node_id = apply_choice(story, state["node_id"], choice_index)
            history = state["history_stack"] + [state["node_id"]]
            if story["nodes"][next_node_id].get("ending"):
                state = {"node_id": next_node_id, "history_stack": history, "mode": "ending"}
                output_lines.extend(_render_ending(story, next_node_id))
            else:
                state = {"node_id": next_node_id, "history_stack": history, "mode": "normal"}
                output_lines.extend(_render_normal(story, next_node_id))
            return state, output_lines, False

    output_lines.append("无效输入")
    output_lines.extend(_render_normal(story, state["node_id"]))
    return state, output_lines, False


def run_game(story_path: str = "story.json", input_fn=input, output_fn=print):
    try:
        story = load_story(story_path)
        validate_story(story)
    except (FileNotFoundError, ValueError) as exc:
        output_fn(str(exc))
        return 1

    output_fn(f"=== {story['title']} ===")
    state = {"node_id": story["start"], "history_stack": [], "mode": "normal"}
    for line in _render_normal(story, state["node_id"]):
        output_fn(line)

    while True:
        user_input = input_fn("> ")
        state, output_lines, should_exit = step(state, user_input, story)
        for line in output_lines:
            output_fn(line)
        if should_exit:
            return 0


if __name__ == "__main__":
    sys.exit(run_game())
