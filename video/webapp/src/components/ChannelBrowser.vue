<template lang="pug">
prompt.c-channel-browser(@close="$emit('close')", :scrollable="false")
	.content
		h2 {{ $t('ChannelBrowser:headline:text') }}
		p {{ $t('ChannelBrowser:intro:text') }}
			a(href="#", @click="$emit('createChannel')", v-if="hasPermission('world:rooms.create.chat')")  {{ $t('ChannelBrowser:create:label') }}
		bunt-input(icon="search", name="search", :placeholder="$t('ChannelBrowser:search:placeholder')", v-model="search")
		scrollbars.channels(y)
			router-link.channel(v-for="channel of searchedChannels", :to="{name: 'room', params: {roomId: channel.room.id}}", @click.native="$emit('close')")
				.channel-info
					.name {{ channel.room.name }}
					.description {{ channel.room.description }}
				.actions
					template(v-if="channel.channelJoined")
						bunt-button#btn-view {{ $t('ChannelBrowser:view:label') }}
					template(v-else)
						bunt-button#btn-preview {{ $t('ChannelBrowser:preview:label') }}
						bunt-button#btn-join(@click="join(channel)") {{ $t('ChannelBrowser:join:label') }}
			.no-results(v-if="search && searchedChannels.length === 0") {{ $t('ChannelBrowser:search:empty') }}
</template>
<script>
import {mapGetters, mapState} from 'vuex'
import Prompt from 'components/Prompt'
import fuzzysearch from 'lib/fuzzysearch'

export default {
	components: { Prompt },
	data () {
		return {
			search: ''
		}
	},
	computed: {
		...mapState(['rooms']),
		...mapState('chat', ['joinedChannels']),
		...mapGetters(['hasPermission']),
		channels () {
			return this.rooms
				.filter(room => room.modules.length === 1 && room.modules[0].type === 'chat.native')
				.map(room => ({room, channelJoined: this.joinedChannels.some(channel => channel.id === room.modules[0].channel_id)}))
		},
		searchedChannels () {
			if (!this.search) return this.channels
			return this.channels.filter(channel => fuzzysearch(this.search.toLowerCase(), channel.room.name.toLowerCase()) || fuzzysearch(this.search.toLowerCase(), channel.room.description?.toLowerCase()))
		}
	}
}
</script>
<style lang="stylus">
.c-channel-browser
	.prompt-wrapper
		width: 580px
		height: 80vh
	.content
		min-height: 0
		display: flex
		flex-direction: column
	h2
		margin: 16px 16px 8px 16px
	p
		margin: 0 16px 8px 16px
		a
			font-weight: 600
	.bunt-input
		margin: 0 16px
	.channels
		.channel
			padding: 16px
			display: flex
			align-items: center
			&:not(:first-child)
				border-top: border-separator()
			.channel-info
				flex: auto
				color: $clr-primary-text-light
				.name
					font-size: 16px
					font-weight: 500
				.description
					white-space: pre-wrap
			.actions
				flex: none
				#btn-view, #btn-preview
					themed-button-secondary()
				#btn-join
					themed-button-primary()
		.no-results
			margin: 16px
			text-align: center
</style>
