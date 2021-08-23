// contains base code for a venueless client
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

export default class VenueLessClient extends EventEmitter {
	// socket
	// clientId
	// user
	// world
	// activeRoom
	// correlationId
	// lastPing

	constructor (url) {
		super()
		this.url = url
		this.correlationId = 1
		this.clientId = uuid()
		this.messagesInFlight = {}
	}

	init (afterInitCb) {
		this.afterInitCb = afterInitCb

		const res = ws.connect(this.url, null, (socket) => {
			concurrentClients.add(1)
			this.socket = socket
			socket.on('open', () => {
				this.send(['authenticate', {client_id: this.clientId}])
			})
			socket.on('message', this.handleMessage.bind(this))
			socket.on('close', () => console.log('disconnected'))
			socket.on('error', function (error) {
				console.log(error.toString())
				connectionErrors.add(1)
			})
		})
		concurrentClients.add(-1)
		check(res, { 'status is 101': (r) => r && r.status === 101 })
	}

	handleMessage (data) {
		// TODO handle errors
		const payload = JSON.parse(data)
		if (payload[0] === 'authenticated') {
			this.ping()

			this.user = payload[1]['user.config']
			this.world = payload[1]['world.config']
			this.stages = this.world.rooms.filter(room => room.modules.some(m => m.type === 'livestream.native'))

			// TODO SLEEP
			this.send('user.update', {
				profile: {display_name: `client ${this.clientId}`}
			})
			this.afterInitCb()
		} else if (payload[0] === 'pong') {
			const pingRTT = Date.now() - this.lastPing
			pingTrend.add(pingRTT)
			check(pingRTT, {
				'ping lower than 1s': pingRTT => pingRTT < 1000
			})
			this.lastPing = null
		} else if (payload[0] === 'success') {
			const timestamp = this.messagesInFlight[payload[1]]
			this.messagesInFlight[payload[1]] = undefined
			responseTrend.add(Date.now() - timestamp)
		} else if(payload[0] === 'chat.event') {
			if (payload[1].sender === this.user.id) {
				chatTrend.add(Date.now() - new Date(payload[1].timestamp))
			}
		}
	}

	close () {
		this.socket.close()
	}

	send (action, data) {
		let payload
		if (action instanceof Array && !data) {
			payload = action
		} else {
			const correlationId = this.correlationId++
			payload = [action, correlationId, data]
			this.messagesInFlight[correlationId] = Date.now()
		}
		this.socket.send(JSON.stringify(payload))
	}

	ping () {
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
		this.setTimeout(this.ping.bind(this), PING_INTERVAL)
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
			this.send('chat.subscribe', {channel: this.chatChannel})
			this.send('chat.join', {channel: this.chatChannel})
		}
	}

	sendChatMessage () {
		this.send('chat.send', {
			channel: this.chatChannel,
			event_type: 'channel.message',
			content: {type: 'text', timestamp: Date.now()}
		})
	}
}
