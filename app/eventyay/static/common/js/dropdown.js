(function() {
    'use strict';
    
    var initDropdowns = function() {
        // Only handle actual dropdown elements
        var dropdowns = document.querySelectorAll('details.dropdown');
        
        document.addEventListener('click', function(event) {
            dropdowns.forEach(function(dropdown) {
                if (dropdown.hasAttribute('open') && !dropdown.contains(event.target)) {
                    dropdown.removeAttribute('open');
                }
            });
        });
    };
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initDropdowns);
    } else {
        initDropdowns();
    }
})();