// Exhibitor Plugin JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize exhibitor functionality
    initializeExhibitorSearch();
    initializeExhibitorFilters();
    initializeLeadManagement();
});

function initializeExhibitorSearch() {
    const searchInput = document.querySelector('.exhibitor-search input');
    if (!searchInput) return;
    
    let searchTimeout;
    searchInput.addEventListener('input', function(e) {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            filterExhibitors(e.target.value);
        }, 300);
    });
}

function initializeExhibitorFilters() {
    const filterSelects = document.querySelectorAll('.exhibitor-filter select');
    filterSelects.forEach(select => {
        select.addEventListener('change', function() {
            applyFilters();
        });
    });
}

function initializeLeadManagement() {
    // Initialize lead status updates
    const statusSelects = document.querySelectorAll('.lead-status-select');
    statusSelects.forEach(select => {
        select.addEventListener('change', function() {
            updateLeadStatus(this.dataset.leadId, this.value);
        });
    });
    
    // Initialize lead notes editing
    const noteButtons = document.querySelectorAll('.edit-note-btn');
    noteButtons.forEach(button => {
        button.addEventListener('click', function() {
            editLeadNote(this.dataset.leadId);
        });
    });
}

function filterExhibitors(searchTerm) {
    const exhibitorCards = document.querySelectorAll('.exhibitor-card');
    const lowerSearchTerm = searchTerm.toLowerCase();
    
    exhibitorCards.forEach(card => {
        const name = card.querySelector('.exhibitor-name').textContent.toLowerCase();
        const description = card.querySelector('.exhibitor-description')?.textContent.toLowerCase() || '';
        
        if (name.includes(lowerSearchTerm) || description.includes(lowerSearchTerm)) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
    
    updateExhibitorCount();
}

function applyFilters() {
    const categoryFilter = document.querySelector('#category-filter')?.value || '';
    const boothFilter = document.querySelector('#booth-filter')?.value || '';
    const exhibitorCards = document.querySelectorAll('.exhibitor-card');
    
    exhibitorCards.forEach(card => {
        let show = true;
        
        if (categoryFilter && !card.dataset.categories?.includes(categoryFilter)) {
            show = false;
        }
        
        if (boothFilter && !card.dataset.boothId?.includes(boothFilter)) {
            show = false;
        }
        
        card.style.display = show ? 'block' : 'none';
    });
    
    updateExhibitorCount();
}

function updateExhibitorCount() {
    const visibleCards = document.querySelectorAll('.exhibitor-card[style*="block"], .exhibitor-card:not([style*="none"])');
    const countElement = document.querySelector('.exhibitor-count');
    if (countElement) {
        countElement.textContent = `${visibleCards.length} exhibitors`;
    }
}

function updateLeadStatus(leadId, status) {
    fetch(`/api/exhibitor/leads/${leadId}/`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({
            follow_up_status: status
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Lead status updated successfully', 'success');
            updateLeadStatusDisplay(leadId, status);
        } else {
            showNotification('Failed to update lead status', 'error');
        }
    })
    .catch(error => {
        console.error('Error updating lead status:', error);
        showNotification('Error updating lead status', 'error');
    });
}

function editLeadNote(leadId) {
    const noteElement = document.querySelector(`[data-lead-id="${leadId}"] .lead-note`);
    const currentNote = noteElement.textContent;
    
    const newNote = prompt('Edit note:', currentNote);
    if (newNote !== null && newNote !== currentNote) {
        updateLeadNote(leadId, newNote);
    }
}

function updateLeadNote(leadId, note) {
    fetch(`/api/exhibitor/leads/${leadId}/`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({
            note: note
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Note updated successfully', 'success');
            document.querySelector(`[data-lead-id="${leadId}"] .lead-note`).textContent = note;
        } else {
            showNotification('Failed to update note', 'error');
        }
    })
    .catch(error => {
        console.error('Error updating note:', error);
        showNotification('Error updating note', 'error');
    });
}

function updateLeadStatusDisplay(leadId, status) {
    const statusElement = document.querySelector(`[data-lead-id="${leadId}"] .lead-status`);
    if (statusElement) {
        statusElement.className = `lead-status ${status}`;
        statusElement.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    }
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Style the notification
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 4px;
        color: white;
        font-weight: bold;
        z-index: 10000;
        opacity: 0;
        transition: opacity 0.3s;
    `;
    
    // Set background color based on type
    const colors = {
        success: '#28a745',
        error: '#dc3545',
        warning: '#ffc107',
        info: '#17a2b8'
    };
    notification.style.backgroundColor = colors[type] || colors.info;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Fade in
    setTimeout(() => {
        notification.style.opacity = '1';
    }, 100);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

function getCsrfToken() {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    return csrfToken ? csrfToken.value : '';
}

// Export functions for use in other scripts
window.ExhibitorJS = {
    filterExhibitors,
    applyFilters,
    updateLeadStatus,
    editLeadNote,
    showNotification
};