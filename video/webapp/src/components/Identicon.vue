<template lang="pug">
.c-identicon
	canvas(ref="canvas", height="500", width="500")
</template>
<script>
import IdentiHeart from 'lib/identiheart'

export default {
	props: {
		id: String
	},
	watch: {
		id: 'update'
	},
	mounted () {
		this.update()
	},
	methods: {
		update () {
			const canvas = this.$refs.canvas
			const ctx = canvas.getContext('2d')

			const h = new IdentiHeart(canvas, ctx)
			h.setUsername(this.id)
			h.init()
			h.draw()
		}
	}
}
</script>
<style lang="stylus">
.c-identicon
	user-select: none
</style>
