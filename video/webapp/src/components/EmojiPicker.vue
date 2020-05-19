<template lang="pug">
.c-emoji-picker
</template>
<script>
// TODO close when clicking outside of picker
import { h, render } from 'preact'
import 'emoji-mart/css/emoji-mart.css'
import data from 'emoji-mart/data/twitter.json'
import { NimblePicker } from 'emoji-mart'
import emojiSheet from 'emoji-datasource-twitter/img/twitter/sheets-256/64.png'

export default {
	components: {},
	data () {
		return {
		}
	},
	computed: {},
	mounted () {
		const picker = h(NimblePicker, {
			set: 'twitter',
			data,
			onSelect: this.$emit.bind(this, 'selected'),
			title: 'Emoji',
			showPreview: true,
			backgroundImageFn (set, sheetSize) {
				return emojiSheet
			}
		})
		render(picker, this.$el)
	},
	methods: {}
}
</script>
<style lang="stylus">
</style>
