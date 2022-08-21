# -*- coding: utf-8 -*-

# Pop-up Dictionary Add-on for Anki
#
# Copyright (C)  2018-2021 Aristotelis P. <https://glutanimate.com/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version, with the additions
# listed at the end of the license file that accompanied this program.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# NOTE: This program is subject to certain additional terms pursuant to
# Section 7 of the GNU Affero General Public License.  You should have
# received a copy of these additional terms immediately following the
# terms and conditions of the GNU Affero General Public License that
# accompanied this program.
#
# If not, please request a copy through one of the means of contact
# listed here: <https://glutanimate.com/contact/>.
#
# Any modifications to this file must keep this entire header intact.

"""
Modifications to Anki's Reviewer
"""

import json
from typing import TYPE_CHECKING, Any, Optional, Tuple, Union

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QMenu, QShortcut

from anki.hooks import wrap
from aqt import mw
from aqt.qt import QWidget
from aqt.reviewer import Reviewer
from aqt.browser.previewer import Previewer

from .browser import browse_to_nid
from .config import config
from .results import PYCMD_IDENTIFIER, get_content_for
from .web import popup_integrator
from .utils import get_card_view_context

if TYPE_CHECKING:  # 2.1.22+
    from aqt.webview import AnkiWebView, WebContent


# UI interaction ####


def setup_shortcuts(widget: QWidget):
    QShortcut(  # type: ignore
        QKeySequence(config["local"]["generalHotkey"]),
        widget,
        activated=on_lookup_triggered,
    )

def on_lookup_triggered(*args):
    card_view_context = get_card_view_context()
    if isinstance(card_view_context.context, Reviewer) and mw.state != "review":
        return
    card_view_context.web.eval("invokeTooltipAtSelectedElm();")


def on_webview_will_show_context_menu(webview: "AnkiWebView", menu: QMenu):
    # shaky heuristic to determine which web view we are in
    if hasattr(webview, "title"):
        if webview.title != "main webview":
            return

    if mw.state != "review" or not webview.selectedText():
        return

    action = menu.addAction("Look up in Pop-up Dictionary...")
    action.setShortcut(config["local"]["generalHotkey"])
    action.triggered.connect(on_lookup_triggered)


# JS <-> PY communication ####


def webview_message_handler(message: str) -> Optional[str]:
    cmd, arg = message.split(":", 1)
    subcmd = cmd.replace(PYCMD_IDENTIFIER, "")

    if subcmd == "Browse":
        (cmd, arg) = message.split(":", 1)
        if not arg:
            return None
        browse_to_nid(int(arg))
    elif subcmd == "Lookup":
        (cmd, payload) = message.split(":", 1)
        term, ignore_nid = json.loads(payload)
        term = term.strip()
        return get_content_for(term, ignore_nid)
    else:
        print(f"Unrecognized pop-up dictionary pycmd identifier {subcmd}")

    return None


def on_webview_will_set_content(
    web_content: "WebContent", context: Union[Reviewer, Any]
):
    if not isinstance(context, (Reviewer, Previewer)):
        return

    # Appending to body rather than using header. Not best practice, but let's stay
    # on the safe side
    web_content.body += popup_integrator

def on_card_will_show(text, card, kind):
    """Make ignoreMinLength config data accessible to web"""
    ign = config["local"]["ignoreMinLength"]
    return text + "<script>var ignoreLength = \"{}\"</script>".format(ign)

def on_webview_did_receive_js_message(
    handled: Tuple[bool, Any], message: str, context: Union[Reviewer, Any]
):
    if not isinstance(context, (Reviewer, Previewer)):
        return handled

    if not message.startswith(PYCMD_IDENTIFIER):
        return handled

    callback_value = webview_message_handler(message)

    return (True, callback_value)


# Hook into Anki ####

# ensure that we only patch once on first profile load
_reviewer_patched: bool = False


def patch_reviewer():
    global _reviewer_patched

    if _reviewer_patched:
        return

    from aqt.gui_hooks import (
        webview_will_set_content,
        webview_did_receive_js_message,
        card_will_show,
    )

    webview_will_set_content.append(on_webview_will_set_content)
    webview_did_receive_js_message.append(on_webview_did_receive_js_message)
    card_will_show.append(on_card_will_show)

    _reviewer_patched = True


def initialize_reviewer():
    """Delay patching reviewer to counteract bad practices in other add-ons that
    overwrite revHtml and _linkHandler in their entirety"""

    from aqt.gui_hooks import profile_did_open, webview_will_show_context_menu

    profile_did_open.append(patch_reviewer)
    webview_will_show_context_menu.append(on_webview_will_show_context_menu)

    setup_shortcuts(mw)
    Previewer.__init__ = wrap(Previewer.__init__, lambda self, *args, **kwargs: setup_shortcuts(self))
