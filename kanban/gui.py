from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from kanban.model import KanbanBoard, TaskStatus


class KanbanGUI:
    _STATUS_TITLE = {
        TaskStatus.TODO: "To Do",
        TaskStatus.IN_PROGRESS: "In Progress",
        TaskStatus.DONE: "Done",
    }

    _STATUS_COLORS = {
        TaskStatus.TODO: "#1D4ED8",
        TaskStatus.IN_PROGRESS: "#B45309",
        TaskStatus.DONE: "#047857",
    }

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
    _AGENT_STATES = ("stopped", "running", "finishing")
    _AGENT_BUTTON_STYLE = {
        "stopped": {"text": "STOPPED", "bg": "#DC2626", "fg": "#FFFFFF"},
        "running": {"text": "RUNNING", "bg": "#16A34A", "fg": "#FFFFFF"},
        "finishing": {"text": "FINISHING", "bg": "#EAB308", "fg": "#0F172A"},
    }

    def __init__(self, board: KanbanBoard, board_file: str | Path | None = None) -> None:
        self.board = board
        self.board_file = Path(board_file) if board_file else None
        self.root = tk.Tk()
        self.root.title("Kanban Board")
        self.root.geometry("1040x660")
        self.root.configure(bg=self._CANVAS_BG)

        self._column_frames: dict[TaskStatus, tk.Frame] = {}
        self._count_labels: dict[TaskStatus, tk.Label] = {}
        self._column_canvases: dict[TaskStatus, tk.Canvas] = {}
        self._column_content_frames: dict[TaskStatus, tk.Frame] = {}
        self._column_window_ids: dict[TaskStatus, int] = {}
        self._id_maps: dict[TaskStatus, list[int]] = {
            TaskStatus.TODO: [],
            TaskStatus.IN_PROGRESS: [],
            TaskStatus.DONE: [],
        }

        self._task_widgets: dict[int, tk.Canvas] = {}
        self._task_widget_status: dict[str, TaskStatus] = {}

        self._color_buttons: dict[str, tk.Widget] = {}
        self._new_task_color = "rng"
        self._cycle_index = 0

        self._drag_source_status: TaskStatus | None = None
        self._drag_source_index: int | None = None
        self._active_drop_status: TaskStatus | None = None
        self._refresh_job: str | None = None
        self._agent_state = "stopped"
        self._agent_button: tk.Button | None = None

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

        for i, status in enumerate((TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.DONE)):
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
        current_index = self._AGENT_STATES.index(self._agent_state)
        self._agent_state = self._AGENT_STATES[(current_index + 1) % len(self._AGENT_STATES)]
        self._sync_agent_button()

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

        self.board.create_task(title, color=self._color_for_new_task())
        self.new_task_var.set("")
        self._render()

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
        destination = self.board_file or Path(".board.json")
        try:
            self.board.save_to_file(destination)
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save board:\n{exc}")
            return
        self.root.destroy()

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
        self._render()

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

            for status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.DONE):
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
        self._render()
        self._refresh_job = self.root.after(800, self.refresh)

    def _render(self) -> None:
        tasks_by_status: dict[TaskStatus, list[tuple[int, str, str]]] = {
            TaskStatus.TODO: [],
            TaskStatus.IN_PROGRESS: [],
            TaskStatus.DONE: [],
        }

        for task in self.board.list_tasks():
            tasks_by_status[task.status].append((task.id, task.title, task.color))

        self._task_widgets = {}
        self._task_widget_status = {}

        for status, content in self._column_content_frames.items():
            for child in content.winfo_children():
                child.destroy()

            self._id_maps[status] = []
            for task_id, title, color in tasks_by_status[status]:
                task_canvas = self._build_task_card(content, title=title, color=color)
                task_canvas.pack(fill=tk.X, padx=8, pady=6)
                task_canvas.bind("<ButtonPress-1>", lambda event, s=status, tid=task_id: self._on_task_press(event, s, tid))

                self._id_maps[status].append(task_id)
                self._task_widgets[task_id] = task_canvas
                self._task_widget_status[str(task_canvas)] = status

            self._count_labels[status].configure(text=str(len(tasks_by_status[status])))
            self._on_content_configure(status)

    def _build_task_card(self, parent: tk.Frame, title: str, color: str) -> tk.Canvas:
        card = tk.Canvas(parent, height=58, bg=self._LIST_BG, highlightthickness=0, bd=0)

        def redraw(event: tk.Event) -> None:
            width = max(event.width - 2, 120)
            height = max(event.height - 2, 48)
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
                height / 2,
                anchor="w",
                text=title,
                font=("Helvetica", 11, "bold"),
                fill=self._text_color_for_background(color),
            )

        card.bind("<Configure>", redraw)
        return card

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
