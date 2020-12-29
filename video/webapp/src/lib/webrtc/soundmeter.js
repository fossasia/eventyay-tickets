/*
 *  Copyright (c) 2015 The WebRTC project authors. All Rights Reserved.
 *
 * Modified by the venueless team to make the "slow" method "quicker"
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree.
 */

'use strict'

// Meter class that generates a number correlated to audio volume.
// The meter class itself displays nothing, but it makes the
// instantaneous and time-decaying volumes available for inspection.
// It also reports on the fraction of samples that were at or near
// the top of the measurement range.
function SoundMeter (context) {
	this.context = context
	this.instant = 0.0
	this.slow = 0.0
	this.clip = 0.0
	this.script = context.createScriptProcessor(2048, 1, 1)
	const that = this
	this.script.onaudioprocess = function (event) {
		const input = event.inputBuffer.getChannelData(0)
		let i
		let sum = 0.0
		let clipcount = 0
		for (i = 0; i < input.length; ++i) {
			sum += input[i] * input[i]
			if (Math.abs(input[i]) > 0.99) {
				clipcount += 1
			}
		}
		that.instant = Math.sqrt(sum / input.length)
		that.slow = 0.90 * that.slow + 0.10 * that.instant // 95:5 originally
		that.clip = clipcount / input.length
	}
}

SoundMeter.prototype.connectToSource = function (stream, callback) {
	console.log('SoundMeter connecting')
	try {
		this.mic = this.context.createMediaStreamSource(stream)
		this.mic.connect(this.script)
		// necessary to make sample run, but should not be.
		this.script.connect(this.context.destination)
		if (typeof callback !== 'undefined') {
			callback(null)
		}
	} catch (e) {
		console.error(e)
		if (typeof callback !== 'undefined') {
			callback(e)
		}
	}
}

SoundMeter.prototype.stop = function () {
	console.log('SoundMeter stopping')
	this.mic.disconnect()
	this.script.disconnect()
}

export default SoundMeter
