import tkinter as tk

class SubtitleWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)  # Remove window borders
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)

        self.label = tk.Label(
            self.root,
            text="Holoyomi ready...",
            font=("Arial", 24),
            fg="white",
            bg="black",
            wraplength=800,
            justify="left"
        )
        self.label.pack(padx=20, pady=10)

        self._offset_x = 0
        self._offset_y = 0

        self.root.bind("<Button-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)

    def start_move(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def do_move(self, event):
        x = event.x_root - self._offset_x
        y = event.y_root - self._offset_y
        self.root.geometry(f"+{x}+{y}")

    def update_text(self, text: str):
        self.label.config(text=text)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    window = SubtitleWindow()
    window.run()