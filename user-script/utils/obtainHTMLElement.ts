export default function obtainHTMLElement<
  K extends keyof HTMLElementTagNameMap
>(tag: K, id: string): { el: HTMLElementTagNameMap[K]; isCreated: boolean } {
  const match = document.getElementById(id) as HTMLElementTagNameMap[K];
  if (match) {
    return { el: match, isCreated: false };
  }
  const el = document.createElement(tag);
  el.id = id;
  return {
    el,
    isCreated: true,
  };
}
