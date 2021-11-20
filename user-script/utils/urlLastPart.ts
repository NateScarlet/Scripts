export default function urlLastPart(url: string): string {
  return url
    .split("/")
    .filter((i) => i)
    .slice(-1)[0];
}
