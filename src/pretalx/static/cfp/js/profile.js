function setImage(url) {
    const image = document.querySelector('.avatar-form img');
    const imageWrapper = document.querySelector('.avatar-form .form-image-preview');
    const imageLink = imageWrapper.querySelector('a');
    image.src = url;
    imageLink.href = url;
    imageLink.dataset.lightbox = url;
    imageWrapper.classList.remove('d-none');
}

$(function () {
    const $imageLink = $(".avatar-form .form-image-preview a");
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
                reader.onload = function (e) { setImage(e.target.result); };
                reader.readAsDataURL(files[0]);
                $resetCheckbox.prop('checked', false);
            } else if ($image.data('avatar')) {
                setImage($image.data('avatar'));
                $resetCheckbox.prop('checked', false);
            } else {
                $imageWrapper.addClass('d-none');
            }
        } else if ($image.data('avatar')) {
            setImage($image.data('avatar'));
            $resetCheckbox.prop('checked', false);
        } else {
            $imageWrapper.addClass('d-none');
        }
    });

    $useGravatar.on('change', function () {
        let gravatarSelected = $useGravatar.prop('checked');

        if (gravatarSelected) {
            $fileInput.val('');
            console.log($image.data('gravatar'));
            setImage("https://www.gravatar.com/avatar/" + $image.data('gravatar') + '?s=512');
            $resetCheckbox.prop('checked', true);
        } else if ($image.data('avatar')) {
            setImage($image.data('avatar'));
            $resetCheckbox.prop('checked', false);
        } else {
            $imageWrapper.addClass('d-none');
        }
    });

    $resetCheckbox.on('change', function () {
        let isResetSelected = $resetCheckbox.prop('checked');
        if (isResetSelected) {
            $fileInput.val('');
            $imageWrapper.addClass('d-none');
        } else if ($image.data('avatar')) {
            setImage($image.data('avatar'));
        } else {
            $imageWrapper.addClass('d-none');
        }
    })
});
