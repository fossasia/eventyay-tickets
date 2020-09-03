<template lang="pug">
prompt.c-profile-greeting-prompt(:allowCancel="false")
	.content
		connect-gravatar(v-if="showConnectGravatar", @change="setGravatar", @close="showConnectGravatar = false")
		.step-display-name(v-else-if="activeStep === 'displayName'")
			h1 {{ $t('profile/GreetingPrompt:step-display-name:heading') }}
			p {{ $t('profile/GreetingPrompt:step-display-name:text') }}
			//- link here not strictly good UX
			a.gravatar-connected-hint(v-if="connectedGravatar", href="#", @click="connectedGravatar = false; showConnectGravatar = true") {{ $t('profile/GreetingPrompt:gravatar-change:label') }}
			p.gravatar-hint(v-else-if="!showConnectGravatar") {{ $t('profile/GreetingPrompt:gravatar-hint:text') }} #[a(href="#", @click="showConnectGravatar = true") gravatar].
			bunt-input.display-name(name="displayName", :label="$t('profile/GreetingPrompt:displayname:label')", v-model.trim="profile.display_name", :validation="$v.profile.display_name")
		.step-avatar(v-else-if="activeStep === 'avatar'")
			h1 {{ $t('profile/GreetingPrompt:step-avatar:heading') }}
			p {{ $t('profile/GreetingPrompt:step-avatar:text') }}
			change-avatar(ref="step", v-model="profile.avatar")
		.step-additional-fields(v-else-if="activeStep === 'additionalFields'")
			h1 {{ $t('profile/GreetingPrompt:step-fields:heading') }}
			p {{ $t('profile/GreetingPrompt:step-fields:text') }}
			change-additional-fields(v-model="profile.fields")
		.actions(v-if="!showConnectGravatar")
			bunt-button#btn-back(v-if="previousStep", @click="activeStep = previousStep") back
			bunt-button#btn-continue(v-if="nextStep", :class="{invalid: $v.$invalid && $v.$dirty}", :disabled="$v.$invalid && $v.$dirty", :loading="processingStep", :key="activeStep", @click="toNextStep") continue
			bunt-button#btn-finish(v-else, :loading="saving", @click="update") finish
</template>
<script>
import { mapState } from 'vuex'
import Prompt from 'components/Prompt'
import ChangeAvatar from './ChangeAvatar'
import ChangeAdditionalFields from './ChangeAdditionalFields'
import ConnectGravatar from './ConnectGravatar'
import { required } from 'buntpapier/src/vuelidate/validators'

export default {
	components: { Prompt, ChangeAvatar, ChangeAdditionalFields, ConnectGravatar },
	data () {
		return {
			activeStep: null,
			showConnectGravatar: false,
			connectedGravatar: false,
			profile: null,
			processingStep: false,
			saving: false,
		}
	},
	validations () {
		if (this.activeStep !== 'displayName') return {}
		return {
			profile: {
				display_name: {
					required: required('Display name cannot be empty')
				}
			}
		}
	},
	computed: {
		...mapState(['user', 'world']),
		steps () {
			const steps = [
				'displayName',
				'avatar'
			]
			if (this.world?.user_profile?.additional_fields) steps.push('additionalFields')
			return steps
		},
		previousStep () {
			return this.steps[this.steps.indexOf(this.activeStep) - 1]
		},
		nextStep () {
			return this.steps[this.steps.indexOf(this.activeStep) + 1]
		}
	},
	created () {
		this.activeStep = this.steps[0]
		this.profile = Object.assign({
			greeted: true,
			display_name: '',
			avatar: {
				identicon: this.user.id
			},
			fields: {}
		}, this.user.profile)
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		async toNextStep () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			if (this.$refs.step?.update) {
				this.processingStep = true
				await this.$refs.step.update()
				this.processingStep = false
			}
			this.activeStep = this.nextStep
		},
		setGravatar (gravatar) {
			Object.assign(this.profile, gravatar)
			this.showConnectGravatar = false
		},
		async update () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			this.saving = true
			if (this.$refs.step?.update) {
				await this.$refs.step.update()
			}
			await this.$store.dispatch('updateUser', {profile: this.profile})
			// TODO error handling
			this.$emit('close')
		}
	}
}
</script>
<style lang="stylus">
.c-profile-greeting-prompt
	.content
		flex: auto
		display: flex
		flex-direction: column
		align-items: center
		position: relative
		padding: 16px
		h1
			margin: 8px 0
		p
			margin: 0 0 8px 0
			width: 360px
		.step-display-name, .step-avatar, .step-additional-fields
			display: flex
			flex-direction: column
			align-items: center
		.display-name
			max-width: 280px

		.actions
			margin-top: 32px
			align-self: stretch
			display: flex
			justify-content: flex-end
		#btn-back
			themed-button-secondary()
			margin-right: 8px
		#btn-continue, #btn-finish
			themed-button-primary()
			&.invalid
				button-style(color: $clr-danger)
		+below('m')
			p
				width: auto
</style>
