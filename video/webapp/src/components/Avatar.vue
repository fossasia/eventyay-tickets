<template lang="pug">
.c-avatar(:style="{'--avatar-size': size + 'px'}", :class="{deleted: user.deleted}")
	img(v-if="imageUrl", :src="imageUrl")
	identicon(v-else, :user="user")
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
		}
	}
}
</script>
<style lang="stylus">
.c-avatar
	display: flex
	&.deleted
		opacity: 0.2
	img, .c-identicon
		width: var(--avatar-size)
		height: var(--avatar-size)
	img
		border-radius: 50%
</style>
