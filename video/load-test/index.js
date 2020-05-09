const client = require('./client')
const blessed = require('blessed')
const contrib = require('blessed-contrib')
const Stats = require('fast-stats').Stats

function main ({MAX_CLIENTS, TOTAL_CHAT_MESSAGES_PER_SECOND, CLIENT_RAMP_UP_TIME, URL}) {
	// Create a screen object.
	const screen = blessed.screen({
		smartCSR: true
	})

	screen.title = 'venueless loadtest'
	const grid = new contrib.grid({rows: 4, cols: 2, screen})
	const log = grid.set(0, 1, 4, 1, blessed.log, {
		fg: 'green',
		selectedFg: 'green',
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

	let pings = new Stats({buckets: [25, 50, 95], store_data: false})
	let timings = new Stats({buckets: [25, 50, 95], store_data: false})

	const createClient = function () {
		if (clients >= MAX_CLIENTS) return
		client(URL, clients, TOTAL_CHAT_MESSAGES_PER_SECOND / MAX_CLIENTS, (ping) => {
			pings.push(ping)
		}, (timing) => {
			timings.push(timing)
		})
		clients++
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
	Ping (avg/med/25%/50%/95%/minMax):\n${pings.amean().toFixed(2)} / ${pings.median().toFixed(2)} / ${pings.percentile(25).toFixed(2)} / ${pings.percentile(50).toFixed(2)} / ${pings.percentile(95).toFixed(2)} / ${pings.range()}\n
	Chat message (avg/med/25%/50%/95%/minMax):\n${timings.amean().toFixed(2)} / ${timings.median().toFixed(2)} / ${timings.percentile(25).toFixed(2)} / ${timings.percentile(50).toFixed(2)} / ${timings.percentile(95).toFixed(2)} / ${timings.range()}\n
	`)
		gauge.setPercent(100 * clients / MAX_CLIENTS)
		screen.render()
	}

	setInterval(createClient, CLIENT_RAMP_UP_TIME)
	setInterval(computePings, 1000)
}

require('yargs')
.scriptName('load-test')
.usage('$0 [args]')
.option('clients', {
	default: '300',
	describe: 'number of clients to start up',
	type: 'number'
})
.option('msgs', {
	default: '1',
	describe: 'total number of chat messages per second',
	type: 'number'
})
.option('rampup', {
	default: '150',
	describe: 'time in ms between each client creation',
	type: 'number'
})
.command('$0 <url>', 'start a load test', (yargs) => {
	yargs.positional('url', {
		type: 'string',
		describe: 'server url to test against'
	})
}, function (argv) {
	main({
		URL: argv.url,
		MAX_CLIENTS: argv.clients,
		TOTAL_CHAT_MESSAGES_PER_SECOND: argv.msgs,
		CLIENT_RAMP_UP_TIME: argv.rampup
	})
})
.help()
.argv
