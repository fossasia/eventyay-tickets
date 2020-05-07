<template lang="pug">
.c-rooms-sidebar
	.logo
		span {{ world.title }}
	.global-links
		router-link.room(:to="{name: 'home'}") About
		router-link.room(:to="{name: 'schedule'}") Schedule
	.group-title
		span Stages
		bunt-icon-button(@click="$emit('createRoom')") plus
	.stages
		router-link.stage(v-for="stage of roomsByType.generic", :to="{name: 'room', params: {roomId: stage.id}}")
			.name {{ stage.name }}
	.group-title
		span Channels
		bunt-icon-button(@click="$emit('createChat')") plus
	.chats
		router-link.video-chat(v-for="chat of roomsByType.videoChat", :to="{name: 'room', params: {roomId: chat.id}}")
			.name {{ chat.name }}
		router-link.text-chat(v-for="chat of roomsByType.textChat", :to="{name: 'room', params: {roomId: chat.id}}")
			.name {{ chat.name }}
	.buffer
	.group-title
		span Administration
	.admin
		router-link.room(:to="{name: 'admin'}") Event Config
		router-link.room(:to="{name: 'admin'}") Users
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
				textChat: [],
				videoChat: []
			}
			for (const room of this.rooms) {
				if (room.modules.length === 1 & room.modules[0].type === 'chat.native') {
					rooms.textChat.push(room)
				} else if (room.modules.length === 1 & room.modules[0].type === 'call.bigbluebutton') {
					rooms.videoChat.push(room)
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
		.bunt-icon-button
			margin-left: 4px
			icon-button-style(color: $clr-primary-text-dark, style: clear)
			margin: -4px -4px -4px 0
			.bunt-icon
				font-size: 18px
				height: 24px
				line-height: @height
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
		margin: 16px 8px 0 16px
		height: 28px
		font-weight: 600
		font-size: 12px
		display: flex
		justify-content: space-between
		align-items: center
		.bunt-icon-button
			margin: -4px 0
			icon-button-style(color: $clr-primary-text-dark, style: clear)
	.stages, .chats, .admin
		display: flex
		flex-direction: column
		> *
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
			&.router-link-active::before
				color: $clr-secondary-text-dark
		.stage
			&::before
				font-family: "Material Design Icons"
				font-size: 18px
				line-height: 34px
				color: $clr-disabled-text-dark
				content: '\F050D'
				margin-right: 4px
		.text-chat
			&::before
				font-family: "Material Design Icons"
				font-size: 18px
				line-height: 34px
				color: $clr-disabled-text-dark
				content: '\F0423'
				margin-right: 4px
		.video-chat
			&::before
				font-family: "Material Design Icons"
				font-size: 18px
				line-height: 34px
				color: $clr-disabled-text-dark
				content: '\F05A0'
				margin-right: 4px
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
