document.addEventListener('DOMContentLoaded', function () {
    toggleReviewSettings();

    document.getElementById('id_is_reviewer').addEventListener('change', function () {
        toggleReviewSettings();
    });

    function toggleReviewSettings() {
        let reviewSettings = document.getElementById('review-settings');
        let isReviewerChecked = document.getElementById('id_is_reviewer').checked;

        if (isReviewerChecked) {
            reviewSettings.style.display = 'block';
        } else {
            reviewSettings.style.display = 'none';
        }
    }
});
