<template lang="pug">
.c-copyable-text(@click="copy")
	.text {{ text }}
	.mdi.mdi-content-copy
	.copy-success(v-if="copied", v-tooltip="{text: 'Copied!', show: true, placement: 'top', fixed: true}")
</template>
<script>
export default {
	props: {
		text: String
	},
	data () {
		return {
			copied: false
		}
	},
	computed: {},
	async created () {},
	async mounted () {
		await this.$nextTick()
	},
	methods: {
		async copy () {
			await navigator.clipboard.writeText(this.text)
			this.copied = true
			setTimeout(() => {
				this.copied = false
			}, 3000)
		}
	}
}
</script>
<style lang="stylus">
.c-copyable-text
	position: relative
	display: flex
	gap: 8px
	padding: 4px
	background-color: $clr-grey-200
	border-radius: 2px
	cursor: pointer
	.copy-success
		position: absolute
		top: 0
		left: 0
		right: 0
		bottom: 0
		background-color: $clr-secondary-text-dark
</style>
