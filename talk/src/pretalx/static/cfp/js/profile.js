function setImage(url) {
    const image = document.querySelector('.avatar-form img');
    const imageWrapper = document.querySelector('.avatar-form .form-image-preview');
    const imageLink = imageWrapper.querySelector('a');
    image.src = url;
    imageLink.href = url;
    imageLink.dataset.lightbox = url;
    imageWrapper.classList.remove('d-none');
}

const updateFileInput = (ev) => {
    const imageSelected = ev.target.value !== '';

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

const updateGravatarInput = async (ev) => {
    const checkbox = ev.target;
    const form = checkbox.closest('.avatar-form');
    const gravatarHash = form.querySelector('img').dataset.gravatar;
    const avatarUrl = form.querySelector('img').dataset.avatar;
    const imagePreview = form.querySelector('.form-image-preview');

    if (checkbox.checked) {
        const gravatarCheckUrl = `https://www.gravatar.com/avatar/${gravatarHash}?d=404`;
        const response = await fetch(gravatarCheckUrl);

        if (response.status === 404) {
            checkbox.checked = false;
            checkbox.disabled = true;
            const helpText = checkbox.parentElement.querySelector(".form-text")
            helpText.classList.add("text-warning")
            helpText.classList.remove("text-muted")
            checkbox.parentElement.querySelector("label").classList.add("text-muted")
        } else {
            form.querySelector('input[type=file]').value = '';
            setImage(`https://www.gravatar.com/avatar/${gravatarHash}?s=512`);
            form.querySelector(".avatar-upload").classList.add("d-none")
        }
    }
    if (!checkbox.checked) {
        form.querySelector(".avatar-upload").classList.remove("d-none")
        if (avatarUrl) {
            setImage(avatarUrl);
        } else {
            imagePreview.classList.add('d-none');
        }
    }
}

const initFileInput = function () {
    document.querySelectorAll(".avatar-form").forEach(form => {
        form.querySelector(".form-image-preview").remove() // remove default preview
        document.querySelectorAll('.avatar-upload input[type=file]').forEach((element) => {
            element.addEventListener('change', updateFileInput)
        })
        document.querySelectorAll('#id_get_gravatar').forEach((checkbox) => {
            checkbox.addEventListener('change', updateGravatarInput)
        })
        document.querySelectorAll('.avatar-upload input[type=checkbox]').forEach((element) => {
            element.addEventListener('change', updateCheckbox)
        })
    })
}

onReady(initFileInput)
