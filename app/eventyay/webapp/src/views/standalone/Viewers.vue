<template lang="pug">
.c-standalone-viewers(v-if="roomViewers")
	h1 {{ $t('standalone/Viewers:header', {count: roomViewers.length}) }}
	.viewers(:class="{many: roomViewers.length > 92}")
		.viewer(v-for="viewer in roomViewers")
			avatar(:user="viewer", :size="64")
</template>
<script>
import { mapState } from 'vuex'
import Avatar from 'components/Avatar'

export default {
	components: { Avatar },
	props: {
		room: Object
	},
	computed: {
		...mapState(['roomViewers']),
	},
}
</script>
<style lang="stylus">
.c-standalone-viewers
	h1
		text-align: center
	.viewers
		display: flex
		flex-wrap: wrap
		gap: 8px
		align-items: center
		justify-content: center
		max-height: 560px
		.viewer
			background-color: $clr-white
			border-radius: 50%
			padding: 2px
		&.many .viewer
			margin: -8px -16px
</style>
