<template lang="pug">
.c-avatar(:style="{'--avatar-size': size + 'px'}")
	img(v-if="imageUrl", :src="imageUrl")
	identicon(v-else, :id="identicon")
</template>
<script>
import Identicon from 'components/Identicon'

export default {
	components: { Identicon },
	props: {
		user: Object,
		size: Number
	},
	computed: {
		imageUrl () {
			return this.user.profile?.avatar?.url
		},
		identicon () {
			return this.user.profile?.avatar?.identicon ?? this.user.id
		}
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-avatar
	display: flex
	img, .c-identicon
		width: var(--avatar-size)
		height: var(--avatar-size)
	img
		border-radius: 50%
</style>
