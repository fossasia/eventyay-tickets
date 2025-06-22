// moment does not let us clone and only locally override `now`
// we need to get a clean instance to manipulate
import config from 'config'
delete require.cache[require.resolve('moment')]
const moment = require('moment-timezone')
moment.locale(config.date_locale || 'en-ie') // use ireland for 24h clock
// moment.tz.setDefault('America/New_York')

for (const key of Object.keys(require.cache)) {
	if (!key.includes('node_modules/moment')) continue
	delete require.cache[key]
}
// conf the global moment instance here
const mainMoment = require('moment')
mainMoment.locale(config.date_locale || 'en-ie') // use ireland for 24h clock
if (config.timetravelTo) {
	const timetravelTimestamp = moment(config.timetravelTo).valueOf()
	moment.now = function() { return timetravelTimestamp }
	console.warn('timetraveling to', moment()._d)
}

export default moment
