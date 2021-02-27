<template lang="pug">
.c-admin-rooms-new
	.ui-page-header
		h1 New room
			template(v-if="chosenType") – {{ chosenType.name }}
	.choose-type(v-if="!type")
		h2 Choose a room type
		p Bla bla room types
		.types
			router-link.type(v-for="type of ROOM_TYPES", :to="{name: 'admin:rooms:new', query: {type: type.id}}")
				.icon.mdi(:class="[`mdi-${type.icon}`]")
				.text
					.name {{ type.name }}
					.description {{ type.description }}
	edit-form(v-else, :config="config", @configChange="config = $event", :creating="true")
</template>
<script>
import EditForm from './EditForm'

const ROOM_TYPES = [{
	id: 'stage',
	icon: 'theater',
	name: 'Stage',
	description: 'livestream und so',
	startingModule: 'livestream.native'
}, {
	id: 'channel-text',
	icon: 'pound',
	name: 'Text Channel',
	description: 'livestream und so',
	startingModule: 'chat.native'
}, {
	id: 'channel-video',
	icon: 'webcam',
	name: 'Video Channel',
	description: 'livestream und so',
	startingModule: 'call.bigbluebutton'
}, {
	id: 'exhibition',
	icon: 'domain',
	name: 'Exhibition',
	description: 'Shilling Stands',
	startingModule: 'exhibition.native'
}, {
	id: 'page.static',
	icon: 'text-box-outline',
	name: 'Page',
	description: 'static stuff',
	startingModule: 'page.static'
}, {
	id: 'page.iframe',
	icon: 'text-box-outline',
	name: 'IFrame',
	description: 'arbitrary interwebs',
	startingModule: 'page.iframe'
}]

// TODO
// page.landing
//
// generic room

export default {
	components: { EditForm },
	data () {
		return {
			ROOM_TYPES,
			type: null,
			config: null
		}
	},
	computed: {
		chosenType () {
			return ROOM_TYPES.find(t => t.id === this.type)
		}
	},
	created () {
		this.type = this.$route.query.type
		if (!this.type || !this.chosenType) return
		this.config = {
			name: '',
			description: '',
			sorting_priority: '',
			pretalx_id: '',
			force_join: false,
			module_config: [{type: this.chosenType.startingModule, config: {}}],
		}
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-admin-rooms-new
	background-color: $clr-white
	display: flex
	flex-direction: column
	min-height: 0
	h1
		font-size: 28px
	.choose-type
		display: flex
		flex-direction: column
		padding: 16px
	.types
		display: flex
		flex-direction: column
		border: border-separator()
		border-radius: 4px
		max-width: 480px
		.type
			display: flex
			height: 52px
			flex: none
			cursor: pointer
			padding: 0 16px 0 8px
			box-sizing: border-box
			font-size: 16px
			align-items: center
			color: $clr-primary-text-light
			&:not(:last-child)
				border-bottom: border-separator()
			&:hover
				background-color: $clr-grey-50
			.icon
				font-size: 30px
				line-height: 52px
				margin: 0 8px 0 0
			.text
				display: flex
				flex-direction: column
			.name
				line-height: 24px
			.description
				color: $clr-secondary-text-light
				font-size: 13px
</style>
