<template lang="pug">
.c-color-picker
	.color(:style="{'--color': modelValue}")
	bunt-input(v-bind="$attrs", :modelValue="modelValue", @update:modelValue="$emit('update:modelValue', $event)")
	input.color-picker(type="color", :value="modelValue", @change="$emit('update:modelValue', $event.target.value)")
</template>
<script>
export default {
	props: {
		modelValue: String
	},
	emits: ['update:modelValue']
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
