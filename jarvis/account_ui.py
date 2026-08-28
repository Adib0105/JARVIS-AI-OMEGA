from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def install_account_ui() -> None:
    """Patch the desktop shell with signed-in profile UI without changing creator identity."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog
    from PIL import Image, ImageTk

    from . import gui
    from .accounts import AccountStore, active_profile, activate_profile_environment, clear_active_profile, remember_active_profile
    from .config import settings

    cls = gui.JarvisDesktop
    if getattr(cls, '_account_ui_installed', False):
        return
    cls._account_ui_installed = True
    original_header = cls._build_header
    original_center = cls._build_center

    def account_dialog(app) -> None:
        store = AccountStore(); profile = active_profile(store)
        if profile is None:
            messagebox.showinfo('Account', 'No active account.', parent=app.root); return
        win = tk.Toplevel(app.root); win.title('JARVIS OMEGA // PROFILE'); win.geometry('430x520'); win.configure(bg=gui.PANEL); win.transient(app.root); win.grab_set()
        avatar_holder = tk.Label(win, bg=gui.PANEL, fg=gui.CYAN, text='PROFILE', font=('Segoe UI', 15, 'bold')); avatar_holder.pack(pady=(22,8))
        def load_avatar() -> None:
            try:
                if profile.avatar_path.is_file():
                    image=Image.open(profile.avatar_path).convert('RGB').resize((112,112)); photo=ImageTk.PhotoImage(image); avatar_holder.configure(image=photo,text=''); avatar_holder.image=photo
            except Exception: pass
        load_avatar()
        name_var=tk.StringVar(value=profile.display_name)
        tk.Label(win,text=f'@{profile.username}',bg=gui.PANEL,fg=gui.MUTED,font=('Consolas',10,'bold')).pack()
        tk.Label(win,text='DISPLAY NAME',bg=gui.PANEL,fg=gui.TEXT).pack(anchor='w',padx=38,pady=(18,3))
        tk.Entry(win,textvariable=name_var,bg='#0a202e',fg='white',insertbackground=gui.CYAN,relief='flat').pack(fill='x',padx=38,ipady=8)
        def save_name():
            nonlocal profile
            try:
                profile=store.update_display_name(profile.id,name_var.get()); remember_active_profile(profile); activate_profile_environment(profile)
                messagebox.showinfo('Profile','Name saved. JARVIS restart ke baad har jagah updated name dikhega.',parent=win)
            except Exception as exc: messagebox.showerror('Profile',str(exc),parent=win)
        def upload_avatar():
            path=filedialog.askopenfilename(parent=win,title='Choose profile photo',filetypes=[('Images','*.png *.jpg *.jpeg *.webp')])
            if not path: return
            try: store.set_avatar(profile,Path(path)); load_avatar(); messagebox.showinfo('Profile','Profile photo saved.',parent=win)
            except Exception as exc: messagebox.showerror('Profile Photo',str(exc),parent=win)
        def recovery():
            code=simpledialog.askstring('Recovery Code','New one-time recovery code (6-200 characters):',show='*',parent=win)
            if code is None: return
            try: store.set_recovery_code(profile.id,code); messagebox.showinfo('Recovery','One-time recovery code updated. Isse safe jagah yaad/rakhna.',parent=win)
            except Exception as exc: messagebox.showerror('Recovery',str(exc),parent=win)
        def logout():
            if not messagebox.askyesno('Logout','Logout karke login screen par wapas jana hai?',parent=win): return
            clear_active_profile()
            try:
                args=[sys.executable]
                if not getattr(sys,'frozen',False): args.append(str(Path(__file__).resolve().parents[1]/'desktop_app.py'))
                subprocess.Popen(args, cwd=str(Path(sys.executable).resolve().parent) if getattr(sys,'frozen',False) else str(Path(__file__).resolve().parents[1]), close_fds=True)
            except Exception: pass
            app.root.destroy()
        for text,command,color in [('SAVE NAME',save_name,gui.GREEN),('UPLOAD PROFILE PHOTO',upload_avatar,gui.MAGENTA),('SET / CHANGE RECOVERY PIN',recovery,gui.GOLD),('LOGOUT / SWITCH ACCOUNT',logout,gui.RED)]:
            tk.Button(win,text=text,command=command,bg='#0b2a3a',fg=color,relief='flat',pady=9).pack(fill='x',padx=38,pady=4)
        tk.Label(win,text='Creator identity stays Adib Azam. This profile controls only the signed-in user name, avatar and private local data.',bg=gui.PANEL,fg=gui.MUTED,wraplength=350,justify='center',font=('Segoe UI',8)).pack(padx=30,pady=(16,0))

    def patched_header(app) -> None:
        original_header(app)
        # Header is the first packed child. Keep creator identity internal, but show the signed-in account in UI.
        try:
            header=app.root.winfo_children()[0]
            def walk(widget):
                for child in widget.winfo_children():
                    try:
                        text=str(child.cget('text'))
                        if text.startswith('OPERATOR:'):
                            child.configure(text=f'ACCOUNT: {settings.user_name.upper()}  •  PROFILE',cursor='hand2')
                            child.bind('<Button-1>',lambda _e: account_dialog(app))
                    except Exception: pass
                    walk(child)
            walk(header)
            profile=active_profile(AccountStore())
            if profile and profile.avatar_path.is_file():
                operator=header.winfo_children()[-1]
                image=Image.open(profile.avatar_path).convert('RGB').resize((38,38)); photo=ImageTk.PhotoImage(image)
                badge=tk.Label(operator,image=photo,bg='#061725',cursor='hand2'); badge.image=photo; badge.pack(side='left',padx=(0,8)); badge.bind('<Button-1>',lambda _e: account_dialog(app)); app._account_avatar_ref=photo
        except Exception: pass

    def patched_center(app, parent) -> None:
        original_center(app,parent)
        # Legacy welcome text used creator_name as the operator. Replace only the visible welcome line.
        try:
            chat=app.chat; state=str(chat.cget('state')); chat.configure(state='normal')
            needle=f'Welcome, {settings.creator_name}'
            start='1.0'
            while True:
                idx=chat.search(needle,start,stopindex='end')
                if not idx: break
                replacement=f'Welcome, {settings.user_name}'
                chat.delete(idx,f'{idx}+{len(needle)}c'); chat.insert(idx,replacement); start=f'{idx}+{len(replacement)}c'
            chat.configure(state=state)
        except Exception: pass

    cls._build_header=patched_header
    cls._build_center=patched_center
    cls._open_account_profile=lambda app: account_dialog(app)

__all__=['install_account_ui']
