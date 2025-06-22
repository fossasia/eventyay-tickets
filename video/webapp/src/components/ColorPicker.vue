<template lang="pug">
.c-color-picker
	.color(:style="{'--color': value}")
	bunt-input(v-bind="$attrs", :value="value", @input="$emit('input', $event)")

	input.color-picker(type="color", :value="value", @change="$emit('input', $event.target.value)")
</template>
<script>
// TODO
// - make picker accept 3 digit hex
export default {
	props: {
		value: String
	}
}
</script>
<style lang="stylus">
.c-color-picker
	position: relative
	.color
		position: absolute
		right: 4px
		top: 20px
		height: 29px
		width: 36px
		background-color: var(--color)
		border-radius: 3px
	.color-picker
		position: absolute
		right: 0
		top: 16px
		opacity: 0
		height: 36px
		width: 36px
</style>
