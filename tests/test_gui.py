import unittest

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


if __name__ == "__main__":
    unittest.main()
