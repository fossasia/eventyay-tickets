// Vite/ESM-friendly moment-timezone bootstrap with optional "timetravel" override
import moment from 'moment'
import 'moment-timezone'
import 'moment/dist/locale/en-ie'
import config from 'config'

// Set locale (use Ireland for 24h clock by default, matching previous behavior)
const locale=(config.date_locale || 'en-ie')
moment.locale(locale)

// Optionally override current time for demos/tests
if (config.timetravelTo) {
	const timetravelTimestamp = moment(config.timetravelTo).valueOf()
	// Override moment.now to freeze time
	moment.now = () => timetravelTimestamp
	// eslint-disable-next-line no-console
	console.warn('timetraveling to', moment()._d())
}

export default moment
