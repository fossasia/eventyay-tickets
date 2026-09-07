function initOrdersDateFilter() {
  const params = new URLSearchParams(window.location.search);
  ['date_from', 'date_to'].forEach((name) => {
    if (!params.get(name)) {
      const input = document.querySelector(`input[name="${name}"]`);
      if (input) {
        input.value = '';
      }
    }
  });

  const fromInput = document.querySelector('input[name="date_from"]');
  const toInput = document.querySelector('input[name="date_to"]');

  if (fromInput && toInput) {
    function syncRangeLimits() {
      if (fromInput.value) {
        toInput.min = fromInput.value;
      } else {
        toInput.removeAttribute('min');
      }

      if (toInput.value) {
        fromInput.max = toInput.value;
      } else {
        fromInput.removeAttribute('max');
      }
    }

    fromInput.addEventListener('change', syncRangeLimits);
    toInput.addEventListener('change', syncRangeLimits);
    syncRangeLimits();
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initOrdersDateFilter);
} else {
  initOrdersDateFilter();
}

export { initOrdersDateFilter };
