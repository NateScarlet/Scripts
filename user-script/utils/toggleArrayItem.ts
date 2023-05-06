export default function toggleArrayItem<T>(
  arr: Pick<T[], 'findIndex' | 'splice'>,
  item: T,
  {
    force,
    prepend = false,
    equal = (a, b) => a === b,
  }: {
    force?: boolean;
    prepend?: boolean;
    equal?: (a: T, b: T) => boolean;
  } = {}
) {
  let index = arr.findIndex((i) => equal(item, i));
  const current = index >= 0;
  const wanted = force ?? !current;
  if (current === wanted) {
    return;
  }
  if (wanted) {
    arr.splice(prepend ? 0 : -1, 0, item);
  } else {
    while (index >= 0) {
      arr.splice(index, 1);
      index = arr.findIndex((i) => equal(item, i));
    }
  }
}
