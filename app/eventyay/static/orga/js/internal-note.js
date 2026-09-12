document.addEventListener('DOMContentLoaded', function() {
    var noteTextarea = document.getElementById('internal_note_textarea');
    var noteCounter = document.getElementById('internal_note_counter');
    if (noteTextarea && noteCounter) {
        noteTextarea.addEventListener('input', function() {
            noteCounter.innerText = this.value.length;
        });
    }
});
