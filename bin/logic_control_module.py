
from bin.gui_assign_type import assign_object_type_view
from bin.gui_object_parameter_view import object_parameter_view
from bin.gui_subobject_parameter_view import subobject_parameter_view
import threading
from bin.logic_pair_control_modules_graphics import linked_graphic_pairing
import io
import logging
from multiprocessing import Manager, Process
import time
import uuid
from PIL import Image
import copy
import math

import cv2
import numpy as np
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.gui_linked_text_entry_view import linked_text_entry
from bin.logic_internal_database import Database
from bin.gui_config_elements import direction_buttons, radio_buttons
from bin.gui_linked_graphic_view import linked_graphic_view
from os import link, name, replace
from tkinter import messagebox
from bin.gui_link_view import image_text_locations_list_view, image_view
import tkinter as tk
from bin.gui_base64_icons import start_scan, test_on_page
from bin.gui_base64_icons import cw_90_blue, cw_180_blue, cw_270_blue
from bin.gui_base64_icons import cw_90_gray, cw_180_gray, cw_270_gray
from bin.gui_elements import cell_line, custom_label, hover_toggle_button, rounded_image_button, set_active_canvas_screen
from bin.logic_linked_graphic import Linked_Graphic
import pyastar2d

from bin.logic_linked_graphic_scanner import Template_Rotate, Template_Flip

from bin.logic_profile import profile


class Control_Module():
    '''
    A class that represents an object in Application Code Manager (ACM) that is used to control a process. This object 
    has access to the ACM database and can be used to retrieve information about the object, such as its parameters and
    subobjects. It can also be used to retrieve the object's linked graphics and linked text.
    '''

    PRIMARY_GRAPHIC = 'Primary Graphic'
    SECONDARY_GRAPHIC = 'Secondary Graphic'

    PRIMARY_GRAPHIC_TYPE = 'control_module_primary'
    SECONDARY_GRAPHIC_TYPE = 'control_module_secondary'

    def __init__(self, id, name, description, go_to_document_callback, linked_callback, group_id, update_roi_name_callback=None) -> None:
        """
        Initializes an instance of the LogicControlModule class.

        Args:
            id (int): The ID of the logic control module.
            name (str): The name of the logic control module.
            description (str): The description of the logic control module.
            go_to_document_callback (callable): A callback function to navigate to a document.
            linked_callback (callable): A callback function for linked graphics.
            group_id (int): The group ID associated with the logic control module.

        Returns:
            None
        """

        self.id = id
        self.name = name
        self.description = description
        self.assignment_id = None
        self.group_id = group_id # Associated with the CatalogNumber column in the ACM SQL database
        self.__db : Database = None
        self.__done_building_func = []
        self.__update_roi_name_func = update_roi_name_callback
        self.__primary_linked_graphic_view = linked_graphic_view( self.PRIMARY_GRAPHIC,redraw_callback=self.__redraw_config_canvas, 
                                                                    change_callback=self.__linked_graphic_change,
                                                                    goto_callback=self.__go_to_callback,
                                                                    is_primary_linked_graphic=True,
                                                                    result_callback=self.__process_single_primary_result,
                                                                    scanning_done_callback=self.__scanning_done_callback,
                                                                    object_type=self.PRIMARY_GRAPHIC_TYPE)
        
        self.__secondary_linked_graphic_view = linked_graphic_view(self.SECONDARY_GRAPHIC,redraw_callback=self.__redraw_config_canvas, 
                                                                    change_callback=self.__linked_graphic_change,
                                                                    goto_callback=self.__go_to_callback,
                                                                    result_callback=self.__process_single_secondary_result,
                                                                    scanning_done_callback=self.__scanning_done_callback,
                                                                    object_type=self.SECONDARY_GRAPHIC_TYPE)
        self.__object_parameter_screen = object_parameter_view(self.name,self.id
                                                                ,self.description
                                                                ,go_to_callback=self.__go_to_callback)
        self.__subobject_parameter_screen = subobject_parameter_view(self.name,self.id
                                                                ,self.description
                                                                ,go_to_callback=self.__go_to_callback)
        self.__assign_object_screen = assign_object_type_view()
        self.__move_to_roi_func = None
        self.__clear_shown_text_roi_list_func = None
        self.__refresh_rois_func = None 
        self.__get_selected_roi_func = None
        self.__go_to_roi_uid = None 
        self.__go_to_pno = None
        self.__document_selected_text = None
        self.__go_to_document_callback = go_to_document_callback
        self.__linked_callback = linked_callback
        self.__linked_text = {}
        self.__full_page_image = None
        self.__busy_loading_data = False # Used to prevent race conditions when loading data
        self.__primary_poi_dict= {}
        self.__secondary_poi_dict = {}
        self.__poi_linking_path = ""
        self.__path = ''
        self.__pno = -1
        self.__flow_direction = direction_buttons.NONE
        self.__flow_direction_description = None 
        self.__primary_linked_graphic_data = None
        self.__secondary_linked_graphic_data = None
        self.__secondary_linked_graphic_rotation:list[Template_Rotate] = [Template_Rotate.NONE
                                                                ,Template_Rotate.CW_90
                                                                ,Template_Rotate.CW_180
                                                                ,Template_Rotate.CW_270]
        self.__secondary_linked_graphic_view.set_template_rotate(self.__secondary_linked_graphic_rotation)
        self.__remove_background_task_callback_func = None
        self.__new_control_modules = {}
        self.__new_control_modules_tagnames = {}
        self.__secondary_scan_started = False
        self.__primary_graphic_scanning_done = False
        self.__secondary_graphic_scanning_done = False
        self.__add_secondary_progress_callback_func = None 
        self.__scanning_started = False
        self.__draw_roi_trigger_func = None
        self.__primary_scanning_count = 0
        self.__secondary_scanning_count = 0
        self.__primary_scan_times = []
        self.__secondary_scan_times = []
        self.__send_document_selected_text_func = None
        self.__primary_single_results_being_processed = []
        self.__secondary_single_results_being_processed = []
        self.__new_overlapping_control_modules_id = set()
        self.__old_overlapping_control_modules_id = set()
        self.__filtered_new_control_modules_id = []
        self.__subobject_parameter_view_setup = False


    def draw_roi_trigger(self, parent_cell_object):
        """
        Activates the manual Draw ROI tool. The parent cell object is forwarded
        so callers that historically supplied a template source still receive
        it, but the tool no longer performs feature matching against it.

        Returns:
            None
        """
        if self.__draw_roi_trigger_func:
            self.__draw_roi_trigger_func(parent_cell_object)
        else:
            logging.warning("No draw ROI callback function set.")
            raise ValueError("No document selected to draw ROI.")


    def get_primary_linked_graphic_data(self):
        """ Public accessor for the primary linked graphic dict (roi, text_location_dict,
        pdf_zoom_scale, template metadata). Returns None when no primary graphic is set. """
        try:
            return self.__primary_linked_graphic_view.get_linked_graphic_data()
        except Exception:
            return None


    def instantiate_manual_placement(self, dest_path, dest_pno, roi_bbox,
                                     rotation=None, flip=None, scale=1.0,
                                     text_roi_polygons=None, wire_kwargs=None):
        """ Create a new linked-graphic copy at the caller-supplied location without
        running feature matching.

        Arguments mirror the scanner path but are user-supplied:
            dest_path:  destination document path (image-space same as source)
            dest_pno:   destination page index
            roi_bbox:   (x1, y1, x2, y2) axis-aligned bbox in the destination doc's
                        image coords
            rotation:   Template_Rotate enum member (NONE / CW_90 / CW_180 / CW_270)
            flip:       Template_Flip enum member (NONE / VERTICALLY / HORIZONTALLY /
                        VERTICALLY_HORIZONTALLY)
            scale:      uniform template_to_match_ratio (float)
            text_roi_polygons: optional list of transformed text-region polygons in
                        unscaled destination-doc coords, one per entry in the
                        source's `text_location_dict`. When provided, the manually
                        placed module's text regions are re-anchored to these
                        polygons and their `text_dict` values are re-detected on
                        the destination page (via OCR / PDF text extraction), so
                        the new module reflects the drawing's actual characters
                        instead of the source template's.
            wire_kwargs: optional kwargs to wire the selection callbacks before
                        touching the primary linked-graphic view. Needed so the
                        `text_roi_polygons` re-detection can reach the current
                        view's page image + text_in_page providers.

        Returns the newly persisted control-module dict, or None if create_copy
        reported an overlap conflict.
        """
        if rotation is None:
            rotation = Template_Rotate.NONE
        if flip is None:
            flip = Template_Flip.NONE

        # Wire the selection callbacks up-front so the (optional) text re-detection
        # below can reach the current view's `get_full_page_image` +
        # `get_text_on_page` providers even when the last-subscribed cell was a
        # different one.
        if wire_kwargs:
            self.ensure_selection_callbacks_wired(**wire_kwargs)

        # `create_copy` (and its private `__rotate_points` / `__flip_points`
        # helpers) expect raw enum values (a `cv2` rotation constant or `None`),
        # not the enum member itself — the historical scanner path always
        # passed `.value`. Preserve that contract here.
        rotation_value = rotation.value if hasattr(rotation, 'value') else rotation
        flip_value = flip.value if hasattr(flip, 'value') else flip

        # Build `text_locations` from the source's own text_location_dict so the
        # new module gets proper text ROI entries (mask_shape carving + text_dict
        # metadata). Without this, `create_copy(..., [])` returns an empty
        # text_location_dict and the new module has no text links to display or
        # scan against.
        text_locations = self.__build_text_locations_for_manual_placement()

        primary_linked_graphic, source_to_copy_roi_map, overlaps = self.__primary_linked_graphic_view.create_copy(
            dest_path, dest_pno, roi_bbox, text_locations,
            template_to_match_ratio=scale,
            rotation=rotation_value,
            flip=flip_value,
        )
        if overlaps:
            logging.info("Manual Draw ROI placement overlapped an existing graphic; skipped.")
            return None

        # Re-anchor text regions to the caller-supplied polygons and re-detect
        # the text underneath them, so the manual placement reflects the actual
        # drawing (not the source template's characters). Also returns the
        # after-create_copy → after-redetect roi-name map so we can compose it
        # with `source_to_copy_roi_map` when propagating the source's
        # linked_text (Name/parameter entries) to the placement.
        detected_text_chars, copy_to_final_roi_map, detected_by_copy_roi = self.__redetect_manual_placement_text_regions(
            primary_linked_graphic, text_roi_polygons, dest_path, dest_pno
        )

        # Give the placement its own template/mask/display artwork cropped from
        # the destination page; `create_copy` only ever copies the source's paths.
        self.__create_manual_placement_template_images(primary_linked_graphic)

        # The Name links reference the *source's* roi_names, so re-key the
        # detected text by source roi_name before composing the placement name.
        detected_by_source_roi = {
            source_roi: detected_by_copy_roi[copy_roi]
            for source_roi, copy_roi in (source_to_copy_roi_map or {}).items()
            if copy_roi in detected_by_copy_roi
        }

        # Distinguish the manually-placed control module from its source so the
        # tag list / DB doesn't collapse them into one. Without a per-placement
        # name the new module inherits the source's name verbatim.
        placement_name, name_link_indexes = self.__derive_manual_placement_name(
            primary_linked_graphic, detected_text_chars, detected_by_source_roi
        )

        # Compose source→final roi-name map so `linked_text` links propagated
        # from the source point at the placement's freshly-keyed text regions.
        # When the caller did not supply polygons (no redetect ran),
        # `copy_to_final_roi_map` is empty and `source_to_copy_roi_map` is used
        # as-is.
        if copy_to_final_roi_map:
            source_to_final_roi_map = {
                src: copy_to_final_roi_map.get(dst, dst)
                for src, dst in (source_to_copy_roi_map or {}).items()
            }
        else:
            source_to_final_roi_map = dict(source_to_copy_roi_map or {})

        new_linked_text = self.__copy_linked_text_for_manual_placement(
            dest_path, dest_pno, placement_name, source_to_final_roi_map,
            name_link_indexes
        )

        control_module_dict = {
            'id': primary_linked_graphic['roi_uid'],
            'name': placement_name,
            'description': self.description,
            'type': 'Unassigned',
            'path': dest_path,
            'pno': dest_pno,
            'primary_linked_graphic': primary_linked_graphic,
            'secondary_linked_graphic': {},
            'linked_text': new_linked_text,
            'flow_direction': self.__flow_direction,
            'template_rotation': [item.value for item in self.__secondary_linked_graphic_rotation],
        }

        roi_list = self.__db.get_project_document_roi(dest_path)
        self.__setup_roi_in_roi_list(roi_list, dest_pno, primary_linked_graphic)
        self.__db.save_bulk_control_modules([control_module_dict])
        self.__save_page_roi(dest_path, roi_list, False)

        return control_module_dict


    def __build_text_locations_for_manual_placement(self):
        """ Convert the source primary linked graphic's text_location_dict into
        the `text_locations` list shape expected by
        `linked_graphic.create_copy` (`{'roi_name', 'points', 'text_dict'}`).
        `points` must be in scaled (pdf_zoom_scale) coords, but the source's
        stored `text_roi` is in unscaled page coords, so we rescale here.
        """
        try:
            source_data = self.__primary_linked_graphic_view.get_linked_graphic_data() or {}
        except Exception:
            source_data = {}
        source_text_dict = source_data.get('text_location_dict') or {}
        if not source_text_dict:
            return []

        document_type = source_data.get('document_type')
        if document_type == Database.DRAWING:
            zoom_scale = source_data.get('pdf_zoom_scale', 2) or 2
        else:
            zoom_scale = 1

        text_locations = []
        for old_roi_name, entry in source_text_dict.items():
            text_roi = entry.get('text_roi') or []
            if not text_roi:
                continue
            points = [(p[0] * zoom_scale, p[1] * zoom_scale) for p in text_roi]
            text_locations.append({
                'roi_name': old_roi_name,
                'points': points,
                'text_dict': entry.get('text_dict', []),
            })
        return text_locations


    def __derive_manual_placement_name(self, primary_linked_graphic, detected_text_chars=None,
                                       detected_by_source_roi=None):
        """ Produce a per-placement name for the manually-placed control module.

        Prefers rebuilding the source's Name template by substituting only its
        linked spans with the text detected under the drawn ROI, so literal
        characters the user typed in the link view (prefixes, suffixes,
        separators) are preserved — this mirrors what the scan path does via
        ``__build_substring_list``/``__replacer``. Falls back to the raw detected
        text (so a manual placement over a symbol labelled ``UY00101`` is named
        ``UY00101``), then to ``<source_name> (<roi_uid_prefix>)`` when no text
        was detected, and to ``<source_name> (manual)`` when the ROI UID is
        unavailable.

        Returns ``(name, name_link_indexes)``; ``name_link_indexes`` maps each
        source Name link key to its corrected ``(start, end)`` span in the new
        name and is empty unless the name came from link substitution.
        """
        composed_name, name_link_indexes = self.__compose_manual_placement_name(detected_by_source_roi)
        if composed_name:
            return composed_name, name_link_indexes
        if detected_text_chars:
            joined = ''.join(detected_text_chars).strip()
            if joined:
                return joined, {}
        base_name = self.name or 'Unassigned'
        roi_uid = primary_linked_graphic.get('roi_uid') if isinstance(primary_linked_graphic, dict) else None
        if roi_uid:
            # roi_uid = "{pno}-{minX}-{minY}-{maxX}-{maxY}-{object_type}"; the
            # coordinate portion uniquely identifies the placement.
            parts = str(roi_uid).split('-')
            if len(parts) >= 5:
                short = '-'.join(parts[:5])
                return f"{base_name} ({short})", {}
        return f"{base_name} (manual)", {}


    def __compose_manual_placement_name(self, detected_by_source_roi):
        """ Rebuild the source's ``Name`` string, replacing each linked span with
        the text detected under the matching region of the manual placement and
        leaving every unlinked character (e.g. a ``PMP-`` prefix) untouched.

        ``detected_by_source_roi`` maps a *source* text roi_name to the string
        detected under the placement's corresponding region. Returns
        ``(name, {link_key: (start, end)})``, or ``(None, {})`` when no
        substitution could be made so the caller can fall back.
        """
        if not detected_by_source_roi:
            return None, {}
        name_entry = (self.__linked_text or {}).get('Name') or {}
        base_string = name_entry.get('string')
        links = name_entry.get('links') or {}
        if not isinstance(base_string, str) or not links:
            return None, {}

        def link_start(item):
            try:
                return int(item[1]['indexes'][0])
            except Exception:
                return 0

        result = base_string
        # Links are applied left to right; `offset` tracks how much earlier
        # substitutions grew/shrank the string so later spans stay aligned.
        offset = 0
        name_link_indexes = {}
        for link_key, link in sorted(links.items(), key=link_start):
            if not isinstance(link, dict):
                continue
            detected = detected_by_source_roi.get(link.get('document_selected_text_roi_name'))
            if detected is None:
                continue
            try:
                doc_indexes = link.get('document_selected_text_indexes') or [0, -1]
                if doc_indexes[1] == -1:
                    sub_string = detected
                else:
                    sub_string = detected[doc_indexes[0]:doc_indexes[1]]
                start = int(link['indexes'][0]) + offset
                end = int(link['indexes'][1]) + offset
            except Exception:
                continue
            if start < 0 or start > len(result) or end < start:
                continue
            result = result[:start] + sub_string + result[end:]
            offset += len(sub_string) - (end - start)
            name_link_indexes[link_key] = (start, start + len(sub_string))

        if not name_link_indexes or not result.strip():
            return None, {}
        return result, name_link_indexes


    def __redetect_manual_placement_text_regions(self, primary_linked_graphic,
                                                 text_roi_polygons, dest_path, dest_pno):
        """ Re-anchor each text region on the just-created placement to the
        caller-supplied polygon (in unscaled destination-doc coords) and replace
        each region's ``text_dict`` with characters actually detected under the
        polygon on the destination page. Returns
        ``(detected_strings, copy_to_final_roi_map, detected_by_copy_roi)`` where
        the first element is the concatenated character strings (one per region,
        in original insertion order) so callers can derive the module name, the
        second maps the roi_name assigned by ``create_copy`` to the final
        roi_name after redetect (so callers can propagate the source's
        ``linked_text`` entries onto the placement's re-keyed regions), and the
        third maps that same ``create_copy`` roi_name to the region's detected
        string.

        No-op when the caller does not supply polygons or when the placement has
        no text regions; existing (source-inherited) content is preserved as a
        best-effort fallback and empty maps are returned.
        """
        if not isinstance(primary_linked_graphic, dict):
            return [], {}, {}
        text_location_dict = primary_linked_graphic.get('text_location_dict') or {}
        if not text_location_dict:
            return [], {}, {}
        if not text_roi_polygons:
            return [], {}, {}

        try:
            document_type = primary_linked_graphic.get('document_type') or Database.DRAWING
        except Exception:
            document_type = Database.DRAWING
        if document_type == Database.DRAWING:
            zoom_scale = primary_linked_graphic.get('pdf_zoom_scale', 2) or 2
        else:
            zoom_scale = 1

        try:
            fresh_text_dicts = self.__primary_linked_graphic_view.redetect_text_dicts_at_polygons(
                text_roi_polygons, dest_path, dest_pno
            )
        except Exception:
            logging.exception("Draw ROI: redetect_text_dicts_at_polygons failed")
            fresh_text_dicts = []

        # Rebuild the text_location_dict so keys (roi_names) reflect the new
        # polygon coordinates and the on-page ROI list picks up the correct
        # bboxes downstream. Order of insertion is preserved so it stays in
        # sync with `text_roi_polygons`.
        old_items = list(text_location_dict.items())
        new_text_location_dict = {}
        new_name_map = {}
        old_name_map = primary_linked_graphic.get('text_location_name_to_roi_name_map') or {}
        detected_strings = []
        copy_to_final_roi_map = {}
        detected_by_copy_roi = {}
        # `mask_shape` is template-local: scaled page coords offset by the
        # placement's template origin.
        template_min_x = int(primary_linked_graphic.get('minX') or 0)
        template_min_y = int(primary_linked_graphic.get('minY') or 0)

        for idx, (old_roi_name, entry) in enumerate(old_items):
            if idx >= len(text_roi_polygons):
                # Fewer polygons than regions — preserve remaining entries as-is.
                new_text_location_dict[old_roi_name] = entry
                copy_to_final_roi_map[old_roi_name] = old_roi_name
                continue
            poly = text_roi_polygons[idx]
            if not poly or len(poly) < 3:
                new_text_location_dict[old_roi_name] = entry
                copy_to_final_roi_map[old_roi_name] = old_roi_name
                continue

            new_entry = dict(entry)
            new_entry['text_roi'] = [(float(p[0]), float(p[1])) for p in poly]
            new_entry['pno'] = dest_pno
            new_entry['path'] = dest_path
            if idx < len(fresh_text_dicts):
                new_entry['text_dict'] = fresh_text_dicts[idx] or []

            scaled = [(p[0] * zoom_scale, p[1] * zoom_scale) for p in poly]
            new_entry['mask_shape'] = [(int(x) - template_min_x, int(y) - template_min_y)
                                       for x, y in scaled]
            # roi_names are keyed off *unscaled* coords everywhere else
            # (`__create_text_location_dict_copy`), so match that convention.
            minX = int(min(p[0] for p in poly))
            minY = int(min(p[1] for p in poly))
            maxX = int(max(p[0] for p in poly))
            maxY = int(max(p[1] for p in poly))
            new_roi_name = (str(dest_pno) + '-' + str(minX) + '-' + str(minY)
                            + '-' + str(maxX) + '-' + str(maxY) + '-' + 'text')

            new_text_location_dict[new_roi_name] = new_entry
            copy_to_final_roi_map[old_roi_name] = new_roi_name
            for user_facing_name, mapped_roi_name in old_name_map.items():
                if mapped_roi_name == old_roi_name:
                    new_name_map[user_facing_name] = new_roi_name

            chars = ''.join((c.get('c') or '') for c in new_entry.get('text_dict', []))
            detected_strings.append(chars)
            detected_by_copy_roi[old_roi_name] = chars

        primary_linked_graphic['text_location_dict'] = new_text_location_dict
        if new_name_map:
            primary_linked_graphic['text_location_name_to_roi_name_map'] = new_name_map
        return detected_strings, copy_to_final_roi_map, detected_by_copy_roi


    def __create_manual_placement_template_images(self, primary_linked_graphic):
        """ Replace the source-inherited template/mask/display image paths on a
        manual placement with a fresh set cropped from the destination page.
        Falls back to the inherited paths (i.e. leaves the dict untouched) if the
        crop cannot be produced, so Done never fails outright. """
        if not isinstance(primary_linked_graphic, dict):
            return
        try:
            images = self.__primary_linked_graphic_view.create_placement_template_images(
                primary_linked_graphic
            )
        except Exception:
            logging.exception("Draw ROI: create_placement_template_images failed")
            return
        if not images:
            logging.info("Draw ROI: placement kept the source template images.")
            return
        primary_linked_graphic.update(images)


    def ensure_selection_callbacks_wired(self, **kwargs):
        """ Force the primary / secondary linked-graphic views to receive the
        selection-callback kwargs (roi_select_func, refresh_roi, etc.) even
        when the singleton selection subscription is currently pointing at a
        different cell. Used by the Draw ROI tool so scan/test work regardless
        of which cell was subscribed last.

        Uses ``selected=False`` so the wire-up does not also trigger the
        `__get_selected_roi()` side effect at the tail of the subscription
        callback — that side effect walks the primary linked-graphic
        text_location_dict + emits document_selected_text callbacks, which can
        stomp on UI state that the Draw ROI tool has just modified (freshly
        placed ROI, in-flight refresh, etc.). Wiring alone is all the Test /
        Scan flow needs.
        """
        self.__document_selection_subscription_callback(False, **kwargs)


    def scan_from_manual_placement(self, roi_uid, pno, template_mask,
                                   scale_factor=1.0, page_index=None,
                                   document_type=None, wire_kwargs=None):
        """ After a manual Draw ROI placement has been persisted, register it as
        a new template variant on the primary linked-graphic view and kick off
        a document-wide scan (same behaviour as the historical Highlight-Similar
        Done button). """
        if wire_kwargs:
            self.ensure_selection_callbacks_wired(**wire_kwargs)
        if document_type is None:
            document_type = Database.DRAWING
        self.__primary_linked_graphic_view.add_graphic_link(
            roi_uid, pno, template_mask,
            template_flip=[Template_Flip.NONE], template_rotate=[Template_Rotate.NONE],
            page_index=page_index, scale_factor=scale_factor,
            document_type=document_type, add_template_image=True,
        )
        self.__primary_graphic_scanning_done = False


    def test_from_manual_placement(self, roi_uid, pno, template_mask,
                                   document_type=None, wire_kwargs=None,
                                   polygon=None):
        """ Run a page-level test scan for the manually-placed template.

        When ``polygon`` (destination-doc unscaled coords) and ``template_mask``
        are supplied, the test uses a fresh template cropped from the destination
        page at that polygon — mirroring what the scan path does — so the
        preview reflects any Draw ROI flip / rotate / scale / move applied by
        the user. Without them, falls back to ``search_current_page`` which
        reuses the source's saved template + text-carved mask (identical
        behaviour to the "Test On Page" button on the linked-graphic view).

        ``roi_uid`` and ``document_type`` are accepted for signature parity
        with ``scan_from_manual_placement`` but are not used here.
        """
        _ = (roi_uid, document_type)
        if wire_kwargs:
            self.ensure_selection_callbacks_wired(**wire_kwargs)
        if polygon and template_mask is not None:
            self.__primary_linked_graphic_view.search_current_page_with_polygon_template(
                polygon, template_mask)
        else:
            self.__primary_linked_graphic_view.search_current_page()
    

    def add_secondary_progress_callback(self, func):
        """
        Adds a secondary progress callback function.

        Parameters:
            func (function): The callback function to be added.

        Returns:
            None
        """
        self.__add_secondary_progress_callback_func = func


    def get_primary_pdf_zoom_scale(self):
        """
        Retrieves the zoom scale for the primary linked graphic.

        Returns:
            int: The zoom scale for the primary linked graphic.
        """
        return self.__primary_linked_graphic_view.get_pdf_zoom_scale()
    

    def get_secondary_pdf_zoom_scale(self):
        """
        Retrieves the zoom scale for the secondary linked graphic.

        Returns:
            int: The zoom scale for the secondary linked graphic.
        """
        return self.__secondary_linked_graphic_view.get_pdf_zoom_scale()


    def set_name(self, name):
        """
        Sets the name of the control module.

        Parameters:
            name (str): The new name for the control module.

        Returns:
            None
        """
    
        if self.name == name:
            return 

        self.__delete_control_module_from_database()

        self.name = name
        self.__linked_graphic_change()

        
    def set_description(self, description):
        """
        Sets the description of the control module.

        Parameters:
            description (str): The new description for the control module.

        Returns:
            None
        """
        if self.description == description:
            return

        self.description = description
        self.__linked_graphic_change()


    def get_document(self):
        """
        Returns the name of the document associated with the logic control module.

        If the path is not set, returns None.

        Returns:
            str or None: The name of the document or None if the path is not set.
        """
        if not self.__path:
            return None
        
        return self.__path.split('/')[-1]


    def get_page(self):
        """
        Returns the page number for the object based on the primary linked graphic.

        Returns:
            int: The current page number incremented by 1.
                If the page number is None or less than 0, returns None.
        """
        if self.__pno is None and self.__pno >= 0:
            return None
        
        return self.__pno + 1


    def get_coordinates(self):
        """
        Retrieves the coordinates of the linked graphic.

        Returns:
            tuple: A tuple containing the X and Y coordinates of the linked graphic, 
                   normalized by the page width and height respectively. 
                   The third element of the tuple is always True.
                   Returns None if no linked graphic is found.
        """
        primary_linked_graphic = self.__primary_linked_graphic_view.get_linked_graphic_data()
        secondary_linked_graphic = self.__secondary_linked_graphic_view.get_linked_graphic_data()
        
        if secondary_linked_graphic:
            linked_graphic = secondary_linked_graphic
        elif primary_linked_graphic:
            linked_graphic = primary_linked_graphic
        else:
            return None 
            
        return (linked_graphic['minX']/linked_graphic['page_width'],
                    linked_graphic['minY']/linked_graphic['page_height'],True)
        


    def __scanning_done_callback(self,linked_graphic_name, results=None):
        """
        Callback function called when scanning is done for a linked graphic.

        Args:
            linked_graphic_name (str): The name of the linked graphic.
            results (list): The results of the scanning process.

        Returns:
            None
        """

        if linked_graphic_name == self.PRIMARY_GRAPHIC:
            self.__primary_graphic_scanning_done = True

        if linked_graphic_name == self.SECONDARY_GRAPHIC:
            self.__secondary_graphic_scanning_done = True

        if results is None:
            self.__scanning_started = False
        
        self.__async_canvas.after(1000,self.__check_if_done_building)


    def __check_if_done_building(self):
        """
        Check if the building process is done.

        This method checks if the building process is done by evaluating the conditions:
        - If the build from primary is not done, or
        - If the build from secondary is not done and the secondary scan has started.

        If the conditions are not met, the method schedules itself to be called again after 1 second.

        After the building process is done, the method calls the refresh ROIs function if it is available.

        Returns:
            None
        """

        primary_not_done = not self.__processed_all_primary_results() or not self.__primary_graphic_scanning_done
        secondary_not_done = not self.__processed_all_secondary_results() or not self.__secondary_graphic_scanning_done

        if primary_not_done or (secondary_not_done and self.__secondary_scan_started):

            self.__async_canvas.after(1000,self.__check_if_done_building)
            return
        
        average_scan_time = sum(self.__primary_scan_times)/len(self.__primary_scan_times)
        logging.info('Average time to scan for Primary Linked Graphic: {}s per page'.format(str(average_scan_time)))
        logging.info('Done building Control Modules from Primary Linked Graphic')

                                        
        

        if self.__refresh_rois_func:
            self.__refresh_rois_func()

        for func in self.__done_building_func:
            func()

        self.__done_building_func = []

        if not self.__secondary_scan_started:
            self.__remove_background_task_callback_func(self.id)
            return
            
        logging.info("Starting Pairing of Primary and Secondary Linked Graphic")
        self.__linked_graphic_pairing = linked_graphic_pairing(self.__poi_linking_path,copy.deepcopy(self.__primary_poi_dict)
                                                                , copy.deepcopy(self.__secondary_poi_dict)
                                                                , self.__linked_graphic_pairing_done)
        self.__add_secondary_progress_callback_func()
       
            



    def __build_from_secondary_linked_graphic(self, results):
        """
        Builds control modules from a secondary linked graphic.

        Args:
            results (list): A list of pages containing result ROI information.

        Returns:
            None

        Raises:
            None

        """
        self.__secondary_poi_dict = {}
        scan_times = []
        self.__secondary_scanning_count = 0
        for page in results:
            result_roi_list, page_index, scan_time, template_to_match_ratio = page

            scan_times.append(scan_time)

            for roi in result_roi_list:
                if page_index not in self.__secondary_poi_dict:
                    self.__secondary_poi_dict[page_index] = []

                center = (int((roi['points'][0]+roi['points'][2])/2),int((roi['points'][1]+roi['points'][3])/2))


                self.__secondary_poi_dict[page_index].append((center,roi['points'],roi['flip'],roi['rotation'],template_to_match_ratio))

                self.__secondary_scanning_count = self.__secondary_scanning_count + 1
        
        average_scan_time = sum(scan_times)/len(scan_times)
        logging.info('Average time to scan for Seconadary Linked Graphic: {}s per page'.format(str(average_scan_time)))
        logging.info('Done building Control Modules from Seconadary Linked Graphic')

        self.__build_from_secondary_done = True
    

    def remove_background_task_callback(self, func):
        """
        Sets the callback function for removing a background task.

        Parameters:
        - func: The callback function to be set.

        Returns:
        None
        """
        self.__remove_background_task_callback_func = func



    def __linked_graphic_pairing_done(self, shortest_path_pairs, path):
        """
        Performs the pairing of primary and secondary linked graphics based on the shortest path pairs.

        Args:
            shortest_path_pairs (dict): A dictionary containing the shortest path pairs.

        Returns:
            None
        """

        self.__linked_graphic_pairs = self.__db.get_linked_graphic_pairs(path)

        for pno, page_primary_poi_dict in self.__primary_poi_dict.items():

            if path not in shortest_path_pairs:
                continue


            shortest_path_pairs_in_doc = shortest_path_pairs[path]

            if pno not in shortest_path_pairs_in_doc: 
                continue

            

            self.__attach_secondary_to_primary(path, pno, page_primary_poi_dict, shortest_path_pairs_in_doc)
                

            if path not in self.__linked_graphic_pairs:
                self.__linked_graphic_pairs[path] = {}

            
            self.__linked_graphic_pairs[path][pno] = shortest_path_pairs_in_doc[pno]


        
        self.__linked_graphic_pairs['path'] = path


        self.__db.save_linked_graphic(self.__linked_graphic_pairs)

        self.__remove_background_task_callback_func(self.id)


        self.__write_secondary_to_control_modules(path)

        if self.__refresh_rois_func:
            self.__refresh_rois_func()
        logging.info('Done pairing Primary Linked Graphic and Secondary Linked Graphic')


    
    def __write_secondary_to_control_modules(self, path):


        roi_list = self.__db.get_project_document_roi(path)

        new_control_modules = self.__new_control_modules

        self.__check_overlapping_primary_results(roi_list, new_control_modules)


        for _,control_module in new_control_modules.items():

            self.__filtered_new_control_modules_id.append(control_module['id'])

            self.__setup_roi_in_roi_list(roi_list, control_module['pno'], control_module['primary_linked_graphic'])
            
            if control_module['secondary_linked_graphic']:
                self.__setup_roi_in_roi_list(roi_list, control_module['pno'], control_module['secondary_linked_graphic'])    

            self.__db.save_control_module(control_module)

        self.__save_page_roi(path,roi_list, False)

   


    def __attach_secondary_to_primary(self, path, pno, page_primary_poi_dict, shortest_path_pairs):
        """
        Attach a secondary graphic to the primary graphic based on the shortest path pairs.

        Parameters:
        - pno (int): The page number.
        - page_primary_poi_dict (dict): A dictionary containing primary graphics as keys and their corresponding POIs as values.
        - shortest_path_pairs (dict): A dictionary containing the shortest path pairs for each primary graphic.

        Returns:
        None
        """
        
        for primary_tagname, values in shortest_path_pairs[pno][0].items():
            costs = np.array([value[0] for value in values])
            index_min = np.argmin(costs)
                #test_img = cv2.polylines(img, [np.array(values[index_min][2][0][2])], 
                            #False, (0,0,255), 5)
            if primary_tagname not in page_primary_poi_dict:
                continue
            page_primary_poi_dict.pop(primary_tagname)
                #cv2.imshow(primary_tagname,cv2.resize(test_img,(1500,int(test_img.shape[0]*1500/test_img.shape[1]))))
                #cv2.waitKey(0)
            if self.name == primary_tagname:
                continue
            secondary_roi = values[index_min][1]
            secondary_linked_graphic, _, __ = self.__secondary_linked_graphic_view.create_copy(path,pno,secondary_roi,[],rotation=values[index_min][4],template_to_match_ratio=values[index_min][5])
            secondary_linked_graphic['flip'] = values[index_min][3]
            secondary_linked_graphic['rotation'] = values[index_min][4]
            
            primary_tag_id = self.__new_control_modules_tagnames[primary_tagname]
            self.__new_control_modules[primary_tag_id]['secondary_linked_graphic']=secondary_linked_graphic



    def __build_new_control_module(self, path, page_index, roi, text_to_search, text_locations, character_differences, template_to_match_ratio, new_control_modules=None):
        """
        Builds a new control module based on the given parameters.

        Args:
            roi_list (list): List of ROIs.
            page_index (int): Index of the page.
            roi (dict): ROI dictionary.
            text_to_search (str): Text to search.
            text_locations (list): List of text locations.
            character_differences (int): Number of character differences.
            template_to_match_ratio (float): Template to match ratio.
            new_control_modules (dict, optional): Dictionary of new control modules. Defaults to None.

        Returns:
            None
        """
        
        primary_linked_graphic, text_old_to_new_roi_names, overlaps = self.__primary_linked_graphic_view.create_copy(path,page_index,roi['points'],text_locations,template_to_match_ratio)
        
        if overlaps:
            return

        if page_index not in self.__primary_poi_dict:
            self.__primary_poi_dict[page_index] = {}

        center = (int((roi['points'][0]+roi['points'][2])/2),int((roi['points'][1]+roi['points'][3])/2))

        self.__primary_poi_dict[page_index][text_to_search] = center

        self.__poi_linking_path = path

        new_linked_text = self.__copy_linked_text(page_index, text_to_search, text_old_to_new_roi_names, character_differences)
         
        if primary_linked_graphic['roi_uid'] == self.__primary_linked_graphic_data['roi_uid']:
            return 
                       
        dict_data = {
                            'id': primary_linked_graphic['roi_uid'],
                            'name': text_to_search,
                            'description': '',
                            'type': 'Unassigned',
                            'path': path,
                            'pno': page_index,
                            'primary_linked_graphic': primary_linked_graphic,
                            'secondary_linked_graphic': {},
                            'linked_text':new_linked_text,
                            'flow_direction':self.__flow_direction,
                            'template_rotation':[item.value for item in self.__secondary_linked_graphic_rotation]
                        }

        self.__new_control_modules[primary_linked_graphic['roi_uid']] = dict_data
        self.__new_control_modules_tagnames[text_to_search] = primary_linked_graphic['roi_uid']

        

        if new_control_modules is not None:
            new_control_modules[primary_linked_graphic['roi_uid']] = dict_data


        
    def __write_new_control_modules_to_db(self, path, new_control_modules=None, force_write=False):
        """
        Writes new control modules to the database.

        Retrieves the ROI list from the project document using the given path.
        Iterates over the new control modules and adds them to the control_modules_list.
        Sets up the ROI in the ROI list for the primary_linked_graphic of each control module.
        If a control module has a secondary_linked_graphic, sets up the ROI in the ROI list for it as well.
        Saves the control_modules_list to the database using the save_bulk_control_modules method.
        Saves the updated ROI list to the page using the save_page_roi method.
        """

        roi_list = self.__db.get_project_document_roi(path)

        control_modules_list = []

        if new_control_modules is None:
            new_control_modules = self.__new_control_modules

        self.__check_overlapping_primary_results(roi_list, new_control_modules)

        new_overlapping_control_modules_id = copy.deepcopy(self.__new_overlapping_control_modules_id)

        for id,control_module in new_control_modules.items():

            if id in new_overlapping_control_modules_id and not force_write:
                continue

            self.__filtered_new_control_modules_id.append(control_module['id'])
            control_modules_list.append(control_module)

            self.__setup_roi_in_roi_list(roi_list, control_module['pno'], control_module['primary_linked_graphic'])
            
            if control_module['secondary_linked_graphic']:
                self.__setup_roi_in_roi_list(roi_list, control_module['pno'], control_module['secondary_linked_graphic'])    

        self.__db.save_bulk_control_modules(control_modules_list)
        self.__save_page_roi(path,roi_list, False)



    def __check_overlapping_primary_results(self, roi_list, control_modules):
            
        for _,control_module in control_modules.items():

            if len(roi_list) <= control_module['pno']:
                continue

            page_roi = roi_list[control_module['pno']]

            if not page_roi:
                continue

            def rectangles_overlap(rect1, rect2):
                x1, y1, x2, y2 = rect1
                a1, b1, a2, b2 = rect2
                return not (x2 <= a1 or a2 <= x1 or y2 <= b1 or b2 <= y1)

            roi = control_module['primary_linked_graphic']['roi']

            minX = int(min(l[0] for l in roi))
            minY = int(min(l[1] for l in roi))
            maxX = int(max(l[0] for l in roi))
            maxY = int(max(l[1] for l in roi))

            r1 = (minX, minY, maxX, maxY)

            for id1, roi  in page_roi.items():
                    
                    if self.PRIMARY_GRAPHIC_TYPE not in id1:
                        continue
                    minX = int(min(l[0] for l in roi))
                    minY = int(min(l[1] for l in roi))
                    maxX = int(max(l[0] for l in roi))
                    maxY = int(max(l[1] for l in roi))

                    r2 = (minX, minY, maxX, maxY)

                    if rectangles_overlap(r1, r2):
                        self.__new_overlapping_control_modules_id.add(control_module['id'])
                        self.__old_overlapping_control_modules_id.add(id1)


    def __copy_linked_text(self, page_index, text_to_search, text_old_to_new_roi_names, character_differences):
        """
        Copies the linked text and updates the necessary fields based on the provided parameters.

        Args:
            page_index (int): The index of the page.
            text_to_search (str): The text to search for.
            text_old_to_new_roi_names (dict): A dictionary mapping old ROI names to new ROI names.
            character_differences (list): A list of character differences.

        Returns:
            dict: The copied and updated linked text.
        """
        new_linked_text = copy.deepcopy(self.__linked_text)

        if not new_linked_text or not 'Name' in new_linked_text:
            return new_linked_text
        
        new_linked_text['Name']['string'] = text_to_search

        new_linked_text['Name']['links'] = self.__correct_link_text_indexes(
                                                        character_differences, 
                                                        new_linked_text['Name']['links']
                                                        )
        
        
        for _, linked_text in new_linked_text['Name']['links'].items():
            linked_text['document_selected_text_roi_name'] = text_old_to_new_roi_names[linked_text['document_selected_text_roi_name']]
            linked_text['document_selected_text_pno'] = page_index
    
        return new_linked_text


    def __copy_linked_text_for_manual_placement(self, dest_path, dest_pno,
                                                placement_name, source_to_final_roi_map,
                                                name_link_indexes=None):
        """ Manual-placement variant of `__copy_linked_text`.

        Deep-copies the source template's ``linked_text`` onto the placement so
        the Draw ROI'd module inherits the Name/parameter linked-text entries
        instead of coming up empty. Differences from the scan-path helper:
          * updates ``document_selected_text_path`` too, since the destination
            document may not match the source document (scan path assumes the
            source path).
          * re-indexes the ``Name`` links from ``name_link_indexes`` (computed
            while recomposing the placement name) instead of running the
            scanner's ``character_differences`` correction. Other entries keep
            their source indexes, so their highlighted spans may drift when the
            detected char count differs from the source.
          * silently drops per-key links whose source roi_name is not in
            ``source_to_final_roi_map`` (missing polygon / redetect skipped)
            instead of raising KeyError.
        """
        new_linked_text = copy.deepcopy(self.__linked_text)
        if not new_linked_text:
            return new_linked_text

        for entry_name, entry in new_linked_text.items():
            if not isinstance(entry, dict):
                continue
            is_name = entry_name == 'Name'
            if is_name and placement_name:
                entry['string'] = placement_name
            links = entry.get('links') or {}
            remapped_links = {}
            for key, link in links.items():
                if not isinstance(link, dict):
                    remapped_links[key] = link
                    continue
                src_roi = link.get('document_selected_text_roi_name')
                new_roi = source_to_final_roi_map.get(src_roi)
                if not new_roi:
                    # No matching destination text region — dropping this link is
                    # safer than leaving it pointing at the source's ROI, which
                    # would go stale the moment the source module is removed.
                    continue
                link['document_selected_text_roi_name'] = new_roi
                link['document_selected_text_pno'] = dest_pno
                link['document_selected_text_path'] = dest_path
                new_key = key
                if is_name and name_link_indexes and key in name_link_indexes:
                    start, end = name_link_indexes[key]
                    link['indexes'] = (start, end)
                    new_key = "{start}-{end}".format(start=start, end=end)
                remapped_links[new_key] = link
            entry['links'] = remapped_links

        return new_linked_text


    def __correct_link_text_indexes(self, character_differences, links):
        """
        Corrects the indexes of link text based on the given character differences.

        Args:
            character_differences (list): A list of dictionaries containing the index and difference of characters.
            links (dict): A dictionary containing the links with their indexes.

        Returns:
            dict: A dictionary containing the corrected indexes of the links.

        """
        corrected_indexes_links = {}
        for _, link in links.items():
            indexes = list(link['indexes'])
            for character_difference in character_differences:
                if indexes[1] >= character_difference['index']:
                    indexes[1] = indexes[1] + character_difference['difference']
                
                if indexes[0] >= character_difference['index']:
                    indexes[0] = indexes[0] + character_difference['difference']
                    if indexes[0] <= 0:
                        indexes[0] = 0

            key = "{start}-{end}".format(start=indexes[0],end=indexes[1])
            link['indexes'] = (indexes[0],indexes[1])
            corrected_indexes_links[key] = link
        return corrected_indexes_links

        
    def __setup_roi_in_roi_list(self, roi_list, page_index, linked_graphic):
        """
        Sets up the region of interest (ROI) in the ROI list.

        Args:
            roi_list (list): The list of ROIs.
            page_index (int): The index of the page.
            linked_graphic (dict): The linked graphic containing ROI information.

        Returns:
            None
        """
        while len(roi_list) - 1  < page_index:
            roi_list.append(None)

        if roi_list[page_index] == None:
            roi_list[page_index] = {}

        roi_list[page_index][linked_graphic['roi_uid']]=linked_graphic['roi']

        for roi_id, text_location in linked_graphic['text_location_dict'].items():
            roi_list[page_index][roi_id]=text_location['text_roi']


        


    def __save_page_roi(self,path,roi_list,referesh=True,page_index=None):
        """
        Saves the page ROI for a specified document path and updates the database.

        Args:
            path (str): The document path the ROI will be saved for.
            roi_list (list): The list of ROIs to be saved.

        Returns:
            None
        """
        self.__db.insert_project_document_roi(path,roi_list)
        if self.__refresh_rois_func and referesh:
            self.__async_canvas.after(100, lambda: self.__refresh_rois_func(page_index=page_index))

    def __replacer(self, s, newstring, indexes, nofail=False, character_differences=None):
        """
        Replaces a substring in a given string with a new string at specified indexes.

        Args:
            s (str): The original string.
            newstring (str): The new string to be inserted.
            indexes (list[int]): A list containing the start and end indexes of the substring to be replaced.
            nofail (bool, optional): If True, no error will be raised if the index is outside the string. Defaults to False.
            character_differences (list[dict], optional): A list of dictionaries containing information about character differences. Defaults to None.

        Returns:
            str: The modified string with the substring replaced.

        Raises:
            ValueError: If the index is outside the given string and nofail is False.

        """

        for character_difference in character_differences:
            if indexes[1] >= character_difference['index']:
                indexes[0] = indexes[0] + character_difference['difference']
                indexes[1] = indexes[1] + character_difference['difference']

        # raise an error if index is outside of the string
        if not nofail and indexes[0] not in range(len(s)):
            raise ValueError("index outside given string")

        # if not erroring, but the index is still not in the correct range..
        if indexes[0] < 0:  # add it to the beginning
            return newstring + s
        if indexes[0] > len(s):  # add it to the end
            return s + newstring
        if len(s[:indexes[0]]) + len(newstring) >= len(s):
            return s[:indexes[0]] + newstring

        # insert the new string between "slices" of the original
        return s[:indexes[0]] + newstring + s[indexes[1]:]
                   


    def __get_substring_of_text_location(self, text_location,linked_text_to_search,character_differences):
        """
        Retrieves a list of substrings from the given text location based on the linked text to search and character differences.

        Parameters:
        - text_location (str): The text location to search for substrings.
        - linked_text_to_search (dict): A dictionary containing linked text names as keys and their corresponding strings as values.
        - character_differences (list): The list to store character differences.

        Returns:
        - substring_list (list): A list of substrings found in the text location.

        """
        
        substring_list = []
        
        for linked_text_name, linked_texts in self.__linked_text.items():
            
            if linked_text_name not in linked_text_to_search.keys():
                linked_text_to_search[linked_text_name]=linked_texts['string']
           
            self.__build_substring_list(text_location, linked_text_to_search, substring_list, linked_text_name, linked_texts, character_differences)
                       
        return substring_list



    def __build_substring_list(self, text_location, linked_text_to_search, substring_list, linked_text_name, linked_texts, character_differences):
        """
        Builds a list of substrings based on the given text location and linked texts.

        Args:
            text_location (dict): The dictionary containing information about the text location.
            linked_text_to_search (dict): The dictionary containing linked text to search.
            substring_list (list): The list to store the generated substrings.
            linked_text_name (str): The name of the linked text.
            linked_texts (dict): The dictionary containing linked texts.
            character_differences (list): The list to store character differences.

        Returns:
            None
        """
        for substring_name, linked_text in linked_texts['links'].items():
            if text_location['roi_name'] == linked_text['document_selected_text_roi_name']:
                string=''


                for char in text_location['text_dict']:
                    string = string + char['c']

                indexes = linked_text['document_selected_text_indexes']
                
                if indexes[1] == -1:
                    sub_string = string
                else:
                    sub_string = string[indexes[0]:indexes[1]]
                    sub_string = self.__correct_if_ocr_used(sub_string
                                                        ,linked_text_to_search
                                                        ,linked_text_name
                                                        ,linked_text
                                                        ,character_differences=character_differences)
                
                
                try:
                    linked_text_to_search[linked_text_name] = self.__replacer(linked_text_to_search[linked_text_name]
                                                                                ,sub_string
                                                                                ,list(linked_text['indexes'])
                                                                                ,character_differences=character_differences)

                    data = {
                        'index':linked_text['indexes'][1],
                        'difference':len(sub_string)-(linked_text['indexes'][1] - linked_text['indexes'][0])
                    }
                    character_differences.append(data)
                except Exception as error:
                    continue
                substring_list.append(( text_location['roi_name'] , linked_text_name, substring_name, sub_string[indexes[0]:indexes[1]]))



    def __correct_if_ocr_used(self,string, linked_text_to_search, linked_text_name, linked_text, character_differences):
        """
        Corrects the given string if OCR (Optical Character Recognition) is used.

        Args:
            string (str): The original string to be corrected.
            linked_text_to_search (dict): A dictionary containing linked text to search.
            linked_text_name (str): The name of the linked text.
            linked_text (dict): A dictionary containing linked text information.
            character_differences (list): A list of character differences.

        Returns:
            str: The corrected string.
        """
        if self.__primary_linked_graphic_view.ocr_used():
            indexes = list(linked_text['indexes'])
            for character_difference in character_differences:
                if indexes[1] >= character_difference['index']:
                    indexes[0] = indexes[0] + character_difference['difference']
                    indexes[1] = indexes[1] + character_difference['difference']
            string = self.__correct_document_text(linked_text_to_search[linked_text_name][indexes[0]:indexes[1]]
                                                    ,string)
                                                        
        return string

         

    def __find_other_control_modules_in_db(self, text_locations):
        for roi_name, text in text_locations:
            pass

    def setup_data_handler(self, data_handler: ACM_Data_Handler):
        """
        Sets up the Application Code Manager data handler for the logic control module.

        :param data_handler: The data handler object.
        :type data_handler: ACM_Data_Handler

        :returns: None
        :rtype: None

        This function sets the data handler for the control module.
        """
        self.__acm_data_handler = data_handler


    def setup_project(self,project_name, database, config):
        """
        Sets up the project with the given project name, database, and configuration.

        :param project_name: The name of the project.
        :type project_name: str
        :param database: The database object.
        :type database: Database
        :param config: The configuration object.
        :type config: Config

        :returns: None
        :rtype: None

        This function sets the project name, database, and configuration for the control module.
        It also sets the project name for the primary and secondary linked graphics.
        It then calls the get_data_from_database method to retrieve data from the database.
        """
        self.__project_name = project_name
        self.__db = database
        self.__config = config
        
        self.__primary_linked_graphic_view.set_project_name(self.__project_name)
        self.__primary_linked_graphic_view.set_config(self.__config)
        self.__secondary_linked_graphic_view.set_project_name(self.__project_name)
        self.__secondary_linked_graphic_view.set_config(self.__config)
        self.__get_data_from_database()
        


    def go_to(self):
        """
        Go to the object location based on the primary linked graphic.

        :returns: None
        :rtype: None

        This function is called when the user clicks on the linked graphic to go to the specified location.
        """
        
        primary_linked_graphic_location = self.__primary_linked_graphic_view.get_document_location()
        if (primary_linked_graphic_location['roi_uid'] == None
                or primary_linked_graphic_location['pno'] == None
                or primary_linked_graphic_location['path'] == None): 
                raise ValueError('Linked graphics are not defined.')
        
        self.__go_to_roi_uid = primary_linked_graphic_location['roi_uid']
        self.__go_to_pno = primary_linked_graphic_location['pno']
        
        self.__go_to_document_callback(primary_linked_graphic_location['path'], primary_linked_graphic_location['document_type'])
        self.__move_to_roi()


    def __go_to_callback(self, roi_uid,pno,path,doc_type=Database.DRAWING):
        """
        Go to the given region-of-interest (ROI).

        :param roi_uid: The region-of-interest (ROI) unique identifier.
        :type roi_uid: int
        :param pno: The page number.
        :type pno: int
        :param path: The path to the document.
        :type path: str
        :param doc_type: The type of the document. Defaults to Database.DRAWING.
        :type doc_type: str

        :returns: None
        :rtype: None

        This function is called when the user clicks on a linked graphic to go to the specified location.
        The function sets the region-of-interest (ROI) unique identifier, page number, and path to the specified values.
        The function then calls the go_to_document_callback method with the specified path and document type.
        The function then calls the move_to_roi method to move to the specified ROI.
        """
        self.__go_to_roi_uid = roi_uid
        self.__go_to_pno = pno

        self.__go_to_document_callback(path,doc_type)
        self.__move_to_roi()


    def setup_canvas(self, canvas:tk.Canvas):
        """ Tkinter element used for calling the main thread"""
        self.__async_canvas = canvas
        
        
    def add_linked_name_text_entry(self, entry: linked_text_entry):
        """ 
        Adds linked text entry to the control module. Done to link the object to the User Interface and populate values on the UI.
        
        :param entry: The linked text entry to add.
        :type entry: linked_text_entry
        
        :returns: None
        :rtype: None
        
        This function adds a linked text entry to the control module. This function is run to 
        link the object to the User Interface and populate values on the UI. The linked text 
        entry is added to the control module using the set_text_link_callback method of 
        the linked text entry. The set_text_link_callback method takes the linked_text_callback 
        function as an argument. The linked text entry is also added to the control module using 
        the set_go_to_callback method of the linked text entry. The set_go_to_callback method takes 
        the go_to_roi_for_linked_text function as an argument. The linked text entry is then drawn 
        using the draw_linked_text method of the control module.
        """
        self.__name_entry = entry
        self.__name_entry.set_text_link_callback(self.__linked_text_callback)
        self.__name_entry.set_go_to_callback(self.__go_to_roi_for_linked_text)
        self.draw_linked_text()

    
    def __linked_text_callback(self, is_linked, indexes, string, name):
        """
        Links or unlinks text in the document to the control module.
        
        :param is_linked: True if the text is to be linked, False if the text is to be unlinked.
        :type is_linked: bool
        :param indexes: The indexes of the selected text in the document.
        :type indexes: tuple(int, int)
        :param string: The selected text in the document.
        :type string: str
        :param name: The name of the linked text entry.
        :type name: str
        
        :returns: None
        :rtype: None
        
        This function links or unlinks text in the document to the control module. If the text is to be linked, 
        the function checks if the selected text in the document matches the selected text in the linked text 
        entry. If the text matches, the function checks if the selected characters have already been linked. If 
        the selected characters have not been linked, the function creates a dictionary with the indexes of the 
        selected text, the path to the document, the page number of the document, the region-of-interest (ROI) 
        name, and the ROI indexes. The dictionary is then added to the linked text entry. If the text is to be 
        unlinked, the function removes the dictionary from the linked text entry.
        """
        
        indexes_id = '{start}-{end}'.format(start=indexes[0],end=indexes[1])

        if not is_linked:
            self.__linked_text[name]['links'].pop(indexes_id, None)
            return
        
        if not self.__is_text_same(string[indexes[0]:indexes[1]],self.__document_selected_text):
            raise ValueError('The selected text in "'+name
                                + '" is not the same as the selected text in the document. Please make sure the text matches.')
            
        if self.__is_char_in_any(name,indexes):
            raise ValueError('The selected characters in "'+name
                                + '" have already been linked.')
            
            
        dict = {
            'indexes':indexes,
            'document_selected_text_path':self.__document_selected_text_path,
            'document_selected_text_pno':self.__document_selected_text_pno,
            'document_selected_text_roi_name' :self.__document_selected_text_roi_name,
            'document_selected_text_indexes' :self.__document_selected_text_indexes
        }
        
        if name not in self.__linked_text.keys():
            self.__linked_text[name] = {
                'string':string,
                'links':{}
                }
        self.__linked_text[name]['links'][indexes_id] = dict

        self.__save_to_database()
        return linked_text_entry.TOP_SIDE

    letter_to_number_correction = {
        'I':'1',
        'Z':'2',
        'S':'5',
        'G':'6',
        'O':'0',
        'Q':'0',
        'o':'0'
    }

    number_to_letter_correction = {
        '1':'I',
        '2':'Z',
        '5':'S',
        '6':'G',
        '0':'O'
    }

    letter_to_letter_correction = {
        'y':'V'
    }

    special_to_letter_correction = {
        '$':'S',
        '/':'I',
        '%':'X',
        '|':'I',
        ']': 'I',
        '[': 'I'
    }

    def __is_text_same(self, actual_text : str, document_text : str):
        """
        Determines if actual_text and the document_text is the same.
        If the Optical Character Recognition was used, corrections 
        are applied to the document_text before check if the text are the same.    
        
        :param actual_text: The actual text.
        :type actual_text: str
        :param document_text: The text from the document.
        :type document_text: str

        :returns: True if the text are the same, False otherwise.
        :rtype: bool

        This function determines if actual_text and the document_text is the same. If the Optical Character Recognition
        was used, corrections are applied to the document_text before check if the text are the same. The function
        returns True if the text are the same, False otherwise.
        """
        
        
        if not self.__primary_linked_graphic_view.ocr_used():
            return actual_text.lower() == document_text.lower()

        correction = self.__correct_document_text(actual_text, document_text)

        return actual_text.lower() == correction.lower() 



    def __correct_document_text(self, actual_text:str, document_text:str):
        """
        Corrects the document text based on the actual text. Checks for common OCR errors.

        :param actual_text: The actual text.
        :type actual_text: str
        :param document_text: The text from the document.
        :type document_text: str

        :returns: The corrected document text.
        :rtype: str

        This function corrects the document text based on the actual text. It checks for common OCR errors
        such as replacing letters with numbers and vice versa. The function returns the corrected document text.
        """

        correction = ''

        #if len(actual_text) != len(document_text):
        #    return ''

        document_text = document_text.upper()

        for i in range(len(document_text)):
            if len(actual_text) - 1 < i:
                break
            if actual_text[i].isdigit() and document_text[i].isalpha() and document_text[i] in self.letter_to_number_correction:
                char = self.letter_to_number_correction[document_text[i]]

                correction = correction + char

            elif actual_text[i].isalpha() and document_text[i].isdigit() and document_text[i] in self.number_to_letter_correction:
                char = self.number_to_letter_correction[document_text[i]]

                correction = correction + char

            elif actual_text[i].isalpha() and document_text[i] in self.special_to_letter_correction:
                char = self.special_to_letter_correction[document_text[i]]

                correction = correction + char

            else:
                correction = correction + document_text[i]
        return correction


        


    def __go_to_roi_for_linked_text(self,name,indexes_id):
        """
        Go to the region of interest (ROI) for the linked text.

        :param name: The name of the linked text entry.
        :type name: str
        :param indexes_id: The indexes of the linked text entry.
        :type indexes_id: str

        :returns: None
        :rtype: None

        This function goes to the region of interest (ROI) for the linked text. It retrieves the path, ROI name, and page number
        of the linked text entry based on the given name and indexes. The function then calls the go_to_document_callback method
        with the path as an argument. It moves to the region of interest using the move_to_roi method.
        """
        
        path = self.__linked_text[name]['links'][indexes_id]['document_selected_text_path']
        self.__go_to_roi_uid = self.__linked_text[name]['links'][indexes_id]['document_selected_text_roi_name']
        self.__go_to_pno = self.__linked_text[name]['links'][indexes_id]['document_selected_text_pno']

        self.__go_to_document_callback(path)
        self.__move_to_roi()


    def __is_char_in_any(self, name, indexes):
        """
        Check if a character is present in any linked text.

        :param name: The name of the linked text entry.
        :type name: str
        :param indexes: The indexes of the linked text entry.
        :type indexes: tuple(int, int)

        :returns: True if the character is present in any linked text, False otherwise.
        :rtype: bool

        This function checks if a character is present in any linked text. It iterates over the linked text entries and checks
        if the character is present in any of them. The function returns True if the character is present in any linked text,
        False otherwise.
        """

        if name in self.__linked_text:
            for _, linked_text in self.__linked_text[name]['links'].items():
                if self.__index_overlap(linked_text['indexes'],indexes):
                    return True

        return False
        

    def __index_overlap(self,index1, index2):
        """
        Check if two index ranges overlap.

        :param index1: The first index range.
        :type index1: tuple(int, int)
        :param index2: The second index range.
        :type index2: tuple(int, int)

        :returns: True if the index ranges overlap, False otherwise.
        :rtype: bool

        This function checks if two index ranges overlap. It creates two ranges based on the given indexes and checks if
        the ranges overlap. The function returns True if the index ranges overlap, False otherwise.
        """
        
        range1 = range(index1[0],index1[1])
        range2 = range(index2[0],index2[1])

        if not range1:
            return True  # empty range is subset of anything
        if not range2:
            return False  # non-empty range can't be subset of empty range
        if len(range1) > 1 and range1.step % range2.step:
            return False  # must have a single value or integer multiple step
        return range1.start in range2 or range1[-1] in range2


    def create_linked_graphics_screen(self, canvas: tk.Canvas ):
        """
        Creates the linked graphics screen on the config canvas that is responsible for presenting the linked graphics views.

        :param canvas: The canvas to draw the linked graphics screen on.
        :type canvas: tk.Canvas

        :return: None
        :rtype: None

        This method is responsible for creating the linked graphics screen on the config canvas. It creates the name label,
        the primary linked graphic view, and the secondary linked graphic view. The primary linked graphic view is set up
        using the setup_view method of the primary linked graphic view. The secondary linked graphic view is set up using
        the setup_view method of the secondary linked graphic view. The flow direction label is created, and the flow direction
        buttons are set up using the direction_buttons class. The scan rotation label is created, and the clockwise 90, clockwise
        180, and clockwise 270 buttons are set up using the hover_toggle_button class. The rotation buttons are set using the
        set_rotation_buttons method.
        """
        self.start_scan = tk.PhotoImage(data=start_scan)
        self.test_on_page = tk.PhotoImage(data=test_on_page)


        self.canvas = canvas
        self.screen_label = custom_label(self.canvas, 8, 0, text="Linked Graphics", fill= '#505050',size=16,weight="bold")
        self.name_label = custom_label(self.canvas, 8, 24, text=self.name, fill= '#505050',size=12,weight="bold")
        self.__primary_linked_graphic_view.setup_view( self.canvas,0,48, 
                                                description='Used for linking texted and positioning if secondary graphic is not defined.' 
                                            )
        self.__divider_line_A = cell_line(self.canvas, 24, 16, 506, fill= '#E5E5E5', width=1)
        self.__secondary_linked_graphic_view.setup_view( self.canvas,0,524,  
                                                description='Only used for positioning.' 
                                            )
        
    
        set_active_canvas_screen(self.canvas, self)
        self.canvas.bind('<Configure>',  self.__redraw_config_canvas)  # canvas is resized
        self.__redraw_config_canvas()
        self.__primary_linked_graphic_view.setup_image_text_locations_list_view()
        self.__secondary_linked_graphic_view.setup_image_text_locations_list_view()
        


    def create_assign_object_screen(self, canvas: tk.Canvas, assignment_id):
        """
        Creates the assign object screen on the given canvas.

        :param canvas: The canvas to draw the assign object screen on.
        :type canvas: tk.Canvas

        :return: None
        :rtype: None

        This method is responsible for creating the assign object screen on the given canvas. It creates the assign object screen
        using the setup_assign_object_screen method of the assign object screen. The assign object screen is set up on the given
        canvas at the specified coordinates.
        """
        self.__assign_object_screen.setup_assign_object_view(canvas,0,0,self.name,self.__acm_data_handler,self.__db,assignment_id)
        set_active_canvas_screen(canvas, self.__assign_object_screen)
        canvas.bind('<Configure>',  self.__assign_object_screen.draw)
        self.__assign_object_screen.draw()

    
    def create_object_parameter_view(self, canvas:tk.Canvas):
        """
        Creates and sets up the object parameter view on the given canvas.

        Parameters:
        - canvas (tk.Canvas): The canvas on which to create the object parameter view.

        Returns:
        - None
        """
        self.__object_parameter_screen.setup_object_parameter_view(canvas,0,0
                                                                    ,self.__project_name
                                                                    ,self.__acm_data_handler
                                                                    ,self.__db
                                                                    ,config=self.__config)
        set_active_canvas_screen(canvas, self.__object_parameter_screen)
        canvas.bind('<Configure>',  self.__object_parameter_screen.draw)
        self.__object_parameter_screen.draw()


    def show_parameter_linked_text(self, linked_text):
        self.__object_parameter_screen.show_linked_text(linked_text)


    def show_add_parameter_view_with_prediction(self, prediction, callback=None):
        self.__object_parameter_screen.show_add_parameter_view_with_prediction(prediction, callback)


    def show_add_subobject_view_with_prediction(self, prediction, callback=None):
        self.__subobject_parameter_screen.show_add_subobject_view_with_prediction(prediction, callback)



    def create_subobject_parameter_view(self, canvas:tk.Canvas, add_to_background_func = None
                                        ,remove_from_background_func = None):
        """
        Creates a subobject parameter view on the given canvas.

        Parameters:
        - canvas (tk.Canvas): The canvas on which to create the subobject parameter view.

        Returns:
        - None
        """
        if not self.__subobject_parameter_view_setup:
            self.__subobject_parameter_screen.setup_subobject_parameter_view(canvas,0,0
                                                                    ,self.__project_name
                                                                    ,self.__acm_data_handler
                                                                    ,self.__db
                                                                    ,config=self.__config
                                                                    ,add_to_background_func=add_to_background_func
                                                                    ,remove_from_background_func=remove_from_background_func)
            
            self.__subobject_parameter_view_setup = True
        set_active_canvas_screen(canvas, self.__subobject_parameter_screen)
        canvas.bind('<Configure>',  self.__subobject_parameter_screen.draw)
        self.__subobject_parameter_screen.draw()


    def show_subobject_linked_text(self, linked_text):
        self.__subobject_parameter_screen.show_linked_text(linked_text)
        

    def __set_rotation_buttons(self):
        """
        Sets the rotation buttons based on the values in `self.__secondary_linked_graphic_rotation`.

        If `Template_Rotate.CW_90` is in `self.__secondary_linked_graphic_rotation`, the `__cw_90_button` is set.
        Otherwise, the `__cw_90_button` is reset.

        If `Template_Rotate.CW_180` is in `self.__secondary_linked_graphic_rotation`, the `__cw_180_button` is set.
        Otherwise, the `__cw_180_button` is reset.

        If `Template_Rotate.CW_270` is in `self.__secondary_linked_graphic_rotation`, the `__cw_270_button` is set.
        Otherwise, the `__cw_270_button` is reset.
        """
        if Template_Rotate.CW_90 in self.__secondary_linked_graphic_rotation:
            self.__cw_90_button.set()
        else:
            self.__cw_90_button.reset()
        
        if Template_Rotate.CW_180 in self.__secondary_linked_graphic_rotation:
            self.__cw_180_button.set()
        else:
            self.__cw_180_button.reset()

        if Template_Rotate.CW_270 in self.__secondary_linked_graphic_rotation:
            self.__cw_270_button.set()
        else:
            self.__cw_270_button.reset()
        
    def __secondary_linked_graphic_cw_90_rotation_scan(self,_, is_on):
        """
        Callback function from the button that sets that a CW 180 rotation scan should be done 
        on the secondary linked graphic.

        Parameters:
        - _: Placeholder parameter.
        - is_on: Boolean indicating whether the rotation scan is turned on or off.

        Returns:
        None
        """

        if not is_on:
            if Template_Rotate.CW_90 in self.__secondary_linked_graphic_rotation:
                self.__secondary_linked_graphic_rotation.remove(Template_Rotate.CW_90)
        else:
            if Template_Rotate.CW_90 not in self.__secondary_linked_graphic_rotation:
                self.__secondary_linked_graphic_rotation.append(Template_Rotate.CW_90)
        self.__secondary_linked_graphic_view.set_template_rotate(self.__secondary_linked_graphic_rotation)
        self.__save_to_database()


    def __secondary_linked_graphic_cw_180_rotation_scan(self,_, is_on):
        """
        Callback function from the button that sets that a CW 180 rotation scan should be done 
        on the secondary linked graphic.

        Parameters:
        - _: Placeholder parameter.
        - is_on: Boolean indicating whether the rotation scan is turned on or off.

        Returns:
        None
        """
        
        if not is_on:
            if Template_Rotate.CW_180 in self.__secondary_linked_graphic_rotation:
                self.__secondary_linked_graphic_rotation.remove(Template_Rotate.CW_180)
        else:
            if Template_Rotate.CW_180 not in self.__secondary_linked_graphic_rotation:
                self.__secondary_linked_graphic_rotation.append(Template_Rotate.CW_180)
        
        self.__secondary_linked_graphic_view.set_template_rotate(self.__secondary_linked_graphic_rotation)
        self.__save_to_database()

    def __secondary_linked_graphic_cw_270_rotation_scan(self,_, is_on):
        """
        Callback function from the button that sets that a CW 270 rotation scan should be done 
        on the secondary linked graphic.

        Parameters:
        - _: Placeholder parameter.
        - is_on: Boolean indicating whether the rotation scan is turned on or off.

        Returns:
        None
        """
        if not is_on:
            if Template_Rotate.CW_270 in self.__secondary_linked_graphic_rotation:
                self.__secondary_linked_graphic_rotation.remove(Template_Rotate.CW_270)
        else:
            if Template_Rotate.CW_270 not in self.__secondary_linked_graphic_rotation:
                self.__secondary_linked_graphic_rotation.append(Template_Rotate.CW_270)
        
        self.__secondary_linked_graphic_view.set_template_rotate(self.__secondary_linked_graphic_rotation)
        self.__save_to_database()
        

    def document_selection_subscription(self, subscription):
        """
        Subscribe to the selection event and register the callback functions to document viewer events.

        :param subscription: The subscription object for the selection event.
        :type subscription: Subscription

        :return: None
        :rtype: None

        This method is used to subscribe to the selection event and register the callback functions. The subscription object is passed as a parameter, which represents the subscription to the selection event. The callback functions are used to handle different events related to the selection, such as document selection, page number selection, selected text, full page image, and text mark.

        Example:
            >>> document_selection_subscription(subscription)
        """
        
        subscription(self.__document_selection_subscription_callback, 
                        self.__document_or_page_number_callback,
                        self.__selected_text_callback,
                        self.__full_page_image,
                        text_mark_callback=self.__text_mark_callback)
        
    def __document_selection_subscription_callback(self, selected , **kwargs): 
        """
        Callback function for document selection subscription from document viewer panel.

        :param selected: Indicates if a document is selected or not.
        :type selected: bool
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict

        :return: None
        :rtype: None

        This function is called when a document is selected or deselected. It handles the logic for moving the document viewer to the requested location, clearing text regions of interest (ROI) in the document, getting the selected ROI, and refreshing the ROIs. It also calls the document_selection_subscription function for the primary linked graphic view, secondary linked graphic view, object parameter screen, and subobject parameter screen.

        Example:
            >>> __document_selection_subscription_callback(True, move_to_roi_func=move_func, clear_shown_text_roi_list=clear_func, roi_select_func=roi_func, refresh_roi=refresh_func)
        """
        
        if kwargs:  
            # Get the function callback from the document viewer panel 
            # responsible for moving the document viewer to the requested location
            self.__move_to_roi_func = kwargs.get('move_to_roi_func',None)

            # Get the function callback from the document viewer panel 
            # responsible for clearing text roi in the document
            self.__clear_shown_text_roi_list_func = kwargs.get('clear_shown_text_roi_list',None)

            # Get the function callback from the document viewer panel 
            # responsible for geting the selected region of interest
            self.__get_selected_roi_func = kwargs.get('roi_select_func',None)

            # Send document selected for text regions back to the docuemnt viewr to allow copying text
            self.__send_document_selected_text_func = kwargs.get('send_document_selected_text_func',None)


            self.__draw_roi_trigger_func = kwargs.get('draw_roi_trigger_func',None)


            self.__refresh_rois_func = kwargs.get('refresh_roi',None)
            self.__primary_linked_graphic_view.setup_text_roi_callback_func(self.__setup_text_roi_doc_viewer)
            self.__secondary_linked_graphic_view.setup_text_roi_callback_func(self.__setup_text_roi_doc_viewer)

        self.__primary_linked_graphic_view.document_selection_subscription(selected, **kwargs)
        self.__secondary_linked_graphic_view.document_selection_subscription(selected, **kwargs)
        self.__object_parameter_screen.document_selection_subscription(selected, **kwargs)
        self.__subobject_parameter_screen.document_selection_subscription(selected, **kwargs)


        if selected:
            self.__get_selected_roi()

    def __text_mark_callback(self, linked_text, parameter):
        """
        Marks text based on the provided regex string and ignore indexes.

        :param regex_string: The regular expression string used to match text.
        :type regex_string: str
        :param ignore_indexes: The indexes of text to be ignored.
        :type ignore_indexes: list
        
        :return: None
        :rtype: None
        
        This function applies the ignore_text method to both the object parameter screen and the subobject parameter screen using the provided regex string and ignore indexes.
        
        Example:
            >>> __text_mark_callback(, [0, 2])
            None
        """
        #self.__object_parameter_screen.ignore_text(linked_text, parameter)
        self.__subobject_parameter_screen.ignore_text(linked_text, parameter)


    def __get_selected_roi(self):
        """
        Retrieves the selected region of interest (ROI) and checks to see if the ROI is a text ROI. If
        it is a text ROI, the text is retrieved and stored in the __document_selected_text variables which
        can be used to link text to the control module. 

        :return: None
        :rtype: None

        """
        if not self.__get_selected_roi_func:
            if self.__send_document_selected_text_func: 
                self.__send_document_selected_text_func()
            return 
        
        try:
            roi_uid, _, pno, path, _, _, _ = self.__get_selected_roi_func()

            if (self.__primary_linked_graphic_data is not None and 
                'text_location_dict' in self.__primary_linked_graphic_data):

                primary_text_dict = self.__primary_linked_graphic_data['text_location_dict']
            
                if (roi_uid in primary_text_dict and primary_text_dict[roi_uid]['pno']==pno and
                primary_text_dict[roi_uid]['path']==path):

                    self.__document_selected_text_roi_name = roi_uid

                    self.__document_selected_text_indexes = [0,-1]
                    
                    text = ''
                    for char in primary_text_dict[roi_uid]['text_dict']:
                        text = text + char['c'] 
                    self.__document_selected_text = text

                    if self.__send_document_selected_text_func: 
                        self.__send_document_selected_text_func(self.__document_selected_text)

                    return
            

            if (self.__secondary_linked_graphic_data is not None and 
                'text_location_dict' in self.__secondary_linked_graphic_data):     

                secondary_text_dict = self.__secondary_linked_graphic_data['text_location_dict']    
                
                if (roi_uid in secondary_text_dict and secondary_text_dict[roi_uid]['pno']==pno and
                    secondary_text_dict[roi_uid]['path']==path):

                    self.__document_selected_text_roi_name = roi_uid

                    self.__document_selected_text_indexes = [0,-1]

                    text = ''
                    for char in secondary_text_dict[roi_uid]['text_dict']:
                        text = text + char['c'] 
                    self.__document_selected_text = text

                    if self.__send_document_selected_text_func: 
                        self.__send_document_selected_text_func(self.__document_selected_text)

        except Exception as e:
            return


    def __setup_text_roi_doc_viewer(self):
        self.__primary_linked_graphic_view.set_document_viewer_text_locations()
        self.__secondary_linked_graphic_view.set_document_viewer_text_locations()


    def clear_text_in_document_viewer_panel(self):
        if self.__clear_shown_text_roi_list_func:
            self.__clear_shown_text_roi_list_func()


    def __document_or_page_number_callback(self,path,pno):
        """
        Callback function sent by document viewer panel that sets the document viewer path and page number for the primary and secondary linked graphic views.

        :param path: The path of the document viewer.
        :type path: str
        :param pno: The page number of the document viewer.
        :type pno: int

        :return: None
        :rtype: None

        This function sets the document viewer path and page number for both the primary and secondary linked graphic views.
        """
        self.__primary_linked_graphic_view.set_document_viewer_path_and_page(path,pno)
        self.__secondary_linked_graphic_view.set_document_viewer_path_and_page(path,pno)


    def __full_page_image(self,path,pno,image,pdf_zoom,svg_page):
        """
        Callback function that sets the full page image for the primary and secondary linked graphic views sent by document viewer panel.

        :param path: The path of the image.
        :type path: str
        :param pno: The page number.
        :type pno: int
        :param image: The image to be set.
        :type image: Image object
        :param pdf_zoom: The zoom level for the PDF.
        :type pdf_zoom: float
        :param svg_page: The SVG page.
        :type svg_page: SVG object

        :return: None
        :rtype: None

        Sets the full page image for the primary and secondary linked graphic views using the provided image, PDF zoom level, and SVG page.

        Example:
            >>> __full_page_image('/path/to/image', 1, image_obj, 1.5, svg_obj)
        """
        
        self.__full_page_image = image
        self.__primary_linked_graphic_view.set_full_page_image(image, pdf_zoom)
        self.__secondary_linked_graphic_view.set_full_page_image(image, pdf_zoom)


    def __selected_text_callback(self, selected_text,path,pno,type):
        """
        Callback function for handling selected text.

        :param selected_text: The selected text.
        :type selected_text: str
        :param path: The file path.
        :type path: str
        :param pno: The page number.
        :type pno: int
        :param type: The type of the selected text (Database.DRAWING, Database.TEXT, Database.TABLE).
        :type type: int

        :return: None
        :rtype: None

        This function handles the selected text based on its type.
        If the type is Database.DRAWING, it calls __drawing_text_selection.
        If the type is Database.TEXT, it calls __text_document_text_selection.
        If the type is Database.TABLE, it calls __table_text_selection.
        """
       
        if type == Database.DRAWING or type == Database.IMAGE:
            self.__drawing_text_selection(selected_text, path, pno)
        if type == Database.TEXT:
            self.__text_document_text_selection(selected_text, path, pno)
        if type == Database.TABLE:
            self.__table_text_selection(selected_text, path, pno)


    def __table_text_selection(self, selected_text, path, pno):
        pass

    def __text_document_text_selection(self, selected_text, path, pno):
        pass

    def __drawing_text_selection(self, selected_text, path, pno):
        """
        Process the selected text from a drawing type document sent by document viewer panel.

        :param selected_text: The selected text.
        :type selected_text: list
        :param path: The path of the document.
        :type path: str
        :param pno: The page number of the document.
        :type pno: int

        :return: None
        :rtype: None
        """
        self.__document_selected_text = ''
        self.__document_selected_text_path = path
        self.__document_selected_text_pno = pno

        if not selected_text:
            if self.__send_document_selected_text_func:
                self.__send_document_selected_text_func()
            return

        self.__document_selected_text_roi_name = selected_text[0][0][:-9]

        self.__document_selected_text_indexes = [10000,-1]

        for text in selected_text:
            if self.__document_selected_text_indexes[0] > int(text[3]): 
                self.__document_selected_text_indexes[0] = int(text[3])

            if self.__document_selected_text_indexes[1] < (int(text[3]) + 1): 
                self.__document_selected_text_indexes[1] = int(text[3]) + 1

            self.__document_selected_text = self.__document_selected_text + text[2]

        if self.__send_document_selected_text_func:
            self.__send_document_selected_text_func(self.__document_selected_text)




    def __move_to_roi(self):    
        """
        Moves to the region of interest (ROI) on the document viewer panel based on the given parameters.
        
        :return: None
        :rtype: None

        This method checks if the move_to_roi_func, go_to_roi_uid, and go_to_pno are not None.
        If all conditions are met, it calls the move_to_roi_func with the go_to_roi_uid and go_to_pno as arguments.
        After the function call, it sets go_to_roi_uid and go_to_pno to None.
        """
        if self.__move_to_roi_func and self.__go_to_roi_uid and self.__go_to_pno is not None:
            self.__move_to_roi_func(self.__go_to_roi_uid,self.__go_to_pno)
            self.__go_to_roi_uid = None 
            self.__go_to_pno = None 

    def document_selected_func(self, func):
        self.__document_selected_func = func

    def __redraw_config_canvas(self,_=None):
        """
        Redraws the configuration canvas.

        :param _ : Placeholder parameter. Ignored.
        :type _: optional

        :return: None
        :rtype: None

        This method is responsible for redrawing the configuration canvas. It deletes any existing static elements and then redraws the screen label, name label, primary linked graphic view, divider lines, flow direction label, flow direction description, flow direction buttons, scan rotation label, and scan rotation description. It also resizes the scroll region of the canvas.
        """
        self.__delete_static_elements()
        self.screen_label.draw(0,0)
        self.name_label.draw(0,0)
        primary_height = self.__primary_linked_graphic_view.draw(0,0)
        self.__divider_line_A.draw(primary_height)
        self.__secondary_linked_graphic_view.draw(0,primary_height)
        self.__resize_scroll_region()


    def __delete_static_elements(self):
        """
        Deletes the static elements from the canvas.

        :return: None
        :rtype: None

        This method deletes the flow direction description and scan rotation description
        from the canvas if they exist.
        """
        if self.__flow_direction_description:
            self.canvas.delete(self.__flow_direction_description)
            self.canvas.delete(self.__scan_rotation_description)


    def __select_flow_direction(self, selection):
        """
        Sets the flow direction to the given selection and saves it to the database.

        :param selection: The selection representing the flow direction.
        :type selection: list

        :return: None
        :rtype: None
        """
        self.__flow_direction = selection
        self.__save_to_database()


    def __resize_scroll_region(self):
        """
        Resizes the scroll region of the canvas based on the bounding box of all items on the canvas.

        :return: None
        :rtype: None

        If the canvas exists and there are items on the canvas, the scroll region is resized to include all items plus an additional 100 units in the y-direction.
        """
        if self.canvas and self.canvas.bbox(tk.ALL):  
            self.canvas.config(scrollregion=(0,0,self.canvas.bbox(tk.ALL)[2],self.canvas.bbox(tk.ALL)[3]+100))


    def __linked_graphic_change(self):
        """
        This method is responsible for handling the linked graphic change event.

        :return: None
        :rtype: None 

        It retrieves the linked graphic data from the primary and secondary linked graphic views.
        If the 'path' key is not present in the primary linked graphic data, the method returns.
        Otherwise, it assigns the 'path' and 'pno' values from the primary linked graphic data to the corresponding instance variables.
        Then, it saves the data to the database and sets up the text ROI document viewer.
        """
        self.__primary_linked_graphic_data = self.__primary_linked_graphic_view.get_linked_graphic_data()
        self.__secondary_linked_graphic_data = self.__secondary_linked_graphic_view.get_linked_graphic_data()
        
        if 'path' not in self.__primary_linked_graphic_data:
            return 

        self.__path = self.__primary_linked_graphic_data['path']
        self.__pno = self.__primary_linked_graphic_data['pno']
        self.__save_to_database()
        self.__setup_text_roi_doc_viewer()


    def __find_connection_between_linked_graphics(self, primary_poi, secondary_poi, image_to_search):
        grid = image_to_search.astype(np.float32)
        grid[grid == 0] = 1
        grid[grid == 255] = 16

        for i in range(len(primary_poi)):
            start = np.array(primary_poi[i])
            start = start*2

            for j in range(len(secondary_poi)):
                end = np.array(secondary_poi[j])

                t0 = time.time()
                
                end = end*2
                path = pyastar2d.astar_path(grid, [start[1],start[0]], [end[1],end[0]], allow_diagonal=False)
                dur = time.time() - t0

                if path is None:
                    continue

                if path.shape[0] > 0:
                    path = path
                    xs, ys = self.__straighten_lines(path)  
                    
                    cost = np.array([grid[point[0],point[1]] for point in path],dtype=int)
                    maze = np.stack((image_to_search, image_to_search, image_to_search), axis=2)
                    pts = np.flip(path, 1)
                    pts = pts.reshape((-1, 1, 2))
                    #maze = cv2.polylines(maze, [pts], 
                    #        False, (0,0,255), 5)
                    #cv2.imshow('test',cv2.resize(maze,(1500,int(maze.shape[0]*1500/maze.shape[1]))))
                    #cv2.waitKey(0)
                    return np.sum(cost).tolist(), (xs, ys), pts.tolist()
                else:
                    return None 


    


    def delete_from_database(self):
        """
        Deletes the current object from the database.

        :return: None
        :rtype: None

        This method calls the private method __delete_all_from_database() to delete all related records from the database.
        """
        self.__delete_all_from_database()


    def __delete_all_from_database(self):
        """
        Deletes all data for the current control module from the database.

        :returns: None
        :rtype: None
        
        This function deletes all data for the control module from the database. This 
        includes the control module itself and the linked text. Lastly if the control module
        was a not template then the regions-of-interests (ROIs) are deleted from the document.
        """

        is_template = self.__delete_control_module_from_database()

        if is_template :
            return 

        roi_to_delete = []
        roi_to_delete = roi_to_delete + self.__primary_linked_graphic_view.get_all_roi_ids()
        roi_to_delete = roi_to_delete + self.__secondary_linked_graphic_view.get_all_roi_ids()

        roi_list = self.__db.get_project_document_roi(self.__path)
        for pno, roi in roi_to_delete:
            try:
                if roi_list[pno]: del(roi_list[pno][roi])
            except KeyError:
                pass

        
        self.__save_page_roi(self.__path,roi_list)
        if self.__refresh_rois_func:
            self.__refresh_rois_func()

        logging.info('Deleted {} Control Module with ID: {} with ROIs '.format(self.name, self.id))


    def __delete_control_module_from_database(self):
        """
        Deletes the control module from the database.

        :return: True if the control module is successfully deleted, False otherwise.
        :rtype: bool
        """
        
        logging.info('Deleting '+self.name+' Control Module with ID: '+self.id)

        deleted = self.__db.delete_control_module_by_id(self.id)
        if not deleted:
            self.__db.delete_control_module(self.name)

        if self.__db.get_control_module_graphic_template_by_id(self.id):
            self.__db.delete_control_module_template(self.id)
            logging.info('Deleted {} Control Module with ID: {} without ROIs '.format(self.name, self.id))
            return True 

        return False 



    def __save_to_database(self):
        """
        Saves the control module data to the database.

        :return: None
        :rtype: None

        This method checks if the control module is busy loading data from the database. If it is, the method returns without saving anything.
        If the primary linked graphic data is None or the 'roi_uid' is None, the method returns without saving anything.
        If the 'roi_uid' is present in the primary linked graphic data but the PRIMARY_GRAPHIC_TYPE is not in the 'roi_uid', the method updates the 'roi_uid' and saves the page ROI.
        If the 'roi_uid' is present in the secondary linked graphic data but the SECONDARY_GRAPHIC_TYPE is not in the 'roi_uid', the method updates the 'roi_uid' and saves the page ROI.
        Finally, the method constructs a dictionary with the control module data and saves it to the database using the __db object. It also saves the control module graphic template to the database and calls the linked callback function.
        """

        # prevents writing to database if busy loading data form database
        if self.__busy_loading_data:
            return 

        if self.__primary_linked_graphic_data is None:
            return 

        if self.__primary_linked_graphic_data['roi_uid'] is None:
            return

        if ('roi_uid' in self.__primary_linked_graphic_data and 
            (self.PRIMARY_GRAPHIC_TYPE not in self.__primary_linked_graphic_data['roi_uid'])):
            roi_list, self.__primary_linked_graphic_data = self.__update_roi_uid(
                                                                self.__primary_linked_graphic_data
                                                                ,self.PRIMARY_GRAPHIC_TYPE)
            self.__primary_linked_graphic_view.set_link_graphic_data(self.__primary_linked_graphic_data)
            self.__save_page_roi(self.__path,roi_list)
            self.__update_roi_name_func(primary_roi_name=self.__primary_linked_graphic_data['roi_uid'])


        if ('roi_uid' in self.__secondary_linked_graphic_data and 
            (self.SECONDARY_GRAPHIC_TYPE not in self.__secondary_linked_graphic_data['roi_uid'])):
            roi_list, self.__secondary_linked_graphic_data = self.__update_roi_uid(
                                                                self.__secondary_linked_graphic_data
                                                                ,self.SECONDARY_GRAPHIC_TYPE
                                                                ,self.__primary_linked_graphic_data['roi_uid'])
            
            self.__secondary_linked_graphic_view.set_link_graphic_data(self.__secondary_linked_graphic_data)
            self.__save_page_roi(self.__path,roi_list)
            self.__update_roi_name_func(secondary_roi_name=self.__secondary_linked_graphic_data['roi_uid'])


        dict_data = {
            'id': self.__primary_linked_graphic_data['roi_uid'],
            'name': self.name,
            'description': self.description,
            'type': self.group_id,
            'path': self.__path,
            'pno': self.__pno,
            'primary_linked_graphic': self.__primary_linked_graphic_data,
            'secondary_linked_graphic': self.__secondary_linked_graphic_data,
            'linked_text':self.__linked_text,
            'flow_direction':self.__flow_direction,
            'template_rotation':[item.value for item in self.__secondary_linked_graphic_rotation]
        }

        self.__db.save_control_module(dict_data)
        self.__db.save_control_module_graphic_template(dict_data)
        self.__linked_callback()


    def __update_roi_uid(self, linked_graphic_data,object_type,object_id=''):
        """
        Updates the region-of-interest (ROI) UID based on the linked graphic data.

        :param linked_graphic_data: The linked graphic data.
        :type linked_graphic_data: dict
        :param object_type: The type of the object.
        :type object_type: str
        :param object_id: The ID of the object (optional).
        :type object_id: str, optional
        
        :return: The updated region-of-interest (ROI) list and linked graphic data.
        :rtype: tuple
        """
        roi_list = self.__db.get_project_document_roi(self.__path)

        roi = linked_graphic_data['roi']
        pno = linked_graphic_data['pno']

        minX = int(min(l[0] for l in roi))
        minY = int(min(l[1] for l in roi))
        maxX = int(max(l[0] for l in roi))
        maxY = int(max(l[1] for l in roi))

        roi_uid = (str(pno) +'-'+ str(minX) +'-'+ str(minY) 
                    +'-'+ str(maxX) +'-'+ str(maxY) +'-'+object_type)

        if object_id != '':
            roi_uid = roi_uid +'-'+ object_id
        roi_list[pno].pop(linked_graphic_data['roi_uid'], None)

        roi_list[pno][roi_uid]=roi
        linked_graphic_data['roi_uid']=roi_uid

        return roi_list, linked_graphic_data




    def __get_data_from_database(self):
        """
        Retrieves data from the database and updates the control module's attributes accordingly.

        :return: None
        :rtype: None

        If the control module's group ID is 'Unassigned', it retrieves the control module by ID.
        Otherwise, it retrieves the control module by name.
        If data is found, it updates the primary and secondary linked graphic views, linked text,
        flow direction, template rotation, and sets up the text ROI document viewer.
        """
        
        self.__busy_loading_data = True

        if self.__db:
            
            if self.group_id == 'Unassigned':
                data = self.__db.get_control_module_by_id(self.id)
            else:
                data = self.__db.get_control_module(self.name)
            
            if data:
                self.__primary_linked_graphic_view.set_link_graphic_data(data['primary_linked_graphic'])
                self.__secondary_linked_graphic_view.set_link_graphic_data(data['secondary_linked_graphic'])
                if 'linked_text' in data.keys():
                    self.__linked_text = data['linked_text']
                if 'flow_direction' in data.keys():
                    self.__flow_direction = data['flow_direction']
                    
                if 'template_rotation' in data.keys():
                    self.__secondary_linked_graphic_rotation = [Template_Rotate(item) for item in data['template_rotation']]
                    self.__secondary_linked_graphic_view.set_template_rotate(self.__secondary_linked_graphic_rotation)
                self.__setup_text_roi_doc_viewer()
        

        self.__busy_loading_data = False
               


    def draw_linked_text(self):
        """
        Draws linked text on the screen.

        :return: None
        :rtype: None

        This method iterates over the linked text dictionary and draws each linked text on the screen.
        It retrieves the start and end indexes of each linked text and calls the `primary_link_text` method
        of the `name_entry` object to draw the linked text as retangles above the linked text entry.
        """
        for _, linked_texts in self.__linked_text.items():
            for _, linked_text in linked_texts['links'].items():
                    start = linked_text['indexes'][0]
                    end = linked_text['indexes'][1]
                    self.__name_entry.primary_link_text(start,end)




    def start_document_scan(self,page_index=None):
        """
        Starts the document scan process.

        :return: None
        :rtype: None

        :raises OSError: If scanning is already in progress.
        :raises ValueError: If an exception is raised while starting the scan.

        This method starts the document scan process by calling the start_scan method of the primary linked graphic view.
        If scanning is already in progress, an OSError is raised.
        If an exception is raised while starting the scan, a ValueError is raised.
        """
        # Only the primary linked graphic should raise exceptions

        if self.__scanning_started:
            raise OSError('Please wait. Busy scanning already.')
        
        if not self.__linked_text:
            raise ValueError('No linked text. Please link text first before scanning.')
        
        try:
            self.__primary_linked_graphic_view.start_scan()
        except Exception as error:
            raise ValueError(error)

        self.__scanning_started = True
        self.__primary_scanning_count = 0
        self.__secondary_scanning_count = 0
        self.__primary_scan_times = []
        self.__secondary_scan_times = []
        self.__filtered_new_control_modules_id = []
        self.__new_overlapping_control_modules_id = set()
        self.__old_overlapping_control_modules_id = set()
        self.__primary_graphic_scanning_done = False
        self.__secondary_graphic_scanning_done = False

        self.__secondary_scan_started = self.__secondary_linked_graphic_view.start_scan(template_rotate=self.__secondary_linked_graphic_rotation)
        



    def start_page_scan(self):
        """
        Starts the page scan process.

        :param page_index: The page index to scan.
        :type page_index: int

        :return: None
        :rtype: None

        :raises OSError: If scanning is already in progress.
        :raises ValueError: If an exception is raised while starting the scan.

        This method starts the document scan process by calling the start_scan method of the primary linked graphic view.
        If scanning is already in progress, an OSError is raised.
        If an exception is raised while starting the scan, a ValueError is raised.
        """
        # Only the primary linked graphic should raise exceptions
        
        if not self.__get_selected_roi_func:
            raise ValueError('No page open. Please open a document page first before testing.') 
        

        _, _, pno, path, _, _, _ = self.__get_selected_roi_func()
        
        if not self.__linked_text:
            raise ValueError('No linked text. Please link text first before scanning.')
        
        

        
        if self.__scanning_started:
            raise OSError('Please wait. Busy scanning already.')
        try:
            self.__primary_linked_graphic_view.start_scan(page_index=pno)
        except Exception as error:
            raise ValueError(error)
        
        self.__primary_scanning_count = 0
        self.__secondary_scanning_count = 0
        self.__primary_scan_times = []
        self.__secondary_scan_times = []
        self.__filtered_new_control_modules_id = []
        self.__new_overlapping_control_modules_id = set()
        self.__old_overlapping_control_modules_id = set()

        self.__scanning_started = True
        self.__primary_graphic_scanning_done = False
        self.__secondary_graphic_scanning_done = False

        self.__secondary_scan_started = self.__secondary_linked_graphic_view.start_scan(template_rotate=self.__secondary_linked_graphic_rotation,page_index=pno)
  
        
    def find_similar_primary_from_image(self, matcher, image, page_index=None, callback=None,document_type=Database.DRAWING):
        """
        Finds the primary linked graphic in the given image.

        Args:
            image (numpy.ndarray): The image to search for the primary linked graphic.

        Returns:
            None
        """

        if not self.__linked_text:
            raise ValueError('No linked text. Please link text first before scanning.')

        self.__done_building_func.append(callback)
        try:
            result = self.__primary_linked_graphic_view.find_similar_from_image(matcher,image,page_index=page_index,document_type=document_type)
            result.append(self.__test_new_graphic_link)
            return result
        except Exception as error:
            raise ValueError(error)
        
    
    def add_graphic_link(self,roi_uid,pno,new_template_mask,template_flip,template_rotate
                         ,page_index,scale_factor,document_type,add_template_image=False):
        """
        Adds a graphic link to the primary linked graphic view.
        """
        
        self.__primary_linked_graphic_view.add_graphic_link(roi_uid,pno,new_template_mask,template_flip,template_rotate
                                                            ,page_index,scale_factor,document_type,add_template_image=add_template_image)
        self.__primary_graphic_scanning_done = False

    def __test_new_graphic_link(self,roi_uid,pno,new_template_mask,template_flip,template_rotate,document_type=Database.DRAWING):

        self.__primary_linked_graphic_view.new_graphic_search(roi_uid,pno,new_template_mask,template_flip,template_rotate
                            ,document_type)



    def find_similar_secondary_from_image(self,matcher, image, page_index=None, callback=None,document_type=Database.DRAWING):
        """
        Finds the secondary linked graphic in the given image.

        Args:
            image (numpy.ndarray): The image to search for the secondary linked graphic.

        Returns:
            None
        """
        self.__done_building_func.append(callback)
        try:
            self.__secondary_linked_graphic_view.find_similar_from_image(matcher,image,template_rotate=self.__secondary_linked_graphic_rotation
                                                                         ,page_index=page_index,document_type=document_type)
        except Exception as error:
            raise ValueError(error)
        self.__secondary_graphic_scanning_done = False
        self.__secondary_scan_started = True


    def check_scanner_progress(self):
        """
        Check the progress of the scanner.
        
        :return: A tuple containing the following information:
                - total_number_of_tasks (int): The total number of tasks.
                - total_number_done (int): The total number of tasks done.
                - percentage (float): The percentage of tasks completed.
                - done (bool): Indicates if the scanning is done.
                - error (str): Error message, if any.
        :rtype: tuple
        """
        total_number_of_tasks,total_number_done, _ , done_scanning, error, cancel_scan_1 = self.__primary_linked_graphic_view.check_scanner_progress()

        cancel_scan_funcs = [cancel_scan_1]

        if self.__secondary_scan_started:
            number_of_tasks_2,number_done_2, _ , done_2, error_2, cancel_scan_2 = self.__secondary_linked_graphic_view.check_scanner_progress()
        
            cancel_scan_funcs.append(cancel_scan_2)

            total_number_of_tasks = total_number_of_tasks + number_of_tasks_2
            total_number_done = total_number_done + number_done_2

            done_scanning = done_scanning and done_2
            if error :
                error = 'Control Module named "'+self.name+'" Primary Graphic '+error
            elif error_2 :
                error = 'Control Module named "'+self.name+'" Secondary Graphic '+error_2


        if (done_scanning or error) and not self.__secondary_scan_started:
            self.__scanning_started = False

        if total_number_of_tasks: 
            percentage = total_number_done/total_number_of_tasks
        else:
            percentage = 1.0

        done_saving = self.__db.check_if_save_bulk_control_modules_threads_finished() and done_scanning and self.__processed_all_primary_results()

        self.__primary_scanning_count = len(self.__filtered_new_control_modules_id)

        if self.__secondary_scan_started:
            count = [self.__primary_scanning_count,self.__secondary_scanning_count]
        else:
            count = [self.__primary_scanning_count]

        return (total_number_of_tasks, total_number_done, percentage
                ,done_scanning,count,done_saving,['Control Modules', 'Secondary Graphics'], error, cancel_scan_funcs)



    def check_pairing_progress(self):
        """
        Check the progress of the graphic pairing process.

        :return: A tuple containing the following information:
                - total_number_of_tasks (int): The total number of tasks in the pairing process.
                - total_number_done (int): The total number of tasks that have been completed.
                - percentage (float): The percentage of tasks completed.
                - done (bool): Indicates whether the pairing process is done or not.
                - error (str): If an error occurred during the pairing process, the error message is provided. Otherwise, it is an empty string.
        :rtype: tuple: 
        """
        total_number_of_tasks,total_number_done, _ , done, error = self.__linked_graphic_pairing.check_multiprocess_graphic_pairing_progress()
        
        if done or error:
            self.__scanning_started = False

        if total_number_of_tasks: 
            percentage = total_number_done/total_number_of_tasks
        else:
            percentage = 1.0

        if error:
            error = 'Control Module named "'+self.name+'" Pairing ' + error

        return (total_number_of_tasks, total_number_done, percentage,done, error)




    def __build_from_primary_linked_graphic(self, results):
        """
        Builds control modules from the primary linked graphic.

        :param results: List of results containing ROI information.
        :type results: list

        :return: None
        :rtype: None

        Builds control modules from the primary linked graphic by iterating through the results and extracting relevant information. It then calls the __build_new_control_module method to create new control modules based on the extracted information. Finally, it saves the page ROI data and logs the average scan time.

        Example:
            >>> __build_from_primary_linked_graphic(results)
        """
        
        self.__primary_linked_graphic_data = self.__primary_linked_graphic_view.get_linked_graphic_data()
        path = ""
        roi_list = None

        scan_times = []
        self.__primary_scanning_count = 0
        
        for result_roi_list, page_index, scan_time, template_to_match_ratio in results:

            scan_times.append(scan_time)

            for roi in result_roi_list:

                if roi_list is None:
                    path = roi['path']
                    roi_list = self.__db.get_project_document_roi(path)

                text_locations = roi['text_locations']
                list = []
                linked_text_to_search ={}
                character_differences = [] 
                for text_location in text_locations:
                    list.append(self.__get_substring_of_text_location(text_location,linked_text_to_search,character_differences))
            
                for linked_text_name, text_to_search in linked_text_to_search.items():
                    #if text_to_search == self.name:
                    #    continue

                    if linked_text_name != 'Name':
                        continue

                    if ((self.group_id == 'Unassigned') or 
                            ( self.__acm_data_handler.is_object_in_project(text_to_search,self.group_id))):

                        self.__build_new_control_module(path, page_index, roi, text_to_search, text_locations, character_differences, template_to_match_ratio)

        self.__save_page_roi(path,roi_list,False)
        self.__primary_scanning_count = len(self.__new_control_modules)

        average_scan_time = sum(scan_times)/len(scan_times)
        logging.info('Average time to scan for Primary Linked Graphic: {}s per page'.format(str(average_scan_time)))
        logging.info('Done building Control Modules from Primary Linked Graphic')

        #if self.__refresh_rois_func:
        #    self.__refresh_rois_func()

        if not self.__secondary_scan_started:
            self.__write_new_control_modules_to_db(path)
            self.__remove_background_task_callback_func(self.id)



    def __process_single_primary_result(self, result, done_scanning=False):
        """ Processes a single result from the primary linked graphic scan.

        :param result: The result to process.
        :type result: dict

        :return: None
        :rtype: None

        """
        
        # Run the processing in a separate thread to avoid blocking the UI
        thread = threading.Thread(
            target=self.__process_single_primary_result_threaded,
            args=(result, done_scanning)
        )
        thread.start()

        self.__primary_single_results_being_processed.append(thread)

    
    def __processed_all_primary_results(self):

        all_processed = True

        for thread in self.__primary_single_results_being_processed:
            thread.join(timeout=0.1)
            if thread.is_alive():
                all_processed = False

        self.__primary_single_results_being_processed = [t for t in self.__primary_single_results_being_processed if t.is_alive()]

        return all_processed



    def __process_single_primary_result_threaded(self, result, done_scanning=False):
        """ Threaded version of processing a single result from the primary linked graphic scan.

        :param result: The result to process.
        :type result: dict
        :param done_scanning: Whether scanning is complete.
        :type done_scanning: bool

        :return: None
        :rtype: None

        """

        result_roi_list, page_index, scan_time, template_to_match_ratio = result

        self.__primary_scan_times.append(scan_time)

        new_control_modules = {}
        path = None

        for roi in result_roi_list:

                path = roi['path']
                roi_list = self.__db.get_project_document_roi(path)

                text_locations = roi['text_locations']
                list = []
                linked_text_to_search ={}
                character_differences = [] 
                number_of_text_found = 0
                for text_location in text_locations:
                    list.append(self.__get_substring_of_text_location(text_location,linked_text_to_search,character_differences))
                    number_of_text_found = number_of_text_found + len(text_location['text_dict'])

                if number_of_text_found == 0:
                    continue

                for linked_text_name, text_to_search in linked_text_to_search.items():
                    #if text_to_search == self.name:
                    #    continue

                    if not text_to_search or not text_to_search.strip():
                        continue

                    if linked_text_name != 'Name':
                        continue

                    self.__build_new_control_module(path, page_index, roi, text_to_search, text_locations, character_differences, template_to_match_ratio, new_control_modules)

        if len(result_roi_list) > 0 and path:
            self.__save_page_roi(path,roi_list,page_index=page_index)
            self.__write_new_control_modules_to_db(path, new_control_modules)
        logging.info('Done building Control Modules from Primary Linked Graphic for page index: {}'.format(page_index))


    
    def __process_single_secondary_result(self, result, done_scanning=False):
        """ Processes a single result from the secondary linked graphic scan.

        :param result: The result to process.
        :type result: dict

        :return: None
        :rtype: None

        """
        
        # Run the processing in a separate thread to avoid blocking the UI
        thread = threading.Thread(
            target=self.__process_single_secondary_result_threaded,
            args=(result, done_scanning),
            daemon=True
        )
        thread.start()

        self.__secondary_single_results_being_processed.append(thread)

    
    def __processed_all_secondary_results(self):

        all_processed = True

        for thread in self.__secondary_single_results_being_processed:
            thread.join(timeout=0.1)
            if thread.is_alive():
                all_processed = False

        self.__secondary_single_results_being_processed = [t for t in self.__secondary_single_results_being_processed if t.is_alive()]

        return all_processed
   


    def __process_single_secondary_result_threaded(self, result, done_scanning=False):
        """ Threaded version of processing a single result from the secondary linked graphic scan.

        :param result: The result to process.
        :type result: dict
        :param done_scanning: Whether scanning is complete.
        :type done_scanning: bool

        :return: None
        :rtype: None

        """

        result_roi_list, page_index, scan_time, template_to_match_ratio = result

        self.__secondary_scan_times.append(scan_time)

        for roi in result_roi_list:
            if page_index not in self.__secondary_poi_dict:
                self.__secondary_poi_dict[page_index] = []

            center = (int((roi['points'][0]+roi['points'][2])/2),int((roi['points'][1]+roi['points'][3])/2))


            self.__secondary_poi_dict[page_index].append((center,roi['points'],roi['flip'],roi['rotation'],template_to_match_ratio))

            self.__secondary_scanning_count = self.__secondary_scanning_count + 1

        self.__build_from_secondary_done = done_scanning
        self.__secondary_done_saving = done_scanning



 