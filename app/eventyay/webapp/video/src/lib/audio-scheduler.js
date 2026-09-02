/**
 * AudioScheduler — Jitter-buffered playback queue for TTS audio segments.
 *
 * Instead of playing each incoming audio buffer the instant it arrives
 * (which causes silence gaps between sentences), this scheduler uses
 * the Web Audio API's sample-accurate timing to schedule each buffer to
 * start exactly when the previous one ends.
 *
 * When the queue empties (the speaker pauses), optional comfort noise
 * fades in to avoid jarring digital silence.
 *
 * Usage:
 *   const scheduler = createAudioScheduler(audioCtx, {
 *     jitterBufferSec: 0.25,
 *     comfortNoiseEnabled: true,
 *     comfortNoiseLevelDb: -40,
 *   });
 *   scheduler.scheduleBuffer(decodedAudioBuffer);
 *   scheduler.reset();
 */
'use strict';

/**
 * @param {AudioContext} audioCtx
 * @param {object} [opts]
 * @param {number} [opts.jitterBufferSec=0.25]  Safety margin (seconds) when
 *        re-anchoring after a gap.
 * @param {boolean} [opts.comfortNoiseEnabled=true]  Whether to play comfort
 *        noise when the queue is empty.
 * @param {number} [opts.comfortNoiseLevelDb=-40]  Comfort noise amplitude
 *        in dB (relative to full scale).
 * @param {number} [opts.comfortNoiseFadeSec=0.5]  Fade-in/out duration for
 *        comfort noise transitions.
 * @returns {object} AudioScheduler public API
 */
function createAudioScheduler(audioCtx, opts) {
  opts = opts || {};

  var JITTER_BUFFER_SEC = typeof opts.jitterBufferSec === 'number'
    ? opts.jitterBufferSec : 0.25;
  var COMFORT_NOISE_ENABLED = opts.comfortNoiseEnabled !== false;
  var COMFORT_NOISE_LEVEL_DB = typeof opts.comfortNoiseLevelDb === 'number'
    ? opts.comfortNoiseLevelDb : -40;
  var COMFORT_NOISE_FADE_SEC = typeof opts.comfortNoiseFadeSec === 'number'
    ? opts.comfortNoiseFadeSec : 0.5;

  /** @type {number} audioCtx.currentTime when the last scheduled buffer ends */
  var nextScheduledTime = 0;

  /** @type {AudioBufferSourceNode|null} Currently playing comfort noise source */
  var comfortNoiseSource = null;
  /** @type {GainNode|null} Gain node for comfort noise fade-in/out */
  var comfortNoiseGain = null;
  /** @type {AudioBuffer|null} Cached comfort noise buffer (2 seconds, looping) */
  var comfortNoiseBuffer = null;
  /** @type {boolean} Whether comfort noise is currently audible */
  var comfortNoiseActive = false;

  // ── Comfort noise ──────────────────────────────────────────────────────

  /**
   * Create a short noise buffer for looping.  Uses white noise shaped to
   * the target dB level — sounds like quiet "room tone".
   */
  function getComfortNoiseBuffer() {
    if (comfortNoiseBuffer) return comfortNoiseBuffer;

    var sampleRate = audioCtx.sampleRate;
    var length = Math.floor(sampleRate * 2); // 2-second loop
    var buffer = audioCtx.createBuffer(1, length, sampleRate);
    var data = buffer.getChannelData(0);

    // Convert dB to linear amplitude: 10^(dB/20)
    var amplitude = Math.pow(10, COMFORT_NOISE_LEVEL_DB / 20);

    for (var i = 0; i < length; i++) {
      // White noise: random values in [-amplitude, +amplitude]
      data[i] = (Math.random() * 2 - 1) * amplitude;
    }

    comfortNoiseBuffer = buffer;
    return buffer;
  }

  function startComfortNoise() {
    if (!COMFORT_NOISE_ENABLED || comfortNoiseActive) return;
    if (audioCtx.state === 'closed' || audioCtx.state === 'suspended') return;

    try {
      comfortNoiseGain = audioCtx.createGain();
      comfortNoiseGain.gain.setValueAtTime(0, audioCtx.currentTime);
      comfortNoiseGain.gain.linearRampToValueAtTime(
        1, audioCtx.currentTime + COMFORT_NOISE_FADE_SEC
      );
      comfortNoiseGain.connect(audioCtx.destination);

      comfortNoiseSource = audioCtx.createBufferSource();
      comfortNoiseSource.buffer = getComfortNoiseBuffer();
      comfortNoiseSource.loop = true;
      comfortNoiseSource.connect(comfortNoiseGain);
      comfortNoiseSource.start(0);

      comfortNoiseActive = true;
    } catch (e) {
      // AudioContext may be in a bad state; silently fail
      comfortNoiseActive = false;
    }
  }

  function stopComfortNoise() {
    if (!comfortNoiseActive) return;

    try {
      if (comfortNoiseGain) {
        var now = audioCtx.currentTime;
        comfortNoiseGain.gain.cancelScheduledValues(now);
        comfortNoiseGain.gain.setValueAtTime(comfortNoiseGain.gain.value, now);
        comfortNoiseGain.gain.linearRampToValueAtTime(
          0, now + COMFORT_NOISE_FADE_SEC
        );
      }

      // Stop the source after fade-out completes
      if (comfortNoiseSource) {
        var src = comfortNoiseSource;
        setTimeout(function () {
          try { src.stop(); } catch (_) { /* already stopped */ }
        }, (COMFORT_NOISE_FADE_SEC + 0.1) * 1000);
      }
    } catch (_) {
      // Best effort cleanup
    }

    comfortNoiseSource = null;
    comfortNoiseGain = null;
    comfortNoiseActive = false;
  }

  // ── Idle detection ─────────────────────────────────────────────────────

  /** @type {number|null} Timer ID for the idle check */
  var idleTimer = null;

  /**
   * Called after each buffer is scheduled.  Sets a timer for when the queue
   * should be empty (nextScheduledTime).  If no new buffer is scheduled
   * before then, we start comfort noise.
   */
  function scheduleIdleCheck() {
    if (idleTimer !== null) {
      clearTimeout(idleTimer);
      idleTimer = null;
    }

    var now = audioCtx.currentTime;
    var delayMs = Math.max(0, (nextScheduledTime - now) * 1000) + 100;

    idleTimer = setTimeout(function () {
      idleTimer = null;
      if (audioCtx.currentTime >= nextScheduledTime) {
        startComfortNoise();
      }
    }, delayMs);
  }

  // ── Public API ─────────────────────────────────────────────────────────

  return {
    /**
     * Schedule an AudioBuffer for gapless playback.
     *
     * @param {AudioBuffer} audioBuffer  Decoded audio data to play.
     * @returns {{ startTime: number, endTime: number }}  The scheduled times.
     */
    scheduleBuffer: function (audioBuffer) {
      if (!audioBuffer || !audioBuffer.duration) {
        return { startTime: 0, endTime: 0 };
      }

      // Fade out comfort noise when real audio arrives
      stopComfortNoise();

      var now = audioCtx.currentTime;
      var startTime;

      if (nextScheduledTime <= now) {
        // Queue is empty or has fallen behind — re-anchor with jitter buffer
        startTime = now + JITTER_BUFFER_SEC;
      } else {
        // Schedule seamlessly after the last queued buffer
        startTime = nextScheduledTime;
      }

      var source = audioCtx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioCtx.destination);
      source.start(startTime);

      var endTime = startTime + audioBuffer.duration;
      nextScheduledTime = endTime;

      // Set up idle detection for comfort noise
      scheduleIdleCheck();

      return { startTime: startTime, endTime: endTime };
    },

    /**
     * @returns {boolean} True if no audio is currently scheduled for playback.
     */
    isIdle: function () {
      return audioCtx.currentTime >= nextScheduledTime;
    },

    /**
     * @returns {number} The audioCtx.currentTime when the last scheduled
     *          buffer will finish playing.
     */
    getNextScheduledTime: function () {
      return nextScheduledTime;
    },

    /**
     * Reset all scheduler state.  Stops comfort noise and clears the
     * scheduled time pointer.  Does NOT stop already-scheduled
     * AudioBufferSourceNodes (they will play to completion).
     */
    reset: function () {
      nextScheduledTime = 0;
      stopComfortNoise();
      if (idleTimer !== null) {
        clearTimeout(idleTimer);
        idleTimer = null;
      }
      comfortNoiseBuffer = null;
    },
  };
}

// Export for use from listener-event.js
export const AudioScheduler = { create: createAudioScheduler };
