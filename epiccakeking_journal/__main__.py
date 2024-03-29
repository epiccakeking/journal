"""
Copyright 2022 epiccakeking

This file is part of epiccakeking_journal.

epiccakeking_journal is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your option) any later
version.

epiccakeking_journal is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
epiccakeking_journal. If not, see <https://www.gnu.org/licenses/>.
"""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib

# Try to load Libadwaita.
have_adw = False
try:
    gi.require_version("Adw", "1")
    from gi.repository import Adw

    have_adw = True
except Exception:  # Oh no! Anyway
    pass
from pkg_resources import resource_string
import datetime
from pathlib import Path
from epiccakeking_journal.utilities import strip_non_letters, templated
from epiccakeking_journal.backend import Backend, Settings
from epiccakeking_journal.widgets import SearchResult, WordCloud, JournalPage
from epiccakeking_journal.modals import (
    SearchModal,
    AboutModal,
    SettingsModal,
    StatsModal,
    ErrorDialog,
)

APP_ID = "io.github.epiccakeking.Journal"


def main():
    app = (Adw if have_adw else Gtk).Application(application_id=APP_ID)
    settings = Settings(Path(GLib.get_user_config_dir()) / APP_ID / "settings.json")
    gui = AltGui if settings.get("alt_gui") else MainWindow
    app.connect("activate", lambda _: gui(app, settings))
    app.run(None)


@templated
class MainWindow(Gtk.ApplicationWindow):
    __gtype_name__ = "MainWindow"
    backward = Gtk.Template.Child("backward")
    forward = Gtk.Template.Child("forward")
    calendar_menu = Gtk.Template.Child("calendar_menu")
    calendar = Gtk.Template.Child("calendar")
    page = None

    def __init__(self, app, settings):
        super().__init__(application=app)

        self.connect("close-request", self.on_close_request)
        self.backward.connect("clicked", self.on_backward)
        self.forward.connect("clicked", self.on_forward)
        self.calendar_menu.connect("show", self.on_calendar_activate)
        self.setup_calendar()
        self.setup_actions()
        self.backend = Backend(
            Path(GLib.get_user_data_dir()) / app.get_application_id() / "journal"
        )
        self.settings = settings

        self.change_day(datetime.date.today())
        self.page.focus()
        # Add CSS
        css = Gtk.CssProvider()
        css.load_from_data(resource_string(__name__, "css/main.css"))
        Gtk.StyleContext().add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        self.present()

    def setup_actions(self):
        """initialize action handlers"""
        self.set_action("stats", lambda *_: StatsModal(self))
        self.set_action("settings", lambda *_: SettingsModal(self))
        self.set_action("about", lambda *_: AboutModal(self))
        self.set_action("search", lambda *_: SearchModal(self))
        self.set_action("insert_line", lambda *_: self.page.insert_line())
        self.set_action("insert_header", lambda *_: self.page.insert_header())
        self.set_action("insert_code", lambda *_: self.page.insert_code())

    def setup_calendar(self):
        self.calendar.connect("day-selected", self.on_calendar_select)
        # Update the calendar when the displayed month changes
        for signal in ("next-month", "next-year", "prev-month", "prev-year"):
            self.calendar.connect(signal, self.update_calendar)

    def set_action(self, name, handler):
        """Connect an action"""
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", handler)
        self.add_action(action)

    def on_close_request(self, *_):
        """Ensure journal is saved before closing"""
        try:
            return not self.page.save()
        except Exception as e:
            ErrorDialog(self, str(e))
            return True  # Cancel the close request

    def change_day(self, date):
        """Set which day to show"""
        if self.page and not self.page.save():
            return False
        page = JournalPage(self.backend, date)
        self.set_child(page)
        self.page = page
        date_format = self.settings.get("date_format") or "%Y-%m-%d"
        self.set_title("Journal: " + date.strftime(date_format))
        return True

    def on_backward(self, *_):
        self.change_day(self.page.date - datetime.timedelta(days=1))

    def on_forward(self, *_):
        self.change_day(self.page.date + datetime.timedelta(days=1))

    def on_calendar_activate(self, *_):
        """Sync calendar to current date"""
        self.calendar.select_day(
            GLib.DateTime(GLib.TimeZone.new_utc(), *self.page.date.timetuple()[:6])
        )
        self.update_calendar()

    def on_calendar_select(self, *_):
        self.change_day(datetime.date(*self.calendar.get_date().get_ymd()))
        self.update_calendar()

    def update_calendar(self, *_):
        """Reload edited day indicators"""
        # Hacky workaround because Gtk marks are a terrible system
        grid = self.calendar.get_last_child()
        month_offset = -1
        row = 1
        date = self.calendar.get_date()
        year, month, _day = date.get_ymd()
        # Iterate over the rows of the calendar
        while grid.get_child_at(1, row):
            for x in range(1, 8):
                child = grid.get_child_at(x, row)
                if int(child.has_css_class("other-month")) != month_offset % 2:
                    month_offset += 1
                day = int(child.get_label())
                if self.backend.get_day(
                    datetime.date(
                        year - ((month + month_offset - 1) // 12),
                        (month + month_offset - 1) % 12 + 1,
                        day,
                    )
                ):
                    child.add_css_class("edited")
                else:
                    child.remove_css_class("edited")
            row += 1


@templated
class AltGui(Gtk.ApplicationWindow):
    __gtype_name__ = "AltGui"
    backward = Gtk.Template.Child("backward")
    forward = Gtk.Template.Child("forward")
    calendar = Gtk.Template.Child("calendar")
    pane = Gtk.Template.Child("pane")
    box = Gtk.Template.Child("box")
    search = Gtk.Template.Child("search")
    stack = Gtk.Template.Child("stack")
    search_scroller = Gtk.Template.Child("search_scroller")
    page = None

    def __init__(self, app, settings):
        Gtk.ApplicationWindow.__init__(self, application=app)

        self.connect("close-request", self.on_close_request)
        self.backward.connect("clicked", self.on_backward)
        self.forward.connect("clicked", self.on_forward)
        self.calendar.connect("day-selected", self.on_calendar_select)
        self.search.connect("changed", self.on_search_input)
        MainWindow.setup_actions(self)
        MainWindow.setup_calendar(self)
        self.backend = Backend(
            Path(GLib.get_user_data_dir()) / app.get_application_id() / "journal"
        )
        self.settings = settings
        self.cloud = WordCloud(press_callback=self.search.set_text)

        self.change_day(datetime.date.today())
        self.page.focus()
        MainWindow.on_calendar_activate(self)
        self.update_cloud()
        self.stack.add_child(self.cloud)
        self.stack.set_visible_child(self.cloud)
        # Add CSS
        css = Gtk.CssProvider()
        css.load_from_data(resource_string(__name__, "css/main.css"))
        Gtk.StyleContext().add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        self.present()

    # Reuse functions from MainWindow
    on_close_request = MainWindow.on_close_request
    on_calendar_select = MainWindow.on_calendar_select
    set_action = MainWindow.set_action
    update_calendar = MainWindow.update_calendar

    def on_backward(self, *_):
        MainWindow.on_backward(self)
        MainWindow.on_calendar_activate(self)

    def on_forward(self, *_):
        MainWindow.on_forward(self)
        MainWindow.on_calendar_activate(self)

    def change_day(self, date):
        if self.page and not self.page.save():
            return False
        page = JournalPage(self.backend, date)
        self.pane.set_end_child(page)
        self.page = page
        date_format = self.settings.get("date_format") or "%Y-%m-%d"
        self.set_title(f"Journal: {date.strftime(date_format)}")
        self.update_cloud()
        return True

    def update_cloud(self):
        exclude = set(self.settings.get("word_cloud_exclusions"))
        word_dict = {}
        for day in self.backend.get_edited_days():
            for word in self.backend.get_day(day).split():
                word = strip_non_letters(word)
                if word and word not in exclude:
                    word_dict.setdefault(word, 0)
                    word_dict[word] += 1
        self.cloud.load(word_dict.items())

    def on_search_input(self, *_):
        text = self.search.get_text()
        if not text:
            self.stack.set_visible_child(self.cloud)
            return
        results_box = Gtk.Box(orientation=1, vexpand=True)
        for result in self.backend.search(text):
            results_box.append(SearchResult(self, *result))
        self.search_scroller.set_child(results_box)
        self.stack.set_visible_child(self.search_scroller)


if __name__ == "__main__":
    main()
