"""Explicit, live UI translations; screenshot pixels and user data stay untouched."""
import json
import logging
from pathlib import Path
import tempfile
import weakref

from translations import ENGLISH


LANGUAGES = {"pl": "Polski", "en": "English"}


class Message(str):
    def __new__(cls, source, values=None, limit=None):
        values = values or {}
        instance = super().__new__(cls, source.format(**values) if values else source)
        instance.source, instance.values, instance.limit = source, values, limit
        return instance

    def clipped(self, limit):
        return Message(self.source, self.values, limit)


def msg(source, **values):
    if isinstance(source, Message) and not values:
        return source
    return Message(source, values)


def error_message(error):
    return error.args[0] if error.args and isinstance(error.args[0], Message) else str(error)


def settings_path():
    from app_storage import data_directory
    return data_directory() / "settings.json"


def load_language(path=None):
    try:
        path = path if path is not None else settings_path()
        if path.stat().st_size > 4096:
            return "pl"
        language = json.loads(path.read_text(encoding="utf-8")).get("language")
        return language if language in LANGUAGES else "pl"
    except (OSError, ValueError, AttributeError, TypeError):
        return "pl"


def save_language(language, path=None):
    if language not in LANGUAGES:
        raise ValueError("Unsupported language")
    path = path if path is not None else settings_path()
    # A tiny preferences file, separate from disposable capture sessions.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".settings-", suffix=".tmp",
                                         dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(json.dumps({"language": language}) + "\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class LocalizedUI:
    def __init__(self, language="pl"):
        if language not in LANGUAGES:
            raise ValueError("Unsupported language")
        self.language = language
        self._bindings = weakref.WeakKeyDictionary()

    def render(self, value):
        if isinstance(value, Message):
            template = ENGLISH.get(value.source, value.source) if self.language == "en" else value.source
            # Only explicitly marked messages are translated. Filenames,
            # window titles, paths and error details passed as values are data.
            values = {key: self.render(item) if isinstance(item, Message) else item
                      for key, item in value.values.items()}
            result = template.format(**values) if values else template
            return result[:value.limit] + "…" if value.limit and len(result) > value.limit else result
        return ENGLISH.get(value, value) if self.language == "en" and isinstance(value, str) else value

    def source_value(self, value, choices):
        for source in choices:
            if value in (source, ENGLISH.get(source)):
                return source
        raise ValueError("Unknown translated choice")

    def _remember(self, widget, kind, source):
        self._bindings.setdefault(widget, {})[kind] = source

    def widget(self, factory, *args, **options):
        source = options.get("text")
        arguments = list(args)
        name = factory.__name__
        if name == "RoundedButton" and len(arguments) > 1:
            source = arguments[1]
            arguments[1] = self.render(source)
        if "text" in options:
            options["text"] = self.render(source)
        card_sources = None
        if name == "ModeCard":
            card_sources = (arguments[2], arguments[3])
            arguments[2:4] = [self.render(value) for value in card_sources]
        widget = factory(*arguments, **options)
        if source is not None:
            self._remember(widget, "text", source)
        if card_sources:
            self._remember(widget, "card", card_sources)
        return widget

    def set(self, widget, **options):
        if "text" in options:
            source = options["text"]
            self._remember(widget, "text", source)
            options["text"] = self.render(source)
        widget.configure(**options)

    def title(self, widget, source):
        self._remember(widget, "title", source)
        widget.title(self.render(source))

    def heading(self, widget, column, source, **options):
        self._remember(widget, ("heading", column), source)
        widget.heading(column, text=self.render(source), **options)

    def body(self, widget, source):
        self._remember(widget, "body", source)
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", self.render(source))
        widget.configure(state="disabled")

    def dialog(self, function, title, message, **options):
        return function(self.render(title), self.render(message), **options)

    def set_language(self, language):
        if language not in LANGUAGES:
            raise ValueError("Unsupported language")
        self.language = language
        for widget, bindings in list(self._bindings.items()):
            if not widget.winfo_exists():
                continue
            for kind, source in bindings.items():
                if kind == "title":
                    widget.title(self.render(source))
                elif kind == "card":
                    widget.title, widget.subtitle = (self.render(value) for value in source)
                    widget._draw()
                elif kind == "body":
                    self.body(widget, source)
                elif isinstance(kind, tuple) and kind[0] == "heading":
                    widget.heading(kind[1], text=self.render(source))
                else:
                    widget.configure(**{kind: self.render(source)})


def remember_language(language):
    try:
        save_language(language)
        return True
    except OSError:
        logging.getLogger(__name__).warning("Could not save language preference", exc_info=True)
        return False
