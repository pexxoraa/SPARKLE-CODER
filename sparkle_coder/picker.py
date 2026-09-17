"""Run the native folder picker in its own GUI main thread."""

import json

try:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askdirectory(title="Choose a project folder")
    root.destroy()
    print(json.dumps({"path": path}))
except Exception:
    print(json.dumps({"error": "Folder chooser is unavailable. Paste the absolute folder path instead."}))
