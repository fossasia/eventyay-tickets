// platform-fee-vouchers.js
export function initCopyButtons() {
  const copyButtons = document.querySelectorAll('.pfv-code-copy');
  copyButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const code = btn.getAttribute('data-code');
      if (code) {
        navigator.clipboard.writeText(code).then(() => {
          const icon = btn.querySelector('i');
          if (icon) {
            const originalClassName = icon.className;
            icon.className = 'fa fa-check text-success';
            setTimeout(() => {
              icon.className = originalClassName;
            }, 2000);
          }
        });
      }
    });
  });
}

export function initActionsDropdowns() {
  const toggles = document.querySelectorAll('.pfv-actions-toggle');
  toggles.forEach(toggle => {
    toggle.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const dropdown = toggle.closest('.pfv-actions-dropdown');
      
      // Close all others
      document.querySelectorAll('.pfv-actions-dropdown.open').forEach(openDrop => {
        if (openDrop !== dropdown) openDrop.classList.remove('open');
      });
      
      dropdown.classList.toggle('open');
    });
  });

  document.addEventListener('click', () => {
    document.querySelectorAll('.pfv-actions-dropdown.open').forEach(openDrop => {
      openDrop.classList.remove('open');
    });
  });
}

export function initScopeToggle() {
  const scopeRadios = document.querySelectorAll('input[name="scope_type"]');
  const scopeEvents = document.getElementById('scope-events');
  const scopeOrganisers = document.getElementById('scope-organisers');
  
  if (!scopeRadios.length) return;

  function updateVisibility() {
    const selected = document.querySelector('input[name="scope_type"]:checked');
    if (!selected) return;
    
    const val = selected.value;
    if (scopeEvents) scopeEvents.style.display = (val === 'specific_events' || val === 'both') ? 'block' : 'none';
    if (scopeOrganisers) scopeOrganisers.style.display = (val === 'all_by_organisers' || val === 'both') ? 'block' : 'none';
  }

  scopeRadios.forEach(radio => {
    radio.addEventListener('change', updateVisibility);
  });
  updateVisibility();
}

export function initWaiverTypeToggle() {
  const waiverSelect = document.getElementById('id_waiver_type');
  const valueContainer = document.getElementById('waiver-value-container');
  if (!waiverSelect || !valueContainer) return;

  function updateVisibility() {
    const val = waiverSelect.value;
    valueContainer.style.display = (val === 'percent' || val === 'subtract') ? 'block' : 'none';
  }

  waiverSelect.addEventListener('change', updateVisibility);
  updateVisibility();
}

export function initLiveSummary() {
  const panel = document.getElementById('summary-panel');
  if (!panel) return;
  
  const codeField = document.getElementById('id_code');
  const summaryCode = document.getElementById('summary-code');
  if (codeField && summaryCode) {
    codeField.addEventListener('input', () => {
      summaryCode.textContent = codeField.value || '...';
    });
  }

  const statusField = document.getElementById('id_status');
  const summaryStatus = document.getElementById('summary-status');
  if (statusField && summaryStatus) {
    statusField.addEventListener('change', () => {
      summaryStatus.textContent = statusField.options[statusField.selectedIndex].text;
    });
  }

  const waiverField = document.getElementById('id_waiver_type');
  const valueField = document.getElementById('id_value');
  const summaryWaiver = document.getElementById('summary-waiver');
  if (waiverField && valueField && summaryWaiver) {
    const updateWaiver = () => {
      const wType = waiverField.value;
      const wVal = valueField.value;
      if (wType === 'none') summaryWaiver.textContent = 'No effect';
      else if (wType === 'percent_100') summaryWaiver.textContent = '100% waiver';
      else if (wType === 'percent') summaryWaiver.textContent = (wVal || '0') + '% waiver';
      else if (wType === 'subtract') summaryWaiver.textContent = 'Fixed credit';
      else summaryWaiver.textContent = '...';
    };
    waiverField.addEventListener('change', updateWaiver);
    valueField.addEventListener('input', updateWaiver);
    updateWaiver();
  }
}

export function init() {
  initCopyButtons();
  initActionsDropdowns();
  initScopeToggle();
  initWaiverTypeToggle();
  initLiveSummary();
}

document.addEventListener('DOMContentLoaded', init);
