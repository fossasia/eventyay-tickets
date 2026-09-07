<template lang="pug">
.c-mainconfig
	.ui-page-header
		bunt-icon-button(@click="$router.push({name: 'organizer'})", :tooltip="$t('Back to Overview')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h1 {{ $t('Settings') }}
	scrollbars(y)
		bunt-progress-circular(size="huge", v-if="!loaded && !error")
		.error(v-if="error") {{ $t('We could not fetch the current configuration.') }}
		.ui-form-body(v-if="loaded")
			.config-tabs(role="tablist")
				button.tab-btn(type="button", role="tab", v-if="hasGeneral", :class="{active: activeTab === 'general'}", @click="activeTab = 'general'") {{ $t('General & Live Features') }}
				button.tab-btn(type="button", role="tab", v-if="hasBBB", :class="{active: activeTab === 'bbb'}", @click="activeTab = 'bbb'") {{ $t('BigBlueButton') }}
				button.tab-btn(type="button", role="tab", v-if="hasZoom", :class="{active: activeTab === 'zoom'}", @click="activeTab = 'zoom'") {{ $t('Zoom') }}
				button.tab-btn(type="button", role="tab", v-if="hasJitsi", :class="{active: activeTab === 'jitsi'}", @click="activeTab = 'jitsi'") {{ $t('Jitsi Meet') }}
				button.tab-btn(type="button", role="tab", v-if="hasJanus", :class="{active: activeTab === 'janus'}", @click="activeTab = 'janus'") {{ $t('Janus WebRTC') }}
				button.tab-btn(type="button", role="tab", v-if="hasStage", :class="{active: activeTab === 'stages'}", @click="activeTab = 'stages'") {{ $t('Stages & Streams') }}
			.tab-content(v-if="hasGeneral", v-show="activeTab === 'general'")
				h2 {{ $t('Live platform features') }}
				bunt-checkbox(v-model="config.live_features.chat_rooms", :label="$t('Enable Chat Rooms')", name="enable_chat_rooms")
				bunt-checkbox(v-model="config.live_features.kiosks", :label="$t('Enable Kiosks')", name="enable_kiosks")
				bunt-checkbox(v-model="config.live_features.direct_messaging", :label="$t('Enable Direct messaging')", name="enable_direct_messaging")
				bunt-checkbox(v-model="config.live_features.announcements", :label="$t('Allow Announcements')", name="allow_announcements")
				h2 {{ $t('Tracking and statistics') }}
				bunt-checkbox(v-model="config.track_room_views", :label="$t('Track room views')", name="track_room_views")
				bunt-checkbox(v-model="config.track_video_event_views", :label="$t('Track video event views')", name="track_video_event_views")
				h2 {{ $t('System details') }}
				bunt-input(v-model="config.connection_limit", :label="$t('Max connections')", name="connection_limit", :hint="$t('Set to 0 to allow unlimited connections per user')", :validation="v$.config.connection_limit")
			.tab-content(v-if="hasBBB", v-show="activeTab === 'bbb'")
				h2 {{ $t('Settings for newly-created BBB rooms') }}
				bunt-checkbox(v-model="config.bbb_defaults.record", :label="$t('Allow recording')", name="record")
				bunt-checkbox(v-model="config.bbb_defaults.hide_presentation", :label="$t('Hide presentation when users join')", name="hide_presentation")
				bunt-checkbox(v-model="config.bbb_defaults.waiting_room", :label="$t('Put new users in waiting room first (needs to be set before first join)')", name="waiting_room")
				bunt-checkbox(v-model="config.bbb_defaults.auto_microphone", :label="$t('Auto-join users with microphone on (skip dialog asking how to join)')", name="auto_microphone")
				bunt-checkbox(v-model="config.bbb_defaults.auto_camera", :label="$t('Auto-join users with camera on')", name="auto_camera")
				bunt-checkbox(v-model="config.bbb_defaults.bbb_mute_on_start", :label="$t('Auto-mute users')", name="bbb_mute_on_start")
				bunt-checkbox(v-model="config.bbb_defaults.bbb_disable_cam", :label="$t('Disable camera for non-moderators')", name="bbb_disable_cam")
				bunt-checkbox(v-model="config.bbb_defaults.bbb_disable_chat", :label="$t('Disable public chat for non-moderators')", name="bbb_disable_chat")
			.tab-content(v-if="hasZoom", v-show="activeTab === 'zoom'")
				h2 {{ $t('Settings for newly-created Zoom rooms') }}
				bunt-checkbox(v-model="config.zoom_defaults.disable_chat", :label="$t('Disable Zoom in-meeting chat')", name="zoom_disable_chat")
				bunt-checkbox(v-model="config.zoom_defaults.enable_platform_chat", :label="$t('Enable platform chat sidebar by default')", name="zoom_enable_platform_chat")
				bunt-checkbox(v-model="config.zoom_defaults.enable_platform_qa", :label="$t('Enable platform Q&A by default')", name="zoom_enable_platform_qa")
				bunt-checkbox(v-model="config.zoom_defaults.enable_platform_polls", :label="$t('Enable platform polls by default')", name="zoom_enable_platform_polls")
			.tab-content(v-if="hasJitsi", v-show="activeTab === 'jitsi'")
				h2 {{ $t('Settings for newly-created Jitsi Meet rooms') }}
				bunt-checkbox(v-model="config.jitsi_defaults.waiting_room", :label="$t('Put new users in waiting room first (needs to be set before first join)')", name="jitsi_waiting_room")
				bunt-checkbox(v-model="config.jitsi_defaults.start_with_audio_muted", :label="$t('Auto-mute users on join')", name="jitsi_start_with_audio_muted")
				bunt-checkbox(v-model="config.jitsi_defaults.start_with_video_muted", :label="$t('Auto-disable camera on join')", name="jitsi_start_with_video_muted")
				bunt-checkbox(v-model="config.jitsi_defaults.record", :label="$t('Allow recording')", name="jitsi_record")
				bunt-checkbox(v-model="config.jitsi_defaults.livestreaming", :label="$t('Allow livestreaming')", name="jitsi_livestreaming")
				bunt-checkbox(v-model="config.jitsi_defaults.disable_cam", :label="$t('Disable camera for non-moderators')", name="jitsi_disable_cam")
				bunt-checkbox(v-model="config.jitsi_defaults.disable_chat", :label="$t('Disable public chat for non-moderators')", name="jitsi_disable_chat")
				bunt-checkbox(v-model="config.jitsi_defaults.require_display_name", :label="$t('Require display name to join')", name="jitsi_require_display_name")
			.tab-content(v-if="hasJanus", v-show="activeTab === 'janus'")
				h2 {{ $t('Settings for newly-created Janus WebRTC rooms') }}
				bunt-checkbox(v-model="config.janus_defaults.waiting_room", :label="$t('Put new users in waiting room first')", name="janus_waiting_room")
				bunt-checkbox(v-model="config.janus_defaults.start_with_audio_muted", :label="$t('Auto-mute users on join')", name="janus_start_with_audio_muted")
				bunt-checkbox(v-model="config.janus_defaults.start_with_video_muted", :label="$t('Auto-disable camera on join')", name="janus_start_with_video_muted")
				bunt-checkbox(v-model="config.janus_defaults.disable_cam", :label="$t('Disable camera for non-moderators')", name="janus_disable_cam")
				bunt-checkbox(v-model="config.janus_defaults.disable_chat", :label="$t('Disable public chat for non-moderators')", name="janus_disable_chat")
			.tab-content(v-if="hasStage", v-show="activeTab === 'stages'")
				h2 {{ $t('Settings for stages') }}
				bunt-input-outline-container(:label="$t('hls.js config')", :class="{error: v$.hlsConfig.$invalid}")
					template(#default="{focus, blur}")
						textarea(@focus="focus", @blur="blur", v-model="hlsConfig")
				.json-error-message(v-if="v$.hlsConfig.$invalid") {{ v$.hlsConfig.$errors[0]?.$message || $t('Invalid JSON') }}
	.ui-form-actions(v-if="loaded")
		bunt-button.btn-save(@click="save", :loading="saving", :error-message="error") {{ $t('Save') }}
		.errors {{ validationErrors.join(', ') }}
</template>
<script setup>
import { ref, computed, watch, onMounted, getCurrentInstance } from 'vue'
import { useStore } from 'vuex'
import { useVuelidate } from '@vuelidate/core'
import api from 'lib/api'
import i18n from 'i18n'
import { required, integer, isJson, url } from 'lib/validators'

const store = useStore()
const loaded = ref(false)

const hasGeneral = computed(() => Boolean(store.getters['hasPermission']?.('world:update') || store.getters['isAdminMode']))
const hasBBB = computed(() => Boolean(store.getters['hasPermission']?.('world:rooms.create.bbb') || store.getters['hasPermission']?.('world:rooms.create.stage') || store.getters['isAdminMode']))
const hasZoom = computed(() => Boolean(store.getters['hasPermission']?.('world:rooms.create.bbb') || store.getters['hasPermission']?.('world:rooms.create.stage') || store.getters['isAdminMode']))
const hasJitsi = computed(() => Boolean(store.getters['hasPermission']?.('world:rooms.create.jitsi') || store.getters['hasPermission']?.('world:rooms.create.stage') || store.getters['isAdminMode']))
const hasJanus = computed(() => Boolean(store.getters['hasPermission']?.('world:rooms.create.chat') || store.getters['hasPermission']?.('world:rooms.create.stage') || store.getters['isAdminMode']))
const hasStage = computed(() => Boolean(store.getters['hasPermission']?.('world:rooms.create.stage') || store.getters['isAdminMode']))

const defaultTab = computed(() => {
	if (hasGeneral.value) return 'general'
	if (hasBBB.value) return 'bbb'
	if (hasZoom.value) return 'zoom'
	if (hasJitsi.value) return 'jitsi'
	if (hasJanus.value) return 'janus'
	if (hasStage.value) return 'stages'
	return 'general'
})
const activeTab = ref(defaultTab.value)

watch([hasGeneral, hasBBB, hasZoom, hasJitsi, hasJanus, hasStage], () => {
	const validTabs = []
	if (hasGeneral.value) validTabs.push('general')
	if (hasBBB.value) validTabs.push('bbb')
	if (hasZoom.value) validTabs.push('zoom')
	if (hasJitsi.value) validTabs.push('jitsi')
	if (hasJanus.value) validTabs.push('janus')
	if (hasStage.value) validTabs.push('stages')
	if (!validTabs.includes(activeTab.value)) {
		activeTab.value = validTabs[0] || 'general'
	}
})

const config = ref({
	connection_limit: 0,
	conftool_url: '',
	conftool_password: '',
	track_room_views: true,
	track_video_event_views: true,
	live_features: {
		chat_rooms: false,
		kiosks: false,
		direct_messaging: false,
		announcements: true
	},
	bbb_defaults: {
		record: false,
		hide_presentation: false,
		waiting_room: false,
		auto_microphone: false,
		auto_camera: false,
		bbb_mute_on_start: false,
		bbb_disable_cam: false,
		bbb_disable_chat: false
	},
	jitsi_defaults: {
		waiting_room: false,
		start_with_audio_muted: false,
		start_with_video_muted: false,
		record: false,
		livestreaming: false,
		disable_cam: false,
		disable_chat: false,
		require_display_name: false
	},
	janus_defaults: {
		waiting_room: false,
		start_with_audio_muted: false,
		start_with_video_muted: false,
		disable_cam: false,
		disable_chat: false
	},
	zoom_defaults: {
		disable_chat: false,
		enable_platform_chat: true,
		enable_platform_qa: false,
		enable_platform_polls: false
	}
})
const hlsConfig = ref('')
const saving = ref(false)
const error = ref(null)
const instance = getCurrentInstance()
const features = instance?.proxy?.$features

const validationErrors = computed(() => v$.value.$errors?.map(e => e.$message) || [])

// Validation rules
const rules = computed(() => ({
	config: {
		connection_limit: {
			required: required(i18n.t('Max connections is required')),
			integer: integer(i18n.t('Max connections must be a number'))
		},
		...(features?.enabled('conftool') && config.value?.conftool_url ? {
			conftool_url: { url: url(i18n.t('Conftool URL must be a URL')) }
		} : {})
	},
	hlsConfig: { isJson: isJson(i18n.t('Invalid JSON')) }
}))

const v$ = useVuelidate(rules, { config, hlsConfig })

async function fetchConfig() {
	try {
		const data = await api.call('world.config.get')
		data.bbb_defaults = Object.assign({
			record: false,
			hide_presentation: false,
			waiting_room: false,
			auto_microphone: false,
			auto_camera: false,
			bbb_mute_on_start: false,
			bbb_disable_cam: false,
			bbb_disable_chat: false
		}, data.bbb_defaults || {})
		data.jitsi_defaults = Object.assign({
			waiting_room: false,
			start_with_audio_muted: false,
			start_with_video_muted: false,
			record: false,
			livestreaming: false,
			disable_cam: false,
			disable_chat: false,
			require_display_name: false
		}, data.jitsi_defaults || {})
		data.janus_defaults = Object.assign({
			waiting_room: false,
			start_with_audio_muted: false,
			start_with_video_muted: false,
			disable_cam: false,
			disable_chat: false
		}, data.janus_defaults || {})
		data.zoom_defaults = Object.assign({
			disable_chat: false,
			enable_platform_chat: true,
			enable_platform_qa: false,
			enable_platform_polls: false
		}, data.zoom_defaults || {})
		config.value = {
			...data,
			track_video_event_views: data.track_video_event_views ?? data.track_event_views ?? data.track_world_views ?? true,
			live_features: Object.assign({
				chat_rooms: false,
				kiosks: false,
				direct_messaging: false,
				announcements: true
			}, data.live_features || {})
		}
		hlsConfig.value = data.video_player?.['hls.js'] ? JSON.stringify(data.video_player['hls.js'], null, 2) : ''
		loaded.value = true
	} catch (e) {
		error.value = e.message || e.toString()
		console.error(e)
	}
}

onMounted(() => {
	if (store.state.connected) {
		fetchConfig()
	} else {
		const unwatch = store.watch(
			state => state.connected,
			connected => {
				if (connected) {
					fetchConfig()
					unwatch()
				}
			}
		)
	}
})

async function save() {
	v$.value.$touch()
	if (v$.value.$invalid) return
	if (!config.value) return
	saving.value = true
	try {
		const patch = {}
		if (hasGeneral.value) {
			patch.connection_limit = parseInt(config.value.connection_limit, 10) || 0
			patch.track_room_views = Boolean(config.value.track_room_views)
			patch.track_event_views = Boolean(config.value.track_video_event_views)
			patch.track_video_event_views = Boolean(config.value.track_video_event_views)
			patch.live_features = {
				chat_rooms: Boolean(config.value.live_features?.chat_rooms),
				kiosks: Boolean(config.value.live_features?.kiosks),
				direct_messaging: Boolean(config.value.live_features?.direct_messaging),
				announcements: config.value.live_features?.announcements !== false
			}
			if (features?.enabled('conftool')) {
				patch.conftool_url = config.value.conftool_url || ''
				patch.conftool_password = config.value.conftool_password || ''
			}
		}
		if (hasBBB.value) {
			patch.bbb_defaults = config.value.bbb_defaults
		}
		if (hasZoom.value) {
			patch.zoom_defaults = config.value.zoom_defaults
		}
		if (hasJitsi.value) {
			patch.jitsi_defaults = config.value.jitsi_defaults
		}
		if (hasJanus.value) {
			patch.janus_defaults = config.value.janus_defaults
		}
		if (hasStage.value) {
			if (hlsConfig.value && hlsConfig.value.trim()) {
				patch.video_player = { 'hls.js': JSON.parse(hlsConfig.value.trim()) }
			} else {
				patch.video_player = null
			}
		}
		const updated = await api.call('world.config.patch', patch)
		if (store.state.world && patch.live_features) {
			store.state.world.live_features = patch.live_features
		}
	} catch (e) {
		console.error(e.apiError || e)
		error.value = e.apiError?.code || e.message || e.toString()
	} finally {
		saving.value = false
	}
}
</script>
<style lang="stylus">
.c-mainconfig
	flex: auto
	display: flex
	flex-direction: column
	min-height: 0
	height: 100%
	.ui-page-header
		flex: none
		position: sticky
		top: 0
		z-index: 10
		background-color: $clr-grey-50
	> .c-scrollbars
		flex: auto
		min-height: 0
	.config-tabs
		display: flex
		border-bottom: 1px solid #e2e8f0
		margin-bottom: 20px
		gap: 8px
		.tab-btn
			background: transparent
			border: none
			border-bottom: 2px solid transparent
			padding: 10px 16px
			font-size: 14px
			font-weight: 500
			color: #64748b
			cursor: pointer
			transition: all 0.15s ease
			&:hover
				color: #0f172a
			&.active
				color: var(--color-primary, #2185d0)
				border-bottom-color: var(--color-primary, #2185d0)
				font-weight: 600
	.tab-content
		display: flex
		flex-direction: column
	.ui-form-actions
		flex: none
		position: sticky
		bottom: 0
		background-color: white
		border-top: border-separator()
		padding: 16px
		z-index: 10
	.bunt-input-outline-container
		margin-top: 16px
		&.error
			label
				color: $clr-danger
			.outline
				stroke: $clr-danger
				stroke-width: 2px
		textarea
			background-color: transparent
			border: none
			outline: none
			resize: vertical
			min-height: 120px
			padding: 0 8px
	.json-error-message
		color: $clr-danger
		margin: 4px
</style>
