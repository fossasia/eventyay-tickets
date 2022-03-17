import Vue from 'vue'
import Quill from 'quill'
import IframeBlocker from 'components/IframeBlocker'

const BlockEmbed = Quill.import('blots/block/embed')
const Link = Quill.import('formats/link')

export default class VideoResponsive extends BlockEmbed {
	/*
		With inspiration taken from https://github.com/pblobp/quill-video-responsive
		Copyright (c) 2019 pblobp, MIT License
	*/

	static blotName = 'video'
	static tagName = 'div'
	static className = 'ql-video-wrapper'

	static create (value) {
		const node = super.create(value)
		const src = this.sanitize(value)
		const innerNode = document.createElement('div')
		innerNode.classList.add('ql-video-inner')
		innerNode.contentEditable = false
		innerNode.dataset.src = src
		node.appendChild(innerNode)
		const blocker = document.createElement('div')
		innerNode.appendChild(blocker)
		new Vue({
			render: h => h(IframeBlocker, {
				props: {
					src,
					frameborder: '0',
					allowfullscreen: true
				}
			})
		}).$mount(blocker)
		return node
	}

	static sanitize (url) {
		return Link.sanitize(url)
	}

	static value (domNode) {
		const iframe = domNode.querySelector('.ql-video-inner')
		return iframe ? iframe.dataset.src : ''
	}
}
