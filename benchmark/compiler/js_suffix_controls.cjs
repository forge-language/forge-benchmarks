const crypto = require('node:crypto');
const fs = require('node:fs');
const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

if (config.disable_encode_into) delete TextEncoder.prototype.encodeInto;

globalThis.ForgeNative = {
  lower(value) { return value.toLowerCase(); },
  measure(repository, substring) {
    const start = BigInt(config.start);
    const length = BigInt(config.length);
    const call = config.urls ? repository : value => substring(value, start, length);
    const warm = Math.floor(config.count / 4);
    const pool = config.urls || Array.from(
      {length: config.distinct ? config.count + 2 * warm : 16},
      (_, index) => {
        const tag = 'case-id-' + String(index).padStart(8, '0');
        // Materialize flat strings before measurement, including unique warmup inputs.
        return Buffer.from(config.block.repeat(config.repeats) + tag).toString('utf8');
      });
    if (config.prime) substring('Z'.repeat(196608), 196589n, 16n);
    function run(offset, count, outputs) {
      let checksum = 0;
      for (let i = 0; i < count; i++) {
        const value = call(pool[(offset + i) % pool.length]);
        checksum += value.length * 31 + (value.charCodeAt(0) || 0) +
          (value.charCodeAt(value.length - 1) || 0);
        if (outputs) outputs[i] = value;
      }
      return checksum;
    }
    run(0, warm);
    run(warm, warm);
    const offset = config.distinct ? 2 * warm : 0;
    const begin = process.hrtime.bigint();
    const checksum = run(offset, config.count, null);
    const ns = Number(process.hrtime.bigint() - begin);
    // Independently verify the entire timed input domain after timing.
    const outputs = Array(config.distinct ? config.count : pool.length);
    run(offset, outputs.length, outputs);
    const digest = crypto.createHash('sha256').update(JSON.stringify(outputs)).digest('hex');
    console.log(JSON.stringify({ns, checksum, digest}));
    return 0n;
  }
};
