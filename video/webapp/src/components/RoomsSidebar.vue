<template lang="pug">
.c-rooms-sidebar
	.logo {{ world.title }}
	.group-title Rooms
	.rooms
		router-link.room(v-for="room of rooms", :to="{name: 'room', params: {roomId: room.id}}")
			.name {{ room.name }}
</template>
<script>
import { mapState } from 'vuex'

export default {
	components: {},
	data () {
		return {
		}
	},
	computed: {
		...mapState(['world', 'rooms'])
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
	// box-shadow: 2px 2px 5px 0 rgba(0,0,0,0.16), 2px 12px 10px 0 rgba(0,0,0,0.12)
	// z-index: 100
	.logo
		font-size: 24px
		text-align: center
		margin: 16px 0
	.group-title
		color: $clr-secondary-text-dark
		margin: 32px 16px 8px 16px
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
</style>
