// Native app origins remain fixed. The loopback harness serves both UI and API.
window.APlusRuntime = Object.freeze({
  origin: location.protocol === 'http:' && location.hostname === '127.0.0.1'
    ? location.origin : 'https://app.a-esthetic.de',
});
