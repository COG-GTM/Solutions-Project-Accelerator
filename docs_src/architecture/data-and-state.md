# Data and state

SPA keeps everything on the local disk. There is no application server and no
shared store, so "where is the data?" always has a filesystem answer.

---

## Where state lives

| State | Location | Format |
| --- | --- | --- |
| Application settings and window layout | `temp/config.ini` | INI |
| Application log | `temp/logfile.log` | Rotating text log, 10 MB × 6 |
| Project contents | `projects/<name>/database/database.json` | TinyDB JSON |
| Project name, description, version | `projects/<name>/project.ini` | INI |
| Source documents | `projects/<name>/drawings/`, `projects/<name>/images/` | Copied in, named by UUID |
| OpenAI API key | DPAPI-encrypted blob, `bin/logic_secret_store.py` | Windows DPAPI |
| Deployment settings | `.env`, loaded by `logic_env_file.load_env_file()` | Environment variables |
| ACM project data | SQL Server, via `logic_acm_data_handler.py` | External database |

Documents are copied into the project and renamed to a UUID. The original
filename survives in the `documents` table, not on disk, so moving or renaming
the source file afterwards does not break the project.

---

## Application settings

`logic_config.Config` wraps `configparser`. The file is always
`<app dir>/temp/config.ini`, resolved from `__main__.__file__` so the dev tree
and the frozen build behave the same way.

The pattern throughout the class is a private default, a section name, and a
getter/setter pair:

```python
self.__default_geometry = '1269x779+256+89'
# ... get_win_geometry() / set_win_geometry() read and write [Window] Geometry
```

Adding a setting means adding the default and the accessor pair here, then a
control in `gui_settings.py`. Notable sections: `[Window]` (geometry, state,
sash positions), `[SQL]` (the ACM connection string), the OCR and scanning
options, and the HMI defaults (display size, line widths and colours, and the
ACM library versions such as `DEFAULT_ACM_HMI_TEMPLATE`).

!!! warning "Secrets do not go in `config.ini`"
    The OpenAI API key never passes through `Config`. `logic_secret_store.py`
    encrypts it with the Windows Data Protection API
    (`win32crypt.CryptProtectData`, user plus machine scope) and writes the
    blob separately. `gui_settings.py` only ever shows a placeholder for a key
    that is already stored.

    The ACM SQL Server password is handled the same way: `Config.set_connection_string`
    keeps only the non-secret part of the connection string in `[SQL]` and writes
    the `PWD` value to `temp/sql_password.dat` through `logic_secret_store`;
    `get_connection_string` adds it back in memory. A plaintext `PWD=` left in
    `config.ini` by an older version is moved out on first read. Log the
    connection string only through `logic_connection_string.redact_connection_string`,
    which drops the `PWD` attribute.

---

## The project database

Each project gets a `Database` instance from `logic_internal_database.py`,
backed by TinyDB:

```python
self.__db = TinyDB(self.__dir + '/database.json',
                   storage=CachingMiddleware(JSONStorage))
```

`CachingMiddleware` is what makes it usable. Scanning writes thousands of
records, and writing straight through to JSON would rewrite the whole file each
time. Instead, writes land in memory and a `threading.Timer` flushes five
seconds after the last one; every write resets the timer. A read/write lock
guards concurrent access, and `close_db` is registered with `atexit` so a flush
still happens if the window is closed with work pending.

The practical consequence: **the JSON on disk lags the in-memory state by up to
five seconds.** Do not read `database.json` from outside the app and expect it
to be current, and do not kill the process to "cancel" an operation.

### Tables

| Table | Holds |
| --- | --- |
| `settings` | Project-level settings. This is the default table. |
| `documents` | The documents added to the project. |
| `rois` | Regions of interest drawn on those documents. |
| `control_modules` | Process objects. |
| `control_modules_graphic_templates` | The templates used to find them. |
| `linked_graphic_pairs` | Graphic-to-object pairings. |
| `static_graphics` | Extracted static graphics. |
| `static_graphics_graphic_templates` | Their templates. |
| `displays` | HMI displays. |
| `displays_roi_to_page_link` | Page-link regions on a display. |
| `hmi_displays_graphic_templates` | Templates used for page-link scanning. |
| `unapproved_text_links` | Text links the engine proposed, awaiting review. |
| `approved_text_links` | Links the user accepted. |
| `rejected_text_links` | Links the user rejected. |
| `linked_text_regexes` | User-defined regexes for text linking. |
| `object_assignment_regexes` | Regexes that assign objects to types. |
| `build_hmi_displays` | Build-time state for display generation. |
| `tables_already_processed_by_llm` | Guard against re-processing tables. |
| `llm_library_prompts` | Prompts per ACM library. |

The three text-link tables are a review queue, not three kinds of link. Nothing
the language model proposes is ever written to `approved_text_links` directly.
A human moves it there.

### Change subscriptions

Views register for updates instead of polling, for example
`subscribe_linked_text_regex_table(func)` and
`subscribe_object_assignment_regex_table(func)`. The `Database` instance keeps
the callback lists and fires them after the relevant write, so whichever code
performed the write does not need to know which views are open.

---

## Data models

`bin/data_models.py` holds the dataclasses that cross layer boundaries. They
are not an ORM, because TinyDB stores plain dictionaries, so each one carries
`to_dict()` and `from_dict()` and converts at the database edge.

| Model | Represents |
| --- | --- |
| `Document`, `DocumentType` | A document in the project, with `is_pdf()` / `is_image()` / `is_excel()` helpers. |
| `RegionOfInterest` | A bounding box, with derived `min_x`, `max_x`, `center`, `width`, `height`. |
| `CharacterData` | One OCR character and its box. Frozen, so OCR output is never mutated in place. |
| `TextLocation` | An ordered run of `CharacterData`, with substring and whitespace helpers. |
| `LinkedGraphic` | A detected graphic, its ROI, its text locations, and its `TemplateFlip` / `TemplateRotate`. |
| `ControlModule` | A process object and its linked graphics, primary and secondary. |

`CharacterData` being frozen matters more than it looks: the OCR correction
stages in `logic_linked_graphic_scanner.py` rebuild character lists rather than
edit them, which keeps the original recognition result available for
comparison.
