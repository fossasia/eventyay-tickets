<template lang="pug">
.c-emoji-picker
</template>
<script>
import { h, render } from 'preact'
import 'emoji-mart/css/emoji-mart.css'
import data from 'emoji-mart/data/twitter.json'
import { NimblePicker } from 'emoji-mart'

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
			showPreview: true
		})
		render(picker, this.$el)
	},
	methods: {}
}
</script>
<style lang="stylus">
</style>
