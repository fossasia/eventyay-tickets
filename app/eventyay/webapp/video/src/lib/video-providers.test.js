/**
 * Video provider dropdown helpers.
 * Run: node --test src/lib/video-providers.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {
	VIDEO_CREATE_PROVIDERS,
	applyVideoProviderToConfig,
	getAvailableVideoProviders,
	getConfiguredRoomLabel,
	hasEmbeddedSuite,
	isVideoProviderEnabled,
	isVideoProviderPermitted,
	isRoomVisibleToAttendee,
	supportsPlatformSidebar,
} from './video-providers.js'

function allow(permissions) {
	const permitted = new Set(permissions)
	return (permission) => permitted.has(permission)
}

function features(enabledFlags) {
	const flags = new Set(enabledFlags)
	return (flag) => flags.has(flag)
}

test('dropdown labels match the organiser create options', () => {
	assert.deepEqual(
		VIDEO_CREATE_PROVIDERS.map(provider => provider.label),
		['Stream (YT, HLS)', 'BBB', 'Zoom', 'Jitsi', 'Janus', 'LoungeMesh']
	)
})

test('without admin mode, room:update only exposes Stream', () => {
	const providers = getAvailableVideoProviders(
		allow(['room:update']),
		false,
		features(['jitsi', 'janus'])
	)
	assert.deepEqual(providers.map(provider => provider.id), ['stream'])
})

test('disabled feature flags hide Jitsi and Janus even in admin mode', () => {
	const providers = getAvailableVideoProviders(
		allow(['world:rooms.create.bbb', 'world:rooms.create.jitsi']),
		true,
		features([])
	)
	assert.deepEqual(providers.map(provider => provider.id), ['stream', 'bbb', 'zoom', 'loungemesh'])
})

test('admin mode with create permissions includes gated providers', () => {
	const providers = getAvailableVideoProviders(
		allow(['world:rooms.create.bbb', 'world:rooms.create.jitsi']),
		true,
		features(['jitsi', 'janus'])
	)
	assert.deepEqual(providers.map(provider => provider.id), ['stream', 'bbb', 'zoom', 'jitsi', 'janus', 'loungemesh'])
})

test('users without create or update permission see no providers', () => {
	const providers = getAvailableVideoProviders(
		allow([]),
		false,
		features(['jitsi', 'janus'])
	)
	assert.equal(providers.length, 0)
})

test('stage create permission is enough for Stream', () => {
	const providers = getAvailableVideoProviders(
		allow(['world:rooms.create.stage']),
		false,
		features([])
	)
	assert.deepEqual(providers.map(provider => provider.id), ['stream'])
})

test('Jitsi requires permission when not in admin mode', () => {
	assert.equal(
		isVideoProviderPermitted(
			VIDEO_CREATE_PROVIDERS.find(provider => provider.id === 'jitsi'),
			allow(['room:update']),
			false
		),
		false
	)
	assert.equal(
		isVideoProviderPermitted(
			VIDEO_CREATE_PROVIDERS.find(provider => provider.id === 'jitsi'),
			allow(['world:rooms.create.jitsi']),
			false
		),
		true
	)
})

test('Jitsi stays hidden when its feature flag is off', () => {
	assert.equal(
		isVideoProviderEnabled(
			VIDEO_CREATE_PROVIDERS.find(provider => provider.id === 'jitsi'),
			features([])
		),
		false
	)
})

test('configured room labels include the video provider', () => {
	assert.equal(getConfiguredRoomLabel({id: 'stage', name: 'Stage'}), 'Stage: Stream')
	assert.equal(getConfiguredRoomLabel({id: 'channel-bbb', name: 'Video Channel'}), 'Video Channel: BBB')
	assert.equal(getConfiguredRoomLabel({id: 'channel-jitsi', name: 'Video Channel (Jitsi)'}), 'Video Channel: Jitsi')
	assert.equal(getConfiguredRoomLabel({id: 'channel-janus', name: 'Video Channel (beta)'}), 'Video Channel: Janus')
	assert.equal(getConfiguredRoomLabel({id: 'channel-zoom', name: 'Video Channel (Zoom)'}), 'Video Channel: Zoom')
	assert.equal(getConfiguredRoomLabel({id: 'channel-loungemesh', name: 'Spatial Lounge (LoungeMesh)'}), 'Video Channel: LoungeMesh')
	assert.equal(getConfiguredRoomLabel({id: 'channel-text', name: 'Text Channel'}), 'Text Channel')
})

test('applying a provider sets the starting module config', () => {
	const config = { module_config: [] }
	assert.equal(
		applyVideoProviderToConfig(config, {id: 'stage', startingModule: 'livestream.native'}),
		true
	)
	assert.deepEqual(config.module_config, [{
		type: 'livestream.native',
		config: { playback_mode: 'always_on' }
	}])

	const zoomConfig = { module_config: [] }
	assert.equal(
		applyVideoProviderToConfig(zoomConfig, {id: 'channel-zoom', startingModule: 'call.zoom'}),
		true
	)
	assert.deepEqual(zoomConfig.module_config, [
		{
			type: 'call.zoom',
			config: {
				meeting_number: '',
				password: '',
				disable_chat: false
			}
		},
		{
			type: 'chat.native',
			config: { volatile: true }
		}
	])

	const lmConfig = { module_config: [] }
	assert.equal(
		applyVideoProviderToConfig(lmConfig, {id: 'channel-loungemesh', startingModule: 'call.loungemesh'}),
		true
	)
	assert.deepEqual(lmConfig.module_config, [
		{
			type: 'call.loungemesh',
			config: {
				prefer_server: '',
				enable_notes: true,
				enable_whiteboard: true,
				enable_spatial_chat: true
			}
		}
	])
})

test('hasEmbeddedSuite identifies BBB and Jitsi but not Janus, Zoom, or LoungeMesh', () => {
	assert.equal(hasEmbeddedSuite({ 'call.bigbluebutton': {} }), true)
	assert.equal(hasEmbeddedSuite({ 'call.jitsi': {} }), true)
	assert.equal(hasEmbeddedSuite({ 'call.zoom': {} }), false)
	assert.equal(hasEmbeddedSuite({ 'call.janus': {} }), false)
	assert.equal(hasEmbeddedSuite({ 'call.loungemesh': {} }), false)
	assert.equal(hasEmbeddedSuite([{ type: 'call.janus' }]), false)
	assert.equal(hasEmbeddedSuite([{ type: 'call.jitsi' }]), true)
	assert.equal(hasEmbeddedSuite([{ type: 'call.zoom' }]), false)
	assert.equal(hasEmbeddedSuite([{ type: 'call.loungemesh' }]), false)
})

test('supportsPlatformSidebar allows chat/polls for Janus, stage, Zoom, and LoungeMesh addons, but suppresses for embedded suites', () => {
	// Janus with chat.native
	assert.equal(supportsPlatformSidebar({ 'call.janus': {}, 'chat.native': {} }), true)
	// Zoom with chat.native (supported via platform sidebar)
	assert.equal(supportsPlatformSidebar({ 'call.zoom': {}, 'chat.native': {} }), true)
	// LoungeMesh with question addon (supported via platform sidebar)
	assert.equal(supportsPlatformSidebar({ 'call.loungemesh': {}, question: {} }), true)
	// LoungeMesh alone (suppressed by default for spatial immersion)
	assert.equal(supportsPlatformSidebar({ 'call.loungemesh': {} }), false)
	// BBB with chat.native (suppressed because BBB has native chat)
	assert.equal(supportsPlatformSidebar({ 'call.bigbluebutton': {}, 'chat.native': {} }), false)
	// Jitsi with poll (suppressed because Jitsi has native polls)
	assert.equal(supportsPlatformSidebar({ 'call.jitsi': {}, poll: {} }), false)
	// Stage with chat.native
	assert.equal(supportsPlatformSidebar({ 'livestream.native': {}, 'chat.native': {} }), true)
	// Standalone chat only
	assert.equal(supportsPlatformSidebar({ 'chat.native': {} }), false)
})

test('videoProvidersConfig hides disabled providers from organizer creation', () => {
	const config = {
		jitsi: { organizer: false, attendee: true },
		bbb: { organizer: true, attendee: true },
		loungemesh: { organizer: false, attendee: false }
	}
	const providers = getAvailableVideoProviders(
		allow(['world:rooms.create.bbb', 'world:rooms.create.jitsi']),
		true,
		features(['jitsi', 'janus']),
		config
	)
	// Jitsi and LoungeMesh should be excluded because organizer === false
	assert.deepEqual(
		providers.map(p => p.id),
		['stream', 'bbb', 'zoom', 'janus']
	)
})

test('isRoomVisibleToAttendee checks provider attendee visibility', () => {
	const config = {
		jitsi: { organizer: true, attendee: false },
		bbb: { organizer: true, attendee: true },
		loungemesh: { organizer: true, attendee: false }
	}
	assert.equal(isRoomVisibleToAttendee({ modules: [{ type: 'call.jitsi' }] }, config), false)
	assert.equal(isRoomVisibleToAttendee({ modules: [{ type: 'call.bigbluebutton' }] }, config), true)
	assert.equal(isRoomVisibleToAttendee({ modules: [{ type: 'call.loungemesh' }] }, config), false)
	assert.equal(isRoomVisibleToAttendee({ modules: [{ type: 'chat.native' }] }, config), true)
	assert.equal(isRoomVisibleToAttendee({ modules: [{ type: 'call.jitsi' }] }, null), true)
})
