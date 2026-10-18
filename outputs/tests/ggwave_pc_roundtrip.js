// Run with the official ggwave npm package (0.4.0): node ggwave_pc_roundtrip.js.
// Set GGWAVE_JS_MODULE to the package path when it is not on NODE_PATH.
const assert = require('node:assert/strict');
const factory = require(process.env.GGWAVE_JS_MODULE || 'ggwave');

function through48k(pcm24) {
  const source = new Int16Array(pcm24.buffer, pcm24.byteOffset, pcm24.byteLength / 2);
  const upsampled = new Int16Array(source.length * 2);
  for (let i = 0; i < source.length; i++) {
    upsampled[2 * i] = source[i];
    upsampled[2 * i + 1] = Math.round((source[i] + source[Math.min(i + 1, source.length - 1)]) / 2);
  }
  const downsampled = new Int16Array(source.length);
  for (let i = 0; i < source.length; i++) {
    downsampled[i] = Math.trunc((upsampled[2 * i] + upsampled[2 * i + 1]) / 2);
  }
  return new Uint8Array(downsampled.buffer);
}

factory().then(ggwave => {
  const parameters = ggwave.getDefaultParameters();
  parameters.payloadLength = 16;
  parameters.sampleRateInp = 24000;
  parameters.sampleRateOut = 24000;
  parameters.sampleRate = 24000;
  parameters.samplesPerFrame = 512;
  parameters.sampleFormatInp = ggwave.SampleFormat.GGWAVE_SAMPLE_FORMAT_I16;
  parameters.sampleFormatOut = ggwave.SampleFormat.GGWAVE_SAMPLE_FORMAT_I16;
  const tx = ggwave.init(parameters);
  const rx = ggwave.init(parameters);
  for (const message of ['こんにちは', '你好', 'Hello']) {
    assert.ok(Buffer.byteLength(message, 'utf8') <= 16);
    const waveform = ggwave.encode(tx, message, ggwave.ProtocolId.GGWAVE_PROTOCOL_DT_FASTEST, 10);
    assert.ok(waveform.length > 0);
    const decoded = ggwave.decode(rx, through48k(waveform));
    assert.ok(decoded, `${message}: no payload decoded`);
    const bytes = Buffer.from(decoded).subarray(0, 16);
    const ending = bytes.indexOf(0);
    const text = bytes.subarray(0, ending < 0 ? 16 : ending).toString('utf8');
    assert.equal(text, message);
    console.log(`PASS ${message}: ${waveform.length} waveform bytes at 24 kHz`);
  }
  ggwave.free(tx);
  ggwave.free(rx);
}).catch(error => { console.error(error); process.exitCode = 1; });
