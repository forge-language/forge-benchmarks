const fs = require('node:fs');
const crypto = require('node:crypto');
const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const inputs = config.inputs.map(([text, start, length]) => [text, BigInt(start), BigInt(length)]);

globalThis.ForgeNative = {
  lower(value) { return value.toLowerCase(); },
  measure(repository, substring) {
    const call = config.operation === 'repository'
      ? ([value]) => repository(value)
      : ([value, start, length]) => substring(value, start, length);
    const outputs = inputs.map(call);
    const digest = crypto.createHash('sha256').update(JSON.stringify(outputs)).digest('hex');
    function run(count) {
      let checksum = 0;
      for (let i = 0; i < count; i++) {
        const value = call(inputs[i % inputs.length]);
        checksum += value.length * 31 + (value.charCodeAt(0) || 0) +
          (value.charCodeAt(value.length - 1) || 0);
      }
      return checksum;
    }
    run(Math.floor(config.count / 4));
    run(Math.floor(config.count / 4));
    const start = process.hrtime.bigint();
    const checksum = run(config.count);
    const ns = Number(process.hrtime.bigint() - start);
    console.log(JSON.stringify({digest, checksum, ns}));
    return 0n;
  }
};
