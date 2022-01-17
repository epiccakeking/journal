import traceback

from gi.repository import Gtk

from epiccakeking_journal.utilities import templated
from epiccakeking_journal.widgets import SearchResult, SetManager


@templated
class SearchModal(Gtk.Dialog):
    __gtype_name__ = 'SearchModal'
    search = Gtk.Template.Child('search')
    results_scroller = Gtk.Template.Child('results_scroller')

    def __init__(self, parent):
        super().__init__(modal=True, transient_for=parent)
        self.parent = parent
        self.search.connect('activate', self.on_search)
        self.present()

    def on_search(self, *_):
        result_box = Gtk.Box(orientation=1, vexpand=True)
        for result in self.parent.backend.search(self.search.get_text()):
            result_box.append(SearchResult(self, *result))
        self.results_scroller.set_child(result_box)

    def change_day(self, date):
        self.parent.change_day(date)
        self.close()


class AboutModal(Gtk.AboutDialog):
    def __init__(self, parent):
        super().__init__(
            authors=(
                'epiccakeking',
            ),
            copyright='Copyright 2022 epiccakeking',
            license_type='GTK_LICENSE_GPL_3_0',
            program_name='Journal',
        )
        self.set_logo_icon_name('io.github.epiccakeking.Journal')
        self.set_modal(True)
        self.set_transient_for(parent)
        self.present()


@templated
class SettingsModal(Gtk.Window):
    __gtype_name__ = 'SettingsModal'
    date_format = Gtk.Template.Child('date_format')
    alt_gui = Gtk.Template.Child('alt_gui')
    stack = Gtk.Template.Child('stack')
    back = Gtk.Template.Child('back')
    word_cloud_exclusions_button = Gtk.Template.Child('word_cloud_exclusions_button')

    def __init__(self, parent):
        super().__init__()
        self.set_modal(True)
        self.set_transient_for(parent)
        self.parent = parent
        self.page_history = []
        self.date_format.set_text(self.parent.settings.get('date_format'))
        self.alt_gui.set_active(self.parent.settings.get('alt_gui'))
        self.alt_gui.set_active(self.parent.settings.get('alt_gui'))
        self.word_cloud_exclusions = self.parent.settings.get('word_cloud_exclusions')
        self.connect('close-request', self.on_close_request)
        self.back.connect('clicked', self.back_stack)
        self.word_cloud_exclusions_button.connect('clicked', lambda *_: self.change_page(
            SetManager(self.word_cloud_exclusions, lambda w: self.set_word_cloud_exclusions(w.get_list()))
        ))
        self.present()

    def on_close_request(self, *_):
        try:
            self.save_changes()
        except Exception:
            traceback.print_exc()
            return True

    def save_changes(self):
        self.parent.settings.set(
            date_format=self.date_format.get_text(),
            alt_gui=self.alt_gui.get_active(),
            word_cloud_exclusions=self.word_cloud_exclusions,
        )

    def back_stack(self, *_):
        prev_page=self.page_history.pop()
        self.back.set_visible(bool(self.page_history))
        current_page=self.stack.get_visible_child()
        self.stack.set_visible_child(prev_page)
        self.stack.remove(current_page)

    def change_page(self, widget):
        self.stack.add_named(widget)
        self.page_history.append(self.stack.get_visible_child())
        self.stack.set_visible_child(widget)
        self.back.set_visible(True)

    def set_word_cloud_exclusions(self, exclusions):
        self.word_cloud_exclusions = exclusions
