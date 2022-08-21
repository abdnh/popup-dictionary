from dataclasses import dataclass
from typing import Optional, Union

from anki.notes import NoteId
from aqt import mw
from aqt.browser.previewer import Previewer
from aqt.qt import QApplication
from aqt.reviewer import Reviewer
from aqt.webview import AnkiWebView


@dataclass
class CardViewContext:
    context: Union[Reviewer, Previewer]
    web: AnkiWebView
    nid: Optional[NoteId]

def get_card_view_context() -> CardViewContext:
    window = QApplication.activeWindow()
    nid = None
    if isinstance(window, Previewer):
        context = window
        web = window._web # pylint: disable=protected-access
        card = window.card()
        if card:
            nid = card.note().id
    else:
        context = mw.reviewer
        web = mw.reviewer.web
        card = mw.reviewer.card
        if card:
            nid = card.note().id
    return CardViewContext(context, web, nid)
