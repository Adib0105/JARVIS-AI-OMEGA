from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Broad Unicode emoji coverage without bundling or copying WhatsApp artwork.
# Rendering uses the operating system's emoji font (Segoe UI Emoji on Windows).
EMOJI_CATEGORIES: dict[str, tuple[str, ...]] = {
    'Smileys': tuple('😀 😃 😄 😁 😆 😅 😂 🤣 😊 😇 🙂 🙃 😉 😌 😍 🥰 😘 😗 😙 😚 😋 😛 😝 😜 🤪 🤨 🧐 🤓 😎 🤩 🥳 😏 😒 😞 😔 😟 😕 🙁 ☹️ 😣 😖 😫 😩 🥺 😢 😭 😤 😠 😡 🤬 🤯 😳 🥵 🥶 😱 😨 😰 😥 😓 🤗 🤔 🤭 🤫 🤥 😶 😐 😑 😬 🙄 😯 😦 😧 😮 😲 🥱 😴 🤤 😪 😵 🤐 🥴 🤢 🤮 🤧 😷 🤒 🤕'.split()),
    'People': tuple('👋 🤚 🖐️ ✋ 🖖 👌 🤌 🤏 ✌️ 🤞 🤟 🤘 🤙 👈 👉 👆 👇 ☝️ 👍 👎 ✊ 👊 🤛 🤜 👏 🙌 👐 🤲 🤝 🙏 ✍️ 💅 🤳 💪 🦾 🦿 🦵 🦶 👂 👃 🧠 🫀 🫁 🦷 🦴 👀 👁️ 👅 👄 🧑 👨 👩 👶 🧒 👦 👧 🧔 👱 👴 👵 🙍 🙎 🙅 🙆 💁 🙋 🧏 🙇 🤦 🤷 👮 👷 💂 🕵️ 👩‍⚕️ 👨‍⚕️ 👩‍🎓 👨‍🎓 👩‍💻 👨‍💻 👩‍🚀 👨‍🚀'.split()),
    'Hearts': tuple('❤️ 🧡 💛 💚 💙 💜 🖤 🤍 🤎 💔 ❣️ 💕 💞 💓 💗 💖 💘 💝 💟 ♥️ 💌 💋 🫶'.split()),
    'Animals': tuple('🐶 🐱 🐭 🐹 🐰 🦊 🐻 🐼 🐻‍❄️ 🐨 🐯 🦁 🐮 🐷 🐸 🐵 🙈 🙉 🙊 🐒 🐔 🐧 🐦 🐤 🦆 🦅 🦉 🦇 🐺 🐗 🐴 🦄 🐝 🪱 🐛 🦋 🐌 🐞 🐜 🪰 🪲 🪳 🕷️ 🦂 🐢 🐍 🦎 🐙 🦑 🦐 🦞 🦀 🐠 🐟 🐡 🐬 🐳 🦈 🐊 🐅 🐆 🦓 🦍 🐘 🦛 🦏 🐪 🦒 🦘 🦬 🐃 🐄 🐎 🐖 🐏 🐐 🦌 🐕 🐈 🪶 🐓 🦃 🦚 🦜 🦢 🦩 🕊️ 🐇 🦝 🦨 🦡 🦫 🦦 🦥 🐁 🐿️ 🦔'.split()),
    'Food': tuple('🍏 🍎 🍐 🍊 🍋 🍌 🍉 🍇 🍓 🫐 🍈 🍒 🍑 🥭 🍍 🥥 🥝 🍅 🍆 🥑 🥦 🥬 🥒 🌶️ 🫑 🌽 🥕 🫒 🧄 🧅 🥔 🍠 🥐 🥯 🍞 🥖 🥨 🧀 🥚 🍳 🧈 🥞 🧇 🥓 🥩 🍗 🍖 🌭 🍔 🍟 🍕 🥪 🥙 🧆 🌮 🌯 🥗 🥘 🫕 🍝 🍜 🍲 🍛 🍣 🍱 🥟 🦪 🍤 🍙 🍚 🍘 🍥 🥠 🥮 🍢 🍡 🍧 🍨 🍦 🥧 🧁 🍰 🎂 🍮 🍭 🍬 🍫 🍿 🍩 🍪 ☕ 🫖 🍵 🥤 🧋 🧃 🧉 🥛'.split()),
    'Activity': tuple('⚽ 🏀 🏈 ⚾ 🥎 🎾 🏐 🏉 🥏 🎱 🪀 🏓 🏸 🏒 🏑 🥍 🏏 🪃 🥅 ⛳ 🪁 🏹 🎣 🤿 🥊 🥋 🎽 🛹 🛼 🛷 ⛸️ 🥌 🎿 ⛷️ 🏂 🪂 🏋️ 🤼 🤸 ⛹️ 🤺 🤾 🏌️ 🏇 🧘 🏄 🏊 🤽 🚣 🧗 🚴 🚵 🏆 🥇 🥈 🥉 🏅 🎖️'.split()),
    'Travel': tuple('🚗 🚕 🚙 🚌 🚎 🏎️ 🚓 🚑 🚒 🚐 🛻 🚚 🚛 🚜 🏍️ 🛵 🚲 🛴 🚨 🚔 🚍 🚘 🚖 🚡 🚠 🚟 🚃 🚋 🚞 🚝 🚄 🚅 🚈 🚂 🚆 🚇 🚊 🚉 ✈️ 🛫 🛬 🛩️ 💺 🛰️ 🚀 🛸 🚁 🛶 ⛵ 🚤 🛥️ 🛳️ ⛴️ 🚢 ⚓ ⛽ 🚧 🚦 🚥 🗺️ 🗿 🗽 🗼 🏰 🏯 🏟️ 🎡 🎢 🎠 ⛲ ⛺ 🌁 🌃 🏙️ 🌄 🌅 🌆 🌇 🌉'.split()),
    'Objects': tuple('⌚ 📱 💻 ⌨️ 🖥️ 🖨️ 🖱️ 💽 💾 💿 📀 🧮 🎥 🎞️ 📞 ☎️ 📺 📻 🎙️ 🎚️ 🎛️ 🧭 ⏱️ ⏰ ⌛ 📡 🔋 🔌 💡 🔦 🕯️ 🧯 🛢️ 💸 💵 💰 💳 💎 ⚖️ 🧰 🔧 🔨 ⚒️ 🛠️ ⛏️ 🔩 ⚙️ 🧱 ⛓️ 🧲 🔫 💣 🧨 🪓 🔪 🗡️ 🛡️ 🚬 ⚰️ 🪦 ⚱️ 🔮 📿 🧿 💈 ⚗️ 🔭 🔬 🕳️ 🩹 🩺 💊 💉 🩸 🚪 🛏️ 🛋️ 🚽 🚿 🛁 🧴 🧷 🧹 🧺 🧻 🧼 🪥 🧽 🧯 🛒 🎁 🎈 🎀 🎊 🎉'.split()),
    'Symbols': tuple('✅ ❌ ❗ ❓ ‼️ ⁉️ 💯 🔥 ✨ ⭐ 🌟 💫 ⚡ 💥 💢 💦 💨 🕳️ 💣 💬 👁️‍🗨️ 🗨️ 🗯️ 💭 💤 ♻️ ✔️ ☑️ ⚠️ 🚫 ⛔ 📛 🔞 ⭕ ❎ ➕ ➖ ➗ ✖️ ♾️ ©️ ®️ ™️ #️⃣ *️⃣ 0️⃣ 1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣ 6️⃣ 7️⃣ 8️⃣ 9️⃣ 🔟 ▶️ ⏸️ ⏯️ ⏹️ ⏺️ ⏭️ ⏮️ ⏩ ⏪ 🔀 🔁 🔂'.split()),
    'Flags': tuple('🇮🇳 🇺🇸 🇬🇧 🇨🇦 🇦🇺 🇯🇵 🇰🇷 🇨🇳 🇫🇷 🇩🇪 🇮🇹 🇪🇸 🇧🇷 🇦🇷 🇲🇽 🇦🇪 🇸🇦 🇵🇰 🇧🇩 🇳🇵 🇱🇰 🇸🇬 🇲🇾 🇮🇩 🇹🇭 🇻🇳 🇵🇭 🇿🇦 🇳🇬 🇪🇬 🇹🇷 🇷🇺 🇺🇦 🇳🇿'.split()),
}


def emoji_font(root: tk.Misc, size: int = 14) -> tuple[str, int]:
    """Return a native emoji-capable font tuple, preferring Windows color emoji."""
    try:
        families = {name.lower(): name for name in root.tk.call('font', 'families')}
    except Exception:
        families = {}
    for wanted in ('Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji', 'Apple Color Emoji'):
        if wanted.lower() in families:
            return (families[wanted.lower()], size)
    return ('Segoe UI', size)


def show_emoji_picker(root: tk.Misc, target: tk.Entry) -> tk.Toplevel:
    """Show an in-app searchable Unicode emoji picker and insert into target Entry."""
    win = tk.Toplevel(root)
    win.title('JARVIS // EMOJI PICKER')
    win.geometry('560x520')
    win.minsize(460, 400)
    win.transient(root)
    bg = '#07131d'; panel = '#0a202e'; fg = '#dff9ff'; accent = '#53e7ff'
    win.configure(bg=bg)

    search_var = tk.StringVar()
    search = tk.Entry(win, textvariable=search_var, bg=panel, fg=fg, insertbackground=accent, relief='flat', font=('Segoe UI', 11))
    search.pack(fill='x', padx=12, pady=(12, 8), ipady=7)

    notebook = ttk.Notebook(win)
    notebook.pack(fill='both', expand=True, padx=10, pady=(0, 10))
    font = emoji_font(root, 16)

    def insert(value: str) -> None:
        try:
            target.insert(tk.INSERT, value)
            target.focus_set()
        except Exception:
            pass

    def populate(frame: tk.Frame, values: tuple[str, ...], query: str = '') -> None:
        for child in frame.winfo_children():
            child.destroy()
        q = query.strip().lower()
        shown = [value for value in values if not q or q in value]
        columns = 9
        for index, value in enumerate(shown):
            button = tk.Button(frame, text=value, command=lambda e=value: insert(e), bg=panel, fg=fg,
                               activebackground='#12445b', activeforeground='white', relief='flat',
                               font=font, width=2, height=1, cursor='hand2')
            button.grid(row=index // columns, column=index % columns, padx=2, pady=2, sticky='nsew')
        for col in range(columns):
            frame.grid_columnconfigure(col, weight=1)

    frames: dict[str, tk.Frame] = {}
    for name, values in EMOJI_CATEGORIES.items():
        outer = tk.Frame(notebook, bg=bg)
        canvas = tk.Canvas(outer, bg=bg, highlightthickness=0)
        scroll = tk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        frame = tk.Frame(canvas, bg=bg)
        frame.bind('<Configure>', lambda _e, c=canvas: c.configure(scrollregion=c.bbox('all')))
        canvas.create_window((0, 0), window=frame, anchor='nw')
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side='left', fill='both', expand=True); scroll.pack(side='right', fill='y')
        notebook.add(outer, text=name)
        frames[name] = frame
        populate(frame, values)

    def refresh(*_args) -> None:
        q = search_var.get().strip()
        # Search is intentionally visual/character based; category tabs remain available.
        for name, frame in frames.items():
            populate(frame, EMOJI_CATEGORIES[name], q)

    search_var.trace_add('write', refresh)
    search.focus_set()
    return win


__all__ = ['EMOJI_CATEGORIES', 'emoji_font', 'show_emoji_picker']
