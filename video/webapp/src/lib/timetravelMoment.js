// Vite/ESM-friendly moment-timezone bootstrap with optional "timetravel" override
import moment from 'moment-timezone'
import config from 'config'

// Set locale (use Ireland for 24h clock by default, matching previous behavior)
moment.locale(config.date_locale || 'en-ie')

// Optionally override current time for demos/tests
if (config.timetravelTo) {
	const timetravelTimestamp = moment(config.timetravelTo).valueOf()
	// Override moment.now to freeze time
	moment.now = () => timetravelTimestamp
	// eslint-disable-next-line no-console
	console.warn('timetraveling to', moment().toDate())
}

export default moment
