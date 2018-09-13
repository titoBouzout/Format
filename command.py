import sublime, sublime_plugin
import subprocess, os, sys
import platform
import tempfile
import threading
from .edit.Edit import Edit as Edit


class Globals:
    pass


Globals = Globals()
Globals.Formatters = {}
Globals.format_on_save = True
Globals.save_no_format = False
Globals.counter = 0
Globals.already_shown = {}
Globals.binary_file_patterns = []


def plugin_loaded():
    s = sublime.load_settings("Format.sublime-settings")
    s.clear_on_change("reload")
    s.add_on_change("reload", lambda: plugin_loaded())
    Globals.Formatters = s.get("format", {})
    Globals.format_on_save = s.get("format_on_save", True)

    s = sublime.load_settings("Preferences.sublime-settings")
    s.clear_on_change("reload")
    s.add_on_change("reload", lambda: plugin_loaded())
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
    def on_post_save(self, view):
        if Globals.format_on_save and not Globals.save_no_format:
            Format(sublime.active_window().active_view(), True).run()
        Globals.save_no_format = False


class format_code_save_no_format(sublime_plugin.WindowCommand):
    def run(self):
        Globals.save_no_format = True
        sublime.active_window().run_command("save")


class Format(threading.Thread):
    def __init__(self, view, from_save=False):
        self.view = view
        self.file_extension = None
        self.command = None
        self.extension = self.guess_formatter()
        self.change_count = view.change_count()
        self.from_save = from_save
        threading.Thread.__init__(self)

    def run(self):
        if not self.extension or self.extension not in Globals.Formatters:
            if self.extension:
                msg = [
                    self.view.file_name(),
                    "No formatter declared for file extension: " + str(self.extension),
                ]
                key = ",".join(msg)

                if key not in Globals.already_shown:
                    Globals.already_shown[key] = True
                    self.print(msg)
            return
        if "command" not in Globals.Formatters[self.extension]:
            msg = [
                self.view.file_name(),
                "Command to run for the extension '"
                + (self.extension)
                + "' is empty on package settings",
            ]
            key = ",".join(msg)

            if key not in Globals.already_shown:
                Globals.already_shown[key] = True
                self.print(msg)
            return

        sel = self.view.sel() or []
        sel = list(sel)
        sel.reverse()
        sel_is_empty = len(sel) == 1 and sel[0].empty()
        if self.from_save or (
            sel_is_empty and self.view.file_name() and not self.view.is_dirty()
        ):
            for item in Globals.binary_file_patterns:
                if item in self.view.file_name():
                    return
            if self.view.change_count() == self.change_count:
                self.command = Globals.Formatters[self.extension]["command"] + [
                    "--",
                    self.view.file_name(),
                ]
                for k, v in enumerate(self.command):
                    self.command[k] = self.expand(self.command[k])
                p = self.cli(self.command)
                if p["returncode"] != 0:
                    if (
                        self.file_extension != self.extension
                        and "on unrecognised" in Globals.Formatters[self.extension]
                        and Globals.Formatters[self.extension]["on unrecognised"]
                        in p["stderr"]
                    ):
                        temporal = (
                            self.view.file_name()
                            + ".sublime-format-temporal."
                            + self.extension
                        )
                        with open(temporal, "wb") as f:
                            with open(self.view.file_name(), "rb") as r:
                                f.write(r.read())
                                r.close()
                                f.close()
                                p = self.cli(
                                    Globals.Formatters[self.extension]["command"]
                                    + ["--", temporal]
                                )
                                if p["returncode"] != 0:
                                    self.print_error(p)
                                else:
                                    if self.view.change_count() == self.change_count:
                                        open(self.view.file_name(), "wb").write(
                                            open(temporal, "rb").read()
                                        )
                                        self.message("Formatted")
                                try:
                                    os.unlink(temporal)
                                except:
                                    pass
                    else:
                        self.print_error(p)

                else:
                    self.message("Formatted")
        elif sel_is_empty and not self.view.file_name():
            self.format_region(sublime.Region(0, self.view.size()))
        else:
            for region in sel:
                if region.empty():
                    continue
                self.format_region(region)

    def format_region(self, region):
        text = self.view.substr(region)

        Globals.counter += 1

        if self.view.file_name():
            temporal = (
                os.path.dirname(self.view.file_name())
                + "/sublime-format-temporal-"
                + str(Globals.counter)
                + "."
                + self.extension
            )
        else:
            temporal = tempfile.NamedTemporaryFile(
                delete=False, suffix="." + self.extension
            ).name

        with open(temporal, "wb") as f:
            f.write(bytes(text, "UTF-8"))
            f.close()
            self.command = Globals.Formatters[self.extension]["command"] + [
                "--",
                temporal,
            ]
            for k, v in enumerate(self.command):
                self.command[k] = self.expand(self.command[k])
            p = self.cli(self.command)

            if p["returncode"] != 0:
                self.print_error(p)
            else:
                with open(temporal, "rb") as r:
                    new_text = r.read().decode("utf8")
                    if new_text != text:
                        if self.view.change_count() == self.change_count:
                            self.change_count += 1
                            with Edit(self.view) as edit:
                                edit.replace(region, new_text)
                                self.message("Formatted")
                        else:
                            # self.print("Code changed since the time we started formatting")
                            pass
                    else:
                        # self.print("Code didnt change, skipping")
                        pass
            try:
                os.unlink(temporal)
            except:
                pass

    def guess_formatter(self):
        extension = None
        self.file_extension = None
        if self.view.file_name():
            try:
                extension = self.view.file_name().split(".").pop()
                self.file_extension = extension
                if extension in Globals.Formatters:
                    if not "command" in Globals.Formatters[extension]:
                        pass
                    else:
                        return extension
            except:
                pass
        syntax = self.view.settings().get("syntax", "").lower()
        for item in Globals.Formatters.keys():
            if (
                "syntax contains" in Globals.Formatters[item]
                and Globals.Formatters[item]["syntax contains"] in syntax
            ):
                if (
                    "pretend to be" in Globals.Formatters[item]
                    and Globals.Formatters[item]["pretend to be"]
                ):
                    extension = Globals.Formatters[item]["pretend to be"]
                else:
                    extension = item
                break

        return extension

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

        p = {"stderr": str(stderr), "stdout": str(stdout), "returncode": p.returncode}
        return p

    def message(self, msg):
        sublime.set_timeout(lambda: sublime.active_window().status_message(msg), 0)

    def print_error(self, p):
        self.print(
            "file path: " + self.view.file_name(),
            "return code: " + str(p["returncode"]),
            "command: " + str(self.command),
            "on unrecognised: "
            + str(
                Globals.Formatters[self.extension]["on unrecognised"]
                if "on unrecognised" in Globals.Formatters[self.extension]
                else ""
            ),
            "stdout: " + p["stdout"],
            "stderr: " + p["stderr"],
        )
        self.message("Format Error")

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