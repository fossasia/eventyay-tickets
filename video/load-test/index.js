const client = require('./client')
const blessed = require('blessed')
const contrib = require('blessed-contrib')
const Stats = require('fast-stats').Stats

const MAX_CLIENTS = 1000
const MESSAGES_PER_CLIENT_PER_SECOND = 0.01
const CLIENT_RAMP_UP_TIME = 150

// Create a screen object.
const screen = blessed.screen({
	smartCSR: true
})

screen.title = 'venueless loadtest'
const grid = new contrib.grid({rows: 4, cols: 2, screen})
const log = grid.set(0, 1, 4, 1, blessed.log, {
	fg: "green",
	selectedFg: "green",
	label: 'Log',
	scrollable: true,
	mouse: true
})

const text = grid.set(0, 0, 2, 1, blessed.text, {
})

const gauge = grid.set(2, 0, 1, 1, contrib.gauge, {
	label: 'Connected Clients',
	stroke: 'green',
	fill: 'white'
})

const pingSpark = grid.set(3, 0, 1, 1, contrib.sparkline, {
	label: 'Ping'
})

console.log = log.log.bind(log)
console.warn = log.log.bind(log)
console.error = log.log.bind(log)

// Quit on Escape, q, or Control-C.
screen.key(['escape', 'q', 'C-c'], function(ch, key) {
	return process.exit(0)
})

screen.render()

let clients = 0
gauge.setPercent(0)

let pings = new Stats()

const createClient = function () {
	if (clients >= MAX_CLIENTS) return
	client(clients, MESSAGES_PER_CLIENT_PER_SECOND, (ping) => {
		pings.push(ping)
	})
	clients++
	gauge.setPercent(100 * clients / MAX_CLIENTS)
	screen.render()

}

const pingAverages = []

const computePings = function () {
	pingAverages.push(pings.amean())
	if (pingAverages.length > 25) pingAverages.shift()
	pingSpark.setData([ 'Average'], [pingAverages])
	text.setText(`
		Clients: ${clients}/${MAX_CLIENTS}\n
		Ramp Up: ${CLIENT_RAMP_UP_TIME}ms\n
		Average Ping: ${pings.amean()}\n
		Median Ping: ${pings.median()}\n
		Ping Percentile 95%: ${pings.percentile(95)}\n
		Ping Percentile 50%: ${pings.percentile(50)}\n
		Ping Percentile 25%: ${pings.percentile(25)}\n
		Ping Range: ${pings.range()}\n
		`)
	screen.render()
}

setInterval(createClient, CLIENT_RAMP_UP_TIME)

setInterval(computePings, 500)


// console.log(`starting ${MAX_CLIENTS} sending ${MESSAGES_PER_CLIENT_PER_SECOND} messages/s`)
