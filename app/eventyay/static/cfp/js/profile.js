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
        const helpText = form.querySelector(".form-text");
        if (!helpText.dataset.originalText) {
            helpText.dataset.originalText = helpText.innerText;
        }

        checkbox.disabled = true;
        helpText.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Checking for Gravatar...';

        const gravatarCheckUrl = `https://www.gravatar.com/avatar/${gravatarHash}?d=404`;
        try {
            const response = await fetch(gravatarCheckUrl);
            if (response.status === 404) {
                checkbox.checked = false;
                helpText.classList.add("text-warning");
                helpText.classList.remove("text-muted");
                helpText.innerText = "We couldn't find a Gravatar image associated with your email address.";
                checkbox.parentElement.querySelector("label").classList.add("text-muted");
            } else {
                checkbox.disabled = false;
                helpText.innerText = helpText.dataset.originalText;
                form.querySelector('input[type=file]').value = '';
                setImage(`https://www.gravatar.com/avatar/${gravatarHash}?s=512`);
                form.querySelector(".avatar-upload").classList.add("d-none");
            }
        } catch (error) {
            checkbox.checked = false;
            checkbox.disabled = false;
            helpText.classList.add("text-warning");
            helpText.classList.remove("text-muted");
            helpText.innerText = "Failed to check Gravatar. Please try again later.";
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
        const preview = form.querySelector(".form-image-preview");
        // Don't remove the preview element - it needs to persist
        if (preview) {
            const img = preview.querySelector('img');
            if (img && !img.src) {
                preview.classList.add('d-none');
            }
        }
        
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

const initImageInput = function () {
    document.querySelectorAll('.eventyay-image-input').forEach((container) => {
        const fileInput = container.querySelector('.eventyay-image-file')
        const nameSpan = container.querySelector('.eventyay-file-name')
        const picker = container.querySelector('.eventyay-image-picker')
        const clearCheckbox = container.querySelector('.eventyay-image-clear')
        const current = container.querySelector('.eventyay-image-current')
        const currentName = container.querySelector('.eventyay-image-name')
        const deleteButton = container.querySelector('.eventyay-image-delete')
        const replaceButton = container.querySelector('.eventyay-image-replace')

        if (!fileInput) return

        if (replaceButton) {
            replaceButton.addEventListener('click', () => fileInput.click())
        }

        if (picker) {
            picker.addEventListener('click', (event) => {
                if (event.target.tagName !== 'LABEL') fileInput.click()
            })
        }

        fileInput.addEventListener('change', () => {
            const files = fileInput.files
            const chosen = files && files.length ? files[0].name : ''
            if (nameSpan) nameSpan.textContent = chosen
            if (!chosen) return
            // A new upload and a clear signal together make Django raise
            // FILE_INPUT_CONTRADICTION, so picking a file always cancels the delete.
            if (clearCheckbox) clearCheckbox.checked = false
            if (currentName && current && !current.hidden) {
                currentName.textContent = chosen
                currentName.title = chosen
            }
        })

        if (!deleteButton || !clearCheckbox) return

        deleteButton.addEventListener('click', () => {
            clearCheckbox.checked = true
            clearCheckbox.dispatchEvent(new Event('change', { bubbles: true }))
            fileInput.value = ''
            if (nameSpan) nameSpan.textContent = ''
            if (current) current.hidden = true
            if (picker) picker.hidden = false
            container.classList.remove('has-image')
        })
    })
}

onReady(initFileInput)
onReady(initImageInput)
