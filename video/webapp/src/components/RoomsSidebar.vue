<template lang="pug">
transition(name="sidebar")
	.c-rooms-sidebar(v-show="show && !snapBack", :style="style", @pointerdown="onPointerdown", @pointermove="onPointermove", @pointerup="onPointerup", @pointercancel="onPointercancel")
		//- TODO clickable logo
		.logo(v-if="$mq.above['m']", :class="{'fit-to-width': theme.logo.fitToWidth}")
			img(:src="theme.logo.url", :alt="world.title")
		bunt-icon-button#btn-close-sidebar(v-else, @click="$emit('close')") menu
		scrollbars(y)
			.global-links
				router-link.room(v-if="roomsByType.page.includes(rooms[0])", :to="{name: 'home'}") {{ rooms[0].name }}
				router-link.room(:to="{name: 'schedule'}", v-if="!!world.pretalx.base_url") {{ $t('RoomsSidebar:schedule:label') }}
				router-link.room(v-for="page of roomsByType.page", v-if="page !== rooms[0]", :to="{name: 'room', params: {roomId: page.id}}") {{ page.name }}
			.group-title(v-if="roomsByType.stage.length || hasPermission('world:rooms.create.stage')")
				span {{ $t('RoomsSidebar:stages-headline:text') }}
				bunt-icon-button(v-if="hasPermission('world:rooms.create.stage')", @click="$emit('createRoom')") plus
			.stages
				router-link.stage(v-for="stage of roomsByType.stage", :to="stage === rooms[0] ? {name: 'home'} : {name: 'room', params: {roomId: stage.id}}")
					.name {{ stage.name }}
			.group-title(v-if="roomsByType.videoChat.length || roomsByType.textChat.length || hasPermission('world:rooms.create.chat') || hasPermission('world:rooms.create.bbb')")
				span {{ $t('RoomsSidebar:channels-headline:text') }}
				bunt-icon-button(v-if="hasPermission('world:rooms.create.chat') || hasPermission('world:rooms.create.bbb')", @click="$emit('createChat')") plus
			.chats
				router-link.video-chat(v-for="chat of roomsByType.videoChat", :to="chat === rooms[0] ? {name: 'home'} : {name: 'room', params: {roomId: chat.id}}")
					.name {{ chat.name }}
				router-link.text-chat(v-for="chat of roomsByType.textChat", :to="chat === rooms[0] ? {name: 'home'} : {name: 'room', params: {roomId: chat.id}}", :class="{unread: hasUnreadMessages(chat.modules[0].channel_id)}")
					.name {{ chat.name }}
			.group-title
				span {{ $t('RoomsSidebar:direct-messages-headline:text') }}
				bunt-icon-button(@click="$emit('createDM')") plus
			.direct-messages
				router-link.direct-message(v-for="channel of directMessageChannels", :to="{name: 'channel', params: {channelId: channel.id}}") {{ channel.user.profile.display_name }}
			template(v-if="hasPermission('world:users.list') || hasPermission('world:update') || hasPermission('room:update')")
				.buffer
				.group-title
					span {{ $t('RoomsSidebar:admin-headline:text') }}
				.admin
					router-link.room(:to="{name: 'admin:users'}", v-if="hasPermission('world:users.list')") {{ $t('RoomsSidebar:admin-users:label') }}
					router-link.room(:to="{name: 'admin:rooms'}", v-if="hasPermission('room:update')") {{ $t('RoomsSidebar:admin-rooms:label') }}
					router-link.room(:to="{name: 'admin:config'}", v-if="hasPermission('world:update')") {{ $t('RoomsSidebar:admin-config:label') }}
		.profile(@click="$emit('editProfile')")
			avatar(:user="user", :size="36")
			.display-name {{ user.profile.display_name }}
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import theme from 'theme'
import Avatar from 'components/Avatar'

export default {
	props: {
		show: Boolean
	},
	components: { Avatar },
	data () {
		return {
			theme,
			lastPointer: null,
			pointerMovementX: 0,
			snapBack: false
		}
	},
	computed: {
		...mapState(['user', 'world', 'rooms']),
		...mapState('chat', ['joinedChannels']),
		...mapGetters('chat', ['hasUnreadMessages']),
		...mapGetters(['hasPermission']),
		style () {
			if (this.pointerMovementX === 0) return
			return {
				transform: `translateX(${this.pointerMovementX}px)`
			}
		},
		roomsByType () {
			const rooms = {
				page: [],
				stage: [],
				textChat: [],
				videoChat: []
			}
			for (const room of this.rooms) {
				if (room.modules.length === 1 & room.modules[0].type === 'chat.native') {
					rooms.textChat.push(room)
				} else if (room.modules.length === 1 & room.modules[0].type === 'call.bigbluebutton') {
					rooms.videoChat.push(room)
				} else if (room.modules.some(module => module.type === 'livestream.native')) {
					rooms.stage.push(room)
				} else {
					rooms.page.push(room)
				}
			}
			return rooms
		},
		directMessageChannels () {
			return this.joinedChannels?.filter(channel => channel.members).map(channel => ({id: channel.id, user: channel.members.find(member => member.id !== this.user.id)}))
		}
	},
	methods: {
		onPointerdown (event) {
			if (this.$mq.above.m) return
			this.lastPointer = event.pointerId
		},
		onPointermove (event) {
			if (this.$mq.above.m || this.lastPointer !== event.pointerId) return
			this.pointerMovementX += event.movementX / window.devicePixelRatio // because apparently the browser does not do this
			if (this.pointerMovementX > 0) {
				this.pointerMovementX = 0
			}
		},
		async onPointerup (event) {
			if (this.$mq.above.m || this.lastPointer !== event.pointerId) return
			this.lastPointer = null
			if (this.pointerMovementX < -80) {
				this.$emit('close')
			}
			this.pointerMovementX = 0
			// TODO not the cleanest, control transition completely ourselves
			this.snapBack = true
			await this.$nextTick()
			this.snapBack = false
		},
		onPointercancel (event) {
			this.lastPointer = null
			this.pointerMovementX = 0
		}
	}
}
</script>
<style lang="stylus">
.c-rooms-sidebar
	background-color: var(--clr-sidebar)
	color: var(--clr-sidebar-text-primary)
	display: flex
	flex-direction: column
	min-height: 0
	max-height: var(--vh100)
	.logo
		font-size: 18px
		text-align: center
		margin: 0 16px
		height: 56px
		img
			height: 100%
			max-width: 100%
			object-fit: contain
		&.fit-to-width
			height: auto
	#btn-close-sidebar
		margin: 8px
		icon-button-style(color: var(--clr-sidebar-text-primary), style: clear)
	> .c-scrollbars
		flex: auto
		.scroll-content
			flex: auto
		.scrollbar-rail-y
			.scrollbar-thumb
				background-color: var(--clr-sidebar-text-secondary)
	.global-links
		display: flex
		flex-direction: column
		> *
			flex: none
			height: 36px
			line-height: 36px
			padding: 0 24px
			color: var(--clr-sidebar-text-secondary)
			&:hover
				background-color: rgba(255, 255, 255, .3)
				color: var(--clr-sidebar-text-primary)
			&.router-link-exact-active
				background-color: rgba(255, 255, 255, .4)
				color: var(--clr-sidebar-text-primary)
	.group-title
		flex: none
		color: var(--clr-sidebar-text-secondary)
		margin: 16px 8px 0 16px
		height: 28px
		font-weight: 600
		font-size: 12px
		display: flex
		justify-content: space-between
		align-items: center
		.bunt-icon-button
			margin: -4px 0
			icon-button-style(color: var(--clr-sidebar-text-primary), style: clear)
	.stages, .chats, .direct-messages, .admin
		display: flex
		flex-direction: column
		> *
			flex: none
			height: 36px
			line-height: 36px
			padding: 0 24px
			color: var(--clr-sidebar-text-secondary)
			display: flex
			position: relative
			&:hover
				background-color: rgba(255, 255, 255, .3)
				color: var(--clr-sidebar-text-primary)
			&.router-link-exact-active
				background-color: rgba(255, 255, 255, .4)
				color: var(--clr-sidebar-text-primary)
			&.router-link-active::before
				color: var(--clr-sidebar-text-secondary)
			&::before
				font-family: "Material Design Icons"
				font-size: 18px
				line-height: 34px
				color: var(--clr-sidebar-text-disabled)
				margin-right: 4px
			&.unread
				color: var(--clr-sidebar-text-primary)
				font-weight: 500
				&::after
					content: ''
					position: absolute
					background-color: var(--clr-sidebar-text-primary)
					left: 10px
					top: 15px
					height: 6px
					width: @height
					border-radius: 50%
			.name
				ellipsis()
		.stage
			&::before
				content: '\F050D'
		.text-chat
			&::before
				content: '\F0423'
		.video-chat
			&::before
				content: '\F05A0'
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
	+below('m')
		position: fixed
		left: 0
		top: 0
		z-index: 1000
		width: var(--sidebar-width)
		height: var(--vh100)
		touch-action: pan-y
		> .c-scrollbars .scroll-content
			touch-action: pan-y
		&.sidebar-enter-active, &.sidebar-leave-active
			transition: transform .2s
		&.sidebar-enter, &.sidebar-leave-to
			transform: translateX(calc(-1 * var(--sidebar-width)))
</style>
