<template lang="pug">
.v-standalone-kiosk
	transition(name="kiosk")
		.slide(v-if="activeSlide", :key="activeSlide.id")
			component(:is="activeSlide.component", :room="room")
</template>
<script>
import moment from 'lib/timetravelMoment'
import PollSlide from './Poll'
// import VoteSlide from './Vote'
import QuestionSlide from './Question'
import NextSessionSlide from './NextSession'
import ViewersSlide from './Viewers'

const SLIDES = [{
	id: 'poll',
	condition () {
		return this.config.slides.pinned_poll && !!this.$store.getters['poll/pinnedPoll']
	},
	watch () {
		return this.config.slides.pinned_poll && this.$store.getters['poll/pinnedPoll']
	},
	priority: 10,
	component: PollSlide
// }, {
// 	id: 'vote',
// 	condition () {
// 		return !!this.$store.getters['poll/pinnedPoll']
// 	},
// 	component: VoteSlide
}, {
	id: 'question',
	condition () {
		return this.config.slides.pinned_question && !!this.$store.getters['question/pinnedQuestion']
	},
	watch () {
		return this.config.slides.pinned_question && this.$store.getters['question/pinnedQuestion']
	},
	priority: 10,
	component: QuestionSlide
}, {
	id: 'nextSession',
	condition () {
		if (!this.config.slides.next_session) return false
		const currentSession = this.$store.getters['schedule/currentSessionPerRoom']?.[this.room.id]?.session
		const nextSession = this.$store.getters['schedule/sessions']?.find(session => session.room === this.room && session.start.isAfter(this.now))
		return !!nextSession && (!currentSession || currentSession.end.isBefore(moment().add(10, 'minutes')))
	},
	watch () {
		return this.config.slides.next_session && this.$store.getters['schedule/sessions']
	},
	priority: 1,
	component: NextSessionSlide
}, {
	id: 'viewers',
	condition () {
		return this.config.slides.viewers && this.$store.state.roomViewers?.length > 0
	},
	watch () {
		return this.config.slides.viewers && this.$store.state.roomViewers
	},
	priority: 1,
	component: ViewersSlide
}]

const SLIDE_INTERVAL = 2000

export default {
	props: {
		room: Object,
		config: Object
	},
	data () {
		return {
			activeSlide: SLIDES[0],
		}
	},
	mounted () {
		this.nextSlide()
		for (const slide of SLIDES) {
			if (slide.watch) {
				this.$watch(slide.watch.bind(this), () => {
					if (slide.condition.call(this)) {
						this.activeSlide = slide
					} else {
						this.nextSlide()
					}
				})
			}
		}
	},
	methods: {
		nextSlide () {
			if (this.slideTimer) clearTimeout(this.slideTimer)
			let index = SLIDES.indexOf(this.activeSlide)
			const stoppingIndex = Math.max(0, index)
			let nextSlide
			do {
				index++
				if (index >= SLIDES.length) index = 0
				const slide = SLIDES[index]
				if (
					slide.priority > (nextSlide?.priority ?? 0) &&
					slide.condition.call(this)
				) nextSlide = SLIDES[index]
			} while (index !== stoppingIndex)
			this.activeSlide = nextSlide
			this.slideTimer = setTimeout(this.nextSlide.bind(this), SLIDE_INTERVAL)
		}
	}
}
</script>
<style lang="stylus">
.v-standalone-kiosk
	display: flex
	flex-direction: column
	justify-content: center
	align-items: center
	height: 100%
	width: 100%
	position: relative
	> .slide
		position: absolute
		&.kiosk-enter-active, &.kiosk-leave-active
			transition: translate 1s
		&.kiosk-enter
			translate: -100vw 0
		&.kiosk-leave-to
			translate: 100vw 0
</style>
