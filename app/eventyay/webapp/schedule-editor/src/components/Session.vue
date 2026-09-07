<template lang="pug">
.c-linear-schedule-session(:style="style", @pointerdown.stop="onPointerDown", :class="classes")
	.time-box
		.start(:class="{'has-ampm': startTime?.ampm}", v-if="startTime")
			.time {{ startTime.time }}
			.ampm(v-if="startTime.ampm") {{ startTime.ampm }}
		.duration {{ durationPretty }}
	.info
		.title-row(style="display: flex; justify-content: space-between; align-items: flex-start;")
			.title(:class="{'title-clamped': isShortSession}") {{ getLocalizedString(session.title) }}
		.speakers(v-if="hasSpeakersWithNames", :class="{'speakers-clamped': isShortSession}") {{ speakerNames }}
		.pending-line(v-if="session.state === 'pending'")
			i.fa.fa-exclamation-circle
			span {{ $t('Pending proposal state') }}
		.bottom-info(v-if="!isBreak && (session.track || session.do_not_record)")
			.track(v-if="session.track") {{ getLocalizedString(session.track.name) }}
			.do_not_record.no-print(v-if="session.do_not_record", :title="$t('This session will not be recorded.')", :aria-label="$t('This session will not be recorded.')")
				svg(viewBox="0 0 116.59076 116.59076", width="24px", height="24px", fill="none", xmlns="http://www.w3.org/2000/svg", aria-hidden="true")
					g(transform="translate(-9.3465481,-5.441411)")
						rect(style="fill:#000000;fill-opacity;stroke:none;stroke-width:11.2589;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", width="52.753284", height="39.619537", x="35.496307", y="43.927021", rx="5.5179553", ry="7.573648")
						path(style="fill:#000000;fill-opacity:1;stroke:none;stroke-width:18.7997;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", d="M 99.787546,47.04792 V 80.425654 L 77.727407,63.736793 Z")
						path(style="fill:none;stroke:#b23e65;stroke-width:12;stroke-linecap:round;stroke-dasharray:none;stroke-opacity:1;paint-order:markers stroke fill", d="m 35.553146,95.825578 64.177559,-64.17757 m 16.294055,32.08879 A 48.382828,48.382828 0 0 1 67.641925,112.11961 48.382828,48.382828 0 0 1 19.259099,63.736798 48.382828,48.382828 0 0 1 67.641925,15.353968 48.382828,48.382828 0 0 1 116.02476,63.736798 Z")
	.warning.no-print(v-if="warnings?.length")
		.warning-icon.text-danger
			span(v-if="warnings.length > 1") {{ warnings.length }}
			i.fa.fa-exclamation-triangle
</template>

<script lang="ts" setup>
import { computed } from 'vue'
import moment, { Moment } from 'moment-timezone'
import { translate } from '~/lib/i18n'
import { getLocalizedString } from '~/utils'
import { resolveMode, resolveSessionKind } from '~/teamshifts-adapter'

interface Speaker {
  name: string
  code?: string
  [key: string]: string | undefined
}

interface Track {
  name: string | Record<string, string>
  color?: string
  id?: number | string
  [key: string]: string | number | Record<string, string> | undefined
}

interface Session {
  id: number | string
  title: string | Record<string, string>
  speakers?: Speaker[]
  state?: string
  track?: Track
  start?: Moment
  end?: Moment
  code?: string | null
  duration: number
  abstract?: string
  room?: string | number
  do_not_record?: boolean
  [key: string]: string | number | boolean | Record<string, string> | Speaker[] | Track | Moment | null | undefined
}

interface Warning {
  message: string
  type?: string
  [key: string]: string | undefined
}

const props = defineProps<{
  session: Session
  warnings?: Warning[]
  isDragged?: boolean
  isDragClone?: boolean
  overrideStart?: Moment | null
}>()

const emit = defineEmits<{
  (e: 'startDragging', payload: { session: Session; event: PointerEvent }): void
  (e: 'editSession', payload: Session): void
  (e: 'deleteSession', payload: Session): void
}>()

const mode = resolveMode()
const isBreak = computed(() => resolveSessionKind(mode, props.session) === 'break')

const hasSpeakersWithNames = computed(() => {
  return props.session.speakers && props.session.speakers.some(speaker => speaker.name)
})

const speakerNames = computed(() => {
  if (!props.session.speakers) return ''
  return props.session.speakers
    .filter(speaker => speaker.name)
    .map(speaker => speaker.name)
    .join(', ')
})

const classes = computed(() => {
  const cls: string[] = []

  if (isBreak.value) {
    cls.push('isbreak')
  } else {
    cls.push('istalk')

    if (props.session.state === 'pending') {
      cls.push('pending')
    } else if (
      props.session.state &&
      props.session.state !== 'confirmed' &&
      props.session.state !== 'accepted'
    ) {
      cls.push('unconfirmed')
    } else if (props.session.state !== 'confirmed') {
      cls.push('unconfirmed')
    }
  }

  if (props.isDragged) cls.push('dragging')
  if (props.isDragClone) cls.push('clone')
  if (isShortSession.value) cls.push('short-session')

  return cls
})

const style = computed(() => {
  const trackColor = props.session.track?.color || 'var(--color-primary)'
  return { '--track-color': trackColor }
})

const startTime = computed<{ time: string; ampm?: string } | undefined>(() => {
  const time: Moment | undefined = props.overrideStart || props.session.start
  if (!time) return undefined

  if (moment.localeData().longDateFormat('LT').endsWith(' A')) {
    return {
      time: time.format('h:mm'),
      ampm: time.format('A'),
    }
  } else {
    return { time: time.format('LT') }
  }
})

const durationMinutes = computed<number>(() => {
  if (!props.session.start || !props.session.end) return props.session.duration
  return moment(props.session.end).diff(props.session.start, 'minutes')
})

const isShortSession = computed<boolean>(() => {
  const minutes = durationMinutes.value
  return minutes > 0 && minutes <= 15
})

const durationPretty = computed<string | undefined>(() => {
  const minutes = durationMinutes.value
  if (!minutes) return undefined
  const minLabel = translate('min')
  const hourLabel = translate('h')

  if (minutes <= 60) {
    return `${minutes}${minLabel}`
  }
  const hours = Math.floor(minutes / 60)
  const leftoverMinutes = minutes % 60
  if (leftoverMinutes) {
    return `${hours}${hourLabel}${leftoverMinutes}${minLabel}`
  }
  return `${hours}${hourLabel}`
})

function onPointerDown(event: PointerEvent): void {
  if (!event.isPrimary || event.button !== 0) return
  const el = event.target as HTMLElement
  if (el && el.releasePointerCapture) {
    try { el.releasePointerCapture(event.pointerId) } catch (_) {}
  }
  emit('startDragging', { session: props.session, event })
}
</script>

<style lang="stylus">
sessionTextClamp(lines)
	min-width: 0
	display: -webkit-box
	-webkit-line-clamp: lines
	line-clamp: lines
	-webkit-box-orient: vertical
	overflow: hidden
	overflow-wrap: break-word
	overflow-wrap: anywhere
	word-break: break-word
	text-overflow: ellipsis

sessionTextExpand()
	display: block
	-webkit-line-clamp: unset
	line-clamp: unset
	-webkit-box-orient: unset
	overflow: hidden
	white-space: normal
	overflow-wrap: break-word
	overflow-wrap: anywhere
	word-break: break-word
	text-overflow: clip

.c-linear-schedule-session
	display: flex
	min-width: 300px
	min-height: 96px
	margin: 8px
	overflow: hidden
	color: $clr-primary-text-light
	position: relative
	cursor: pointer
	touch-action: none
	@media (max-width: 767px)
		min-width: 250px
	&.clone
		z-index: 200
	&.dragging
		filter: opacity(0.3)
		cursor: inherit
	&.isbreak
		background-color: $clr-grey-200
		border-radius: 6px
		.time-box
			background-color: $clr-grey-500
			.start
				color: $clr-primary-text-dark
			.duration
				color: $clr-secondary-text-dark
		.info
			justify-content: center
			align-items: center
			.title
				font-size: 20px
				color: $clr-secondary-text-light
				align: center
	&.istalk
		.time-box
			background-color: var(--track-color)
			.start
				color: $clr-primary-text-dark
			.duration
				color: $clr-secondary-text-dark
		.info
			border: 1px solid $clr-dividers-light
			border-left: none
			border-radius: 0 6px 6px 0
			background-color: $clr-white
			.title
				font-size: 16px
				margin-bottom: 4px
		&:hover
			.info
				border: 1px solid var(--track-color)
				border-left: none
				.title
					color: var(--color-primary)
	&.pending, &.unconfirmed
		.time-box
			opacity: 0.5
		.info
			background-image: repeating-linear-gradient(-38deg, $clr-grey-100, $clr-grey-100 10px, $clr-white 10px, $clr-white 20px)
		&:hover
			.info
				border: 1px solid var(--track-color)
				border-left: none
				.title
					color: var(--color-primary)
	&.pending
		.info
			border-style: dashed dashed dashed none
	.time-box
		width: 69px
		box-sizing: border-box
		padding: 12px 16px 8px 12px
		border-radius: 6px 0 0 6px
		display: flex
		flex-direction: column
		align-items: center
		.start
			font-size: 16px
			font-weight: 600
			margin-bottom: 8px
			display: flex
			flex-direction: column
			align-items: flex-end
			&.has-ampm
				align-self: stretch
			.ampm
				font-weight: 400
				font-size: 13px
	.info
		flex: auto
		display: flex
		flex-direction: column
		padding: 8px
		min-width: 0
		.title
			font-weight: 500
			&.title-clamped
				sessionTextClamp(2)
		.speakers
			color: $clr-secondary-text-light
			&.speakers-clamped
				sessionTextClamp(1)
		.bottom-info
			flex: auto
			display: flex
			align-items: flex-end
			gap: 4px
			min-width: 0
			.track
				flex: 1
				min-width: 0
				color: var(--track-color)
				ellipsis()
			.do_not_record
				flex: none
				display: flex
				align-items: center
				line-height: 0
	.pending-line
		color: $clr-warning
		.fa
			margin-right: 4px
	.warning
		position: absolute
		top: 0
		right: 0
		padding: 4px
		margin: 4px
		color: #b23e65
		font-size: 16px
		.warning-icon span
			padding-right: 4px

	@media (hover: hover) and (pointer: fine)
		&:hover:not(.dragging, .clone)
			.title.title-clamped, .speakers.speakers-clamped
				sessionTextExpand()

@media print
	.c-linear-schedule-session.isbreak
		border: 2px solid $clr-grey-300 !important
	.c-linear-schedule-session.istalk .time-box
		border: 2px solid var(--track-color) !important
	.c-linear-schedule-session.istalk .info
		border-right: 2px solid var(--track-color) !important
		border-top: 2px solid var(--track-color) !important
		border-bottom: 2px solid var(--track-color) !important
</style>
