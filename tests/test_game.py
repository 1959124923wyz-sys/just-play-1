import unittest

from game import apply_choice, get_choices, load_story, run_game, step, validate_story


class GameTests(unittest.TestCase):
    def setUp(self):
        self.story = load_story("story.json")
        validate_story(self.story)

    def test_can_load_story(self):
        self.assertIn("nodes", self.story)

    def test_invalid_input_stays_in_node(self):
        state = {"node_id": self.story["start"], "history_stack": [], "mode": "normal"}
        state, output_lines, should_exit = step(state, "abc", self.story)
        self.assertFalse(should_exit)
        self.assertEqual(state["node_id"], self.story["start"])
        self.assertIn("无效输入", output_lines)

    def test_choice_jumps_to_correct_node(self):
        start = self.story["start"]
        next_node, _, _ = apply_choice(self.story, start, 1, set(), {})
        choices = get_choices(self.story, start)
        self.assertEqual(next_node, choices[0]["next"])

    def test_step_choice_jumps_to_correct_node(self):
        state = {"node_id": self.story["start"], "history_stack": [], "mode": "normal"}
        state, _, _ = step(state, "1", self.story)
        expected_next = get_choices(self.story, self.story["start"])[0]["next"]
        self.assertEqual(state["node_id"], expected_next)

    def test_can_go_back_to_previous_node(self):
        state = {"node_id": self.story["start"], "history_stack": [], "mode": "normal"}
        state, _, _ = step(state, "1", self.story)
        state, _, _ = step(state, "8", self.story)
        self.assertEqual(state["node_id"], self.story["start"])

    def test_back_at_start_shows_message(self):
        state = {"node_id": self.story["start"], "history_stack": [], "mode": "normal"}
        state, output_lines, _ = step(state, "8", self.story)
        self.assertEqual(state["node_id"], self.story["start"])
        self.assertIn("无法后退，已经在起点。", output_lines)

    def test_restart_from_ending_clears_history(self):
        state = {"node_id": self.story["start"], "history_stack": [], "mode": "normal"}
        state, _, _ = step(state, "2", self.story)
        state, _, _ = step(state, "2", self.story)
        self.assertEqual(state["mode"], "ending")
        self.assertGreater(len(state["history_stack"]), 0)
        state, _, _ = step(state, "1", self.story)
        self.assertEqual(state["node_id"], self.story["start"])
        self.assertEqual(state["history_stack"], [])
        self.assertEqual(state["mode"], "normal")

    def test_set_flags_applied(self):
        story = {
            "title": "测试",
            "start": "start",
            "nodes": {
                "start": {
                    "text": "起点",
                    "choices": [
                        {"text": "拿线索", "next": "next", "set_flags": ["clue"]},
                        {"text": "等待", "next": "next"},
                    ],
                },
                "next": {"text": "继续", "choices": [{"text": "回去", "next": "start"}]},
            },
        }
        validate_story(story)
        state = {"node_id": "start", "history_stack": [], "mode": "normal", "flags": set()}
        state, _, _ = step(state, "1", story)
        self.assertIn("clue", state["flags"])

    def test_requires_filters_choices(self):
        story = {
            "title": "测试",
            "start": "start",
            "flag_descriptions": {"clue": "线索"},
            "nodes": {
                "start": {
                    "text": "起点",
                    "choices": [
                        {"text": "获取线索", "next": "start", "set_flags": ["clue"]},
                        {"text": "隐藏选项", "next": "secret", "requires": ["clue"]},
                    ],
                },
                "secret": {"text": "秘密结局", "ending": True},
            },
        }
        validate_story(story)
        choices_without = get_choices(story, "start", set())
        self.assertEqual(len(choices_without), 1)
        choices_with = get_choices(story, "start", {"clue"})
        self.assertEqual(len(choices_with), 2)

    def test_empty_input_renders_without_change(self):
        state = {"node_id": self.story["start"], "history_stack": [], "mode": "normal"}
        state, output_lines, _ = step(state, "", self.story)
        self.assertEqual(state["node_id"], self.story["start"])
        self.assertIn(self.story["nodes"][self.story["start"]]["text"], output_lines)

    def test_empty_input_renders_twice(self):
        inputs = iter(["", "9"])
        outputs = []

        def input_fn(_prompt):
            return next(inputs)

        def output_fn(message):
            outputs.append(message)

        run_game("story.json", input_fn=input_fn, output_fn=output_fn)

        node_text = self.story["nodes"][self.story["start"]]["text"]
        self.assertGreaterEqual(outputs.count(node_text), 2)

    def test_exit_input_sets_should_exit(self):
        state = {"node_id": self.story["start"], "history_stack": [], "mode": "normal"}
        _, output_lines, should_exit = step(state, "9", self.story)
        self.assertTrue(should_exit)
        self.assertIn("已退出游戏。", output_lines)

    def test_delta_stats_applied_and_clamped(self):
        story = {
            "title": "测试",
            "start": "start",
            "nodes": {
                "start": {
                    "text": "起点",
                    "choices": [
                        {
                            "text": "冒险",
                            "next": "start",
                            "delta_stats": {"suspicion": 2, "silver": -5},
                        }
                    ],
                }
            },
        }
        validate_story(story)
        state = {"node_id": "start", "history_stack": [], "mode": "normal"}
        state, _, _ = step(state, "1", story)
        self.assertEqual(state["stats"]["suspicion"], 2)
        self.assertEqual(state["stats"]["silver"], 0)

    def test_requires_stats_filters_choices(self):
        story = {
            "title": "测试",
            "start": "start",
            "flag_descriptions": {},
            "nodes": {
                "start": {
                    "text": "起点",
                    "choices": [
                        {"text": "普通", "next": "start"},
                        {"text": "买通", "next": "start", "requires_stats": {"silver": 3}},
                    ],
                }
            },
        }
        validate_story(story)
        choices_without = get_choices(story, "start", set(), {"silver": 0})
        self.assertEqual(len(choices_without), 1)
        choices_with = get_choices(story, "start", set(), {"silver": 3})
        self.assertEqual(len(choices_with), 2)

    def test_suspicion_threshold_forces_ending(self):
        story = {
            "title": "测试",
            "start": "start",
            "stats_config": {"suspicion_max": 3, "suspicion_fail_node": "ending_suspicion"},
            "flag_descriptions": {},
            "nodes": {
                "start": {
                    "text": "起点",
                    "choices": [
                        {"text": "冒险", "next": "start", "delta_stats": {"suspicion": 3}}
                    ],
                },
                "ending_suspicion": {"text": "结局", "ending": True},
            },
        }
        validate_story(story)
        state = {"node_id": "start", "history_stack": [], "mode": "normal"}
        state, _, _ = step(state, "1", story)
        self.assertEqual(state["node_id"], "ending_suspicion")
        self.assertEqual(state["mode"], "ending")

    def test_locked_choices_visible(self):
        story = {
            "title": "测试",
            "start": "start",
            "flag_descriptions": {"clue_a": "线索A"},
            "nodes": {
                "start": {
                    "text": "起点",
                    "choices": [
                        {"text": "普通", "next": "start"},
                        {"text": "需要线索", "next": "start", "requires": ["clue_a"]},
                        {"text": "买通", "next": "start", "requires_stats": {"silver": 3}},
                    ],
                }
            },
        }
        validate_story(story)
        state = {"node_id": "start", "history_stack": [], "mode": "normal"}
        _, output_lines, _ = step(state, "", story)
        output = "\n".join(output_lines)
        self.assertIn("尚不可行", output)
        self.assertIn("条件未具备", output)
        self.assertIn("钱袋不够沉", output)

    def test_help_panel_contains_sections(self):
        story = {
            "title": "测试",
            "start": "start",
            "flag_descriptions": {"clue_a": "线索A"},
            "nodes": {
                "start": {
                    "text": "起点文本",
                    "title": "起点",
                    "where": "汴梁",
                    "goal": "求真",
                    "summary": "起点摘要",
                    "choices": [{"text": "前进", "next": "next"}],
                },
                "next": {
                    "text": "继续",
                    "title": "继续",
                    "summary": "继续摘要",
                    "choices": [{"text": "返回", "next": "start"}],
                },
            },
        }
        validate_story(story)
        state = {
            "node_id": "start",
            "history_stack": ["next"],
            "mode": "normal",
            "flags": {"clue_a"},
            "stats": {"suspicion": 1, "silver": 2},
            "last_choice": "前进",
        }
        _, output_lines, _ = step(state, "0", story)
        output = "\n".join(output_lines)
        self.assertIn("帮助：输入", output)
        self.assertIn("回车可重显", output)

    def test_help_panel_debug_sections(self):
        story = {
            "title": "测试",
            "start": "start",
            "flag_descriptions": {"clue_a": "线索A"},
            "nodes": {
                "start": {
                    "text": "起点文本",
                    "title": "起点",
                    "where": "汴梁",
                    "goal": "求真",
                    "summary": "起点摘要",
                    "choices": [{"text": "前进", "next": "next"}],
                },
                "next": {
                    "text": "继续",
                    "title": "继续",
                    "summary": "继续摘要",
                    "choices": [{"text": "返回", "next": "start"}],
                },
            },
        }
        validate_story(story)
        state = {
            "node_id": "start",
            "history_stack": ["next"],
            "mode": "normal",
            "flags": {"clue_a"},
            "stats": {"suspicion": 1, "silver": 2},
            "last_choice": "前进",
        }
        state, _, _ = step(state, "0", story)
        _, output_lines, _ = step(state, "0", story)
        output = "\n".join(output_lines)
        self.assertIn("调试信息", output)
        self.assertIn("flags=", output)
        self.assertIn("stats:", output)

    def test_normal_render_has_no_status_line(self):
        story = {
            "title": "测试",
            "start": "start",
            "flag_descriptions": {},
            "nodes": {
                "start": {
                    "text": "起点文本",
                    "choices": [{"text": "前进", "next": "start"}],
                },
            },
        }
        validate_story(story)
        state = {"node_id": "start", "history_stack": [], "mode": "normal"}
        _, output_lines, _ = step(state, "", story)
        output = "\n".join(output_lines)
        self.assertNotIn("状态：嫌疑", output)

    def test_strip_scene_prefix_on_render(self):
        story = {
            "title": "测试",
            "start": "start",
            "flag_descriptions": {},
            "nodes": {
                "start": {
                    "text": "风月暗线第2场：帘后传来低语，酒香混着寒意。",
                    "choices": [{"text": "前进", "next": "start"}],
                },
            },
        }
        validate_story(story)
        state = {"node_id": "start", "history_stack": [], "mode": "normal"}
        _, output_lines, _ = step(state, "", story)
        output = "\n".join(output_lines)
        self.assertNotIn("风月暗线第2场", output)
        self.assertIn("帘后传来低语", output)

    def test_can_reach_ending_and_exit(self):
        inputs = iter(["2", "2", "9"])
        outputs = []

        def input_fn(_prompt):
            return next(inputs)

        def output_fn(message):
            outputs.append(message)

        result = run_game("story.json", input_fn=input_fn, output_fn=output_fn)

        self.assertEqual(result, 0)
        self.assertIn("结局：输入 1 重开，9 退出。", outputs)


if __name__ == "__main__":
    unittest.main()
