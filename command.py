import sublime, sublime_plugin
import subprocess, os, sys
import platform
import tempfile
import threading
import time
from .edit.Edit import Edit

try:
    import thread
except:
    import _thread as thread

for path in os.environ["PATH"].split(";"):
    sys.path.append(path)
sys.path = list(set(list(sys.path)))


class Globals:
    pass


Globals = Globals()

Globals.formatters = []

Globals.on_save = False
Globals.on_save_no_format = False

Globals.binary_file_patterns = []

Globals.temp = 0

Globals.debug = False


def plugin_loaded():
    s = sublime.load_settings("Format.sublime-settings")
    s.clear_on_change("format_reload")
    s.add_on_change("format_reload", lambda: plugin_loaded())
    Globals.formatters = s.get("formatters", Globals.formatters)
    Globals.on_save = s.get("on_save", Globals.on_save)

    s = sublime.load_settings("Preferences.sublime-settings")
    s.clear_on_change("format_reload_st")
    s.add_on_change("format_reload_st", lambda: plugin_loaded())
    Globals.binary_file_patterns = s.get(
        "binary_file_patterns", Globals.binary_file_patterns
    )


# from save
class format_code_on_save(sublime_plugin.EventListener):
    def on_post_save(self, view):
        if Globals.on_save and not Globals.on_save_no_format:
            Format(view, True).start()
        Globals.on_save_no_format = False


# from save without formatting
class format_code_on_save_no_format(sublime_plugin.WindowCommand):
    def run(self):
        Globals.on_save_no_format = True
        sublime.active_window().active_view().run_command("save")


# from command palette (for selections or complete document)
class format_code(sublime_plugin.TextCommand):
    def run(self, edit):
        Format(sublime.active_window().active_view()).start()


# toggles


class format_on_save_toggle(sublime_plugin.WindowCommand):
    def run(self):
        Globals.on_save = not Globals.on_save
        s = sublime.load_settings("Format.sublime-settings")
        s.set("on_save", Globals.on_save)
        sublime.save_settings("Format.sublime-settings")


# format


class Format(threading.Thread):
    def __init__(self, view, from_save=False):
        self.view = view
        self.file_name = view.file_name() or ""
        self.change_count = view.change_count()
        self.from_save = from_save
        self.syntax = ""

        self.command = None
        self.formatter = None
        self.binary = None

        if self.file_name:
            try:
                self.file_extension = (self.file_name.split(".").pop() or "").lower()
            except:
                self.file_extension = ""
        else:
            self.file_extension = ""

        self.syntax = (view.settings().get("syntax", "") or "").lower()
        if not self.syntax:
            self.syntax = ""

        for item in Globals.formatters:
            if "extensions" in item and self.file_extension in [
                ext.lower() for ext in item["extensions"]
            ]:
                self.formatter = item
                break

        if not self.formatter:
            for item in Globals.formatters:
                if not self.formatter and "syntax contains" in item:
                    for s in item["syntax contains"]:
                        if s in self.syntax:
                            self.formatter = item
                            break

        if not self.formatter:
            for item in Globals.formatters:
                if not self.formatter and "default" in item:
                    self.formatter = item
                    if Globals.debug:
                        self.print("Using default formatter")
                    break

        for item in Globals.binary_file_patterns:
            if item in self.file_name:
                if Globals.debug:
                    self.print("Matched binary", item, "in", self.file_name)
                self.binary = True

        threading.Thread.__init__(self)

    def run(self):

        if self.binary:
            return

        if not self.formatter:
            msg = [
                "No formatter. Extension: '"
                + self.file_extension
                + "' Syntax: '"
                + self.syntax
                + "'"
            ]
            self.print(msg)
            return

        sel = list(self.view.sel() or [])
        sel.reverse()
        sel_is_empty = all([False for _sel in sel if _sel and not _sel.empty()])

        if self.view.change_count() == self.change_count:

            if (
                self.file_name
                and self.file_extension
                in [ext.lower() for ext in self.formatter["extensions"]]
                and (self.from_save or (sel_is_empty and not self.view.is_dirty()))
            ):
                if Globals.debug:
                    self.print("Formatting from complete document")
                self.format_region(sublime.Region(0, self.view.size()), True)
                if (
                    self.from_save
                    and self.view.is_dirty()
                    and self.view.change_count() == self.change_count
                ):
                    sublime.set_timeout(lambda: self.view.run_command("save"), 0)
            elif self.from_save or (sel_is_empty):
                if Globals.debug:
                    self.print("Formatting from complete document")
                self.format_region(sublime.Region(0, self.view.size()), True)
                if (
                    self.from_save
                    and self.view.is_dirty()
                    and self.view.change_count() == self.change_count
                ):
                    sublime.set_timeout(lambda: self.view.run_command("save"), 0)
            else:
                if Globals.debug:
                    self.print("Formatting selections")
                for region in sel:
                    if region.empty():
                        continue
                    self.format_region(region)

        else:
            if Globals.debug:
                self.print("Code changed since the time we started formatting")

    def format_region(self, region, complete=False):

        if not "stdout" in self.formatter:
            msg = [
                "Cannot format region if no stdout command is provided. Extension: '"
                + str(self.file_extension)
                + "' Syntax: '"
                + str(self.syntax)
                + "'"
            ]
            self.print(msg)
            return

        text = self.view.substr(region)

        if self.file_name and complete:
            temporal = self.file_name
        elif self.file_name:
            temporal = os.path.join(
                os.path.dirname(self.file_name), "st-format-tmp-" + str(Globals.temp)
            )
        else:
            temporal = tempfile.NamedTemporaryFile(
                delete=False, suffix="." + self.formatter["extensions"][0]
            ).name

        if temporal != self.file_name:
            with open(temporal, "wb") as f:
                f.write(bytes(text, "UTF-8"))
                f.close()
        if platform.system() == "Windows" or os.name == "nt":
            command = "type"
        else:
            command = "cat"
        self.command = [command, temporal, "|"] + self.formatter["stdout"]

        for k, v in enumerate(self.command):
            if self.command[k] == "$FILE":
                self.command[k] = temporal
            elif self.command[k] == "$DUMMY_FILE_NAME":
                self.command[k] = "f." + self.formatter["extensions"][0]
            else:
                self.command[k] = self.expand(self.command[k])

        p = self.cli(self.command)
        if p["returncode"] != 0:
            self.error(p)
        else:
            new_text = p["stdout"].decode("utf8")

            if new_text != text:
                if new_text == "":
                    if Globals.debug:
                        self.print("Formatted code is empty")
                elif self.view.change_count() == self.change_count:
                    self.change_count += 1

                    point = self.view.line(self.view.visible_region().a).b

                    selections = list(self.view.sel())

                    with Edit(self.view) as edit:
                        edit.replace(region, new_text)
                        self.success(p)
                    self.view.sel().clear()
                    for sel in selections:
                        self.view.sel().add(sel)
                    self.view.show(point, False)
                else:
                    if Globals.debug:
                        self.print("Code changed since the time we started formatting")
            else:
                if Globals.debug:
                    self.print("Code didn't change, skipping")
                    self.success(p)
        try:
            if temporal and temporal != self.file_name:
                os.unlink(temporal)
        except:
            pass

    def cli(self, command):
        info = subprocess.STARTUPINFO()
        info.dwFlags = subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = 0
        p = subprocess.Popen(
            command,
            startupinfo=info,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=platform.system() == "Windows" or os.name == "nt",
        )
        stdout, stderr = p.communicate()
        try:
            p.kill()
        except:
            pass

        return {"stderr": stderr, "stdout": stdout, "returncode": p.returncode}

    def message(self, msg):
        sublime.set_timeout(lambda: sublime.active_window().status_message(msg), 0)

    def error(self, p):
        msg = [
            "file path: " + self.file_name,
            "return code: " + str(p["returncode"]),
            "command: " + str(self.command),
        ]
        if p["stderr"]:
            msg.append(p["stderr"])
        self.print(msg)
        self.message("Format Error")

    def success(self, p):
        msg = [str(self.command)]
        self.print(" : ".join(msg))
        self.message("Formatted")

    def print(self, *args):
        for item in args:
            if isinstance(item, (list,)):
                for i in item:
                    print("Format Code:", str(i).strip())
            else:
                print("Format Code:", str(item).strip())

    def expand(self, s):
        home = os.path.expanduser("~") + "/"
        s = s.replace("~/", home)
        for k, v in list(os.environ.items()):
            s = s.replace("%" + k + "%", v).replace("%" + k.lower() + "%", v)
        return s
