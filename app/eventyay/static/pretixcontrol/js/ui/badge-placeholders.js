(function () {
  'use strict';

  function initPlaceholderGrids() {
    var widgets = document.querySelectorAll('[data-placeholder-grid-widget]');
    widgets.forEach(function (widget) {
      if (!widget || widget.dataset.initialized === 'true') return;
      widget.dataset.initialized = 'true';

      var summary = widget.querySelector('[data-placeholder-grid-summary]');
      var searchInput = widget.querySelector('[data-placeholder-grid-search]');
      var badgesContainer = widget.querySelector('[data-placeholder-grid-badges]');
      var countLabel = widget.querySelector('[data-placeholder-grid-count]');
      var noResults = widget.querySelector('[data-placeholder-grid-no-results]');
      var selectDefaultBtn = widget.querySelector('[data-placeholder-grid-select-default]');
      var selectAllBtn = widget.querySelector('[data-placeholder-grid-select-all]');
      var deselectAllBtn = widget.querySelector('[data-placeholder-grid-deselect-all]');
      var categoryGroups = Array.from(widget.querySelectorAll('[data-placeholder-category-group]'));
      var cells = Array.from(widget.querySelectorAll('[data-placeholder-grid-cell]'));

      function syncSummary() {
        var selectedCount = 0;
        var maxBadges = 6;
        if (badgesContainer) badgesContainer.innerHTML = '';

        cells.forEach(function (cell) {
          var checkbox = cell.querySelector('input[type="checkbox"]');
          if (checkbox && checkbox.checked) {
            cell.classList.add('is-checked');
            selectedCount++;
            if (selectedCount <= maxBadges && badgesContainer) {
              var badge = document.createElement('span');
              badge.className = 'placeholder-grid-badge';
              badge.textContent = cell.getAttribute('data-placeholder-name') || checkbox.value;
              badgesContainer.appendChild(badge);
            }
          } else {
            cell.classList.remove('is-checked');
          }
        });

        if (countLabel) {
          if (selectedCount === 0) {
            countLabel.textContent = countLabel.dataset.emptyText || 'No placeholders selected';
          } else if (selectedCount > maxBadges) {
            var diff = selectedCount - maxBadges;
            countLabel.textContent = '+' + diff + ' ' + (countLabel.dataset.selectedPluralText || 'placeholders enabled');
          } else {
            countLabel.textContent = selectedCount === 1 ? '1 ' + (countLabel.dataset.selectedSingularText || 'placeholder enabled') : selectedCount + ' ' + (countLabel.dataset.selectedPluralText || 'placeholders enabled');
          }
        }
      }

      if (summary) {
        summary.addEventListener('click', function (e) {
          e.preventDefault();
          widget.classList.toggle('is-collapsed');
          var isExpanded = !widget.classList.contains('is-collapsed');
          summary.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
        });

        summary.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            summary.click();
          }
        });
      }

      cells.forEach(function (cell) {
        var checkbox = cell.querySelector('input[type="checkbox"]');
        if (!checkbox) return;
        checkbox.addEventListener('change', function () {
          syncSummary();
        });

        cell.addEventListener('click', function (e) {
          if (e.target.tagName.toLowerCase() === 'input' || e.target.closest('label')) {
            return;
          }
          checkbox.checked = !checkbox.checked;
          syncSummary();
        });
      });

      if (searchInput) {
        searchInput.addEventListener('input', function () {
          var query = searchInput.value.trim().toLowerCase();
          var totalVisible = 0;

          categoryGroups.forEach(function (group) {
            var groupCells = Array.from(group.querySelectorAll('[data-placeholder-grid-cell]'));
            var visibleInGroup = 0;

            groupCells.forEach(function (cell) {
              var name = (cell.getAttribute('data-placeholder-name') || '').toLowerCase();
              var key = (cell.getAttribute('data-placeholder-key') || '').toLowerCase();
              var matches = !query || name.indexOf(query) !== -1 || key.indexOf(query) !== -1;
              cell.style.display = matches ? '' : 'none';
              if (matches) visibleInGroup++;
            });

            group.style.display = visibleInGroup > 0 ? '' : 'none';
            totalVisible += visibleInGroup;
          });

          if (noResults) {
            noResults.style.display = totalVisible === 0 ? 'block' : 'none';
          }
        });
      }

      if (selectDefaultBtn) {
        selectDefaultBtn.addEventListener('click', function (e) {
          e.preventDefault();
          cells.forEach(function (cell) {
            var isDefault = cell.getAttribute('data-is-default') === 'true';
            var checkbox = cell.querySelector('input[type="checkbox"]');
            if (checkbox) {
              checkbox.checked = isDefault;
            }
          });
          syncSummary();
        });
      }

      if (selectAllBtn) {
        selectAllBtn.addEventListener('click', function (e) {
          e.preventDefault();
          cells.forEach(function (cell) {
            var checkbox = cell.querySelector('input[type="checkbox"]');
            if (checkbox && cell.style.display !== 'none') {
              checkbox.checked = true;
            }
          });
          syncSummary();
        });
      }

      if (deselectAllBtn) {
        deselectAllBtn.addEventListener('click', function (e) {
          e.preventDefault();
          cells.forEach(function (cell) {
            var checkbox = cell.querySelector('input[type="checkbox"]');
            if (checkbox && cell.style.display !== 'none') {
              checkbox.checked = false;
            }
          });
          syncSummary();
        });
      }

      syncSummary();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPlaceholderGrids);
  } else {
    initPlaceholderGrids();
  }
})();
