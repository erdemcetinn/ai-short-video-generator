import tkinter as tk
import sys

placeholder = "Example: 'the part where I explain the pricing'\nLeave blank and AI will pick the most viral segment."
result = {"text": ""}

root = tk.Tk()
root.title("AI Shorts Generator")
root.resizable(False, False)
root.configure(bg="#1e1e2e")

w, h = 560, 340
x = (root.winfo_screenwidth() - w) // 2
y = (root.winfo_screenheight() - h) // 2
root.geometry(f"{w}x{h}+{x}+{y}")
root.lift()
root.attributes("-topmost", True)
root.focus_force()

tk.Label(root, text="🎬  AI Shorts Generator",
         bg="#1e1e2e", fg="#cdd6f4",
         font=("Helvetica Neue", 15, "bold")).pack(pady=(22, 4))

tk.Label(root, text="Which part of the video should we turn into a short?",
         bg="#1e1e2e", fg="#a6adc8",
         font=("Helvetica Neue", 11)).pack(pady=(0, 14))

text_frame = tk.Frame(root, bg="#313244")
text_frame.pack(padx=30, fill="x")

txt = tk.Text(text_frame, height=5, font=("Helvetica Neue", 12),
              bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
              relief="flat", padx=10, pady=8, wrap="word",
              highlightthickness=1, highlightbackground="#45475a")
txt.pack(fill="x")
txt.insert("1.0", placeholder)
txt.config(fg="#585b70")

def on_focus_in(e):
    if txt.get("1.0", "end-1c") == placeholder:
        txt.delete("1.0", "end")
        txt.config(fg="#cdd6f4")

def on_focus_out(e):
    if not txt.get("1.0", "end-1c").strip():
        txt.insert("1.0", placeholder)
        txt.config(fg="#585b70")

txt.bind("<FocusIn>", on_focus_in)
txt.bind("<FocusOut>", on_focus_out)

def submit(e=None):
    val = txt.get("1.0", "end-1c").strip()
    result["text"] = val if val and val != placeholder else ""
    root.quit()

def cancel(e=None):
    result["text"] = ""
    root.quit()
    sys.exit(0)

btn_frame = tk.Frame(root, bg="#1e1e2e")
btn_frame.pack(pady=16)

def make_btn(parent, text, cmd, bg, fg):
    f = tk.Frame(parent, bg=bg, cursor="hand2")
    lbl = tk.Label(f, text=text, bg=bg, fg=fg,
                   font=("Helvetica Neue", 11, "bold"), padx=20, pady=8)
    lbl.pack()
    f.bind("<Button-1>", lambda e: cmd())
    lbl.bind("<Button-1>", lambda e: cmd())
    return f

make_btn(btn_frame, "Cancel", cancel, "#45475a", "#cdd6f4").pack(side="left", padx=6)
make_btn(btn_frame, "Continue", submit, "#89b4fa", "#1e1e2e").pack(side="left", padx=6)

root.bind("<Escape>", cancel)
root.bind("<Return>", lambda e: submit() if not (e.state & 0x1) else None)
root.protocol("WM_DELETE_WINDOW", cancel)
txt.focus_set()

root.mainloop()
root.destroy()

print(result["text"])
