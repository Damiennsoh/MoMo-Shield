/**
 * Encode recorded audio (webm/opus from MediaRecorder) into a 16-bit PCM WAV
 * blob. The demo backend's /transcribe endpoint only accepts RIFF/WAVE.
 */
export async function blobToWav(blob: Blob): Promise<Blob> {
  const arrayBuffer = await blob.arrayBuffer();
  const AudioCtx =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const ctx = new AudioCtx();
  try {
    const decoded = await ctx.decodeAudioData(arrayBuffer);
    const mono = downmixToMono(decoded);
    const sampleRate = mono.sampleRate;
    const pcm = floatTo16BitPCM(mono.getChannelData(0));
    return encodeWav(pcm, sampleRate, 1);
  } finally {
    void ctx.close();
  }
}

function downmixToMono(buffer: AudioBuffer): AudioBuffer {
  if (buffer.numberOfChannels === 1) return buffer;
  const length = buffer.length;
  const out = new Float32Array(length);
  for (let ch = 0; ch < buffer.numberOfChannels; ch++) {
    const data = buffer.getChannelData(ch);
    for (let i = 0; i < length; i++) out[i] += data[i] / buffer.numberOfChannels;
  }
  const mono = new AudioBuffer({ length, numberOfChannels: 1, sampleRate: buffer.sampleRate });
  mono.copyToChannel(out, 0);
  return mono;
}

function floatTo16BitPCM(input: Float32Array): DataView {
  const buffer = new ArrayBuffer(input.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return view;
}

function encodeWav(view: DataView, sampleRate: number, channels: number): Blob {
  const dataLength = view.byteLength;
  const buffer = new ArrayBuffer(44 + dataLength);
  const v = new DataView(buffer);
  const writeStr = (off: number, s: string) => {
    for (let i = 0; i < s.length; i++) v.setUint8(off + i, s.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  v.setUint32(4, 36 + dataLength, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  v.setUint32(16, 16, true); // PCM chunk size
  v.setUint16(20, 1, true); // PCM format
  v.setUint16(22, channels, true);
  v.setUint32(24, sampleRate, true);
  v.setUint32(28, sampleRate * channels * 2, true); // byte rate
  v.setUint16(32, channels * 2, true); // block align
  v.setUint16(34, 16, true); // bits per sample
  writeStr(36, "data");
  v.setUint32(40, dataLength, true);
  new Uint8Array(buffer, 44).set(new Uint8Array(view.buffer));
  return new Blob([buffer], { type: "audio/wav" });
}
