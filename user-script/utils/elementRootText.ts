export default function elementRootText(element: Element): string {
  let ret = "";
  for (const i of element.childNodes) {
    if (i.nodeType === i.TEXT_NODE) {
      ret += i.nodeValue;
    }
  }
  return ret.trim();
}
