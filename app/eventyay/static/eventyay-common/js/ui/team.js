document.addEventListener('DOMContentLoaded', () => {
    const reviewerCheckbox = document.getElementById('id_is_reviewer');
    const reviewSettings = document.getElementById('review-settings');

    const toggleReviewSettings = () => {
        if (!reviewerCheckbox || !reviewSettings) return;

        reviewSettings.style.display = reviewerCheckbox.checked ? 'block' : 'none';
    };

    if (reviewerCheckbox) {
        reviewerCheckbox.addEventListener('change', toggleReviewSettings);
        toggleReviewSettings();
    }
});
