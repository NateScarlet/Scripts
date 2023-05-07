export default function obtainHTMLElement<
  K extends keyof HTMLElementTagNameMap
>(
  tag: K,
  id: string,
  { onCreate }: { onCreate?: (el: HTMLElementTagNameMap[K]) => void } = {}
): HTMLElementTagNameMap[K] {
  const match = document.getElementById(id) as HTMLElementTagNameMap[K];
  if (match) {
    return match;
  }
  const el = document.createElement(tag);
  el.id = id;
  onCreate(el);
  return el;
}
