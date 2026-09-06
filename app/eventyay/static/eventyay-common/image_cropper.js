$(function() {
    var cropper = null;
    var currentInput = null;

    var $modal = $('#cropperModal');
    var image = document.getElementById('cropperImage');
    var $saveBtn = $('#cropperSaveBtn');

    var cropApplied = false;

    var config = {
        'id_settings-event_logo_image': { ratio: NaN }, // Free form aspect ratio for Logo
        'id_settings-logo_image': { ratio: 1920 / 640 }, // 3:1 aspect ratio for Header Image (recommended 1920x640)
        'id_basics-logo_image': { ratio: 1920 / 640 }, // 3:1 aspect ratio for Meetup Creation Header Image (recommended 1920x640)
        'id_settings-event_preview_image': { ratio: 16 / 9 }, // 16:9 aspect ratio for Event Preview Image (recommended 16:9)
        'id_settings-organizer_logo_image': { ratio: NaN }, // Free form aspect ratio for Organizer Logo
        'id_settings-organizer_header_image': { ratio: 1920 / 640 }, // Aspect ratio for Organizer Header Image (recommended 1920x640)
        'id_settings-og_image': { ratio: 1200 / 630 }, // 1200:630 aspect ratio for Social Media Image (recommended 1200x630)
        'id_picture': { ratio: NaN }, // Free form aspect ratio for Product picture
        'id_profile_picture': { ratio: 1 } // 1:1 aspect ratio for Profile Picture
    };

    function initCropperForInput(inputId) {
        var $input = $('#' + inputId);
        if ($input.length === 0) return;

        // Insert hidden fields right after the input
        var fieldName = $input.attr('name');
        var hiddenFields = `
            <input type="hidden" name="${fieldName}_crop_x" id="id_${fieldName}_crop_x">
            <input type="hidden" name="${fieldName}_crop_y" id="id_${fieldName}_crop_y">
            <input type="hidden" name="${fieldName}_crop_w" id="id_${fieldName}_crop_w">
            <input type="hidden" name="${fieldName}_crop_h" id="id_${fieldName}_crop_h">
        `;
        $input.after(hiddenFields);


        $input.on('mousedown click', function() {
            this.value = '';
        });

        $input.on('change', function(e) {
            var files = e.target.files;
            if (files && files.length > 0) {
                var file = files[0];
                if (!file.type.startsWith('image/')) return;
                
                // Bypass cropper for GIFs to preserve animations (backend skips optimization for animated GIFs anyway)
                if (file.type === 'image/gif') {
                    return;
                }
                
                cropApplied = false;
                currentInput = inputId;
                var reader = new FileReader();
                reader.onload = function(evt) {
                    if (cropper) {
                        cropper.destroy();
                        cropper = null;
                    }
                    image.src = evt.target.result;

                    var setupCropper = function() {
                        if (cropper) {
                            cropper.destroy();
                        }
                        cropper = new Cropper(image, {
                            aspectRatio: config[inputId].ratio,
                            viewMode: 1,
                        });
                    };

                    if ($modal.is(':visible')) {
                        setupCropper();
                    } else {
                        $modal.one('shown.bs.modal', setupCropper);
                        $modal.modal({ backdrop: 'static', keyboard: false }).modal('show');
                    }
                };
                reader.readAsDataURL(file);
            }
        });
    }

    Object.keys(config).forEach(initCropperForInput);

    $modal.on('hidden.bs.modal', function() {
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
        if (!cropApplied && currentInput) {
            // If the user cancelled, clear the file input so the uncropped image isn't saved.
            $('#' + currentInput).val('');
        }
        currentInput = null;
    });

    $saveBtn.on('click', function() {
        if (cropper && currentInput) {
            cropApplied = true;
            var cropData = cropper.getData(true);
            var $input = $('#' + currentInput);
            var fieldName = $input.attr('name');
            
            // Construct the hidden field ID based on the input name
            // The name is usually "settings-event_logo_image", so hidden field ID is "id_settings-event_logo_image_crop_x"
            $('#id_' + fieldName + '_crop_x').val(cropData.x);
            $('#id_' + fieldName + '_crop_y').val(cropData.y);
            $('#id_' + fieldName + '_crop_w').val(cropData.width);
            $('#id_' + fieldName + '_crop_h').val(cropData.height);

            // Persist the preview directly into the form's existing thumbnail
            var canvas = cropper.getCroppedCanvas();
            if (canvas) {
                var dataUrl = canvas.toDataURL();
                var $container = $input.closest('[class*="col-"]');
                if ($container.length === 0) {
                    $container = $input.parent();
                }
                
                var imgStyles = {
                    maxWidth: '100%',
                    maxHeight: '150px',
                    width: 'auto',
                    objectFit: 'contain',
                    display: 'block',
                    marginBottom: '10px'
                };

                var $existingImg = $container.find('img').first();
                if ($existingImg.length) {
                    $existingImg.attr('src', dataUrl).css(imgStyles);
                    $existingImg.removeAttr('srcset');
                    if ($existingImg.parent().is('a')) {
                        $existingImg.parent().attr('href', dataUrl);
                    }

                    var $wrapper = $existingImg.closest('.initial-file-container');
                    $wrapper.find('.thumbnailed-file-checkbox').prop('checked', false);
                    $wrapper.find('.delete-confirm-msg').hide();

                    var $delBtn = $wrapper.find('.btn-delete-image-ajax');
                    if ($delBtn.length) {
                        $delBtn.prop('disabled', false).removeClass('btn-warning').addClass('btn-danger');
                        $delBtn.find('i').removeClass('fa-spinner fa-spin').addClass('fa-trash');
                        $delBtn.attr('title', $delBtn.attr('data-original-title') || 'Delete Image');
                        $delBtn.removeAttr('data-confirming');
                    }

                    $wrapper.removeClass('thumbnailed-file-initial-hidden').show();
                } else {
                    var $newImg = $('<img>').attr('src', dataUrl).css(imgStyles);
                    $newImg.insertBefore($input);
                }
            }

            $modal.modal('hide');
        }
    });
});
