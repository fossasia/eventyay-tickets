<template lang="pug">
.c-live-captions
	.caption-log(ref="log")
		.caption-line(v-for="(line, index) in lines", :key="line.id || index") {{ line.text }}
</template>

<script>
export default {
	name: 'LiveCaptions',
	props: {
		wsUrl: {
			type: String,
			default: null
		}
	},
	data() {
		return {
			lines: [],
			ws: null,
			reconnectAttempts: 0,
			maxReconnectAttempts: 5,
			reconnectTimeout: null,
			nextId: 1
		}
	},
	watch: {
		wsUrl(newUrl) {
			this.teardown()
			this.lines = [] // Clear full history on track switch
			if (newUrl) {
				this.connect()
			}
		}
	},
	mounted() {
		if (this.wsUrl) {
			this.connect()
		}
	},
	beforeUnmount() {
		this.teardown()
	},
	methods: {
		async connect() {
			this.clearReconnectTimer()
			if (!this.wsUrl) return
			
			this.ws = new WebSocket(this.wsUrl)
			this.ws.onmessage = this.onMessage
			this.ws.onopen = () => {
				this.reconnectAttempts = 0
			}
			this.ws.onclose = () => {
				this.ws = null
				this.attemptReconnect()
			}
			this.ws.onerror = (e) => {
				console.error('Caption WebSocket error:', e)
				this.ws?.close()
			}
		},
		async teardown() {
			this.clearReconnectTimer()
			if (this.ws) {
				const ws = this.ws
				this.ws = null
				ws.onclose = null
				ws.onerror = null
				ws.onmessage = null
				ws.close()
			}
		},
		clearReconnectTimer() {
			if (this.reconnectTimeout) {
				clearTimeout(this.reconnectTimeout)
				this.reconnectTimeout = null
			}
		},
                attemptReconnect() {
                        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                                this.lines = [{ id: this.nextId++, text: this.$t('Captions disconnected') }]
                                return
                        }
                        const backoffMs = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000)
                        this.reconnectAttempts++
                        this.reconnectTimeout = setTimeout(() => {
                                this.connect()
                        }, backoffMs)
                },
                async onMessage(event) {
                        try {
                                if (event.data instanceof Blob) {
                                        return; // TTS removed for now
                                }
                                
                                const data = JSON.parse(event.data);
                                
								if ((data.type === 'caption' || data.type === 'translated_caption') && data.text) {
                                        this.lines.push({ id: this.nextId++, text: data.text })
                                        if (this.lines.length > 2) {
                                                this.lines = this.lines.slice(-2)
                                        }
                                }
			} catch (e) {
				console.error('Failed to parse caption message', e)
			}
		}
	}
}
</script>

<style lang="stylus">
.c-live-captions
        position: relative
        width: 100%
        margin: 0 auto
        align-self: center
        background-color: #000000
        color: #ffffff
        padding: 8px 16px
        box-sizing: border-box
        flex: none
        display: flex
        flex-direction: column
        align-items: center
        
        font-size: clamp(14px, 2.5vh, 22px)
        line-height: 1.5
        font-weight: 500

        .caption-log
                height: calc(3em + 12px)
                max-height: calc(3em + 12px)
                overflow-y: hidden
                text-align: center
                width: 100%
                max-width: 800px
                
        .caption-line
                overflow-wrap: anywhere
                text-shadow: 0px 1px 4px rgba(0,0,0,0.9), 0px 0px 2px rgba(0,0,0,0.8)
                background-color: rgba(0, 0, 0, 0.4)
                padding: 2px 8px
                border-radius: 4px
                display: inline-block
                margin-bottom: 2px
</style>
