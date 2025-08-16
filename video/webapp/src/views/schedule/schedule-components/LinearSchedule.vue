<template lang="pug">
.c-linear-schedule(v-scrollbar.y="")
	.bucket(v-for="({date, sessions}, index) of sessionBuckets")
		.bucket-label(:ref="getBucketName(date)", :data-date="date.format()")
			.day(v-if="index === 0 || date.clone().startOf('day').diff(sessionBuckets[index - 1].date.clone().startOf('day'), 'day') > 0")  {{ date.format('dddd DD. MMMM') }}
			.time {{ date.format('LT') }}
			template(v-for="session of sessions")
				session(
					v-if="isProperSession(session)",
					:session="session",
					:faved="session.id && favs.includes(session.id)",
					@fav="$emit('fav', session.id)",
					@unfav="$emit('unfav', session.id)",
					isLinearSchedule=true
				)
				.break(v-else)
					.title {{ getLocalizedString(session.title) }}
</template>
<script>
import moment from 'moment-timezone'
import { getLocalizedString } from 'views/schedule/utils'
import Session from './Session'

export default {
	components: { Session },
	emits: ['fav', 'unfav', 'changeDay'],
	props: {
		sessions: Array,
		rooms: Array,
		favs: {
			type: Array,
			default() {
				return []
			}
		},
		currentDay: Object,
		now: Object,
		scrollParent: Element,
		sortBy: String,
	},
	data() {
		return {
			moment,
			getLocalizedString,
			scrolledDay: null
		}
	},
	computed: {
		sessionBuckets() {
			const buckets = {}
			for (const session of this.sessions) {
				const key = session.start.format()
				if (!buckets[key]) {
					buckets[key] = []
				}
				if (!session.id) {
					// Remove duplicate breaks, meaning same start, end and text
					session.break_id = `${session.start}${session.end}${session.title}`
					if (buckets[key].filter(s => s.break_id === session.break_id).length === 0) buckets[key].push(session)
				} else {
					buckets[key].push(session)
				}
			}

			return Object.entries(buckets).map(([date, sessions]) => {
				let sessionBucket = {}
				switch (this.sortBy) {
					case 'title':
						sessionBucket = {
							date: sessions[0].start,
							// sort by room for stable sort across time buckets
							sessions: sessions.sort((a, b) => {
								return a.title.localeCompare(b.title)
							})
						}
						break
					case 'popularity':
						sessionBucket = {
							date: sessions[0].start,
							// sort by room for stable sort across time buckets
							sessions: sessions.sort((a, b) => {
								return b.fav_count - a.fav_count
							})
						}
						break
					default:
						sessionBucket = {
							date: sessions[0].start,
							// sort by room for stable sort across time buckets
							sessions: sessions.sort((a, b) => this.rooms.findIndex(room => room.id === a.room.id) - this.rooms.findIndex(room => room.id === b.room.id))
						}
				}

				return sessionBucket
			})
		}
	},
	watch: {
		currentDay: 'changeDay'
	},
	async mounted() {
		await this.$nextTick()
		this.observer = new IntersectionObserver(this.onIntersect, {
			root: this.scrollParent,
			rootMargin: '-45% 0px'
		})
		let lastBucket
		for (const [ref, el] of Object.entries(this.$refs)) {
			if (!ref.startsWith('bucket')) continue
			const date = moment.parseZone(el[0].dataset.date)
			if (lastBucket) {
				if (lastBucket.isSame(date, 'date')) continue
			}
			lastBucket = date
			this.observer.observe(el[0])
		}
		// scroll to now
		// scroll to now, unless URL overrides now
		let fragmentIsDate = false
		const fragment = window.location.hash.slice(1)
		if (fragment && fragment.length === 10) {
			const initialDay = moment(fragment, 'YYYY-MM-DD')
			if (initialDay) {
				fragmentIsDate = true
			}
		}
		if (fragmentIsDate) return
		const nowIndex = this.sessionBuckets.findIndex(bucket => this.now.isBefore(bucket.date))
		const beforeIndex = this.sessionBuckets.findIndex(bucket => this.now.isBefore(bucket.date))
		// do not scroll if the event has not started yet
		if ((nowIndex < 0) || (beforeIndex === 0)) return
		const nowBucket = this.sessionBuckets[Math.max(0, nowIndex - 1)]
		const scrollTop = this.$refs[this.getBucketName(nowBucket.date)]?.[0]?.offsetTop - 90
		if (this.scrollParent && typeof this.scrollParent.scrollTo === 'function') {
			this.scrollParent.scrollTo({ top: scrollTop })
		} else {
			window.scroll({top: scrollTop + this.getOffsetTop()})
		}
	},
	methods: {
		isProperSession(session) {
			// breaks and such don't have ids
			return !!session.id
		},
		getBucketName(date) {
			return `bucket-${date.format('YYYY-MM-DD-HH-mm')}`
		},
		getOffsetTop() {
			const rect = this.$parent.$el.getBoundingClientRect()
			return rect.top + window.scrollY
		},
		changeDay(day) {
			if (this.scrolledDay === day) return
			const dayBucket = this.sessionBuckets.find(bucket => day.isSame(bucket.date, 'day'))
			if (!dayBucket) return
			const el = this.$refs[this.getBucketName(dayBucket.date)]?.[0]
			if (!el) return
			const scrollTop = el.offsetTop + this.getOffsetTop() - 8
			if (this.scrollParent && typeof this.scrollParent.scrollTo === 'function') {
				this.scrollParent.scrollTo({ top: scrollTop })
			} else {
				window.scroll({top: scrollTop})
			}
		},
		onIntersect(results) {
			const intersection = results[0]
			const day = moment.parseZone(intersection.target.dataset.date).startOf('day')
			if (intersection.isIntersecting) {
				this.scrolledDay = day
				this.$emit('changeDay', this.scrolledDay)
			} else if (intersection.rootBounds && (intersection.boundingClientRect.y - intersection.rootBounds.y) > 0) {
				this.scrolledDay = day.subtract(1, 'day')
				this.$emit('changeDay', this.scrolledDay)
			}
		}
	}
}
</script>
<style lang="stylus">
.c-linear-schedule
	display: flex
	flex-direction: column
	min-height: 0
	.bucket
		padding-top: 8px
		.bucket-label
			font-size: 14px
			font-weight: 500
			color: $clr-secondary-text-light
			padding-left: 16px
			.day
				font-weight: 600
		.break
			z-index: 10
			margin: 8px
			padding: 8px
			border-radius: 4px
			background-color: $clr-grey-200
			display: flex
			justify-content: center
			align-items: center
			.title
				font-size: 20px
				font-weight: 500
				color: $clr-secondary-text-light
</style>
