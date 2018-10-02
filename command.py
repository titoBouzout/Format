import sublime, sublime_plugin
import subprocess, os, sys
import platform
import tempfile
import threading
from .edit.Edit import Edit


class Globals:
    pass


Globals = Globals()
Globals.Formatters = []
Globals.format_on_save = True
Globals.save_no_format = False
Globals.counter = 0
Globals.binary_file_patterns = []


def plugin_loaded():
    s = sublime.load_settings("Format.sublime-settings")
    s.clear_on_change("reload_format")
    s.add_on_change("reload_format", lambda: plugin_loaded())
    Globals.Formatters = s.get("formatters", [])
    Globals.format_on_save = s.get("format_on_save", True)

    s = sublime.load_settings("Preferences.sublime-settings")
    s.clear_on_change("reload_format_sublime")
    s.add_on_change("reload_format_sublime", lambda: plugin_loaded())
    Globals.binary_file_patterns = s.get("binary_file_patterns", [])


for path in os.environ["PATH"].split(";"):
    sys.path.append(path)
sys.path = list(set(list(sys.path)))


class format_code(sublime_plugin.TextCommand):
    def run(self, edit):
        Format(sublime.active_window().active_view()).start()


class format_code_toggle(sublime_plugin.WindowCommand):
    def run(self):
        Globals.format_on_save = not Globals.format_on_save
        s = sublime.load_settings("Format.sublime-settings")
        s.set("format_on_save", Globals.format_on_save)
        sublime.save_settings("Format.sublime-settings")


class format_code_on_save(sublime_plugin.EventListener):
    def on_post_save_async(self, view):
        if Globals.format_on_save and not Globals.save_no_format:
            Format(sublime.active_window().active_view(), True).start()
        Globals.save_no_format = False


class format_code_save_no_format(sublime_plugin.WindowCommand):
    def run(self):
        Globals.save_no_format = True
        sublime.active_window().active_view().run_command("save")


class Format(threading.Thread):
    def __init__(self, view, from_save=False):
        self.view = view
        self.file_name = view.file_name()
        self.change_count = view.change_count()
        self.from_save = from_save

        self.command = None
        self.formatter = None
        self.binary = None

        if self.file_name:
            try:
                self.file_extension = self.file_name.split(".").pop()
            except:
                self.file_extension = None

        self.syntax = view.settings().get("syntax", "").lower()
        if not self.syntax:
            self.syntax = None

        for item in Globals.Formatters:
            if (
                "syntax contains" in item
                and "extension" in item
                and str(self.file_extension).lower() == str(item["extension"]).lower()
                and item["syntax contains"] in self.syntax
            ):
                self.formatter = item
                break

        if not self.formatter:
            for item in Globals.Formatters:
                if "syntax contains" in item and item["syntax contains"] in self.syntax:
                    self.formatter = item
                    break

        for item in Globals.binary_file_patterns:
            if item in self.file_name:
                self.binary = True

        threading.Thread.__init__(self)

    def run(self):

        if self.binary:
            return

        if not self.formatter:
            msg = [
                self.file_name,
                "No formatter declared for file. Extension: '"
                + str(self.file_extension)
                + "' Syntax: '"
                + str(self.syntax)
                + "'",
            ]
            self.print(msg)
            return

        if "command" not in self.formatter or "extension" not in self.formatter:
            msg = [
                self.file_name,
                "Command or Extension not declared in package settings. Extension '"
                + str(self.file_extension)
                + "' Syntax: '"
                + str(self.syntax)
                + "' ",
            ]
            self.print(msg)
            return

        sel = list(self.view.sel() or [])
        sel.reverse()
        sel_is_empty = all([False for _sel in sel if _sel and not _sel.empty()])

        if str(self.file_extension).lower() == str(
            self.formatter["extension"]
        ).lower() and (
            self.from_save
            or (sel_is_empty and self.file_name and not self.view.is_dirty())
        ):
            if self.view.change_count() == self.change_count:

                self.command = self.formatter["command"] + [self.file_name]
                for k, v in enumerate(self.command):
                    self.command[k] = self.expand(self.command[k])

                p = self.cli(self.command)
                if p["returncode"] != 0:
                    self.print_error(p)
                else:
                    if "use stdout" in self.formatter and self.formatter["use stdout"]:
                        new_text = p["stdout"].decode("utf8")
                        if new_text != self.view.substr(
                            sublime.Region(0, self.view.size())
                        ):
                            if self.view.change_count() == self.change_count:
                                self.change_count += 1
                                with Edit(self.view) as edit:
                                    edit.replace(
                                        sublime.Region(0, self.view.size()), new_text
                                    )
                                if self.from_save and self.view.is_dirty():
                                    self.view.run_command("save")
                                self.print_success(p)
                            else:
                                # self.print("Code changed since the time we started formatting")
                                pass
                        else:
                            # self.print("Code didn't change, skipping")
                            # self.print_success(p)
                            pass
                    else:
                        self.print_success(p)

        elif sel_is_empty or self.from_save:
            self.format_region(sublime.Region(0, self.view.size()))
            if self.from_save and self.view.is_dirty():
                self.view.run_command("save")
        else:
            for region in sel:
                if region.empty():
                    continue
                self.format_region(region)

    def format_region(self, region):
        text = self.view.substr(region)

        Globals.counter += 1

        if self.file_name:
            temporal = os.path.join(
                os.path.dirname(self.file_name),
                "sublime-package-format-temporal-"
                + str(Globals.counter)
                + "."
                + self.formatter["extension"],
            )
        else:
            temporal = tempfile.NamedTemporaryFile(
                delete=False, suffix="." + self.formatter["extension"]
            ).name

        with open(temporal, "wb") as f:
            f.write(bytes(text, "UTF-8"))
            f.close()

            self.command = self.formatter["command"] + [temporal]
            for k, v in enumerate(self.command):
                self.command[k] = self.expand(self.command[k])

            p = self.cli(self.command)
            if p["returncode"] != 0:
                self.print_error(p)
            else:
                with open(temporal, "rb") as r:
                    if "use stdout" in self.formatter and self.formatter["use stdout"]:
                        new_text = p["stdout"].decode("utf8")
                    else:
                        new_text = r.read().decode("utf8")
                    if new_text != text:
                        if self.view.change_count() == self.change_count:
                            self.change_count += 1
                            with Edit(self.view) as edit:
                                edit.replace(region, new_text)
                                self.print_success(p)
                        else:
                            # self.print("Code changed since the time we started formatting")
                            pass
                    else:
                        # self.print("Code didn't change, skipping")
                        # self.print_success(p)
                        pass
            try:
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

        p = {"stderr": stderr, "stdout": stdout, "returncode": p.returncode}
        return p

    def message(self, msg):
        sublime.set_timeout(lambda: sublime.active_window().status_message(msg), 0)

    def print_error(self, p):
        msg = [
            "file path: " + self.file_name,
            "return code: " + str(p["returncode"]),
            "command: " + str(self.command),
        ]
        if p["stdout"]:
            msg.append(p["stdout"])

        if p["stderr"]:
            msg.append(p["stderr"])
        self.print(msg)
        self.message("Format Error")

    def print_success(self, p):
        msg = [str(self.command)]
        if "use stdout" in self.formatter and self.formatter["use stdout"]:
            msg.append("[..code..]")
        elif p["stdout"]:
            msg.append(str(p["stdout"]))
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
