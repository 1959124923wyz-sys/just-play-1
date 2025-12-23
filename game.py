import json
import re
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
    stats_config = story.get("stats_config")
    flag_descriptions = story.get("flag_descriptions", {})
    if not isinstance(title, str) or not title.strip():
        raise ValueError("故事结构错误：缺少标题")
    if not isinstance(start, str) or not start.strip():
        raise ValueError("故事结构错误：缺少起始节点")
    if not isinstance(nodes, dict) or not nodes:
        raise ValueError("故事结构错误：缺少节点列表")
    if flag_descriptions is not None and not isinstance(flag_descriptions, dict):
        raise ValueError("故事结构错误：flag_descriptions 必须是对象")
    if stats_config is not None:
        if not isinstance(stats_config, dict):
            raise ValueError("故事结构错误：stats_config 必须是对象")
        suspicion_max = stats_config.get("suspicion_max")
        fail_node = stats_config.get("suspicion_fail_node")
        if not isinstance(suspicion_max, int) or suspicion_max < 0:
            raise ValueError("故事结构错误：suspicion_max 必须是非负整数")
        if not isinstance(fail_node, str) or not fail_node.strip():
            raise ValueError("故事结构错误：suspicion_fail_node 必须是字符串")
        if fail_node not in nodes:
            raise ValueError("故事结构错误：suspicion_fail_node 不存在")
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
            requires = choice.get("requires")
            set_flags = choice.get("set_flags")
            delta_stats = choice.get("delta_stats")
            requires_stats = choice.get("requires_stats")
            if not isinstance(choice_text, str) or not choice_text.strip():
                raise ValueError(f"故事结构错误：节点 {node_id} 选项缺少文本")
            if not isinstance(next_id, str) or not next_id.strip():
                raise ValueError(f"故事结构错误：节点 {node_id} 选项缺少跳转")
            if next_id not in nodes:
                raise ValueError(
                    f"故事结构错误：节点 {node_id} 选项跳转不存在：{next_id}"
                )
            if requires is not None:
                if not isinstance(requires, list) or not all(
                    isinstance(item, str) for item in requires
                ):
                    raise ValueError(
                        f"故事结构错误：节点 {node_id} 选项 requires 必须是字符串列表"
                    )
            if set_flags is not None:
                if not isinstance(set_flags, list) or not all(
                    isinstance(item, str) for item in set_flags
                ):
                    raise ValueError(
                        f"故事结构错误：节点 {node_id} 选项 set_flags 必须是字符串列表"
                    )
            if requires is not None:
                missing = [flag for flag in requires if flag not in flag_descriptions]
                if missing:
                    raise ValueError(
                        f"故事结构错误：节点 {node_id} 选项 requires 未定义描述：{', '.join(missing)}"
                    )
            if delta_stats is not None:
                if not isinstance(delta_stats, dict) or not all(
                    isinstance(key, str) and isinstance(value, int)
                    for key, value in delta_stats.items()
                ):
                    raise ValueError(
                        f"故事结构错误：节点 {node_id} 选项 delta_stats 必须是整数映射"
                    )
            if requires_stats is not None:
                if not isinstance(requires_stats, dict) or not all(
                    isinstance(key, str) and isinstance(value, int)
                    for key, value in requires_stats.items()
                ):
                    raise ValueError(
                        f"故事结构错误：节点 {node_id} 选项 requires_stats 必须是整数映射"
                    )
    return True


def get_choices(story: dict, node_id: str, flags=None, stats=None):
    node = story["nodes"][node_id]
    choices = node.get("choices", [])
    if not flags:
        flags = set()
    if stats is None:
        stats = {}
    return [
        choice
        for choice in choices
        if set(choice.get("requires", [])).issubset(flags)
        and all(stats.get(key, 0) >= value for key, value in choice.get("requires_stats", {}).items())
    ]


def get_locked_choices(story: dict, node_id: str, flags=None, stats=None):
    node = story["nodes"][node_id]
    choices = node.get("choices", [])
    if not flags:
        flags = set()
    if stats is None:
        stats = {}
    locked = []
    for choice in choices:
        missing_flags = [f for f in choice.get("requires", []) if f not in flags]
        missing_stats = [
            (key, value)
            for key, value in choice.get("requires_stats", {}).items()
            if stats.get(key, 0) < value
        ]
        if missing_flags or missing_stats:
            locked.append((choice, missing_flags, missing_stats))
    return locked


def apply_choice(story: dict, node_id: str, choice_index: int, flags=None, stats=None):
    choices = get_choices(story, node_id, flags, stats)
    if choice_index < 1 or choice_index > len(choices):
        raise IndexError("选项索引超出范围")
    choice = choices[choice_index - 1]
    return (
        choice["next"],
        set(choice.get("set_flags", [])),
        dict(choice.get("delta_stats", {})),
    )


def strip_scene_prefix(text: str):
    match = None
    if text:
        match = re.match(r"^(?P<route>\S+?)第(?P<index>\d+)场[:：]\s*", text)
    if not match:
        return text, {}
    meta = {"route": match.group("route"), "index": int(match.group("index"))}
    return text[match.end():], meta


def _render_normal(story: dict, node_id: str, flags, stats):
    node = story["nodes"][node_id]
    clean_text, _ = strip_scene_prefix(node["text"])
    lines = [clean_text, "请选择："]
    for index, choice in enumerate(get_choices(story, node_id, flags, stats), start=1):
        lines.append(f"{index}. {choice['text']}")
    locked = get_locked_choices(story, node_id, flags, stats)
    if locked:
        lines.append("【尚不可行】")
        for choice, missing_flags, missing_stats in locked:
            requirements = []
            if missing_flags:
                requirements.append("条件未具备")
            if missing_stats:
                stat_texts = []
                for key, value in missing_stats:
                    if key == "silver":
                        stat_texts.append("钱袋不够沉")
                    elif key == "suspicion":
                        stat_texts.append("风声太紧")
                    else:
                        stat_texts.append("时机不对")
                requirements.append(" / ".join(stat_texts))
            lines.append(f"- {choice['text']}（{'; '.join(requirements)}）")
    lines.append("输入 0 查看帮助，9 退出，8 后退。")
    return lines


def _render_ending(story: dict, node_id: str, stats):
    node = story["nodes"][node_id]
    clean_text, _ = strip_scene_prefix(node["text"])
    return [
        clean_text,
        "结局：输入 1 重开，9 退出。",
    ]


def step(state: dict, user_input: str, story: dict):
    output_lines = []
    trimmed = user_input.strip()
    flags = set(state.get("flags", set()))
    history = list(state.get("history_stack", []))
    stats = dict(state.get("stats", {"suspicion": 0, "silver": 0}))
    stats.setdefault("suspicion", 0)
    stats.setdefault("silver", 0)
    stats_config = story.get("stats_config", {})
    last_choice = state.get("last_choice")
    help_mode = state.get("help_mode", 0)

    if trimmed == "":
        if state["mode"] == "ending":
            output_lines.extend(_render_ending(story, state["node_id"], stats))
        else:
            output_lines.extend(_render_normal(story, state["node_id"], flags, stats))
        return state, output_lines, False

    if state["mode"] == "ending":
        if trimmed == "1":
            new_state = {
                "node_id": story["start"],
                "history_stack": [],
                "mode": "normal",
                "flags": set(),
                "stats": {"suspicion": 0, "silver": 0},
            }
            output_lines.extend(
                _render_normal(story, new_state["node_id"], new_state["flags"], new_state["stats"])
            )
            return new_state, output_lines, False
        if trimmed == "9":
            output_lines.append("已退出游戏。")
            return state, output_lines, True
        output_lines.append("无效输入")
        output_lines.extend(_render_ending(story, state["node_id"], stats))
        return state, output_lines, False

    if trimmed == "0":
        node = story["nodes"][state["node_id"]]
        output_lines.append("帮助：输入 1..N 选择，8 后退，9 退出。")
        output_lines.append("提示：回车可重显当前内容。")
        if help_mode == 1:
            output_lines.append(f"调试信息：node_id={state['node_id']}")
            if flags:
                output_lines.append(f"flags={', '.join(sorted(flags))}")
            output_lines.append(
                f"stats: suspicion={stats.get('suspicion', 0)}, silver={stats.get('silver', 0)}"
            )
            _, meta = strip_scene_prefix(node.get("text", ""))
            if meta:
                output_lines.append(
                    f"route={meta.get('route', '未知')}, index={meta.get('index', '未知')}"
                )
            output_lines.append("提示：再次输入 0 返回简洁帮助。")
        help_mode = 0 if help_mode == 1 else 1
        state["help_mode"] = help_mode
        output_lines.extend(_render_normal(story, state["node_id"], flags, stats))
        return state, output_lines, False

    if trimmed == "9":
        output_lines.append("已退出游戏。")
        return state, output_lines, True

    if trimmed == "8":
        if history:
            new_node_id = history.pop()
            state = {
                "node_id": new_node_id,
                "history_stack": history,
                "mode": "normal",
                "flags": flags,
                "stats": stats,
            }
        else:
            output_lines.append("无法后退，已经在起点。")
        output_lines.extend(_render_normal(story, state["node_id"], flags, stats))
        return state, output_lines, False

    if trimmed.isdigit():
        choice_index = int(trimmed)
        choices = get_choices(story, state["node_id"], flags, stats)
        if 1 <= choice_index <= len(choices):
            next_node_id, new_flags, delta_stats = apply_choice(
                story, state["node_id"], choice_index, flags, stats
            )
            last_choice = choices[choice_index - 1]["text"]
            flags = flags.union(new_flags)
            history.append(state["node_id"])
            for key, delta in delta_stats.items():
                stats[key] = stats.get(key, 0) + delta
                if delta != 0:
                    if key == "silver":
                        if delta > 0:
                            output_lines.append("钱袋沉了一些。")
                        else:
                            output_lines.append("钱袋轻了些。")
                    elif key == "suspicion":
                        if delta > 0:
                            output_lines.append("你感觉目光变得更锋利了。")
                        else:
                            output_lines.append("风声似乎缓了一点。")
            if stats.get("silver", 0) < 0:
                stats["silver"] = 0
            if stats_config:
                suspicion_max = stats_config.get("suspicion_max")
                fail_node = stats_config.get("suspicion_fail_node")
                if suspicion_max is not None and fail_node and stats.get("suspicion", 0) >= suspicion_max:
                    state = {
                        "node_id": fail_node,
                        "history_stack": history,
                        "mode": "ending",
                        "flags": flags,
                        "stats": stats,
                        "last_choice": last_choice,
                        "help_mode": help_mode,
                    }
                    output_lines.append("你察觉风声骤紧，麻烦在逼近。")
                    output_lines.extend(_render_ending(story, fail_node, stats))
                    return state, output_lines, False
            if story["nodes"][next_node_id].get("ending"):
                state = {
                    "node_id": next_node_id,
                    "history_stack": history,
                    "mode": "ending",
                    "flags": flags,
                    "stats": stats,
                    "last_choice": last_choice,
                    "help_mode": help_mode,
                }
                output_lines.extend(_render_ending(story, next_node_id, stats))
            else:
                state = {
                    "node_id": next_node_id,
                    "history_stack": history,
                    "mode": "normal",
                    "flags": flags,
                    "stats": stats,
                    "last_choice": last_choice,
                    "help_mode": help_mode,
                }
                output_lines.extend(_render_normal(story, next_node_id, flags, stats))
            return state, output_lines, False

    output_lines.append("无效输入")
    output_lines.extend(_render_normal(story, state["node_id"], flags, stats))
    return state, output_lines, False


def run_game(story_path: str = "story.json", input_fn=input, output_fn=print):
    try:
        story = load_story(story_path)
        validate_story(story)
    except (FileNotFoundError, ValueError) as exc:
        output_fn(str(exc))
        return 1

    output_fn(f"=== {story['title']} ===")
    state = {
        "node_id": story["start"],
        "history_stack": [],
        "mode": "normal",
        "flags": set(),
        "stats": {"suspicion": 0, "silver": 0},
        "last_choice": None,
        "help_mode": 0,
    }
    for line in _render_normal(story, state["node_id"], state["flags"], state["stats"]):
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
