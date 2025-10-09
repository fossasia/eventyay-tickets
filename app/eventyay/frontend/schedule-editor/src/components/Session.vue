<template lang="pug">
.c-linear-schedule-session(:style="style", @pointerdown.stop="onPointerDown", :class="classes")
	.time-box
		.start(:class="{'has-ampm': startTime?.ampm}", v-if="startTime")
			.time {{ startTime.time }}
			.ampm(v-if="startTime.ampm") {{ startTime.ampm }}
		.duration {{ durationPretty }}
	.info
		.title {{ getLocalizedString(session.title) }}
		.speakers(v-if="hasSpeakersWithNames") {{ speakerNames }}
		.pending-line(v-if="session.state && session.state !== 'confirmed' && session.state !== 'accepted'")
			i.fa.fa-exclamation-circle
			span {{ $t('Pending proposal state') }}
		.bottom-info(v-if="!isBreak")
			.track(v-if="session.track") {{ getLocalizedString(session.track.name) }}
	.warning.no-print(v-if="warnings?.length")
		.warning-icon.text-danger
			span(v-if="warnings.length > 1") {{ warnings.length }}
			i.fa.fa-exclamation-triangle
</template>

<script lang="ts" setup>
import { computed } from 'vue'
import moment, { Moment } from 'moment-timezone'
import { getLocalizedString } from '~/utils'

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
}>()

const isBreak = computed(() => !props.session.code)

const hasSpeakersWithNames = computed(() => {
  return props.session.speakers && props.session.speakers.some(speaker => speaker.name)
})

const speakerNames = computed(() => {
  if (!props.session.speakers) return ''
  return props.session.speakers
    .filter(speaker => speaker.name) // Only include speakers with names
    .map(speaker => speaker.name)
    .join(', ')
})

const classes = computed(() => {
  const cls: string[] = []
  if (isBreak.value) {
    cls.push('isbreak')
  } else {
    cls.push('istalk')
    if (
      props.session.state !== 'confirmed' &&
      props.session.state !== 'accepted'
    ) {
      cls.push('pending')
    } else if (props.session.state !== 'confirmed') {
      cls.push('unconfirmed')
    }
  }
  if (props.isDragged) cls.push('dragging')
  if (props.isDragClone) cls.push('clone')
  return cls
})

const style = computed(() => ({
  '--track-color': props.session.track?.color || 'var(--color-primary)'
}))

const startTime = computed< { time: string; ampm?: string } | undefined>(() => {
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

const durationPretty = computed<string | undefined>(() => {
  const minutes = durationMinutes.value
  if (!minutes) return undefined

  if (minutes <= 60) {
    return `${minutes}min`
  }
  const hours = Math.floor(minutes / 60)
  const leftoverMinutes = minutes % 60
  if (leftoverMinutes) {
    return `${hours}h${leftoverMinutes}min`
  }
  return `${hours}h`
})

function onPointerDown(event: PointerEvent): void {
  emit('startDragging', { session: props.session, event })
}
</script>

<style lang="stylus">
.c-linear-schedule-session
	display: flex
	min-width: 300px
	min-height: 96px
	margin: 8px
	overflow: hidden
	color: $clr-primary-text-light
	position: relative
	cursor: pointer
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
			border: border-separator()
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
		.speakers
			color: $clr-secondary-text-light
		.bottom-info
			flex: auto
			display: flex
			align-items: flex-end
			.track
				flex: 1
				color: var(--track-color)
				ellipsis()
				margin-right: 4px
	.pending-line
		color: $clr-warning
		.fa
			margin-right: 4px
	.warning
		position: absolute
		top: 0
		right: 0
		padding: 4px 4px
		margin: 4px
		color: #b23e65
		font-size: 16px
		.warning-icon span
			padding-right: 4px
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
