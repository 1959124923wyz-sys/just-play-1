import unittest

from game import apply_choice, get_choices, load_story, run_game, step, validate_story


class GameTests(unittest.TestCase):
    def setUp(self):
        self.story = load_story("story.json")
        validate_story(self.story)

    def test_can_load_story(self):
        self.assertIn("nodes", self.story)

    def test_invalid_input_stays_in_node(self):
        inputs = iter(["abc", "9"])
        outputs = []

        def input_fn(_prompt):
            return next(inputs)

        def output_fn(message):
            outputs.append(message)

        run_game("story.json", input_fn=input_fn, output_fn=output_fn)

        node_text = self.story["nodes"][self.story["start"]]["text"]
        self.assertGreaterEqual(outputs.count(node_text), 2)
        self.assertIn("无效输入", outputs)

    def test_choice_jumps_to_correct_node(self):
        start = self.story["start"]
        next_node = apply_choice(self.story, start, 1)
        choices = get_choices(self.story, start)
        self.assertEqual(next_node, choices[0]["next"])

    def test_can_go_back_to_previous_node(self):
        state = {"node_id": self.story["start"], "history_stack": [], "mode": "normal"}
        state, _, _ = step(state, "1", self.story)
        state, _, _ = step(state, "#", self.story)
        self.assertEqual(state["node_id"], self.story["start"])

    def test_back_at_start_shows_message(self):
        state = {"node_id": self.story["start"], "history_stack": [], "mode": "normal"}
        state, output_lines, _ = step(state, "#", self.story)
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

    def test_empty_input_renders_without_change(self):
        state = {"node_id": self.story["start"], "history_stack": [], "mode": "normal"}
        state, output_lines, _ = step(state, "", self.story)
        self.assertEqual(state["node_id"], self.story["start"])
        self.assertIn(self.story["nodes"][self.story["start"]]["text"], output_lines)

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
