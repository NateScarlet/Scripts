export default function parseHeader(headers: string): Map<string, string[]> {
  const ret: Map<string, string[]> = new Map();
  for (const line of headers.split("\r\n")) {
    if (!line) {
      continue;
    }
    const match = /^(.+?): ?(.+)$/.exec(line);
    if (!match) {
      throw new Error(`malformed header: ${line}`);
    }
    const [_, key, value] = match;
    if (!ret.has(key)) {
      ret.set(key, []);
    }
    ret.get(key).push(value);
  }
  return ret;
}
