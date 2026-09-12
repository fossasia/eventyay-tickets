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
				button.tab-btn(type="button", role="tab", v-if="hasStage", :class="{active: activeTab === 'stages'}", @click="activeTab = 'stages'") {{ $t('Stages & Streams') }}
			.tab-content(v-if="hasGeneral", v-show="activeTab === 'general'")
				h2 {{ $t('Live platform features') }}
				bunt-checkbox(v-model="config.live_features.chat_rooms", name="enable_chat_rooms")
					span.feature-label {{ $t('Enable Chat Rooms') }}
					span.badge-experimental {{ $t('Experimental') }}
				bunt-checkbox(v-model="config.live_features.kiosks", name="enable_kiosks")
					span.feature-label {{ $t('Enable Kiosks') }}
					span.badge-experimental {{ $t('Experimental') }}
				bunt-checkbox(v-model="config.live_features.direct_messaging", name="enable_direct_messaging")
					span.feature-label {{ $t('Enable Direct messaging') }}
					span.badge-experimental {{ $t('Experimental') }}
				bunt-checkbox(v-model="config.live_features.announcements", name="allow_announcements")
					span.feature-label {{ $t('Allow Announcements') }}
					span.badge-experimental {{ $t('Experimental') }}
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
const hasStage = computed(() => Boolean(store.getters['hasPermission']?.('world:rooms.create.stage') || store.getters['isAdminMode']))

const activeTab = ref(hasGeneral.value ? 'general' : (hasStage.value ? 'stages' : (hasBBB.value ? 'bbb' : 'general')))

watch([hasGeneral, hasStage, hasBBB], () => {
	if (activeTab.value === 'general' && !hasGeneral.value) {
		activeTab.value = hasStage.value ? 'stages' : (hasBBB.value ? 'bbb' : 'general')
	} else if (activeTab.value === 'stages' && !hasStage.value) {
		activeTab.value = hasGeneral.value ? 'general' : (hasBBB.value ? 'bbb' : 'stages')
	} else if (activeTab.value === 'bbb' && !hasBBB.value) {
		activeTab.value = hasGeneral.value ? 'general' : (hasStage.value ? 'stages' : 'bbb')
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
		announcements: false
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
		config.value = {
			...data,
			track_video_event_views: data.track_video_event_views ?? data.track_event_views ?? data.track_world_views ?? true,
			live_features: Object.assign({
				chat_rooms: false,
				kiosks: false,
				direct_messaging: false,
				announcements: false
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
				announcements: Boolean(config.value.live_features?.announcements)
			}
			if (features?.enabled('conftool')) {
				patch.conftool_url = config.value.conftool_url || ''
				patch.conftool_password = config.value.conftool_password || ''
			}
		}
		if (hasBBB.value) {
			patch.bbb_defaults = config.value.bbb_defaults
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
	.badge-experimental
		display: inline-block
		margin-left: 8px
		padding: 2px 6px
		font-size: 11px
		font-weight: 500
		line-height: 1.2
		border-radius: 4px
		background-color: $clr-grey-200
		color: $clr-secondary-text-light
		vertical-align: middle
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
