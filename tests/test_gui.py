import unittest

from kanban.agent import AgentInvocation
from kanban.gui import KanbanGUI


class _FakeButton:
    def __init__(self) -> None:
        self.config: dict[str, str] = {}

    def configure(self, **kwargs: str) -> None:
        self.config.update(kwargs)

    def __getitem__(self, key: str) -> str:
        return self.config[key]


class _FakeController:
    def __init__(self, states: list[str]) -> None:
        self._states = states
        self._index = 0

    @property
    def state(self) -> str:
        return self._states[self._index]

    def cycle_state(self) -> str:
        self._index = min(self._index + 1, len(self._states) - 1)
        return self.state


class _FakeConfigController(_FakeController):
    def __init__(self) -> None:
        super().__init__(["stopped"])
        self.updated: list[tuple[str, str]] = []
        self._last_invocation: AgentInvocation | None = None

    def update_execution_config(self, command: str, prompt_template: str) -> None:
        self.updated.append((command, prompt_template))

    def last_invocation(self) -> AgentInvocation | None:
        return self._last_invocation


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def configure(self, **kwargs: str) -> None:
        self.text = kwargs.get("text", self.text)


class KanbanGUITests(unittest.TestCase):
    def test_agent_button_defaults_to_stopped_red(self):
        gui = KanbanGUI.__new__(KanbanGUI)
        gui._agent_button = _FakeButton()
        gui._agent_state = "stopped"

        gui._sync_agent_button()

        self.assertEqual(gui._agent_button["text"], "STOPPED")
        self.assertEqual(gui._agent_button["bg"], "#DC2626")

    def test_toggle_agent_button_cycles_through_three_states(self):
        gui = KanbanGUI.__new__(KanbanGUI)
        gui._agent_button = _FakeButton()
        gui._agent_controller = None
        gui._agent_state = "stopped"
        gui._sync_agent_button()

        gui._toggle_agent_state()
        self.assertEqual(gui._agent_button["text"], "RUNNING")
        self.assertEqual(gui._agent_button["bg"], "#16A34A")

        gui._toggle_agent_state()
        self.assertEqual(gui._agent_button["text"], "FINISHING")
        self.assertEqual(gui._agent_button["bg"], "#EAB308")

        gui._toggle_agent_state()
        self.assertEqual(gui._agent_button["text"], "STOPPED")
        self.assertEqual(gui._agent_button["bg"], "#DC2626")

    def test_toggle_agent_button_uses_controller_state(self):
        gui = KanbanGUI.__new__(KanbanGUI)
        gui._agent_button = _FakeButton()
        gui._agent_controller = _FakeController(["stopped", "finishing"])
        gui._agent_state = "stopped"
        gui._sync_agent_button()

        gui._toggle_agent_state()
        self.assertEqual(gui._agent_button["text"], "FINISHING")
        self.assertEqual(gui._agent_button["bg"], "#EAB308")

    def test_push_agent_execution_config_updates_controller(self):
        gui = KanbanGUI.__new__(KanbanGUI)
        gui._agent_controller = _FakeConfigController()

        gui._push_agent_execution_config("codex exec --model gpt-5", "Implement TASK_TEXT")

        self.assertEqual(
            gui._agent_controller.updated,
            [("codex exec --model gpt-5", "Implement TASK_TEXT")],
        )

    def test_sync_execution_preview_shows_last_invocation(self):
        gui = KanbanGUI.__new__(KanbanGUI)
        controller = _FakeConfigController()
        controller._last_invocation = AgentInvocation(
            task_id=7,
            command="codex exec",
            prompt="Implement API task",
            argv=["codex", "exec", "Implement API task"],
        )
        gui._agent_controller = controller
        gui._last_exec_command_label = _FakeLabel()
        gui._last_exec_prompt_label = _FakeLabel()

        gui._sync_execution_preview()

        self.assertEqual(gui._last_exec_command_label.text, "codex exec")
        self.assertEqual(gui._last_exec_prompt_label.text, "Implement API task")


if __name__ == "__main__":
    unittest.main()
