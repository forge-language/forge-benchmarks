const fs = require('node:fs');
const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

globalThis.ForgeNative = {
  stream_input(i) { return config.inputs[Number(i) % config.inputs.length]; },
  measure(digest, chars, brackets, at, views, stream) {
    const work = {digest, chars, brackets, at, views}[config.operation];
    const offset = BigInt(config.offset);
    const run = (start, count) => {
      if (config.operation === 'stream') return stream(BigInt(start), BigInt(count), offset);
      let result = 0n;
      for (let i = 0; i < count; i++) {
        const value = config.inputs[(start + i) % config.inputs.length];
        result += work(value, offset);
      }
      return result;
    };
    const warmup = Math.max(1, Math.floor(config.count / 4));
    run(0, warmup);
    run(warmup, warmup);
    const start = process.hrtime.bigint();
    const result = run(2 * warmup, config.count);
    const ns = Number(process.hrtime.bigint() - start);
    console.log(JSON.stringify({result: result.toString(), ns}));
    return 0n;
  }
};
