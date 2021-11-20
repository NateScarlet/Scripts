export default function unescapeHTML(input: string): string {
  const doc = new DOMParser().parseFromString(input, "text/html");
  return doc.documentElement.textContent;
}
