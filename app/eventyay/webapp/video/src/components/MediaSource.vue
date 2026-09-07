<template lang="pug">
.c-media-source(:class="{'in-background': background, 'in-room-manager': inRoomManager}")
	transition(name="background-room")
		router-link.background-room(v-if="background", :to="backgroundRoomLink")
			.description
				.hint {{ $t('Currently playing') }}
				.room-name(v-if="room", v-html="$emojify(room.name)")
				.room-name(v-else-if="call") {{ $t('Private call') }}
			.global-placeholder
			bunt-icon-button(@click.prevent.stop="$emit('close')") close
	Livestream(v-if="room && shouldUseLivestream", ref="livestream", :room="room", :module="module", :size="background ? 'tiny' : 'normal'", :key="`livestream-${room.id}`", @playback-state-changed="onMainPlayerPlaybackChanged")
	JanusCall(v-else-if="room && module.type === 'call.janus'", ref="janus", :room="room", :module="module", :background="background", :size="background ? 'tiny' : 'normal'", :key="`janus-${room.id}`")
	JanusChannelCall(v-else-if="call", ref="janus", :call="call", :background="background", :size="background ? 'tiny' : 'normal'", :key="`call-${call.id}`", @close="$emit('close')")
	.iframe-consent-gate(v-if="consentBlockedUrl && !background")
		iframe-blocker(:src="consentBlockedUrl", allow="camera *; autoplay *; microphone *; fullscreen *; display-capture *", allowfullscreen, @consent-given="onConsentGiven")
	.iframe-error(v-if="!iframeEl && !consentBlockedUrl && (iframeError || iframeOffline)", :class="{background: background, 'size-tiny': background}")
		.offline-message(v-if="iframeOffline") {{ $t('Stream offline') }}
		.offline-message(v-else) {{ $t('We could not connect to the video conference server, sorry.') }}
	iframe#video-player-translation(v-if="languageIframeUrl", ref="translationIframeEl", :src="languageIframeUrl", style="position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none;", frameborder="0", gesture="media", allow="autoplay; encrypted-media", referrerpolicy="strict-origin-when-cross-origin", @load="onTranslationIframeLoaded")
	audio(ref="whepAudioEl", autoplay, style="display: none;")
</template>
<script setup>
// TODO functional component?
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useStore } from 'vuex';
import { isEqual } from 'lodash';
import api from 'lib/api';
import { normalizeYoutubeVideoId } from 'lib/validators';
import { isDomainBlocked, getUrlDomain } from 'lib/iframeConsent';
import IframeBlocker from 'components/IframeBlocker';
import JanusCall from 'components/JanusCall';
import JanusChannelCall from 'components/JanusChannelCall';
import Livestream from 'components/Livestream';
import { WhepClient } from 'lib/webrtc/whep';
import {
	getStagePlaybackMode,
	PLAYBACK_MODE_SCHEDULE_DRIVEN,
	STREAM_TYPE_HLS,
	STREAM_TYPE_VIMEO,
	STREAM_TYPE_YOUTUBE,
} from 'lib/stage-streams';

const jitsiExternalApiLoaders = new Map();

// Props & Emits
defineOptions({
	components: { Livestream, JanusCall, JanusChannelCall, IframeBlocker },
});
const props = defineProps({
	room: Object,
	call: Object,
	background: {
		type: Boolean,
		default: false,
	},
});
const emit = defineEmits(['close']);

const store = useStore();
const route = useRoute();
const router = useRouter();

const iframeError = ref(null);
const iframeEl = ref(null);
const languageIframeUrl = ref(null);
const isUnmounted = ref(false);
const consentBlockedUrl = ref(null);
// Prevents overlapping initializeIframe runs (e.g. store watcher + consent handler)
// from both passing the iframeEl guard before the first await.
let iframeInitInProgress = false;

// WHEP audio client
const whepAudioEl = ref(null);
const translationIframeEl = ref(null);
let whepClient = null;

// Template refs
const livestream = ref(null);
const janus = ref(null);
let jitsiApi = null;

// Mapped state/getters
const activeInterpretation = computed(() => {
	if (!props.room?.id) return null;
	return store.state.interpretationStreamsByRoom?.[props.room.id] || store.state.youtubeTranslationsByRoom?.[props.room.id] || null;
});
const autoplay = computed(() => store.getters.autoplay);
const mainPlayerPaused = ref(!autoplay.value);

const module = computed(() => {
	if (!props.room) return null;
	return props.room.modules.find((m) =>
		[
			'livestream.native',
			'livestream.youtube',
			'call.bigbluebutton',
			'call.janus',
			'call.zoom',
			'call.jitsi',
		].includes(m.type)
	);
});

const isLivestreamModule = computed(() =>
	[
		'livestream.native',
		'livestream.youtube',
	].includes(module.value?.type)
);

const isScheduleDrivenStage = computed(() =>
	isLivestreamModule.value &&
	getStagePlaybackMode(module.value) === PLAYBACK_MODE_SCHEDULE_DRIVEN
);

const shouldUseLivestream = computed(() => {
	if (!props.room || !module.value) return false;
	const streamType = isScheduleDrivenStage.value ? props.room?.currentStream?.stream_type : null;

	if (streamType) {
		return streamType === STREAM_TYPE_HLS;
	}

	return module.value.type === 'livestream.native';
});

// When stream schedules are enabled, the backend returns 404 (mapped to null) if
// no stream is currently active. For iframe-based streams we show a full-size
// offline placeholder (same frame size as the player) instead of showing nothing.
//
// Important: If the module has a configured default URL/ytid, we still render it
// even when there is no active schedule.
const iframeOffline = computed(() => {
	if (!props.room || !module.value) return false;
	if (shouldUseLivestream.value) return false;

	const isScheduleDriven = isScheduleDrivenStage.value;
	const currentStream = isScheduleDriven ? props.room?.currentStream : null;
	const streamType = currentStream?.stream_type;
	const moduleType = module.value.type;
	const isYouTube = streamType === STREAM_TYPE_YOUTUBE || moduleType === 'livestream.youtube';
	const isVimeo = streamType === STREAM_TYPE_VIMEO;

	if (!isYouTube && !isVimeo) return false;

	const scheduleUrl = currentStream?.url || null;

	if (isYouTube) {
		if (scheduleUrl && normalizeYoutubeVideoId(scheduleUrl)) return false;
		if (isScheduleDriven) return true;
		const ytid = module.value.config?.ytid || null;
		if (ytid && normalizeYoutubeVideoId(ytid)) return false;
		return true;
	}

	if (scheduleUrl) return false;
	if (isScheduleDriven) return true;
	const moduleUrl = module.value.config?.url || null;
	return !moduleUrl;
});

const inRoomManager = computed(() => route.name === 'room:manage');

const backgroundRoomLink = computed(() => {
	if (!props.room) return props.call ? { name: 'channel', params: { channelId: props.call.channel } } : { name: 'about' };
	return { name: 'room', params: { roomId: props.room.id } };
});

watch(
	() => props.background,
	(value) => {
		if (value && consentBlockedUrl.value && !iframeEl.value) {
			emit('close')
			return
		}
		if (!iframeEl.value) return;
		if (value) {
			iframeEl.value.classList.add('background');
			iframeEl.value.classList.add('size-tiny');
		} else {
			iframeEl.value.classList.remove('background');
			iframeEl.value.classList.remove('size-tiny');
		}
	}
);

watch(module, async (value, oldValue) => {
	if (isEqual(value, oldValue)) return;
	resetMainPlayerPaused();
	destroyIframe();
	if (shouldUseLivestream.value) return;
	await initializeIframe(false);
	await applyInterpretation(activeInterpretation.value);
});

watch(shouldUseLivestream, async (shouldUse, oldShouldUse) => {
	if (shouldUse === oldShouldUse) return;
	resetMainPlayerPaused();
	if (shouldUse) {
		destroyIframe();
	} else {
		await initializeIframe(false);
		await applyInterpretation(activeInterpretation.value);
	}
});

watch(
	() => props.room?.currentStream,
	async (newStream, oldStream) => {
		if (!isEqual(newStream, oldStream) && module.value) {
			resetMainPlayerPaused();
			if (shouldUseLivestream.value) {
				return;
			}
			destroyIframe();
			await initializeIframe(false);
			await applyInterpretation(activeInterpretation.value);
		}
	},
	{ deep: true }
);

watch(
	() => store.state.unblockedIframeDomains,
	() => {
		if (iframeEl.value) return
		if (!consentBlockedUrl.value) return // gate not active; nothing to reconcile
		const domain = getUrlDomain(consentBlockedUrl.value)
		if (domain && !isDomainBlocked(domain)) {
			consentBlockedUrl.value = null
			// Covers store-only unblocks (e.g. consent changed elsewhere) while the
			// gate URL is still set. Persistent "Remember" relies on this path only;
			// onConsentGiven skips initializeIframe for that case to avoid a double init race.
			initializeIframe(false)
		}
	}
)

const isPlayingTranslationVideo = ref(false);
const activeTranslationVideoId = ref(null);
let interpretationUpdateToken = 0;

watch(activeInterpretation, applyInterpretation);

async function applyInterpretation(interpConfig) {
	if (!props.room) return;
	const streamType = isScheduleDrivenStage.value ? props.room?.currentStream?.stream_type : null;
	const isYouTube = streamType === STREAM_TYPE_YOUTUBE || module.value?.type === 'livestream.youtube';

	const updateToken = ++interpretationUpdateToken;
	disconnectWhepTranslation();

	const audioSource = interpConfig?.url || null;
	const requestedUseVideo = interpConfig?.useVideo || false;
	const translationVideoId = audioSource ? normalizeYoutubeVideoId(audioSource) : null;
	const useVideo = requestedUseVideo && !!translationVideoId;

	if (useVideo) {
		if (isPlayingTranslationVideo.value && iframeEl.value && activeTranslationVideoId.value === translationVideoId) return;
		isPlayingTranslationVideo.value = true;
		activeTranslationVideoId.value = translationVideoId;
		languageIframeUrl.value = null; // Clear any audio iframe
		destroyIframe();
		await initializeIframe(false);
		return;
	} else if (isPlayingTranslationVideo.value) {
		isPlayingTranslationVideo.value = false;
		activeTranslationVideoId.value = null;
		destroyIframe();
		await initializeIframe(false);
	}

	if (audioSource) {
		let isWhep = false;
		try {
			new URL(audioSource);
			if (!normalizeYoutubeVideoId(audioSource)) {
				isWhep = true;
			}
		} catch (e) {
			isWhep = false;
		}

		if (isWhep) {
			languageIframeUrl.value = null;
			const client = new WhepClient(audioSource, whepAudioEl.value);
			whepClient = client;
			try {
				await client.connect();
				if (updateToken !== interpretationUpdateToken) {
					client.disconnect();
					if (whepClient === client) whepClient = null;
				}
			} catch (err) {
				console.error('Failed to connect to WHEP interpretation source', err);
				client.disconnect();
				if (whepClient === client) whepClient = null;
			}
		} else {
			// Create hidden interpretation audio iframe for YouTube audio translation
			languageIframeUrl.value = getLanguageIframeUrl(audioSource);
		}

		muteMainPlayer();

		if (mainPlayerPaused.value) {
			setTimeout(() => {
				if (updateToken !== interpretationUpdateToken) return;
				pauseTranslationAudio();
			}, 600);
		}
	} else {
		languageIframeUrl.value = null;
		setTimeout(() => {
			if (updateToken !== interpretationUpdateToken) return;
			const streamType = isScheduleDrivenStage.value ? props.room?.currentStream?.stream_type : null;
			const isYouTube = streamType === STREAM_TYPE_YOUTUBE || module.value?.type === 'livestream.youtube';
			if (isYouTube && getYoutubeConfig().startMuted) return;
			unmuteMainPlayer();
		}, 100);
	}
}

onMounted(async () => {
	window.addEventListener('message', onWindowMessage);
	if (!props.room) return;
	if (shouldUseLivestream.value) return;
	await initializeIframe(false);
	await applyInterpretation(activeInterpretation.value);
});

onBeforeUnmount(() => {
	isUnmounted.value = true;
	window.removeEventListener('message', onWindowMessage);
	if (whepClient) {
		disconnectWhepTranslation();
	}
	iframeEl.value?.remove();
	if (api.socketState !== 'open') return;
	// TODO move to store?
	if (props.room) api.call('room.leave', { room: props.room.id });
});

function hasAudioOnlyInterpretation() {
	return Boolean(activeInterpretation.value?.url && !activeInterpretation.value?.useVideo);
}

function muteMainPlayer() {
	muteYouTubePlayer();
	const videoEl = livestream.value?.$refs?.video || livestream.value?.$el?.querySelector?.('video');
	if (videoEl) {
		videoEl.muted = true;
	}
}

function unmuteMainPlayer() {
	unmuteYouTubePlayer();
	const videoEl = livestream.value?.$refs?.video || livestream.value?.$el?.querySelector?.('video');
	if (videoEl) {
		videoEl.muted = false;
	}
}

function muteYouTubePlayer() {
	if (!iframeEl.value || !iframeEl.value.contentWindow) return;
	try {
		subscribeToYouTubePlayerEvents();
		iframeEl.value.contentWindow.postMessage(
			'{"event":"command","func":"mute","args":""}',
			'*'
		);
	} catch (error) {
		console.warn('Failed to mute embedded YouTube player', {
			roomId: props.room?.id,
			error,
		});
	}
}

function getYoutubeConfig() {
	const streamType = isScheduleDrivenStage.value ? props.room?.currentStream?.stream_type : null;
	const currentStream = streamType === STREAM_TYPE_YOUTUBE ? props.room?.currentStream : null;
	return {
		...(currentStream?.config || {}),
		...(module.value?.config || {}),
	};
}

function disconnectWhepTranslation() {
	if (!whepClient) return;
	whepClient.disconnect();
	whepClient = null;
}

function unmuteYouTubePlayer() {
	if (!iframeEl.value || !iframeEl.value.contentWindow) return;
	try {
		subscribeToYouTubePlayerEvents();
		iframeEl.value.contentWindow.postMessage(
			'{"event":"command","func":"unMute","args":""}',
			'*'
		);
	} catch (error) {
		console.warn('Failed to unmute embedded YouTube player', {
			roomId: props.room?.id,
			error,
		});
	}
}

function pauseTranslationAudio() {
	if (whepAudioEl.value && !whepAudioEl.value.paused) {
		whepAudioEl.value.pause();
	}
	pauseYouTubeTranslationIframe();
}

function resumeTranslationAudio() {
	if (whepAudioEl.value && whepAudioEl.value.srcObject) {
		whepAudioEl.value.play().catch(e =>
			console.warn('Failed to resume WHEP interpretation audio:', e)
		);
	}
	resumeYouTubeTranslationIframe();
}

function pauseYouTubeTranslationIframe() {
	const iframe = translationIframeEl.value;
	if (!iframe?.contentWindow) return;
	try {
		iframe.contentWindow.postMessage(
			'{"event":"command","func":"pauseVideo","args":""}',
			'*'
		);
	} catch (error) {
		console.warn('Failed to pause translation iframe:', error);
	}
}

function resumeYouTubeTranslationIframe() {
	const iframe = translationIframeEl.value;
	if (!iframe?.contentWindow) return;
	try {
		iframe.contentWindow.postMessage(
			'{"event":"command","func":"playVideo","args":""}',
			'*'
		);
	} catch (error) {
		console.warn('Failed to resume translation iframe:', error);
	}
}

function onMainPlayerPlaybackChanged(isPlaying) {
	mainPlayerPaused.value = !isPlaying;
	if (!activeInterpretation.value?.url) return;
	if (isPlaying) {
		resumeTranslationAudio();
	} else {
		pauseTranslationAudio();
	}
}

function resetMainPlayerPaused() {
	mainPlayerPaused.value = !autoplay.value;
}

function onTranslationIframeLoaded() {
	if (mainPlayerPaused.value) {
		pauseYouTubeTranslationIframe();
	}
}

function onWindowMessage(event) {
	if (!iframeEl.value?.contentWindow || event.source !== iframeEl.value.contentWindow) return;

	let data = event.data;
	if (typeof data === 'string') {
		try {
			data = JSON.parse(data);
		} catch {
			return;
		}
	}
	if (!data || typeof data !== 'object') return;

	let playerState = null;
	if (data.event === 'onStateChange' && typeof data.info === 'number') {
		playerState = data.info;
	} else if (data.event === 'infoDelivery' && typeof data.info?.playerState === 'number') {
		playerState = data.info.playerState;
	}
	if (playerState === null) return;

	if (playerState === 1) {
		onMainPlayerPlaybackChanged(true);
	} else if (playerState === 2 || playerState === 0) {
		onMainPlayerPlaybackChanged(false);
	}
}

function subscribeToYouTubePlayerEvents() {
	if (!iframeEl.value?.contentWindow) return;
	try {
		iframeEl.value.contentWindow.postMessage(
			JSON.stringify({ event: 'listening', id: iframeEl.value.id }),
			'*'
		);
		iframeEl.value.contentWindow.postMessage(
			JSON.stringify({ event: 'command', func: 'addEventListener', args: ['onStateChange'] }),
			'*'
		);
	} catch (error) {
		console.warn('Failed to subscribe to embedded YouTube player events', {
			roomId: props.room?.id,
			error,
		});
	}
}

async function initializeIframe(mute, skipConsentCheck = false) {
	if (!module.value) return;
	if (shouldUseLivestream.value) return;
	if (iframeOffline.value) return;
	if (iframeEl.value) return; // already initialised
	if (iframeInitInProgress) return;
	iframeInitInProgress = true;
	iframeError.value = null;
	try {
		let iframeUrl;
		let hideIfBackground = false;
		let isYouTube = false;
		let jitsiConfig = null;
		const isScheduleDriven = isScheduleDrivenStage.value;
		const currentStream = isScheduleDriven ? props.room?.currentStream : null;
		const streamType = currentStream?.stream_type;
		const effectiveModuleType = streamType === STREAM_TYPE_YOUTUBE
			? 'livestream.youtube'
			: streamType === STREAM_TYPE_VIMEO
			? 'livestream.vimeo'
			: (!isScheduleDriven ? module.value.type : null);

		switch (effectiveModuleType) {
			case 'call.bigbluebutton': {
				({ url: iframeUrl } = await api.call('bbb.room_url', {
					room: props.room.id,
				}));
				hideIfBackground = true;
				break;
			}
			case 'call.zoom': {
				({ url: iframeUrl } = await api.call('zoom.room_url', {
					room: props.room.id,
				}));
				hideIfBackground = true;
				break;
			}
			case 'call.jitsi': {
				jitsiConfig = await api.call('jitsi.room_config', {
					room: props.room.id,
				});
				iframeUrl = getJitsiRoomUrl(jitsiConfig);
				hideIfBackground = true;
				break;
			}
			case 'livestream.vimeo': {
				const vimeoUrl = currentStream?.url || module.value.config?.url;
				if (vimeoUrl) {
					const vimeoMatch = vimeoUrl.match(/vimeo\.com\/(?:.*\/)?(\d+)/);
					if (vimeoMatch) {
						iframeUrl = `https://player.vimeo.com/video/${vimeoMatch[1]}?autoplay=${autoplay.value ? '1' : '0'}&muted=${mute ? '1' : '0'}`;
					} else {
						iframeUrl = vimeoUrl;
					}
				}
				break;
			}
			case 'livestream.youtube': {
				isYouTube = true;
				let ytid;
				const translationVideoId = activeInterpretation.value?.useVideo && activeInterpretation.value?.url
					? normalizeYoutubeVideoId(activeInterpretation.value.url)
					: null;
				if (translationVideoId) {
					ytid = translationVideoId;
					isPlayingTranslationVideo.value = true;
					activeTranslationVideoId.value = translationVideoId;
				} else if (streamType === STREAM_TYPE_YOUTUBE && currentStream?.url) {
					ytid = normalizeYoutubeVideoId(currentStream.url);
					isPlayingTranslationVideo.value = false;
					activeTranslationVideoId.value = null;
				} else if (!isScheduleDriven && module.value.type === 'livestream.youtube' && module.value.config?.ytid) {
					ytid = normalizeYoutubeVideoId(module.value.config.ytid);
					isPlayingTranslationVideo.value = false;
					activeTranslationVideoId.value = null;
				} else {
					ytid = null;
					isPlayingTranslationVideo.value = false;
					activeTranslationVideoId.value = null;
				}
				if (!ytid) {
					iframeError.value = new Error('Invalid YouTube video ID');
					break;
				}
				const config = getYoutubeConfig();
				const shouldStartMuted = Boolean(
					mute || config.startMuted || hasAudioOnlyInterpretation()
				);
				const shouldAutoplay = Boolean(autoplay.value && !config.hideControls);
				iframeUrl = getYoutubeUrl(
					ytid,
					shouldAutoplay,
					shouldStartMuted,
					config.hideControls,
					config.noRelated,
					config.showInfo,
					config.disableKb,
					config.loop,
					config.modestBranding,
					config.enablePrivacyEnhancedMode
				);
				break;
			}
		}
		if (!iframeUrl || isUnmounted.value) return;

		// Check iframe consent policy before creating the element.
		// skipConsentCheck is set when the user clicked "Show" in the consent gate
		// so the iframe can be created even for the "Show once" (non-persistent) path.
		// Consent applies to all iframe providers (including BBB/Zoom). hideIfBackground
		// only affects CSS for miniplayer layout, not whether consent is required.
		if (!skipConsentCheck) {
			const urlDomain = getUrlDomain(iframeUrl)
			if (isDomainBlocked(urlDomain)) {
				consentBlockedUrl.value = iframeUrl
				return
			}
		}
		// Consent is satisfied (or not required); clear any previous gate.
		consentBlockedUrl.value = null

		if (jitsiConfig) {
			await createJitsiIframe(jitsiConfig, hideIfBackground);
			return;
		}

		const iframe = document.createElement('iframe');
		iframe.src = iframeUrl;
		iframe.classList.add('iframe-media-source');
		if (hideIfBackground) {
			iframe.classList.add('hide-if-background');
		}
		// Add background and size-tiny classes if in background mode
		if (props.background) {
			iframe.classList.add('background');
			iframe.classList.add('size-tiny');
		}
		// Set iframe permissions and attributes
		iframe.allow =
			'screen-wake-lock *; camera *; microphone *; fullscreen *; display-capture *; encrypted-media *' +
			(autoplay.value ? '; autoplay *' : '');
		iframe.allowFullscreen = true;
		iframe.setAttribute('allowusermedia', 'true');
		iframe.setAttribute('allowfullscreen', ''); // iframe.allowfullscreen is not enough in firefox
		// Set referrerpolicy for YouTube embed compatibility (fixes Error 153)
		// https://developers.google.com/youtube/terms/required-minimum-functionality#embedded-player-api-client-identity
		if (isYouTube) {
			iframe.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
			iframe.id = `youtube-player-${Date.now()}`;
		}
		const container = document.querySelector('#media-source-iframes');
		if (!container) return;
		container.appendChild(iframe);
		iframeEl.value = iframe;

		// Wait for iframe to load before sending postMessage commands
		if (isYouTube) {
			iframe.onload = () => {
				subscribeToYouTubePlayerEvents();
			};
		}
	} catch (error) {
		iframeError.value = error;
	} finally {
		iframeInitInProgress = false;
	}
}

function destroyIframe() {
	if (jitsiApi) {
		const api = jitsiApi;
		jitsiApi = null;
		api.dispose();
	}
	iframeEl.value?.remove();
	iframeEl.value = null;
	languageIframeUrl.value = null;
	disconnectWhepTranslation();
	consentBlockedUrl.value = null;
}

function createJitsiIframe(config, hideIfBackground) {
	const container = document.querySelector('#media-source-iframes');
	if (!container) return;
	return createJitsiApiIframe(config, hideIfBackground, container);
}

async function createJitsiApiIframe(config, hideIfBackground, container) {
	const JitsiMeetExternalAPI = await loadJitsiExternalApi(config);
	if (isUnmounted.value) return;

	jitsiApi = new JitsiMeetExternalAPI(config.domain, {
		roomName: config.roomName,
		parentNode: container,
		jwt: config.jwt,
		noSSL: config.protocol === 'http',
		configOverwrite: config.configOverwrite,
		interfaceConfigOverwrite: config.interfaceConfigOverwrite,
		userInfo: config.userInfo,
	});

	const iframe = jitsiApi.getIFrame();
	iframe.classList.add('iframe-media-source');
	iframe.classList.add('jitsi-media-source');
	if (hideIfBackground) {
		iframe.classList.add('hide-if-background');
	}
	if (props.background) {
		iframe.classList.add('background');
		iframe.classList.add('size-tiny');
	}
	iframe.allow =
		'screen-wake-lock *; camera *; microphone *; fullscreen *; display-capture *' +
		(autoplay.value ? '; autoplay *' : '');
	iframe.allowFullscreen = true;
	iframe.setAttribute('allowusermedia', 'true');
	iframe.setAttribute('allowfullscreen', '');
	iframeEl.value = iframe;
	jitsiApi.addListener('videoConferenceJoined', () => applyJitsiDisplayOverrides(config));
	jitsiApi.addListener('videoConferenceLeft', closeJitsiIframe);
	jitsiApi.addListener('readyToClose', closeJitsiIframe);
}

function closeJitsiIframe() {
	destroyIframe();
	emit('close');
	router.push({ name: 'about' }).catch(() => {});
}

function applyJitsiDisplayOverrides(config) {
	if (!jitsiApi) return;
	const commands = {};
	if (config.roomDisplayName) {
		commands.subject = [config.roomDisplayName];
		commands.localSubject = [config.roomDisplayName];
	}
	if (!Object.keys(commands).length) return;
	try {
		jitsiApi.executeCommands(commands);
	} catch (error) {
		console.warn('Failed to apply Jitsi display overrides', {
			roomId: props.room?.id,
			error,
		});
	}
}

function loadJitsiExternalApi(config) {
	const url = new URL(config.url || `https://${config.domain}`);
	url.pathname = '/external_api.js';
	url.search = '';
	url.hash = '';
	const scriptUrl = url.toString();
	if (window.JitsiMeetExternalAPI) {
		return Promise.resolve(window.JitsiMeetExternalAPI);
	}
	if (jitsiExternalApiLoaders.has(scriptUrl)) {
		return jitsiExternalApiLoaders.get(scriptUrl);
	}
	const loader = new Promise((resolve, reject) => {
		const script = document.createElement('script');
		script.src = scriptUrl;
		script.async = true;
		const rejectAndForget = (error) => {
			jitsiExternalApiLoaders.delete(scriptUrl);
			reject(error);
		};
		script.onload = () => {
			if (window.JitsiMeetExternalAPI) {
				resolve(window.JitsiMeetExternalAPI);
			} else {
				rejectAndForget(new Error('Jitsi external API did not load'));
			}
		};
		script.onerror = () => rejectAndForget(new Error('Jitsi external API could not be loaded'));
		document.head.appendChild(script);
	});
	jitsiExternalApiLoaders.set(scriptUrl, loader);
	return loader;
}

function encodeJitsiHash(prefix, values) {
	return Object.entries(values || {})
		.filter(([, value]) => value !== undefined && value !== null)
		.map(([key, value]) => `${prefix}.${key}=${encodeURIComponent(JSON.stringify(value))}`);
}

function getJitsiRoomUrl(config) {
	const url = new URL(config.url || `https://${config.domain}`);
	url.pathname = `/${encodeURIComponent(config.roomName)}`;
	if (config.jwt) {
		url.searchParams.set('jwt', config.jwt);
	}
	const hash = [
		...encodeJitsiHash('config', config.configOverwrite),
		...encodeJitsiHash('interfaceConfig', config.interfaceConfigOverwrite),
		...encodeJitsiHash('userInfo', config.userInfo),
	];
	if (hash.length) {
		url.hash = hash.join('&');
	}
	return url.toString();
}

function onConsentGiven(persistent) {
	if (persistent) {
		// Store commit runs first; unblockedIframeDomains watcher clears the gate and
		// calls initializeIframe once. Calling it here too can race with overlapping async inits.
		return
	}
	consentBlockedUrl.value = null
	initializeIframe(false, true)
}

function isPlaying() {
	if (props.call) {
		return janus.value?.roomId;
	}
	if (shouldUseLivestream.value) {
		return livestream.value?.playing && !livestream.value?.offline;
	}
	if (module.value?.type === 'call.janus') {
		return janus.value?.roomId;
	}
	// For every iframe-based module (BBB, Zoom, YouTube, Vimeo, custom iframe):
	// the room is "playing" only when the iframe element actually exists.
	// This correctly returns false when consent is pending (no iframe yet),
	// preventing App.vue from activating the miniplayer.
	return !!iframeEl.value;
}

function getYoutubeUrl(
	ytid,
	autoplayVal,
	mute,
	hideControls,
	noRelated,
	showinfo,
	disableKb,
	loop,
	modestBranding,
	enablePrivacyEnhancedMode
) {
	const params = new URLSearchParams();

	// Always add autoplay and mute as they control core functionality
	params.append('autoplay', autoplayVal ? '1' : '0');
	params.append('mute', mute ? '1' : '0');

	// Enable IFrame API for programmatic control
	params.append('enablejsapi', '1');
	params.append('origin', window.location.origin);

	// Only add optional parameters when explicitly enabled
	if (hideControls) {
		params.append('controls', '0');
	}

	if (noRelated) {
		params.append('rel', '0');
	}

	if (showinfo) {
		params.append('showinfo', '0');
	}

	if (disableKb) {
		params.append('disablekb', '1');
	}

	if (loop) {
		params.append('loop', '1');
		// Loop requires playlist parameter to work properly
		params.append('playlist', ytid);
	}

	if (modestBranding) {
		params.append('modestbranding', '1');
	}

	const domain = enablePrivacyEnhancedMode
		? 'www.youtube-nocookie.com'
		: 'www.youtube.com';
	return `https://${domain}/embed/${ytid}?${params}`;
}

function getLanguageIframeUrl(languageUrl) {
	if (!languageUrl) return null;
	const config = getYoutubeConfig();
	const origin = window.location.origin;
	const params = new URLSearchParams();
	params.append('autoplay', autoplay.value ? '1' : '0');
	params.append('mute', config.startMuted ? '1' : '0');
	params.append('enablejsapi', '1');
	params.append('origin', origin);
	params.append('controls', '0');

	if (config.noRelated) {
		params.append('rel', '0');
	}
	if (config.showInfo) {
		params.append('showinfo', '0');
	}
	if (config.disableKb) {
		params.append('disablekb', '1');
	}
	if (config.loop) {
		params.append('loop', '1');
		params.append('playlist', languageUrl);
	}
	if (config.modestBranding) {
		params.append('modestbranding', '1');
	}

	const domain = config.enablePrivacyEnhancedMode
		? 'www.youtube-nocookie.com'
		: 'www.youtube.com';
	return `https://${domain}/embed/${languageUrl}?${params}`;
}

// Expose instance methods (used by parents via template refs)
defineExpose({ isPlaying });
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
		top: 51px
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
.c-media-source .c-livestream, .c-media-source .c-januscall, .c-media-source .c-januschannelcall, .c-media-source .iframe-error, iframe.iframe-media-source
	position: fixed
	transition: all .3s ease
	&.size-tiny, &.background
		bottom: calc(var(--vh100) - 48px - 51px)
		right: 4px + 36px + 4px
		+below('l')
			bottom: calc(var(--vh100) - 48px - 48px - 3px)
	&:not(.size-tiny):not(.background)
		top: var(--mediasource-placeholder-top, 104px)
		left: var(--mediasource-placeholder-left, var(--sidebar-width))
		width: var(--mediasource-placeholder-width, 100vw)
		height: var(--mediasource-placeholder-height, var(--mobile-media-height, 40vh))
iframe.iframe-media-source
	transition: all .3s ease
	border: none
	&.jitsi-media-source
		// Jitsi External API writes inline width/height on the generated iframe.
		// Force it back into the same measured media placeholder used by BBB/Zoom.
		&:not(.size-tiny):not(.background)
			top: var(--mediasource-placeholder-top, 104px) !important
			left: var(--mediasource-placeholder-left, var(--sidebar-width)) !important
			width: var(--mediasource-placeholder-width, 100vw) !important
			height: var(--mediasource-placeholder-height, var(--mobile-media-height, 40vh)) !important
	&.background
		pointer-events: none
		height: 48px !important
		width: 86px !important
		z-index: 101
		&.hide-if-background
			width: 0 !important
			height: 0 !important
.c-media-source .iframe-consent-gate
	position: fixed
	display: flex
	transition: all .3s ease
	z-index: 1
	top: var(--mediasource-placeholder-top, 104px)
	left: var(--mediasource-placeholder-left, var(--sidebar-width))
	width: var(--mediasource-placeholder-width, 100vw)
	height: var(--mediasource-placeholder-height, var(--mobile-media-height, 40vh))
	.c-iframe-blocker
		flex: auto
.c-media-source .iframe-error
	display: flex
	justify-content: center
	align-items: center
	background-color: $clr-blue-grey-200
	z-index: 1
	overflow: hidden
	// Fallbacks prevent the overlay from shrinking to its text when
	// --mediasource-placeholder-* are not yet available.
	&:not(.size-tiny):not(.background)
		width: var(--mediasource-placeholder-width, 100vw)
		height: var(--mediasource-placeholder-height, var(--mobile-media-height, 40vh))
	&.size-tiny, &.background
		width: 86px
		height: 48px
		pointer-events: none
		z-index: 101
	.offline-message
		font-size: 36px
		color: $clr-secondary-text-light
		text-align: center
		padding: 16px
	&.size-tiny, &.background
		.offline-message
			font-size: 14px
			padding: 8px
</style>
