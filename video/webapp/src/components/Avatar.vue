<template lang="pug">
.c-avatar(:style="{'--avatar-size': size + 'px'}")
	img.gravatar-avatar(v-if="gravatarAvatarUrl", :src="gravatarAvatarUrl")
	identicon(v-else, :id="identicon")
</template>
<script>
import Identicon from 'components/Identicon'
import { getAvatarUrl } from 'lib/gravatar'

export default {
	components: { Identicon },
	props: {
		user: Object,
		size: Number
	},
	computed: {
		gravatarAvatarUrl () {
			if (!this.user.profile?.gravatar_hash) return
			return getAvatarUrl(this.user.profile.gravatar_hash, this.size)
		},
		identicon () {
			return this.user.profile?.identicon ?? this.user.id
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
	.gravatar-avatar, .c-identicon
		width: var(--avatar-size)
		height: var(--avatar-size)
	.gravatar-avatar
		border-radius: 50%
</style>
