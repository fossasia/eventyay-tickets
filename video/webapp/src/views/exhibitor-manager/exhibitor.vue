<template lang="pug">
.c-manage-exhibitor
	.error(v-if="error") {{ $t('Exhibitors:exhibitor-not-found:text') }}
	template(v-else-if="exhibitor")
		.header
			bunt-icon-button(@click="$router.push({name: 'exhibitors'})") arrow_left
			h2 {{ exhibitor.name }}
			.actions
				.button-group
					bunt-button(:class="{enabled: !showPreview}", @click="showPreview = false") edit
					bunt-button(:class="{enabled: showPreview}", @click="showPreview = true") preview
				bunt-button.btn-save(@click="save", :loading="saving") {{ $t('Exhibitors:save:label') }}
		exhibitor-preview(v-show="showPreview", :exhibitor="exhibitor")
		.main-form(v-show="!showPreview", v-scrollbar.y="")
			bunt-input(v-model="exhibitor.name", :disabled="!hasPermission('world:rooms.create.exhibition')", :label="$t('Exhibitors:name:label')", name="name", :validation="$v.exhibitor.name")
			bunt-input(v-model="exhibitor.tagline", :label="$t('Exhibitors:tagline:label')", name="tagline", :validation="$v.exhibitor.tagline")
			bunt-input(v-model="exhibitor.short_text", :label="$t('Exhibitors:short-text:label')", name="shortText", :validation="$v.exhibitor.shortText")
			bunt-input-outline-container(v-if="exhibitor.text_legacy", :label="$t('Exhibitors:text:label')")
				textarea(slot-scope="{focus, blur}", @focus="focus", @blur="blur", v-model="exhibitor.text_legacy")
			rich-text-editor(v-else, v-model="exhibitor.text_content")
			upload-url-input(v-model="exhibitor.logo", :label="$t('Exhibitors:logo:label')", name="logo", :validation="$v.exhibitor.logo")
			upload-url-input(v-model="exhibitor.banner_list", :label="$t('Exhibitors:banner-list:label')", name="bannerList", :validation="$v.exhibitor.banner_list")
			upload-url-input(v-model="exhibitor.banner_detail", :label="$t('Exhibitors:banner-detail:label')", name="bannerDetail", :validation="$v.exhibitor.banner_detail")
			bunt-select(v-model="exhibitor.size", :disabled="!hasPermission('world:rooms.create.exhibition')", :label="$t('Exhibitors:size:label')", name="size", :options="sizes", :validation="$v.exhibitor.size")
			bunt-input(v-model="exhibitor.sorting_priority", :disabled="!hasPermission('world:rooms.create.exhibition')", :label="$t('Exhibitors:sorting-priority:label')", name="sortingPriority", :validation="$v.exhibitor.sorting_priority")
			bunt-select(v-model="exhibitor.room_id", :disabled="!hasPermission('world:rooms.create.exhibition')", :label="$t('Exhibitors:room:label')", name="room", :options="rooms", option-label="name", :validation="$v.exhibitor.room_id")
			bunt-select(v-model="exhibitor.highlighted_room_id", :label="$t('Exhibitors:highlighted-room:label')", name="highlighted_room", :options="all_rooms_or_none", option-label="name", :validation="$v.exhibitor.highlighted_room_id")
				template(slot-scope="{ option }")
					.label {{ option.name }}
			table.links
				thead
					tr
						th {{ $t('Exhibitors:social-media-link:label') }}
						th
						th
				tbody
					tr(v-for="(link, index) in exhibitor.social_media_links")
						td
							bunt-select(v-model="link.display_text", :label="$t('Exhibitors:social-link-text:label')", name="displayText", :options="supportedNetworks", :validation="$v.exhibitor.social_media_links.$each[index].display_text")
						td
							bunt-input(:value="link.url", :label="$t('Exhibitors:link-url:label')", @input="set_social_media_link_url(index, $event)", name="url", :validation="$v.exhibitor.social_media_links.$each[index].url")
						td.actions
							bunt-icon-button(@click="remove_social_media_link(index)") delete-outline
				tfoot
					tr
						td
							bunt-button(@click="add_social_media_link") {{ $t('Exhibitors:add-link:text') }}
						td
						td
			table.links
				thead
					tr
						th {{ $t('Exhibitors:profile-link:label') }}
						th
						th
				tbody
					tr(v-for="(link, index) in exhibitor.profileLinks")
						td
							bunt-input(:value="link.display_text", @input="set_link_text(index, link.category, $event)", :label="$t('Exhibitors:link-text:label')", name="displayText", :validation="$v.exhibitor.profileLinks.$each[index].display_text")
						td
							bunt-input(:value="link.url", @input="set_link_url(index, link.category, $event)", :label="$t('Exhibitors:link-url:label')", name="url", :validation="$v.exhibitor.profileLinks.$each[index].url")
						td.actions
							bunt-icon-button(@click="remove_link(index, link.category)") delete-outline
							bunt-icon-button(@click="up_link(index, link.category)") arrow-up-bold-outline
							bunt-icon-button(@click="down_link(index, link.category)") arrow-down-bold-outline
				tfoot
				tfoot
					tr
						td
							bunt-button(@click="add_link('profile')") {{ $t('Exhibitors:add-link:text') }}
						td
						td
			table.links
				thead
					tr
						th {{ $t('Exhibitors:download-link:label') }}
						th
						th
				tbody
					tr(v-for="(link, index) in exhibitor.downloadLinks")
						td
							bunt-input(v-model="link.display_text", :label="$t('Exhibitors:link-text:label')", name="displayText", :validation="$v.exhibitor.downloadLinks.$each[index].display_text")
						td
							upload-url-input(v-model="link.url", :label="$t('Exhibitors:link-url:label')", name="url", :validation="$v.exhibitor.downloadLinks.$each[index].url")
						td.actions
							bunt-icon-button(@click="remove_link(index, link.category)") delete-outline
							bunt-icon-button(@click="up_link(index, link.category)") arrow-up-bold-outline
							bunt-icon-button(@click="down_link(index, link.category)") arrow-down-bold-outline
				tfoot
						td
							bunt-button(@click="add_link('download')") {{ $t('Exhibitors:add-link:text') }}
						td
						td
			table.staff
				thead
					tr
						th {{ $t('Exhibitors:staff:label') }}
						th
				tbody
					tr(v-for="(user, index) in exhibitor.staff")
						td.user
							avatar(:user="user", :size="36")
							span.display-name {{ user ? user.profile.display_name : '' }}
						td.actions
							bunt-icon-button(v-if="hasPermission('world:rooms.create.exhibition')", @click="remove_staff(index)") delete-outline
				tfoot(v-if="hasPermission('world:rooms.create.exhibition')")
					tr
						td
							bunt-button(@click="showStaffPrompt=true") {{ $t('Exhibitors:add-staff:text') }}
						td
						td
			bunt-checkbox(v-model="exhibitor.contact_enabled", :label="$t('Exhibitors:contact-enabled:label')", name="contactEnabled")

			.danger-zone(v-if="hasPermission('world:rooms.create.exhibition')")
				bunt-button.delete(icon="delete", @click="showDeletePrompt = true") {{ $t('DeletePrompt:button:label') }}
				span {{ $t('DeletePrompt:button:warning') }}
	bunt-progress-circular(v-else, size="huge")
	transition(name="prompt")
		prompt.delete-prompt(v-if="showDeletePrompt", @close="showDeletePrompt = false")
			.content
				p {{ $t('DeletePrompt:confirm:text') }}
				.name {{ exhibitor.name }}
				bunt-input(name="exhibitorName", :label="$t('Exhibitors:name:label')", v-model="deletingExhibitorName")
				bunt-button.room(icon="delete", :disabled="deletingExhibitorName !== exhibitor.name", @click="deleteExhibitor", :loading="deleting", :error-message="deleteError") {{ $t('Exhibitors:delete:label') }}
	prompt.add-staff-prompt(v-if="showStaffPrompt", :scrollable="false", @close="showStaffPrompt=false")
		.content
			h1 {{ $t('Exhibitors:add-staff:text') }}
			user-select(:button-label="$t('Exhibitors:add-staff:label')", @selected="add_staff")
</template>
<script>
import { mapGetters } from 'vuex'
import { required, maxLength } from 'buntpapier/src/vuelidate/validators'
import { helpers } from 'vuelidate/lib/validators'
import { withParams } from 'vuelidate/lib/validators/common'
import api from 'lib/api'
import router from 'router'
import Avatar from 'components/Avatar'
import Prompt from 'components/Prompt'
import UserSelect from 'components/UserSelect'
import UploadUrlInput from 'components/config/UploadUrlInput'
import RichTextEditor from 'components/RichTextEditor'
import ExhibitorPreview from 'views/exhibitors/item'

const absrelurl = (message) => withParams({message: message}, value => helpers.regex('absrelurl', /^(https?:\/\/|mailto:|\/)[^ ]+$/)(value))

export default {
	components: { Avatar, ExhibitorPreview, Prompt, UploadUrlInput, UserSelect, RichTextEditor },
	props: {
		exhibitorId: String
	},
	data () {
		return {
			exhibitor: null,
			saving: false,
			error: null,
			showDeletePrompt: false,
			showStaffPrompt: false,
			deletingExhibitorName: '',
			deleting: false,
			deleteError: null,
			sizes: ['1x1', '3x1', '3x3'],
			showPreview: false
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		all_rooms_or_none () {
			const r = [{name: '', id: ''}]
			r.push(...this.$store.state.rooms)
			return r
		},
		rooms () {
			return this.$store.state.rooms.filter(room => room.modules.filter(m => m.type === 'exhibition.native').length > 0)
		},
		supportedNetworks () {
			return [
				'Facebook',
				'LinkedIn',
				'Xing',
				'Twitter',
				'Mastodon',
				'Reddit',
				'Instagram',
				'YouTube',
				'Discord'
			]
		}
	},
	validations () {
		return {
			exhibitor: {
				name: {
					required: required(this.$t('Exhibitors:validation-name:required')),
					maxLength: maxLength(80, this.$t('Exhibitors:validation-name:maxLength'))
				},
				logo: {
					maxLength: maxLength(200, this.$t('Exhibitors:validation-url:maxLength')),
					absrelurl: absrelurl(this.$t('Exhibitors:validation-url:valid'))
				},
				banner_list: {
					maxLength: maxLength(200, this.$t('Exhibitors:validation-url:maxLength')),
					absrelurl: absrelurl(this.$t('Exhibitors:validation-url:valid'))
				},
				banner_detail: {
					maxLength: maxLength(200, this.$t('Exhibitors:validation-url:maxLength')),
					absrelurl: absrelurl(this.$t('Exhibitors:validation-url:valid'))
				},
				tagline: {
					maxLength: maxLength(250, this.$t('Exhibitors:validation-tagline:maxLength'))
				},
				shortText: {
					maxLength: maxLength(500, this.$t('Exhibitors:validation-short-text:maxLength'))
				},
				size: {
					required: required(this.$t('Exhibitors:validation-size:required'))
				},
				room_id: {
					required: required(this.$t('Exhibitors:validation-room:required'))
				},
				highlighted_room_id: {},
				sorting_priority: {
					required: required(this.$t('Exhibitors:validation-sorting:required'))
				},
				social_media_links: {
					$each: {
						display_text: {
							required: required(this.$t('Exhibitors:validation-social-links-display-text:required'))
						},
						url: {
							required: required(this.$t('Exhibitors:validation-links-url:required')),
							maxLength: maxLength(200, this.$t('Exhibitors:validation-url:maxLength')),
							absrelurl: absrelurl(this.$t('Exhibitors:validation-links-url:required'))
						}
					}
				},
				profileLinks: {
					$each: {
						display_text: {
							required: required(this.$t('Exhibitors:validation-links-display-text:required')),
							maxLength: maxLength(300, this.$t('Exhibitors:validation-links-display-text:maxLength'))
						},
						url: {
							required: required(this.$t('Exhibitors:validation-links-url:required')),
							maxLength: maxLength(200, this.$t('Exhibitors:validation-url:maxLength')),
							absrelurl: absrelurl(this.$t('Exhibitors:validation-links-url:required'))
						}
					}
				},
				downloadLinks: {
					$each: {
						display_text: {
							required: required(this.$t('Exhibitors:validation-links-display-text:required')),
							maxLength: maxLength(300, this.$t('Exhibitors:validation-links-display-text:maxLength'))
						},
						url: {
							required: required(this.$t('Exhibitors:validation-links-url:required')),
							maxLength: maxLength(200, this.$t('Exhibitors:validation-url:maxLength')),
							absrelurl: absrelurl(this.$t('Exhibitors:validation-links-url:required'))
						}
					}
				}
			}
		}
	},
	async created () {
		try {
			if (this.exhibitorId !== '') {
				this.exhibitor = (await api.call('exhibition.get', {exhibitor: this.exhibitorId})).exhibitor
				this.$set(this.exhibitor, 'downloadLinks', this.exhibitor.links.filter(l => l.category === 'download').sort((a, b) => a.sorting_priority - b.sorting_priority))
				this.$set(this.exhibitor, 'profileLinks', this.exhibitor.links.filter(l => l.category === 'profile').sort((a, b) => a.sorting_priority - b.sorting_priority))
			} else {
				this.exhibitor = {
					id: '',
					name: '',
					tagline: '',
					short_text: '',
					text: '',
					logo: '',
					banner_list: '',
					banner_detail: '',
					size: '',
					sorting_priority: 0,
					room_id: '',
					highlighted_room_id: '',
					social_media_links: [],
					links: [],
					staff: [],
					contact_enabled: true,
				}
				this.$set(this.exhibitor, 'downloadLinks', [])
				this.$set(this.exhibitor, 'profileLinks', [])
			}
		} catch (error) {
			this.error = error
			console.log(error)
		}
	},
	methods: {
		remove_social_media_link (link) {
			this.$delete(this.exhibitor.social_media_links, link)
		},
		add_social_media_link () {
			this.exhibitor.social_media_links.push({display_text: '', url: ''})
		},
		set_social_media_link_text (index, displayText) {
			this.exhibitor.social_media_links[index].display_text = displayText
		},
		set_social_media_link_url (index, url) {
			this.exhibitor.social_media_links[index].url = url
		},
		remove_link (index, category) {
			if (category === 'profile') {
				this.$delete(this.exhibitor.profileLinks, index)
			} else if (category === 'download') {
				this.$delete(this.exhibitor.downloadLinks, index)
			}
		},
		add_link (category) {
			if (category === 'profile') {
				this.exhibitor.profileLinks.push({display_text: '', url: '', category: category, sorting_priority: 0})
			} else if (category === 'download') {
				this.exhibitor.downloadLinks.push({display_text: '', url: '', category: category, sorting_priority: 0})
			}
		},
		up_link (index, category) {
			if (index === 0) return
			if (category === 'profile') {
				const l = this.exhibitor.profileLinks[index - 1]
				this.$set(this.exhibitor.profileLinks, index - 1, this.exhibitor.profileLinks[index])
				this.$set(this.exhibitor.profileLinks, index, l)
			} else if (category === 'download') {
				const l = this.exhibitor.downloadLinks[index - 1]
				this.$set(this.exhibitor.downloadLinks, index - 1, this.exhibitor.downloadLinks[index])
				this.$set(this.exhibitor.downloadLinks, index, l)
			}
		},
		down_link (index, category) {
			if (category === 'profile') {
				if (index === this.exhibitor.profileLinks.length - 1) return
				const l = this.exhibitor.profileLinks[index + 1]
				this.$set(this.exhibitor.profileLinks, index + 1, this.exhibitor.profileLinks[index])
				this.$set(this.exhibitor.profileLinks, index, l)
			} else if (category === 'download') {
				if (index === this.exhibitor.downloadLinks.length - 1) return
				const l = this.exhibitor.downloadLinks[index + 1]
				this.$set(this.exhibitor.downloadLinks, index + 1, this.exhibitor.downloadLinks[index])
				this.$set(this.exhibitor.downloadLinks, index, l)
			}
		},
		set_link_text (index, category, displayText) {
			if (category === 'profile') {
				this.exhibitor.profileLinks[index].display_text = displayText
			} else if (category === 'download') {
				this.exhibitor.downloadLinks[index].display_text = displayText
			}
		},
		set_link_url (index, category, url) {
			if (category === 'profile') {
				this.exhibitor.profileLinks[index].url = url
			} else if (category === 'download') {
				this.exhibitor.downloadLinks[index].url = url
			}
		},
		add_staff (users) {
			this.exhibitor.staff = this.exhibitor.staff.concat(users)
			this.exhibitor.staff = this.exhibitor.staff.filter((user, index) => this.exhibitor.staff.indexOf(user) === index)
			this.showStaffPrompt = false
		},
		remove_staff (user) {
			this.$delete(this.exhibitor.staff, user)
		},
		async save () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			this.saving = true

			this.exhibitor.profileLinks.forEach((l, i) => l.sorting_priority = i)
			this.exhibitor.downloadLinks.forEach((l, i) => l.sorting_priority = i)
			this.exhibitor.links = [...this.exhibitor.downloadLinks, ...this.exhibitor.profileLinks]

			const exhibitor = (await api.call('exhibition.patch', {
				id: this.exhibitorId,
				name: this.exhibitor.name,
				tagline: this.exhibitor.tagline,
				short_text: this.exhibitor.short_text,
				text_legacy: this.exhibitor.text_legacy || null,
				text_content: this.exhibitor.text_content,
				logo: this.exhibitor.logo,
				banner_list: this.exhibitor.banner_list,
				banner_detail: this.exhibitor.banner_detail,
				size: this.exhibitor.size,
				sorting_priority: this.exhibitor.sorting_priority,
				room_id: this.exhibitor.room_id,
				highlighted_room_id: this.exhibitor.highlighted_room_id,
				social_media_links: this.exhibitor.social_media_links,
				links: this.exhibitor.links,
				staff: this.exhibitor.staff,
				contact_enabled: this.exhibitor.contact_enabled,
			})).exhibitor
			if (this.exhibitorId === '') await router.push({name: 'exhibitors:exhibitor', params: {exhibitorId: exhibitor.id}})
			this.saving = false
			// TODO error handling
		},
		async deleteExhibitor () {
			this.deleting = true
			this.deleteError = null
			try {
				await api.call('exhibition.delete', {exhibitor: this.exhibitorId})
				this.$router.replace({name: 'exhibitors'})
			} catch (error) {
				this.deleteError = this.$t(`error:${error.code}`)
			}
			this.deleting = false
		}
	}
}
</script>
<style lang="stylus">
.c-manage-exhibitor
	display: flex
	flex-direction: column
	background: $clr-white
	min-height: 0
	.bunt-icon-button
		icon-button-style(style: clear)
	.header
		background-color: $clr-grey-100
		border-bottom: border-separator()
		display: flex
		padding: 8px
		flex: none
		.bunt-icon-button
			margin-right: 8px
		h2
			flex: auto
			font-size: 21px
			font-weight: 500
			margin: 1px 16px 0 0
			ellipsis()
		.actions
			display: flex
			flex: none
			.button-group
				margin-right: 32px
				> .bunt-button
					&.enabled
						themed-button-primary()
					&:not(.enabled)
						themed-button-secondary()
						border: 2px solid var(--clr-primary)
					&:first-child
						border-radius: 4px 0 0 4px
					&:last-child
						border-radius: 0 4px 4px 0
			.btn-save
				themed-button-primary()
	.main-form
		display: block
		flex-direction: column
		> *
			margin: 0 16px
		.bunt-input-outline-container
			textarea
				background-color: transparent
				border: none
				outline: none
				resize: vertical
				min-height: 250px
				padding: 0 8px
	h2
		margin-top: 0
		margin-bottom: 16px
	.links, .staff
		margin-bottom: 30px
		th
			text-align: left
			border-bottom: 1px solid #ccc
			padding: 10px
		td
			vertical-align: center
		td.actions
			text-align: right
		td.user
			display: flex
			align-items: center
			min-height: 48px
			.display-name
				margin-left: 8px
				flex: auto
				ellipsis()

	.danger-zone
		margin: 50px 8px
		color: $clr-danger
		border-top: 2px solid $clr-danger
		padding: 8px
		.delete
			button-style(color: $clr-danger)
			margin: 0 8px

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
		.name
			font-family: monospace
			font-size: 16px
			border: border-separator()
			border-radius: 4px
			padding: 4px 8px
			background-color: $clr-grey-100
			align-self: center
		.delete
			button-style(color: $clr-danger)

	.add-staff-prompt
		.prompt-wrapper
			height: 80vh
			width: 600px
		.content
			display: flex
			flex-direction: column
			position: relative
			box-sizing: border-box
			min-height: 0
			#btn-close
				icon-button-style(style: clear)
				position: absolute
				top: 8px
				right: 8px
			h1
				margin: 0
				text-align: center
			p
				max-width: 320px
			form
				display: flex
				flex-direction: column
				align-self: stretch
				.bunt-button
					themed-button-primary()
					margin-top: 16px
				.bunt-select
					select-style(size: compact)
					ul li
						display: flex
						.mdi
							margin-right: 8px
				.bunt-input-outline-container
					textarea
						background-color: transparent
						border: none
						outline: none
						resize: vertical
						min-height: 64px
						padding: 0 8px
</style>
