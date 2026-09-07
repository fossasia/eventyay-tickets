/**
 * Builds the toolbar DOM element for a Tiptap editor instance.
 * @param {import('@tiptap/core').Editor} editor
 * @param {object} options
 * @param {string} options.profile - 'richtext' | 'email'
 * @param {string[]} options.placeholders - list of placeholder variable names (email profile only)
 * @param {string} options.previewUrl - URL for email preview endpoint (email profile only)
 * @param {string} options.locale - BCP 47 locale for the active editor tab (email profile only)
 * @param {HTMLElement} [options.editorEl] - visual editor root used for HTML source toggle
 * @param {HTMLTextAreaElement} [options.textarea] - backing form textarea
 * @returns {HTMLElement}
 */
export function buildToolbar(
  editor,
  { profile, placeholders = [], previewUrl = '', locale = '', editorEl = null, textarea = null },
) {
  const bar = document.createElement('div')
  bar.className = 'tiptap-toolbar'
  bar.setAttribute('role', 'toolbar')
  bar.setAttribute('aria-label', 'Text formatting')

  const button = (label, title, action, isActiveKey = null) => {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'tiptap-btn'
    btn.title = title
    btn.setAttribute('aria-label', title)
    const doc = new DOMParser().parseFromString(label, 'text/html')
    btn.append(...doc.body.childNodes)
    btn.addEventListener('click', (e) => {
      e.preventDefault()
      action()
      editor.view.focus()
      syncActive()
    })
    if (isActiveKey) {
      btn.dataset.activeKey = isActiveKey
    }
    return btn
  }

  const separator = () => {
    const sep = document.createElement('span')
    sep.className = 'tiptap-separator'
    sep.setAttribute('aria-hidden', 'true')
    return sep
  }

  const boldBtn = button('<b>B</b>', 'Bold', () => editor.chain().focus().toggleBold().run(), 'bold')
  const italicBtn = button('<i>I</i>', 'Italic', () => editor.chain().focus().toggleItalic().run(), 'italic')
  const underlineBtn = button('<u>U</u>', 'Underline', () => editor.chain().focus().toggleUnderline().run(), 'underline')
  const ulBtn = button('&#8226;&#8212;', 'Bullet list', () => editor.chain().focus().toggleBulletList().run(), 'bulletList')
  const olBtn = button('1.&#8212;', 'Numbered list', () => editor.chain().focus().toggleOrderedList().run(), 'orderedList')
  const linkWrapper = document.createElement('span')
  linkWrapper.className = 'tiptap-link-menu'
  const linkBtn = button('&#128279;', 'Insert link', () => showLinkPopover(editor, linkWrapper), 'link')
  linkWrapper.append(linkBtn)
  const clearBtn = button('&#10005;', 'Clear formatting', () => editor.chain().focus().clearNodes().unsetAllMarks().run())
  const undoBtn = button('&#8630;', 'Undo', () => editor.chain().focus().undo().run())
  const redoBtn = button('&#8631;', 'Redo', () => editor.chain().focus().redo().run())

  bar.append(boldBtn, italicBtn, underlineBtn, separator(), ulBtn, olBtn, separator(), linkWrapper, separator(), clearBtn, separator(), undoBtn, redoBtn)

  if (editorEl) {
    bar.append(separator(), buildHtmlSourceButton(editor, editorEl, textarea, bar))
  }

  if (profile === 'email') {
    if (placeholders.length > 0) {
      bar.append(separator(), buildPlaceholderMenu(editor, placeholders))
    }
    if (previewUrl) {
      bar.append(separator(), buildPreviewButton(editor, previewUrl, locale))
    }
  }

  const syncActive = () => {
    bar.querySelectorAll('[data-active-key]').forEach((btn) => {
      const key = btn.dataset.activeKey
      btn.classList.toggle('is-active', editor.isActive(key))
      btn.setAttribute('aria-pressed', String(editor.isActive(key)))
    })
    undoBtn.disabled = !editor.can().undo()
    redoBtn.disabled = !editor.can().redo()
  }

  editor.on('selectionUpdate', syncActive)
  editor.on('transaction', syncActive)

  return bar
}

/**
 * Toggle between visual editing and raw HTML source editing.
 * @param {import('@tiptap/core').Editor} editor
 * @param {HTMLElement} editorEl
 * @param {HTMLTextAreaElement|null} textarea
 * @param {HTMLElement} toolbar
 * @returns {HTMLButtonElement}
 */
function buildHtmlSourceButton(editor, editorEl, textarea, toolbar) {
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'tiptap-btn tiptap-html-btn'
  btn.title = 'HTML'
  btn.setAttribute('aria-label', 'Edit HTML source')
  btn.setAttribute('aria-pressed', 'false')
  btn.innerHTML = '&lt;/&gt;'

  let sourceMode = false
  let sourceView = null

  const setFormattingEnabled = (enabled) => {
    toolbar.querySelectorAll('.tiptap-btn').forEach((other) => {
      if (other === btn) {
        return
      }
      other.disabled = !enabled
    })
  }

  const enterSourceMode = () => {
    sourceView = document.createElement('textarea')
    sourceView.className = 'tiptap-html-source'
    sourceView.value = editor.getHTML()
    sourceView.setAttribute('aria-label', 'HTML source')
    sourceView.spellcheck = false

    sourceView.addEventListener('input', () => {
      if (textarea) {
        textarea.value = sourceView.value
      }
    })

    editorEl.hidden = true
    editorEl.parentNode.insertBefore(sourceView, editorEl.nextSibling)
    sourceMode = true
    btn.classList.add('is-active')
    btn.setAttribute('aria-pressed', 'true')
    btn.title = 'Visual editor'
    btn.setAttribute('aria-label', 'Return to visual editor')
    setFormattingEnabled(false)
    sourceView.focus()
  }

  const exitSourceMode = () => {
    const html = sourceView ? sourceView.value : ''
    editor.commands.setContent(html, { emitUpdate: true })
    // Keep the backing form field in sync even if TipTap normalizes the HTML.
    if (textarea) {
      textarea.value = editor.getHTML()
    }
    if (sourceView) {
      sourceView.remove()
      sourceView = null
    }
    editorEl.hidden = false
    sourceMode = false
    btn.classList.remove('is-active')
    btn.setAttribute('aria-pressed', 'false')
    btn.title = 'HTML'
    btn.setAttribute('aria-label', 'Edit HTML source')
    setFormattingEnabled(true)
    editor.view.focus()
  }

  btn.addEventListener('click', (e) => {
    e.preventDefault()
    if (sourceMode) {
      exitSourceMode()
    } else {
      enterSourceMode()
    }
  })

  return btn
}

function showLinkPopover(editor, anchor) {
  document.querySelectorAll('.tiptap-link-popover').forEach((el) => {
    if (typeof el.closePopover === 'function') {
      el.closePopover()
    } else {
      el.remove()
    }
  })

  const wrapper = document.createElement('span')
  wrapper.className = 'tiptap-link-popover'

  const form = document.createElement('form')
  form.className = 'tiptap-link-form'
  form.noValidate = true

  const input = document.createElement('input')
  input.type = 'url'
  input.className = 'tiptap-link-input'
  input.placeholder = 'https://...'
  input.value = editor.getAttributes('link').href || ''
  input.setAttribute('aria-label', 'Link URL')

  const error = document.createElement('div')
  error.className = 'tiptap-link-error'
  error.hidden = true
  error.textContent = 'Only https:// and http:// URLs are allowed.'

  const actions = document.createElement('div')
  actions.className = 'tiptap-link-actions'

  const applyBtn = document.createElement('button')
  applyBtn.type = 'submit'
  applyBtn.className = 'tiptap-btn'
  applyBtn.textContent = 'Apply'

  const removeBtn = document.createElement('button')
  removeBtn.type = 'button'
  removeBtn.className = 'tiptap-btn'
  removeBtn.textContent = 'Remove'

  const close = () => {
    wrapper.remove()
    document.removeEventListener('click', onDocumentClick)
    document.removeEventListener('keydown', onKeydown)
  }
  wrapper.closePopover = close

  const applyLink = () => {
    const url = input.value.trim()
    error.hidden = true
    if (!url) {
      editor.chain().focus().extendMarkRange('link').unsetLink().run()
      close()
      return
    }
    if (!/^https?:\/\//i.test(url)) {
      error.hidden = false
      input.focus()
      return
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
    close()
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault()
    applyLink()
  })

  removeBtn.addEventListener('click', (e) => {
    e.preventDefault()
    editor.chain().focus().extendMarkRange('link').unsetLink().run()
    close()
  })

  const onDocumentClick = (e) => {
    if (!wrapper.contains(e.target) && !anchor.contains(e.target)) {
      close()
    }
  }

  const onKeydown = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      close()
    }
  }

  actions.append(applyBtn, removeBtn)
  form.append(input, error, actions)
  wrapper.append(form)
  anchor.append(wrapper)
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
  input.focus()
  input.select()
}

function buildPlaceholderMenu(editor, placeholders) {
  const wrapper = document.createElement('span')
  wrapper.className = 'tiptap-placeholder-menu'

  const toggle = document.createElement('button')
  toggle.type = 'button'
  toggle.className = 'tiptap-btn'
  toggle.textContent = '{ } Placeholder'
  toggle.setAttribute('aria-haspopup', 'listbox')
  toggle.setAttribute('aria-expanded', 'false')

  const dropdown = document.createElement('ul')
  dropdown.className = 'tiptap-placeholder-dropdown'
  dropdown.setAttribute('role', 'listbox')
  dropdown.hidden = true

  placeholders.forEach((variable) => {
    const li = document.createElement('li')
    li.className = 'tiptap-placeholder-item'
    li.setAttribute('role', 'option')
    li.tabIndex = 0
    li.textContent = `{${variable}}`
    const insert = () => {
      editor.chain().focus().insertPlaceholder(variable).run()
      dropdown.hidden = true
      toggle.setAttribute('aria-expanded', 'false')
    }
    li.addEventListener('click', insert)
    li.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        insert()
      }
    })
    dropdown.appendChild(li)
  })

  toggle.addEventListener('click', (e) => {
    e.stopPropagation()
    const open = !dropdown.hidden
    document.querySelectorAll('.tiptap-placeholder-dropdown').forEach((d) => {
      if (d !== dropdown) {
        d.hidden = true
        const btn = d.closest('.tiptap-placeholder-menu')?.querySelector('.tiptap-btn[aria-haspopup="listbox"]')
        if (btn) btn.setAttribute('aria-expanded', 'false')
      }
    })
    dropdown.hidden = open
    toggle.setAttribute('aria-expanded', String(!open))
  })

  document.addEventListener('click', () => {
    dropdown.hidden = true
    toggle.setAttribute('aria-expanded', 'false')
  })

  wrapper.append(toggle, dropdown)
  return wrapper
}

function buildPreviewButton(editor, previewUrl, locale = '') {
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'tiptap-btn tiptap-preview-btn'
  btn.textContent = 'Preview'
  btn.setAttribute('aria-label', 'Preview email')

  let isPreviewMode = false
  let previewEl = null

  btn.addEventListener('click', async (e) => {
    e.preventDefault()

    const editorEl = editor.options.element
    const toolbar = btn.closest('.tiptap-toolbar')
    const allButtons = Array.from(toolbar.querySelectorAll('button, select')).filter(b => b !== btn)

    if (isPreviewMode) {
      // Switch to Edit Mode
      isPreviewMode = false
      btn.textContent = 'Preview'
      btn.classList.remove('is-active')
      if (previewEl) {
        previewEl.style.display = 'none'
      }
      editorEl.style.display = ''
      allButtons.forEach(b => b.disabled = false)
      editor.commands.focus()
      return
    }

    const html = editor.getHTML()
    
    // Disable all other buttons in the toolbar while in preview mode
    allButtons.forEach(b => b.disabled = true)
    btn.disabled = true
    btn.textContent = 'Loading...'

    try {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
      const response = await fetch(previewUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ html, locale: locale || undefined }),
      })
      if (!response.ok) throw new Error(`Preview request failed: ${response.status}`)
      const data = await response.json()
      
      if (!previewEl) {
        previewEl = document.createElement('div')
        previewEl.className = 'tiptap-inline-preview tiptap-prosemirror ProseMirror'
        editorEl.parentNode.insertBefore(previewEl, editorEl.nextSibling)
      }
      
      const doc = new DOMParser().parseFromString(data.html, 'text/html')
      previewEl.replaceChildren(...doc.body.childNodes)
      
      isPreviewMode = true
      btn.textContent = 'Edit'
      btn.classList.add('is-active')
      
      editorEl.style.display = 'none'
      previewEl.style.display = 'block'
    } catch (err) {
      console.error('Email preview failed:', err)
      alert('An error occurred while generating the preview. Please try again.')
      allButtons.forEach(b => b.disabled = false)
    } finally {
      btn.disabled = false
      if (!isPreviewMode) {
        btn.textContent = 'Preview'
      }
    }
  })

  return btn
}
