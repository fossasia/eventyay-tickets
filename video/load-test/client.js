// simulates a realistic venueless frontend
// - pings
// - on room join, if chat module is present, fetches backlog
// - if encountering new users (in chat messages), fetches missing profiles

import { check, sleep } from 'k6'
import ws from 'k6/ws'
import { Counter, Trend } from 'k6/metrics'
import { uuidv4 as uuid } from "https://jslib.k6.io/k6-utils/1.1.0/index.js"
import EventEmitter from './events.js'

const PING_INTERVAL = 10000

const pingTrend = new Trend('ping_time', true)
const chatTrend = new Trend('chat_message_time', true)
const responseTrend = new Trend('request_response_time', true)
const concurrentClients = new Counter('concurrent_clients')
const connectionErrors = new Counter('connection_errors')
const messageErrors = new Counter('message_errors')

export default class VenueLessClient extends EventEmitter {

	constructor (url) {
		super()
		this.url = url
		this.clientId = uuid()
		this._correlationId = 1
		this._messagesInFlight = {}
		this._userProfiles = {}
	}

	init (afterInitCb) {
		const res = ws.connect(this.url, null, (socket) => {
			concurrentClients.add(1)
			this.socket = socket
			socket.on('open', () => {
				this.send(['authenticate', {client_id: this.clientId}])
			})
			socket.on('message', (data) => {
				const payload = JSON.parse(data)
				if (payload[0] === 'authenticated') {
					this._ping()
					this.user = payload[1]['user.config']
					this.world = payload[1]['world.config']
					this.stages = this.world.rooms.filter(room => room.modules.some(m => m.type === 'livestream.native'))
					// TODO SLEEP
					this.send('user.update', {
						profile: {display_name: `client ${this.clientId}`}
					})
					afterInitCb()
				} else if (payload[0] === 'pong') {
					const pingRTT = Date.now() - this.lastPing
					pingTrend.add(pingRTT)
					check(pingRTT, {
						'ping lower than 1s': pingRTT => pingRTT < 1000
					})
					this.lastPing = null
				} else if (payload[0] === 'success') {
					const {timestamp, cb} = this._messagesInFlight[payload[1]]
					this._messagesInFlight[payload[1]] = undefined
					responseTrend.add(Date.now() - timestamp)
					if (cb) cb(payload[2])
				} else if(payload[0] === 'chat.event') {
					if (payload[1].sender === this.user.id) {
						chatTrend.add(Date.now() - new Date(payload[1].timestamp))
					} else {
						this._fetchUsersFromMessages([payload[1]])
					}
				} else if (payload[0] === 'error') {
					console.log(data)
					messageErrors.add(1)
				}
			})
			socket.on('close', () => console.log('disconnected'))
			socket.on('error', function (error) {
				console.log(error.toString())
				connectionErrors.add(1)
			})
		})
		concurrentClients.add(-1)
		check(res, { 'status is 101': (r) => r && r.status === 101 })
	}

	close () {
		this.socket.close()
	}

	send (action, data, cb) {
		let payload
		if (action instanceof Array && !data) {
			payload = action
		} else {
			const correlationId = this._correlationId++
			payload = [action, correlationId, data]
			this._messagesInFlight[correlationId] = {
				timestamp: Date.now(),
				cb
			}
		}
		this.socket.send(JSON.stringify(payload))
	}

	setTimeout (fn, ms) {
		return this.socket.setTimeout(fn, ms)
	}

	joinRoom (room) {
		if (this.room) {
			this.send('room.leave', {room: this.room.id})
			if (this.chatChannel) {
				this.send('chat.unsubscribe', {channel: this.chatChannel})
			}
		}
		this.room = room
		this.send('room.enter', {room: this.room.id})
		const channelModule = room.modules.find(m => m.type === 'chat.native')
		this.chatChannel = channelModule ? channelModule.channel_id : undefined
		if (this.chatChannel) {
			this.send('chat.subscribe', {channel: this.chatChannel}, ({next_event_id}) => {
				this.send('chat.fetch', {
					channel: this.chatChannel,
					before_id: next_event_id,
					count: 25
				}, ({results}) => {
					this._fetchUsersFromMessages(results)
					if (results.length < 25) return
					// fetch twice, seems to be the usual amount for bigger screens
					this.send('chat.fetch', {
						channel: this.chatChannel,
						before_id: results[0].event_id,
						count: 25
					}, ({results}) => this._fetchUsersFromMessages(results))
				})

			})
			this.send('chat.join', {channel: this.chatChannel})
		}
	}

	sendChatMessage () {
		this.send('chat.send', {
			channel: this.chatChannel,
			event_type: 'channel.message',
			content: {type: 'text', timestamp: Date.now(), 'body': Date.now().toString()}
		})
	}

	// PRIVATE METHODS

	_ping () {
		check(this.lastPing, {
			'ping didn\'t timeout': lastPing => !lastPing
		}, {ping: 'no-timeout'})
		if (this.lastPing) {
			const pingRTT = Date.now() - this.lastPing
			pingTrend.add(pingRTT)
			return
		}
		this.lastPing = Date.now()
		this.send(['ping', this.lastPing])
		this.setTimeout(this._ping.bind(this), PING_INTERVAL)
	}

	_fetchUsersFromMessages (messages) {
		const missingProfiles = new Set()
		for (const event of messages) {
			if (!this._userProfiles[event.sender]) {
				missingProfiles.add(event.sender)
			}
			if (event.content.user && !this._userProfiles[event.content.user.id]) {
				missingProfiles.add(event.content.user.id)
			}
		}
		this.send('user.fetch', {ids: Array.from(missingProfiles)})
		// we don't care for the actual content
		for (const id of missingProfiles) {
			this._userProfiles[id] = true
		}
	}
}
