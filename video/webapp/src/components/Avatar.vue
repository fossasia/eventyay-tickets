<template lang="pug">
.c-avatar(:style="{'--avatar-size': size + 'px'}")
	img(v-if="imageUrl", :src="imageUrl")
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
		imageUrl () {
			return this.user.profile?.avatar?.url ?? this.gravatarAvatarUrl
		},
		identicon () {
			return this.user.profile?.avatar?.identicon ?? this.user.profile?.identicon ?? this.user.id
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
