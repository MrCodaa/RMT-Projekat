import os
import socket
import threading
import time
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk
import customtkinter as ctk

import protocol as proto

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, on_connect):
        super().__init__(master, corner_radius=16)
        self.on_connect = on_connect

        ctk.CTkLabel(self, text="Remote Control Center",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(32, 4))
        ctk.CTkLabel(self, text="Povezi se na server",
                     font=ctk.CTkFont(size=13), text_color="gray").pack(pady=(0, 24))

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(padx=40, fill="x")

        ctk.CTkLabel(form, text="Server IP", anchor="w").grid(row=0, column=0, sticky="w", pady=4)
        self.host_entry = ctk.CTkEntry(form, placeholder_text="127.0.0.1")
        self.host_entry.insert(0, "127.0.0.1")
        self.host_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=4)

        ctk.CTkLabel(form, text="Port", anchor="w").grid(row=1, column=0, sticky="w", pady=4)
        self.port_entry = ctk.CTkEntry(form, placeholder_text="9999")
        self.port_entry.insert(0, "9999")
        self.port_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=4)

        ctk.CTkLabel(form, text="Lozinka", anchor="w").grid(row=2, column=0, sticky="w", pady=4)
        self.pwd_entry = ctk.CTkEntry(form, placeholder_text="controller123", show="*")
        self.pwd_entry.insert(0, "controller123")
        self.pwd_entry.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=4)

        form.columnconfigure(1, weight=1)

        self.error_label = ctk.CTkLabel(self, text="", text_color="#e05252",
                                        font=ctk.CTkFont(size=12))
        self.error_label.pack(pady=(12, 0))

        ctk.CTkButton(self, text="Povezi se", command=self.connect,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      height=40).pack(pady=(12, 32), padx=40, fill="x")

        self.pwd_entry.bind("<Return>", lambda e: self.connect())

    def connect(self):
        host = self.host_entry.get().strip() or "127.0.0.1"
        try:
            port = int(self.port_entry.get().strip() or "9999")
        except ValueError:
            self.error_label.configure(text="Port mora biti broj.")
            return
        pwd = self.pwd_entry.get()
        self.error_label.configure(text="Povezivanje...")
        self.on_connect(host, port, pwd, self.show_error)

    def show_error(self, msg):
        self.error_label.configure(text=msg)


class Dashboard(ctk.CTkFrame):
    def __init__(self, master, send_fn, disconnect_fn):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.send_fn = send_fn
        self.disconnect_fn = disconnect_fn
        self.selected_agent = None
        self.agents = {}
        self.processes = []
        self.selected_pid = None
        self.selected_file = None

        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=0)

        # lijevi panel - lista agenata
        left = ctk.CTkFrame(self, width=260, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Online Agenti",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, pady=(12, 4), padx=10, sticky="w")

        self.agent_list_frame = ctk.CTkScrollableFrame(left)
        self.agent_list_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))

        # centralni panel
        center = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", padx=2)
        center.rowconfigure(0, weight=0)
        center.rowconfigure(1, weight=1)
        center.rowconfigure(2, weight=1)
        center.columnconfigure(0, weight=1)

        # metrike
        metrics_panel = ctk.CTkFrame(center, corner_radius=8)
        metrics_panel.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        metrics_panel.columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(metrics_panel, text="Sistemske metrike",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(8, 4))

        cpu_col = ctk.CTkFrame(metrics_panel, fg_color="transparent")
        cpu_col.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")
        ctk.CTkLabel(cpu_col, text="CPU", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.cpu_bar = ctk.CTkProgressBar(cpu_col, width=160)
        self.cpu_bar.set(0)
        self.cpu_bar.pack(fill="x", pady=2)
        self.cpu_label = ctk.CTkLabel(cpu_col, text="0 %", font=ctk.CTkFont(size=11))
        self.cpu_label.pack(anchor="e")

        ram_col = ctk.CTkFrame(metrics_panel, fg_color="transparent")
        ram_col.grid(row=1, column=1, padx=12, pady=(0, 10), sticky="ew")
        ctk.CTkLabel(ram_col, text="RAM", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.ram_bar = ctk.CTkProgressBar(ram_col, width=160)
        self.ram_bar.set(0)
        self.ram_bar.pack(fill="x", pady=2)
        self.ram_label = ctk.CTkLabel(ram_col, text="0 / 0 GB", font=ctk.CTkFont(size=11))
        self.ram_label.pack(anchor="e")

        disk_col = ctk.CTkFrame(metrics_panel, fg_color="transparent")
        disk_col.grid(row=1, column=2, padx=12, pady=(0, 10), sticky="ew")
        ctk.CTkLabel(disk_col, text="Disk", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.disk_bar = ctk.CTkProgressBar(disk_col, width=160)
        self.disk_bar.set(0)
        self.disk_bar.pack(fill="x", pady=2)
        self.disk_label = ctk.CTkLabel(disk_col, text="0 / 0 GB", font=ctk.CTkFont(size=11))
        self.disk_label.pack(anchor="e")

        # terminal panel
        terminal_panel = ctk.CTkFrame(center, corner_radius=8)
        terminal_panel.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        terminal_panel.rowconfigure(1, weight=1)
        terminal_panel.columnconfigure(0, weight=1)

        term_hdr = ctk.CTkFrame(terminal_panel, fg_color="transparent")
        term_hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        ctk.CTkLabel(term_hdr, text="Udaljeni terminal",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        allowed_str = ", ".join(sorted(proto.ALLOWED_COMMANDS))
        ctk.CTkLabel(term_hdr, text=f"Dozvoljeno: {allowed_str}",
                     font=ctk.CTkFont(size=10), text_color="gray").pack(side="left", padx=(10, 0))

        self.term_output = ctk.CTkTextbox(terminal_panel, state="disabled",
                                          font=ctk.CTkFont(family="Courier", size=11))
        self.term_output.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)

        cmd_row = ctk.CTkFrame(terminal_panel, fg_color="transparent")
        cmd_row.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 8))
        cmd_row.columnconfigure(0, weight=1)

        self.cmd_entry = ctk.CTkEntry(cmd_row, placeholder_text="Unesi komandu...")
        self.cmd_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(cmd_row, text="Pokreni", width=70,
                      command=self.run_command).grid(row=0, column=1)
        self.cmd_entry.bind("<Return>", lambda e: self.run_command())

        # panel sa procesima
        process_panel = ctk.CTkFrame(center, corner_radius=8)
        process_panel.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
        process_panel.rowconfigure(1, weight=1)
        process_panel.columnconfigure(0, weight=1)

        proc_hdr = ctk.CTkFrame(process_panel, fg_color="transparent")
        proc_hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 4))
        ctk.CTkLabel(proc_hdr, text="Lista procesa",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(proc_hdr, text="Osvjezi", width=80,
                      command=self.request_process_list).pack(side="left", padx=(10, 0))
        ctk.CTkButton(proc_hdr, text="Ugasi proces", width=100,
                      fg_color="#b03030", hover_color="#8a2020",
                      command=self.kill_process).pack(side="left", padx=(8, 0))

        # stil za treeview
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.Treeview",
                        background="#1a1a2e", foreground="white",
                        rowheight=22, fieldbackground="#1a1a2e",
                        borderwidth=0, font=("Courier", 10))
        style.configure("Dark.Treeview.Heading",
                        background="#2a2a40", foreground="#aaaacc",
                        relief="flat", font=("Helvetica", 10, "bold"))
        style.map("Dark.Treeview",
                  background=[("selected", "#2a3a6e")],
                  foreground=[("selected", "white")])

        tree_frame = ctk.CTkFrame(process_panel, fg_color="transparent")
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.proc_tree = ttk.Treeview(tree_frame,
                                      columns=("pid", "name", "cpu", "memory"),
                                      show="headings",
                                      style="Dark.Treeview",
                                      selectmode="browse")
        self.proc_tree.heading("pid", text="PID", anchor="w")
        self.proc_tree.heading("name", text="Naziv", anchor="w")
        self.proc_tree.heading("cpu", text="CPU %", anchor="w")
        self.proc_tree.heading("memory", text="RAM (MB)", anchor="w")
        self.proc_tree.column("pid", width=60, minwidth=50, anchor="w")
        self.proc_tree.column("name", width=200, minwidth=50, anchor="w")
        self.proc_tree.column("cpu", width=70, minwidth=50, anchor="w")
        self.proc_tree.column("memory", width=90, minwidth=50, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.proc_tree.yview)
        self.proc_tree.configure(yscrollcommand=vsb.set)
        self.proc_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.proc_tree.bind("<<TreeviewSelect>>", self.select_process)

        # desni panel
        right = ctk.CTkFrame(self, width=300, corner_radius=0)
        right.grid(row=0, column=2, sticky="nsew", padx=(2, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=0)
        right.rowconfigure(1, weight=1)

        # panel za slanje fajlova
        file_panel = ctk.CTkFrame(right, corner_radius=8)
        file_panel.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        file_panel.columnconfigure(0, weight=1)

        ctk.CTkLabel(file_panel, text="Posalji fajl",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(8, 4))

        self.file_path_label = ctk.CTkLabel(file_panel, text="Nije odabran fajl",
                                            text_color="gray",
                                            font=ctk.CTkFont(size=11), anchor="w")
        self.file_path_label.grid(row=1, column=0, sticky="ew", padx=12, pady=2)

        btn_row = ctk.CTkFrame(file_panel, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))
        ctk.CTkButton(btn_row, text="Pretrazi", width=90,
                      command=self.browse_file).pack(side="left")
        ctk.CTkButton(btn_row, text="Posalji agentu", width=110,
                      command=self.send_file).pack(side="left", padx=(8, 0))

        self.file_status = ctk.CTkLabel(file_panel, text="", font=ctk.CTkFont(size=11),
                                        text_color="#5ec25e")
        self.file_status.grid(row=3, column=0, sticky="w", padx=12, pady=(0, 8))

        # panel za upozorenja
        alert_panel = ctk.CTkFrame(right, corner_radius=8)
        alert_panel.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        alert_panel.rowconfigure(1, weight=1)
        alert_panel.columnconfigure(0, weight=1)

        ctk.CTkLabel(alert_panel, text="Upozorenja",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(8, 4))

        self.alert_box = ctk.CTkTextbox(alert_panel, state="disabled",
                                        font=ctk.CTkFont(family="Courier", size=11))
        self.alert_box.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        # log aktivnosti na dnu
        bottom = ctk.CTkFrame(self, height=140, corner_radius=0)
        bottom.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(2, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(1, weight=1)

        ctk.CTkLabel(bottom, text="Log aktivnosti",
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(6, 0))

        self.activity_log = ctk.CTkTextbox(bottom, height=100, state="disabled",
                                           font=ctk.CTkFont(family="Courier", size=11))
        self.activity_log.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

    def update_agent_list(self, agents_list):
        self.agents = {}
        for a in agents_list:
            self.agents[a["agent_id"]] = a

        for w in self.agent_list_frame.winfo_children():
            w.destroy()

        for agent in agents_list:
            aid = agent["agent_id"]
            status = agent.get("status", "online")

            if status == "online":
                dot_color = "#4caf50"
            else:
                dot_color = "#e05252"

            label = f"●  {agent.get('hostname', aid)}\n    {agent.get('os', '')}"

            if aid == self.selected_agent:
                bg = "#2a2d3e"
            else:
                bg = "transparent"

            btn = ctk.CTkButton(
                self.agent_list_frame,
                text=label,
                anchor="w",
                fg_color=bg,
                text_color=dot_color if status != "online" else "white",
                hover_color="#2a2d3e",
                command=lambda a=aid: self.select_agent(a),
                font=ctk.CTkFont(size=11),
            )
            btn.pack(fill="x", pady=2, padx=2)

        if self.selected_agent:
            info = self.agents.get(self.selected_agent)
            if info and info.get("status") != "online":
                self.reset_metrics()

    def select_agent(self, agent_id):
        self.selected_agent = agent_id
        self.update_agent_list(list(self.agents.values()))
        self.log_activity(f"Selektovan agent {agent_id}")

    def update_metrics(self, msg):
        if msg.get("sender") != self.selected_agent:
            return

        cpu = msg.get("cpu", 0.0)
        ru = msg.get("ram_used", 0.0)
        rt = msg.get("ram_total", 1.0)
        du = msg.get("disk_used", 0.0)
        dt = msg.get("disk_total", 1.0)

        self.cpu_bar.set(cpu / 100)
        if cpu > 90:
            self.cpu_bar.configure(progress_color="#e05252")
        else:
            self.cpu_bar.configure(progress_color="#1f6aa5")
        self.cpu_label.configure(text=f"{cpu:.1f} %")

        if rt > 0:
            self.ram_bar.set(ru / rt)
        self.ram_label.configure(text=f"{ru:.1f} / {rt:.1f} GB")

        if dt > 0:
            self.disk_bar.set(du / dt)
        self.disk_label.configure(text=f"{du:.1f} / {dt:.1f} GB")

    def reset_metrics(self):
        self.cpu_bar.set(0)
        self.ram_bar.set(0)
        self.disk_bar.set(0)
        self.cpu_label.configure(text="0 %")
        self.ram_label.configure(text="0 / 0 GB")
        self.disk_label.configure(text="0 / 0 GB")

    def run_command(self):
        if not self.selected_agent:
            messagebox.showwarning("Nema agenta", "Prvo selektuj agenta.")
            return
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return
        self.cmd_entry.delete(0, "end")
        self.append_terminal(f"\n$ {cmd}\n")
        self.send_fn({
            "type": proto.MSG_COMMAND,
            "target": self.selected_agent,
            "sender": "controller",
            "command": cmd
        })
        self.log_activity(f"Komanda poslana agentu {self.selected_agent}: {cmd}")

    def handle_command_result(self, msg):
        output = msg.get("output", "")
        exit_code = msg.get("exit_code", 0)
        self.append_terminal(output)
        if exit_code != 0:
            self.append_terminal(f"\n[exit code {exit_code}]\n")

    def append_terminal(self, text):
        self.term_output.configure(state="normal")
        self.term_output.insert("end", text)
        self.term_output.see("end")
        self.term_output.configure(state="disabled")

    def request_process_list(self):
        if not self.selected_agent:
            messagebox.showwarning("Nema agenta", "Prvo selektuj agenta.")
            return
        self.send_fn({
            "type": proto.MSG_PROCESS_LIST_REQUEST,
            "target": self.selected_agent,
            "sender": "controller"
        })
        self.log_activity(f"Zatrazena lista procesa od {self.selected_agent}")

    def handle_process_list(self, msg):
        self.processes = msg.get("processes", [])
        self.selected_pid = None

        for row in self.proc_tree.get_children():
            self.proc_tree.delete(row)

        for proc in self.processes:
            self.proc_tree.insert("", "end", iid=str(proc["pid"]), values=(
                proc["pid"],
                proc["name"],
                f"{proc['cpu']:.1f}",
                f"{proc['memory']:.1f}"
            ))

    def select_process(self, event=None):
        sel = self.proc_tree.selection()
        if sel:
            self.selected_pid = int(sel[0])

    def kill_process(self):
        if not self.selected_agent:
            messagebox.showwarning("Nema agenta", "Prvo selektuj agenta.")
            return
        sel = self.proc_tree.selection()
        if not sel:
            messagebox.showwarning("Nema procesa", "Prvo selektuj proces iz liste.")
            return
        self.selected_pid = int(sel[0])
        ok = messagebox.askyesno("Potvrda", f"Ugasiti PID {self.selected_pid} na {self.selected_agent}?")
        if not ok:
            return
        self.send_fn({
            "type": proto.MSG_KILL_PROCESS,
            "target": self.selected_agent,
            "sender": "controller",
            "pid": self.selected_pid
        })
        self.log_activity(f"Zahtjev za gasenje PID {self.selected_pid} poslan agentu {self.selected_agent}")

    def handle_kill_result(self, msg):
        pid = msg.get("pid")
        success = msg.get("success", False)
        message = msg.get("message", "")
        if success:
            self.log_activity(f"PID {pid} ugasen: {message}")
            messagebox.showinfo("Rezultat", message)
        else:
            self.log_activity(f"PID {pid} GRESKA: {message}")
            messagebox.showerror("Greska", message)

    def browse_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.selected_file = path
            self.file_path_label.configure(text=os.path.basename(path))
            self.file_status.configure(text="")

    def send_file(self):
        if not self.selected_agent:
            messagebox.showwarning("Nema agenta", "Prvo selektuj agenta.")
            return
        if not self.selected_file:
            messagebox.showwarning("Nema fajla", "Prvo odaberi fajl.")
            return
        try:
            b64, size = proto.encode_file(self.selected_file)
        except ValueError as e:
            messagebox.showerror("Fajl prevelik", str(e))
            return
        filename = os.path.basename(self.selected_file)
        self.send_fn({
            "type": proto.MSG_FILE,
            "target": self.selected_agent,
            "sender": "controller",
            "filename": filename,
            "size": size,
            "data": b64
        })
        self.file_status.configure(text=f"Saljem {filename}...")
        self.log_activity(f"Fajl '{filename}' poslan agentu {self.selected_agent} ({size} bajtova)")

    def handle_file_ack(self, msg):
        filename = msg.get("filename", "")
        saved = msg.get("saved_path", "")
        error = msg.get("error", "")
        if error:
            self.file_status.configure(text=f"Greska: {error}", text_color="#e05252")
        else:
            self.file_status.configure(text=f"Sacuvano: {saved}", text_color="#5ec25e")
        self.log_activity(f"Fajl '{filename}' primljen: {saved or 'GRESKA'}")

    def add_alert(self, msg):
        level = msg.get("level", "info")
        sender = msg.get("sender", "?")
        message = msg.get("message", "")

        if level == "warning":
            color = "#f0c040"
        elif level == "error":
            color = "#e05252"
        else:
            color = "#5ec25e"

        ts = time.strftime("%H:%M:%S")
        prefix = f"[{ts}] [{level.upper()}] [{sender}] "
        line = message + "\n"

        self.alert_box.configure(state="normal")
        self.alert_box._textbox.tag_configure(level, foreground=color)
        self.alert_box._textbox.insert("end", prefix, level)
        self.alert_box._textbox.insert("end", line)
        self.alert_box.see("end")
        self.alert_box.configure(state="disabled")
        self.log_activity(f"UPOZORENJE [{level}] {sender}: {message}")

    def add_offline_event(self, agent_id, reason):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] [OFFLINE] [{agent_id}] {reason}\n"
        self.alert_box.configure(state="normal")
        self.alert_box._textbox.tag_configure("offline", foreground="#e05252")
        self.alert_box._textbox.insert("end", line, "offline")
        self.alert_box.see("end")
        self.alert_box.configure(state="disabled")
        self.log_activity(f"Agent {agent_id} offline: {reason}")

    def log_activity(self, text):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {text}\n"
        self.activity_log.configure(state="normal")
        self.activity_log.insert("end", line)
        self.activity_log.see("end")
        self.activity_log.configure(state="disabled")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Remote Control Center")
        self.geometry("1200x780")
        self.minsize(900, 600)

        self.sock = None
        self.sock_lock = threading.Lock()
        self.dashboard = None
        self.recv_buf = b""

        self.show_login()

    # Prijava

    def show_login(self):
        for w in self.winfo_children():
            w.destroy()
        self.login = LoginFrame(self, on_connect=self.do_connect)
        self.login.place(relx=0.5, rely=0.5, anchor="center")

    def do_connect(self, host, port, password, show_error):
        def worker():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((host, port))
                s.settimeout(None)

                proto.send_message(s, {
                    "type": proto.MSG_REGISTER,
                    "role": "controller",
                    "password": password
                })

                buf = b""
                while True:
                    data = s.recv(4096)
                    if not data:
                        self.after(0, show_error, "Server zatvorio konekciju.")
                        return
                    msgs, buf = proto.recv_messages(buf, data)
                    for msg in msgs:
                        if msg.get("type") == "error":
                            self.after(0, show_error, msg.get("message", "Greska pri prijavi"))
                            s.close()
                            return
                        if msg.get("type") == proto.MSG_AGENT_LIST:
                            with self.sock_lock:
                                self.sock = s
                            self.recv_buf = buf
                            self.after(0, self.show_dashboard, msg)
                            self.after(0, self.start_recv_loop)
                            return
            except OSError as e:
                self.after(0, show_error, f"Konekcija neuspjesna: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def show_dashboard(self, initial_msg):
        for w in self.winfo_children():
            w.destroy()
        self.dashboard = Dashboard(self, send_fn=self.send_msg, disconnect_fn=self.disconnect)
        self.dashboard.pack(fill="both", expand=True, padx=4, pady=4)
        self.dashboard.update_agent_list(initial_msg.get("agents", []))

    def start_recv_loop(self):
        t = threading.Thread(target=self.recv_loop, daemon=True)
        t.start()

    def recv_loop(self):
        with self.sock_lock:
            s = self.sock
        if s is None:
            return
        buf = self.recv_buf
        self.recv_buf = b""
        try:
            while True:
                data = s.recv(4096)
                if not data:
                    self.after(0, self.handle_disconnect, "Server zatvorio konekciju")
                    break
                msgs, buf = proto.recv_messages(buf, data)
                for msg in msgs:
                    self.after(0, self.dispatch_message, msg)
        except OSError as e:
            if self.sock is not None:
                self.after(0, self.handle_disconnect, str(e))

    #Postoji prostor za dodatno

    def dispatch_message(self, msg):
        if self.dashboard is None:
            return
        msg_type = msg.get("type", "")

        if msg_type == proto.MSG_AGENT_LIST:
            self.dashboard.update_agent_list(msg.get("agents", []))

        elif msg_type == proto.MSG_AGENT_OFFLINE:
            aid = msg.get("agent_id", "?")
            reason = msg.get("reason", "")
            self.dashboard.add_offline_event(aid, reason)
            agents = list(self.dashboard.agents.values())
            for a in agents:
                if a["agent_id"] == aid:
                    a["status"] = "offline"
            self.dashboard.update_agent_list(agents)

        elif msg_type == proto.MSG_METRICS:
            self.dashboard.update_metrics(msg)

        elif msg_type == proto.MSG_ALERT:
            self.dashboard.add_alert(msg)

        elif msg_type == proto.MSG_COMMAND_RESULT:
            self.dashboard.handle_command_result(msg)

        elif msg_type == proto.MSG_PROCESS_LIST:
            self.dashboard.handle_process_list(msg)

        elif msg_type == proto.MSG_KILL_RESULT:
            self.dashboard.handle_kill_result(msg)

        elif msg_type == proto.MSG_FILE_ACK:
            self.dashboard.handle_file_ack(msg)

    #Treba se vratiti na ovo

    def handle_disconnect(self, reason):
        print(f"[CTRL] Diskonektovan: {reason}")
        with self.sock_lock:
            self.sock = None
        messagebox.showerror("Diskonektovan", f"Izgubljena veza:\n{reason}")
        self.show_login()

    def send_msg(self, msg):
        with self.sock_lock:
            s = self.sock
        if s:
            try:
                proto.send_message(s, msg)
            except OSError as e:
                print(f"[CTRL] Greska pri slanju: {e}")

    def disconnect(self):
        with self.sock_lock:
            s = self.sock
            self.sock = None
        if s:
            try:
                s.close()
            except:
                pass
        self.show_login()


if __name__ == "__main__":
    app = App()
    app.mainloop()
