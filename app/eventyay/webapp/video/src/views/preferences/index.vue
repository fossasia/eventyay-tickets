<template lang="pug">
.v-preferences
	.ui-page-header
		bunt-icon-button.btn-back(@click="onBack", :tooltip="$t('Back to Overview')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h1 {{ $t('Your profile') }}
	scrollbars(y)
		.inputs
			.avatar-wrapper
				avatar(:user="{profile}", :size="128")
				bunt-button#btn-change-avatar(@click="showChangeAvatar = true") {{ $t('change avatar') }}
			bunt-input.display-name(name="displayName", :label="`${$t('Display name')} *`", v-model.trim="profile.display_name", :validation="v$.profile.display_name")
			template(v-if="languages")
				h2 {{ $t('Interface Language') }}
				bunt-select#select-interface-language(name="interface-language", v-model="interfaceLanguage", :options="languages", option-value="code", option-label="nativeLabel")
			h2 {{ $t('Profile Visibility') }}
			p {{ $t('Making your profile public allows other attendees to find you in the networking chat list and see you in room viewer lists. Private profiles are completely hidden.') }}
			bunt-switch#switch-show-publicly(
				name="showPublicly",
				:label="showPublicly ? $t('Public – visible to other attendees') : $t('Private – hidden from attendee lists')",
				:model-value="showPublicly",
				@update:modelValue="toggleVisibility"
			)
			h2 {{ $t('Desktop Notifications') }}
			p {{ $t('Get desktop notifications for direct messages, contact requests and more while the event is running in the background.') }}
			bunt-button#btn-enable-desktop-notifications(v-if="notificationPermission === 'default'", icon="bell", @click="$store.dispatch('notifications/askForPermission')") {{ $t('Enable desktop notifications') }}
			.notification-permission-denied(v-else-if="notificationPermission === 'denied'") {{ $t('Desktop notifications are blocked for this site. Please change the setting in your browser.') }}
			template(v-else)
				bunt-switch(name="notificationSettings.notify", :label="$t('Enable desktop notifications')", v-model="notificationSettings.notify")
				bunt-switch(name="notificationSettings.playSounds", :label="$t('Play a sound for notifications')", v-model="notificationSettings.playSounds")
			h2 {{ $t('Stream Autoplay') }}
			p {{ $t('By default, livestreams start playing automatically when you enter a stage. Disable autoplay when you attend this event physically and want to use stage features without watching the livestream.') }}
			bunt-switch(name="autoplay", v-model="autoplay", :label="$t('Autoplay streams')")
	.ui-form-actions
		bunt-button#btn-save(:disabled="v$.$invalid && v$.$dirty", :loading="saving", @click="save") {{ $t('save') }}
	transition(name="prompt")
		prompt.change-avatar-prompt(v-if="showChangeAvatar", @close="showChangeAvatar = false")
			.content
				change-avatar(ref="avatar", v-model="profile.avatar", :profile="profile", @blockSave="blockSave = $event")
				.actions
					bunt-button#btn-cancel(@click="showChangeAvatar = false") {{ $t('cancel') }}
					bunt-button#btn-upload(:loading="savingAvatar", :disabled="blockSave", @click="uploadAvatar") {{ $t('save') }}
</template>
<script>
// TODO communicate language change to other tabs?
import { mapState } from 'vuex'
import { cloneDeep } from 'lodash'
import { useVuelidate } from '@vuelidate/core'
import config from 'config'
import { resolveLanguageOptions } from 'locales'
import Avatar from 'components/Avatar'
import Prompt from 'components/Prompt'
import ChangeAvatar from 'components/profile/ChangeAvatar'
import { required } from 'lib/validators'

export default {
	components: { Avatar, Prompt, ChangeAvatar },
	setup:() => ({v$: useVuelidate()}),
	data() {
		return {
			profile: null,
			interfaceLanguage: this.$i18n.resolvedLanguage,
			notificationSettings: cloneDeep(this.$store.state.notifications.settings),
			autoplay: true,
			showChangeAvatar: false,
			savingAvatar: false,
			blockSave: false,
			saving: false
		}
	},
	validations() {
		return {
			profile: {
				display_name: {
					required: required(this.$t('Display name cannot be empty'))
				}
			}
		}
	},
	computed: {
		...mapState(['user', 'world']),
		...mapState('notifications', {
			notificationPermission: 'permission'
		}),
		showPublicly() {
			return !!this.$store.state.user?.show_publicly
		},
		languages() {
			const options = resolveLanguageOptions(config.locales)
			return options.length ? options : null
		}
	},
	created() {
		this.profile = Object.assign({}, this.user.profile)
		this.autoplay = this.$store.getters.autoplay
		if (!this.profile.avatar || (!this.profile.avatar.url && !this.profile.avatar.identicon)) {
			this.profile.avatar = {
				identicon: this.user.id
			}
		}
	},
	methods: {
		async toggleVisibility(value) {
			await this.$store.dispatch('setProfileVisibility', value)
		},
		async uploadAvatar() {
			this.savingAvatar = true
			await this.$refs.avatar.update()
			await this.$store.dispatch('updateUser', {profile: Object.assign({}, this.user.profile, {avatar: this.profile.avatar})})
			this.showChangeAvatar = false
			this.savingAvatar = false
		},
		async save() {
			this.v$.$touch()
			if (this.v$.$invalid) return
			this.saving = true
			await this.$store.dispatch('updateUser', {profile: this.profile})
			this.$store.dispatch('notifications/updateSettings', this.notificationSettings)
			this.$store.dispatch('setAutoplay', this.autoplay)
			this.$store.dispatch('schedule/setCurrentLanguage', this.interfaceLanguage)
			try {
				await this.$store.dispatch('updateUserLocale', this.interfaceLanguage)
			} catch (error) {
				console.error(error)
			}
			this.saving = false
		},
		onBack() {
			if (window.history.state && window.history.state.back) {
				this.$router.back()
			} else if (window.eventyay?.isOrganizerArea) {
				this.$router.replace({ name: 'organizer' })
			} else {
				this.$router.replace({ name: 'about' })
			}
		}
	}
}
</script>
<style lang="stylus">
.v-preferences
	background-color: $clr-white
	display: flex
	flex-direction: column
	flex: auto
	min-height: 0
	.scroll-content
		padding: 16px 32px
	h1
		margin: 0
	h2
		font-size: 20px
		font-weight: 500
		border-bottom: border-separator()
	.avatar-wrapper
		display: flex
		align-items: center
		#btn-change-avatar
			themed-button-secondary()
			margin-left: 16px
	.scroll-content .inputs
		width: 420px
		display: flex
		flex-direction: column
		.permission-info
			font-size 13px
			line-height 18px
			padding 6px 0px 6px 16px
			color: $clr-red
	#btn-enable-desktop-notifications
		themed-button-secondary()
	.notification-permission-denied
		background-color: $clr-red-a700
		color: $clr-primary-text-dark
		border-radius: 4px
		padding: 16px
		font-weight: 500
	#switch-show-publicly
		margin-top: 4px
	#btn-save
		themed-button-primary()

	.change-avatar-prompt
		.content
			display: flex
			flex-direction: column
			padding: 48px 32px 32px
			min-height: 0
		.actions
			margin-top: 32px
			align-self: stretch
			display: flex
			justify-content: flex-end
			flex-shrink: 0
		#btn-cancel
			themed-button-secondary()
			margin-right: 8px
		#btn-upload
			themed-button-primary()
	+below('s')
		.inputs
			width: auto
</style>
