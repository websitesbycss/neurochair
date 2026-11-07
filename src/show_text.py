"""Full-screen, large-text window for the reading blocks. Closes after N seconds or on Esc.

Usage: python src/show_text.py "<text>" <seconds>
"""
import sys
import tkinter as tk

text = sys.argv[1]
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0

root = tk.Tk()
root.attributes("-topmost", True)
root.attributes("-fullscreen", True)
root.configure(bg="white", cursor="none")
root.bind("<Escape>", lambda e: root.destroy())
tk.Label(root, text=text, font=("Georgia", 34), wraplength=root.winfo_screenwidth() - 220,
         justify="left", bg="white", fg="black").pack(expand=True)
root.after(int(secs * 1000), root.destroy)
root.mainloop()
