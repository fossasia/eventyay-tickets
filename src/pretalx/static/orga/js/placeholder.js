let lastFocusedInput = null;

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

})
