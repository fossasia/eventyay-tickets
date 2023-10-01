<template lang="pug">
.c-standalone-anonymous
	AppBar(:showActions="false", :showUser="true")
	.content-wrapper
		h2.room
			| {{ $t('standalone/Anonymous:header_room') }}:&nbsp;
			span.room-name(v-html="$emojify(room.name)")
		.session(v-if="session")
			.title {{ $localize(session.title) }}
			.speakers {{ session.speakers ? session.speakers.map(s => s.name).join(', ') : '' }}
		.room-content(v-if="modules['question'] || modules['poll']", :class="unreadTabsClasses")
			bunt-tabs(v-if="(!!modules['question'] + !!modules['poll']) > 1 && activeSidebarTab", :active-tab="activeSidebarTab")
				bunt-tab(v-if="modules['poll']", id="polls", :header="$t('Room:sidebar:tabs-header:polls')", @selected="activeSidebarTab = 'polls'")
				bunt-tab(v-if="modules['question']", id="questions", :header="$t('Room:sidebar:tabs-header:questions')", @selected="activeSidebarTab = 'questions'")
				bunt-tab(v-if="sessions", id="schedule", :header="$t('standalone/Anonymous:tabs-header:schedule')", @selected="activeSidebarTab = 'schedule'")
			Scrollbars(y="")
				questions(v-if="modules['question']", v-show="activeSidebarTab === 'questions'", :module="modules['question']", @change="changedTabContent('questions')")
				polls(v-if="modules['poll']", v-show="activeSidebarTab === 'polls'", :module="modules['poll']", @change="changedTabContent('polls')")
				.schedule(v-if="activeSidebarTab === 'schedule'")
					template(v-if="session")
						h3 {{ $t('standalone/Anonymous:schedule:current-session') }}
						Session(:session="session")
					template(v-if="nextSessions.length")
						h3 {{ $t('standalone/Anonymous:schedule:next-sessions') }}
						Session(v-for="session of nextSessions", :session="session")
					.no-sessions(v-if="!session && !nextSessions.length") {{ $t('standalone/Anonymous:no-sessions') }}
			.hint(v-if="activeSidebarTab !== 'schedule' && isAnonymous") {{ $t('standalone/Anonymous:footer-anonymously') }}
		.no-content(v-else) {{ $t('standalone/Anonymous:no-content') }}
</template>
<script>
// TODO
// - reactions?
import { mapState, mapGetters } from 'vuex'
import { Session } from '@pretalx/schedule'
import AppBar from 'components/AppBar'
import Polls from 'components/Polls'
import Questions from 'components/Questions'
import Scrollbars from 'components/Scrollbars'

export default {
	components: { AppBar, Polls, Questions, Session, Scrollbars },
	props: {
		room: Object
	},
	data () {
		return {
			activeSidebarTab: null, // chat, questions, polls
			unreadTabs: {
				questions: false,
				polls: false
			},
		}
	},
	computed: {
		...mapState(['now', 'user']),
		...mapGetters('poll', ['pinnedPoll']),
		...mapGetters('schedule', ['sessions', 'currentSessionPerRoom']),
		modules () {
			return this.room?.modules.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		isAnonymous () {
			return Object.keys(this.user.profile).length === 0
		},
		unreadTabsClasses () {
			return Object.entries(this.unreadTabs).filter(([tab, value]) => value).map(([tab]) => `tab-${tab}-unread`)
		},
		session () {
			return this.currentSessionPerRoom?.[this.room.id]?.session
		},
		nextSessions () {
			if (!this.sessions) return
			// current or next sessions per room
			const sessions = []
			for (const session of this.sessions) {
				if (session.room !== this.room || !session.id || session === this.session) continue
				if (session.end.isBefore(this.now) || sessions.reduce((acc, s) => s.room === session.room ? ++acc : acc, 0) >= 3) continue
				sessions.push(session)
			}
			return sessions
		},
	},
	watch: {
		activeSidebarTab (tab) {
			this.unreadTabs[tab] = false
		}
	},
	mounted () {
		if (this.modules.poll) {
			this.activeSidebarTab = 'polls'
		} else if (this.modules.question) {
			this.activeSidebarTab = 'questions'
		}
	},
	methods: {
		changedTabContent (tab) {
			if (tab === this.activeSidebarTab) return
			this.unreadTabs[tab] = true
		}
	}
}
</script>
<style lang="stylus">
.c-standalone-anonymous
	flex: auto
	display: flex
	flex-direction: column
	background-color: $clr-white
	color: $clr-primary-text-light
	min-height: 0
	.content-wrapper
		display: flex
		flex-direction: column
		flex: auto
		width: 100%
		max-width: 960px
		min-height: 0
		align-self: center
	h2.room
		margin: 8px 8px 0 8px
		display: flex
		font-size: 20px
		font-weight: 400
		color: $clr-secondary-text-light
		.room-name
			color: $clr-primary-text-light
			ellipsis()
	.session
		display: flex
		flex-direction: column
		margin: 0 8px 8px 8px
		.title, .speakers
			ellipsis()
		.title
			font-size: 18px
			font-weight: 500
		.speakers
			line-height: 20px
			font-size: 14px
			color: $clr-secondary-text-light
	.room-content
		display: flex
		flex-direction: column
		min-height: 0
		flex: auto
		> .bunt-tabs
			tabs-style(active-color: var(--clr-primary), indicator-color: var(--clr-primary), background-color: transparent)
			margin: 0
			border-bottom: border-separator()
			.bunt-tabs-header-items
				justify-content: center
		for tab in chat questions polls
			&.tab-{tab}-unread [aria-controls=\"{tab}\"] .bunt-tab-header-item-text
				position: relative
				&::after
					content: ''
					position: absolute
					top: -2px
					right: -8px
					display: block
					height: 5px
					width: 5px
					border-radius: 50%
					background-color: $clr-danger
	.schedule
		h3
			font-size: 20px
			font-weight: 500
			margin: 8px
		.c-linear-schedule-session
			pointer-events: none
	.hint
		text-align: center
		color: $clr-secondary-text-light
		margin: 16px
	.no-content, .no-sessions
		text-align: center
		margin: 16px
		font-size: 20px
</style>
