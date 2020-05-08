const client = require('./client')
const blessed = require('blessed')
const contrib = require('blessed-contrib')
const Stats = require('fast-stats').Stats

const MAX_CLIENTS = 1000
const TOTAL_CHAT_MESSAGES_PER_SECOND = 25
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

// Quit on Escape, q, or Control-C.
screen.key(['escape', 'q', 'C-c'], function(ch, key) {
	return process.exit(0)
})

screen.render()

let clients = 0
gauge.setPercent(0)

let pings = new Stats()
let timings = new Stats()

const createClient = function () {
	if (clients >= MAX_CLIENTS) return
	client(clients, TOTAL_CHAT_MESSAGES_PER_SECOND / MAX_CLIENTS, (ping) => {
		pings.push(ping)
	}, (timing) => {
		timings.push(timing)
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
msg/s (at max clients): ${TOTAL_CHAT_MESSAGES_PER_SECOND}\n
Ramp Up: ${CLIENT_RAMP_UP_TIME}ms\n
Ping (avg/med/25%/50%/95%/minMax):\n${pings.amean().toFixed(2)} / ${pings.median()} / ${pings.percentile(25)} / ${pings.percentile(50)} / ${pings.percentile(95)} / ${pings.range()}\n
Chat message (avg/med/25%/50%/95%/minMax):\n${timings.amean().toFixed(2)} / ${timings.median()} / ${timings.percentile(25)} / ${timings.percentile(50)} / ${timings.percentile(95)} / ${timings.range()}\n
`)
	screen.render()
}

setInterval(createClient, CLIENT_RAMP_UP_TIME)
setInterval(computePings, 500)
