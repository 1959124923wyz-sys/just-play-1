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


def run_game(story_path: str = "story.json", input_fn=input, output_fn=print):
    try:
        story = load_story(story_path)
        validate_story(story)
    except (FileNotFoundError, ValueError) as exc:
        output_fn(str(exc))
        return 1

    output_fn(f"=== {story['title']} ===")
    node_id = story["start"]

    while True:
        node = story["nodes"][node_id]
        output_fn(node["text"])
        if node.get("ending"):
            output_fn("已到达结局，游戏结束。")
            return 0

        choices = get_choices(story, node_id)
        output_fn("请选择：")
        for index, choice in enumerate(choices, start=1):
            output_fn(f"{index}. {choice['text']}")
        output_fn("输入 0 查看帮助，9 退出。")

        user_input = input_fn("> ").strip()
        if user_input == "0":
            output_fn("帮助：输入 1/2/3... 选择选项，输入 9 退出游戏。")
            continue
        if user_input == "9":
            output_fn("已退出游戏。")
            return 0
        if user_input.isdigit():
            choice_index = int(user_input)
            if 1 <= choice_index <= len(choices):
                node_id = apply_choice(story, node_id, choice_index)
                continue
        output_fn("无效输入")


if __name__ == "__main__":
    sys.exit(run_game())
