"""Widget gallery for the TeamMARS glass theme. Run: .venv/bin/python teammars/theme_gallery.py [out.png]"""
import sys
import tkinter as tk
from tkinter import ttk

from ardupilot_methodic_configurator.frontend_tkinter_glass_theme import apply_glass_theme

root = tk.Tk(className="TeamMARSPIDTuner")
root.title("TeamMARS-PID-tuner(DRONE) - theme gallery")
style = apply_glass_theme(root)
style.configure("default_v.TEntry", fieldbackground="#CFE8F3", foreground="black")
style.configure("below_limit.TEntry", fieldbackground="orangered", foreground="black")
style.configure("above_limit.TEntry", fieldbackground="red3", foreground="white")
main = ttk.Frame(root, padding=12)
main.pack(fill="both", expand=True)

lf = ttk.LabelFrame(main, text="Rate controller")
lf.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
for i, (n, v, s) in enumerate([("ATC_RAT_RLL_P", "0.135", "TEntry"), ("ATC_RAT_RLL_I", "0.135", "default_v.TEntry"), ("ATC_RAT_RLL_D", "0.0001", "below_limit.TEntry"), ("ATC_RAT_PIT_P", "9.0", "above_limit.TEntry")]):
    ttk.Label(lf, text=n).grid(row=i, column=0, sticky="w", padx=4, pady=3)
    e = ttk.Entry(lf, style=s, width=10); e.insert(0, v); e.grid(row=i, column=1, padx=4, pady=3)
cb = ttk.Combobox(lf, values=["Stabilize", "AltHold", "Loiter"], state="readonly"); cb.current(2); cb.grid(row=4, column=0, columnspan=2, sticky="ew", padx=4, pady=3)
ttk.Spinbox(lf, from_=0, to=10).grid(row=5, column=0, columnspan=2, sticky="ew", padx=4, pady=3)

lf2 = ttk.LabelFrame(main, text="Actions")
lf2.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
ttk.Button(lf2, text="Upload selected params to FC").pack(fill="x", padx=4, pady=3)
b = ttk.Button(lf2, text="Focused button"); b.pack(fill="x", padx=4, pady=3)
ttk.Button(lf2, text="Disabled", state="disabled").pack(fill="x", padx=4, pady=3)
v1 = tk.BooleanVar(value=True); v2 = tk.BooleanVar(value=False)
ttk.Checkbutton(lf2, text="Annotate docs into .param", variable=v1).pack(anchor="w", padx=4)
ttk.Checkbutton(lf2, text="Skip unchanged", variable=v2).pack(anchor="w", padx=4)
rv = tk.StringVar(value="a")
ttk.Radiobutton(lf2, text="Serial", value="a", variable=rv).pack(anchor="w", padx=4)
ttk.Radiobutton(lf2, text="UDP", value="b", variable=rv).pack(anchor="w", padx=4)
pb = ttk.Progressbar(lf2, value=62); pb.pack(fill="x", padx=4, pady=6)
ttk.Scale(lf2, from_=0, to=1, value=0.4).pack(fill="x", padx=4)

nb = ttk.Notebook(main)
nb.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
f = ttk.Frame(nb); nb.add(f, text="Parameters"); nb.add(ttk.Frame(nb), text="Logs"); nb.add(ttk.Frame(nb), text="Hardware")
tv = ttk.Treeview(f, columns=("v", "d"), height=4)
tv.heading("#0", text="Param"); tv.heading("v", text="Value"); tv.heading("d", text="Default")
for r in [("INS_GYRO_FILTER", "40", "20"), ("ATC_ACCEL_R_MAX", "110000", "110000"), ("MOT_THST_HOVER", "0.21", "0.35"), ("LOIT_SPEED_MS", "12.5", "12.5")]:
    tv.insert("", "end", text=r[0], values=r[1:])
tv.selection_set(tv.get_children()[2])
tv.pack(side="left", fill="both", expand=True, padx=4, pady=4)
ttk.Scrollbar(f, orient="vertical", command=tv.yview).pack(side="right", fill="y")
t = tk.Text(main, height=3); t.insert("1.0", "Classic tk.Text: documentation pane"); t.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=6)

root.geometry("760x560+80+80")
root.update()
b.focus_set()
if len(sys.argv) > 1:
    def shot():
        root.update()
        import subprocess
        subprocess.run(["xwd", "-silent", "-id", str(root.winfo_id()), "-out", sys.argv[1] + ".xwd"], check=False, timeout=10)
        root.destroy()
    root.after(1200, shot)
root.mainloop()
