// moment does not let us clone and only locally override `now`
// we need to get a clean instance to manipulate
delete require.cache[require.resolve('moment')]
var moment = require('moment')
moment.locale('en-ie') // use ireland for 24h formatting
delete require.cache[require.resolve('moment')]

moment.now = function () { return 1587206880000 }
console.log(moment()._d)
export default moment
