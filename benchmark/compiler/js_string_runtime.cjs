const fs = require('node:fs');
const {createHash} = require('node:crypto');
const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

globalThis.ForgeNative = {
  js_measure(length, append, report) {
    const work = {length, append, report}[config.operation];
    const inputs = config.boxed ? config.inputs.map(value => Object(value)) : config.inputs;
    const count = BigInt(config.iterations);
    const warmup = BigInt(Math.max(1, Math.floor(config.iterations / 4)));
    work(...inputs, warmup);
    work(...inputs, warmup);
    const start = process.hrtime.bigint();
    const value = work(...inputs, count);
    const ns = Number(process.hrtime.bigint() - start);
    const result = typeof value === 'bigint' ? value.toString()
      : createHash('sha256').update(value, 'utf8').digest('hex');
    console.log(JSON.stringify({ns, result}));
    return 0n;
  }
};
