// moment does not let us clone and only locally override `now`
// we need to get a clean instance to manipulate
import config from 'config'
delete require.cache[require.resolve('moment')]
const moment = require('moment')
moment.locale(config.dateLocale || 'en-ie') // use ireland for 24h clock

for (const key of Object.keys(require.cache)) {
	if (!key.includes('node_modules/moment')) continue
	delete require.cache[key]
}
// conf the global moment instance here
const mainMoment = require('moment')
mainMoment.locale(config.dateLocale || 'en-ie') // use ireland for 24h clock

if (config.timetravelTo) {
	const timetravelTimestamp = moment(config.timetravelTo).valueOf()
	moment.now = function () { return timetravelTimestamp }
	console.warn('timetraveling to', moment()._d)
}

export default moment
