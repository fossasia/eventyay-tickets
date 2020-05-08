const client = require('./client')

const MAX_CLIENTS = 250
const MESSAGES_PER_CLIENT_PER_SECOND = 1
const CLIENT_RAMP_UP_TIME = 500

let clients = 0

const createClient = function () {
	if (clients > MAX_CLIENTS) return
	client(clients, MESSAGES_PER_CLIENT_PER_SECOND)
	console.log(`created client ${clients}`)
	clients++
}

setInterval(createClient, CLIENT_RAMP_UP_TIME)


console.log(`starting ${MAX_CLIENTS} sending ${MESSAGES_PER_CLIENT_PER_SECOND} messages/s`)
