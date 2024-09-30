function setImage(url) {
    const image = document.querySelector('.avatar-form img');
    const imageWrapper = document.querySelector('.avatar-form .form-image-preview');
    const imageLink = imageWrapper.querySelector('a');
    image.src = url;
    imageLink.href = url;
    imageLink.dataset.lightbox = url;
    imageWrapper.classList.remove('d-none');
}

/* TODO: rewrite without jquery */

const updateFileInput = (ev) => {
    const imateSelected = ev.target.value !== '';

    if (imageSelected) {
        ev.target.closest('.avatar-form').querySelector('input[type=checkbox]').checked = false;
        const files = ev.target.files;
        if (files) {
            const reader = new FileReader();
            reader.onload = (e) => setImage(e.target.result);
            reader.readAsDataURL(files[0]);
            ev.target.closest('.avatar-form').querySelector('input[type=checkbox]').checked = false;
        } else if (ev.target.closest('.avatar-form').querySelector('img').dataset.avatar) {
            setImage(ev.target.closest('.avatar-form').querySelector('img').dataset.avatar);
            ev.target.closest('.avatar-form').querySelector('input[type=checkbox]').checked = false;
        } else {
            ev.target.closest('.avatar-form').querySelector('.form-image-preview').classList.add('d-none');
        }
    } else if (ev.target.closest('.avatar-form').querySelector('img').dataset.avatar) {
        setImage(ev.target.closest('.avatar-form').querySelector('img').dataset.avatar);
        ev.target.closest('.avatar-form').querySelector('input[type=checkbox]').checked = false;
    } else {
        ev.target.closest('.avatar-form').querySelector('.form-image-preview').classList.add('d-none');
    }
}

const updateCheckbox = (ev) => {
    if (ev.target.checked) {
        ev.target.closest('.avatar-form').querySelector('input[type=file]').value = '';
        ev.target.closest('.avatar-form').querySelector('.form-image-preview').classList.add('d-none');
    } else if (ev.target.closest('.avatar-form').querySelector('img').dataset.avatar) {
        setImage(ev.target.closest('.avatar-form').querySelector('img').dataset.avatar);
    } else {
        ev.target.closest('.avatar-form').querySelector('.form-image-preview').classList.add('d-none');
    }
}

const updateGravatarInput = (ev) => {
    if (ev.target.checked) {
        ev.target.closest('.avatar-form').querySelector('input[type=file]').value = '';
        setImage(`https://www.gravatar.com/avatar/${ev.target.closest('.avatar-form').querySelector('img').dataset.gravatar}?s=512`);
    } else if (ev.target.closest('.avatar-form').querySelector('img').dataset.avatar) {
        setImage(ev.target.closest('.avatar-form').querySelector('img').dataset.avatar);
    } else {
        ev.target.closest('.avatar-form').querySelector('.form-image-preview').classList.add('d-none');
    }
}

const initFileInput = function () {
    document.querySelectorAll('.avatar-form .avatar-upload input[type=file]').forEach((element) => {
        element.addEventListener('change', updateFileInput)
    })
    document.querySelectorAll('.avatar-form #id_get_gravatar').forEach((element) => {
        element.addEventListener('change', updateGravatarInput)
    })
    document.querySelectorAll('.avatar-form .avatar-upload input[type=checkbox]').forEach((element) => {
        element.addEventListener('change', updateCheckbox)
    })
    document.querySelectorAll('.avatar-form .form-group .form-image-preview').forEach((element) => {
        element.classList.add('d-none')
    })
}

onReady(initFileInput)
