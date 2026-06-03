"""
NexForge UCE — drag-and-drop GUI
Clean, minimal Tkinter interface.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)


DARK_BG     = '#0d0d0d'
PANEL_BG    = '#141414'
BORDER      = '#1e1e1e'
ACCENT      = '#00e5ff'
ACCENT2     = '#7c3aed'
TEXT_PRI    = '#f0f0f0'
TEXT_SEC    = '#666666'
TEXT_MUT    = '#333333'
SUCCESS     = '#00c896'
WARNING     = '#f59e0b'
DANGER      = '#ef4444'
FONT_MONO   = ('Consolas', 9)
FONT_UI     = ('Segoe UI', 9)
FONT_TITLE  = ('Segoe UI', 13, 'bold')
FONT_SMALL  = ('Segoe UI', 8)


def _human_size(n: int) -> str:
    if n < 1024:
        return f'{n} B'
    elif n < 1024 ** 2:
        return f'{n / 1024:.1f} KB'
    elif n < 1024 ** 3:
        return f'{n / 1024**2:.1f} MB'
    else:
        return f'{n / 1024**3:.2f} GB'


def _ratio_color(ratio: float) -> str:
    if ratio >= 100:
        return SUCCESS
    elif ratio >= 10:
        return ACCENT
    elif ratio >= 2:
        return WARNING
    return TEXT_SEC


class UCEApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('NexForge UCE')
        self.geometry('820x600')
        self.minsize(700, 500)
        self.configure(bg=DARK_BG)
        self.resizable(True, True)

        self._initialized = False
        self._busy = False

        self._build_ui()
        self._check_init()

    def _build_ui(self):
        self._build_header()
        self._build_body()
        self._build_statusbar()

    def _build_header(self):
        hdr = tk.Frame(self, bg=PANEL_BG, height=52)
        hdr.pack(fill='x', side='top')
        hdr.pack_propagate(False)

        tk.Label(hdr, text='NexForge  UCE',
                 font=FONT_TITLE, bg=PANEL_BG, fg=TEXT_PRI).pack(side='left', padx=20, pady=14)

        tk.Label(hdr, text='Universal Compression Engine',
                 font=FONT_SMALL, bg=PANEL_BG, fg=TEXT_SEC).pack(side='left', pady=14)

        self._hdm_label = tk.Label(hdr, text='HDM: initialising...',
                                   font=FONT_SMALL, bg=PANEL_BG, fg=TEXT_SEC)
        self._hdm_label.pack(side='right', padx=20, pady=14)

        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill='x', side='top')

    def _build_body(self):
        body = tk.Frame(self, bg=DARK_BG)
        body.pack(fill='both', expand=True)

        left = tk.Frame(body, bg=DARK_BG, width=280)
        left.pack(side='left', fill='y', padx=(16, 8), pady=16)
        left.pack_propagate(False)

        self._build_drop_zone(left)
        self._build_progress_area(left)
        self._build_retrieve_area(left)

        right = tk.Frame(body, bg=DARK_BG)
        right.pack(side='left', fill='both', expand=True, padx=(8, 16), pady=16)

        self._build_file_list(right)

    def _build_drop_zone(self, parent):
        lbl = tk.Label(parent, text='COMPRESS', font=FONT_SMALL,
                       bg=DARK_BG, fg=TEXT_SEC)
        lbl.pack(anchor='w', pady=(0, 4))

        zone = tk.Frame(parent, bg=PANEL_BG, relief='flat',
                        highlightthickness=1, highlightbackground=BORDER)
        zone.pack(fill='x')
        zone.pack_propagate(False)
        zone.config(height=120)

        inner = tk.Label(zone,
                         text='Drop file here\nor',
                         font=FONT_UI, bg=PANEL_BG, fg=TEXT_SEC,
                         justify='center')
        inner.place(relx=0.5, rely=0.38, anchor='center')

        browse_btn = tk.Button(zone, text='Browse file',
                               font=FONT_SMALL, bg=BORDER, fg=ACCENT,
                               relief='flat', padx=8, pady=3, cursor='hand2',
                               activebackground=ACCENT, activeforeground=DARK_BG,
                               command=self._browse_compress)
        browse_btn.place(relx=0.5, rely=0.72, anchor='center')

        zone.bind('<Button-1>', lambda e: self._browse_compress())
        inner.bind('<Button-1>', lambda e: self._browse_compress())

        try:
            zone.drop_target_register('DND_Files')
            zone.dnd_bind('<<Drop>>', self._on_drop)
        except Exception:
            pass

        self._drop_zone = zone
        self._drop_inner = inner

    def _build_progress_area(self, parent):
        self._prog_frame = tk.Frame(parent, bg=DARK_BG)
        self._prog_frame.pack(fill='x', pady=(12, 0))

        self._prog_label = tk.Label(self._prog_frame, text='',
                                    font=FONT_SMALL, bg=DARK_BG, fg=TEXT_SEC,
                                    wraplength=260, justify='left')
        self._prog_label.pack(anchor='w')

        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('UCE.Horizontal.TProgressbar',
                        troughcolor=PANEL_BG, background=ACCENT,
                        bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT)

        self._progress = ttk.Progressbar(self._prog_frame, style='UCE.Horizontal.TProgressbar',
                                         length=260, mode='determinate')
        self._progress.pack(fill='x', pady=(4, 0))

        self._result_label = tk.Label(self._prog_frame, text='',
                                      font=FONT_SMALL, bg=DARK_BG, fg=SUCCESS,
                                      wraplength=260, justify='left')
        self._result_label.pack(anchor='w', pady=(4, 0))

    def _build_retrieve_area(self, parent):
        sep = tk.Frame(parent, bg=BORDER, height=1)
        sep.pack(fill='x', pady=14)

        lbl = tk.Label(parent, text='RETRIEVE', font=FONT_SMALL,
                       bg=DARK_BG, fg=TEXT_SEC)
        lbl.pack(anchor='w', pady=(0, 4))

        tk.Label(parent, text='Select a file from the list\nand click Retrieve.',
                 font=FONT_SMALL, bg=DARK_BG, fg=TEXT_MUT,
                 justify='left').pack(anchor='w')

        self._retrieve_btn = tk.Button(parent, text='Retrieve Selected File',
                                       font=FONT_SMALL, bg=PANEL_BG, fg=ACCENT,
                                       relief='flat', padx=10, pady=5, cursor='hand2',
                                       activebackground=ACCENT, activeforeground=DARK_BG,
                                       command=self._retrieve_selected,
                                       state='disabled')
        self._retrieve_btn.pack(fill='x', pady=(8, 0))

        self._delete_btn = tk.Button(parent, text='Delete from HDM',
                                     font=FONT_SMALL, bg=PANEL_BG, fg=DANGER,
                                     relief='flat', padx=10, pady=5, cursor='hand2',
                                     activebackground=DANGER, activeforeground=DARK_BG,
                                     command=self._delete_selected,
                                     state='disabled')
        self._delete_btn.pack(fill='x', pady=(6, 0))

    def _build_file_list(self, parent):
        lbl = tk.Label(parent, text='STORED FILES', font=FONT_SMALL,
                       bg=DARK_BG, fg=TEXT_SEC)
        lbl.pack(anchor='w', pady=(0, 6))

        cols = ('name', 'type', 'extractor', 'original', 'seed', 'ratio', 'date')
        col_conf = {
            'name':      ('File', 180, 'w'),
            'type':      ('Type', 60, 'center'),
            'extractor': ('Method', 100, 'center'),
            'original':  ('Original', 70, 'e'),
            'seed':      ('Seed', 70, 'e'),
            'ratio':     ('Ratio', 55, 'e'),
            'date':      ('Stored', 130, 'center'),
        }

        style = ttk.Style(self)
        style.configure('UCE.Treeview',
                        background=PANEL_BG, foreground=TEXT_PRI,
                        fieldbackground=PANEL_BG, borderwidth=0,
                        rowheight=22, font=FONT_SMALL)
        style.configure('UCE.Treeview.Heading',
                        background=BORDER, foreground=TEXT_SEC,
                        font=FONT_SMALL, relief='flat')
        style.map('UCE.Treeview',
                  background=[('selected', ACCENT2)],
                  foreground=[('selected', TEXT_PRI)])

        frame = tk.Frame(parent, bg=DARK_BG)
        frame.pack(fill='both', expand=True)

        scrollbar = tk.Scrollbar(frame, orient='vertical', bg=PANEL_BG,
                                 troughcolor=DARK_BG, width=8)
        scrollbar.pack(side='right', fill='y')

        self._tree = ttk.Treeview(frame, columns=cols, show='headings',
                                  style='UCE.Treeview',
                                  yscrollcommand=scrollbar.set)
        scrollbar.config(command=self._tree.yview)
        self._tree.pack(fill='both', expand=True)

        for col, (head, width, anchor) in col_conf.items():
            self._tree.heading(col, text=head)
            self._tree.column(col, width=width, anchor=anchor, stretch=col == 'name')

        self._tree.bind('<<TreeviewSelect>>', self._on_select)

        self._refresh_btn = tk.Button(parent, text='Refresh List',
                                      font=FONT_SMALL, bg=PANEL_BG, fg=TEXT_SEC,
                                      relief='flat', padx=8, pady=3, cursor='hand2',
                                      command=self._refresh_list)
        self._refresh_btn.pack(anchor='e', pady=(6, 0))

    def _build_statusbar(self):
        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill='x', side='bottom')

        bar = tk.Frame(self, bg=PANEL_BG, height=24)
        bar.pack(fill='x', side='bottom')
        bar.pack_propagate(False)

        self._status_var = tk.StringVar(value='Initialising engine...')
        tk.Label(bar, textvariable=self._status_var,
                 font=FONT_SMALL, bg=PANEL_BG, fg=TEXT_SEC,
                 anchor='w').pack(side='left', padx=12)

    def _check_init(self):
        from engine.installer import is_initialized, initialize

        if is_initialized(BASE_DIR):
            self._initialized = True
            self._status_var.set('Engine ready.')
            self._hdm_label.config(text='HDM: ready', fg=SUCCESS)
            self._refresh_list()
        else:
            self._status_var.set('First-time setup — initialising engine...')
            self._run_in_thread(
                lambda: initialize(BASE_DIR, progress_cb=self._setup_progress),
                on_done=self._on_init_done
            )

    def _setup_progress(self, frac: float, msg: str):
        self.after(0, lambda: self._status_var.set(msg))
        self.after(0, lambda: self._progress.config(value=frac * 100))

    def _on_init_done(self, error=None):
        if error:
            self._status_var.set(f'Init failed: {error}')
            messagebox.showerror('Init Error', str(error))
        else:
            self._initialized = True
            self._status_var.set('Engine ready.')
            self._hdm_label.config(text='HDM: ready', fg=SUCCESS)
            self._progress.config(value=0)
            self._refresh_list()

    def _on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        if paths:
            self._compress(paths[0])

    def _browse_compress(self):
        path = filedialog.askopenfilename(title='Select file to compress')
        if path:
            self._compress(path)

    def _compress(self, file_path: str):
        if not self._initialized:
            messagebox.showwarning('Not Ready', 'Engine is still initialising.')
            return
        if self._busy:
            return
        if not os.path.isfile(file_path):
            messagebox.showerror('Error', f'Not a file:\n{file_path}')
            return

        self._busy = True
        self._result_label.config(text='')
        self._drop_inner.config(text=f'Compressing...\n{os.path.basename(file_path)}',
                                fg=ACCENT)
        self._status_var.set(f'Compressing {os.path.basename(file_path)}...')

        def _do():
            from engine.compressor import compress_file
            return compress_file(file_path, BASE_DIR, progress_cb=self._compress_progress)

        self._run_in_thread(_do, on_done=self._on_compress_done)

    def _compress_progress(self, frac: float, msg: str):
        self.after(0, lambda: self._progress.config(value=frac * 100))
        self.after(0, lambda: self._prog_label.config(text=msg))
        self.after(0, lambda: self._status_var.set(msg))

    def _on_compress_done(self, result=None, error=None):
        self._busy = False
        self._drop_inner.config(text='Drop file here\nor', fg=TEXT_SEC)
        self._progress.config(value=0)
        self._prog_label.config(text='')

        if error:
            self._result_label.config(text=f'Error: {error}', fg=DANGER)
            self._status_var.set(f'Error: {error}')
            messagebox.showerror('Compression Error', str(error))
            return

        ratio = result.get('ratio', 0)
        orig = _human_size(result.get('original_size', 0))
        seed = _human_size(result.get('seed_size', 0))
        ext = result.get('extractor', '?')

        msg = (f'{orig} → {seed}  ({ratio:.1f}:1)\n'
               f'Method: {ext}')
        self._result_label.config(text=msg, fg=_ratio_color(ratio))
        self._status_var.set(f'Compressed {ratio:.1f}:1 via {ext}')
        self._refresh_list()

    def _refresh_list(self):
        for item in self._tree.get_children():
            self._tree.delete(item)

        try:
            from engine.compressor import list_stored_files
            files = list_stored_files(BASE_DIR)
        except Exception:
            return

        total_orig = 0
        total_seed = 0

        for rec in files:
            name = os.path.basename(rec['path'])
            orig = rec.get('original_size', 0)
            seed = rec.get('seed_size', 0)
            ratio = round(orig / seed, 1) if seed > 0 else 0
            total_orig += orig
            total_seed += seed

            self._tree.insert('', 'end', iid=rec['path'], values=(
                name,
                rec.get('extractor', '?').split('_')[0],
                rec.get('extractor', '?'),
                _human_size(orig),
                _human_size(seed),
                f'{ratio}:1',
                rec.get('compressed_at', '')[:16],
            ))

        total_ratio = round(total_orig / total_seed, 1) if total_seed > 0 else 0
        n = len(files)
        self._hdm_label.config(
            text=f'HDM: {n} file{"s" if n != 1 else ""}  |  '
                 f'{_human_size(total_orig)} → {_human_size(total_seed)}  '
                 f'({total_ratio}:1)',
            fg=ACCENT if n > 0 else TEXT_SEC
        )

    def _on_select(self, event):
        sel = self._tree.selection()
        state = 'normal' if sel else 'disabled'
        self._retrieve_btn.config(state=state)
        self._delete_btn.config(state=state)

    def _retrieve_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        file_path = sel[0]
        name = os.path.basename(file_path)
        ext = os.path.splitext(name)[1]

        out_path = filedialog.asksaveasfilename(
            title='Save retrieved file as',
            initialfile=name,
            defaultextension=ext,
        )
        if not out_path:
            return

        self._busy = True
        self._status_var.set(f'Retrieving {name}...')
        self._retrieve_btn.config(state='disabled')

        def _do():
            from engine.compressor import decompress_file
            ok = decompress_file(file_path, out_path, BASE_DIR,
                                 progress_cb=self._compress_progress)
            return ok

        def _done(result=None, error=None):
            self._busy = False
            self._progress.config(value=0)
            self._prog_label.config(text='')
            self._retrieve_btn.config(state='normal')
            if error:
                self._status_var.set(f'Retrieve error: {error}')
                messagebox.showerror('Retrieve Error', str(error))
            elif result:
                self._status_var.set(f'Retrieved: {out_path}')
                messagebox.showinfo('Success', f'File retrieved to:\n{out_path}')
            else:
                self._status_var.set('Retrieve failed — record not found.')

        self._run_in_thread(_do, on_done=_done)

    def _delete_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        file_path = sel[0]
        name = os.path.basename(file_path)
        if not messagebox.askyesno('Confirm Delete',
                                   f'Remove "{name}" from HDM?\n'
                                   f'(This cannot be undone.)'):
            return

        from engine.compressor import delete_stored_file
        ok = delete_stored_file(file_path, BASE_DIR)
        if ok:
            self._status_var.set(f'Deleted {name} from HDM.')
        self._refresh_list()

    def _run_in_thread(self, fn, on_done=None):
        def _worker():
            try:
                result = fn()
                if on_done:
                    self.after(0, lambda: on_done(result=result))
            except Exception as e:
                if on_done:
                    self.after(0, lambda err=e: on_done(error=err))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()


def launch():
    try:
        from tkinterdnd2 import TkinterDnD
        app = TkinterDnD.Tk()
        app.__class__ = UCEApp
        UCEApp.__init__(app)
    except ImportError:
        app = UCEApp()
    app.mainloop()
