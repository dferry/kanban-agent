from __future__ import annotations

import random
import tkinter as tk
import textwrap
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

from kanban.agent import AgentController, STOP_TASK_TITLE, TASK_TEXT_TOKEN, default_prompt_template
from kanban.model import KanbanBoard, TaskStatus


class KanbanGUI:
    _STATUS_TITLE = {
        TaskStatus.TODO: "To Do",
        TaskStatus.IN_PROGRESS: "In Progress",
        TaskStatus.DONE: "Done",
        TaskStatus.IGNORE: "Ignore",
    }

    _STATUS_COLORS = {
        TaskStatus.TODO: "#1D4ED8",
        TaskStatus.IN_PROGRESS: "#B45309",
        TaskStatus.DONE: "#047857",
        TaskStatus.IGNORE: "#6B7280",
    }
    _BOARD_STATUSES: tuple[TaskStatus, ...] = (
        TaskStatus.TODO,
        TaskStatus.IN_PROGRESS,
        TaskStatus.DONE,
        TaskStatus.IGNORE,
    )

    _NEW_TASK_COLORS = [
        ("Red", "#ef4444"),
        ("Green", "#22c55e"),
        ("Blue", "#3b82f6"),
        ("Purple", "#a855f7"),
        ("Cyan", "#06b6d4"),
        ("Magenta", "#d946ef"),
    ]

    _CANVAS_BG = "#F5F7FB"
    _CARD_BG = "#FFFFFF"
    _CARD_BORDER = "#D7DEE9"
    _CARD_BORDER_ACTIVE = "#0F172A"
    _LIST_BG = "#FBFCFF"
    _STOP_TASK_COLOR = "#0f172a"
    _AGENT_STATES = ("stopped", "running", "finishing")
    _AGENT_BUTTON_STYLE = {
        "stopped": {"text": "STOPPED", "bg": "#DC2626", "fg": "#FFFFFF"},
        "running": {"text": "RUNNING", "bg": "#16A34A", "fg": "#FFFFFF"},
        "finishing": {"text": "FINISHING", "bg": "#EAB308", "fg": "#0F172A"},
    }

    def __init__(
        self,
        board: KanbanBoard,
        board_file: str | Path | None = None,
        agent_controller: AgentController | None = None,
    ) -> None:
        self.board = board
        self.board_file = Path(board_file) if board_file else None
        self._agent_controller = agent_controller
        self.root = tk.Tk()
        self.root.title("Kanban Board")
        self.root.geometry("1320x660")
        self.root.configure(bg=self._CANVAS_BG)

        self._column_frames: dict[TaskStatus, tk.Frame] = {}
        self._count_labels: dict[TaskStatus, tk.Label] = {}
        self._column_canvases: dict[TaskStatus, tk.Canvas] = {}
        self._column_content_frames: dict[TaskStatus, tk.Frame] = {}
        self._column_window_ids: dict[TaskStatus, int] = {}
        self._id_maps: dict[TaskStatus, list[int]] = {status: [] for status in self._BOARD_STATUSES}

        self._task_widgets: dict[int, tk.Canvas] = {}
        self._task_widget_status: dict[str, TaskStatus] = {}

        self._color_buttons: dict[str, tk.Widget] = {}
        self._new_task_color = "rng"
        self._cycle_index = 0

        self._drag_source_status: TaskStatus | None = None
        self._drag_source_index: int | None = None
        self._active_drop_status: TaskStatus | None = None
        self._refresh_job: str | None = None
        self._last_board_fingerprint: tuple[tuple[int, str, str, str], ...] | None = None
        self._agent_state = "stopped"
        self._agent_button: tk.Button | None = None
        self._agent_command_var: tk.StringVar | None = None
        self._agent_prompt_input: tk.Text | None = None
        self._last_exec_command_label: tk.Label | None = None
        self._last_exec_prompt_label: tk.Label | None = None
        self._todo_context_menu: tk.Menu | None = None

        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self.root.bind_all("<B1-Motion>", self._on_global_drag_motion)
        self.root.bind_all("<ButtonRelease-1>", self._on_drag_release)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind_all("<Button-4>", self._on_mousewheel)
        self.root.bind_all("<Button-5>", self._on_mousewheel)
        self.refresh()

    def _build_layout(self) -> None:
        top = tk.Frame(self.root, bg=self._CANVAS_BG, padx=18, pady=16)
        top.pack(fill=tk.X)

        title = tk.Label(
            top,
            text="Kanban Board",
            bg=self._CANVAS_BG,
            fg="#0F172A",
            font=("Helvetica", 18, "bold"),
        )
        title.grid(row=0, column=0, sticky="w")

        hint = tk.Label(
            top,
            text="Pick a color, create tasks, then drag them between columns.",
            bg=self._CANVAS_BG,
            fg="#475569",
            font=("Helvetica", 10),
        )
        hint.grid(row=1, column=0, sticky="w", pady=(4, 10))

        create_row = tk.Frame(top, bg=self._CANVAS_BG)
        create_row.grid(row=2, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)

        self.new_task_var = tk.StringVar()
        entry = tk.Entry(
            create_row,
            textvariable=self.new_task_var,
            relief=tk.FLAT,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
            font=("Helvetica", 11),
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=7)
        entry.bind("<Return>", lambda _event: self.add_task())

        add_button = tk.Button(
            create_row,
            text="Add Task",
            command=self.add_task,
            bg="#2563EB",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            padx=16,
            pady=7,
            font=("Helvetica", 10, "bold"),
            cursor="hand2",
        )
        add_button.pack(side=tk.LEFT, padx=(10, 0))

        save_button = tk.Button(
            create_row,
            text="Save Board",
            command=self.save_board,
            bg="#0F172A",
            fg="#FFFFFF",
            activebackground="#1E293B",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            padx=14,
            pady=7,
            font=("Helvetica", 10, "bold"),
            cursor="hand2",
        )
        save_button.pack(side=tk.LEFT, padx=(8, 0))

        self._agent_button = tk.Button(
            create_row,
            text="STOPPED",
            command=self._toggle_agent_state,
            bg="#DC2626",
            fg="#FFFFFF",
            activebackground="#DC2626",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            padx=14,
            pady=7,
            font=("Helvetica", 10, "bold"),
            cursor="hand2",
        )
        self._agent_button.pack(side=tk.LEFT, padx=(8, 0))
        self._sync_agent_button()

        color_row = tk.Frame(top, bg=self._CANVAS_BG)
        color_row.grid(row=3, column=0, sticky="w", pady=(10, 0))

        color_label = tk.Label(
            color_row,
            text="New task color:",
            bg=self._CANVAS_BG,
            fg="#334155",
            font=("Helvetica", 10, "bold"),
        )
        color_label.pack(side=tk.LEFT, padx=(0, 8))

        for name, color in self._NEW_TASK_COLORS:
            button = tk.Button(
                color_row,
                text=name,
                command=lambda c=color: self._set_new_task_color(c),
                bg=color,
                fg=self._text_color_for_background(color),
                activebackground=color,
                activeforeground=self._text_color_for_background(color),
                relief=tk.FLAT,
                padx=10,
                pady=4,
                font=("Helvetica", 9, "bold"),
                cursor="hand2",
            )
            button.pack(side=tk.LEFT, padx=3)
            self._color_buttons[color] = button

        random_button = tk.Button(
            color_row,
            text="RNG",
            command=lambda: self._set_new_task_color("rng"),
            bg="#0F172A",
            fg="#FFFFFF",
            activebackground="#1E293B",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            font=("Helvetica", 9, "bold"),
            cursor="hand2",
        )
        random_button.pack(side=tk.LEFT, padx=(8, 0))
        self._color_buttons["rng"] = random_button

        cycle_button = self._create_cycle_button(color_row)
        cycle_button.pack(side=tk.LEFT, padx=(6, 0))
        self._color_buttons["cycle"] = cycle_button
        self._sync_color_button_states()

        columns_frame = tk.Frame(self.root, bg=self._CANVAS_BG, padx=14, pady=10)
        columns_frame.pack(fill=tk.BOTH, expand=True)

        for i, status in enumerate(self._BOARD_STATUSES):
            columns_frame.grid_columnconfigure(i, weight=1)

            container = tk.Frame(
                columns_frame,
                bg=self._CARD_BG,
                highlightthickness=2,
                highlightbackground=self._CARD_BORDER,
            )
            container.grid(row=0, column=i, sticky="nsew", padx=6)
            self._column_frames[status] = container

            header = tk.Frame(container, bg=self._CARD_BG, padx=12, pady=10)
            header.pack(fill=tk.X)

            dot = tk.Label(header, text="●", bg=self._CARD_BG, fg=self._STATUS_COLORS[status], font=("Helvetica", 10, "bold"))
            dot.pack(side=tk.LEFT)

            label = tk.Label(
                header,
                text=self._STATUS_TITLE[status],
                bg=self._CARD_BG,
                fg="#0F172A",
                font=("Helvetica", 12, "bold"),
            )
            label.pack(side=tk.LEFT, padx=(6, 0))

            count = tk.Label(
                header,
                text="0",
                bg="#E2E8F0",
                fg="#1E293B",
                padx=8,
                pady=2,
                font=("Helvetica", 9, "bold"),
            )
            count.pack(side=tk.RIGHT)
            self._count_labels[status] = count

            list_region = tk.Frame(container, bg=self._CARD_BG)
            list_region.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

            scrollbar = tk.Scrollbar(list_region, orient=tk.VERTICAL)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            canvas = tk.Canvas(list_region, bg=self._LIST_BG, bd=0, highlightthickness=0)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            canvas.configure(yscrollcommand=scrollbar.set)
            scrollbar.configure(command=canvas.yview)

            content = tk.Frame(canvas, bg=self._LIST_BG)
            window_id = canvas.create_window((0, 0), window=content, anchor="nw")
            content.bind("<Configure>", lambda _event, s=status: self._on_content_configure(s))
            canvas.bind("<Configure>", lambda event, s=status: self._on_canvas_configure(event, s))

            self._column_canvases[status] = canvas
            self._column_content_frames[status] = content
            self._column_window_ids[status] = window_id
            if status == TaskStatus.TODO:
                self._bind_todo_flow_shortcuts(canvas, content)

        self._build_agent_execution_panel()

    def _build_agent_execution_panel(self) -> None:
        box = tk.Frame(self.root, bg="#E2E8F0", padx=14, pady=10)
        box.pack(fill=tk.X, padx=14, pady=(0, 10))

        title = tk.Label(
            box,
            text="Agent Execution Box",
            bg="#E2E8F0",
            fg="#0F172A",
            font=("Helvetica", 10, "bold"),
        )
        title.grid(row=0, column=0, sticky="w")

        help_label = tk.Label(
            box,
            text=f"Use {TASK_TEXT_TOKEN} in the prompt; it is replaced with each task title at execution time.",
            bg="#E2E8F0",
            fg="#334155",
            font=("Helvetica", 9),
        )
        help_label.grid(row=1, column=0, sticky="w", pady=(2, 8))

        command_label = tk.Label(box, text="Command:", bg="#E2E8F0", fg="#1E293B", font=("Helvetica", 9, "bold"))
        command_label.grid(row=2, column=0, sticky="w")

        command, prompt_template = self._initial_execution_templates()
        self._agent_command_var = tk.StringVar(value=command)
        self._agent_command_var.trace_add("write", self._on_agent_execution_config_change)

        command_entry = tk.Entry(
            box,
            textvariable=self._agent_command_var,
            relief=tk.FLAT,
            bg="#FFFFFF",
            fg="#0F172A",
            insertbackground="#0F172A",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
            font=("Helvetica", 10),
        )
        command_entry.grid(row=3, column=0, sticky="ew", pady=(4, 8), ipady=5)

        prompt_label = tk.Label(box, text="Prompt Template:", bg="#E2E8F0", fg="#1E293B", font=("Helvetica", 9, "bold"))
        prompt_label.grid(row=4, column=0, sticky="w")

        self._agent_prompt_input = tk.Text(
            box,
            height=4,
            relief=tk.FLAT,
            bg="#FFFFFF",
            fg="#0F172A",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
            font=("Helvetica", 10),
            wrap=tk.WORD,
        )
        self._agent_prompt_input.grid(row=5, column=0, sticky="ew", pady=(4, 8))
        self._agent_prompt_input.insert("1.0", prompt_template)
        self._agent_prompt_input.bind("<KeyRelease>", self._on_agent_execution_config_change)

        last_header = tk.Label(
            box,
            text="Last Invocation:",
            bg="#E2E8F0",
            fg="#1E293B",
            font=("Helvetica", 9, "bold"),
        )
        last_header.grid(row=6, column=0, sticky="w")

        self._last_exec_command_label = tk.Label(
            box,
            text="-",
            bg="#E2E8F0",
            fg="#0F172A",
            font=("Helvetica", 9),
            anchor="w",
            justify=tk.LEFT,
        )
        self._last_exec_command_label.grid(row=7, column=0, sticky="w", pady=(2, 0))

        self._last_exec_prompt_label = tk.Label(
            box,
            text="-",
            bg="#E2E8F0",
            fg="#0F172A",
            font=("Helvetica", 9),
            anchor="w",
            justify=tk.LEFT,
            wraplength=980,
        )
        self._last_exec_prompt_label.grid(row=8, column=0, sticky="w", pady=(2, 0))

        box.grid_columnconfigure(0, weight=1)
        self._push_agent_execution_config(command, prompt_template)

    def _on_content_configure(self, status: TaskStatus) -> None:
        canvas = self._column_canvases[status]
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event, status: TaskStatus) -> None:
        canvas = self._column_canvases[status]
        canvas.itemconfigure(self._column_window_ids[status], width=event.width)

    def _set_new_task_color(self, color: str) -> None:
        if color == "cycle" and self._new_task_color != "cycle":
            self._cycle_index = 0
        self._new_task_color = color
        self._sync_color_button_states()

    def _sync_color_button_states(self) -> None:
        for color, control in self._color_buttons.items():
            if color == self._new_task_color:
                if isinstance(control, tk.Button):
                    control.configure(relief=tk.SOLID, bd=2, highlightthickness=0)
                else:
                    control.configure(highlightthickness=2, highlightbackground="#0F172A")
            else:
                if isinstance(control, tk.Button):
                    control.configure(relief=tk.FLAT, bd=1, highlightthickness=0)
                else:
                    control.configure(highlightthickness=1, highlightbackground="#64748B")

    def _color_for_new_task(self) -> str:
        if self._new_task_color == "rng":
            red = random.randint(0, 255)
            green = random.randint(0, 255)
            blue = random.randint(0, 255)
            return f"#{red:02x}{green:02x}{blue:02x}"
        if self._new_task_color == "cycle":
            palette = [color for _name, color in self._NEW_TASK_COLORS]
            color = palette[self._cycle_index % len(palette)]
            self._cycle_index = (self._cycle_index + 1) % len(palette)
            return color
        return self._new_task_color

    def _create_cycle_button(self, parent: tk.Frame) -> tk.Canvas:
        canvas = tk.Canvas(
            parent,
            width=78,
            height=28,
            bd=0,
            highlightthickness=1,
            highlightbackground="#64748B",
            cursor="hand2",
        )
        bands = ["#ef4444", "#f59e0b", "#eab308", "#22c55e", "#06b6d4", "#3b82f6", "#a855f7", "#d946ef"]
        x = 0
        band_width = 78 / len(bands)
        for color in bands:
            canvas.create_rectangle(x, 0, x + band_width, 28, fill=color, outline=color)
            x += band_width
        canvas.create_text(39, 14, text="Cycle", fill="#0B1020", font=("Helvetica", 9, "bold"))
        canvas.bind("<Button-1>", lambda _event: self._set_new_task_color("cycle"))
        return canvas

    def _toggle_agent_state(self) -> None:
        if self._agent_controller is not None:
            self._agent_state = self._agent_controller.cycle_state()
        else:
            current_index = self._AGENT_STATES.index(self._agent_state)
            self._agent_state = self._AGENT_STATES[(current_index + 1) % len(self._AGENT_STATES)]
        self._sync_agent_button()

    def _initial_execution_templates(self) -> tuple[str, str]:
        if self._agent_controller is None:
            command, prompt_template = self.board.agent_execution_config_snapshot()
            if not prompt_template:
                prompt_template = default_prompt_template()
            return command, prompt_template
        return self._agent_controller.execution_config_snapshot()

    def _on_agent_execution_config_change(self, *_args: object) -> None:
        if self._agent_command_var is None or self._agent_prompt_input is None:
            return
        command = self._agent_command_var.get()
        prompt_template = self._agent_prompt_input.get("1.0", "end-1c")
        self._push_agent_execution_config(command, prompt_template)

    def _push_agent_execution_config(self, command: str, prompt_template: str) -> None:
        self.board.set_agent_execution_config(command=command, prompt_template=prompt_template)
        if self._agent_controller is None:
            return
        self._agent_controller.update_execution_config(command=command, prompt_template=prompt_template)

    def _sync_execution_preview(self) -> None:
        if self._last_exec_command_label is None or self._last_exec_prompt_label is None:
            return
        if self._agent_controller is None:
            self._last_exec_command_label.configure(text="-")
            self._last_exec_prompt_label.configure(text="-")
            return

        invocation = self._agent_controller.last_invocation()
        if invocation is None:
            self._last_exec_command_label.configure(text="-")
            self._last_exec_prompt_label.configure(text="-")
            return

        self._last_exec_command_label.configure(text=invocation.command)
        self._last_exec_prompt_label.configure(text=invocation.prompt)

    def _sync_agent_button(self) -> None:
        if self._agent_button is None:
            return

        style = self._AGENT_BUTTON_STYLE[self._agent_state]
        self._agent_button.configure(
            text=style["text"],
            bg=style["bg"],
            fg=style["fg"],
            activebackground=style["bg"],
            activeforeground=style["fg"],
        )

    def add_task(self) -> None:
        title = self.new_task_var.get().strip()
        if not title:
            messagebox.showerror("Invalid task", "Task title cannot be empty")
            return

        task = self.board.create_task(title, color=self._color_for_new_task())
        self.board.move_task(task.id, TaskStatus.TODO, index=0)
        self.new_task_var.set("")
        self._render(force=True)

    def _open_task_edit_dialog(self, task_id: int) -> None:
        try:
            task = self.board.get_task(task_id)
        except KeyError:
            messagebox.showerror("Task missing", "Task no longer exists.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Task")
        dialog.transient(self.root)
        self._set_dialog_modal(dialog)
        dialog.configure(bg="#F8FAFC")
        dialog.resizable(False, False)

        body = tk.Frame(dialog, bg="#F8FAFC", padx=14, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(body, text="Title", bg="#F8FAFC", fg="#0F172A", font=("Helvetica", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        title_var = tk.StringVar(value=task.title)
        title_entry = tk.Entry(
            body,
            textvariable=title_var,
            relief=tk.FLAT,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
            font=("Helvetica", 10),
            width=44,
        )
        title_entry.grid(row=1, column=0, sticky="ew", pady=(4, 10), ipady=4)

        tk.Label(body, text="Color", bg="#F8FAFC", fg="#0F172A", font=("Helvetica", 10, "bold")).grid(
            row=2, column=0, sticky="w"
        )
        color_var = tk.StringVar(value=task.color)
        color_entry = tk.Entry(
            body,
            textvariable=color_var,
            relief=tk.FLAT,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
            font=("Helvetica", 10),
        )
        color_entry.grid(row=3, column=0, sticky="ew", pady=(4, 10), ipady=4)

        tk.Label(body, text="Command", bg="#F8FAFC", fg="#0F172A", font=("Helvetica", 10, "bold")).grid(
            row=4, column=0, sticky="w"
        )
        command_var = tk.StringVar(value=task.command)
        command_entry = tk.Entry(
            body,
            relief=tk.FLAT,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
            font=("Helvetica", 10),
            textvariable=command_var,
        )
        command_entry.grid(row=5, column=0, sticky="ew", pady=(4, 10), ipady=4)

        tk.Label(body, text="Prompt", bg="#F8FAFC", fg="#0F172A", font=("Helvetica", 10, "bold")).grid(
            row=6, column=0, sticky="w"
        )
        prompt_input = tk.Text(
            body,
            height=3,
            relief=tk.FLAT,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
            font=("Helvetica", 10),
            wrap=tk.WORD,
        )
        prompt_input.grid(row=7, column=0, sticky="ew", pady=(4, 10))
        prompt_input.insert("1.0", task.prompt)

        tk.Label(body, text="Output", bg="#F8FAFC", fg="#0F172A", font=("Helvetica", 10, "bold")).grid(
            row=8, column=0, sticky="w"
        )
        output_input = tk.Text(
            body,
            height=6,
            relief=tk.FLAT,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
            font=("Helvetica", 10),
            wrap=tk.WORD,
        )
        output_input.grid(row=9, column=0, sticky="ew", pady=(4, 10))
        output_input.insert("1.0", task.output)

        tk.Label(body, text="Start Time", bg="#F8FAFC", fg="#0F172A", font=("Helvetica", 10, "bold")).grid(
            row=10, column=0, sticky="w"
        )
        start_time_var = tk.StringVar(value=task.start_time)
        start_time_entry = tk.Entry(
            body,
            textvariable=start_time_var,
            relief=tk.FLAT,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
            font=("Helvetica", 10),
        )
        start_time_entry.grid(row=11, column=0, sticky="ew", pady=(4, 10), ipady=4)

        tk.Label(body, text="End Time", bg="#F8FAFC", fg="#0F172A", font=("Helvetica", 10, "bold")).grid(
            row=12, column=0, sticky="w"
        )
        end_time_var = tk.StringVar(value=task.end_time)
        end_time_entry = tk.Entry(
            body,
            textvariable=end_time_var,
            relief=tk.FLAT,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
            font=("Helvetica", 10),
        )
        end_time_entry.grid(row=13, column=0, sticky="ew", pady=(4, 10), ipady=4)

        tk.Label(body, text="Duration", bg="#F8FAFC", fg="#0F172A", font=("Helvetica", 10, "bold")).grid(
            row=14, column=0, sticky="w"
        )
        duration_var = tk.StringVar(value=task.duration)
        duration_entry = tk.Entry(
            body,
            textvariable=duration_var,
            relief=tk.FLAT,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
            font=("Helvetica", 10),
        )
        duration_entry.grid(row=15, column=0, sticky="ew", pady=(4, 10), ipady=4)

        tk.Label(body, text="Tokens Used", bg="#F8FAFC", fg="#0F172A", font=("Helvetica", 10, "bold")).grid(
            row=16, column=0, sticky="w"
        )
        tokens_used_var = tk.StringVar(value=task.tokens_used)
        tokens_used_entry = tk.Entry(
            body,
            textvariable=tokens_used_var,
            relief=tk.FLAT,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
            font=("Helvetica", 10),
        )
        tokens_used_entry.grid(row=17, column=0, sticky="ew", pady=(4, 10), ipady=4)

        tk.Label(body, text="Exit Code", bg="#F8FAFC", fg="#0F172A", font=("Helvetica", 10, "bold")).grid(
            row=18, column=0, sticky="w"
        )
        exit_code_var = tk.StringVar(value=task.exit_code)
        exit_code_entry = tk.Entry(
            body,
            textvariable=exit_code_var,
            relief=tk.FLAT,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
            font=("Helvetica", 10),
        )
        exit_code_entry.grid(row=19, column=0, sticky="ew", pady=(4, 10), ipady=4)

        actions = tk.Frame(body, bg="#F8FAFC")
        actions.grid(row=20, column=0, sticky="e")
        tk.Button(
            actions,
            text="Cancel",
            command=dialog.destroy,
            relief=tk.FLAT,
            bg="#E2E8F0",
            fg="#0F172A",
            activebackground="#CBD5E1",
            activeforeground="#0F172A",
            padx=10,
            pady=5,
            cursor="hand2",
            font=("Helvetica", 9, "bold"),
        ).pack(side=tk.RIGHT)
        tk.Button(
            actions,
            text="Save",
            command=lambda: self._save_task_edits(
                task_id,
                dialog,
                title_var,
                color_var,
                command_var,
                prompt_input,
                output_input,
                start_time_var,
                end_time_var,
                duration_var,
                tokens_used_var,
                exit_code_var,
            ),
            relief=tk.FLAT,
            bg="#2563EB",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            padx=12,
            pady=5,
            cursor="hand2",
            font=("Helvetica", 9, "bold"),
        ).pack(side=tk.RIGHT, padx=(0, 8))

        body.grid_columnconfigure(0, weight=1)
        title_entry.focus_set()
        title_entry.icursor(tk.END)

    def _set_dialog_modal(self, dialog: tk.Misc) -> None:
        # Toplevel may not be viewable immediately on some window managers.
        # Wait for visibility and retry grab once on the next idle cycle.
        dialog.wait_visibility()
        try:
            dialog.grab_set()
        except tk.TclError:
            def _retry_grab() -> None:
                try:
                    dialog.grab_set()
                except tk.TclError:
                    return

            dialog.after_idle(_retry_grab)

    def _save_task_edits(
        self,
        task_id: int,
        dialog: tk.Misc,
        title_var: tk.StringVar,
        color_var: tk.StringVar,
        command_var: tk.StringVar,
        prompt_input: tk.Text,
        output_input: tk.Text,
        start_time_var: tk.StringVar,
        end_time_var: tk.StringVar,
        duration_var: tk.StringVar,
        tokens_used_var: tk.StringVar,
        exit_code_var: tk.StringVar,
    ) -> None:
        title = title_var.get().strip()
        color = color_var.get().strip()
        command = command_var.get().strip()
        prompt = prompt_input.get("1.0", "end-1c").strip()
        output = output_input.get("1.0", "end-1c").strip()
        start_time = start_time_var.get().strip()
        end_time = end_time_var.get().strip()
        duration = duration_var.get().strip()
        tokens_used = tokens_used_var.get().strip()
        exit_code = exit_code_var.get().strip()
        try:
            self.board.update_task(
                task_id,
                title=title,
                color=color,
                command=command,
                prompt=prompt,
                output=output,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                tokens_used=tokens_used,
                exit_code=exit_code,
            )
        except ValueError as exc:
            messagebox.showerror("Invalid task", str(exc))
            return
        except KeyError:
            messagebox.showerror("Task missing", "Task no longer exists.")
            return

        dialog.destroy()
        self._render(force=True)

    def save_board(self) -> None:
        destination = self.board_file
        if destination is None:
            selected = filedialog.asksaveasfilename(
                title="Save Kanban Board",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            )
            if not selected:
                return
            destination = Path(selected)
            self.board_file = destination

        try:
            self.board.save_to_file(destination)
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save board:\n{exc}")
            return
        messagebox.showinfo("Board saved", f"Saved board to:\n{destination}")

    def _on_window_close(self) -> None:
        if self._agent_controller is not None:
            self._agent_controller.shutdown()

        destination = self.board_file or Path(".board.json")
        try:
            self.board.save_to_file(destination)
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save board:\n{exc}")
            return
        self.root.destroy()

    def _delete_task(self, task_id: int) -> None:
        self.board.delete_task(task_id)
        self._render(force=True)

    def _on_task_press(self, event: tk.Event, status: TaskStatus, task_id: int) -> None:
        if task_id not in self._id_maps[status]:
            return

        self._drag_source_status = status
        self._drag_source_index = self._id_maps[status].index(task_id)
        self.root.config(cursor="hand2")

    def _on_global_drag_motion(self, event: tk.Event) -> None:
        if self._drag_source_status is None:
            return

        target_widget = self.root.winfo_containing(event.x_root, event.y_root)
        target_status = self._status_for_widget(target_widget)
        self._set_drop_target(target_status)

    def _on_drag_release(self, event: tk.Event) -> None:
        if self._drag_source_status is None or self._drag_source_index is None:
            self._set_drop_target(None)
            self.root.config(cursor="")
            return

        source_status = self._drag_source_status
        source_index = self._drag_source_index

        self._drag_source_status = None
        self._drag_source_index = None
        self.root.config(cursor="")

        target_widget = self.root.winfo_containing(event.x_root, event.y_root)
        target_status = self._status_for_widget(target_widget)
        self._set_drop_target(None)

        if source_index >= len(self._id_maps[source_status]):
            return

        if target_status is None:
            return

        task_id = self._id_maps[source_status][source_index]
        target_index = self._drop_index_for_status(target_status, event)

        if target_status == source_status and target_index > source_index:
            target_index -= 1

        self.board.move_task(task_id, target_status, index=target_index)
        self._render(force=True)

    def _on_mousewheel(self, event: tk.Event) -> str | None:
        status = self._status_for_widget(event.widget if isinstance(event.widget, tk.Misc) else None)
        if status is None:
            pointer_x, pointer_y = self.root.winfo_pointerxy()
            hovered = self.root.winfo_containing(pointer_x, pointer_y)
            status = self._status_for_widget(hovered)
        if status is None:
            return None

        if hasattr(event, "num") and event.num in (4, 5):
            units = -1 if event.num == 4 else 1
        elif getattr(event, "delta", 0):
            delta = int(event.delta)
            direction = -1 if delta > 0 else 1
            steps = max(1, abs(delta) // 120)
            units = direction * steps
        else:
            units = 0

        if units:
            self._column_canvases[status].yview_scroll(units, "units")
            return "break"
        return None

    def _status_for_widget(self, widget: tk.Misc | None) -> TaskStatus | None:
        current = widget
        while current is not None:
            current_key = str(current)
            if current_key in self._task_widget_status:
                return self._task_widget_status[current_key]

            for status in self._BOARD_STATUSES:
                if current in (
                    self._column_frames.get(status),
                    self._column_canvases.get(status),
                    self._column_content_frames.get(status),
                ):
                    return status
            current = current.master
        return None

    def _drop_index_for_status(self, status: TaskStatus, event: tk.Event) -> int:
        task_ids = self._id_maps[status]
        if not task_ids:
            return 0

        for index, task_id in enumerate(task_ids):
            widget = self._task_widgets.get(task_id)
            if widget is None:
                continue
            midpoint = widget.winfo_rooty() + (widget.winfo_height() / 2)
            if event.y_root < midpoint:
                return index
        return len(task_ids)

    def _set_drop_target(self, status: TaskStatus | None) -> None:
        if status == self._active_drop_status:
            return

        for current_status, frame in self._column_frames.items():
            border_color = self._CARD_BORDER_ACTIVE if current_status == status else self._CARD_BORDER
            frame.configure(highlightbackground=border_color)

        self._active_drop_status = status

    def refresh(self) -> None:
        if self._agent_controller is not None:
            self._agent_state = self._agent_controller.state
            self._sync_agent_button()
        self._sync_execution_preview()
        self._render()
        self._refresh_job = self.root.after(800, self.refresh)

    def _capture_scroll_positions(self) -> dict[TaskStatus, float]:
        positions: dict[TaskStatus, float] = {}
        for status, canvas in self._column_canvases.items():
            start, _end = canvas.yview()
            positions[status] = start
        return positions

    def _restore_scroll_positions(self, positions: dict[TaskStatus, float]) -> None:
        for status, saved in positions.items():
            canvas = self._column_canvases.get(status)
            if canvas is None:
                continue
            clamped = max(0.0, min(1.0, saved))
            canvas.yview_moveto(clamped)

    def _render(self, force: bool = False) -> None:
        tasks = self.board.list_tasks()
        fingerprint = tuple(
            (
                task.id,
                task.status.value,
                task.title,
                task.color,
                task.command,
                task.prompt,
                task.output,
                task.start_time,
                task.end_time,
                task.duration,
                task.tokens_used,
                task.exit_code,
            )
            for task in tasks
        )
        if not force and fingerprint == self._last_board_fingerprint:
            return
        self._last_board_fingerprint = fingerprint

        tasks_by_status: dict[TaskStatus, list[tuple[int, str, str]]] = {status: [] for status in self._BOARD_STATUSES}

        for task in tasks:
            tasks_by_status[task.status].append((task.id, task.title, task.color))

        scroll_positions = self._capture_scroll_positions()
        self._task_widgets = {}
        self._task_widget_status = {}

        for status, content in self._column_content_frames.items():
            for child in content.winfo_children():
                child.destroy()

            self._id_maps[status] = []
            for task_id, title, color in tasks_by_status[status]:
                task_canvas = self._build_task_card(
                    content,
                    title=title,
                    color=color,
                    on_delete=lambda tid=task_id: self._delete_task(tid),
                )
                task_canvas.pack(fill=tk.X, padx=8, pady=6)
                task_canvas.bind("<ButtonPress-1>", lambda event, s=status, tid=task_id: self._on_task_press(event, s, tid))
                self._bind_task_edit_shortcuts(task_canvas, task_id=task_id)

                self._id_maps[status].append(task_id)
                self._task_widgets[task_id] = task_canvas
                self._task_widget_status[str(task_canvas)] = status

            self._count_labels[status].configure(text=str(len(tasks_by_status[status])))
            self._on_content_configure(status)
        self._restore_scroll_positions(scroll_positions)

    def _bind_task_edit_shortcuts(self, task_canvas: tk.Canvas, task_id: int) -> None:
        task_canvas.bind("<Button-3>", lambda event, tid=task_id: self._on_task_edit_request(event, tid))
        task_canvas.bind("<Double-Button-1>", lambda event, tid=task_id: self._on_task_edit_request(event, tid))

    def _bind_todo_flow_shortcuts(self, todo_canvas: tk.Canvas, todo_content: tk.Frame) -> None:
        todo_canvas.bind("<Button-3>", self._on_todo_flow_right_click)
        todo_content.bind("<Button-3>", self._on_todo_flow_right_click)

    def _on_todo_flow_right_click(self, event: tk.Event) -> str:
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Stop Running Here", command=lambda: self._create_stop_task_at_event(event))
        self._todo_context_menu = menu
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _create_stop_task_at_event(self, event: tk.Event) -> None:
        insert_index = self._drop_index_for_status(TaskStatus.TODO, event)
        task = self.board.create_task(STOP_TASK_TITLE, color=self._STOP_TASK_COLOR)
        self.board.move_task(task.id, TaskStatus.TODO, index=insert_index)
        self._render(force=True)

    def _on_task_edit_request(self, event: tk.Event, task_id: int) -> str:
        _ = event
        self._drag_source_status = None
        self._drag_source_index = None
        self._set_drop_target(None)
        self.root.config(cursor="")
        self._open_task_edit_dialog(task_id)
        return "break"

    def _build_task_card(self, parent: tk.Frame, title: str, color: str, on_delete: Callable[[], None] | None = None) -> tk.Canvas:
        card = tk.Canvas(parent, height=58, bg=self._LIST_BG, highlightthickness=0, bd=0)
        hovering = False

        def on_hover_enter(_event: tk.Event) -> None:
            nonlocal hovering
            if hovering:
                return
            hovering = True
            redraw()

        def on_hover_leave(_event: tk.Event) -> None:
            nonlocal hovering
            if not hovering:
                return
            hovering = False
            redraw()

        def on_delete_click(_event: tk.Event) -> str:
            if on_delete is not None:
                on_delete()
            return "break"

        def redraw(event: tk.Event | None = None) -> None:
            width = self._task_card_width(card, event)
            text_width = max(width - 30, 70)
            card_height = self._estimate_task_card_height(title, text_width_px=text_width)
            if int(card.cget("height")) != card_height:
                card.configure(height=card_height)
            height = max(card_height - 2, 48)
            card.delete("all")

            # Shadow
            self._draw_rounded_rect(
                card,
                7,
                8,
                width - 3,
                height - 3,
                radius=12,
                fill="#000000",
                outline="",
                stipple="gray50",
            )
            # Main card
            self._draw_rounded_rect(
                card,
                3,
                3,
                width - 7,
                height - 7,
                radius=12,
                fill=color,
                outline="#000000",
                width_px=2,
            )
            card.create_text(
                18,
                11,
                anchor="nw",
                text=title,
                font=("Helvetica", 11, "bold"),
                fill=self._text_color_for_background(color),
                width=text_width,
                justify=tk.LEFT,
            )
            if hovering:
                delete_x1 = width - 33
                delete_y1 = 7
                delete_x2 = width - 9
                delete_y2 = 31
                self._draw_rounded_rect(
                    card,
                    delete_x1,
                    delete_y1,
                    delete_x2,
                    delete_y2,
                    radius=10,
                    fill="#F8FAFC",
                    outline="#0F172A",
                    width_px=1,
                )
                card.create_rectangle(
                    delete_x1,
                    delete_y1,
                    delete_x2,
                    delete_y2,
                    fill="",
                    outline="",
                    tags=("delete_button",),
                )
                card.create_text(
                    width - 21,
                    19,
                    text="x",
                    fill="#0F172A",
                    font=("Helvetica", 10, "bold"),
                    tags=("delete_button",),
                )
                card.tag_bind("delete_button", "<ButtonPress-1>", on_delete_click)

        card.bind("<Configure>", redraw)
        card.bind("<Enter>", on_hover_enter)
        card.bind("<Leave>", on_hover_leave)
        return card

    def _task_card_width(self, card: tk.Canvas, event: tk.Event | None) -> int:
        if event is not None:
            raw_width = int(event.width)
        else:
            raw_width = int(card.winfo_width())
            if raw_width <= 1:
                raw_width = int(card.cget("width"))
        return max(raw_width - 2, 120)

    def _estimate_task_card_height(self, title: str, text_width_px: int) -> int:
        line_height = 20
        vertical_padding = 28
        min_height = 58
        approx_chars_per_line = max(6, text_width_px // 9)

        line_count = 0
        for raw_line in title.splitlines() or [""]:
            wrapped = textwrap.wrap(raw_line, width=approx_chars_per_line) if raw_line else [""]
            line_count += max(1, len(wrapped))

        estimated = vertical_padding + (line_count * line_height)
        return max(min_height, estimated)

    def _draw_rounded_rect(
        self,
        canvas: tk.Canvas,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int,
        fill: str,
        outline: str,
        width_px: int = 1,
        stipple: str = "",
    ) -> None:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        canvas.create_polygon(
            points,
            smooth=True,
            splinesteps=18,
            fill=fill,
            outline=outline,
            width=width_px,
            stipple=stipple,
        )

    def _text_color_for_background(self, color: str) -> str:
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
        luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
        return "#0B1020" if luminance > 160 else "#F8FAFC"

    def run(self) -> None:
        self.root.mainloop()
