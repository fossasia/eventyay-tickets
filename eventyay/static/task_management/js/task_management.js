document.addEventListener('DOMContentLoaded', function() {
    const checkboxes = document.querySelectorAll('.task-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const form = this.closest('.task-form');
            if (form) {
                this.disabled = true;
                form.submit();
            }
        });
    });
});
