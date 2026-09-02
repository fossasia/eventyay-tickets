<template lang="pug">
.c-live-captions
	.caption-log(ref="log", @scroll="onScroll")
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
			isAutoScrollPaused: false,
			nextId: 1
		}
	},
	watch: {
		wsUrl(newUrl) {
			console.log('LiveCaptions wsUrl changed to:', newUrl);
			this.teardown()
			this.lines = [] // Clear full history on track switch
			if (newUrl) {
				this.connect()
			}
		}
	},
	mounted() {
		console.log('LiveCaptions mounted, initial wsUrl:', this.wsUrl);
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
                                this.lines = [{ id: this.nextId++, text: '[Captions disconnected]' }]
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
                                let data;
                                if (event.data instanceof Blob) {
                                        // This is a binary TTS frame from VoxBento
                                        const buffer = await event.data.arrayBuffer();
                                        const view = new DataView(buffer);
                                        const version = view.getUint8(0);
                                        if (version !== 1) {
                                                console.error('Unknown TTS frame version:', version);
                                                return;
                                        }
                                        const headerLength = view.getUint32(1); // big-endian
                                        const headerBytes = new Uint8Array(buffer, 5, headerLength);
                                        const headerString = new TextDecoder().decode(headerBytes);
                                        data = JSON.parse(headerString);
                                        
                                        // Map TTS header format to our format
                                        data.type = 'tts_bundle';
                                        if (data.translation) {
                                                data.translated = data.translation;
                                        }
                                } else {
                                        data = JSON.parse(event.data);
                                }

                                console.log('LiveCaptions received:', data);
								if ((data.type === 'caption' || data.type === 'translated_caption') && data.text) {
                                        this.lines.push({ id: this.nextId++, text: data.text })
                                        if (this.lines.length > 100) {
                                                this.lines = this.lines.slice(-50)
                                        }
                                        this.$nextTick(() => {
                                                if (!this.isAutoScrollPaused && this.$refs.log) {
                                                        this.$refs.log.scrollTop = this.$refs.log.scrollHeight
                                                }
                                        })
                                } else if (data.type === 'tts_bundle' && data.translated) {
                                        this.lines.push({ id: this.nextId++, text: data.translated })
                                        if (this.lines.length > 100) {
                                                this.lines = this.lines.slice(-50)
                                        }
                                        this.$nextTick(() => {
						if (!this.isAutoScrollPaused && this.$refs.log) {
							this.$refs.log.scrollTop = this.$refs.log.scrollHeight
						}
					})
				}
			} catch (e) {
				console.error('Failed to parse caption message', e)
			}
		},
		onScroll(e) {
			const target = e.target
			// If we scroll up from the bottom (with a small 2px threshold for floating point rounding), pause auto-scroll
			const isAtBottom = Math.abs(target.scrollHeight - target.scrollTop - target.clientHeight) < 2
			this.isAutoScrollPaused = !isAtBottom
		}
	}
}
</script>

<style lang="stylus">
.c-live-captions
        position: relative
        
        
        
        
        width: 100%
        background-color: #000000
        color: #ffffff
        padding: 8px 16px
        box-sizing: border-box
        flex: none
        display: flex
        flex-direction: column
        align-items: center
        
        font-size: clamp(16px, 3cqi, 28px)
        line-height: 1.5
        font-weight: 500

        .caption-log
                height: 3em 
                max-height: 3em
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
