// moment does not let us clone and only locally override `now`
// we need to get a clean instance to manipulate
import config from 'config'
delete require.cache[require.resolve('moment')]
var moment = require('moment')
moment.locale(config.dateLocale || 'en-ie') // use ireland for 24h clock
delete require.cache[require.resolve('moment')]

if (config.timetravelTo) {
	const timetravelTimestamp = moment(config.timetravelTo).valueOf()
	moment.now = function () { return timetravelTimestamp }
	console.warn('timetraveling to', moment()._d)
}

export default moment
