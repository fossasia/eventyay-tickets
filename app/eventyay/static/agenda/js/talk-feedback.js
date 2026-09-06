/**
 * Session talk feedback UI: replies, reactions, ratings, emoji picker, and speaker filter.
 */

const COMMON_EMOJIS = [
  '😀', '😃', '😄', '😁', '😅', '😂', '🤣', '😊', '😇', '🙂',
  '😉', '😌', '😍', '🥰', '😘', '😋', '😜', '🤪', '🤨', '🧐',
  '🤓', '😎', '🤩', '🥳', '😏', '😒', '😞', '😔', '😟', '😕',
  '🙁', '😣', '😖', '😫', '😩', '🥺', '😢', '😭', '😤', '😠',
  '🤯', '😳', '🥵', '🥶', '😱', '😨', '🤗', '🤔', '🤭', '🤫',
  '😶', '😐', '😑', '😬', '🙄', '😯', '😮', '😲', '🥱', '😴',
  '🤤', '😪', '😵', '🤠', '😈', '👍', '👎', '👏', '🙌', '🙏',
  '✌️', '🤞', '🤟', '🤘', '👌', '👈', '👉', '👆', '👇', '👋',
  '💪', '❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '💔', '💕',
  '🔥', '⭐', '🌟', '✨', '💯', '🎉', '🎊', '✅', '❌', '👀',
];

function insertTextAtCursor(textarea, text) {
  const start = textarea.selectionStart ?? textarea.value.length;
  const end = textarea.selectionEnd ?? textarea.value.length;
  const before = textarea.value.slice(0, start);
  const after = textarea.value.slice(end);
  textarea.value = before + text + after;
  const caret = start + text.length;
  textarea.setSelectionRange(caret, caret);
  textarea.focus();
  textarea.dispatchEvent(new Event('input', { bubbles: true }));
}

function ensureEmojiPicker(root) {
  let picker = document.getElementById('talk-emoji-picker');
  if (picker) {
    return picker;
  }
  picker = document.createElement('div');
  picker.id = 'talk-emoji-picker';
  picker.className = 'talk-emoji-picker d-none';
  picker.setAttribute('role', 'dialog');
  const ariaLabel = typeof window.gettext === 'function' ? window.gettext('Emoji picker') : 'Emoji picker';
  picker.setAttribute('aria-label', ariaLabel);
  const grid = document.createElement('div');
  grid.className = 'talk-emoji-picker__grid';
  COMMON_EMOJIS.forEach((emoji) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'talk-emoji-picker__emoji';
    btn.textContent = emoji;
    btn.setAttribute('aria-label', emoji);
    grid.appendChild(btn);
  });
  picker.appendChild(grid);
  (root.body || document.body).appendChild(picker);
  return picker;
}

function hideEmojiPicker(picker, toggle) {
  if (!picker) {
    return;
  }
  picker.classList.add('d-none');
  const active = toggle || picker._activeToggle;
  picker._activeToggle = null;
  if (active) {
    active.setAttribute('aria-expanded', 'false');
  }
}

function positionEmojiPicker(picker, toggle) {
  const rect = toggle.getBoundingClientRect();
  const pickerWidth = Math.min(264, window.innerWidth - 16);
  const left = Math.min(
    Math.max(8, rect.left - pickerWidth + rect.width),
    window.innerWidth - pickerWidth - 8,
  );
  let top = rect.bottom + 6;
  const estimatedHeight = 240;
  if (top + estimatedHeight > window.innerHeight - 8) {
    top = Math.max(8, rect.top - estimatedHeight - 6);
  }
  picker.style.width = `${pickerWidth}px`;
  picker.style.left = `${left}px`;
  picker.style.top = `${top}px`;
}

function initEmojiPickers(root = document) {
  const picker = ensureEmojiPicker(document);
  const toggles = root.querySelectorAll('.emoji-picker-toggle');

  toggles.forEach((toggle) => {
    if (toggle.dataset.emojiPickerInit === 'true') {
      return;
    }
    toggle.dataset.emojiPickerInit = 'true';
    toggle.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      const isOpen = !picker.classList.contains('d-none') && picker._activeToggle === toggle;
      if (isOpen) {
        hideEmojiPicker(picker, toggle);
        return;
      }
      if (picker._activeToggle && picker._activeToggle !== toggle) {
        picker._activeToggle.setAttribute('aria-expanded', 'false');
      }
      picker.classList.remove('d-none');
      picker._activeToggle = toggle;
      toggle.setAttribute('aria-expanded', 'true');
      positionEmojiPicker(picker, toggle);
      picker._activeTextarea = toggle
        .closest('.comment-compose-row, .youtube-comment-form, form')
        ?.querySelector('textarea');
    });
  });

  if (picker.dataset.emojiPickerGlobalInit === 'true') {
    return;
  }
  picker.dataset.emojiPickerGlobalInit = 'true';

  picker.addEventListener('click', (event) => {
    const btn = event.target.closest('.talk-emoji-picker__emoji');
    if (!btn) {
      return;
    }
    const textarea = picker._activeTextarea;
    if (textarea) {
      insertTextAtCursor(textarea, btn.textContent);
    }
    hideEmojiPicker(picker);
  });

  document.addEventListener('click', (event) => {
    if (picker.classList.contains('d-none')) {
      return;
    }
    if (event.target.closest('#talk-emoji-picker, .emoji-picker-toggle')) {
      return;
    }
    hideEmojiPicker(picker);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !picker.classList.contains('d-none')) {
      hideEmojiPicker(picker);
    }
  });
}

function initRateMeDialog(root = document) {

  root.querySelectorAll('fieldset.rate-me-emoji-rating').forEach((fieldset) => {
    if (fieldset.dataset.rateMeInit === 'true') {
      return;
    }
    fieldset.dataset.rateMeInit = 'true';
    fieldset.querySelectorAll('.rate-me-emoji-option input[type="radio"]').forEach((radio) => {
      radio.addEventListener('change', () => {
        fieldset.querySelectorAll('.rate-me-emoji-option').forEach((option) => {
          option.classList.toggle('is-selected', option.querySelector('input')?.checked === true);
        });
      });
    });
  });
}

function updateCommentCount(list, visibleCount) {
  const label = document.querySelector('.comment-count-label');
  if (!label) {
    return;
  }
  const total = Number(label.dataset.total || '0');
  label.textContent = String(visibleCount);
  if (visibleCount !== total && total > 0) {
    label.dataset.filtered = 'true';
  } else {
    label.dataset.filtered = 'false';
  }
}

function filterCommentsBySpeaker(select) {
  const list = document.querySelector('.comment-list');
  if (!list || !select) {
    return;
  }
  const speakerId = select.value || '';
  const items = list.querySelectorAll('.comment-item[data-speaker-id]');
  let visible = 0;
  items.forEach((item) => {
    // Only filter top-level comments (replies stay nested under parents).
    if (item.classList.contains('reply-item')) {
      return;
    }
    const itemSpeaker = item.getAttribute('data-speaker-id') || '';
    // Selected speaker sees their targeted comments plus general (all speakers) ones.
    const show = !speakerId || itemSpeaker === speakerId || itemSpeaker === '';
    item.classList.toggle('d-none', !show);
    if (show) {
      visible += 1;
    }
  });

  const emptyEl = list.querySelector('.speaker-filter-empty');
  if (emptyEl) {
    if (speakerId && visible === 0) {
      emptyEl.textContent = list.getAttribute('data-empty-filter-text') || '';
      emptyEl.classList.remove('d-none');
    } else {
      emptyEl.classList.add('d-none');
      emptyEl.textContent = '';
    }
  }
  updateCommentCount(list, speakerId ? visible : Number(
    document.querySelector('.comment-count-label')?.dataset.total || visible,
  ));
}

function initSpeakerFilter(root = document) {
  const selects = root.querySelectorAll('.main-feedback-form .speaker-target-select, select.speaker-target-select');
  selects.forEach((select) => {
    if (select.dataset.speakerFilterInit === 'true') {
      return;
    }
    // Only the compose-form select drives list filtering.
    if (!select.closest('.main-feedback-form')) {
      return;
    }
    select.dataset.speakerFilterInit = 'true';
    select.addEventListener('change', () => {
      filterCommentsBySpeaker(select);
    });
  });
}

export function initTalkFeedback(root = document) {
  const replyBtns = root.querySelectorAll('.reply-btn');
  replyBtns.forEach((btn) => {
    if (btn.dataset.talkFeedbackInit === 'true') {
      return;
    }
    btn.dataset.talkFeedbackInit = 'true';
    btn.addEventListener('click', function () {
      const formId = this.getAttribute('data-form-id') || this.getAttribute('data-id');
      const parentId = this.getAttribute('data-parent-id') || this.getAttribute('data-id');
      const formContainer = root.getElementById
        ? root.getElementById('reply-form-' + formId)
        : document.getElementById('reply-form-' + formId);
      if (!formContainer) {
        return;
      }
      const replyItem = this.closest('.reply-item');
      if (replyItem) {
        replyItem.parentNode.insertBefore(formContainer, replyItem.nextSibling);
      } else {
        const actionsContainer = this.closest('.comment-actions');
        if (actionsContainer) {
          actionsContainer.parentNode.insertBefore(formContainer, actionsContainer.nextSibling);
        }
      }
      const parentInput = formContainer.querySelector('input[name="parent"]');
      if (parentInput && parentId) {
        parentInput.value = parentId;
      }
      formContainer.classList.remove('d-none');
      formContainer.style.display = 'block';
      const textarea = formContainer.querySelector('textarea');
      if (textarea) {
        textarea.focus();
      }
    });
  });

  const reactBtns = root.querySelectorAll('.react-btn');
  reactBtns.forEach((btn) => {
    if (btn.dataset.talkFeedbackReactInit === 'true') {
      return;
    }
    btn.dataset.talkFeedbackReactInit = 'true';
    btn.addEventListener('click', function () {
      let action = this.getAttribute('data-action');
      if (this.classList.contains('active-vote')) {
        action = 'remove';
      }
      const url = this.getAttribute('data-url');
      const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
      if (!csrfInput) {
        return;
      }
      const csrfToken = csrfInput.value;
      const container = this.closest('.d-flex');

      const formData = new FormData();
      formData.append('action', action);

      fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
        },
        body: formData,
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.error) {
            alert(data.error);
            return;
          }

          const upvoteBtn = container.querySelector('[data-action="upvote"]');
          const downvoteBtn = container.querySelector('[data-action="downvote"]');
          const upvoteIcon = upvoteBtn.querySelector('i');
          const downvoteIcon = downvoteBtn.querySelector('i');

          upvoteBtn.classList.remove('active-vote');
          upvoteIcon.className = 'fa fa-thumbs-o-up';
          downvoteBtn.classList.remove('active-vote');
          downvoteIcon.className = 'fa fa-thumbs-o-down';

          if (action === 'upvote') {
            upvoteBtn.classList.add('active-vote');
            upvoteIcon.className = 'fa fa-thumbs-up text-success';
          } else if (action === 'downvote') {
            downvoteBtn.classList.add('active-vote');
            downvoteIcon.className = 'fa fa-thumbs-down text-danger';
          }

          container.querySelector('.upvote-count').textContent = data.upvotes;
          container.querySelector('.downvote-count').textContent = data.downvotes;
        })
        .catch((error) => {
          console.error('Talk feedback reaction failed', error);
        });
    });
  });

  const starContainers = root.querySelectorAll('.youtube-rating-stars');
  starContainers.forEach((container) => {
    if (container.dataset.talkFeedbackStarsInit === 'true') {
      return;
    }
    container.dataset.talkFeedbackStarsInit = 'true';
    const labels = Array.from(container.querySelectorAll('.star-label'));

    function updateStars(index) {
      labels.forEach((lbl, i) => {
        if (i <= index) {
          lbl.classList.add('active');
        } else {
          lbl.classList.remove('active');
        }
      });
    }

    labels.forEach((label, index) => {
      label.addEventListener('mouseover', () => {
        updateStars(index);
      });

      label.addEventListener('click', () => {
        labels.forEach((lbl) => lbl.classList.remove('selected'));
        label.classList.add('selected');
        const radio = label.querySelector('input[type="radio"]');
        if (radio) {
          radio.checked = true;
        }
      });
    });

    container.addEventListener('mouseleave', () => {
      labels.forEach((lbl) => lbl.classList.remove('active'));
      const selectedIndex = labels.findIndex((lbl) => lbl.classList.contains('selected'));
      if (selectedIndex !== -1) {
        updateStars(selectedIndex);
      }
    });

    const initialSelected = labels.findIndex((lbl) => lbl.classList.contains('selected'));
    if (initialSelected !== -1) {
      updateStars(initialSelected);
    }
  });

  root.querySelectorAll('.reply-form-container').forEach((form) => {
    form.style.display = 'none';
  });

  root.querySelectorAll('.comment-text-collapsed').forEach((content) => {
    if (content.dataset.talkFeedbackReadMoreInit === 'true') {
      return;
    }
    if (content.scrollHeight <= content.clientHeight) {
      return;
    }
    const btn = content.nextElementSibling;
    if (!btn || !btn.classList.contains('read-more-btn')) {
      return;
    }
    content.dataset.talkFeedbackReadMoreInit = 'true';
    btn.classList.remove('d-none');
    btn.addEventListener('click', function () {
      const expanded = this.getAttribute('data-expanded') === 'true';
      const readMoreText = this.getAttribute('data-read-more');
      const showLessText = this.getAttribute('data-show-less');

      if (expanded) {
        content.classList.add('comment-text-collapsed');
        this.textContent = readMoreText;
        this.setAttribute('data-expanded', 'false');
      } else {
        content.classList.remove('comment-text-collapsed');
        this.textContent = showLessText;
        this.setAttribute('data-expanded', 'true');
      }
    });
  });

  root.querySelectorAll('.replies-toggle-btn').forEach((btn) => {
    if (btn.dataset.talkFeedbackRepliesInit === 'true') {
      return;
    }
    btn.dataset.talkFeedbackRepliesInit = 'true';
    btn.addEventListener('click', function () {
      const targetId = this.getAttribute('data-target');
      const target = document.getElementById(targetId);
      if (!target) {
        return;
      }
      target.classList.toggle('d-none');
      const expanded = this.getAttribute('data-expanded') === 'true';
      const icon = this.querySelector('i');
      if (expanded) {
        this.setAttribute('data-expanded', 'false');
        icon.classList.remove('fa-caret-up');
        icon.classList.add('fa-caret-down');
      } else {
        this.setAttribute('data-expanded', 'true');
        icon.classList.remove('fa-caret-down');
        icon.classList.add('fa-caret-up');
      }
    });
  });

  root.querySelectorAll('[data-confirm-message]').forEach((button) => {
    if (button.dataset.talkFeedbackConfirmInit === 'true') {
      return;
    }
    button.dataset.talkFeedbackConfirmInit = 'true';
    button.addEventListener('click', function (event) {
      const message = this.getAttribute('data-confirm-message');
      if (message && !window.confirm(message)) {
        event.preventDefault();
      }
    });
  });

  initEmojiPickers(root);
  initRateMeDialog(root);
  initSpeakerFilter(root);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => initTalkFeedback());
} else {
  initTalkFeedback();
}
