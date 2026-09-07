<template lang="pug">
.c-admin-kiosk
	.error(v-if="error") {{ $t('We could not fetch the current configuration.') }}
	template(v-else-if="kiosk")
		.ui-page-header
			bunt-icon-button(@click="$router.push({name: 'admin:kiosks:index'})", :tooltip="$t('Back to Kiosks')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
			h1 {{ kiosk.profile.display_name }}
			.actions
				bunt-button.btn-delete-kiosk(@click="showDeletePrompt = true") delete
		.scroll-wrapper(v-scrollbar.y="")
			.ui-form-body
				copyable-text(
					:url="loginUrl",
					:label="$t('Kiosk Login URL')",
					:hint="$t('Open this link to display the kiosk or copy it to configure your device.')",
					:show-launch="true",
					:launch-label="$t('Launch')",
					:is-card="true"
				)
				bunt-input(name="name", v-model="kiosk.profile.display_name", :label="$t('Name')", :validation="v$.kiosk.profile.display_name")
				bunt-select(v-model="kiosk.profile.room_id", :label="$t('Room')", name="room", :options="rooms", option-label="name", :validation="v$.kiosk.profile.room_id")
				bunt-switch(name="show_reactions", v-model="kiosk.profile.show_reactions", :label="$t('Show reaction cloud')")
				h2 {{ $t('Slides') }}
				p {{ $t('Choose which panels appear on the kiosk. Multiple items are shown together; pin a poll or question to take over the full screen (unpin to return). If only one item has content, it is shown full screen automatically.') }}
				bunt-checkbox(name="show_pinned_poll", :model-value="!!kiosk.profile.slides.pinned_poll", @update:model-value="setSlide('pinned_poll', $event)", :label="$t('Poll')")
				bunt-checkbox(name="show_pinned_question", :model-value="!!kiosk.profile.slides.pinned_question", @update:model-value="setSlide('pinned_question', $event)", :label="$t('Question')")
				bunt-checkbox(name="show_next_session", :model-value="!!kiosk.profile.slides.next_session", @update:model-value="setSlide('next_session', $event)", :label="$t('Next session')")
				bunt-checkbox(name="show_viewers", :model-value="!!kiosk.profile.slides.viewers", @update:model-value="setSlide('viewers', $event)", :label="$t('Active viewers')")
		.ui-form-actions
			bunt-button.btn-save(@click="save", :loading="saving", :error-message="saveError") {{ $t('Save') }}
			.errors {{ validationErrors.join(', ') }}
	bunt-progress-circular(v-else, size="huge")
	transition(name="prompt")
		prompt.delete-prompt(v-if="showDeletePrompt", @close="showDeletePrompt = false")
			.content
				.prompt-header
					h3 {{ $t('Are you ABSOLUTELY sure?') }}
				p {{ $t('This action CANNOT be undone. This will permanently delete the kiosk') }}
				.kiosk-name {{ kiosk.profile.display_name }}
				p {{ $t('Please type in the name of the kiosk to confirm.') }}
				bunt-input(name="deletingKioskName", :label="$t('Kiosk name')", v-model="deletingKioskName", @keypress.enter="deleteKiosk")
				bunt-button.delete-kiosk(icon="delete", :disabled="deletingKioskName !== kiosk.profile.display_name", @click="deleteKiosk", :loading="deleting", :error-message="deleteError") {{ $t('delete this kiosk') }}
</template>
<script>
import { useVuelidate } from '@vuelidate/core'
import api from 'lib/api'
import { required } from 'lib/validators'
import { inferRoomType } from 'lib/room-types'
import CopyableText from 'components/CopyableText'
import Prompt from 'components/Prompt'
import ValidationErrorsMixin from 'components/mixins/validation-errors'

export default {
	name: 'AdminKiosk',
	components: { CopyableText, Prompt },
	mixins: [ValidationErrorsMixin],
	props: {
		kioskId: String
	},
	setup:() => ({v$:useVuelidate()}),
	data() {
		return {
			error: null,
			kiosk: null,
			saving: false,
			saveError: null,
			showDeletePrompt: false,
			deletingKioskName: '',
			deleting: false,
			deleteError: null
		}
	},
	computed: {
		rooms() {
			return this.$store.state.rooms.filter(room => inferRoomType(room)?.id === 'stage')
		},
		loginUrl() {
			return `${window.location.origin}/login/${this.kiosk.token}`
		}
	},
	validations() {
		return {
			kiosk: {
				profile: {
					display_name: {
						required: required(this.$t('Name is required'))
					},
					room_id: {
						required: required(this.$t('Room is required'))
					}
				}
			}
		}
	},
	watch: {
		kioskId: {
			async handler() {
				try {
					this.kiosk = await api.call('user.kiosk.fetch', {id: this.kioskId})
					if (this.kiosk?.profile?.show_reactions == null && this.kiosk?.profile) this.kiosk.profile.show_reactions = true
					if (!this.kiosk?.profile?.slides || typeof this.kiosk.profile.slides !== 'object') {
						if (this.kiosk?.profile) {
							this.kiosk.profile.slides = {
								pinned_poll: true,
								pinned_question: true,
								next_session: true,
								viewers: false
							}
						}
					}
				} catch (error) {
					this.error = error
					console.error(error)
				}
			}
		}
	},
	async created() {
		try {
			this.kiosk = await api.call('user.kiosk.fetch', {id: this.kioskId})
			if (this.kiosk.profile.show_reactions == null) this.kiosk.profile.show_reactions = true
			if (!this.kiosk.profile.slides || typeof this.kiosk.profile.slides !== 'object') {
				// Never configured: classic panels on, viewers opt-in.
				this.kiosk.profile.slides = {
					pinned_poll: true,
					pinned_question: true,
					next_session: true,
					viewers: false
				}
			} else {
				const slides = this.kiosk.profile.slides
				// Keep unchecked boxes as false (not undefined) so Save persists correctly.
				this.kiosk.profile.slides = {
					pinned_poll: slides.pinned_poll === true,
					pinned_question: slides.pinned_question === true,
					next_session: slides.next_session === true,
					viewers: slides.viewers === true
				}
			}
		} catch (error) {
			this.error = error
			console.error(error)
		}
	},
	methods: {
		setSlide(key, value) {
			if (!this.kiosk?.profile) return
			if (!this.kiosk.profile.slides || typeof this.kiosk.profile.slides !== 'object') {
				this.kiosk.profile.slides = {
					pinned_poll: false,
					pinned_question: false,
					next_session: false,
					viewers: false
				}
			}
			this.kiosk.profile.slides = {
				...this.kiosk.profile.slides,
				[key]: value === true
			}
		},
		async save() {
			this.saveError = null
			this.v$.$touch()
			if (this.v$.$invalid) return
			this.saving = true
			try {
				if (!this.kiosk.profile.slides) this.kiosk.profile.slides = {}
				const slides = this.kiosk.profile.slides
				this.kiosk.profile.slides = {
					pinned_poll: slides.pinned_poll === true,
					pinned_question: slides.pinned_question === true,
					next_session: slides.next_session === true,
					viewers: slides.viewers === true
				}
				await api.call('user.kiosk.update', {
					id: this.kiosk.id,
					profile: this.kiosk.profile
				})
			} catch (e) {
				this.saveError = e.message
			} finally {
				this.saving = false
			}
		},
		async deleteKiosk() {
			if (this.deletingKioskName !== this.kiosk.profile.display_name) return
			this.deleting = true
			this.deleteError = null
			try {
				await api.call('user.delete', {id: this.kiosk.id})
				this.$router.replace({name: 'admin:kiosks:index'})
			} catch (error) {
				this.deleteError = error?.message || this.$t('Something went wrong.')
			}
			this.deleting = false
		},
		async copyUrl() {
			await navigator.clipboard.writeText(this.loginUrl)
			this.copied = true
			setTimeout(() => {
				this.copied = false
			}, 2500)
		}
	}
}
</script>
<style lang="stylus">
.c-admin-kiosk
	display: flex
	flex-direction: column
	background: $clr-white
	min-height: 0
	min-width: 0
	.bunt-icon-button
		icon-button-style(style: clear)
	.ui-page-header
		background-color: $clr-grey-100
		.bunt-icon-button
			margin-right: 8px
		h1
			flex: auto
			font-size: 24px
			font-weight: 500
			margin: 1px 16px 0 0
			ellipsis()
		.actions
			display: flex
			flex: none
			.bunt-button:not(:last-child)
				margin-right: 16px
			.btn-delete-kiosk
				button-style(color: $clr-danger)
	.scroll-wrapper
		flex: auto
		display: flex
		flex-direction: column
		height: 83vh

	.ui-form-body
		.bunt-checkbox
			margin-bottom: 8px

	.delete-prompt
		.content
			display: flex
			flex-direction: column
			padding: 16px
		.question-box-header
			margin-top: -10px
			margin-bottom: 15px
			align-items: center
			display: flex
			justify-content: space-between
		.kiosk-name
			font-family: monospace
			font-size: 16px
			border: border-separator()
			border-radius: 4px
			padding: 4px 8px
			background-color: $clr-grey-100
			align-self: center
		.delete-kiosk
			button-style(color: $clr-danger)
</style>
