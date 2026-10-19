""" Modal dialog that lets the user pick a FactoryTalk View SE
    application to hand off to ``SEAddComponent.exe`` during the
    "Build HMI → View Designer" flow.

    Discovery of the candidate list is delegated to
    :mod:`bin.logic_ftview_apps`. This module is a thin Tk view: it
    populates a searchable Treeview, tracks the selection, and returns
    either the chosen ``{'name', 'app_type'}`` dict or ``None`` when the
    user cancels / closes the window.

    Consumer contract::

        picker = FTViewAppPicker(
            parent,
            default_name='Demo_FTview',
            default_app_type='Distributed',
        )
        result = picker.get_result()
        if result is None:
            # user cancelled — caller must skip SEAddComponent
            ...
        else:
            name = result['name']
            app_type = result['app_type']   # 'Distributed' / 'Stand-alone' / 'SE Station'
"""

from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List

try:
    from bin.logic_ftview_apps import (
        discover_ftview_applications,
        APP_TYPE_DISTRIBUTED,
        APP_TYPE_STAND_ALONE,
        APP_TYPE_SE_STATION,
    )
except ImportError:
    from logic_ftview_apps import (            # type: ignore[no-redef]
        discover_ftview_applications,
        APP_TYPE_DISTRIBUTED,
        APP_TYPE_STAND_ALONE,
        APP_TYPE_SE_STATION,
    )


_APP_TYPE_OPTIONS = (APP_TYPE_DISTRIBUTED, APP_TYPE_STAND_ALONE, APP_TYPE_SE_STATION)

# Sentinel value for the type-filter combobox meaning "show every type".
_TYPE_FILTER_ALL = 'All'


class FTViewAppPicker:
    """ Modal FTView SE application picker. Blocks until the user
        confirms or cancels — call :meth:`get_result` after construction
        returns to read the choice. """

    def __init__(self,
                 parent: tk.Misc,
                 default_name: str = '',
                 default_app_type: str = APP_TYPE_DISTRIBUTED):
        self.__parent = parent
        self.__default_name = (default_name or '').strip()
        self.__default_app_type = (default_app_type or APP_TYPE_DISTRIBUTED).strip()
        if self.__default_app_type not in _APP_TYPE_OPTIONS:
            self.__default_app_type = APP_TYPE_DISTRIBUTED

        # The full discovered list, plus the currently-visible subset
        # after filtering. Cached so keystroke filtering is a cheap
        # in-memory scan rather than a re-discovery. Index the full
        # list by lower-cased name so __on_ok can recover the type of a
        # discovered app even when the row isn't currently selected
        # (e.g. the user typed the name manually or filtered it out).
        self.__all_apps: List[Dict[str, str]] = discover_ftview_applications()
        self.__by_name_lower: Dict[str, Dict[str, str]] = {
            a['name'].lower(): a for a in self.__all_apps
        }
        self.__visible_apps: List[Dict[str, str]] = list(self.__all_apps)

        self.__result: Optional[Dict[str, str]] = None

        self.__form = tk.Toplevel(parent)
        self.__setup_form()

        # Standard modal dance used elsewhere in this codebase
        # (see gui_db_connection.db_conntection_form / gui_settings.settings).
        self.__form.wait_visibility()
        self.__form.grab_set()
        self.__form.transient(parent if isinstance(parent, (tk.Tk, tk.Toplevel)) else None)
        self.__form.wait_window()

    # ── public API ──────────────────────────────────────────────────────

    def get_result(self) -> Optional[Dict[str, str]]:
        """ Return the picked application as ``{'name', 'app_type'}``, or
            ``None`` if the user cancelled / closed the dialog. """
        return self.__result

    # ── form construction ──────────────────────────────────────────────

    def __setup_form(self) -> None:
        self.__form.title("Select FactoryTalk View SE Application")
        self.__form.geometry('640x520')
        self.__form.minsize(560, 520)
        try:
            this_dir = os.path.dirname(os.path.realpath(__file__))
            self.__form.iconbitmap(os.path.join(this_dir, 'logo.ico'))
        except tk.TclError:
            # Icon missing (dev environments, packaged tests) — ignore.
            pass

        # Cancel-on-close so the caller sees the same intent as clicking
        # the Cancel button.
        self.__form.protocol("WM_DELETE_WINDOW", self.__on_cancel)

        outer = ttk.Frame(self.__form, padding=(10, 10, 10, 10))
        outer.pack(fill=tk.BOTH, expand=True)

        # ── header text ────────────────────────────────────────────────
        header = ttk.Label(
            outer,
            text=(
                "Choose the FactoryTalk View SE application."
            ),
            wraplength=610,
            justify=tk.LEFT,
        )
        header.pack(fill=tk.X, pady=(0, 8))

        # ── filter row (name substring + type filter) ──────────────────
        filter_row = ttk.Frame(outer)
        filter_row.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(filter_row, text="Filter:").pack(side=tk.LEFT)
        self.__search_var = tk.StringVar()
        self.__search_var.trace_add('write', self.__on_filters_changed)
        search_entry = ttk.Entry(filter_row, textvariable=self.__search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))

        ttk.Label(filter_row, text="Type:").pack(side=tk.LEFT)
        self.__type_filter_var = tk.StringVar(value=_TYPE_FILTER_ALL)
        self.__type_filter_var.trace_add('write', self.__on_filters_changed)
        self.__type_filter_cb = ttk.Combobox(
            filter_row,
            state='readonly',
            textvariable=self.__type_filter_var,
            values=[_TYPE_FILTER_ALL, *_APP_TYPE_OPTIONS],
            width=14,
        )
        self.__type_filter_cb.pack(side=tk.LEFT, padx=(6, 0))

        # ── treeview + scrollbar ───────────────────────────────────────
        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('name', 'type', 'source')
        self.__tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show='headings',
            selectmode='browse',
            height=10,
        )
        self.__tree.heading('name', text='Application name')
        self.__tree.heading('type', text='Type')
        self.__tree.heading('source', text='Source')
        self.__tree.column('name', width=220, anchor=tk.W, stretch=True)
        self.__tree.column('type', width=110, anchor=tk.W, stretch=False)
        self.__tree.column('source', width=280, anchor=tk.W, stretch=True)
        self.__tree.bind('<<TreeviewSelect>>', self.__on_tree_select)
        self.__tree.bind('<Double-1>', lambda _e: self.__on_ok())

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.__tree.yview)
        self.__tree.configure(yscrollcommand=vsb.set)
        self.__tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # ── manual override ────────────────────────────────────────────
        # The type is not editable here — it is derived from the picked
        # row when the name matches a discovered app, otherwise it falls
        # back to the SEAddComponent default set in Settings.
        manual_row = ttk.LabelFrame(outer, text="Selected application")
        manual_row.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(manual_row, text="Name:")\
            .grid(row=0, column=0, sticky=tk.W, padx=(6, 4), pady=(6, 6))
        self.__name_var = tk.StringVar(value=self.__default_name)
        self.__name_entry = ttk.Entry(manual_row, textvariable=self.__name_var, width=38)
        self.__name_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 6), pady=(6, 6))
        manual_row.columnconfigure(1, weight=1)

        # ── status line ────────────────────────────────────────────────
        self.__status_var = tk.StringVar()
        status = ttk.Label(outer, textvariable=self.__status_var, foreground='#555')
        status.pack(fill=tk.X, pady=(6, 0))

        # ── OK / Cancel buttons ────────────────────────────────────────
        btn_row = ttk.Frame(outer)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_row, text='Cancel', command=self.__on_cancel, width=10)\
            .pack(side=tk.RIGHT)
        ttk.Button(btn_row, text='OK', command=self.__on_ok, width=10)\
            .pack(side=tk.RIGHT, padx=(0, 6))

        # Populate the tree and pre-select the default row if present.
        self.__refresh_tree()
        self.__select_default_row()
        self.__update_status()
        search_entry.focus_set()

    # ── event handlers ─────────────────────────────────────────────────

    def __on_filters_changed(self, *_args) -> None:
        needle = self.__search_var.get().strip().lower()
        type_filter = self.__type_filter_var.get().strip()

        def _matches(app: Dict[str, str]) -> bool:
            if needle and needle not in app['name'].lower():
                return False
            if type_filter and type_filter != _TYPE_FILTER_ALL \
                    and app['app_type'] != type_filter:
                return False
            return True

        self.__visible_apps = [a for a in self.__all_apps if _matches(a)]
        self.__refresh_tree()
        self.__update_status()

    def __on_tree_select(self, _event=None) -> None:
        sel = self.__tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except ValueError:
            return
        if 0 <= idx < len(self.__visible_apps):
            app = self.__visible_apps[idx]
            self.__name_var.set(app['name'])

    def __on_ok(self) -> None:
        name = self.__name_var.get().strip()
        if not name:
            self.__status_var.set(
                "Please pick an application from the list or type its name."
            )
            self.__name_entry.focus_set()
            return

        # Prefer the discovered type when the typed name matches a known
        # application (case-insensitive); otherwise fall back to the
        # default type supplied by the caller (i.e. the SEAddComponent
        # default configured in Settings). This means manual entries for
        # remote servers still get a sensible type without asking the
        # user for extra clicks.
        discovered = self.__by_name_lower.get(name.lower())
        if discovered is not None:
            app_type = discovered['app_type']
        else:
            app_type = self.__default_app_type

        self.__result = {'name': name, 'app_type': app_type}
        logging.info(
            f"FTView SE picker: user selected name={name!r} type={app_type!r}"
        )
        self.__form.destroy()

    def __on_cancel(self) -> None:
        self.__result = None
        logging.info("FTView SE picker: user cancelled — SEAddComponent will be skipped.")
        self.__form.destroy()

    # ── helpers ────────────────────────────────────────────────────────

    def __refresh_tree(self) -> None:
        # Repopulate — iid is the index into __visible_apps so we can
        # round-trip selection → dict lookup without extra bookkeeping.
        for row_id in self.__tree.get_children():
            self.__tree.delete(row_id)
        for idx, app in enumerate(self.__visible_apps):
            self.__tree.insert(
                '',
                tk.END,
                iid=str(idx),
                values=(app['name'], app['app_type'], app['source']),
            )

    def __select_default_row(self) -> None:
        if not self.__default_name:
            return
        target = self.__default_name.lower()
        for idx, app in enumerate(self.__visible_apps):
            if app['name'].lower() == target:
                iid = str(idx)
                self.__tree.selection_set(iid)
                self.__tree.focus(iid)
                self.__tree.see(iid)
                break

    def __update_status(self) -> None:
        total = len(self.__all_apps)
        shown = len(self.__visible_apps)
        if total == 0:
            self.__status_var.set(
                "No FactoryTalk View SE applications were auto-discovered "
                "on this machine — enter the name manually below."
            )
        elif shown == total:
            self.__status_var.set(f"{total} application(s) discovered.")
        else:
            self.__status_var.set(f"Showing {shown} of {total} application(s).")
