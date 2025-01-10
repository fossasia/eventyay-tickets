document.addEventListener('DOMContentLoaded', function () {
    const loginForm = document.getElementById('login-form');
    const toggleLogin = document.getElementById('toggle-login');
    const collapseStateKey = 'loginFormCollapseState';

    // Restore state from localStorage
    const storedState = localStorage.getItem(collapseStateKey);
    console.log(storedState);
    if (storedState === 'open') {
        loginForm.classList.add('in');
    } else {
        loginForm.classList.remove('in');
    }

    // Save state on toggle
    toggleLogin.addEventListener('click', function () {
        if (loginForm.classList.contains('in')) {
            localStorage.setItem(collapseStateKey, 'closed');
        } else {
            localStorage.setItem(collapseStateKey, 'open');
        }
    });
});
