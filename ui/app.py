"""
NexForge UCE — drag-and-drop GUI
Complete interface with folder compression, search, and help.
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
        self.geometry('900x640')
        self.minsize(720, 520)
        self.configure(bg=DARK_BG)
        self.resizable(True, True)

        self._initialized = False
        self._busy = False
        self._last_compressed_path = None

        self._build_menu()
        self._build_ui()
        self._check_init()

    def _build_menu(self):
        menubar = tk.Menu(self, bg=PANEL_BG, fg=TEXT_PRI,
                          activebackground=ACCENT2, activeforeground=TEXT_PRI,
                          relief='flat', bd=0)

        file_menu = tk.Menu(menubar, tearoff=0, bg=PANEL_BG, fg=TEXT_PRI,
                            activebackground=ACCENT2, activeforeground=TEXT_PRI)
        file_menu.add_command(label='Compress File…',    command=self._browse_compress)
        file_menu.add_command(label='Compress Folder…',  command=self._browse_folder)
        file_menu.add_separator()
        file_menu.add_command(label='Retrieve Selected', command=self._retrieve_selected)
        file_menu.add_separator()
        file_menu.add_command(label='Exit',              command=self.destroy)
        menubar.add_cascade(label='File', menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0, bg=PANEL_BG, fg=TEXT_PRI,
                            activebackground=ACCENT2, activeforeground=TEXT_PRI)
        help_menu.add_command(label='How to Build .exe', command=self._show_build_help)
        help_menu.add_command(label='About NexForge UCE', command=self._show_about)
        menubar.add_cascade(label='Help', menu=help_menu)

        self.config(menu=menubar)

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

        self._hdm_label = tk.Label(hdr, text='HDM: initialising…',
                                   font=FONT_SMALL, bg=PANEL_BG, fg=TEXT_SEC)
        self._hdm_label.pack(side='right', padx=20, pady=14)

        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill='x', side='top')

    def _build_body(self):
        body = tk.Frame(self, bg=DARK_BG)
        body.pack(fill='both', expand=True)

        left = tk.Frame(body, bg=DARK_BG, width=290)
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
        zone.config(height=130)

        inner = tk.Label(zone,
                         text='Drop file or folder here',
                         font=FONT_UI, bg=PANEL_BG, fg=TEXT_SEC,
                         justify='center')
        inner.place(relx=0.5, rely=0.30, anchor='center')

        btn_frame = tk.Frame(zone, bg=PANEL_BG)
        btn_frame.place(relx=0.5, rely=0.65, anchor='center')

        browse_btn = tk.Button(btn_frame, text='Browse File',
                               font=FONT_SMALL, bg=BORDER, fg=ACCENT,
                               relief='flat', padx=8, pady=3, cursor='hand2',
                               activebackground=ACCENT, activeforeground=DARK_BG,
                               command=self._browse_compress)
        browse_btn.pack(side='left', padx=(0, 6))

        folder_btn = tk.Button(btn_frame, text='Browse Folder',
                               font=FONT_SMALL, bg=BORDER, fg=ACCENT2,
                               relief='flat', padx=8, pady=3, cursor='hand2',
                               activebackground=ACCENT2, activeforeground=TEXT_PRI,
                               command=self._browse_folder)
        folder_btn.pack(side='left')

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
                                    wraplength=270, justify='left')
        self._prog_label.pack(anchor='w')

        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('UCE.Horizontal.TProgressbar',
                        troughcolor=PANEL_BG, background=ACCENT,
                        bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT)

        self._progress = ttk.Progressbar(self._prog_frame,
                                         style='UCE.Horizontal.TProgressbar',
                                         length=270, mode='determinate')
        self._progress.pack(fill='x', pady=(4, 0))

        self._result_label = tk.Label(self._prog_frame, text='',
                                      font=FONT_SMALL, bg=DARK_BG, fg=SUCCESS,
                                      wraplength=270, justify='left')
        self._result_label.pack(anchor='w', pady=(4, 0))

        self._del_orig_btn = tk.Button(
            self._prog_frame,
            text='Delete Original File',
            font=FONT_SMALL, bg=PANEL_BG, fg=DANGER,
            relief='flat', padx=8, pady=3, cursor='hand2',
            activebackground=DANGER, activeforeground=DARK_BG,
            command=self._delete_original,
        )

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
        lbl.pack(anchor='w', pady=(0, 4))

        search_frame = tk.Frame(parent, bg=DARK_BG)
        search_frame.pack(fill='x', pady=(0, 6))

        tk.Label(search_frame, text='Search:', font=FONT_SMALL,
                 bg=DARK_BG, fg=TEXT_SEC).pack(side='left')

        self._search_var = tk.StringVar()
        self._search_var.trace_add('write', self._on_search_change)

        search_entry = tk.Entry(search_frame, textvariable=self._search_var,
                                bg=PANEL_BG, fg=TEXT_PRI, insertbackground=ACCENT,
                                relief='flat', font=FONT_SMALL,
                                highlightthickness=1,
                                highlightbackground=BORDER,
                                highlightcolor=ACCENT)
        search_entry.pack(side='left', fill='x', expand=True, padx=(6, 0), ipady=3)

        cols = ('name', 'type', 'extractor', 'original', 'seed', 'ratio', 'date')
        col_conf = {
            'name':      ('File', 180, 'w'),
            'type':      ('Type', 60, 'center'),
            'extractor': ('Method', 100, 'center'),
            'original':  ('Original', 72, 'e'),
            'seed':      ('Seed', 72, 'e'),
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
            self._tree.column(col, width=width, anchor=anchor,
                              stretch=col == 'name')

        self._tree.bind('<<TreeviewSelect>>', self._on_select)

        self._refresh_btn = tk.Button(parent, text='Refresh List',
                                      font=FONT_SMALL, bg=PANEL_BG, fg=TEXT_SEC,
                                      relief='flat', padx=8, pady=3, cursor='hand2',
                                      command=self._refresh_list)
        self._refresh_btn.pack(anchor='e', pady=(6, 0))

        self._all_records = []

    def _build_statusbar(self):
        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill='x', side='bottom')

        bar = tk.Frame(self, bg=PANEL_BG, height=24)
        bar.pack(fill='x', side='bottom')
        bar.pack_propagate(False)

        self._status_var = tk.StringVar(value='Initialising engine…')
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
            self._status_var.set('First-time setup — initialising engine…')
            self._run_in_thread(
                lambda: initialize(BASE_DIR, progress_cb=self._setup_progress),
                on_done=self._on_init_done
            )

    def _setup_progress(self, frac: float, msg: str):
        self.after(0, lambda: self._status_var.set(msg))
        self.after(0, lambda: self._progress.config(value=frac * 100))

    def _on_init_done(self, result=None, error=None):
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
        if not paths:
            return
        path = paths[0]
        if os.path.isdir(path):
            self._compress_folder(path)
        else:
            self._compress(path)

    def _browse_compress(self):
        path = filedialog.askopenfilename(title='Select file to compress')
        if path:
            self._compress(path)

    def _browse_folder(self):
        path = filedialog.askdirectory(title='Select folder to compress')
        if path:
            self._compress_folder(path)

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
        self._last_compressed_path = None
        self._del_orig_btn.pack_forget()
        self._result_label.config(text='')
        self._drop_inner.config(
            text=f'Compressing…\n{os.path.basename(file_path)}', fg=ACCENT)
        self._status_var.set(f'Compressing {os.path.basename(file_path)}…')

        def _do():
            from engine.compressor import compress_file
            return compress_file(file_path, BASE_DIR,
                                 progress_cb=self._compress_progress)

        self._run_in_thread(_do, on_done=lambda result=None, error=None:
                            self._on_compress_done(result, error, file_path))

    def _compress_folder(self, folder_path: str):
        if not self._initialized:
            messagebox.showwarning('Not Ready', 'Engine is still initialising.')
            return
        if self._busy:
            return

        self._busy = True
        self._last_compressed_path = None
        self._del_orig_btn.pack_forget()
        self._result_label.config(text='')
        name = os.path.basename(folder_path)
        self._drop_inner.config(text=f'Compressing folder…\n{name}', fg=ACCENT2)
        self._status_var.set(f'Compressing folder: {name}…')

        def _do():
            from engine.compressor import compress_folder
            return compress_folder(folder_path, BASE_DIR,
                                   progress_cb=self._compress_progress)

        self._run_in_thread(_do, on_done=lambda result=None, error=None:
                            self._on_folder_done(result, error, folder_path))

    def _compress_progress(self, frac: float, msg: str):
        self.after(0, lambda: self._progress.config(value=frac * 100))
        self.after(0, lambda: self._prog_label.config(text=msg))
        self.after(0, lambda: self._status_var.set(msg))

    def _on_compress_done(self, result=None, error=None, file_path=None):
        self._busy = False
        self._drop_inner.config(text='Drop file or folder here', fg=TEXT_SEC)
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

        if file_path and os.path.isfile(file_path):
            self._last_compressed_path = file_path
            self._del_orig_btn.pack(fill='x', pady=(6, 0))

        self._refresh_list()

    def _on_folder_done(self, result=None, error=None, folder_path=None):
        self._busy = False
        name = os.path.basename(folder_path) if folder_path else ''
        self._drop_inner.config(text='Drop file or folder here', fg=TEXT_SEC)
        self._progress.config(value=0)
        self._prog_label.config(text='')

        if error:
            self._result_label.config(text=f'Error: {error}', fg=DANGER)
            self._status_var.set(f'Folder error: {error}')
            messagebox.showerror('Compression Error', str(error))
            return

        n = result.get('files', 0)
        errs = result.get('errors', 0)
        orig = _human_size(result.get('original_size', 0))
        seed = _human_size(result.get('seed_size', 0))
        ratio = result.get('ratio', 0)

        msg = (f'{n} files: {orig} → {seed}  ({ratio:.1f}:1)')
        if errs:
            msg += f'\n{errs} file(s) failed'
        self._result_label.config(text=msg, fg=_ratio_color(ratio))
        self._status_var.set(
            f'Folder done — {n} files at {ratio:.1f}:1' +
            (f' ({errs} errors)' if errs else ''))

        if errs and result.get('error_list'):
            err_details = '\n'.join(
                f'{os.path.basename(p)}: {e}'
                for p, e in result['error_list'][:10]
            )
            messagebox.showwarning('Some files failed',
                                   f'{errs} file(s) could not be compressed:\n\n'
                                   f'{err_details}')

        self._refresh_list()

    def _delete_original(self):
        if not self._last_compressed_path:
            return
        path = self._last_compressed_path
        name = os.path.basename(path)
        if not messagebox.askyesno(
                'Delete Original?',
                f'Remove the original file from disk?\n\n'
                f'"{name}"\n\n'
                f'The compressed seed is safely stored in the HDM.\n'
                f'This cannot be undone.'):
            return
        try:
            os.remove(path)
            self._del_orig_btn.pack_forget()
            self._last_compressed_path = None
            self._status_var.set(f'Original deleted: {name}')
        except Exception as e:
            messagebox.showerror('Delete Error', str(e))

    def _refresh_list(self):
        for item in self._tree.get_children():
            self._tree.delete(item)

        try:
            from engine.compressor import list_stored_files
            self._all_records = list_stored_files(BASE_DIR)
        except Exception:
            self._all_records = []
            return

        search = self._search_var.get().lower() if hasattr(self, '_search_var') else ''
        self._populate_tree(search)

    def _populate_tree(self, search: str = ''):
        for item in self._tree.get_children():
            self._tree.delete(item)

        total_orig = 0
        total_seed = 0
        count = 0

        for rec in self._all_records:
            name = os.path.basename(rec['path'])
            if search and search not in name.lower() and search not in rec['path'].lower():
                continue

            orig = rec.get('original_size', 0)
            seed = rec.get('seed_size', 0)
            ratio = round(orig / seed, 1) if seed > 0 else 0
            total_orig += orig
            total_seed += seed
            count += 1

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
        n_total = len(self._all_records)
        if search and count != n_total:
            label = (f'HDM: {count}/{n_total} files shown  |  '
                     f'{_human_size(total_orig)} → {_human_size(total_seed)}  '
                     f'({total_ratio}:1)')
        else:
            label = (f'HDM: {n_total} file{"s" if n_total != 1 else ""}  |  '
                     f'{_human_size(total_orig)} → {_human_size(total_seed)}  '
                     f'({total_ratio}:1)')
        self._hdm_label.config(text=label,
                               fg=ACCENT if n_total > 0 else TEXT_SEC)

    def _on_search_change(self, *_):
        search = self._search_var.get().lower()
        self._populate_tree(search)

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
        self._status_var.set(f'Retrieving {name}…')
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

    def _show_build_help(self):
        win = tk.Toplevel(self)
        win.title('How to Build NexForge_UCE.exe')
        win.configure(bg=DARK_BG)
        win.geometry('640x520')
        win.resizable(True, True)

        tk.Label(win, text='Building NexForge UCE as a Windows .exe',
                 font=FONT_TITLE, bg=DARK_BG, fg=TEXT_PRI).pack(pady=(20, 4), padx=20, anchor='w')

        sep = tk.Frame(win, bg=BORDER, height=1)
        sep.pack(fill='x', padx=20)

        text = tk.Text(win, bg=PANEL_BG, fg=TEXT_PRI, font=FONT_MONO,
                       relief='flat', wrap='word', padx=12, pady=12,
                       highlightthickness=0)
        text.pack(fill='both', expand=True, padx=20, pady=12)

        instructions = (
            "STEP 1 — Prerequisites\n"
            "  Install Python 3.10+ from https://python.org\n"
            "  Make sure 'Add Python to PATH' is checked during install.\n\n"
            "STEP 2 — Install required packages\n"
            "  Open Command Prompt in the project folder and run:\n\n"
            "    pip install -r requirements.txt\n"
            "    pip install pyinstaller\n\n"
            "STEP 3 — Build the .exe\n"
            "  Double-click  build_exe.bat  (or run it from Command Prompt).\n"
            "  This produces:  dist\\NexForge_UCE.exe\n\n"
            "  (Build takes 1–3 minutes on first run.)\n\n"
            "STEP 4 — Set up the flash drive\n"
            "  Copy the following to the root of your flash drive:\n\n"
            "    NexForge_UCE.exe   (from dist\\)\n"
            "    autorun.inf\n"
            "    launch.bat\n"
            "    launch_portable.bat\n"
            "    requirements.txt\n\n"
            "  The engine\\  folder is created automatically on first launch.\n"
            "  First launch takes ~30 seconds to generate the codebook.\n\n"
            "STEP 5 — Auto-launch on USB plug-in (Windows)\n"
            "  autorun.inf is already configured. On Windows 10/11, AutoRun\n"
            "  is disabled by default for security. The user will see an\n"
            "  AutoPlay popup — they click 'Run launch.bat' to start the app.\n\n"
            "  To enable full auto-launch (advanced):\n"
            "    1. Open Group Policy Editor (gpedit.msc)\n"
            "    2. Navigate to: Computer Config > Admin Templates >\n"
            "       Windows Components > AutoPlay Policies\n"
            "    3. Enable 'Turn on AutoPlay' and set to 'All drives'\n\n"
            "STEP 6 — Portable Python (no install required on target PC)\n"
            "  Download the embeddable Python package from python.org.\n"
            "  Extract it into a  python\\  subfolder on the flash drive.\n"
            "  launch_portable.bat will use it automatically.\n"
        )

        text.insert('1.0', instructions)
        text.config(state='disabled')

        tk.Button(win, text='Close', command=win.destroy,
                  font=FONT_SMALL, bg=PANEL_BG, fg=ACCENT,
                  relief='flat', padx=12, pady=4, cursor='hand2').pack(pady=(0, 16))

    def _show_about(self):
        win = tk.Toplevel(self)
        win.title('About NexForge UCE')
        win.configure(bg=DARK_BG)
        win.geometry('500x440')
        win.resizable(False, False)

        tk.Label(win, text='NexForge UCE',
                 font=FONT_TITLE, bg=DARK_BG, fg=TEXT_PRI).pack(pady=(24, 2))
        tk.Label(win, text='Universal Compression Engine',
                 font=FONT_UI, bg=DARK_BG, fg=TEXT_SEC).pack()

        sep = tk.Frame(win, bg=BORDER, height=1)
        sep.pack(fill='x', padx=30, pady=16)

        about_text = (
            "Six specialised seed extractors fused with a\n"
            "Hyperdimensional Memory (HDM) for extreme compression.\n\n"
            "  Fractal IFS     — images, 3D geometry (self-similarity)\n"
            "  Tensor Networks — tabular/CSV (low-rank SVD)\n"
            "  Grammar Infer   — text, code, documents\n"
            "  Program Synth   — numeric sequences & patterns\n"
            "  Holographic CB  — random/encrypted data\n"
            "  Boundary Ext.   — video & audio\n\n"
            "Every file type is guaranteed lossless.\n"
            "All seeds stored in a SQLite-backed HDM with\n"
            "content-addressable recall via hypervectors.\n\n"
            "Runs fully offline. No LLM. No internet required."
        )

        tk.Label(win, text=about_text, font=FONT_SMALL, bg=DARK_BG, fg=TEXT_PRI,
                 justify='left').pack(padx=30, anchor='w')

        sep2 = tk.Frame(win, bg=BORDER, height=1)
        sep2.pack(fill='x', padx=30, pady=16)

        tk.Label(win, text='Powered by: Python · NumPy · Pillow · zstd · Tkinter',
                 font=FONT_SMALL, bg=DARK_BG, fg=TEXT_MUT).pack()

        tk.Button(win, text='Close', command=win.destroy,
                  font=FONT_SMALL, bg=PANEL_BG, fg=ACCENT,
                  relief='flat', padx=12, pady=4, cursor='hand2').pack(pady=16)

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
