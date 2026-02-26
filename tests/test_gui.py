import unittest

from kanban.agent import AgentInvocation
from kanban.model import TaskStatus
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


class _FakeCanvas:
    def __init__(self, start: float = 0.0, end: float = 1.0) -> None:
        self.start = start
        self.end = end
        self.moved_to: list[float] = []

    def yview(self) -> tuple[float, float]:
        return (self.start, self.end)

    def yview_moveto(self, fraction: float) -> None:
        self.moved_to.append(fraction)


class _FakeCardCanvas:
    def __init__(self, actual_width: int, configured_width: int) -> None:
        self._actual_width = actual_width
        self._configured_width = configured_width

    def winfo_width(self) -> int:
        return self._actual_width

    def cget(self, key: str) -> int:
        if key != "width":
            raise KeyError(key)
        return self._configured_width


class _FakeWidget:
    def __init__(self, master: object | None = None) -> None:
        self.master = master


class _FakeBoard:
    def __init__(self) -> None:
        self.deleted: list[int] = []

    def delete_task(self, task_id: int) -> None:
        self.deleted.append(task_id)


class _FakeTask:
    def __init__(self, task_id: int) -> None:
        self.id = task_id


class _FakeCreateBoard:
    def __init__(self) -> None:
        self.created: list[tuple[str, str]] = []
        self.moved: list[tuple[int, TaskStatus, int | None]] = []
        self._next_id = 1

    def create_task(self, title: str, color: str) -> _FakeTask:
        self.created.append((title, color))
        task = _FakeTask(self._next_id)
        self._next_id += 1
        return task

    def move_task(self, task_id: int, status: TaskStatus, index: int | None = None) -> None:
        self.moved.append((task_id, status, index))


class _FakeStringVar:
    def __init__(self, value: str) -> None:
        self._value = value
        self.set_calls: list[str] = []

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value
        self.set_calls.append(value)


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

    def test_estimate_task_card_height_keeps_minimum_for_short_title(self):
        gui = KanbanGUI.__new__(KanbanGUI)

        height = gui._estimate_task_card_height("Short title", text_width_px=320)

        self.assertEqual(height, 58)

    def test_estimate_task_card_height_grows_for_long_title(self):
        gui = KanbanGUI.__new__(KanbanGUI)
        long_title = "Implement drag and drop behavior across columns with state sync and API updates"

        height = gui._estimate_task_card_height(long_title, text_width_px=120)

        self.assertGreaterEqual(height, 120)

    def test_estimate_task_card_height_handles_explicit_newlines(self):
        gui = KanbanGUI.__new__(KanbanGUI)

        one_line = gui._estimate_task_card_height("Line one", text_width_px=220)
        three_lines = gui._estimate_task_card_height("Line one\nLine two\nLine three", text_width_px=220)

        self.assertGreater(three_lines, one_line)

    def test_capture_scroll_positions_uses_canvas_view_start(self):
        gui = KanbanGUI.__new__(KanbanGUI)
        gui._column_canvases = {
            TaskStatus.TODO: _FakeCanvas(start=0.25, end=0.55),
            TaskStatus.IN_PROGRESS: _FakeCanvas(start=0.4, end=0.8),
            TaskStatus.DONE: _FakeCanvas(start=0.0, end=0.3),
        }

        positions = gui._capture_scroll_positions()

        self.assertEqual(
            positions,
            {
                TaskStatus.TODO: 0.25,
                TaskStatus.IN_PROGRESS: 0.4,
                TaskStatus.DONE: 0.0,
            },
        )

    def test_restore_scroll_positions_clamps_and_applies(self):
        gui = KanbanGUI.__new__(KanbanGUI)
        todo = _FakeCanvas()
        in_progress = _FakeCanvas()
        done = _FakeCanvas()
        gui._column_canvases = {
            TaskStatus.TODO: todo,
            TaskStatus.IN_PROGRESS: in_progress,
            TaskStatus.DONE: done,
        }

        gui._restore_scroll_positions(
            {
                TaskStatus.TODO: -0.4,
                TaskStatus.IN_PROGRESS: 0.7,
                TaskStatus.DONE: 1.4,
            }
        )

        self.assertEqual(todo.moved_to, [0.0])
        self.assertEqual(in_progress.moved_to, [0.7])
        self.assertEqual(done.moved_to, [1.0])

    def test_task_card_width_uses_rendered_width_before_configured_width(self):
        gui = KanbanGUI.__new__(KanbanGUI)
        card = _FakeCardCanvas(actual_width=240, configured_width=820)

        width = gui._task_card_width(card, event=None)  # type: ignore[arg-type]

        self.assertEqual(width, 238)

    def test_delete_task_removes_from_board_and_rerenders(self):
        gui = KanbanGUI.__new__(KanbanGUI)
        gui.board = _FakeBoard()
        render_calls: list[bool] = []
        gui._render = lambda force=False: render_calls.append(force)

        gui._delete_task(7)

        self.assertEqual(gui.board.deleted, [7])
        self.assertEqual(render_calls, [True])

    def test_add_task_places_new_task_at_top_of_todo(self):
        gui = KanbanGUI.__new__(KanbanGUI)
        gui.board = _FakeCreateBoard()
        gui.new_task_var = _FakeStringVar("  New task  ")
        gui._color_for_new_task = lambda: "#112233"
        render_calls: list[bool] = []
        gui._render = lambda force=False: render_calls.append(force)

        gui.add_task()

        self.assertEqual(gui.board.created, [("New task", "#112233")])
        self.assertEqual(gui.board.moved, [(1, TaskStatus.TODO, 0)])
        self.assertEqual(gui.new_task_var.set_calls, [""])
        self.assertEqual(render_calls, [True])

    def test_status_for_widget_maps_ignore_column_container(self):
        gui = KanbanGUI.__new__(KanbanGUI)
        ignore_container = _FakeWidget()
        gui._task_widget_status = {}
        gui._column_frames = {
            TaskStatus.TODO: _FakeWidget(),
            TaskStatus.IN_PROGRESS: _FakeWidget(),
            TaskStatus.DONE: _FakeWidget(),
            TaskStatus.IGNORE: ignore_container,
        }
        gui._column_canvases = {}
        gui._column_content_frames = {}

        inner_widget = _FakeWidget(master=ignore_container)

        status = gui._status_for_widget(inner_widget)  # type: ignore[arg-type]

        self.assertEqual(status, TaskStatus.IGNORE)


if __name__ == "__main__":
    unittest.main()
