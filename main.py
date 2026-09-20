"""Clubapp - a minimal front end for the Aether core (SOCKS5 tunnel)."""
import json
import os
import re
import subprocess
import threading
import webbrowser

from kivy.app import App
from kivy.clock import mainthread
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

TELEGRAM = "https://t.me/Clubapp8"
SOCKS_ADDR = "127.0.0.1:1819"

# label -> (AETHER_PROTOCOL, use h2)
PROTOCOLS = {
    "MASQUE (h3 / UDP)": ("masque", False),
    "MASQUE (h2 / TCP)": ("masque", True),
    "WireGuard": ("wg", False),
    "gool (WireGuard in WireGuard)": ("gool", False),
}
NOIZE = {
    "masque": ["firewall", "gfw", "off"],
    "wg": ["balanced", "aggressive", "light", "off"],
    "gool": ["balanced", "aggressive", "light", "off"],
}
SCANS = ["balanced", "turbo", "thorough", "stealth"]

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def find_binary():
    """Aether is shipped as libaether.so so Android lets us execute it."""
    try:
        from jnius import autoclass

        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        lib_dir = activity.getApplicationInfo().nativeLibraryDir
        path = os.path.join(lib_dir, "libaether.so")
        if os.path.exists(path):
            return path
    except Exception:
        pass
    for name in ("aether", "aether.exe"):  # desktop testing
        if os.path.exists(name):
            return os.path.abspath(name)
    return None


class Core:
    def __init__(self, workdir, on_output, on_exit):
        self.workdir = workdir
        self.on_output = on_output
        self.on_exit = on_exit
        self.proc = None

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, protocol, http2, noize, scan):
        binary = find_binary()
        if not binary:
            raise RuntimeError("Aether binary not found in the app.")
        env = os.environ.copy()
        env.update(
            {
                "HOME": self.workdir,
                "AETHER_PROTOCOL": protocol,
                "AETHER_NOIZE": noize,
                "AETHER_SCAN": scan,
                "AETHER_SOCKS": SOCKS_ADDR,
            }
        )
        if http2:
            env["AETHER_MASQUE_HTTP2"] = "1"
        else:
            env.pop("AETHER_MASQUE_HTTP2", None)
        self.proc = subprocess.Popen(
            [binary],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=self.workdir,
            env=env,
            bufsize=0,
        )
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()

    def _reader(self, proc):
        while True:
            chunk = proc.stdout.read(1024)
            if not chunk:
                break
            text = ANSI.sub("", chunk.decode("utf-8", "replace")).replace("\r", "")
            self.on_output(text)
        self.on_exit(proc.wait())

    def send(self, text):
        if self.running:
            try:
                self.proc.stdin.write((text + "\n").encode())
                self.proc.stdin.flush()
            except Exception:
                pass

    def stop(self):
        if self.running:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.kill()


class Root(BoxLayout):
    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", padding=dp(16), spacing=dp(10), **kw)
        self.app = app
        self.settings = app.load_settings()
        self.core = Core(app.user_data_dir, self.on_output, self.on_exit)

        head = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(10))
        head.add_widget(Image(source="icon.png", size_hint_x=None, width=dp(56)))
        head.add_widget(Label(text="Clubapp", font_size="26sp", bold=True, halign="left"))
        self.add_widget(head)

        self.status = Label(text="Disconnected", size_hint_y=None, height=dp(28))
        self.add_widget(self.status)

        self.protocol = self._spinner("Protocol", list(PROTOCOLS), self.settings["protocol"])
        self.noize = self._spinner("Obfuscation", NOIZE["masque"], self.settings["noize"])
        self.scan = self._spinner("Scan mode", SCANS, self.settings["scan"])
        self.protocol.bind(text=self._on_protocol)
        self._on_protocol(self.protocol, self.protocol.text)

        self.button = Button(text="Connect", size_hint_y=None, height=dp(56), font_size="18sp")
        self.button.bind(on_release=self.toggle)
        self.add_widget(self.button)

        self.log_text = ""
        self.log = Label(text="", size_hint_y=None, halign="left", valign="top", font_size="12sp")
        self.log.bind(width=lambda *_: setattr(self.log, "text_size", (self.log.width, None)))
        self.log.bind(texture_size=lambda *_: setattr(self.log, "height", self.log.texture_size[1]))
        self.scroll = ScrollView()
        self.scroll.add_widget(self.log)
        self.add_widget(self.scroll)

        row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        self.input = TextInput(multiline=False, hint_text="Type here if the core asks something")
        self.input.bind(on_text_validate=self.send_input)
        send = Button(text="Send", size_hint_x=None, width=dp(70))
        send.bind(on_release=self.send_input)
        row.add_widget(self.input)
        row.add_widget(send)
        self.add_widget(row)

        tg = Button(text="Telegram channel", size_hint_y=None, height=dp(44))
        tg.bind(on_release=lambda *_: webbrowser.open(TELEGRAM))
        self.add_widget(tg)

    def _spinner(self, title, values, current):
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        row.add_widget(Label(text=title, size_hint_x=0.4))
        sp = Spinner(text=current if current in values else values[0], values=values)
        row.add_widget(sp)
        self.add_widget(row)
        return sp

    def _on_protocol(self, spinner, text):
        proto = PROTOCOLS[text][0]
        self.noize.values = NOIZE[proto]
        if self.noize.text not in NOIZE[proto]:
            self.noize.text = NOIZE[proto][0]

    def _lock(self, locked):
        for w in (self.protocol, self.noize, self.scan):
            w.disabled = locked

    def toggle(self, *_):
        if self.core.running:
            self.core.stop()
            return
        proto, h2 = PROTOCOLS[self.protocol.text]
        self.app.save_settings(
            {"protocol": self.protocol.text, "noize": self.noize.text, "scan": self.scan.text}
        )
        self.log_text = ""
        self.log.text = ""
        try:
            self.core.start(proto, h2, self.noize.text, self.scan.text)
        except Exception as e:
            self.on_output("Error: %s\n" % e)
            return
        self._lock(True)
        self.button.text = "Disconnect"
        self.status.text = "Connecting..."

    def send_input(self, *_):
        self.core.send(self.input.text)
        self.input.text = ""

    @mainthread
    def on_output(self, text):
        self.log_text = (self.log_text + text)[-6000:]
        self.log.text = self.log_text
        self.scroll.scroll_y = 0
        if "listening" in text.lower():
            self.status.text = "Connected - SOCKS5 %s" % SOCKS_ADDR

    @mainthread
    def on_exit(self, code):
        self._lock(False)
        self.button.text = "Connect"
        self.status.text = "Disconnected"


class ClubappApp(App):
    title = "Clubapp"
    icon = "icon.png"

    def build(self):
        self.root_widget = Root(self)
        return self.root_widget

    def on_stop(self):
        self.root_widget.core.stop()

    @property
    def _settings_path(self):
        return os.path.join(self.user_data_dir, "settings.json")

    def load_settings(self):
        data = {"protocol": "MASQUE (h3 / UDP)", "noize": "firewall", "scan": "balanced"}
        try:
            with open(self._settings_path) as f:
                data.update(json.load(f))
        except Exception:
            pass
        if data["protocol"] not in PROTOCOLS:
            data["protocol"] = "MASQUE (h3 / UDP)"
        return data

    def save_settings(self, data):
        try:
            with open(self._settings_path, "w") as f:
                json.dump(data, f)
        except Exception:
            pass


if __name__ == "__main__":
    ClubappApp().run()
