<template lang="pug">
.c-media-source(:class="{'in-background': background, 'in-room-manager': inRoomManager}")
	transition(name="background-room")
		router-link.background-room(v-if="background", :to="room ? {name: 'room', params: {roomId: room.id}}: {name: 'channel', params: {channelId: call.channel}}")
			.description
				.hint {{ $t('MediaSource:room:hint') }}
				.room-name(v-if="room") {{ room.name }}
				.room-name(v-else-if="call") {{ $t('MediaSource:call:label') }}
			.global-placeholder
			bunt-icon-button(@click.prevent.stop="$emit('close')") close
	Livestream(v-if="room && module.type === 'livestream.native'", ref="livestream", :room="room", :module="module", :size="background ? 'tiny' : 'normal'", :key="`livestream-${room.id}`")
	JanusCall(v-else-if="room && module.type === 'call.janus'", ref="janus", :room="room", :module="module", :background="background", :size="background ? 'tiny' : 'normal'", :key="`janus-${room.id}`")
	JanusChannelCall(v-else-if="call", ref="janus", :call="call", :background="background", :size="background ? 'tiny' : 'normal'", :key="`call-${call.id}`", @close="$emit('close')")
	.iframe-error(v-if="iframeError") {{ $t('MediaSource:iframe-error:text') }}
	iframe#video-player-translation(v-if="languageIframeUrl", :src="languageIframeUrl", style="position: absolute; width: 50%; height: 100%; z-index: -1", frameborder="0", gesture="media", allow="autoplay; encrypted-media", allowfullscreen="true")
</template>
<script setup>
// TODO functional component?
import { ref, computed, watch, onMounted, onBeforeUnmount, getCurrentInstance } from 'vue'
import { useRoute } from 'vue-router'
import { useStore } from 'vuex'
import { isEqual } from 'lodash'
import api from 'lib/api'
import JanusCall from 'components/JanusCall'
import JanusChannelCall from 'components/JanusChannelCall'
import Livestream from 'components/Livestream'

// Props & Emits
defineOptions({
	components: { Livestream, JanusCall, JanusChannelCall }
})
const props = defineProps({
	room: Object,
	call: Object,
	background: {
		type: Boolean,
		default: false
	}
})
defineEmits(['close'])

const store = useStore()
const route = useRoute()

const iframeError = ref(null)
const iframeEl = ref(null)
const languageAudioUrl = ref(null)
const languageIframeUrl = ref(null)
const isUnmounted = ref(false)
const eventBusRef = ref(null)

// Template refs
const livestream = ref(null)
const janus = ref(null)

// Mapped state/getters
const streamingRoom = computed(() => store.state.streamingRoom)
const youtubeTransUrl = computed(() => store.state.youtubeTransUrl)
const autoplay = computed(() => store.getters.autoplay)

const module = computed(() => {
	if (!props.room) return null
	return props.room.modules.find(m => ['livestream.native', 'livestream.youtube', 'livestream.iframe', 'call.bigbluebutton', 'call.janus', 'call.zoom'].includes(m.type))
})

const inRoomManager = computed(() => route.name === 'room:manage')

watch(() => props.background, (value) => {
	if (!iframeEl.value) return
	if (value) iframeEl.value.classList.add('background')
	else iframeEl.value.classList.remove('background')
})

watch(module, (value, oldValue) => {
	if (isEqual(value, oldValue)) return
	destroyIframe()
	initializeIframe(false)
})

watch(youtubeTransUrl, (ytUrl) => {
	if (!props.room) return
	// Only react for YouTube livestream modules
	if (module.value?.type !== 'livestream.youtube') return
	// Rebuild iframe with the new translation video id without mutating module config
	destroyIframe()
	initializeIframe(false)
})

onMounted(async () => {
	if (!props.room) return
	await initializeIframe(false)
	const instance = getCurrentInstance && getCurrentInstance()
	const eventBus = instance?.appContext?.config?.globalProperties?.$eventBus || instance?.proxy?.$root?.$eventBus
	if (eventBus) {
		eventBus.on('languageChanged', handleLanguageChange)
		eventBusRef.value = eventBus
	}
})

onBeforeUnmount(() => {
	isUnmounted.value = true
	iframeEl.value?.remove()
	if (api.socketState !== 'open') return
	// TODO move to store?
	if (props.room) api.call('room.leave', { room: props.room.id })
	// Clean up event listener
	if (eventBusRef.value) {
		eventBusRef.value.off('languageChanged', handleLanguageChange)
	}
})

async function initializeIframe(mute) {
	try {
		if (!module.value) return
		let iframeUrl
		let hideIfBackground = false
		switch (module.value.type) {
			case 'call.bigbluebutton': {
				({ url: iframeUrl } = await api.call('bbb.room_url', { room: props.room.id }))
				hideIfBackground = true
				break
			}
			case 'call.zoom': {
				({ url: iframeUrl } = await api.call('zoom.room_url', { room: props.room.id }))
				hideIfBackground = true
				break
			}
			case 'livestream.iframe': {
				iframeUrl = module.value.config.url
				break
			}
					case 'livestream.youtube': {
						const ytid = youtubeTransUrl.value || module.value.config.ytid
						iframeUrl = getYoutubeUrl(
							ytid,
							autoplay.value,
							mute,
							module.value.config.hideControls,
							module.value.config.noRelated,
							module.value.config.showinfo,
							module.value.config.disableKb,
							module.value.config.loop,
							module.value.config.modestBranding,
							module.value.config.enablePrivacyEnhancedMode
						)
						break
					}
		}
		if (!iframeUrl || isUnmounted.value) return
		const iframe = document.createElement('iframe')
		iframe.src = iframeUrl
		iframe.classList.add('iframe-media-source')
		if (hideIfBackground) {
			iframe.classList.add('hide-if-background')
		}
		iframe.allow = 'screen-wake-lock *; camera *; microphone *; fullscreen *; display-capture *' + (autoplay.value ? '; autoplay *' : '')
		iframe.allowFullscreen = true
		iframe.setAttribute('allowusermedia', 'true')
		iframe.setAttribute('allowfullscreen', '') // iframe.allowfullscreen is not enough in firefox#media-source-iframes
		const container = document.querySelector('#media-source-iframes')
		if (!container) return
		container.appendChild(iframe)
		iframeEl.value = iframe
	} catch (error) {
		// TODO handle bbb/zoom.join.missing_profile
		iframeError.value = error
		console.error(error)
	}
}

function destroyIframe() {
	iframeEl.value?.remove()
	iframeEl.value = null
}

function isPlaying() {
	if (props.call) {
		return janus.value?.roomId
	}
	if (module.value?.type === 'livestream.native') {
		return livestream.value?.playing && !livestream.value?.offline
	}
	if (module.value?.type === 'call.janus') {
		return janus.value?.roomId
	}
	if (module.value?.type === 'call.bigbluebutton') {
		return !!iframeEl.value
	}
	if (module.value?.type === 'call.zoom') {
		return !!iframeEl.value
	}
	return true
}

function handleLanguageChange(languageUrl) {
	languageAudioUrl.value = languageUrl // Set the audio source to the selected language URL
	const mute = !!languageUrl // Mute if language URL is present, otherwise unmute
	destroyIframe()
	initializeIframe(mute) // Initialize iframe with the appropriate mute state
	// Set the language iframe URL when language changes
	languageIframeUrl.value = getLanguageIframeUrl(languageUrl)
}

function getYoutubeUrl(ytid, autoplayVal, mute, hideControls, noRelated, showinfo, disableKb, loop, modestBranding, enablePrivacyEnhancedMode) {
	const params = new URLSearchParams({
		autoplay: autoplayVal ? '1' : '0',
		mute: mute ? '1' : '0',
		controls: hideControls ? '0' : '1',
		rel: noRelated ? '0' : '1',
		showinfo: showinfo ? '0' : '1',
		disablekb: disableKb ? '1' : '0',
		loop: loop ? '1' : '0',
		modestbranding: modestBranding ? '1' : '0',
		playlist: ytid,
	})

	const domain = enablePrivacyEnhancedMode ? 'www.youtube-nocookie.com' : 'www.youtube.com'
	return `https://${domain}/embed/${ytid}?${params}`
}

// Added method to get the language iframe URL
function getLanguageIframeUrl(languageUrl) {
	// Checks if the languageUrl is not provided the retun null
	if (!languageUrl) return null
	const config = module.value?.config || {}
	const params = new URLSearchParams({
		enablejsapi: '1',
		autoplay: '1',
		modestbranding: '1',
		loop: '1',
		controls: '0',
		disablekb: '1',
		rel: '0',
		showinfo: '0',
		playlist: languageUrl,
	})

	const domain = config.enablePrivacyEnhancedMode ? 'www.youtube-nocookie.com' : 'www.youtube.com'
	return `https://${domain}/embed/${languageUrl}?${params}`
}

// Expose instance methods (used by parents via template refs)
defineExpose({ isPlaying })
</script>
<style lang="stylus">
.c-media-source
	position: absolute
	width: 0
	height: 0
	&.in-background
		z-index: 101
	.background-room
		position: fixed
		top: 3px
		right: 4px
		card()
		display: flex
		align-items: center
		height: 48px
		min-width: 280px
		max-width: 380px
		.description
			flex: auto
			align-self: stretch
			padding: 4px 8px
			max-width: 238px
			.hint
				color: $clr-secondary-text-light
				font-size: 10px
				margin-bottom: 2px
			.room-name
				color: var(--clr-text-primary)
				font-weight: 500
				flex-grow: 0
				ellipsis()
		.global-placeholder
			width: 86px
			flex: none
		.bunt-icon-button
			icon-button-style(style: clear)
			margin: 0 2px
		+below('l')
			top: 51px
	.background-room-enter-active, .background-room-leave-active
		transition: transform .3s ease
	// .background-room-enter-active
	// 	transition-delay: .1s
	.background-room-enter-from, .background-room-leave-to
		transform: translate(calc(-1 * var(--chatbar-width)), 52px)
.c-media-source .c-livestream, .c-media-source .c-januscall, .c-media-source .c-januschannelcall, iframe.iframe-media-source
	position: fixed
	transition: all .3s ease
	&.size-tiny, &.background
		bottom: calc(var(--vh100) - 48px - 3px)
		right: 4px + 36px + 4px
		+below('l')
			bottom: calc(var(--vh100) - 48px - 48px - 3px)
	&:not(.size-tiny):not(.background)
		bottom: calc(var(--vh100) - 56px - var(--mediasource-placeholder-height))
		right: calc(100vw - var(--sidebar-width) - var(--mediasource-placeholder-width))
		width: var(--mediasource-placeholder-width)
		height: var(--mediasource-placeholder-height)
		+below('l')
			bottom: calc(var(--vh100) - 48px - 56px - var(--mediasource-placeholder-height))
			right: calc(100vw - var(--mediasource-placeholder-width))
iframe.iframe-media-source
	transition: all .3s ease
	border: none
	&.background
		pointer-events: none
		height: 48px
		width: 86px
		z-index: 101
		&.hide-if-background
			width: 0
			height: 0
</style>
