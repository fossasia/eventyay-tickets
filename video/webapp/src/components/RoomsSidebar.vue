<template lang="pug">
.c-rooms-sidebar
	.logo {{ world.title }}
	.global-links
		router-link.room(:to="{name: 'home'}") About
		router-link.room(:to="{name: 'schedule'}") Schedule
	.group-title Rooms
	.rooms
		router-link.room(v-for="room of roomsByType.generic", :to="{name: 'room', params: {roomId: room.id}}")
			.name {{ room.name }}
	.group-title Channels
	.rooms
		router-link.room(v-for="room of roomsByType.chat", :to="{name: 'room', params: {roomId: room.id}}")
			.name {{ room.name }}
	.buffer
	.profile(@click="$emit('editProfile')")
		avatar(:user="user", :size="36")
		.display-name {{ user.profile.display_name }}
</template>
<script>
import { mapState } from 'vuex'
import Avatar from 'components/Avatar'

export default {
	components: { Avatar },
	data () {
		return {
		}
	},
	computed: {
		...mapState(['user', 'world', 'rooms']),
		roomsByType () {
			const rooms = {
				generic: [],
				chat: []
			}
			for (const room of this.rooms) {
				if (room.modules.length === 1 & room.modules[0].type === 'chat.native') {
					rooms.chat.push(room)
				} else {
					rooms.generic.push(room)
				}
			}
			return rooms
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
.c-rooms-sidebar
	background-color: #180044
	color: $clr-primary-text-dark
	display: flex
	flex-direction: column
	.logo
		font-size: 18px
		text-align: center
		margin: 16px 0 32px 0
	.global-links
		display: flex
		flex-direction: column
		> *
			flex: none
			height: 36px
			line-height: 36px
			padding: 0 24px
			color: $clr-secondary-text-dark
			&:hover
				background-color: rgba(255, 255, 255, .3)
				color: $clr-primary-text-dark
			&.router-link-exact-active
				background-color: rgba(255, 255, 255, .4)
				color: $clr-primary-text-dark
	.group-title
		color: $clr-secondary-text-dark
		margin: 16px 16px 8px 16px
		font-weight: 600
		font-size: 12px
	.rooms
		display: flex
		flex-direction: column
		.room
			flex: none
			height: 36px
			line-height: 36px
			padding: 0 24px
			color: $clr-secondary-text-dark
			display: flex
			&:hover
				background-color: rgba(255, 255, 255, .3)
				color: $clr-primary-text-dark
			&.router-link-active
				background-color: rgba(255, 255, 255, .4)
				color: $clr-primary-text-dark
			&::before
				font-family: "Material Design Icons"
				font-size: 18px
				line-height: 34px
				color: $clr-disabled-text-dark
				content: '\F0423'
				margin-right: 4px
			&.router-link-active::before
				color: $clr-secondary-text-dark
	.buffer
		flex: auto
	.profile
		display: flex
		padding: 8px
		align-items: center
		cursor: pointer
		&:hover
			background-color: rgba(255, 255, 255, 0.3)
		.c-avatar
			background-color: $clr-white
			border-radius: 50%
			padding: 4px
		.display-name
			font-weight: 600
			font-size: 18px
			margin-left: 8px
</style>
