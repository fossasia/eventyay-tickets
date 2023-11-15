let lastFocusedInput = null;

const makePlaceholderActive = (placeholder) => {
    placeholder.querySelector('.unavailable').classList.add('d-none');
    placeholder.querySelector('.list-group').classList.remove('d-none');
}

const makePlaceholderInactive = (placeholder) => {
    placeholder.querySelector('.unavailable').classList.remove('d-none');
    placeholder.querySelector('.list-group').classList.add('d-none');
}

const updateVisiblePlaceholders = () => {
    const speakerCount = $('#id_speakers').val().length;
    console.log('speakerCount', speakerCount);
    if (speakerCount === 0) {
        makePlaceholderActive(document.querySelector('#placeholder-submission'))
        makePlaceholderActive(document.querySelector('#placeholder-slot'))
    } else {
        makePlaceholderInactive(document.querySelector('#placeholder-submission'))
        makePlaceholderInactive(document.querySelector('#placeholder-slot'))
    }
}


document.addEventListener('DOMContentLoaded', function() {
    lastFocusedInput = document.querySelector('#id_text_0');

    // When an input matching id_text_\d or id_subject\d is focused, set lastFocusedInput to that input
    document.querySelectorAll('textarea[id^="id_text_"], input[id^="id_subject"]').forEach((input) => {
        input.addEventListener('focus', function() {
            lastFocusedInput = this;
            console.log('lastFocusedInput set to', lastFocusedInput);
        })
    })

    // When any placeholder is clicked, insert its text into lastFocusedInput
    document.querySelectorAll('.placeholder').forEach((placeholder) => {
        placeholder.addEventListener('click', function(e) {
            if (e.target.classList.contains('fa-question')) {
                return;
            }
            if (lastFocusedInput) {
                const placeholderValue = '{' + this.dataset.placeholder + '}'
                const content = lastFocusedInput.value;
                let start = lastFocusedInput.selectionStart;
                let end = lastFocusedInput.selectionEnd;
                const selectedPlaceholderStart = /\{\w*$/.exec(content.substring(0, start));
                var selectedPlaceholderEnd = /^\w*\}/.exec(content.substring(end));
                if (selectedPlaceholderStart) {
                    start -= selectedPlaceholderStart[0].length
                }
                if (selectedPlaceholderEnd) {
                    end += selectedPlaceholderEnd[0].length;
                }

                lastFocusedInput.value = content.substring(0, start) + placeholderValue + content.substring(end);
                lastFocusedInput.selectionStart = start;
                lastFocusedInput.selectionEnd = start + placeholderValue.length
                lastFocusedInput.focus();
            }
        })
    })

    // When an individual speaker is added, hide all placeholders that are proposal-specific
    $('#id_speakers').on('change', () => updateVisiblePlaceholders())
    updateVisiblePlaceholders()
})
