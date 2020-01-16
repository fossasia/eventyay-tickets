$(function () {
    const $image = $(".avatar-form img");
    const $fileInput = $(".avatar-form .avatar-upload input[type=file]");
    const $resetCheckbox = $(".avatar-form .avatar-upload input[type=checkbox]");
    const $useGravatar = $('.avatar-form #id_get_gravatar');

    $fileInput.on('change', function () {
        let imageSelected = $fileInput.val() !== '';

        if (imageSelected) {
            $useGravatar.prop('checked', false);

            let files = $fileInput.prop('files');
            if (files) {
                const reader = new FileReader();
                reader.onload = function (e) {
                    $image.attr('src', e.target.result);
                    $image.removeClass('d-none');
                };
                reader.readAsDataURL(files[0]);
                $resetCheckbox.prop('checked', false);
            } else if ($image.data('avatar')) {
                $image.attr('src', $image.data('avatar'));
                $resetCheckbox.prop('checked', false);
            } else {
                $image.addClass('d-none');
            }
        } else if ($image.data('avatar')) {
            $image.attr('src', $image.data('avatar'));
            $image.removeClass('d-none');
            $resetCheckbox.prop('checked', false);
        } else {
            $image.addClass('d-none');
        }
    });

    $useGravatar.on('change', function () {
        let gravatarSelected = $useGravatar.prop('checked');

        if (gravatarSelected) {
            $fileInput.val('');
            $image.removeClass('d-none');
            $image.attr('src', "https://www.gravatar.com/avatar/" + $image.data('gravatar') + '?s=512');
            $resetCheckbox.prop('checked', true);
        } else if ($image.data('avatar')) {
            $image.attr('src', $image.data('avatar'));
            $image.removeClass('d-none');
            $resetCheckbox.prop('checked', false);
        } else {
            $image.addClass('d-none');
        }
    });

    $resetCheckbox.on('change', function () {
        let isResetSelected = $resetCheckbox.prop('checked');
        if (isResetSelected) {
            $fileInput.val('');
            $image.addClass('d-none');
        } else if ($image.data('avatar')) {
            $image.attr('src', $image.data('avatar'));
            $image.removeClass('d-none');
        } else {
            $image.addClass('d-none');
        }
    })
});
