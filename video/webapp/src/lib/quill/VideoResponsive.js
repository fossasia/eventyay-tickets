import Quill from 'quill'

const BlockEmbed = Quill.import('blots/block/embed')
const Link = Quill.import('formats/link')

class VideoResponsive extends BlockEmbed {
	/*
	 With inspiration taken from https://github.com/pblobp/quill-video-responsive
	Copyright (c) 2019 pblobp, MIT License
	 */

	static blotName = 'video'
	static tagName = 'div'
	static className = 'ql-video-wrapper'

	static create (value) {
		const node = super.create(value)

		const innerNode = document.createElement('div')
		innerNode.classList.add('ql-video-inner')
		node.appendChild(innerNode)

		const child = document.createElement('iframe')
		child.setAttribute('frameborder', '0')
		child.setAttribute('allowfullscreen', true)
		child.setAttribute('src', this.sanitize(value))
		innerNode.appendChild(child)

		return node
	}

	static sanitize (url) {
		return Link.sanitize(url)
	}

	static value (domNode) {
		const iframe = domNode.querySelector('iframe')
		return iframe ? iframe.getAttribute('src') : ''
	}
}

export default VideoResponsive
