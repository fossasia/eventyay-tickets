/*globals $, gettext, fabric, PDFJS*/
fabric.Poweredby = fabric.util.createClass(fabric.Image, {
    type: 'poweredby',

    initialize: function (options) {
        options || (options = {});

        var el = $("#poweredby-" + options.content).get(0)
        this.callSuper('initialize', el, options);
        this.set('label', options.label || '');
    },

    toObject: function () {
        return fabric.util.object.extend(this.callSuper('toObject'), {});
    },

    _render: function (ctx) {
        this.callSuper('_render', ctx);
    },
});
fabric.Poweredby.fromObject = function (object, callback, forceAsync) {
    return fabric.Object._fromObject('Poweredby', object, callback, forceAsync);
};
fabric.Imagearea = fabric.util.createClass(fabric.Rect, {
    type: 'imagearea',

    initialize: function (text, options) {
        options || (options = {});

        this.callSuper('initialize', text, options);
        this.set('label', options.label || '');
    },

    toObject: function () {
        return fabric.util.object.extend(this.callSuper('toObject'), {});
    },

    _render: function (ctx) {
        ctx.fillStyle = '#009'
        this.callSuper('_render', ctx);

        ctx.font = '12px Helvetica';
        ctx.fillStyle = '#fff';
        ctx.fillText(this.content, -this.width / 2, -this.height / 2 + 20, this.width);
    },
});
fabric.Imagearea.fromObject = function (object, callback, forceAsync) {
    return fabric.Object._fromObject('Imagearea', object, callback, forceAsync);
};
fabric.Barcodearea = fabric.util.createClass(fabric.Rect, {
    type: 'barcodearea',

    initialize: function (text, options) {
        options || (options = {});

        this.callSuper('initialize', text, options);
        this.set('label', options.label || '');
    },

    toObject: function () {
        return fabric.util.object.extend(this.callSuper('toObject'), {});
    },

    _render: function (ctx) {
        this.callSuper('_render', ctx);

        ctx.font = '16px Helvetica';
        ctx.fillStyle = '#fff';
        if (this.content === "pseudonymization_id") {
            ctx.fillText(gettext('Lead Scan QR'), -this.width / 2, -this.height / 2 + 20);
        } else {
            ctx.fillText(gettext('Check-in QR'), -this.width / 2, -this.height / 2 + 20);
        }
    },
});
fabric.Barcodearea.fromObject = function (object, callback, forceAsync) {
    return fabric.Object._fromObject('Barcodearea', object, callback, forceAsync);
};
fabric.Textarea = fabric.util.createClass(fabric.Textbox, {
    type: 'textarea',

    initialize: function (text, options) {
        options || (options = {});

        this.callSuper('initialize', text, options);
        this.set('content', options.content || '');
        this.autofit_width = editor._parse_autofit_width(options.autofit_width);
        if (typeof options.maxFontPt === 'number' && !isNaN(options.maxFontPt)) {
            this.maxFontPt = options.maxFontPt;
        }
    },

    initDimensions: function () {
        if (this.__skipDimension) {
            return;
        }
        this.isEditing && this.initDelayedCursor();
        this.clearContextTop();
        this._clearCache();
        this.dynamicMinWidth = 0;
        this._styleMap = this._generateStyleMap(this._splitText());
        if (this.textAlign.indexOf('justify') !== -1) {
            this.enlargeSpaces();
        }
        this.height = this.calcTextHeight();
        this.saveState({propertySet: '_dimensionAffectingProps'});
    },

    toObject: function(propertiesToInclude) {
        return this.callSuper('toObject', ['content', 'autofit_width', 'maxFontPt'].concat(propertiesToInclude));
    }
});
fabric.Textarea.fromObject = function (object, callback, forceAsync) {
    return fabric.Object._fromObject('Textarea', object, callback, forceAsync, 'text');
};


var editor = {
    $pdfcv: null,
    $fcv: null,
    $cva: null,
    $fabric: null,
    objects: [],
    history: [],
    clipboard: [],
    pdf_page: null,
    pdf_scale: 1,
    pdf_viewport: null,
    _history_pos: 0,
    _history_modification_in_progress: false,
    _toolbox_update_in_progress: false,
    dirty: false,
    pdf_url: null,
    uploaded_file_id: null,
    page_width_mm: null,
    page_height_mm: null,
    page_aspect_ratio: null,
    page_size_lock_aspect: false,
    _page_resize_in_progress: false,
    _page_size_timer: null,
    _window_loaded: false,
    _fabric_loaded: false,
    _last_active_object: null,
    _drag_start: null,
    _PAGE_SIZE_TOLERANCE: 0.05,
    _AUTOFIT_MIN_PT: 4,
    _NUDGE_MM: 1,
    _NUDGE_SHIFT_MM: 10,

    _px2mm: function (v) {
        return v / editor.pdf_scale / 72 * editor.pdf_page.userUnit * 25.4;
    },

    _mm2px: function (v) {
        return v * editor.pdf_scale * 72 / editor.pdf_page.userUnit / 25.4;
    },

    _px2pt: function (v) {
        return v / editor.pdf_scale * editor.pdf_page.userUnit;
    },

    _pt2px: function (v) {
        return v * editor.pdf_scale / editor.pdf_page.userUnit;
    },

    _get_text_max_font_pt: function (o) {
        if (typeof o.maxFontPt === 'number' && !isNaN(o.maxFontPt)) {
            return o.maxFontPt;
        }
        return editor._px2pt(o.fontSize);
    },

    _parse_autofit_width: function (value) {
        return value === true || value === 'true' || value === 1 || value === '1';
    },

    _compute_autofit_pt: function (o, maxPt, widthMm) {
        if (!o.autofit_width) {
            return maxPt;
        }

        var text = o.text || '';
        if (!text) {
            return maxPt;
        }

        maxPt = typeof maxPt === 'number' && !isNaN(maxPt) ? maxPt : editor._get_text_max_font_pt(o);
        widthMm = typeof widthMm === 'number' && !isNaN(widthMm) ? widthMm : editor._px2mm(o.width);

        var lines = text.split(/\r\n|\r|\n/).filter(function (line) {
            return line.length > 0;
        });
        if (!lines.length) {
            return maxPt;
        }

        var widthPx = editor._mm2px(widthMm);
        var canvas = document.createElement('canvas');
        var ctx = canvas.getContext('2d');
        var fontFamily = o.fontFamily || 'Open Sans';
        var fontWeight = o.fontWeight === 'bold' ? 'bold ' : '';
        var fontStyle = o.fontStyle === 'italic' ? 'italic ' : '';

        for (var pt = maxPt; pt >= editor._AUTOFIT_MIN_PT; pt -= 0.5) {
            ctx.font = fontStyle + fontWeight + editor._pt2px(pt) + 'px ' + fontFamily;
            var fits = true;
            for (var i = 0; i < lines.length; i++) {
                if (ctx.measureText(lines[i]).width > widthPx) {
                    fits = false;
                    break;
                }
            }
            if (fits) {
                return pt;
            }
        }
        return editor._AUTOFIT_MIN_PT;
    },

    _apply_autofit_fontsize: function (o, maxPt, widthMm) {
        maxPt = typeof maxPt === 'number' && !isNaN(maxPt) ? maxPt : editor._get_text_max_font_pt(o);
        o.maxFontPt = maxPt;
        o.set('fontSize', editor._pt2px(
            o.autofit_width ? editor._compute_autofit_pt(o, maxPt, widthMm) : maxPt
        ));
        if (o.initDimensions) {
            o.initDimensions();
        }
    },

    _csrf_token: function () {
        return $("input[name=csrfmiddlewaretoken]").val();
    },

    _nudge_px: function (shiftKey) {
        return editor._mm2px(shiftKey ? editor._NUDGE_SHIFT_MM : editor._NUDGE_MM);
    },

    _is_hotkey_target: function () {
        return !$("#source-container").is(':visible');
    },

    _get_active_object: function () {
        return editor.fabric ? editor.fabric.getActiveObject() : null;
    },

    _is_active_selection: function (o) {
        return !!(o && o.type === 'activeSelection');
    },

    _get_active_objects: function () {
        if (!editor.fabric) {
            return [];
        }
        var selected = editor.fabric.getActiveObjects();
        return selected ? selected.slice() : [];
    },

    _dump_selection: function (thing) {
        if (!thing) {
            return [];
        }
        if (editor._is_active_selection(thing)) {
            return editor.dump(thing.getObjects());
        }
        return editor.dump([thing]);
    },

    _set_selection: function (objs) {
        editor.fabric.discardActiveObject();
        if (!objs || !objs.length) {
            editor._update_toolbox();
            return;
        }
        if (objs.length === 1) {
            editor.fabric.setActiveObject(objs[0]);
            editor._last_active_object = objs[0];
        } else {
            editor.fabric.setActiveObject(new fabric.ActiveSelection(objs, {canvas: editor.fabric}));
        }
        editor.fabric.renderAll();
        editor._update_toolbox();
    },

    _remove_active: function () {
        var thing = editor._get_active_object();
        if (!thing) {
            return false;
        }
        if (editor._is_active_selection(thing)) {
            thing.forEachObject(function (o) {
                editor.fabric.remove(o);
            });
            editor.fabric.remove(thing);
        } else {
            editor.fabric.remove(thing);
        }
        editor.fabric.discardActiveObject();
        return true;
    },

    _object_abs_rect: function (o) {
        var r = o.getBoundingRect();
        return {left: r.left, top: r.top, width: r.width, height: r.height};
    },

    _snap_to_step: function (value, origin, step) {
        if (!step) {
            return value;
        }
        return origin + Math.round((value - origin) / step) * step;
    },

    _nudge_active: function (dx, dy, shiftKey) {
        var thing = editor._get_active_object();
        if (!thing) {
            return false;
        }
        var step = editor._nudge_px(shiftKey);
        thing.set({
            left: thing.get('left') + dx * step,
            top: thing.get('top') + dy * step
        });
        thing.setCoords();
        editor._create_savepoint();
        return true;
    },

    _focus_canvas: function () {
        var el = editor.$cva && editor.$cva.get(0);
        if (!el || typeof el.focus !== 'function') {
            return;
        }
        try {
            el.focus({preventScroll: true});
        } catch (err) {
            el.focus();
        }
    },

    _set_background_buttons_busy: function (busy, showUploadProgress) {
        editor._page_resize_in_progress = busy;
        $("#fileupload").prop("disabled", busy);
        $("#pdf-info-width, #pdf-info-height").prop("disabled", busy);
        $(".background-button").toggleClass("disabled", busy);
        if (showUploadProgress) {
            $("#loading-container, #loading-upload").show();
            $("#loading-upload .progress").show();
            $("#loading-upload .progress-bar").css("width", 0);
        }
    },

    _get_page_size_from_fields: function () {
        var width = parseFloat($("#pdf-info-width").val());
        var height = parseFloat($("#pdf-info-height").val());
        if (isNaN(width) || isNaN(height) || width <= 0 || height <= 0) {
            return null;
        }
        return {width: width, height: height};
    },

    _page_dimension_changed: function (value, stored) {
        return stored === null || Math.abs(value - stored) >= editor._PAGE_SIZE_TOLERANCE;
    },

    _resolve_page_resize_size: function (size) {
        var widthChanged = editor._page_dimension_changed(size.width, editor.page_width_mm);
        var heightChanged = editor._page_dimension_changed(size.height, editor.page_height_mm);
        if (!widthChanged && !heightChanged) {
            return null;
        }
        var width = size.width;
        var height = size.height;
        if (!editor.page_size_lock_aspect) {
            if (widthChanged && !heightChanged) {
                height = editor.page_height_mm;
            } else if (heightChanged && !widthChanged) {
                width = editor.page_width_mm;
            }
        }
        return {width: width, height: height};
    },

    _set_page_size_field: function (dimension, mm) {
        $("#pdf-info-" + dimension).val(mm.toFixed(2));
    },

    _sync_page_size_fields_from_viewport: function (viewport) {
        ["width", "height"].forEach(function (dimension) {
            var el = $("#pdf-info-" + dimension);
            if (!el.is(":focus")) {
                var px = dimension === "width" ? viewport.width : viewport.height;
                el.val(editor._px2mm(px).toFixed(2));
            }
        });
        editor.page_width_mm = parseFloat($("#pdf-info-width").val());
        editor.page_height_mm = parseFloat($("#pdf-info-height").val());
        editor._update_page_aspect_ratio();
    },

    _apply_background_ok: function (data, size, keepPageSizeFields) {
        editor.page_width_mm = size.width;
        editor.page_height_mm = size.height;
        editor._update_page_aspect_ratio();
        editor.uploaded_file_id = data.id;
        editor.dirty = true;
        editor._replace_pdf_file(data.url, keepPageSizeFields);
    },

    _finish_save_button: function ($btn, defaultLabel, ok) {
        $btn.find("span.fa-spin").remove();
        $btn.prop("disabled", false);
        if (!ok) {
            alert(gettext("Saving failed."));
            return;
        }
        editor.dirty = false;
        editor.uploaded_file_id = null;
        $btn.html('<span class="fa fa-check"></span> ' + gettext("Saved"));
        window.setTimeout(function () {
            $btn.text(defaultLabel);
        }, 2000);
    },

    _update_page_aspect_ratio: function () {
        if (editor.page_width_mm > 0 && editor.page_height_mm > 0) {
            editor.page_aspect_ratio = editor.page_width_mm / editor.page_height_mm;
        }
    },

    _revoke_preview_blob: function () {
        var $iframe = $("#preview-iframe");
        var oldUrl = $iframe.data("blob-url");
        if (!oldUrl) {
            return;
        }
        URL.revokeObjectURL(oldUrl);
        $iframe.removeData("blob-url");
        $iframe.attr("src", "about:blank");
    },

    _show_preview_blob: function (blob) {
        editor._revoke_preview_blob();
        var url = URL.createObjectURL(blob);
        $("#preview-iframe").data("blob-url", url).attr("src", url);
        $("#preview-modal").modal("show");
    },

    dump: function (objs) {
        var d = [];
        objs = objs || editor.fabric.getObjects();

        for (var i in objs) {
            var o = objs[i];
            var top = o.top;
            var left = o.left;
            if (o.group) {
                top += o.group.top + o.group.height / 2;
                left += o.group.left + o.group.width / 2;
            }
            if (o.type === "textarea") {
                var col = (new fabric.Color(o.fill))._source;
                var bottom = editor.pdf_viewport.height - o.height - top;
                if (o.downward) {
                    bottom = editor.pdf_viewport.height - top;
                }
                d.push({
                    type: "textarea",
                    locale: $("#pdf-info-locale").val(),
                    left: editor._px2mm(left).toFixed(2),
                    bottom: editor._px2mm(bottom).toFixed(2),
                    fontsize: editor._get_text_max_font_pt(o).toFixed(1),
                    color: col,
                    //lineheight: o.lineHeight,
                    fontfamily: o.fontFamily,
                    bold: o.fontWeight === 'bold',
                    italic: o.fontStyle === 'italic',
                    width: editor._px2mm(o.width).toFixed(2),
                    downward: o.downward || false,
                    autofit_width: editor._parse_autofit_width(o.autofit_width),
                    content: o.content,
                    text: o.content === "other" ? (o.placeholder_text || o.text) : o.text,
                    rotation: o.angle,
                    align: o.textAlign,
                });
            } else  if (o.type === "imagearea") {
                d.push({
                    type: "imagearea",
                    left: editor._px2mm(left).toFixed(2),
                    bottom: editor._px2mm(editor.pdf_viewport.height - o.height * o.scaleY - top).toFixed(2),
                    height: editor._px2mm(o.height * o.scaleY).toFixed(2),
                    width: editor._px2mm(o.width * o.scaleX).toFixed(2),
                    content: o.content,
                });
            } else  if (o.type === "barcodearea") {
                d.push({
                    type: "barcodearea",
                    left: editor._px2mm(left).toFixed(2),
                    bottom: editor._px2mm(editor.pdf_viewport.height - o.height * o.scaleY - top).toFixed(2),
                    size: editor._px2mm(o.height * o.scaleY).toFixed(2),
                    content: o.content,
                });
            } else  if (o.type === "poweredby") {
                d.push({
                    type: "poweredby",
                    left: editor._px2mm(left).toFixed(2),
                    bottom: editor._px2mm(editor.pdf_viewport.height - o.height * o.scaleY - top).toFixed(2),
                    size: editor._px2mm(o.height * o.scaleY).toFixed(2),
                    content: o.content,
                });
            }
        }
        return d;
    },

    _add_from_data: function (d) {
        if (d.type === "barcodearea") {
            o = editor._add_qrcode();
            o.content = d.content;
            o.scaleToHeight(editor._mm2px(d.size));
        } else if (d.type === "imagearea") {
            o = editor._add_imagearea(d.content);
            o.content = d.content;
            o.set('height', editor._mm2px(d.height));
            o.set('width', editor._mm2px(d.width));
            o.set('scaleX', 1);
            o.set('scaleY', 1);
        } else if (d.type === "poweredby") {
            o = editor._add_poweredby(d.content);
            o.content = d.content;
            o.scaleToHeight(editor._mm2px(d.size));
        } else if (d.type === "textarea" || d.type === "text") {
            o = editor._add_text();
            o.set('fill', 'rgb(' + d.color[0] + ',' + d.color[1] + ',' + d.color[2] + ')');
            o.maxFontPt = parseFloat(d.fontsize);
            o.autofit_width = editor._parse_autofit_width(d.autofit_width);
            o.set('fontSize', editor._pt2px(d.fontsize));
            o.set('lineHeight', d.lineheight || 1);
            o.set('fontFamily', d.fontfamily);
            o.set('fontWeight', d.bold ? 'bold' : 'normal');
            o.set('fontStyle', d.italic ? 'italic' : 'normal');
            o.downward = d.downward || false;
            o.content = editor._normalize_text_content(d.content);
            o.set('textAlign', d.align);
            var rotationVal = parseFloat(d.rotation);
            if (!isNaN(rotationVal)) {
                o.rotate(rotationVal);
            } else {
                o.rotate(0);
            }
            if (o.content === "other") {
                o.placeholder_text = d.text;
                o.set('text', editor._resolve_other_text_sample(d.text));
            } else if (o.content === "other_i18n") {
                o.text_i18n = d.text_i18n
                o.set('text', d.text_i18n[Object.keys(d.text_i18n)[0]]);
            } else if (o.content) {
                o.set('text', editor._resolve_text_sample(o.content) || d.text || '');
            } else if (d.text) {
                o.set('text', d.text);
            }
            var widthVal = parseFloat(d.width);
            o.set('width', editor._mm2px(isNaN(widthVal) ? 50 : widthVal));
            editor._apply_autofit_fontsize(o, o.maxFontPt, widthVal);
            if (d.locale) {
                // The data format allows to set the locale per text field but we currently only expose a global field
                $("#pdf-info-locale").val(d.locale);
            }
        }

        var new_top = editor.pdf_viewport.height - editor._mm2px(d.bottom) - (o.height * o.scaleY);
        if (o.downward) {
            new_top = editor.pdf_viewport.height - editor._mm2px(d.bottom);
        }
        o.set('left', editor._mm2px(d.left));
        o.set('top', new_top);
        o.setCoords();
        return o;
    },

    load: function(data) {
        editor.fabric.clear();
        for (var i in data) {
            var d = data[i], o;
            editor._add_from_data(d);
        }
        editor.fabric.renderAll();
        editor._update_toolbox_values();
    },

    _normalize_text_content: function (key) {
        if (key === 'item') {
            return 'event_name';
        }
        return key;
    },

    _get_text_option: function (key) {
        return $('#toolbox-content option').filter(function () {
            return $(this).val() === key;
        }).first();
    },

    _get_text_sample: function (key) {
        key = editor._normalize_text_content(key);
        if (!key) {
            return '';
        }
        if (key.startsWith('itemmeta:')) {
            return key.substr(9);
        } else if (key.startsWith('meta:')) {
            return key.substr(5);
        }
        var option = editor._get_text_option(key);
        return (option.length ? option.attr('data-sample') : '') || '';
    },

    _resolve_text_sample: function (key) {
        var sample = editor._get_text_sample(key);
        if (sample) {
            return sample;
        }

        var option = editor._get_text_option(key);
        if (!option.length) {
            return '';
        }

        var fallbackLabel = $.trim(option.text() || '');
        var colonPos = fallbackLabel.indexOf(':');
        if (colonPos > -1) {
            return $.trim(fallbackLabel.substr(colonPos + 1));
        }
        return fallbackLabel;
    },

    _resolve_layout_placeholder_sample: function (key) {
        key = $.trim(key);
        if (!key) {
            return '';
        }
        if (key.toLowerCase().indexOf('question:') === 0) {
            var label = $.trim(key.substr(9)).toLowerCase();
            var match = $('#toolbox-content option').filter(function () {
                var optionLabel = $.trim($(this).text() || '').toLowerCase();
                if (optionLabel.indexOf('question:') !== 0) {
                    return false;
                }
                return $.trim(optionLabel.substr(9)) === label;
            }).first();
            return match.attr('data-sample') || '';
        }
        key = editor._normalize_text_content(key);
        return editor._resolve_text_sample(key) || '';
    },

    _resolve_other_text_sample: function (text) {
        if (!text || text.indexOf('{') === -1) {
            return text;
        }
        return text.replace(/\{([^{}]+)\}/g, function (match, key) {
            var sample = editor._resolve_layout_placeholder_sample(key);
            return sample || match;
        });
    },

    _update_disabled_placeholder_warning: function () {
        var selected = $("#toolbox-content option:selected");
        var isTemp = selected.hasClass('editor-temp-option');
        var val = $("#toolbox-content").val();
        var shouldShow = isTemp && val && val !== 'other';
        $('#toolbox-disabled-placeholder-warning').toggle(!!shouldShow);
    },

    _set_toolbox_content_value: function (content, fallbackText) {
        content = editor._normalize_text_content(content);
        $('#toolbox-content option.editor-temp-option').remove();

        var option = editor._get_text_option(content);
        if (!option.length && content) {
            option = $('<option></option>', {
                value: content,
                text: (fallbackText || content) + (window.gettext ? ' (' + window.gettext('Disabled in settings') + ')' : ' (Disabled in settings)'),
                class: 'editor-temp-option is-disabled-placeholder'
            });
            if (fallbackText) {
                option.attr('data-sample', fallbackText);
            }
            $('#toolbox-content').append(option);
        }

        $('#toolbox-content').val(content || 'other');
        if (!$('#toolbox-content').val()) {
            $('#toolbox-content').val('other');
        }

        editor._update_disabled_placeholder_warning();
    },

    _get_toolbox_target_object: function (allowFallback) {
        var activeObject = editor._get_active_object();
        if (activeObject) {
            editor._last_active_object = activeObject;
            return activeObject;
        }

        if (
            allowFallback !== false &&
            $("#toolbox").attr("data-type") &&
            editor._last_active_object &&
            editor.fabric &&
            editor.fabric.getObjects().indexOf(editor._last_active_object) !== -1
        ) {
            return editor._last_active_object;
        }

        return null;
    },

    _apply_text_content_to_object: function (o) {
        var content = editor._normalize_text_content($("#toolbox-content").val());

        $("#toolbox-content").val(content || 'other');
        $("#toolbox-content-other").toggle($("#toolbox-content").val() === "other");

        editor._update_disabled_placeholder_warning();

        o.content = $("#toolbox-content").val();
        if (o.content === "other") {
            o.placeholder_text = $("#toolbox-content-other").val();
            o.set('text', editor._resolve_other_text_sample(o.placeholder_text));
        } else {
            o.placeholder_text = '';
            o.set('text', editor._resolve_text_sample(o.content) || o.text || '');
        }
    },

    _sync_active_text_object_from_toolbox: function () {
        var o = editor._get_toolbox_target_object(true);
        if (!o || (o.type !== "textarea" && o.type !== "text")) {
            return false;
        }

        editor._apply_text_content_to_object(o);
        editor._apply_autofit_fontsize(o);
        o.setCoords();
        editor.fabric.renderAll();
        return true;
    },

    _load_pdf: function (dump, keepPageSizeFields) {
        // TODO: Loading indicators
        var url = editor.pdf_url;
        // TODO: Handle cross-origin issues if static files are on a different origin
        PDFJS.workerSrc = editor.$pdfcv.attr("data-worker-url");

        // Asynchronous download of PDF
        var loadingTask = PDFJS.getDocument(url);
        loadingTask.promise.then(function (pdf) {
            console.log('PDF loaded');

            // Fetch the first page
            var pageNumber = 1;
            pdf.getPage(pageNumber).then(function (page) {
                console.log('Page loaded');
                var canvas = document.getElementById('pdf-canvas');

                var scale = editor.$cva.width() / page.getViewport(1.0).width;
                var viewport = page.getViewport(scale);

                // Prepare canvas using PDF page dimensions
                var context = canvas.getContext('2d');
                context.clearRect(0, 0, canvas.width, canvas.height);
                canvas.height = viewport.height;
                canvas.width = viewport.width;

                editor.pdf_page = page;
                editor.pdf_scale = scale;
                editor.pdf_viewport = viewport;

                if (!keepPageSizeFields) {
                    editor._sync_page_size_fields_from_viewport(viewport);
                }

                // Render PDF page into canvas context
                var renderContext = {
                    canvasContext: context,
                    viewport: viewport
                };
                var renderTask = page.render(renderContext);
                renderTask.then(function () {
                    console.log('Page rendered');
                    editor._init_fabric(dump);
                });
            });
        }, function (reason) {
            var msg = gettext('The PDF background file could not be loaded for the following reason:');
            editor._error(msg + ' ' + reason);
        });
    },

    _init_fabric: function (dump) {
        editor.$fcv.get(0).width = editor.$pdfcv.get(0).width;
        editor.$fcv.get(0).height = editor.$pdfcv.get(0).height;
        editor.fabric = new fabric.Canvas('fabric-canvas');

        editor.fabric.on('object:modified', editor._create_savepoint);
        editor.fabric.on('object:added', editor._create_savepoint);
        editor.fabric.on('selection:cleared', editor._update_toolbox);
        editor.fabric.on('selection:created', editor._update_toolbox);
        editor.fabric.on('selection:updated', editor._update_toolbox);
        editor.fabric.on('object:modified', editor._update_toolbox_values);
        editor.fabric.on('mouse:down', editor._on_canvas_mouse_down);
        editor.fabric.on('object:moving', editor._on_object_moving);
        editor._update_toolbox();

        $("#toolbox-content-other").hide();
        $(".add-buttons button").prop('disabled', false);

        if (dump) {
            editor.load(dump);
        } else {
            var data = $.trim($("#editor-data").text());
            if (data) {
                editor.load(JSON.parse(data));
            }
        }
        editor.history = [];
        editor._create_savepoint();
        editor.dirty = !!dump;

        if ($("#loading-upload").is(":visible")) {
            $("#loading-container, #loading-upload").hide();
        }

        editor._fabric_loaded = true;
        console.log("Fabric loaded");
        if (editor._recheck_page_size_after_load) {
            editor._recheck_page_size_after_load = false;
            editor._on_page_size_field_change();
        }
        if (editor._window_loaded) {
            editor._ready();
        }
    },

    _window_load_event: function () {
        editor._window_loaded = true;
        console.log("Window loaded");
        if (editor._fabric_loaded) {
            editor._ready();
        }
    },

    _ready: function () {
        var isOpera = (!!window.opr && !!opr.addons) || !!window.opera || navigator.userAgent.indexOf(' OPR/') >= 0;
        var isFirefox = typeof InstallTrigger !== 'undefined';
        var isChrome = !!window.chrome && (!!window.chrome.webstore || !!window.chrome.runtime);
        var isEdgeChromium = isChrome && (navigator.userAgent.indexOf("Edg") != -1);
        if (isChrome || isOpera || isFirefox || isEdgeChromium) {
            $("#loading-container").hide();
            $("#loading-initial").remove();
        } else {
            $("#editor-loading").hide();
            $("#editor-start").removeClass("sr-only");
            $("#editor-start").click(function () {
                $("#loading-container").hide();
                $("#loading-initial").remove();
            });
        }
    },

    _update_toolbox_values: function () {
        var o = editor._get_toolbox_target_object(true);
        if (!o) {
            $("#toolbox-autofit-width").prop('checked', false);
            return;
        }
        editor._toolbox_update_in_progress = true;

        var setVal = function (selector, val) {
            var el = $(selector);
            if (!el.is(":focus")) {
                el.val(val);
            }
        };

        if (editor._is_active_selection(o)) {
            var bound = editor._object_abs_rect(o);
            var groupBottom = editor.pdf_viewport.height - bound.height - bound.top;
            setVal("#toolbox-position-x", editor._px2mm(bound.left).toFixed(2));
            setVal("#toolbox-position-y", editor._px2mm(groupBottom).toFixed(2));
            editor._toolbox_update_in_progress = false;
            return;
        }

        var bottom = editor.pdf_viewport.height - o.height * o.scaleY - o.top;
        if (o.downward) {
            bottom = editor.pdf_viewport.height - o.top;
        }
        setVal("#toolbox-position-x", editor._px2mm(o.left).toFixed(2));
        setVal("#toolbox-position-y", editor._px2mm(bottom).toFixed(2));

        if (o.type === "barcodearea") {
            setVal("#toolbox-squaresize", editor._px2mm(o.height * o.scaleY).toFixed(2));
        } else if (o.type === "imagearea") {
            setVal("#toolbox-height", editor._px2mm(o.height * o.scaleY).toFixed(2));
            setVal("#toolbox-width", editor._px2mm(o.width * o.scaleX).toFixed(2));
            setVal("#toolbox-imagecontent", o.content);
        } else if (o.type === "poweredby") {
            setVal("#toolbox-squaresize", editor._px2mm(o.height * o.scaleY).toFixed(2));
            setVal("#toolbox-poweredby-style", o.content);
        } else if (o.type === "text" || o.type === "textarea") {
            var col = (new fabric.Color(o.fill))._source;
            var hexColor = "#" + ((1 << 24) + (col[0] << 16) + (col[1] << 8) + col[2]).toString(16).slice(1);
            setVal("#toolbox-col", hexColor);
            // Update colorpicker's internal state and preview
            var $colorInput = $("#toolbox-col");
            if ($colorInput.data('colorpicker')) {
                $colorInput.colorpicker('setValue', hexColor);
            }
            $colorInput.closest('.colorpicker-preview-group').find('.colorpicker-preview').css('background-color', hexColor);
            setVal("#toolbox-fontsize", editor._get_text_max_font_pt(o).toFixed(1));
            //$("#toolbox-lineheight").val(o.lineHeight);
            setVal("#toolbox-fontfamily", o.fontFamily);
            $("#toolbox").find("button[data-action=bold]").toggleClass('active', o.fontWeight === 'bold');
            $("#toolbox").find("button[data-action=italic]").toggleClass('active', o.fontStyle === 'italic');
            $("#toolbox").find("button[data-action=downward]").toggleClass('active', o.downward || false);
            $("#toolbox-autofit-width").prop('checked', editor._parse_autofit_width(o.autofit_width));
            $("#toolbox").find("button[data-action=left]").toggleClass('active', o.textAlign === 'left');
            $("#toolbox").find("button[data-action=center]").toggleClass('active', o.textAlign === 'center');
            $("#toolbox").find("button[data-action=right]").toggleClass('active', o.textAlign === 'right');
            var pxWidth = editor._px2mm(o.width);
            setVal("#toolbox-textwidth", isNaN(pxWidth) ? "13.00" : pxWidth.toFixed(2));
            var angleVal = typeof o.angle === "number" ? o.angle : 0.0;
            setVal("#toolbox-textrotation", isNaN(angleVal) ? "0.0" : angleVal.toFixed(1));
            if (o.type === "textarea") {
                editor._set_toolbox_content_value(o.content, o.text);
                $("#toolbox-content-other").toggle($("#toolbox-content").val() === "other");
                if (o.content === "other") {
                    setVal("#toolbox-content-other", o.placeholder_text || o.text);
                } else {
                    setVal("#toolbox-content-other", "");
                }
            }
        }
        editor._toolbox_update_in_progress = false;
    },

    _update_values_from_toolbox: function () {
        if (editor._toolbox_update_in_progress) {
            return;
        }
        var o = editor._get_toolbox_target_object(true);
        if (!o) {
            return;
        }

        if (editor._is_active_selection(o)) {
            var bound = editor._object_abs_rect(o);
            var newLeftMm = parseFloat($("#toolbox-position-x").val());
            var newBottomMm = parseFloat($("#toolbox-position-y").val());
            if (isNaN(newLeftMm) || isNaN(newBottomMm)) {
                return;
            }
            var newLeft = editor._mm2px(newLeftMm);
            var newTop = editor.pdf_viewport.height - editor._mm2px(newBottomMm) - bound.height;
            o.set({
                left: o.left + (newLeft - bound.left),
                top: o.top + (newTop - bound.top)
            });
            o.setCoords();
            editor.fabric.renderAll();
            editor._update_toolbox_values();
            return;
        }

        var new_top = editor.pdf_viewport.height - editor._mm2px($("#toolbox-position-y").val()) - o.height * o.scaleY;
        if (o.type === "textarea" || o.type === "text") {
            if ($("#toolbox").find("button[data-action=downward]").is('.active')) {
                new_top = editor.pdf_viewport.height - editor._mm2px($("#toolbox-position-y").val());
            }
        }
        o.set('left', editor._mm2px($("#toolbox-position-x").val()));
        o.set('top', new_top);

        if (o.type === "barcodearea") {
            var new_h = editor._mm2px($("#toolbox-squaresize").val());
            new_top += o.height * o.scaleY - new_h;
            o.set('height', new_h);
            o.set('width', new_h);
            o.set('scaleX', 1);
            o.set('scaleY', 1);
            o.set('top', new_top)
        } else if (o.type === "imagearea") {
            var new_w = editor._mm2px($("#toolbox-width").val());
            var new_h = editor._mm2px($("#toolbox-height").val());
            new_top += o.height * o.scaleY - new_h;
            o.set('height', new_h);
            o.set('width', new_w);
            o.set('scaleX', 1);
            o.set('scaleY', 1);
            o.set('top', new_top)
            o.content = $("#toolbox-imagecontent").val();
        } else if (o.type === "poweredby") {
            var new_h = Math.max(1, editor._mm2px($("#toolbox-squaresize").val()));
            new_top += o.height * o.scaleY - new_h;
            o.set('width', new_h / o.height * o.width);
            o.set('height', new_h);
            o.set('scaleX', 1);
            o.set('scaleY', 1);
            o.set('top', new_top)
            if ($("#toolbox-poweredby-style").val() !== o.content) {
                var data = editor.dump([o]);
                data[0].content = $("#toolbox-poweredby-style").val();
                var newo = editor._add_from_data(data[0]);
                editor.fabric.remove(o);
                editor.fabric.discardActiveObject();
                editor.fabric.setActiveObject(newo);
            }
        } else if (o.type === "textarea" || o.type === "text") {
            o.set('fill', $("#toolbox-col").val());
            var maxFontPt = parseFloat($("#toolbox-fontsize").val());
            if (!isNaN(maxFontPt)) {
                o.maxFontPt = maxFontPt;
            }
            o.set('lineHeight', $("#toolbox-lineheight").val() || 1);
            o.set('fontFamily', $("#toolbox-fontfamily").val());
            o.set('fontWeight', $("#toolbox").find("button[data-action=bold]").is('.active') ? 'bold' : 'normal');
            o.set('fontStyle', $("#toolbox").find("button[data-action=italic]").is('.active') ? 'italic' : 'normal');
            o.autofit_width = $("#toolbox-autofit-width").prop('checked');
            var align = $("#toolbox-align").find(".active").attr("data-action");
            if (align) {
                o.set('textAlign', align);
            }
            var w = parseFloat($("#toolbox-textwidth").val());
            if (!isNaN(w)) {
                o.set('width', editor._mm2px(w));
                o.set('scaleX', 1);
                o.set('scaleY', 1);
                if (o.initDimensions) o.initDimensions();
                if (o._clearCache) o._clearCache();
                o.dirty = true;
            }
            o.downward = $("#toolbox").find("button[data-action=downward]").is('.active');
            var r = parseFloat($("#toolbox-textrotation").val());
            if (!isNaN(r)) {
                o.rotate(r);
                o.dirty = true;
            }
            editor._apply_text_content_to_object(o);
            editor._apply_autofit_fontsize(o, o.maxFontPt, w);
        }

        o.setCoords();
        editor.fabric.renderAll();
        editor._update_toolbox_values();
    },

    _update_toolbox: function () {
        var selected = editor.fabric.getActiveObjects();
        if (selected.length > 1) {
            $("#toolbox").attr("data-type", "group");
            $("#toolbox-heading").text(gettext("Group of objects"));
        } else if (selected.length == 1) {
            var o = selected[0];
            editor._last_active_object = o;
            $("#toolbox").attr("data-type", o.type);
            if (o.type === "textarea" || o.type === "text") {
                $("#toolbox-heading").text(gettext("Text object"));
            } else if (o.type === "barcodearea") {
                $("#toolbox-heading").text(gettext("Barcode area"));
            } else if (o.type === "imagearea") {
                $("#toolbox-heading").text(gettext("Image area"));
            } else if (o.type === "poweredby") {
                $("#toolbox-heading").text(gettext("Powered by pretix"));
            } else {
                $("#toolbox-heading").text(gettext("Object"));
            }
        } else {
            $("#toolbox").removeAttr("data-type");
            $("#toolbox-heading").text(gettext("Ticket design"));
        }
        var isSingleText = selected.length === 1 && (selected[0].type === "textarea" || selected[0].type === "text");
        if (isSingleText) {
            editor._update_disabled_placeholder_warning();
        } else {
            $("#toolbox-disabled-placeholder-warning").hide();
        }
        editor._update_toolbox_values();
    },

    _on_page_size_dimension_input: function (changed) {
        if (!editor.page_size_lock_aspect || !editor.page_aspect_ratio) {
            return;
        }
        var size = editor._get_page_size_from_fields();
        if (!size) {
            return;
        }
        if (changed === "width") {
            editor._set_page_size_field("height", size.width / editor.page_aspect_ratio);
        } else {
            editor._set_page_size_field("width", size.height * editor.page_aspect_ratio);
        }
    },

    _on_page_size_field_change: function () {
        window.clearTimeout(editor._page_size_timer);
        editor._page_size_timer = window.setTimeout(function () {
            if ($("#pdf-info-width").is(":focus") || $("#pdf-info-height").is(":focus")) {
                return;
            }
            if (editor._page_resize_in_progress) {
                editor._on_page_size_field_change();
                return;
            }
            editor._apply_page_size_from_fields();
        }, 0);
    },

    _apply_page_size_from_fields: function () {
        if (editor._page_resize_in_progress || !editor.pdf_page) {
            return;
        }
        var size = editor._get_page_size_from_fields();
        if (!size) {
            return;
        }
        size = editor._resolve_page_resize_size(size);
        if (!size) {
            return;
        }

        var resizeSize = size;
        editor._set_background_buttons_busy(true);
        $.post(window.location.href, {
            csrfmiddlewaretoken: editor._csrf_token(),
            resizebackground: "true",
            width: resizeSize.width,
            height: resizeSize.height,
            background: editor.uploaded_file_id || "",
        }, function (data) {
            editor._set_background_buttons_busy(false);
            if (data.status === "ok") {
                editor._apply_background_ok(data, resizeSize, true);
            } else {
                alert(data.error || gettext("Error while updating the background PDF, please try again."));
            }
        }, "json").fail(function () {
            editor._set_background_buttons_busy(false);
            alert(gettext("Error while updating the background PDF, please try again."));
        });
    },

    _toggle_page_size_lock: function () {
        editor.page_size_lock_aspect = !editor.page_size_lock_aspect;
        var $btn = $("#pdf-info-lock-aspect");
        $btn.toggleClass("active", editor.page_size_lock_aspect);
        $btn.attr("aria-pressed", editor.page_size_lock_aspect ? "true" : "false");
        $btn.find(".fa")
            .toggleClass("fa-link", editor.page_size_lock_aspect)
            .toggleClass("fa-unlink", !editor.page_size_lock_aspect);
        if (editor.page_size_lock_aspect) {
            editor._update_page_aspect_ratio();
        }
    },

    _error: function (msg) {
        editor.$cva.before("<div class='alert alert-danger'>" + msg + "</div>");
    },

    _add_text: function () {
        var text = new fabric.Textarea(editor._get_text_sample('event_name'), {
            left: 0,
            top: 100,
            width: editor.pdf_viewport.width,
            lockRotation: false,
            centeredRotation: true,
            fontFamily: 'Open Sans',
            lineHeight: 1,
            content: 'event_name',
            editable: false,
            fontSize: editor._pt2px(13)
        });
        text.downward = true;
        text.setControlsVisibility({
            'tr': false,
            'tl': false,
            'mt': false,
            'br': false,
            'bl': false,
            'mb': false,
            'mr': true,
            'ml': true,
            'mtr': true
        });
        editor.fabric.add(text);
        editor.fabric.setActiveObject(text);
        editor._last_active_object = text;
        editor._update_toolbox();
        editor._create_savepoint();
        return text;
    },

    _add_poweredby: function (content) {
        var rect = new fabric.Poweredby({
            left: 100,
            top: 100,
            height: 629,
            width: 1024,
            lockRotation: true,
            content: content
        });
        rect.scaleToHeight(126);
        rect.setControlsVisibility({'mtr': false, 'mb': false, 'mt': false, 'mr': false, 'ml': false});
        editor.fabric.add(rect);
        editor._create_savepoint();
        return rect;
    },

    _add_imagearea: function () {
        var rect = new fabric.Imagearea({
            left: 100,
            top: 100,
            width: 100,
            height: 100,
            lockRotation: true,
            fill: '#666',
            content: '',
        });
        rect.setControlsVisibility({'mtr': false});
        editor.fabric.add(rect);
        editor._create_savepoint();
        return rect;
    },

    _add_qrcode: function () {
        var rect = new fabric.Barcodearea({
            left: 100,
            top: 100,
            width: 100,
            height: 100,
            lockRotation: true,
            fill: '#666',
            content: $(this).attr("data-content"),
        });
        rect.setControlsVisibility({'mtr': false, 'mb': false, 'mt': false, 'mr': false, 'ml': false});
        editor.fabric.add(rect);
        editor._create_savepoint();
        return rect;
    },

    _cut: function () {
        var thing = editor._get_active_object();
        if (!thing) {
            return;
        }
        editor._history_modification_in_progress = true;
        editor.clipboard = editor._dump_selection(thing);
        editor._remove_active();
        editor._history_modification_in_progress = false;
        editor._create_savepoint();
    },

    _copy: function () {
        var thing = editor._get_active_object();
        if (!thing) {
            return;
        }
        editor.clipboard = editor._dump_selection(thing);
    },

    _paste: function () {
        if (editor.clipboard.length < 1) {
            return;
        }
        editor._history_modification_in_progress = true;
        var objs = [];
        for (var i in editor.clipboard) {
            objs.push(editor._add_from_data(editor.clipboard[i]));
        }
        editor._set_selection(objs);
        editor._history_modification_in_progress = false;
        editor._create_savepoint();
    },

    _delete: function () {
        if (!editor._remove_active()) {
            return;
        }
        editor._create_savepoint();
        editor._update_toolbox();
    },

    _on_canvas_mouse_down: function () {
        editor._focus_canvas();
        editor._drag_start = null;
    },

    _on_object_moving: function (opt) {
        var o = opt.target;
        if (!o || !opt.e) {
            return;
        }
        if (!editor._drag_start) {
            editor._drag_start = {left: o.left, top: o.top};
        }
        if (!opt.e.shiftKey) {
            return;
        }
        var step = editor._nudge_px(true);
        o.set({
            left: editor._snap_to_step(o.left, editor._drag_start.left, step),
            top: editor._snap_to_step(o.top, editor._drag_start.top, step)
        });
        o.setCoords();
    },

    _select_all: function () {
        if (!editor.fabric) {
            return;
        }
        editor._set_selection(editor.fabric.getObjects().slice());
    },

    _align_selection: function (alignment) {
        var objs = editor._get_active_objects();
        if (objs.length < 2) {
            return;
        }
        editor.fabric.discardActiveObject();
        objs.forEach(function (o) {
            o.setCoords();
        });

        var rects = objs.map(function (o) {
            var r = editor._object_abs_rect(o);
            r.obj = o;
            return r;
        });
        var minL = Math.min.apply(null, rects.map(function (r) { return r.left; }));
        var minT = Math.min.apply(null, rects.map(function (r) { return r.top; }));
        var maxR = Math.max.apply(null, rects.map(function (r) { return r.left + r.width; }));
        var maxB = Math.max.apply(null, rects.map(function (r) { return r.top + r.height; }));
        var centerX = (minL + maxR) / 2;
        var centerY = (minT + maxB) / 2;
        var deltas = {
            left: function (r) { return {dx: minL - r.left, dy: 0}; },
            center: function (r) { return {dx: centerX - (r.left + r.width / 2), dy: 0}; },
            right: function (r) { return {dx: maxR - (r.left + r.width), dy: 0}; },
            top: function (r) { return {dx: 0, dy: minT - r.top}; },
            middle: function (r) { return {dx: 0, dy: centerY - (r.top + r.height / 2)}; },
            bottom: function (r) { return {dx: 0, dy: maxB - (r.top + r.height)}; }
        };
        var deltaFor = deltas[alignment];
        if (!deltaFor) {
            editor._set_selection(objs);
            return;
        }

        rects.forEach(function (r) {
            var d = deltaFor(r);
            r.obj.set({
                left: r.obj.left + d.dx,
                top: r.obj.top + d.dy
            });
            r.obj.setCoords();
        });

        editor._set_selection(objs);
        editor._create_savepoint();
    },

    _on_number_shift_nudge: function (e) {
        var isUp = e.key === 'ArrowUp' || e.keyCode === 38;
        var isDown = e.key === 'ArrowDown' || e.keyCode === 40;
        if ((!isUp && !isDown) || !e.shiftKey) {
            return;
        }
        e.preventDefault();
        var $input = $(this);
        var current = parseFloat($input.val());
        if (isNaN(current)) {
            current = 0;
        }
        var bigStep = $input.attr('id') === 'toolbox-fontsize' ? 1 : editor._NUDGE_SHIFT_MM;
        current += isDown ? -bigStep : bigStep;
        var stepAttr = ($input.attr('step') || '1').toString();
        var decimals = stepAttr.indexOf('.') === -1 ? 0 : stepAttr.split('.')[1].length;
        $input.val(current.toFixed(decimals));
        $input.trigger('change');
    },

    _on_keydown: function (e) {
        if (!editor._is_hotkey_target() || !editor.fabric) {
            return;
        }
        var thing = editor._get_active_object();
        var cmd = e.ctrlKey || e.metaKey;
        var handled = false;
        switch (e.keyCode) {
            case 38:  /* Up arrow */
            case 40:  /* Down arrow */
            case 37:  /* Left arrow */
            case 39:  /* Right arrow */
                e.preventDefault();
                editor._nudge_active(
                    e.keyCode === 37 ? -1 : e.keyCode === 39 ? 1 : 0,
                    e.keyCode === 38 ? -1 : e.keyCode === 40 ? 1 : 0,
                    e.shiftKey
                );
                handled = true;
                break;
            case 46:  /* Delete */
                if (!thing) {
                    return;
                }
                editor._delete();
                handled = true;
                break;
            case 65:  /* A */
                if (!cmd) {
                    return;
                }
                editor._select_all();
                handled = true;
                break;
            case 89:  /* Y */
                if (!cmd) {
                    return;
                }
                editor._redo();
                handled = true;
                break;
            case 90:  /* Z */
                if (!cmd) {
                    return;
                }
                editor._undo();
                handled = true;
                break;
            case 88:  /* X */
                if (!cmd || !thing) {
                    return;
                }
                editor._cut();
                handled = true;
                break;
            case 86:  /* V */
                if (!cmd || editor.clipboard.length < 1) {
                    return;
                }
                editor._paste();
                handled = true;
                break;
            case 67:  /* C */
                if (!cmd || !thing) {
                    return;
                }
                editor._copy();
                handled = true;
                break;
            default:
                return;
        }
        if (handled) {
            e.preventDefault();
            editor.fabric.renderAll();
            editor._update_toolbox_values();
        }
    },

    _create_savepoint: function () {
        if (editor._history_modification_in_progress) {
            return;
        }
        var state = editor.dump();
        if (editor._history_pos > 0) {
            editor.history.splice(-1 * editor._history_pos, editor._history_pos);
            editor._history_pos = 0;
        }
        editor.history.push(state);
        editor.dirty = true;
    },

    _undo: function undo() {
        if (editor._history_pos < editor.history.length - 1) {
            editor._history_modification_in_progress = true;
            editor._history_pos += 1;
            editor.fabric.clear().renderAll();
            editor.load(editor.history[editor.history.length - 1 - editor._history_pos]);
            editor._history_modification_in_progress = false;
            editor.dirty = true;
        }
    },

    _redo: function redo() {
        if (editor._history_pos > 0) {
            editor._history_modification_in_progress = true;
            editor._history_pos -= 1;
            editor.load(editor.history[editor.history.length - 1 - editor._history_pos]);
            editor._history_modification_in_progress = false;
            editor.dirty = true;
        }
    },

    _save: function (e) {
        if (e) {
            e.preventDefault();
        }
        var $btn = $("#editor-save");
        var defaultLabel = $btn.data("default-label");
        if (!defaultLabel) {
            defaultLabel = $.trim($btn.text());
            $btn.data("default-label", defaultLabel);
        }
        $btn.prop("disabled", true).prepend('<span class="fa fa-cog fa-spin"></span> ');
        editor._sync_active_text_object_from_toolbox();
        var payload = {
            data: JSON.stringify(editor.dump()),
            csrfmiddlewaretoken: editor._csrf_token(),
        };
        if (editor.uploaded_file_id) {
            payload.background = editor.uploaded_file_id;
        }
        $.post(window.location.href, payload, function (data) {
            editor._finish_save_button($btn, defaultLabel, data.status === "ok");
        }, "json").fail(function () {
            editor._finish_save_button($btn, defaultLabel, false);
        });
        return false;
    },

    _preview: function (e) {
        e.preventDefault();
        editor._sync_active_text_object_from_toolbox();
        var formData = new FormData();
        formData.append("data", JSON.stringify(editor.dump()));
        formData.append("background", editor.uploaded_file_id || "");
        formData.append("preview", "true");
        formData.append("csrfmiddlewaretoken", editor._csrf_token());

        $("#editor-preview").prop("disabled", true);
        fetch(window.location.href, {
            method: "POST",
            body: formData,
            credentials: "same-origin",
        }).then(function (response) {
            if (!response.ok) {
                throw new Error("Preview failed");
            }
            return response.blob();
        }).then(function (blob) {
            editor._show_preview_blob(blob);
        }).catch(function () {
            alert(gettext("Preview failed."));
        }).finally(function () {
            $("#editor-preview").prop("disabled", false);
        });
        return false;
    },

    _replace_pdf_file: function (url, keepPageSizeFields) {
        editor.pdf_url = url;
        editor._sync_active_text_object_from_toolbox();
        var dump = editor.dump();
        editor.fabric.dispose();
        editor._recheck_page_size_after_load = !!keepPageSizeFields;
        editor._load_pdf(dump, keepPageSizeFields);
    },

    _source_show: function () {
        editor._sync_active_text_object_from_toolbox();
        $("#source-textarea").text(JSON.stringify(editor.dump()));
        $("#source-container").show();
    },

    _source_close: function () {
        $("#source-container").hide();
    },

    _source_save: function () {
        editor.load(JSON.parse($("#source-textarea").val()));
        $("#source-container").hide();
    },

    _create_empty_background: function () {
        editor._set_background_buttons_busy(true, true);
        $.post(window.location.href, {
            csrfmiddlewaretoken: editor._csrf_token(),
            emptybackground: "true",
            width: $("#pdf-info-width").val(),
            height: $("#pdf-info-height").val(),
        }, function (data) {
            if (data.status === "ok") {
                editor.uploaded_file_id = data.id;
                editor._replace_pdf_file(data.url, true);
            } else {
                alert(data.error || gettext("Error while uploading your PDF file, please try again."));
                $("#loading-container, #loading-upload").hide();
            }
            editor._set_background_buttons_busy(false);
        }, "json");
    },

    init: function () {
        editor.$pdfcv = $("#pdf-canvas");
        editor.pdf_url = editor.$pdfcv.attr("data-pdf-url");
        editor.$fcv = $("#fabric-canvas");
        editor.$cva = $("#editor-canvas-area");
        editor._load_pdf();
        $("#editor-add-qrcode, #editor-add-qrcode-lead").click(editor._add_qrcode);
        $("#editor-add-image").click(editor._add_imagearea);
        $("#editor-add-text").click(editor._add_text);
        $("#editor-add-poweredby").click(function() {editor._add_poweredby("dark")});
        editor.$cva.get(0).tabIndex = 1000;
        editor.$cva.on("keydown", editor._on_keydown);
        $("#editor-save").on("click", editor._save);
        $("#editor-preview").on("click", editor._preview);
        $("#preview-modal").on("hidden.bs.modal", editor._revoke_preview_blob);
        window.onbeforeunload = function () {
            if (editor.dirty) {
                return gettext("Do you really want to leave the editor without saving your changes?");
            }
        };
        $("#source-container").hide();


        $("#pdf-empty").on("click", editor._create_empty_background);
        $("#pdf-info-lock-aspect").on("click", editor._toggle_page_size_lock);
        $("#pdf-info-width, #pdf-info-height").on("input", function () {
            editor._on_page_size_dimension_input(this.id === "pdf-info-width" ? "width" : "height");
        });
        $("#pdf-info-width, #pdf-info-height").on("change focusout", editor._on_page_size_field_change);
        $('#fileupload').fileupload({
            url: location.href,
            dataType: 'json',
            done: function (e, data) {
                if (data.result.status === "ok") {
                    editor.uploaded_file_id = data.result.id;
                    editor._replace_pdf_file(data.result.url);
                } else {
                    alert(data.result.error || gettext("Error while uploading your PDF file, please try again."));
                    $("#loading-container, #loading-upload").hide();
                }
                editor._set_background_buttons_busy(false);
            },
            add: function (e, data) {
                data.formData = {
                    csrfmiddlewaretoken: editor._csrf_token()
                };
                editor._set_background_buttons_busy(true, true);
                data.process().done(function () {
                    data.submit();
                });
            },
            progressall: function (e, data) {
                var progress = parseInt(data.loaded / data.total * 100, 10);
                $('#loading-upload .progress-bar').css('width', progress + '%');
            }
        }).prop('disabled', !$.support.fileInput).parent().addClass($.support.fileInput ? undefined : 'disabled');

        $("#toolbox input[type=number], #toolbox textarea:not(#toolbox-content-other), #toolbox input[type=text]").bind('change keydown keyup' +
            ' input', editor._update_values_from_toolbox);
        $("#toolbox-position-x, #toolbox-position-y, #toolbox-width, #toolbox-height, #toolbox-squaresize, #toolbox-textwidth, #toolbox-fontsize, #toolbox-textrotation").on('keydown', editor._on_number_shift_nudge);
        $("#toolbox-object-align").on('click', 'button[data-align]', function () {
            editor._align_selection($(this).attr('data-align'));
        });
        $("#toolbox input[type=number], #toolbox textarea:not(#toolbox-content-other), #toolbox input[type=text], #toolbox input[type=radio], #toolbox-autofit-width").bind('change', editor._create_savepoint);
        $("#toolbox-autofit-width").bind('change', editor._update_values_from_toolbox);
        $("#toolbox label.btn").bind('click change', editor._update_values_from_toolbox);
        $("#toolbox select:not(#toolbox-content)").bind('change', editor._update_values_from_toolbox);
        $("#toolbox select:not(#toolbox-content)").bind('change', editor._create_savepoint);
        $("#toolbox-content").bind('change', editor._update_values_from_toolbox);
        $("#toolbox-content-other").bind('change keyup input blur', editor._update_values_from_toolbox);
        $("#toolbox-content, #toolbox-content-other").bind('change', editor._create_savepoint);
        $("#toolbox button.toggling").bind('click change', function () {
            if ($(this).is(".option")) {
                $(this).addClass("active");
                $(this).parent().siblings().find("button").removeClass("active");
            } else {
                $(this).toggleClass("active");
            }
            editor._update_values_from_toolbox();
            editor._create_savepoint();
        });
        $("#toolbox .colorpickerfield").bind('changeColor', editor._update_values_from_toolbox);
        $("#toolbox-copy").bind('click', editor._copy);
        $("#toolbox-cut").bind('click', editor._cut);
        $("#toolbox-delete").bind('click', editor._delete);
        $("#toolbox-paste").bind('click', editor._paste);
        $("#toolbox-undo").bind('click', editor._undo);
        $("#toolbox-redo").bind('click', editor._redo);
        $("#toolbox-source").bind('click', editor._source_show);
        $("#source-close").bind('click', editor._source_close);
        $("#source-save").bind('click', editor._source_save);
    }
};

$(function () {
    editor.init();
});
$(window).bind('load', editor._window_load_event);
