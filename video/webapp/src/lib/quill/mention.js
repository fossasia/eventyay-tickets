import Quill from 'quill'

const Embed = Quill.import('blots/embed')

class MentionBlot extends Embed {
	constructor(scroll, node) {
		super(scroll, node)
		this.clickHandler = null
		this.hoverHandler = null
		this.mounted = false
	}

	// Create a new MentionBlot with the provided data
	static create(data) {
		const node = super.create()
		node.innerText = '@' + data.name
		return MentionBlot.setDataValues(node, data)
	}

	// Set data attributes on the DOM element
	static setDataValues(element, data) {
		Object.keys(data).forEach(key => {
			element.dataset[key] = data[key]
		})
		return element
	}

	// Return the dataset of the DOM element
	static value(domNode) {
		return domNode.dataset
	}

	// Attach event listeners for click and hover when the blot is mounted
	attach() {
		super.attach()
		if (!this.mounted) {
			this.mounted = true
			this.clickHandler = this.getClickHandler()
			this.hoverHandler = this.getHoverHandler()
			this.domNode.addEventListener('click', this.clickHandler, false)
			this.domNode.addEventListener('mouseenter', this.hoverHandler, false)
		}
	}

	// Detach event listeners when the blot is unmounted
	detach() {
		super.detach()
		this.mounted = false
		if (this.clickHandler) {
			this.domNode.removeEventListener('click', this.clickHandler)
			this.clickHandler = null
		}
	}

	// Return the click event handler
	getClickHandler() {
		return (e) => {
			const event = this.buildEvent('mention-clicked', e)
			window.dispatchEvent(event)
			e.preventDefault()
		}
	}

	// Return the hover event handler
	getHoverHandler() {
		return (e) => {
			const event = this.buildEvent('mention-hovered', e)
			window.dispatchEvent(event)
			e.preventDefault()
		}
	}

	// Build and return a custom event with the provided name and original event
	buildEvent(name, e) {
		const event = new Event(name, {
			bubbles: true,
			cancelable: true,
		})
		event.value = { ...this.domNode.dataset }
		event.event = e
		return event
	}
}

MentionBlot.blotName = 'mention'
MentionBlot.tagName = 'span'
MentionBlot.className = 'mention'

// Register the MentionBlot with Quill
Quill.register('blots/mention', MentionBlot)
